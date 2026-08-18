# veri — Türk Dili ve Edebiyatı Rubrik Notlandırma Veri Seti

Bu depo, **yerel bir dil modelini (Local LLM) Türk Dili ve Edebiyatı derslerinde rubriğe dayalı notlandırma yapacak şekilde eğitmek ve değerlendirmek** için veri üretme, doğrulama, kalite kontrolü, kota yönetimi ve eğitim formatlarına dönüştürme amacıyla kurulmuştur.

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

> Bu depo rubrik tabanlı değerlendirme modelini eğitir. OCR veya STT sisteminin kendi hatalarını öğretmek ana hedef değildir. Sentetik veride olmayan ses/teslim özellikleri uydurulmaz; speaking örnekleri gerçek audio yoksa transcript-only rubric kullanır.

## Doğrulama kaynakları

Canonical veri doğrulama kaynağını açıkça taşır:

```text
ai_verified       → AI tarafından üretilmiş/yeniden denetlenmiş veri
teacher_verified  → gerçekten insan öğretmen tarafından doğrulanmış veri
```

Sentetik pilot üretimde varsayılan:

```json
{
  "status": "ai_verified",
  "verification_source": "ai"
}
```

olacaktır. `teacher_verified` etiketi AI verisine verilmez.

## Ana tasarım

```text
soru / görev
    +
rubrik
    +
öğrenci cevabı
    +
gold değerlendirme
    +
verification provenance
    +
üretim profili / review metadata
    ↓
canonical record
    ↓
quality + production gate
    ↓
exact-task-aware group split
    ↓
curated SFT / benchmark
```

`dataset/records/` veri setinin **single source of truth** alanıdır. `exports/` yeniden üretilebilir türevleri içerir.

## V1 veri üretim hedefi

V1 için hedef **6.000 verified canonical örnek**tir. Veri tek seferde üretilmez:

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
- hedef olarak **%8–12 gerçek gold `needs_review`**,
- verified verinin en az **%20'sinde ikinci doğrulama geçişi**

izlenir.

`needs_review` oranı kota uğruna yapay olarak doldurulmaz. Rubrik mevcut anchor ile güvenilir puan verebiliyorsa borderline cevap puanlanır; escalation yalnız kanıt gerçekten yetersiz/güvenilmez olduğunda kullanılır.

Ayrıntılar: [`docs/DATA_PRODUCTION_STRATEGY.md`](docs/DATA_PRODUCTION_STRATEGY.md).

Makine tarafından okunan hedefler: [`config/data-production.v1.json`](config/data-production.v1.json).

## Hızlı başlangıç

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Pilot üretimde:

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

Verified kayıtların `verification_source`, üretim metadata'sı ve review-count politikası kontrol edilir.

### `veri quota`

Mevcut veri setini üretim hedefleriyle karşılaştırır:

```bash
veri quota --phase pilot
veri quota --phase v1
veri quota --phase v1 --json
```

Modalite, sınıf, cevap profili, hard-case/adversarial/needs-review oranları, doğrulama kotası, exact soru kapsaması, question-family kapsaması, rubrik çeşitliliği ve doğrulama kaynağını raporlar.

### `veri next-batch`

Sonraki üretim paketini veri açığına göre yönlendirir:

```bash
veri next-batch --phase pilot --count 100
```

Örneğin yazılı veya orta-kısmi cevaplar geride kaldıysa sonraki pakette onların kotasını yükseltir.

### `veri split`

Verified kayıtları varsayılan `80/10/10` train/validation/test oranıyla ayırır. Satır bazlı rastgele split yapmaz.

Aşağıdaki alanlardan **herhangi birini** paylaşan kayıtlar aynı bağlı bileşende tutulur:

```text
task_id
OR subject_group_id
OR exam_family
OR question_family
```

Böylece birebir aynı soru, yakın soru varyantı, aynı sınav formu veya aynı anonim öğrenci bağlantısı train/test arasında bölünemez. Benchmark da aynı dört anahtarla eğitim split'lerinden izole edilir.

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

Üretim etiketleri ve öğrenci/grup metadata'sı modele verilmez. Export metadata'sında `verification_source` korunur; böylece AI-verified ve ilerideki human-verified veri analizde ayrılabilir.

## `needs_review` için kritik ayrım

**Çözülmemiş annotation:**

```text
draft / annotated / quarantined
```

→ SFT exportuna girmez.

**Gold escalation davranışı:**

```text
status = ai_verified | teacher_verified
needs_review = true
review_count >= 2
```

→ kanıtın gerçekten güvenilir puan üretmeye yetmediği bir örnekse curated SFT exportuna girer.

**Borderline tek başına escalation değildir.** Rubrik komşu bir anchor ile puanlamayı çözüyorsa model puan vermelidir.

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
│   ├── DATA_PRODUCTION_STRATEGY.md
│   └── PILOT_500_PRODUCTION_PLAN.md
├── schemas/
│   ├── canonical-record.schema.json
│   └── rubric.schema.json
├── dataset/
│   ├── candidates/
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

Sentetik verified örnek:

```json
{
  "task": {
    "task_id": "tde11-poetry-main-idea-q01",
    "prompt": "...",
    "context": null,
    "max_score": 10
  },
  "metadata": {
    "status": "ai_verified",
    "verification_source": "ai",
    "split": null,
    "pii_reviewed": true,
    "subject_group_id": null,
    "exam_family": "exam-family-...",
    "question_family": "main-idea-poetry",
    "response_quality": "mid_partial",
    "hard_case_types": ["paraphrase_equivalent"],
    "adversarial": false,
    "review_count": 1,
    "adjudicated": false,
    "provenance": "synthetic"
  }
}
```

Tam sözleşme: [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).

## Konuşma sınavlarında kanıt kuralı

Transkript yalnız **ne söylendiğini** temsil eder. Telaffuz, vurgu-tonlama, gerçek akıcılık/duraksama, ses kullanımı veya beden dili yalnız transkriptten puanlanmaz.

- Sentetik speaking veride gerçek audio yoksa bu kriterler rubric'ten çıkarılır ve kayıt `transcript-only` olarak işaretlenir.
- Gerçek audio verisinde bu ölçütler kullanılacaksa uygun `evidence_sources` ve gerçek gözlem/audio kanıtı gerekir.

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
- AI-verified ↔ ileride varsa human-verified slice farkları

izlenmelidir.

Bu depo veri setini, üretim stratejisini ve kalite araçlarını tutar. Model mimarisi, quantization yöntemi veya belirli fine-tuning framework'ü canonical veri sözleşmesinin parçası değildir.
