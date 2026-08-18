# veri — Türk Dili ve Edebiyatı Rubrik Notlandırma Veri Seti

Bu depo, **yerel bir dil modelini (Local LLM) Türk Dili ve Edebiyatı derslerinde rubriğe dayalı notlandırma yapacak şekilde eğitmek ve değerlendirmek** için veri üretme, öğretmen tarafından doğrulama, kalite kontrolü, kota yönetimi ve eğitim formatlarına dönüştürme amacıyla kurulmuştur.

Hedef model; soru/görev + rubrik + öğrenci cevabını birlikte okuyarak:

- ölçüt bazında puan,
- toplam puan,
- öğrenci cevabına dayalı kısa kanıt,
- rubriğe bağlı kısa gerekçe,
- gerektiğinde güvenilir `needs_review`

üretmelidir.

Desteklenen sınav türleri:

- **Yazılı sınav** (`written`)
- **Konuşma sınavı** (`speaking`)
- **Dinleme sınavı** (`listening`)

> Bu depo rubrik tabanlı değerlendirme modelini eğitir. OCR veya STT sisteminin kendi hatalarını öğretmek ana hedef değildir. Canonical öğrenci metni/transkripti mümkün olduğunca öğretmen tarafından doğrulanmış olmalıdır.

## Ana tasarım

```text
soru / görev
    +
rubrik
    +
öğrenci cevabı
    +
öğretmen gold değerlendirmesi
    +
üretim profili / review metadata
    ↓
canonical record
    ↓
quality + production gate
    ↓
group-aware split
    ↓
curated SFT / benchmark
```

`dataset/records/` veri setinin **single source of truth** alanıdır. `exports/` yeniden üretilebilir türevleri içerir.

## V1 veri üretim hedefi

V1 için hedef **6.000 teacher-verified canonical örnek**tir. Veri tek seferde üretilmez:

```text
500    → pilot fine-tune + error mining
1.500  → ikinci fine-tune + error mining
3.000  → üçüncü fine-tune + error mining
6.000  → V1
```

Modalite hedefi:

| Tür | Pay |
|---|---:|
| Yazılı | %50 |
| Konuşma | %25 |
| Dinleme | %25 |

Cevap profili hedefi:

| Profil | Pay |
|---|---:|
| Tam/tama yakın doğru | %20 |
| Yüksek kısmi doğru | %20 |
| Orta kısmi doğru | %20 |
| Düşük kısmi doğru | %15 |
| Yanlış | %10 |
| Boş/ilgisiz | %5 |
| Borderline | %10 |

Buna ek olarak:

- **%15–20 hard case**,
- **%3–5 adversarial**,
- **%8–12 teacher-verified gold `needs_review`**,
- teacher-verified verinin en az **%20'sinde çift insan değerlendirmesi**

hedeflenir.

Ayrıntılar: [`docs/DATA_PRODUCTION_STRATEGY.md`](docs/DATA_PRODUCTION_STRATEGY.md).

Makine tarafından okunan hedefler: [`config/data-production.v1.json`](config/data-production.v1.json).

## Hızlı başlangıç

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Pilot üretime başlarken:

```bash
veri quota --phase pilot
veri next-batch --phase pilot --count 100
veri new
veri check
veri split
veri check
veri export-sft
```

## Dataset Factory komutları

### `veri new`

Yeni draft canonical kayıt oluşturur. Soru/cevap/rubriğe ek olarak:

- exact `task_id`,
- `exam_family`,
- `question_family`,
- anonim `subject_group_id`,
- `response_quality`,
- `hard_case_types`,
- `adversarial`

bilgilerini de toplar.

Yeni kayıt doğrudan eğitime girmez:

```text
status = draft
pii_reviewed = false
needs_review = true
review_count = 0
adjudicated = false
```

### `veri check`

Tek kalite kapısıdır:

```text
JSON Schema + semantic invariants
             +
production profile policy
             +
split leakage
```

`teacher_verified` kayıtta üretim metadata'sı ve insan review politikası da kontrol edilir.

### `veri quota`

Mevcut veri setini üretim hedefleriyle karşılaştırır:

```bash
veri quota --phase pilot
veri quota --phase v1
veri quota --phase v1 --json
```

Modalite, sınıf, cevap profili, hard-case/adversarial/needs-review oranları, review kotası, exact soru kapsaması, question-family kapsaması ve rubrik çeşitliliğini raporlar.

### `veri next-batch`

Sonraki üretim paketini veri açığına göre yönlendirir:

```bash
veri next-batch --phase pilot --count 100
```

Örneğin yazılı veya orta-kısmi cevaplar geride kaldıysa sonraki pakette onların kotasını yükseltir.

### `veri split`

Teacher-verified kayıtları varsayılan `80/10/10` train/validation/test oranıyla ayırır. Satır bazlı rastgele split yapmaz.

Aşağıdaki alanlardan herhangi birini paylaşan kayıtlar aynı bağlı grupta tutulur:

```text
subject_group_id
OR exam_family
OR question_family
```

Benchmark aileleri eğitim split'leriyle çakışamaz.

### `veri export-sft`

Curated Chat/messages JSONL üretir:

```text
exports/sft/train.jsonl
exports/sft/validation.jsonl
exports/sft/test.jsonl
```

Model promptuna yalnız değerlendirme için gereken içerik gider:

```text
task (task_id hariç)
rubric
student_response
```

Üretim etiketleri ve öğrenci/grup metadata'sı modele verilmez.

## `needs_review` için kritik ayrım

İki durum birbirine karıştırılmaz.

**Çözülmemiş annotation:**

```text
draft / annotated / quarantined
```

→ SFT exportuna girmez.

**Gold escalation davranışı:**

```text
status = teacher_verified
needs_review = true
review_count >= 2
```

→ gerçekten modelin “insan incelemesine gönder” demesi doğru olduğundan curated SFT exportuna girer.

Bu sayede model yalnız not vermeyi değil, kanıt yetersiz olduğunda **aşırı özgüven göstermemeyi** de öğrenir.

## Aynı sorudan kaç cevap?

- exact `task.task_id`: **8–20 cevap**,
- `question_family`: **20–40 cevap**,
- V1: yaklaşık **300 question family**.

Amaç binlerce örneği birkaç soruya yığmak değil, farklı soru/rubrik karar yüzeylerine yaymaktır.

## Hard-case örnekleri

Desteklenen etiketlerden bazıları:

- `short_correct`
- `long_irrelevant`
- `keyword_decoy`
- `paraphrase_equivalent`
- `contradictory_answer`
- `prompt_injection`
- `ocr_ambiguity`
- `stt_ambiguity`
- `missing_evidence`
- `rubric_ambiguity`

Bunlar modelin yalnız anahtar kelime veya cevap uzunluğuna göre puan vermesini engellemek için deliberate olarak üretilir.

## Dizin yapısı

```text
.
├── README.md
├── pyproject.toml
├── config/
│   └── data-production.v1.json
├── dataset_factory/
│   ├── __init__.py
│   ├── cli.py
│   ├── core.py
│   └── production.py
├── docs/
│   ├── DATA_CONTRACT.md
│   ├── ANNOTATION_GUIDE.md
│   ├── DATA_QUALITY.md
│   ├── DATASET_FACTORY.md
│   └── DATA_PRODUCTION_STRATEGY.md
├── schemas/
│   ├── canonical-record.schema.json
│   └── rubric.schema.json
├── dataset/
│   ├── records/
│   │   ├── written/
│   │   ├── speaking/
│   │   └── listening/
│   ├── splits/
│   ├── preferences/
│   └── benchmarks/
├── examples/
├── exports/
└── tests/
```

## Canonical metadata özeti

```json
{
  "task": {
    "task_id": "tde11-poetry-main-idea-q01",
    "prompt": "...",
    "context": null,
    "max_score": 10
  },
  "metadata": {
    "status": "teacher_verified",
    "split": null,
    "pii_reviewed": true,
    "subject_group_id": "anon-group-...",
    "exam_family": "exam-family-...",
    "question_family": "main-idea-poetry",
    "response_quality": "mid_partial",
    "hard_case_types": ["paraphrase_equivalent"],
    "adversarial": false,
    "review_count": 1,
    "adjudicated": false,
    "provenance": "real_anonymized"
  }
}
```

Tam sözleşme: [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).

## Konuşma sınavlarında kanıt kuralı

Transkript yalnız **ne söylendiğini** temsil eder. Telaffuz, vurgu-tonlama, gerçek akıcılık/duraksama, ses kullanımı veya beden dili yalnız transkriptten puanlanmaz. Bu ölçütler varsa uygun `evidence_sources` ve öğretmen observation bilgisi gerekir.

## Gizlilik

Canonical kayıtlara öğrenci adı/soyadı, okul numarası, T.C. kimlik numarası, telefon/e-posta, açık okul/şube bilgisi veya kişiyi yeniden tanımlamayı kolaylaştıracak metadata konmaz.

Ham ses, PDF, fotoğraf ve taranmış kâğıtlar varsayılan olarak Git'e alınmaz.

## Başarı ölçütü

Başarı yalnız toplam puan eşleşmesi değildir. Benchmarklarda mümkün olduğunca:

- criterion agreement,
- toplam/ölçüt puan sapması,
- borderline karar performansı,
- `needs_review` precision/recall,
- hard-case ve adversarial alt-küme performansı,
- insan ↔ insan ve model ↔ insan uyumu

izlenmelidir.

Bu depo veri setini, üretim stratejisini ve kalite araçlarını tutar. Model mimarisi, quantization yöntemi veya belirli fine-tuning framework'ü canonical veri sözleşmesinin parçası değildir.
