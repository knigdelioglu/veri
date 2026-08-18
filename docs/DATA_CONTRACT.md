# Veri Sözleşmesi

## 1. Amaç

Bu sözleşme, Türk Dili ve Edebiyatı yazılı, konuşma ve dinleme sınavlarından üretilecek canonical eğitim kayıtlarının anlamını tanımlar. Canonical kayıtlar belirli bir model, tokenizer veya fine-tuning framework'üne bağlı değildir.

## 2. Kayıt birimi

Bir kayıt **tek bir öğrencinin tek bir exact soru/görev için rubrikle değerlendirilmiş cevabını** temsil eder.

Çekirdek bileşenler:

1. `task`: soru/görev ve gerekli bağlam,
2. `rubric`: puanlama ölçütleri,
3. `student_response`: öğrencinin canonical cevabı,
4. `gold_evaluation`: öğretmen tarafından doğrulanmış hedef değerlendirme,
5. `metadata`: leakage, veri üretimi ve kalite kontrol metadata'sı.

## 3. Temel alanlar

### `id`

Depo içinde benzersiz canonical kayıt kimliği. Örnek:

```text
tde12-written-000001
```

### `schema_version`

Canonical sözleşme sürümü. İlk sürüm `1.0`'dır.

### `modality`

- `written`
- `speaking`
- `listening`

### `language`

Şimdilik `tr`.

### `grade`

9–12 arasında sınıf düzeyi.

## 4. `task`

### `task_id`

Birebir aynı soru/görevin veri seti içindeki kararlı kimliğidir. Aynı soruya verilen farklı öğrenci cevapları aynı `task_id` değerini kullanır.

`task_id` iki amaçla kullanılır:

1. exact soru başına veri kotasını ölçmek,
2. birebir aynı sorunun farklı splitlere sızmasını engellemek.

`task_id` veri kürasyonu içindir ve modelin SFT promptuna verilmez.

### `prompt`

Öğrencinin gördüğü soru veya görevdir.

### `context`

Değerlendirme için gerekli ek metin/veridir. Gerekmiyorsa `null` olabilir.

### `max_score`

Görevin toplam azami puanı.

## 5. `rubric`

Her ölçütün kararlı bir `criterion_id` değeri bulunur.

Her criterion:

- `name`,
- `description`,
- `max_score`,
- `scoring_anchors`,
- `evidence_sources`

alanlarını taşır.

Desteklenen kanıt kaynakları:

- `response_text`
- `task_context`
- `audio_delivery`
- `teacher_observation`

Bir model mevcut girdide bulunmayan kanıtı varmış gibi kullanmamalıdır.

Konuşma sınavında transkript yalnız **ne söylendiğini** temsil eder. Telaffuz, vurgu-tonlama ve gerçek zamanlı akıcılık gibi özellikler yalnız uygun ses/gözlem kanıtı varsa puanlanır.

## 6. `student_response`

### `text`

Modelin değerlendireceği canonical öğrenci cevabı veya doğrulanmış konuşma transkriptidir.

### `source`

- `manual`
- `teacher_corrected`
- `verified_ocr`
- `verified_stt`

OCR/STT'nin eklediği hata düzeltilir; öğrencinin kendi dil/anlatım hatası canonical cevapta korunur.

### `observations`

Metinden güvenilir biçimde çıkarılamayan fakat rubrik için gerekli öğretmen gözlemleridir.

```json
{
  "label": "akıcılık",
  "value": "Genel olarak akıcı; iletişimi bozmayan iki kısa duraksama var.",
  "source": "teacher"
}
```

## 7. `gold_evaluation`

Modelin öğrenmesi hedeflenen öğretmen onaylı değerlendirmedir.

Her `criterion_result`:

- `criterion_id`,
- `score`,
- `evidence`,
- `justification`

alanlarını taşır.

Ayrıca:

- `total_score`,
- `max_score`,
- `needs_review`,
- `review_reason`,
- `overall_feedback`

bulunur.

`justification` uzun düşünce zinciri değildir; yalnız puanın dışarıdan denetlenebilmesini sağlayan kısa gerekçedir.

### `needs_review` semantiği

`needs_review=true` her zaman “annotation tamamlanmadı” anlamına gelmez.

**Çözülmemiş annotation:** gold karar güvenilir değilse kayıt `draft`, `annotated` veya `quarantined` kalır ve export edilmez.

**Gold escalation:** doğru model davranışı insan incelemesine yönlendirmekse kayıt `teacher_verified + needs_review=true` olabilir. Bu örnek en az iki bağımsız insan incelemesi görür ve curated SFT exportuna dahil edilir.

## 8. Lifecycle metadata

### `status`

- `draft`: tamamlanmamış,
- `annotated`: ilk değerlendirmesi yapılmış fakat final kalite kapısından geçmemiş,
- `teacher_verified`: canonical gold karar onaylı,
- `quarantined`: şüpheli veya kullanıma uygun olmayan kayıt.

### `pii_reviewed`

Kişisel veri kontrolünün tamamlandığını belirtir. `teacher_verified` kayıt `pii_reviewed=true` olmalıdır.

## 9. Split ve leakage anahtarları

### `split`

- `train`
- `validation`
- `test`
- `benchmark`
- `null`

### `task.task_id`

Birebir aynı soru/görev. Exact soru farklı splitlere ayrılamaz.

### `subject_group_id`

Öğrenciyi tanımlamayan rastgele/grup kimliği. Gerçek okul numarası veya kolay geri çözülebilir öğrenci kimliği kullanılmaz.

### `exam_family`

Aynı sınav/form ailesi.

### `question_family`

Birebir aynı olmayan ancak aynı veya çok yakın beceriyi/soru yapısını temsil eden varyant ailesi.

Curated splitter bu dört anahtar üzerinde bağlı bileşen kurar:

```text
task_id
OR subject_group_id
OR exam_family
OR question_family
```

Bu nedenle bir bağlantı zinciriyle birbirine bağlı kayıtların tamamı aynı splitte kalır. Aynı dört anahtar benchmark izolasyonunda ve leakage kontrolünde de kullanılır.

## 10. Veri üretim metadata'sı

Bu alanlar **model girdisi değildir**; veri setinin dengesi ve doğrulanabilirliği içindir.

### `response_quality`

- `full_correct`
- `high_partial`
- `mid_partial`
- `low_partial`
- `incorrect`
- `blank_irrelevant`
- `borderline`

`teacher_verified` kayıtlar için üretim kalite kapısı bu alanı zorunlu tutar.

### `hard_case_types`

Örneğin hangi deliberate karar sınırını sınadığını belirtir. Birden çok değer taşıyabilir.

### `adversarial`

Örnek prompt injection veya başka deliberate manipülasyon içeriyorsa `true` olur.

### `review_count`

Canonical gold karar üzerinde kaç bağımsız insan değerlendirmesi bulunduğunu belirtir.

- normal teacher-verified: en az 1,
- validation/test/benchmark: en az 2,
- `borderline`: en az 2,
- gold `needs_review=true`: en az 2.

### `adjudicated`

Bağımsız değerlendirmeler arasında anlamlı uyuşmazlık oluşmuş ve nihai gold karar ortak incelemeyle çözülmüşse `true` yapılır. Çift değerlendirme tek başına adjudication değildir.

## 11. `provenance`

- `synthetic`
- `real_anonymized`

Sentetik örnek gerçek öğrenci verisi gibi etiketlenmemelidir. Model tarafından üretilen örnek, öğretmen doğrulaması olmadan gold kabul edilmez.

## 12. Gizlilik

Canonical veri öğrenci adı, okul numarası, T.C. kimlik numarası, telefon/e-posta, açık okul/şube bilgisi veya kişiyi yeniden tanımlamayı kolaylaştıracak serbest metadata içermemelidir.

Ham ses, PDF, fotoğraf ve taranmış materyaller varsayılan olarak Git'e alınmaz.

## 13. Canonical ve türetilmiş veri

Canonical kayıt:

```text
dataset/records/<modality>/<id>.json
```

Canonical kayıt tek gerçek kaynaktır. `exports/` altındaki SFT/preference dosyaları yeniden üretilebilir türevlerdir.

## 14. Curated SFT girdisi

Modele:

```text
task (task_id hariç)
rubric
student_response
```

verilir.

Assistant hedefi yalnız `gold_evaluation` yapısıdır.

Şunlar model promptuna verilmez:

- `task_id`,
- `subject_group_id`,
- `exam_family`,
- `question_family`,
- `response_quality`,
- `hard_case_types`,
- `adversarial`,
- `review_count`,
- `adjudicated`,
- diğer annotation metadata'sı.

Bu ayrım modelin veri kürasyonu etiketlerinden kestirme öğrenmesini engeller.
