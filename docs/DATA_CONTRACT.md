# Veri Sözleşmesi

## 1. Amaç

Bu sözleşme, Türk Dili ve Edebiyatı yazılı, konuşma ve dinleme sınavlarından üretilecek canonical eğitim kayıtlarının anlamını tanımlar. Canonical kayıtlar belirli bir model, tokenizer veya fine-tuning framework'üne bağlı değildir.

## 2. Kayıt birimi

Bir kayıt **tek bir öğrencinin tek bir soru/görev için rubrikle değerlendirilmiş cevabını** temsil eder.

Bir kayıt şu dört çekirdek bileşenden oluşur:

1. `task`: soru/görev ve gerekli bağlam,
2. `rubric`: puanlama ölçütleri,
3. `student_response`: öğrencinin canonical cevabı,
4. `gold_evaluation`: öğretmen tarafından doğrulanmış hedef değerlendirme.

## 3. Zorunlu alanlar

### `id`

Depo içinde benzersiz kayıt kimliği. Örnek: `tde12-written-000001`.

### `schema_version`

İlk sürüm `1.0`'dır. Alanların anlamı geriye dönük uyumsuz değişirse sürüm artırılır.

### `modality`

- `written`
- `speaking`
- `listening`

### `language`

Şimdilik `tr`.

### `grade`

9–12 arasında sınıf düzeyi.

## 4. Task

`task.prompt` öğrencinin gördüğü soru veya görevdir.

`task.context`, değerlendirme için gerekli ek metin/veridir. Örneğin verilen şiir parçası, dinleme metninin değerlendirme için gerekli özeti veya görev yönergesi. Gerekmiyorsa `null` olabilir.

`task.max_score`, bu kayıt için toplam azami puandır.

## 5. Rubrik

Her ölçütün kararlı bir `criterion_id` değeri bulunur. Ölçüt metni değişse bile eski veriler sessizce yeni anlamla yorumlanmamalıdır.

Her ölçüt şunları içerir:

- `name`
- `description`
- `max_score`
- `scoring_anchors`: puan seviyelerini açıklayan çıpalar
- `evidence_sources`: bu ölçütün hangi kanıta dayanabileceği

Desteklenen kanıt kaynakları:

- `response_text`: öğrencinin yazılı cevabı veya doğrulanmış transkripti
- `task_context`: soruda/görevde verilen bağlam
- `audio_delivery`: gerçek ses kaydında gözlenebilen özellik
- `teacher_observation`: öğretmenin yapılandırılmış gözlemi

Bir model, mevcut girdide bulunmayan bir kanıt kaynağını varmış gibi kullanmamalıdır.

## 6. Student response

### `text`

Modelin değerlendireceği canonical öğrenci cevabıdır.

Yazılı sınavda OCR kullanıldıysa OCR çıktısı öğretmen tarafından kontrol edilip düzeltilmelidir. Konuşma sınavında STT kullanıldıysa transkript mümkün olduğunca doğrulanmalıdır.

### `source`

- `manual`
- `teacher_corrected`
- `verified_ocr`
- `verified_stt`

### `observations`

Metinden çıkarılamayan fakat rubrik için gerekli bilgiler için isteğe bağlı yapılandırılmış gözlemler.

Örnek:

```json
{
  "label": "akıcılık",
  "value": "Konuşma genel olarak akıcı; iki kısa duraksama var.",
  "source": "teacher"
}
```

Bu alan özellikle konuşma sınavlarında önemlidir. Transkriptten telaffuz, vurgu-tonlama veya gerçek akıcılık doğrudan çıkarılmamalıdır.

## 7. Gold evaluation

`gold_evaluation` modelin öğrenmesi hedeflenen öğretmen onaylı değerlendirmedir.

Her `criterion_result` şunları içerir:

- `criterion_id`
- `score`
- `evidence`: öğrenci cevabı/gözleminden kısa kanıtlar
- `justification`: rubriğe bağlı kısa açıklama

Ayrıca:

- `total_score`
- `max_score`
- `needs_review`
- `review_reason`
- `overall_feedback`

bulunur.

`justification` uzun düşünce zinciri değildir. Yalnızca puanın dışarıdan denetlenebilmesini sağlayan kısa gerekçedir.

## 8. Metadata

### `status`

- `draft`: kayıt tamamlanmamış
- `annotated`: ilk öğretmen değerlendirmesi yapılmış
- `teacher_verified`: eğitim için onaylanmış
- `quarantined`: şüpheli/uyumsuz kayıt; export edilmez

Yalnızca `teacher_verified` kayıtlar eğitim export'una girebilir.

### `split`

- `train`
- `validation`
- `test`
- `benchmark`
- `null`

### Sızıntı kontrol alanları

- `subject_group_id`: öğrenciyi tanımlamayan rastgele grup kimliği; gerçek numaradan türetilmiş kolay çözülebilir hash kullanılmamalıdır.
- `exam_family`: aynı sınav/form ailesini gruplar.
- `question_family`: aynı veya yakın soru varyantlarını gruplar.

### Gizlilik

`pii_reviewed: true` olmadan kayıt export edilmemelidir.

## 9. Canonical ve türetilmiş veri

Canonical kayıt:

```text
dataset/records/<modality>/<id>.json
```

Split manifestleri canonical kaydı kopyalamak zorunda değildir; tercihen kayıt ID'lerini listeler.

SFT/preference dosyaları `exports/` altında üretilir ve yeniden üretilebilir kabul edilir.

## 10. Eğitim girdisi üretme ilkesi

Bir SFT örneği üretilirken modele şu içerikler verilir:

```text
Görev + gerekli bağlam + rubrik + öğrenci cevabı + mevcut yapılandırılmış gözlemler
```

Hedef çıktı ise yalnızca değerlendirme sözleşmesidir:

```text
ölçüt puanları + kısa kanıt + kısa gerekçe + toplam + needs_review
```

Öğrenci kimliği, kaynak dosya adı, okul bilgisi veya annotation sırasında kullanılan dahili notlar modele verilmez.
