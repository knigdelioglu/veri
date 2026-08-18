# 500 Pilot — AI Verification Addendum

Bu belge `PILOT_500_PRODUCTION_PLAN.md` içindeki **verification/provenance** varsayımlarını günceller. Sayısal modalite, sınıf, response-quality, hard-case ve question-family hedefleri aksi belirtilmedikçe geçerlidir.

## 1. Doğrulama kaynağı

Mevcut pilot üretim insan öğretmen doğrulaması kullanmaz.

Sentetik kayıtlar canonical'a:

```json
{
  "status": "ai_verified",
  "verification_source": "ai",
  "provenance": "synthetic"
}
```

ile girer.

`teacher_verified` yalnız gerçekten insan tarafından doğrulanmış veri ileride eklenirse kullanılır.

## 2. Pilotun provenance bileşimi

Eski plandaki `300 real_anonymized + 200 synthetic` hedefi **mevcut AI üretim pilotu için zorunlu değildir**.

Bu pilotun ana amacı veri üretim mimarisini ve fine-tune karar yüzeyini kalibre etmektir. Dolayısıyla 500 kaydın tamamı sentetik olabilir.

Gerçek anonim öğrenci verisi daha sonra:

- gerçek kullanım benchmarkı,
- distribution-shift testi,
- synthetic ↔ real performans farkı

ölçmek için ayrı slice olarak eklenmelidir.

## 3. Review sayısı

`review_count` AI-only kayıtta bağımsız insan sayısı değildir; deliberate AI kalite geçişi sayısıdır.

- normal verified: en az 1,
- validation/test/benchmark: en az 2,
- borderline: en az 2,
- gold `needs_review=true`: en az 2.

## 4. Borderline ve `needs_review`

Eski plandaki “50 needs_review” hedefi **sert kota değildir**.

Wave 1 ikinci AI denetiminde 10 başlangıç `needs_review` adayının 9'u yanlış escalation olarak bulundu. Bu nedenle:

> `borderline` olmak, `needs_review=true` olmak anlamına gelmez.

Rubrik mevcut anchor ile güvenilir puan veriyorsa cevap puanlanır.

`needs_review=true` yalnız:

- STT/OCR belirsizliği anlamı değiştirebiliyorsa,
- kritik kanıt eksikse,
- rubric gerçekten gerekli ayrımı yapamıyorsa,
- verilen evidence güvenilir puan üretmeye yetmiyorsa

kullanılır.

Hedef aralık `%8–12` izlenmeye devam eder; fakat oranı doldurmak için sahte escalation üretilmez. Bunun yerine sonraki dalgalarda **gerçekten çözülemez evidence koşulları** tasarlanır.

## 5. Sentetik speaking verisi

Gerçek audio bulunmayan sentetik speaking örneklerinde:

- telaffuz,
- akıcılık/duraksama,
- vurgu-tonlama,
- ses kullanımı

uydurulmaz.

Normal sentetik speaking kaydı transcript-only rubric kullanır.

Audio kanıtı gerektiren bir criterion yalnız deliberate `missing_evidence`/escalation örneğinde tutulabilir; bu durumda modelin doğru davranışı puanı uydurmak değil `needs_review` üretmektir.

## 6. Wave 1 mevcut durum

İlk 100 aday:

- 50 written / 25 speaking / 25 listening,
- her sınıftan 25,
- hedef response-quality dağılımı korunmuş,
- 18 hard case,
- 4 adversarial,
- 62 recalibration override,
- 27 metin revizyonu,
- 30 yüksek riskli aday için ikinci AI review,
- 9 false-positive `needs_review` düzeltmesi,
- 1 gerçek escalation adayı

ile canonical materialization'a hazır durumdadır.

Ayrıntılar:

- `dataset/candidates/pilot-wave-1/AUDIT.md`
- `dataset/candidates/pilot-wave-1/AI_REVIEW_PHASE_A.md`
- `dataset/candidates/pilot-wave-1/recalibration/`

## 7. Bundan sonraki dalgalar

Wave 2–5 üretiminde her 100 kayıt için:

```text
üretim
↓
rubric-first recalibration
↓
yüksek riskli ikinci AI review
↓
canonical ai_verified materialization
↓
quality/split gate
```

uygulanır.

Metinlerin doğallığı, rubrik uyumu veya cevap çeşitliliği belirgin biçimde düşmeye başladığında yeni dalga üretimi durdurulur ve hata analizi yapılır.
