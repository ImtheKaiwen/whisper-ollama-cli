# Konsolda Faster-Whisper + Ollama

Bu küçük uygulama tarayıcı veya web sunucusu kullanmaz. Bilgisayarın varsayılan mikrofonunu doğrudan dinler:

```text
Mikrofon → sessizlik algılama → Faster-Whisper → terminalde metin → Ollama → terminalde analiz
```

Konuşma sırasında ses bellekte tutulur. Cümleden sonra yaklaşık 800 ms sessizlik olduğunda ses metne çevrilir ve metin Ollama'ya gönderilir. Ses dosyası diske kaydedilmez.

## 1. Gereksinimler

- Windows 10/11
- Python 3.10 veya üzeri
- Çalışan bir mikrofon
- Ollama
- İlk Whisper modeli ve Ollama modeli için internet bağlantısı

## 2. Projeyi kurma

PowerShell'de bu klasöre girin:

```powershell
cd simple_console_whisper_ollama
```

Sanal ortam oluşturun:

```powershell
python -m venv venv
```

Bağımlılıkları kurun:

```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Ortam dosyasını oluşturun:

```powershell
Copy-Item .env.example .env
```

## 3. Ollama kurulumu

Ollama'nın Windows kurulum dosyasını şu adresten indirin:

```text
https://ollama.com/download/windows
```

Kurulumdan sonra yeni bir PowerShell açıp kontrol edin:

```powershell
ollama --version
```

Türkçe için kullanılacak modeli indirin:

```powershell
ollama pull gemma2:2b
```

Ollama çoğu Windows kurulumunda arka planda otomatik çalışır. Çalışmıyorsa ayrı bir terminalde başlatın:

```powershell
ollama serve
```

Servisi kontrol etmek için:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

İndirilmiş modelleri görmek için:

```powershell
ollama list
```

Başka bir model kullanmak isterseniz önce modeli indirin, sonra `.env` içindeki `OLLAMA_MODEL` değerini değiştirin. Örneğin:

```powershell
ollama pull qwen3:4b
```

```env
OLLAMA_MODEL=qwen3:4b
```

## 4. Uygulamayı çalıştırma

Önce Ollama'nın çalıştığından emin olun. Sonra proje klasöründe:

```powershell
.\venv\Scripts\python.exe main.py
```

İlk çalıştırmada Faster-Whisper `tiny` modeli otomatik indirilir. İndirme tamamlanana kadar terminal bir süre `Faster-Whisper modeli yükleniyor...` satırında kalabilir.

Terminalde `Hazır` yazısını gördükten sonra konuşun. Cümlenizi bitirince yaklaşık bir saniye sessiz kalın:

```text
[dinleniyor] Konuşma algılandı...
[Whisper] Metne çevriliyor...
[Siz] Bu ürünün fiyatı bana biraz yüksek geldi.
[Ollama] Yanıt bekleniyor...
[Ollama] Konu fiyat, duygu kararsızlık...
```

Programı kapatmak için `Ctrl+C` kullanın.

## 5. Ayarlar

Tüm ayarlar `.env` dosyasındadır.

### Whisper modeli

Hızlı başlangıç:

```env
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Daha iyi doğruluk fakat daha fazla CPU/RAM kullanımı:

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

NVIDIA GPU ve gerekli CUDA/cuDNN kütüphaneleri hazırsa:

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

CUDA DLL hatası alırsanız CPU ayarlarına geri dönün. CPU modu ek sistem kurulumu gerektirmediği için varsayılandır.

### Sessizlik algılama

Mikrofon konuşmayı algılamıyorsa eşiği düşürün:

```env
SPEECH_THRESHOLD=0.008
```

Ortam gürültüsünü konuşma sanıyorsa yükseltin:

```env
SPEECH_THRESHOLD=0.025
```

Cümleyi çok erken bölüyorsa sessizlik süresini artırın:

```env
END_SILENCE_MS=1200
```

## 6. Mikrofon sorunları

Uygulama başlangıçta kullanılabilir mikrofonları listeler. `*` işaretli cihaz varsayılan giriş cihazıdır.

Windows'ta mikrofon iznini kontrol edin:

```text
Ayarlar → Gizlilik ve güvenlik → Mikrofon
```

Şunların açık olması gerekir:

- Mikrofon erişimi
- Uygulamaların mikrofonunuza erişmesine izin ver
- Masaüstü uygulamalarının mikrofonunuza erişmesine izin ver

Giriş cihazlarını ayrıca şu komutla görebilirsiniz:

```powershell
.\venv\Scripts\python.exe -c "import sounddevice as sd; print(sd.query_devices())"
```

Varsayılan mikrofon yanlışsa Windows ses ayarından doğru giriş cihazını varsayılan yapın.

## 7. Yaygın hatalar

### `Ollama hatası: Servise bağlanılamadı`

Ollama çalışmıyordur. Ayrı terminalde:

```powershell
ollama serve
```

### `model ... not found`

`.env` içindeki model indirilmemiştir:

```powershell
ollama pull gemma2:2b
```

### Whisper model indirmesi yarıda kaldı

İnternet bağlantısını kontrol edip uygulamayı tekrar çalıştırın. Gerekirse Hugging Face Xet aktarımını kapatın:

```powershell
$env:HF_HUB_DISABLE_XET='1'
.\venv\Scripts\python.exe main.py
```

### Sürekli konuşma algılanıyor

`SPEECH_THRESHOLD` değerini yükseltin. Örneğin `0.025`.

### Hiç konuşma algılanmıyor

Doğru mikrofonun varsayılan olduğundan emin olun ve `SPEECH_THRESHOLD` değerini `0.008` seviyesine düşürün.

