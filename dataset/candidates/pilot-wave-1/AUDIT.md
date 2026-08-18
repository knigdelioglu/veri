# Pilot Wave 1 — Üretim Kalite Denetimi

Durum: **PAUSED — score recalibration required before Wave 2**

Bu denetim, ilk 100 sentetik aday üretildikten sonra yapılmıştır. Adaylar `teacher_verified` değildir ve canonical eğitime giremez.

## Geçen kontroller

- 100 aday üretildi.
- Modalite: 50 written / 25 speaking / 25 listening.
- Sınıf: 9–12 her biri 25.
- `response_quality`: 20 full_correct / 20 high_partial / 20 mid_partial / 15 low_partial / 10 incorrect / 5 blank_irrelevant / 10 borderline.
- 18 hard-case adayı.
- 4 adversarial/prompt-injection adayı.
- 10 `needs_review` adayı.
- 4 question family, 8 exact task; family başına 25, task başına 12–13 cevap.
- 98 dolu öğrenci cevabında birebir tekrar yok.
- Öğrenci cevaplarının içerik ve dil çeşitliliğinde belirgin mekanikleşme gözlenmedi.
- Candidate veriye `teacher_verified` veya gerçek öğretmen gözlemi etiketi verilmedi.

## Durdurma nedeni

Önerilen criterion score'ların bir bölümünde **response-quality kotasını koruma baskısı, rubrik çıpasının önüne geçmeye başladı**. Bu veri gold olarak kullanılmadan önce puanların yalnız rubriğe göre yeniden kalibre edilmesi gerekiyor.

Tespit edilen örnek sınıfları:

1. **Grade 9 / textual evidence** — iki uygun metinsel kanıt kullanan bazı `high_partial` yanıtlar 2/3 önerilmiş; mevcut rubrik çıpası iki uygun kanıt için 3/3 gerektiriyor.
2. **Grade 10 / viewpoint** — kısa fakat doğru bakış açısı tanımları bazı düşük-kısmi örneklerde gereğinden düşük puanlanmış; `effect` ile `clarity` puanları da cevapta gerçekten bulunan unsura göre yeniden dağıtılmalı.
3. **Grade 11 / speaking** — çok ölçütlü rubrikte kısa fakat ilgili cevaplar içerik + düzen + delivery'den doğal olarak puan topluyor. `low_partial` etiketini korumak için gerçek criterion score düşürülmemeli.
4. **Grade 12 / listening** — “dedeyi hatırlamak” gibi cevaplar mevcut comprehension çıpasına göre 6/6'ya yaklaşırken kategori hedefi nedeniyle 3/6 önerilmiş örnekler var. Cevap metni veya kategori değişebilir; gold score değiştirilemez.

## Karar

- Wave 1 candidate metinleri korunur.
- Wave 2 üretimi **başlatılmaz**.
- Önce 100 adayın criterion score'ları rubrik çıpalarına göre yeniden kalibre edilir.
- Recalibration sonrası `response_quality` dağılımı yeniden ölçülür. Dağılım bozulursa puanları zorlamak yerine yeni/yeniden yazılmış cevaplarla kota onarılır.
- Konuşma adaylarındaki sentetik delivery gözlemleri gerçek öğretmen/ses doğrulaması olmadan canonical `teacher_observation` olamaz.
- Ancak bu denetim PASS olduktan sonra öğretmen review/promotion ve Wave 2 başlar.

## İlke

**Gold puan, kota hedefinden türetilmez.** Önce cevap rubriğe göre doğru puanlanır; dağılım gerekiyorsa cevap üretimi değiştirilir. Puan hiçbir zaman hedef kategoriye uydurulmaz.
