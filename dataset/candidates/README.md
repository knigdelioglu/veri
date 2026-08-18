# Candidate veri staging alanı

`dataset/candidates/`, model/üretici tarafından oluşturulan fakat henüz öğretmen tarafından doğrulanmamış veri adaylarını tutar.

Bu alan **canonical eğitim verisi değildir**. Buradaki kayıtlar `dataset/records/` altına otomatik olarak kopyalanmamalı ve SFT exportuna dahil edilmemelidir.

## Durum akışı

```text
generated_pending_teacher_review
        ↓
öğretmen içerik + rubrik + önerilen puanları inceler
        ↓
gerekirse düzeltir
        ↓
PII kontrolü
        ↓
canonical record oluşturulur
        ↓
annotated / teacher_verified
        ↓
veri check
```

## Alanların anlamı

Candidate dosyalarındaki `scores`, `needs_review`, `review_reason` ve konuşma `observations` alanları **öneri** niteliğindedir. Öğretmen doğrulaması yapılmadan `gold_evaluation` veya `teacher_observation` kabul edilmez.

Konuşma adaylarında `observations[].source = synthetic_candidate` kullanılır. Canonical kayda geçerken bu gözlem gerçek ses/gözlemle doğrulanmalı ve ancak o zaman `source = teacher` hâline getirilmelidir.

## Pilot dalgaları

Her üretim dalgası kendi klasöründe tutulur. Dalga manifesti hedef dağılımı ve üretilen aday sayısını kaydeder. Canonical veri setinin tek gerçek kaynağı yine `dataset/records/` olarak kalır.
