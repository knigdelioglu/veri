# Dataset Factory

Bu repo yalnız veri depolamaz; canonical kayıt üretimi, kalite kontrolü, üretim kotası, leakage-safe split ve SFT exportu için Python CLI içerir.

## Kurulum

Python 3.11+ gerekir.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Günlük üretim akışı

```text
veri quota --phase pilot
        ↓
veri next-batch --phase pilot --count 100
        ↓
veri new
        ↓
öğretmen gold puanlama + PII kontrolü + review metadata
        ↓
status = teacher_verified
        ↓
veri check
        ↓
veri split
        ↓
evaluation split'lerine düşen kayıtların ikinci incelemesi
        ↓
veri check
        ↓
veri export-sft
```

Üretim hedeflerinin canonical kaynağı `config/data-production.v1.json`, gerekçeli strateji ise `docs/DATA_PRODUCTION_STRATEGY.md` dosyasıdır.

## 1. Yeni kayıt oluşturma

```bash
veri new
```

Sihirbaz soru/cevap/rubriğe ek olarak şunları toplar:

- `task.task_id`: birebir aynı soru/görev kimliği,
- `exam_family`,
- `question_family`,
- anonim `subject_group_id`,
- `response_quality`,
- `hard_case_types`,
- `adversarial`.

Yeni kayıt:

```text
status = draft
pii_reviewed = false
needs_review = true
review_count = 0
adjudicated = false
```

başlar ve öğretmen gold değerlendirmesi tamamlanmadan eğitim verisi sayılmaz.

## 2. Veri doğrulama

```bash
veri validate
```

Örnek dosyaları da dahil etmek için:

```bash
veri validate --include-examples
```

Başlıca kontroller:

- JSON Schema,
- dosya adı ↔ kayıt ID'si,
- modality ↔ klasör,
- rubrik ölçütleri ↔ gold sonuç ölçütleri,
- ölçüt ve toplam puan sınırları,
- `teacher_verified` ↔ `pii_reviewed`,
- `needs_review` açıklaması,
- temel PII işaretleri,
- metin dışı konuşma ölçütlerinde observation eksikliği.

## 3. Tek kalite kapısı

```bash
veri check
```

Üç katmanı birlikte çalıştırır:

```text
schema/semantic validation
        +
production profile policy
        +
exact-task-aware split leakage
```

`teacher_verified` kayıtlar için `task_id`, `response_quality`, `hard_case_types`, `adversarial`, `review_count` ve `adjudicated` üretim kalite kapısının parçasıdır.

Validation/test/benchmark, `borderline` ve gold `needs_review=true` kayıtlarında en az iki bağımsız inceleme gerekir.

## 4. Kota raporu

```bash
veri quota --phase pilot
veri quota --phase v1
```

Rapor:

- modalite,
- sınıf,
- response quality,
- `needs_review`, hard-case, adversarial ve dual-review oranları,
- exact `task_id` başına cevap sayısı,
- `question_family` başına cevap sayısı,
- rubrik çeşitliliği

hedeflerini izler.

Makine okunabilir çıktı:

```bash
veri quota --phase v1 --json
```

## 5. Sonraki üretim paketi

```bash
veri next-batch --phase pilot --count 100
```

Mevcut açıkları kullanarak sonraki paketin modalite, sınıf ve cevap-profili kotalarını önerir. Hard-case, adversarial, gold `needs_review` ve çift review için minimum adetler de verir.

Kota eksenleri bağımsızdır; tek kayıt birden çok kotayı karşılayabilir.

## 6. Exact-task-aware grup split

```bash
veri split
```

Varsayılan oranlar:

```text
train      80%
validation 10%
test       10%
```

Split satır bazlı değildir. Aşağıdaki alanlardan **herhangi birini** paylaşan kayıtlar union-find bağlı bileşeni olarak aynı splitte tutulur:

```text
task_id
OR subject_group_id
OR exam_family
OR question_family
```

Bunun sonucu:

- birebir aynı soru farklı splitlere ayrılamaz,
- aynı anonim öğrencinin cevapları ayrılamaz,
- aynı sınav formu ayrılamaz,
- yakın soru varyantları ayrılamaz.

Mevcut split atamaları korunur. Aynı bağlı bileşende çelişen mevcut split varsa işlem durur.

Benchmark ile `task_id`, `subject_group_id`, `exam_family` veya `question_family` çakışması varsa split yazma yapmadan bloklanır.

Split manifestindeki grouping rule da bu dört anahtarı açıkça kaydeder.

Bir kayıt split sonrası validation/test'e düşerse ikinci öğretmen incelemesi gerektirebilir; sonraki `veri check`, `review_count < 2` ise bunu hata olarak bildirir.

## 7. Leakage kontrolü

```bash
veri leakage
```

Şu dört anahtar train/validation/test/benchmark arasında taranır:

```text
task_id
subject_group_id
exam_family
question_family
```

Bir değer birden fazla splitte görünürse hata verir.

## 8. Curated SFT exportu

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

Model girdisine yalnız:

```text
task (task_id hariç)
rubric
student_response
```

girer.

`task_id`, response profile, hard-case etiketleri, öğrenci/grup kimlikleri ve annotation metadata model promptuna verilmez.

### `needs_review=true`

İki durum ayrılır:

1. Çözülmemiş annotation: `draft/annotated/quarantined` → export edilmez.
2. Teacher-verified gold escalation: `teacher_verified + needs_review=true + review_count>=2` → curated SFT exportuna dahil edilir.

Böylece model kanıt yetersizliğinde insan incelemesine yönlendirmeyi de öğrenebilir.

Sistem promptu öğrenci cevabının içindeki talimatların sistem talimatı olmadığını açıkça belirtir.

## 9. Temel istatistik

```bash
veri stats
```

Genel sayaçları verir. Üretim hedefi açısından asıl operasyonel rapor `veri quota`dır.

## 10. Üretim fazları

```text
pilot       500
iteration_1 1.500
iteration_2 3.000
v1          6.000
```

Her fazın ardından fine-tune ve hata analizi yapılır; sonraki paket yalnız sayıyı büyütmek yerine modelin hata kümelerine göre yönlendirilir.

## Bilinçli kapsam dışı

Dataset Factory:

- OCR/STT motoru çalıştırmaz,
- öğrencinin yerine gold puan üretmez,
- ham ses/PDF/fotoğrafı Git'e almaz,
- canonical veriyi belirli model veya fine-tuning framework'üne kilitlemez.
