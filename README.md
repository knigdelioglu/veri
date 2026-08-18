# veri — Türk Dili ve Edebiyatı Rubrik Notlandırma Veri Seti

Bu depo, **yerel bir dil modelini (Local LLM) Türk Dili ve Edebiyatı derslerinde rubriğe dayalı notlandırma yapacak şekilde eğitmek ve değerlendirmek** için veri üretme, temizleme, öğretmen tarafından doğrulama, kalite kontrolü ve eğitim formatlarına dönüştürme amacıyla kurulmuştur.

Hedef model; bir sınav sorusunu/görevini, ilgili rubriği ve öğrencinin cevabını birlikte okuyarak:

- ölçüt bazında puan,
- toplam puan,
- öğrenci cevabına dayalı kısa kanıt,
- rubriğe bağlı kısa gerekçe,
- gerekirse `needs_review`

üretmelidir.

Desteklenen sınav türleri:

- **Yazılı sınav** — öğrencinin yazılı cevabı üzerinden rubrik değerlendirmesi.
- **Konuşma sınavı** — doğrulanmış transkript ve gerekli olduğunda öğretmen gözlemleri üzerinden değerlendirme.
- **Dinleme sınavı** — dinleme görevine verilen öğrenci cevabının rubriğe göre değerlendirilmesi.

> Bu depo öncelikle **rubrik tabanlı değerlendirme modelini** eğitir. OCR ve konuşmadan metne (ASR/STT) sistemlerinin kendi hatalarını öğretmek ana hedef değildir. Eğitimde mümkün olduğunca öğretmen tarafından düzeltilmiş öğrenci metni/transkripti canonical cevap olarak kullanılmalıdır.

## Temel tasarım ilkesi

Canonical veri hiçbir eğitim framework'üne bağlı değildir.

```text
soru / görev
    +
rubrik
    +
öğrenci cevabı
    +
öğretmenin doğruladığı değerlendirme
    ↓
canonical record
    ↓
quality gate
    ↓
group-aware split
    ↓
SFT / preference / benchmark export
```

`dataset/records/` altındaki kayıtlar veri setinin **tek gerçek kaynağıdır (single source of truth)**. `exports/` altındaki JSONL dosyaları yeniden üretilebilir türevlerdir.

## Hızlı başlangıç

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Ardından:

```bash
veri new
veri check
veri split
veri check
veri export-sft
veri stats
```

Araçların ayrıntılı kullanımı için [`docs/DATASET_FACTORY.md`](docs/DATASET_FACTORY.md).

## Dataset Factory

Repo içinde `veri` adlı küçük bir CLI bulunur.

### Yeni canonical kayıt

```bash
veri new
```

Etkileşimli sihirbaz soru/görev, cevap, rubrik ölçütleri, puan çıpaları ve kanıt kaynaklarını sorar. Oluşturulan kayıt doğrudan eğitime girmez; başlangıçta:

```text
status = draft
pii_reviewed = false
needs_review = true
```

olur.

### Kalite kapısı

```bash
veri check
```

Şunları kontrol eder:

- JSON Schema,
- dosya adı ↔ kayıt ID'si,
- modality ↔ klasör,
- rubrik ölçütleri ↔ gold sonuç ölçütleri,
- ölçüt puan sınırları,
- rubrik/toplam maksimum puan tutarlılığı,
- ölçüt puanları toplamı ↔ `total_score`,
- `teacher_verified` ↔ `pii_reviewed`,
- `needs_review` açıklaması,
- temel PII işaretleri,
- metin dışı konuşma ölçütlerinde gözlem eksikliği,
- train/validation/test/benchmark leakage.

### Grup-bilinçli split

```bash
veri split
```

Varsayılan oranlar `80/10/10`'dur. Split satır bazlı yapılmaz. Aşağıdaki alanlardan **herhangi birini** paylaşan kayıtlar bağlı grup kabul edilerek aynı split içinde tutulur:

```text
subject_group_id
OR exam_family
OR question_family
```

Mevcut split ataması korunur. Benchmark ile aile çakışması varsa komut yazma yapmadan durur.

### SFT exportu

```bash
veri export-sft
```

Üretilen dosyalar:

```text
exports/sft/train.jsonl
exports/sft/validation.jsonl
exports/sft/test.jsonl
```

SFT girdisine yalnız `task`, `rubric` ve `student_response`; hedefe yalnız `gold_evaluation` konur. Öğrenci/grup metadata'sı modele verilmez. `needs_review=true` kayıtları SFT hedefinden çıkarılır.

## Modelin öğrenmesi gereken çıktı

Her değerlendirmede mümkün olduğunca şu yapı korunur:

1. Her rubrik ölçütü için puan.
2. Ölçüte ilişkin öğrenci cevabından kısa kanıt veya yapılandırılmış gözlem.
3. Ölçüte ilişkin kısa, öğretmen diliyle gerekçe.
4. Toplam puan ve mümkün olan maksimum puan.
5. Puanlama güvenilir değilse `needs_review: true`.

Uzun serbest biçimli düşünce zinciri veri setine eklenmez. Bunun yerine yalnızca puanı açıklayan **kısa ve denetlenebilir değerlendirme gerekçesi** tutulur.

## Dizin yapısı

```text
.
├── README.md
├── .gitignore
├── pyproject.toml
├── dataset_factory/
│   ├── __init__.py
│   ├── cli.py
│   └── core.py
├── docs/
│   ├── DATA_CONTRACT.md
│   ├── ANNOTATION_GUIDE.md
│   ├── DATA_QUALITY.md
│   └── DATASET_FACTORY.md
├── schemas/
│   ├── canonical-record.schema.json
│   └── rubric.schema.json
├── dataset/
│   ├── records/
│   │   ├── written/
│   │   ├── speaking/
│   │   └── listening/
│   ├── splits/
│   │   ├── train/
│   │   ├── validation/
│   │   └── test/
│   ├── preferences/
│   └── benchmarks/
├── examples/
│   ├── written.example.json
│   ├── speaking.example.json
│   └── listening.example.json
├── exports/
│   ├── sft/
│   └── preference/
└── tests/
    └── test_factory.py
```

### `dataset/records/`

Öğretmen tarafından hazırlanıp doğrulanacak canonical JSON kayıtları burada tutulur. Modaliteler birbirinden ayrıdır ancak **aynı veri sözleşmesini** kullanır.

### `dataset/splits/`

Train/validation/test manifestleri burada tutulur. Aynı öğrenci grubuna, sınav ailesine veya soru ailesine bağlı kayıtların split'ler arasında sızması engellenir.

### `dataset/preferences/`

İleride preference optimization / DPO benzeri yöntemler için kullanılabilecek `chosen/rejected` çiftleri burada tutulur. `chosen` mutlaka öğretmen onaylı olmalıdır.

### `dataset/benchmarks/`

Eğitim sırasında görülmemesi gereken sabit değerlendirme örnekleri. Benchmark ailesi eğitim split'leriyle çakışmamalıdır.

### `exports/`

Canonical kayıtlardan eğitim kütüphanesine uygun olarak üretilen JSONL vb. dosyalar. Bunlar veri setinin ana kaynağı değildir ve Git tarafından varsayılan olarak izlenmez.

## Canonical kayıt özeti

Her örnek en az şu yapıyı taşır:

```json
{
  "id": "tde12-written-000001",
  "schema_version": "1.0",
  "modality": "written",
  "language": "tr",
  "grade": 12,
  "task": {
    "prompt": "...",
    "context": null,
    "max_score": 20
  },
  "rubric": {
    "rubric_id": "...",
    "version": "1.0",
    "criteria": []
  },
  "student_response": {
    "text": "...",
    "source": "teacher_corrected",
    "observations": []
  },
  "gold_evaluation": {
    "criterion_results": [],
    "total_score": 0,
    "max_score": 20,
    "needs_review": false,
    "review_reason": null,
    "overall_feedback": "..."
  },
  "metadata": {
    "status": "teacher_verified",
    "split": null,
    "created_at": "YYYY-MM-DD",
    "tags": [],
    "pii_reviewed": true,
    "subject_group_id": null,
    "exam_family": null,
    "question_family": null,
    "provenance": "real_anonymized"
  }
}
```

Ayrıntılı alan kuralları için [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md) ve JSON Schema dosyalarına bakın.

## Önerilen veri üretim akışı

```text
1. Sınav sorusunu/görevini ekle
2. Rubriği yapılandırılmış ölçütlere dönüştür
3. Öğrenci cevabını anonimleştir
4. OCR/STT varsa metni öğretmen tarafından düzelt
5. Öğretmen ölçüt bazında gold puanlama yapar
6. İkinci kontrol / kalite kontrolü yapılır
7. Kayıt teacher_verified durumuna alınır
8. veri check
9. veri split
10. veri check
11. veri export-sft
```

## Veri kalitesi kuralları

- **Gold etiket öğretmen değerlendirmesidir.** Model tarafından üretilen ilk puan doğrudan gold veri olamaz.
- Yalnızca toplam not değil, **ölçüt bazlı puanlar** saklanır.
- Puan gerekçesi rubriğe ve öğrenci cevabındaki gözlenebilir kanıta dayanır.
- Belirsiz veya rubriğin kapsamadığı durumda zorla puan üretmek yerine `needs_review` kullanılır.
- OCR/STT hatası ile öğrencinin gerçek hatası birbirine karıştırılmaz.
- Aynı öğrencinin, sınav ailesinin veya yakın soru varyantlarının split sızıntısı oluşturması engellenir.
- Benchmark kayıtları eğitim export'larına dahil edilmez.
- Şema değişikliklerinde `schema_version` artırılır; eski kayıtların anlamı sessizce değiştirilmez.

## Konuşma sınavlarında kanıt kuralı

Transkript yalnızca **ne söylendiğini** temsil eder. Şunlar yalnız transkriptten puanlanmamalıdır:

- telaffuz,
- vurgu ve tonlama,
- gerçek zamanlı akıcılık/duraksama,
- ses kullanımı,
- beden dili.

Bu ölçütler kullanılacaksa rubrikte uygun `evidence_sources` belirtilmeli ve `student_response.observations` içinde öğretmen tarafından doğrulanmış yapılandırılmış gözlem bulunmalıdır.

## Gizlilik ve öğrenci verisi

Canonical kayıtlara şunları koymayın:

- öğrenci adı/soyadı,
- okul numarası,
- T.C. kimlik numarası,
- telefon/e-posta,
- açık okul/sınıf/şube kimliği,
- öğrenciyi doğrudan veya dolaylı biçimde tanımlayabilecek serbest metadata.

Her öğrenci/oturum gerekiyorsa geri döndürülemeyen anonim bir grup kimliği ile temsil edilmelidir. Gerçek ses, taranmış kâğıt, PDF, fotoğraf ve benzeri ham materyaller varsayılan olarak Git'e alınmaz.

## Eğitim split'i konusunda önemli kural

Rastgele satır bazlı split yeterli değildir. Aynı öğrencinin, aynı sınav formunun veya aynı sorunun yakın varyantlarının train ile test arasında sızması model performansını yapay olarak yükseltir.

Dataset Factory bu nedenle ortak:

```text
subject_group_id
exam_family
question_family
```

değerlerinden herhangi biri üzerinden birbirine bağlanan kayıtları aynı split'te tutar.

## Kayıt adlandırma

Önerilen ID:

```text
<tde><sinif>-<modality>-<6 haneli sıra>
```

Örnekler:

```text
tde09-written-000001
tde11-speaking-000042
tde12-listening-000107
```

Dosya adı kayıt ID'si ile aynı olmalıdır:

```text
dataset/records/written/tde12-written-000001.json
```

## Veri setinin başarı ölçütü

Başarı yalnızca modelin öğretmenle aynı toplam notu vermesi değildir. İyi bir model:

- rubriğin hangi ölçütünü neden uyguladığını doğru belirlemeli,
- kısmi puanı tutarlı kullanmalı,
- öğrenci cevabında olmayan bilgiyi varmış gibi değerlendirmemeli,
- rubriğe ek ölçüt uydurmamalı,
- farklı anlatım biçimlerini aynı anlamı taşıdıklarında kabul edebilmeli,
- belirsiz örneklerde aşırı özgüvenli davranmamalıdır.

Benchmarklarda toplam puan hatasına ek olarak **criterion agreement**, **puan sapması**, **review recall** ve mümkünse öğretmenler arası uyumla karşılaştırma izlenmelidir.

---

Bu depo veri setini, veri sözleşmesini ve veri üretim/kalite araçlarını tutar. Model mimarisi, quantization yöntemi veya belirli fine-tuning framework'ü canonical veri şemasının parçası değildir.
