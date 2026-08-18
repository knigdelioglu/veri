# veri — Türk Dili ve Edebiyatı Rubrik Notlandırma Veri Seti

Bu depo, **yerel bir dil modelini (Local LLM) Türk Dili ve Edebiyatı derslerinde rubriğe dayalı notlandırma yapacak şekilde eğitmek ve değerlendirmek** için veri üretme, temizleme, öğretmen tarafından doğrulama ve eğitim formatlarına dönüştürme amacıyla kurulmuştur.

Hedef model; bir sınav sorusunu/görevini, ilgili rubriği ve öğrencinin cevabını birlikte okuyarak **ölçüt bazında puan**, **toplam puan**, **kanıta dayalı kısa gerekçe** ve gerektiğinde **öğretmen incelemesi gerektiren belirsizlik işareti** üretmelidir.

Depo üç sınav türünü destekler:

- **Yazılı sınav** — öğrencinin yazılı cevabı üzerinden rubrik değerlendirmesi.
- **Konuşma sınavı** — öğrencinin konuşmasının doğrulanmış transkripti üzerinden rubrik değerlendirmesi.
- **Dinleme sınavı** — dinleme görevine verilen öğrenci cevabının rubriğe göre değerlendirilmesi.

> Bu depo öncelikle **rubrik tabanlı değerlendirme modelini** eğitir. OCR ve konuşmadan metne (ASR/STT) sistemlerinin kendi hatalarını öğretmek ana hedef değildir. Eğitimde mümkün olduğunca öğretmen tarafından düzeltilmiş öğrenci metni/transkripti canonical cevap olarak kullanılmalıdır.

## Temel tasarım ilkesi

Canonical veri hiçbir eğitim framework'üne bağımlı değildir.

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
SFT / preference / benchmark export
```

Bu nedenle `dataset/records/` altındaki kayıtlar veri setinin **tek gerçek kaynağıdır (single source of truth)**. `exports/` altındaki dosyalar yeniden üretilebilir türevlerdir.

## Modelin öğrenmesi gereken çıktı

Her değerlendirmede mümkün olduğunca şu yapı korunur:

1. Her rubrik ölçütü için puan.
2. Ölçüte ilişkin öğrenci cevabından kısa kanıt veya gözlem.
3. Ölçüte ilişkin kısa, öğretmen diliyle gerekçe.
4. Toplam puan ve mümkün olan maksimum puan.
5. Puanlama güvenilir değilse `needs_review: true`.

Uzun serbest biçimli “düşünce zinciri” veri setine eklenmez. Bunun yerine yalnızca puanı açıklayan **kısa ve denetlenebilir değerlendirme gerekçesi** tutulur.

## Dizin yapısı

```text
.
├── README.md
├── .gitignore
├── docs/
│   ├── DATA_CONTRACT.md
│   ├── ANNOTATION_GUIDE.md
│   └── DATA_QUALITY.md
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
└── exports/
    ├── sft/
    └── preference/
```

### `dataset/records/`

Öğretmen tarafından doğrulanmış canonical JSON kayıtları burada tutulur. Modaliteler birbirinden ayrıdır ancak **aynı veri sözleşmesini** kullanır.

### `dataset/splits/`

Train/validation/test ayrımlarının manifestleri burada tutulur. Aynı öğrenciye veya aynı sınavın çok benzer varyantlarına ait örneklerin farklı split'lere dağılması engellenmelidir.

### `dataset/preferences/`

İleride tercih optimizasyonu için kullanılabilecek `chosen/rejected` değerlendirme çiftleri burada tutulur. `chosen` mutlaka öğretmen onaylı olmalıdır.

### `dataset/benchmarks/`

Eğitim sırasında görülmemesi gereken sabit değerlendirme örnekleri. Model sürümleri burada karşılaştırılır.

### `exports/`

Canonical kayıtlardan eğitim kütüphanesine uygun olarak üretilen JSONL vb. dosyalar. Bu dosyalar veri setinin ana kaynağı değildir.

## Canonical kayıt özeti

Her örnek en az şu alanları içerir:

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
    "criteria": []
  },
  "student_response": {
    "text": "...",
    "source": "teacher_corrected",
    "transcript_quality": null
  },
  "gold_evaluation": {
    "criterion_results": [],
    "total_score": 0,
    "max_score": 20,
    "needs_review": false,
    "overall_feedback": "..."
  },
  "metadata": {
    "status": "teacher_verified",
    "split": null,
    "created_at": "YYYY-MM-DD",
    "tags": []
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
8. Split atanır
9. Eğitim veya benchmark export'u üretilir
```

## Veri kalitesi kuralları

- **Gold etiket öğretmen değerlendirmesidir.** Model tarafından üretilen ilk puan doğrudan gold veri olamaz.
- Yalnızca toplam not değil, mümkün olduğunca **ölçüt bazlı puanlar** saklanır.
- Puan gerekçesi rubriğe ve öğrenci cevabındaki gözlenebilir kanıta dayanır.
- Belirsiz veya rubriğin kapsamadığı durumlarda zorla puan üretmek yerine `needs_review` kullanılır.
- OCR/STT hatası ile öğrencinin gerçek hatası birbirine karıştırılmaz.
- Aynı sorunun çok benzer cevapları train ve test arasında sızıntı oluşturmayacak şekilde gruplanır.
- Benchmark kayıtları eğitim export'larına dahil edilmez.
- Şema değişikliklerinde `schema_version` artırılır; eski kayıtların anlamı sessizce değiştirilmez.

## Gizlilik ve öğrenci verisi

Bu depo öğrenci değerlendirme verisi içereceği için **kişisel veri içermemelidir**.

Canonical kayıtlara şunları koymayın:

- öğrenci adı/soyadı,
- okul numarası,
- T.C. kimlik numarası,
- telefon/e-posta,
- açık okul/sınıf/şube kimliği,
- öğrenciyi doğrudan veya dolaylı biçimde tanımlayabilecek serbest metadata.

Her öğrenci/oturum gerekiyorsa geri döndürülemeyen anonim bir grup kimliği ile temsil edilmelidir. Gerçek ses, taranmış kâğıt, PDF, fotoğraf ve benzeri ham materyaller varsayılan olarak Git'e alınmaz; `.gitignore` bu tür dosyaları dışarıda bırakır.

## Eğitim split'i konusunda önemli kural

Rastgele satır bazlı split tek başına yeterli değildir. Aynı öğrencinin, aynı sınav formunun veya aynı sorunun yakın varyantlarının train ile test arasında sızması model performansını yapay olarak yükseltir.

Tercih edilen ayırma birimi:

```text
student_group + exam_family + question_family
```

Bu gruplar mümkün olduğunca tek bir split içinde kalmalıdır.

## Kayıt adlandırma

Önerilen ID biçimi:

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

## Veri setinin hedefi

Başarı yalnızca modelin öğretmenle aynı toplam notu vermesi değildir. İyi bir model:

- rubriğin hangi ölçütünü neden uyguladığını doğru belirlemeli,
- kısmi puanı tutarlı kullanmalı,
- öğrenci cevabında olmayan bilgiyi varmış gibi değerlendirmemeli,
- rubriğe ek ölçüt uydurmamalı,
- farklı anlatım biçimlerini aynı anlamı taşıdıklarında kabul edebilmeli,
- belirsiz örneklerde aşırı özgüvenli davranmamalıdır.

Bu nedenle benchmarklarda toplam puan hatasına ek olarak **criterion agreement**, **puan sapması**, **review recall** ve mümkünse öğretmenler arası uyumla karşılaştırma izlenmelidir.

---

Bu depo veri setinin kendisini ve veri sözleşmesini tutar. Model mimarisi, quantization yöntemi veya belirli fine-tuning framework'ü canonical veri şemasının parçası değildir.