# Modüler Stereo Whisper İş Hattı — Uygulama ve Test Raporu

## 1. Kapsam

Bu ek sistem, mevcut `main.py` canlı mikrofon uygulamasını değiştirmeden offline
stereo görüşmeleri işler. Kaynak rapordaki temel sözleşme uygulanmıştır:

- Sol kanal `agent`, sağ kanal `customer` olarak adlandırılır.
- Stereo ses Whisper'a doğrudan verilmez.
- Kanallar ayrı mono waveform olarak çevrilir.
- Her iki kanalın görüşme başlangıcına göre sessizlikleri ve örnek sayısı korunur.
- Segmentler `(start, end, channel_id, segment_id)` anahtarıyla kararlı biçimde sıralanır.
- Eşzamanlı konuşmalar korunur ve ayrıca `overlap_pairs` olarak işaretlenir.
- Analiz katmanı yalnız konuşmacı etiketli final timeline'ı alır.

## 2. Modüler mimari

| Modül | Sınıf / arayüz | Sorumluluk |
|---|---|---|
| `audio.py` | `StereoAudioProcessor` | Stereo doğrulama, L/R ayırma, HQ resample, kalite ölçümü |
| `transcription.py` | `ChannelTranscriber` | Değiştirilebilir ASR sözleşmesi |
| `transcription.py` | `FasterWhisperTranscriber` | Tek modelle kanal bazlı final transkripsiyon |
| `activity.py` | `EnergySpeechActivityDetector` | Kanal bazlı konuşma aralıkları ve overlap otoritesi |
| `postprocessing.py` | `TranscriptSegmentSplitter` | Kelime sessizliklerinden geniş ASR segmentlerini bölme |
| `timeline.py` | `TimelineMerger` | Kararlı sıralama ve VAD tabanlı konuşma çakışmalarını koruma |
| `analysis.py` | `ConversationAnalyzer` | Değiştirilebilir analiz sözleşmesi |
| `analysis.py` | `OllamaConversationAnalyzer` | JSON analiz, şema ve evidence doğrulaması |
| `pipeline.py` | `StereoProcessingPipeline` | Aşamaların orkestrasyonu ve süre izleri |
| `validation.py` | `ReferenceTranscriptValidator` | WER, zaman drift'i ve golden overlap doğrulaması |
| `reporting.py` | `ResultReporter` | Result, audit JSON ve Markdown çıktı |

Model bağımlı sınırlar arayüz arkasındadır. Böylece testlerde deterministik
transcriber/analyzer; gerçek çalıştırmada Faster-Whisper/Ollama kullanılabilir.

## 3. Zaman kaymasını önleme yöntemi

Dosya tam uzunlukta iki kanallı dizi olarak okunur. Sol ve sağ kanallar aynı frame
indekslerinden çıkarılır. Yeniden örnekleme gerekiyorsa her iki kanal aynı kaynak ve
hedef hızla HQ SOXR üzerinden çevrilir; olası tek örneklik yuvarlama farkı iki kanala
ortak son uzunluk uygulanarak giderilir. Kanal bazında ayrı sessizlik kesme ve kalan
parçaları uç uca ekleme yapılmaz.

Bu tasarım pipeline kaynaklı drift üretmez. Whisper segment/kelime zamanları model
tahminidir ve enerji başlangıcından birkaç yüz milisaniye önce/sonra gelebilir; bu
ASR sınır belirsizliğidir, kanalların örnek ekseninin kayması değildir.

## 4. Otomatik test sonucu

Komut:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Sonuç: **9/9 başarılı**

Doğrulanan davranışlar:

1. 16 kHz stereo L/R kanal kimliği ve 48.000 örneklik ortak süre korunuyor.
2. 48 kHz giriş HQ resample sonrasında iki kanalda eşit 16 kHz/48.000 örnek oluyor.
3. Mono dosya yanlışlıkla stereo kabul edilmiyor.
4. RMS, sessizlik ve korelasyon kanal bazında ölçülüyor.
5. Timeline kronolojik ve deterministik; agent/customer çakışması kaybolmuyor.
6. Uçtan uca orkestrasyon yalnız birleşmiş timeline'ı analize veriyor ve altı aşamayı izliyor.
7. Kanal VAD aralıkları transcript sınırlarından bağımsız overlap tespit ediyor.
8. Uzun Whisper segmentleri kelime zamanlarındaki sessizliklere göre otomatik bölünüyor.
9. Referans doğrulayıcı WER, timestamp drift'i ve beklenen overlap sayısını raporluyor.

## 5. Gerçek modelle örnek stereo çalıştırma

Windows yerel konuşma senteziyle iki ayrı mono kayıt üretildi:

- Agent: “Hello, how can I help you today?”
- Customer: “The package is good, but it is too expensive for my budget.”

Agent 0,5 sn; customer 1,5 sn ortak görüşme eksenine yerleştirildi. Dosya 16 kHz
PCM16 stereo olarak işlendi. Gerçek Faster-Whisper `tiny/cpu/int8`, otomatik dil
algılama ve gerçek `gemma2:2b` Ollama servisi kullanıldı.

Ölçülen fixture enerji başlangıçları:

- Agent: 0,603 sn
- Customer: 1,605 sn
- Kanal başlangıç farkı: 1,002 sn (hedef: 1,000 sn)

Whisper çıktısı:

- Agent: 0,270–2,790 — “Hello, how can I help you today?”
- Customer: 1,230–4,850 — “The package is good, but it is too expensive for my budget.”
- Segment: 2
- Çakışma: 1

İki kanal da doğru konuşmacıya atanmış ve metinler doğru çevrilmiştir. Whisper'ın
iki segment başlangıcındaki model padding farkı yaklaşık aynı olduğundan kanalların
birbirine göre hizası korunmuştur.

Örnek işlem süreleri:

| Aşama | Süre |
|---|---:|
| Stereo yükleme ve ayırma | 1,442 ms |
| Kalite ölçümü | 1,621 ms |
| Agent ASR | 556,615 ms |
| Customer ASR | 433,828 ms |
| Timeline merge | 0,022 ms |
| Ollama analiz | 1.449,017 ms |

Ollama müşteri fiyat itirazını `package cost / price` olarak belirlemiş ve yalnız
`customer-0000` segmentini kanıt göstermiştir. Üretilen evidence kimliği timeline
içinde doğrulanmıştır.

## 6. Sınırlar ve sonraki entegrasyon

Bu faz offline dosya işleme içindir. Canlı sisteme geçerken aynı arayüzler korunup
dosya okuyucu yerine kanal buffer/VAD utterance üreticisi bağlanabilir. O fazda
mutlak zaman kuralı `utterance_absolute_start + whisper_relative_start` olarak
uygulanmalı; jitter/reorder, kayıp pakette eş süreli sessizlik, backpressure ve
kanal başına ayrı VAD state eklenmelidir.
