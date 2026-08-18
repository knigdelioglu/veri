# Dataset Factory

Bu repo yalnız veri depolamaz; canonical kayıt üretimi, kalite kontrolü, split ve SFT exportu için küçük bir Python CLI içerir.

## Kurulum

Python 3.11+ gerekir.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Kurulumdan sonra `veri` komutu kullanılabilir.

## 1. Yeni kayıt oluşturma

```bash
veri new
```

Etkileşimli sihirbaz sınav türünü, sınıf düzeyini, soru/görevi, öğrenci cevabını veya doğrulanmış transkripti, rubrik ölçütlerini, puan çıpalarını ve kanıt kaynaklarını sorar.

Yeni kayıt bilinçli olarak `status: draft`, `pii_reviewed: false`, `needs_review: true` başlar. Sihirbazın oluşturduğu kayıt doğrudan eğitim verisi değildir; öğretmen gold puanlamasını ve anonimlik kontrolünü tamamlamalıdır.

## 2. Veri doğrulama

```bash
veri validate
```

Örnekleri de doğrulamak için:

```bash
veri validate --include-examples
```

Kontroller iki katmandır.

### JSON Schema

- zorunlu alanlar,
- veri tipleri,
- enum değerleri,
- ID biçimi,
- rubrik yapısı.

### Semantic invariant

- dosya adı ile kayıt ID'si aynı mı,
- modality doğru klasörde mi,
- rubrik `criterion_id` değerleri benzersiz mi,
- rubrik ile `criterion_results` birebir eşleşiyor mu,
- her ölçüt puanı kendi `max_score` sınırını aşıyor mu,
- rubrik maksimum puan toplamı `task.max_score` ile aynı mı,
- ölçüt puanları toplamı `total_score` ile aynı mı,
- `teacher_verified` kayıt `pii_reviewed=true` mu,
- `needs_review=true` için açıklama var mı,
- temel PII işaretleri görünüyor mu,
- konuşma gibi metin dışı kanıt isteyen ölçütlerde yapılandırılmış gözlem eksik mi.

`warning` exportu tek başına bloklamaz. `error` bloklar.

## 3. Tek kalite kapısı

```bash
veri check
```

Bu komut `validate + split leakage` kontrollerini birlikte çalıştırır. Eğitim exportundan önce tercih edilen kapıdır.

## 4. Grup-bilinçli split

```bash
veri split
```

Varsayılan oranlar:

```text
train      80%
validation 10%
test       10%
```

Örnek:

```bash
veri split --train 0.85 --validation 0.10 --seed tde-v2
```

Split satır bazlı yapılmaz. Kayıtlar şu alanlardan herhangi birini paylaşıyorsa aynı bağlı bileşenin parçası kabul edilir:

```text
subject_group_id
OR exam_family
OR question_family
```

Örneğin A ve B aynı öğrenciden, B ve C aynı soru ailesindense A/B/C birlikte aynı split'e gider. Böylece dolaylı leakage da azaltılır.

Split yalnızca `status == teacher_verified`, `pii_reviewed == true`, `split != benchmark` kayıtlarına uygulanır.

Mevcut bir bağlı grubun zaten `train`, `validation` veya `test` ataması varsa bu atama korunur; komutu farklı seed ile tekrar çalıştırmak eski grupları sessizce başka split'e taşımaz.

Bir kayıt `benchmark` içindeki herhangi bir `subject_group_id`, `exam_family` veya `question_family` ile çakışıyorsa split işlemi yazma yapmadan durur. Böylece benchmark ailesi eğitim verisine taşınmaz.

Sonuç hem canonical `metadata.split` alanına hem de:

```text
dataset/splits/train/manifest.json
dataset/splits/validation/manifest.json
dataset/splits/test/manifest.json
```

dosyalarına yazılır.

## 5. Leakage kontrolü

```bash
veri leakage
```

Aynı `subject_group_id`, `exam_family` veya `question_family` birden fazla split içinde görünürse hata verir. Benchmark da leakage kontrolüne dahildir.

## 6. SFT exportu

Tüm split'ler:

```bash
veri export-sft
```

Yalnız train:

```bash
veri export-sft --split train
```

Üretilen dosyalar:

```text
exports/sft/train.jsonl
exports/sft/validation.jsonl
exports/sft/test.jsonl
```

Her satır modelden bağımsız messages/ChatML-benzeri yapıdadır. User mesajına yalnızca `task`, `rubric`, `student_response`; assistant hedefine yalnızca `gold_evaluation` konur. Öğrenci grup kimliği, exam family ve annotation metadata modele verilmez.

`needs_review=true` kayıtları SFT hedefinden otomatik dışlanır; bunlar önce öğretmen tarafından çözülmelidir.

## 7. İstatistik

```bash
veri stats
```

Toplam kayıt, modality, status, split, teacher-verified ve review sayılarını JSON olarak gösterir.

## Tavsiye edilen günlük akış

```text
veri new
   ↓
öğretmen gold puanlamasını tamamlar
   ↓
anonimlik kontrolü → pii_reviewed=true
   ↓
status → teacher_verified
   ↓
veri check
   ↓
veri split
   ↓
veri check
   ↓
veri export-sft
   ↓
Local LLM fine-tuning
```

## Bilinçli kapsam dışı

Bu ilk sürüm OCR veya STT çalıştırmaz, öğrencinin yerine gold puan üretmez, ham ses/PDF/fotoğrafı Git'e almaz ve belirli bir fine-tuning framework'üne bağlanmaz. Bunlar canonical veri kalitesini model eğitim altyapısından ayırmak için bilinçli kararlardır.
