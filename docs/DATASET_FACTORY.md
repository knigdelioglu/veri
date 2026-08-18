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

Önerilen sıra:

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

Sihirbaz artık yalnız soru/cevap/rubrik istemez. Veri üretim kontrolü için ayrıca şunları toplar:

- `task.task_id`: birebir aynı soru/görev kimliği,
- `exam_family`,
- `question_family`,
- anonim `subject_group_id`,
- `response_quality`,
- `hard_case_types`,
- `adversarial`.

Yeni kayıt bilinçli olarak:

```text
status = draft
pii_reviewed = false
needs_review = true
review_count = 0
adjudicated = false
```

başlar. Bu, henüz eğitim verisi olmadığı anlamına gelir.

## 2. JSON/semantic doğrulama

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

`check`, üç kontrol katmanını birlikte çalıştırır:

```text
schema/semantic validation
        +
production profile policy
        +
split leakage
```

`teacher_verified` kayıtlar için üretim profili de zorunludur. Özellikle:

- `task_id`,
- geçerli `response_quality`,
- `hard_case_types`,
- `adversarial`,
- `review_count`,
- `adjudicated`

kontrol edilir.

Validation/test/benchmark, `borderline` ve gold `needs_review=true` kayıtlarında en az iki bağımsız inceleme gerekir.

## 4. Kota raporu

```bash
veri quota --phase pilot
veri quota --phase v1
```

Rapor mevcut teacher-verified veriyi hedeflerle karşılaştırır:

- modalite,
- sınıf,
- response quality,
- `needs_review`, hard-case, adversarial ve dual-review oranları,
- exact `task_id` başına cevap sayısı,
- `question_family` başına cevap sayısı,
- rubrik çeşitliliği.

JSON çıktı:

```bash
veri quota --phase v1 --json
```

## 5. Sonraki üretim paketi

```bash
veri next-batch --phase pilot --count 100
```

Bu komut mevcut açıkları dikkate alıp sonraki paketin bağımsız kota eksenlerini üretir. Örneğin:

```text
written       50
speaking      25
listening     25

full_correct  20
high_partial  20
...

hard_case minimum 15
adversarial minimum 3
```

Aynı kayıt birden fazla kotayı aynı anda karşılayabilir.

## 6. Grup-bilinçli split

```bash
veri split
```

Varsayılan oranlar:

```text
train      80%
validation 10%
test       10%
```

Split satır bazlı yapılmaz. Kayıtlar şu alanlardan herhangi birini paylaşıyorsa aynı bağlı bileşenin parçası kabul edilir:

```text
subject_group_id
OR exam_family
OR question_family
```

Mevcut split atamaları korunur. Benchmark ailesiyle çakışma varsa yazma işlemi başlamadan hata verilir.

`split` öncesinde üretim profili hataları da bloklanır.

Bir kayıt split sonrası validation/test'e düşerse ikinci öğretmen incelemesi gerektirebilir. Bu durumda sonraki `veri check`, `review_count < 2` ise hatayı açıkça bildirir.

## 7. Leakage kontrolü

```bash
veri leakage
```

Aynı `subject_group_id`, `exam_family` veya `question_family` farklı train/validation/test/benchmark bölümlerinde görünürse hata verir.

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

Model girdisine yalnız değerlendirme için gerekli içerik girer:

```text
task (task_id hariç)
rubric
student_response
```

`task_id`, response profile, hard-case etiketleri, öğrenci/grup kimlikleri ve annotation metadata model promptuna verilmez. Bunlar yalnız veri analizi/export satırı metadata'sında tutulabilir.

### `needs_review=true` kuralı

İki durum ayrılır:

1. **Çözülmemiş annotation:** `draft/annotated/quarantined` → export edilmez.
2. **Teacher-verified gold escalation:** gerçekten insan incelemesine gitmesi doğru davranışsa `teacher_verified + needs_review=true + review_count>=2` → curated SFT exportuna dahil edilir.

Böylece model yalnız puan vermeyi değil, kanıt yetersizliğinde güvenilir biçimde escalation yapmayı da öğrenir.

Sistem promptu ayrıca öğrenci cevabının içindeki talimatların sistem talimatı olmadığını açıkça belirtir.

## 9. Temel istatistik

```bash
veri stats
```

Bu komut genel sayaçları verir. Üretim hedefi açısından asıl operasyonel rapor `veri quota`dır.

## 10. Üretim fazları

```text
pilot       500
iteration_1 1.500
iteration_2 3.000
v1          6.000
```

Her fazın ardından fine-tune ve hata analizi yapılmalıdır. Sonraki veri paketi modelin hata kümelerine göre yönlendirilir; yalnız sayıyı büyütmek amaç değildir.

## Bilinçli kapsam dışı

Dataset Factory:

- OCR/STT motoru çalıştırmaz,
- öğrencinin yerine gold puan üretmez,
- ham ses/PDF/fotoğrafı Git'e almaz,
- belirli bir model veya fine-tuning framework'üne canonical veriyi kilitlemez.

Bu sınırlar veri kalitesini model altyapısından bağımsız tutmak için bilinçlidir.
