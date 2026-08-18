# Öğretmen Annotation Rehberi

## Amaç

Annotation'ın amacı modele “bir öğretmenin nasıl düşündüğünü” uzun biçimde yazmak değil; **rubriği aynı kurallarla uygulayan, denetlenebilir gold değerlendirme** üretmektir.

## Adım 1 — Cevabı doğrula

- Yazılı cevap OCR'dan geldiyse metni asıl cevapla karşılaştır.
- Konuşma cevabı STT'den geldiyse anlam değiştiren transkripsiyon hatalarını düzelt.
- Öğrencinin dilbilgisi/anlatım hatalarını düzeltme; yalnızca OCR/STT'nin eklediği hataları düzelt.
- Okunamayan/duyulamayan bölüm varsa tahmin etme; açık bir işaret kullan veya kaydı karantinaya al.

## Adım 2 — Kişisel veriyi temizle

Ad, soyad, okul numarası, okul/şube bilgisi veya kişiyi tanımlayan serbest metin varsa kaldır veya nötrleştir. `pii_reviewed` yalnızca bu kontrol tamamlandığında `true` yapılır.

## Adım 3 — Rubriği dondur

Gold değerlendirme başlamadan önce kullanılan rubrik sürümü belirli olmalıdır. Annotation bittikten sonra rubrik anlamını sessizce değiştirmek mevcut gold etiketleri geçersiz kılar.

## Adım 4 — Ölçütleri tek tek puanla

Her ölçütte:

1. Ölçütün istediği davranışı belirle.
2. Öğrenci cevabında/gözleminde ilgili kanıtı bul.
3. Uygun puan çıpasını seç.
4. Kısa gerekçe yaz.

Başka ölçütteki başarıyı bu ölçüte taşımayın. Rubrikte olmayan “genel izlenim” puanı eklemeyin.

## Adım 5 — Kanıtı kısa tut

`evidence`, puanı doğrulamak için yeterli fakat mümkün olduğunca kısa olmalıdır. Öğrenci cevabının tamamını tekrar etmeyin.

## Adım 6 — Belirsizliği işaretle

Aşağıdaki durumlarda `needs_review: true` düşünülmelidir:

- rubrik iki farklı makul puana izin veriyor,
- öğrenci cevabının kritik bölümü okunamıyor/duyulamıyor,
- rubrikte gerekli kanıt girdi içinde yok,
- soru veya rubrik hatalı/eksik,
- toplam puan ile ölçüt puanları uyuşmuyor,
- öğretmenler arasında anlamlı görüş ayrılığı var.

## Yazılı sınav kuralları

- Öğrencinin farklı ama anlamca doğru ifadesini anahtar cümleyle birebir eşleşmediği için reddetmeyin.
- Cevapta bulunmayan bilgiyi “kastetmiştir” diyerek tamamlamayın.
- Dil/anlatım yalnızca rubrikte ölçütse puanı etkiler.
- Kısmi doğruluk varsa rubrik izin veriyorsa kısmi puan kullanın.

## Konuşma sınavı kuralları

Transkript yalnızca **ne söylendiğini** güvenilir biçimde temsil eder. Şunlar transkriptten tek başına puanlanmamalıdır:

- telaffuz,
- vurgu ve tonlama,
- ses şiddeti,
- gerçek zamanlı akıcılık/duraksama,
- beden dili.

Bu ölçütler kullanılacaksa `teacher_observation` veya gelecekte doğrudan ses girdisi gibi uygun kanıt sağlanmalıdır.

## Dinleme sınavı kuralları

Dinleme görevinde modelin görevi öğrencinin cevabını değerlendirmektir. Soru ve rubrik doğru cevabı değerlendirmek için yeterliyse ham ses kaydı gerekmez. Değerlendirme için kaynak metindeki özel bilgi gerekiyorsa ilgili `task.context` eklenmelidir.

## Öğretmenler arası uyuşmazlık

Mümkünse veri setinin bir bölümünü iki öğretmen bağımsız puanlasın. Uyuşmazlıklar:

- önce rubrik yorumu açısından incelenir,
- gerekiyorsa ortak kararla adjudication yapılır,
- nihai gold kayıt tek ve açık bir puan seti içerir,
- sistematik anlaşmazlık görülüyorsa rubrik iyileştirilir.

## Export öncesi minimum kabul koşulu

Bir kayıt ancak şu koşullarla eğitime girebilir:

- `status == teacher_verified`
- `pii_reviewed == true`
- ölçüt puanları geçerli aralıkta
- ölçüt puanları toplamı `total_score` ile tutarlı
- `total_score <= max_score`
- rubrik ölçüt ID'leri ile sonuç ölçüt ID'leri eşleşiyor
- split sızıntı kontrolü tamamlanmış
