# Pilot Wave 1 — Üretim Kalite Denetimi

Durum: **RECALIBRATED — PENDING TEACHER REVIEW**

İlk 100 sentetik aday üretildikten sonra yapılan denetimde, bazı önerilen criterion score'ların cevap profili kotasına fazla bağlı kaldığı tespit edilmişti. Wave 2 bu nedenle durduruldu. Recalibration fazı şimdi tamamlandı; adaylar hâlâ `teacher_verified` değildir ve canonical eğitime giremez.

## Üretim kontrolleri

- 100 aday üretildi.
- Modalite: 50 written / 25 speaking / 25 listening.
- Sınıf: 9–12 her biri 25.
- Hedef `response_quality`: 20 full_correct / 20 high_partial / 20 mid_partial / 15 low_partial / 10 incorrect / 5 blank_irrelevant / 10 borderline.
- 18 hard-case adayı.
- 4 adversarial/prompt-injection adayı.
- 10 `needs_review` adayı.
- 4 question family, 8 exact task; family başına 25, task başına 12–13 cevap.
- 98 dolu öğrenci cevabında birebir tekrar yok.
- Candidate veriye `teacher_verified` etiketi verilmedi.

## Recalibration sonucu

Rubrik çıpaları tekrar esas alınarak bütün family'ler yeniden tarandı.

- **62 adayda** puan veya değerlendirme override'ı oluşturuldu.
- **27 adayın metni**, hedef profile gerçekten uyması için yeniden yazıldı. Puan hiçbir adayda kota uğruna düşürülmedi veya yükseltilmedi.
- Grade 9'da iki uygun metinsel kanıt kullanan cevapların `textual_evidence` puanları yükseltildi; düşük-kısmi olması gereken bazı metinler sadeleştirildi.
- Grade 10'da doğru bakış açısı ve bilgi etkisi taşıyan fakat gereğinden düşük puanlanan cevaplar düzeltildi; `low_partial`/`mid_partial` örnekler gerektiğinde yeniden yazıldı.
- Grade 11 konuşma adaylarında **sentetik delivery gözlemleri gold olmaktan tamamen çıkarıldı**. 25 kaydın `delivery_score` değeri `null` kabul edilir ve gerçek ses/öğretmen gözlemi olmadan tamamlanamaz.
- Grade 12 dinlemede temel nedeni açıkça söyleyen cevapların comprehension puanları rubrik çıpasına yükseltildi; high/mid/low profil dengesini korumak için gereken metinler yeniden üretildi.

Recalibration override'ları:

```text
dataset/candidates/pilot-wave-1/recalibration/
├── g09-poetry-theme.json
├── g10-narrator-viewpoint.json
├── g11-speaking-character.json
├── g12-listening-inference.json
└── manifest.json
```

Bir aday için override varsa öğretmen review sırasında **override içindeki `text_override` ve recalibrated score** esas alınır. Override olmayan alanlar kaynak candidate dosyasından gelir.

## Değişmeyen temel ilke

**Gold puan, kota hedefinden türetilmez.**

1. Önce cevap rubriğe göre puanlanır.
2. Cevap hedef kalite sınıfına uymuyorsa gold puan zorlanmaz.
3. Bunun yerine öğrenci cevabı yeniden yazılır veya yeni cevap üretilir.
4. Rewritten cevap tekrar rubriğe göre puanlanır.

## Konuşma için özel blokaj

Konuşma candidate dosyalarındaki `synthetic_candidate` kaynaklı akıcılık/ses gözlemleri yalnız üretim taslağıdır. Bunlar:

- `teacher_observation` değildir,
- gerçek ses kanıtı değildir,
- canonical gold'a taşınamaz,
- `delivery` puanı üretmek için kullanılamaz.

Bu nedenle Grade 11'de içerik/yorum/kanıt/düzen önerileri review edilebilir; `delivery` ise gerçek ses veya öğretmen gözlemi gelene kadar açık kalır.

## Sıradaki kalite kapısı

Wave 2 hâlâ başlatılmaz. Önce teacher review yapılır.

Önerilen sıra:

1. Yüksek riskli review örneklerini kontrol et.
2. Rubrik ve effective response text uyumunu doğrula.
3. Recalibrated criterion score'ları kabul et veya düzelt.
4. `needs_review` hedeflerinin gerçekten escalation gerektirdiğini doğrula.
5. Adversarial cevaplarda öğrenci talimatının puanı etkilemediğini doğrula.
6. Konuşma delivery alanını gerçek kanıt gelmeden kapatma.
7. Yalnız onaylanan kayıtları canonical `dataset/records` içine materialize et.

## Promotion şartı

Bir kayıt ancak aşağıdakiler tamamlandıktan sonra canonical olabilir:

```text
human teacher review
+ PII review
+ rubric-correct criterion scores
+ effective response text accepted
+ speaking ise required delivery evidence
```

Bundan önce `status=teacher_verified` verilemez.
