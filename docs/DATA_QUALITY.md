# Veri Kalitesi ve Değerlendirme

## Kalite kapıları

Eğitim export'una girecek her kayıt için aşağıdaki kapılar uygulanmalıdır.

### Q0 — Şema

- JSON Schema doğrulaması geçiyor.
- Zorunlu alanlar mevcut.
- Puanlar negatif değil ve üst sınırlara uymaktadır.

### Q1 — Gizlilik

- `pii_reviewed == true`.
- Öğrenciyi tanımlayan bilgi yok.
- Ham görsel/ses/PDF Git geçmişine eklenmemiş.

### Q2 — Annotation

- `status == teacher_verified`.
- Her rubrik ölçütünün bir sonucu var.
- Kısa gerekçe rubriğe dayanıyor.
- Kanıt öğrenci cevabı veya mevcut gözlemle destekleniyor.

### Q3 — Matematik

- Ölçüt puanları toplamı `total_score` ile uyumlu.
- Rubrik toplam azami puanı ile görev azami puanı uyumlu.
- Hiçbir ölçüt kendi `max_score` değerini aşmıyor.

### Q4 — Kanıt uygunluğu

Özellikle konuşma sınavında modelin görmediği kanala dayalı puan üretilmemelidir. Örneğin yalnızca transkript varken telaffuz puanı gold hedefe ekleniyorsa gerekli öğretmen gözlemi de model girdisine dahil edilmelidir.

### Q5 — Split sızıntısı

Aşağıdaki gruplar train/validation/test arasında mümkün olduğunca bölünmemelidir:

- aynı `subject_group_id`,
- aynı `exam_family`,
- aynı `question_family` veya çok yakın soru varyantı.

Benchmark verisi hiçbir eğitim export'una dahil edilmez.

## Veri seti dengesi

Sadece yüksek notlu “temiz” cevaplar toplamak modelin gerçek sınıf performansını düşürür. Veri setinde şu örnekler de bulunmalıdır:

- tamamen yanlış cevap,
- boş/çok kısa cevap,
- kısmen doğru cevap,
- doğru fakat beklenmedik ifade biçimi,
- gereksiz bilgi içeren cevap,
- çelişkili cevap,
- rubriğin sınırında kalan cevap,
- öğretmen incelemesi gerektiren örnek.

Her puan bandının ve her sınıf düzeyinin makul temsili hedeflenmelidir.

## Model benchmark metrikleri

Tek başına exact total-score accuracy yeterli değildir. En az şu ölçüler önerilir:

- **MAE / mean absolute score error**: toplam puan sapması,
- **criterion MAE**: ölçüt bazlı puan sapması,
- **exact total agreement**: öğretmenle aynı toplam puan oranı,
- **within-tolerance agreement**: ör. ±1 puan içindeki oran,
- **criterion agreement**: aynı ölçüt kararının uyumu,
- **review recall**: gerçekten belirsiz örnekleri `needs_review` ile yakalama oranı,
- **review precision**: gereksiz öğretmen incelemesi üretmeme,
- mümkünse öğretmenler arası uyumla karşılaştırma.

## Benchmark tasarımı

Benchmark:

- sabit tutulmalı,
- eğitimde görülmemeli,
- farklı sınıf düzeylerini içermeli,
- yazılı/konuşma/dinleme örneklerini kapsamalı,
- kolay ve zor örnekler içermeli,
- sınır puanları ile alternatif doğru anlatımları özellikle içermelidir.

Model sürümleri aynı benchmark üzerinde karşılaştırılmalıdır.
