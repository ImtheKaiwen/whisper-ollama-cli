"""Mikrofon -> Faster-Whisper -> Ollama terminal uygulaması."""

from __future__ import annotations

import json
import os
import queue
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from faster_whisper import WhisperModel


load_dotenv()


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


SAMPLE_RATE = int(env("SAMPLE_RATE", "16000"))
BLOCK_MS = int(env("BLOCK_MS", "50"))
BLOCK_SIZE = SAMPLE_RATE * BLOCK_MS // 1000
SPEECH_THRESHOLD = float(env("SPEECH_THRESHOLD", "0.015"))
MIN_SPEECH_BLOCKS = max(1, int(env("MIN_SPEECH_MS", "250")) // BLOCK_MS)
END_SILENCE_BLOCKS = max(1, int(env("END_SILENCE_MS", "800")) // BLOCK_MS)
MAX_BLOCKS = max(1, int(float(env("MAX_UTTERANCE_SECONDS", "15")) * 1000) // BLOCK_MS)
PRE_ROLL_BLOCKS = max(1, 200 // BLOCK_MS)


@dataclass
class Config:
    whisper_model: str = env("WHISPER_MODEL", "tiny")
    whisper_device: str = env("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = env("WHISPER_COMPUTE_TYPE", "int8")
    whisper_language: str = env("WHISPER_LANGUAGE", "tr")
    ollama_url: str = env("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_model: str = env("OLLAMA_MODEL", "gemma2:2b")
    ollama_timeout: float = float(env("OLLAMA_TIMEOUT_SECONDS", "60"))


class SpeechSegmenter:
    """Basit enerji tabanlı VAD; sessizlikte tamamlanan float32 sesi döndürür."""

    def __init__(self) -> None:
        self.pre_roll: deque[np.ndarray] = deque(maxlen=PRE_ROLL_BLOCKS)
        self.frames: list[np.ndarray] = []
        self.speech_blocks = 0
        self.silence_blocks = 0
        self.speaking = False

    def add(self, block: np.ndarray) -> np.ndarray | None:
        level = float(np.sqrt(np.mean(np.square(block)))) if block.size else 0.0
        has_speech = level >= SPEECH_THRESHOLD

        if not self.speaking:
            self.pre_roll.append(block.copy())
            self.speech_blocks = self.speech_blocks + 1 if has_speech else 0
            if self.speech_blocks >= MIN_SPEECH_BLOCKS:
                self.speaking = True
                self.frames = list(self.pre_roll)
                self.pre_roll.clear()
                self.silence_blocks = 0
                print("\r[dinleniyor] Konuşma algılandı...                    ", end="", flush=True)
            return None

        self.frames.append(block.copy())
        self.silence_blocks = 0 if has_speech else self.silence_blocks + 1
        finished = self.silence_blocks >= END_SILENCE_BLOCKS or len(self.frames) >= MAX_BLOCKS
        if not finished:
            return None

        keep = len(self.frames) - self.silence_blocks
        audio = np.concatenate(self.frames[: max(1, keep)]).astype(np.float32)
        self.reset()
        return audio

    def flush(self) -> np.ndarray | None:
        if not self.frames:
            return None
        audio = np.concatenate(self.frames).astype(np.float32)
        self.reset()
        return audio

    def reset(self) -> None:
        self.frames = []
        self.speech_blocks = 0
        self.silence_blocks = 0
        self.speaking = False


def ask_ollama(text: str, config: Config) -> str:
    prompt = (
        "Aşağıdaki Türkçe konuşmayı kısa biçimde analiz et. "
        "Konuyu, baskın duyguyu, niyeti ve uygun kısa cevabı belirt.\n\n"
        f"Konuşma: {text}"
    )
    payload = json.dumps({
        "model": config.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": "Sen kısa ve faydalı yanıt veren bir Türkçe konuşma analiz asistanısın."},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.1},
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{config.ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.ollama_timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"].strip()
    except urllib.error.URLError as exc:
        return f"[Ollama hatası] Servise bağlanılamadı: {exc.reason}"
    except (KeyError, json.JSONDecodeError) as exc:
        return f"[Ollama hatası] Geçersiz cevap: {exc}"


def list_microphones() -> None:
    print("\nKullanılabilir giriş cihazları:")
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            marker = "*" if index == sd.default.device[0] else " "
            print(f" {marker} {index}: {device['name']}")


def main() -> int:
    config = Config()
    print("Faster-Whisper modeli yükleniyor...")
    try:
        model = WhisperModel(
            config.whisper_model,
            device=config.whisper_device,
            compute_type=config.whisper_compute_type,
        )
    except Exception as exc:
        print(f"Whisper modeli yüklenemedi: {exc}", file=sys.stderr)
        return 1

    audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
    segmenter = SpeechSegmenter()
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    def callback(indata: np.ndarray, frames: int, timing: object, status: sd.CallbackFlags) -> None:
        if status:
            print(f"\n[Ses uyarısı] {status}", file=sys.stderr)
        try:
            audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            print("\n[Ses uyarısı] Buffer doldu; ses bloğu atlandı.", file=sys.stderr)

    signal.signal(signal.SIGINT, stop)
    list_microphones()
    print("\nHazır. Konuşun; cümleden sonra yaklaşık 1 saniye sessiz kalın.")
    print("Çıkmak için Ctrl+C.\n")

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=callback,
        ):
            while running:
                try:
                    block = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                audio = segmenter.add(block)
                if audio is None:
                    continue

                print("\r[Whisper] Metne çevriliyor...                       ")
                started = time.perf_counter()
                segments, info = model.transcribe(
                    audio,
                    language=config.whisper_language,
                    task="transcribe",
                    beam_size=5,
                    vad_filter=False,
                    condition_on_previous_text=False,
                )
                text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
                if not text:
                    print("[Whisper] Anlaşılır bir konuşma bulunamadı.\n")
                    continue
                elapsed = time.perf_counter() - started
                print(f"[Siz] {text}")
                print(f"[Whisper] {elapsed:.2f} sn | dil güveni: {getattr(info, 'language_probability', 0):.0%}")
                print("[Ollama] Yanıt bekleniyor...")
                print(f"[Ollama] {ask_ollama(text, config)}\n")
    except sd.PortAudioError as exc:
        print(f"\nMikrofon açılamadı: {exc}", file=sys.stderr)
        print("README içindeki mikrofon sorunları bölümünü kontrol edin.", file=sys.stderr)
        return 1
    finally:
        print("\nProgram kapatıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

