# CallMetricAI — Faster-Whisper ve Ollama ile Konuşma Analizi

Bu proje, sesi yerel olarak metne çevirmek ve konuşmayı Ollama üzerinden analiz etmek
için hazırlanmış bir Python uygulamasıdır. İki bağımsız çalışma biçimi sunar:

1. **Canlı mikrofon modu:** Varsayılan mikrofonu dinler, sessizlikle tamamlanan
   cümleyi Faster-Whisper ile yazıya çevirir ve kısa bir Ollama analizi gösterir.
2. **Offline stereo çağrı modu:** Sol ve sağ kanaldaki konuşmacıları ayrı ayrı
   transkribe eder; ortak zaman çizelgesini, konuşma çakışmalarını, kanal kalitesini,
   yapılandırılmış çağrı analizini ve denetim kayıtlarını üretir.

Her iki mod da yerel çalışır. Ses veya transcript için harici bir bulut servisi
zorunlu değildir; ancak ilk Whisper modelinin indirilmesi için internet bağlantısı
gerekir.

## İş akışları

### Canlı mikrofon

```text
Mikrofon
  → enerji tabanlı konuşma/sessizlik algılama
  → Faster-Whisper
  → terminalde transcript
  → Ollama /api/chat
  → terminalde kısa analiz
```

Konuşma bellekte tutulur ve ses dosyası diske yazılmaz. Varsayılan ayarlarda en az
250 ms konuşma algılandıktan sonra kayıt başlar; yaklaşık 800 ms sessizlikte veya
15 saniyelik üst sınırda cümle tamamlanır.

### Offline stereo çağrı

```text
Stereo WAV (L=agent, R=customer)
  → biçim doğrulama ve 16 kHz'e resampling
  → senkron mono kanallara ayırma
  → kanal kalitesi + kanal bazlı enerji VAD
  → aynı Faster-Whisper modeliyle sıralı transkripsiyon
  → kelime zamanlarına göre segment normalizasyonu
  → mutlak zamanlı ortak timeline + overlap tespiti
  → Ollama ile kanıta bağlı JSON analiz
  → result.json + audit.json + report.md + pipeline.log
```

Stereo ses birleştirilip Whisper'a verilmez. İki kanal aynı örnek ekseninden
çıkarılır ve eşit uzunlukta tutulur. Böylece sessizlikler ve eşzamanlı konuşmalar
kaybolmaz. Çakışma tespiti transcript segmentlerinden değil, her kanalın bağımsız
ses aktivitesi aralıklarından yapılır.

## Gereksinimler

- Windows 10/11 (canlı mikrofon yönergeleri Windows içindir)
- Python 3.10 veya üzeri
- Canlı mod için çalışan bir mikrofon
- Yerel olarak çalışan [Ollama](https://ollama.com/)
- İlk Faster-Whisper modeli ve Ollama modeli için internet bağlantısı

Temel Python bağımlılıkları:

- `faster-whisper`: konuşmayı metne çevirme
- `sounddevice`: canlı mikrofon girişi
- `soundfile`: WAV okuma/yazma
- `numpy`: ses ve sinyal işlemleri
- `soxr`: stereo dosyaları 16 kHz'e dönüştürme
- `python-dotenv`: `.env` yapılandırması

## Kurulum

PowerShell'de proje klasörüne girin:

```powershell
cd simple_console_whisper_ollama
```

Sanal ortamı oluşturup bağımlılıkları kurun:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Örnek ortam dosyasını kopyalayın:

```powershell
Copy-Item .env.example .env
```

Ollama'yı kurduktan sonra modeli indirin:

```powershell
ollama pull gemma2:2b
```

Ollama çoğu Windows kurulumunda arka planda çalışır. Gerekirse ayrı bir terminalde
başlatın:

```powershell
ollama serve
```

Servisi ve kurulu modelleri kontrol etmek için:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
ollama list
```

## Yapılandırma

Uygulamalar açılışta `.env` dosyasını yükler.

| Değişken | Varsayılan | Açıklama |
|---|---:|---|
| `WHISPER_MODEL` | `tiny` | Faster-Whisper model adı |
| `WHISPER_DEVICE` | `cpu` | `cpu` veya uygun sistemde `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU/GPU hesaplama türü |
| `WHISPER_LANGUAGE` | `tr` | Dil kodu; stereo modda `auto` da kullanılabilir |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama servis adresi |
| `OLLAMA_MODEL` | `gemma2:2b` | Kurulu Ollama modeli |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Analiz isteği zaman aşımı |
| `SAMPLE_RATE` | `16000` | Canlı mikrofon örnekleme hızı |
| `BLOCK_MS` | `50` | Canlı ses blok süresi |
| `SPEECH_THRESHOLD` | `0.015` | Canlı mod enerji eşiği |
| `MIN_SPEECH_MS` | `250` | Konuşma başlangıcı için gereken süre |
| `END_SILENCE_MS` | `800` | Cümleyi bitiren sessizlik süresi |
| `MAX_UTTERANCE_SECONDS` | `15` | Tek canlı cümlenin azami süresi |

Daha iyi doğruluk için CPU üzerinde `small` model kullanılabilir:

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

NVIDIA GPU, uyumlu CUDA ve cuDNN kurulumu varsa:

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

Başka bir Ollama modeli kullanmak için önce modeli indirin, ardından `.env` dosyasını
güncelleyin:

```powershell
ollama pull qwen3:4b
```

```env
OLLAMA_MODEL=qwen3:4b
```

## Canlı mikrofon modunu çalıştırma

```powershell
.\venv\Scripts\python.exe main.py
```

İlk çalıştırmada seçili Whisper modeli otomatik indirilir. Terminalde `Hazır`
mesajını gördükten sonra konuşun ve cümle sonunda yaklaşık bir saniye sessiz kalın.

Örnek çıktı:

```text
[dinleniyor] Konuşma algılandı...
[Whisper] Metne çevriliyor...
[Siz] Bu ürünün fiyatı bana biraz yüksek geldi.
[Whisper] 0.82 sn | dil güveni: 98%
[Ollama] Yanıt bekleniyor...
[Ollama] Konu fiyat, baskın duygu kararsızlık...
```

Programı kapatmak için `Ctrl+C` kullanın.

### Mikrofon ayarı

Uygulama başlarken giriş cihazlarını listeler; `*` varsayılan mikrofonu gösterir.
Windows'ta şu izinlerin açık olduğunu kontrol edin:

```text
Ayarlar → Gizlilik ve güvenlik → Mikrofon
```

- Mikrofon erişimi
- Uygulamaların mikrofonunuza erişmesine izin ver
- Masaüstü uygulamalarının mikrofonunuza erişmesine izin ver

Cihazları elle listelemek için:

```powershell
.\venv\Scripts\python.exe -c "import sounddevice as sd; print(sd.query_devices())"
```

Konuşma algılanmıyorsa `SPEECH_THRESHOLD` değerini örneğin `0.008` seviyesine
düşürün. Ortam gürültüsü konuşma sayılıyorsa `0.025` gibi daha yüksek bir değer
kullanın. Cümleler erken bölünüyorsa `END_SILENCE_MS=1200` deneyin.

## Stereo çağrı modunu çalıştırma

Girdi iki kanallı bir ses dosyası olmalıdır. `soundfile` tarafından desteklenen
dosyalar okunabilse de proje sözleşmesi ve örnek komutlar stereo WAV üzerinedir.
Varsayılan kanal eşlemesi:

```text
Sol kanal  (0) → agent
Sağ kanal (1) → customer
```

En kısa komut:

```powershell
.\venv\Scripts\python.exe run_stereo.py .\gorusme.wav
```

Bu giriş noktası çıktıyı varsayılan olarak
`artifacts/stereo_pipeline/gorusme/` altında oluşturur. Dil ve çıktı klasörü
seçilebilir:

```powershell
.\venv\Scripts\python.exe run_stereo.py .\gorusme.wav `
  --output-dir .\artifacts\gorusme_run `
  --language auto
```

Alternatif, bileşen tabanlı CLI kanal adlarını da değiştirebilir:

```powershell
.\venv\Scripts\python.exe -m stereo_pipeline.cli .\gorusme.wav `
  --output-dir .\artifacts\gorusme_run `
  --left-speaker temsilci `
  --right-speaker musteri `
  --language tr
```

`run_stereo.py` ile `python -m stereo_pipeline.cli` aynı temel bileşenleri kullanır.
İlk komut kolay kullanımlı `StereoPipeline` facade'ını ve `pipeline.log` çıktısını;
ikinci komut ise doğrudan `StereoProcessingPipeline` orkestrasyonunu kullanır.

### Python API

```python
from StereoPipeline import StereoPipeline

pipeline = StereoPipeline(language="tr")
result = pipeline.analyze("gorusme.wav")

print(result.full_transcript)
print(result.analysis)
print(result.timeline.overlap_pairs)
```

Otomatik dil algılama:

```python
pipeline = StereoPipeline(language="auto")
result = pipeline.analyze("gorusme.wav")
```

Bağımlılıklar constructor üzerinden enjekte edilebilir. Bu sayede farklı
transcriber, analiz servisi, VAD, segment ayırıcı veya ses işleyici adaptörleri
kullanılabilir. İş hattının herkese açık adımları da ayrı ayrı çağrılabilir:

```python
channels = pipeline.split_channels("gorusme.wav")
quality = pipeline.measure_channel_quality(channels)
activity = pipeline.detect_speech_activity(channels)

agent_segments = pipeline.transcribe_channel(channels[0])
customer_segments = pipeline.transcribe_channel(channels[1])

timeline = pipeline.merge_transcripts(
    {
        "agent": tuple(agent_segments),
        "customer": tuple(customer_segments),
    },
    activity,
)
analysis = pipeline.send_to_analysis(timeline)
```

### Üretilen çıktılar

```text
artifacts/stereo_pipeline/<dosya_adı>/
├── result.json
├── audit.json
├── report.md
└── pipeline.log
```

- `result.json`: Kaynak bilgisi, kanal kalite ölçümleri, kanal transcriptleri,
  konuşma aktivitesi, timeline, overlap aralıkları, analiz, doğrulama, audit ve
  süre izlerini içeren tam makine çıktısı.
- `audit.json`: İşleme sırasını ve analiz girdisi/çıktısını olay bazında gösteren
  denetim kaydı.
- `report.md`: Kanal kalitesi, ortak timeline, analiz, doğrulama ve aşama sürelerinin
  okunabilir raporu.
- `pipeline.log`: Audit olaylarının satır bazlı JSON kaydı.

Ollama analizinin yapılandırılmış alanları şunlardır:

```text
emotion, need, topic, intent, objection_type, conversation_stage,
recommended_action, confidence, evidence_segment_ids
```

`evidence_segment_ids` yalnız gerçek timeline segmentlerinden seçilir. Kolay
kullanımlı facade, modelin ürettiği geçersiz kanıt kimliklerini atar ve audit
kaydında raporlar.

## Referans transcript ile doğrulama

İnsan etiketli referans verilirse sistem konuşmacı bazlı WER, kelime timestamp
hatası, zaman drift'i ve beklenen/detected overlap sayılarını hesaplar:

```powershell
.\venv\Scripts\python.exe run_stereo.py .\gorusme.wav `
  --output-dir .\artifacts\gorusme_run `
  --reference-json .\reference.json `
  --language auto
```

Referans dosyası bir JSON listesi olmalıdır. Varsayılan rol eşlemesi
`agent → agent`, `caller → customer` biçimindedir:

```json
[
  {
    "index": 0,
    "speaker_role": "agent",
    "start_ms": 500,
    "duration_ms": 1200,
    "human_transcript": "Merhaba, nasıl yardımcı olabilirim?",
    "word_offsets_ms": [0, 250, 500, 850, 1050]
  },
  {
    "index": 1,
    "speaker_role": "caller",
    "start_ms": 1500,
    "duration_ms": 1800,
    "human_transcript": "Fiyat hakkında bilgi almak istiyorum.",
    "word_offsets_ms": [0, 280, 650, 950, 1250, 1500]
  }
]
```

Referans verilmediğinde yalnız yapısal kontroller yapılır; gerçek ASR doğruluğu ve
timestamp drift'i ölçülmüş sayılmaz.

## Opsiyonel queue entegrasyonu

Whisper ve analiz queue kancaları varsayılan olarak kapalıdır; normal kullanımda
broker bağlantısı kurulmaz ve mono ara dosyalar yazılmaz.

```python
from StereoPipeline import QueueOptions, StereoPipeline

pipeline = StereoPipeline(
    queue_options=QueueOptions(
        whisper_enabled=True,
        analysis_enabled=True,
    ),
    queue_publisher=my_queue_publisher,
)
```

`my_queue_publisher`, aşağıdaki metoda sahip bir RabbitMQ, Kafka veya başka broker
adaptörü olabilir:

```python
def publish(queue_name: str, payload: dict) -> None:
    ...
```

Çalıştırma:

```powershell
.\venv\Scripts\python.exe -m stereo_pipeline.cli .\ornek_stereo.wav `
  --output-dir .\artifacts\stereo_run
```

### RabbitMQ'yu Docker ile çalıştırma

RabbitMQ servisi `docker-compose.yml` ile hazırlanmıştır. Docker Desktop açıkken:

```powershell
docker compose up -d rabbitmq
```

Servis durumunu kontrol etmek için:

```powershell
docker compose ps
docker compose logs rabbitmq
```

Yönetim ekranı varsayılan olarak:

```text
http://localhost:15672
```

Bağlantı, kullanıcı, parola, vhost ve queue adları kaynak koddan değil `.env`
dosyasından okunur:

```env
STEREO_QUEUE_BACKEND=rabbitmq
STEREO_WHISPER_QUEUE_ENABLED=false
STEREO_ANALYSIS_QUEUE_ENABLED=false
STEREO_WHISPER_QUEUE_NAME=stereo.whisper
STEREO_ANALYSIS_QUEUE_NAME=stereo.analysis

RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672
RABBITMQ_USER=stereo
RABBITMQ_PASSWORD=stereo-change-me
RABBITMQ_VHOST=/
```

Queue entegrasyonunu açmak için yalnız şu değerleri değiştirin:

```env
STEREO_WHISPER_QUEUE_ENABLED=true
STEREO_ANALYSIS_QUEUE_ENABLED=true
```

Ardından normal stereo komutunu çalıştırın:

```powershell
.\venv\Scripts\python.exe .\run_stereo.py .\gorusme.wav --language auto
```

Bu durumda iki ayrılmış mono kanal `stereo.whisper` queue'suna, final transcript
ve timeline ise `stereo.analysis` queue'suna kalıcı JSON mesaj olarak gönderilir.
Yerel offline Whisper ve Ollama işlemleri de çalışmaya devam eder. RabbitMQ'yu
durdurmak için:

```powershell
docker compose down
```

RabbitMQ verileri named volume içinde korunur. Veriyi de silmek isterseniz
ayrıca `docker compose down -v` kullanılmalıdır.

Varsayılan queue adları `stereo.whisper` ve `stereo.analysis` şeklindedir. Whisper
queue etkinse her kanal `queue_payloads/` altında mono WAV olarak yazılır ve dosya
yolu ile kanal metadatası yayınlanır. Analiz queue mesajı final transcript,
speaker-labelled timeline ve overlap çiftlerini içerir.

Yerel entegrasyon testleri için `InMemoryQueuePublisher` hazır gelir.

## Yardımcı araçlar

Deterministik test stereo WAV'ı üretmek:

```powershell
.\venv\Scripts\python.exe tools\generate_stereo_fixture.py
```

İki mono dosyayı başlangıç ofsetlerini koruyarak stereo dosyada birleştirmek:

```powershell
.\venv\Scripts\python.exe tools\compose_stereo_fixture.py `
  --left .\agent.wav `
  --right .\customer.wav `
  --left-offset 0.5 `
  --right-offset 1.5 `
  --output .\stereo_agent_customer.wav
```

## Testler

Tüm otomatik testleri çalıştırmak için:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testler stereo kanal kimliği ve senkronizasyonu, resampling, mono girdi reddi,
kanal kalite ölçümleri, ses tabanlı overlap tespiti, timeline sıralaması, segment
normalizasyonu, Ollama kanıt doğrulaması, queue davranışı, çıktı üretimi ve
referans bazlı WER/drift hesaplarını kapsar.

## Proje yapısı

```text
.
├── main.py                         # Canlı mikrofon uygulaması
├── run_stereo.py                   # Kolay kullanımlı stereo CLI
├── StereoPipeline.py               # Geriye uyumlu kısa import noktası
├── stereo_pipeline/
│   ├── activity.py                 # Kanal bazlı enerji VAD
│   ├── analysis.py                 # Ollama analiz adaptörü ve sonuç şeması
│   ├── audio.py                    # Stereo doğrulama, split, resampling, kalite
│   ├── cli.py                      # Bileşen tabanlı stereo CLI
│   ├── models.py                   # Immutable domain modelleri
│   ├── pipeline.py                 # Temel orkestrasyon
│   ├── postprocessing.py           # Kelime boşluğuna göre segment ayırma
│   ├── queueing.py                 # Opsiyonel queue sınırları
│   ├── reporting.py                # JSON, audit ve Markdown çıktıları
│   ├── stereo_entry.py             # Yüksek seviyeli StereoPipeline facade'ı
│   ├── timeline.py                 # Timeline ve overlap birleştirme
│   ├── transcription.py            # Faster-Whisper adaptörü
│   └── validation.py               # Referans WER, timing ve overlap doğrulaması
├── tests/                          # Deterministik unit/integration testleri
├── tools/                          # Fixture ve rapor yardımcıları
├── requirements.txt
└── .env.example
```

Daha ayrıntılı mimari ve test değerlendirmesi için
[`STEREO_PIPELINE_REPORT.md`](STEREO_PIPELINE_REPORT.md) dosyasına bakabilirsiniz.

## Yaygın sorunlar

### Ollama servisine bağlanılamıyor

```powershell
ollama serve
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

### `model ... not found`

`.env` içindeki model adının kurulu olduğundan emin olun:

```powershell
ollama pull gemma2:2b
```

### Whisper modeli indirilemiyor

İnternet bağlantısını kontrol edip tekrar deneyin. Gerekirse Hugging Face Xet
aktarımını o terminal için kapatın:

```powershell
$env:HF_HUB_DISABLE_XET='1'
.\venv\Scripts\python.exe main.py
```

### CUDA veya DLL hatası

Uyumlu CUDA/cuDNN kurulumu yoksa CPU ayarlarına dönün:

```env
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

### Stereo dosya reddediliyor

Offline iş hattı tam olarak iki kanal bekler. Mono veya ikiden fazla kanallı
dosyalar `StereoAudioError` ile reddedilir. Sol ve sağ kanalın doğru konuşmacıları
taşıdığını ayrıca doğrulayın.

## Bilinen sınırlar

- Canlı mod tek mikrofon ve basit enerji eşiği kullanır; gelişmiş gürültü bastırma
  veya konuşmacı diarization yapmaz.
- Stereo mod diarization yerine kanal kimliğine güvenir. Yanlış L/R kayıt,
  konuşmacı etiketlerini de yanlış üretir.
- Gerçek analiz için Ollama servisinin çalışması ve seçilen modelin kurulu olması
  gerekir.
- Model indirmesi dışında işlem yereldir; yine de hassas kayıtların saklama ve
  erişim politikasını çıktı klasörleri için ayrıca belirlemelisiniz.
