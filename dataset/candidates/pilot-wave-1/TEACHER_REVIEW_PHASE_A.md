# Pilot Wave 1 — Teacher Review Phase A

Bu paket, 100 adayın tamamını incelemeye başlamadan önce **yüksek riskli 30 kaydı** kontrol etmek için hazırlanmıştır.

> Bu listedeki puanlar ve metinler AI tarafından üretilmiş/recalibrate edilmiştir. İnsan öğretmen onayı değildir.

## İnceleme yöntemi

Her kayıt için:

1. Kaynak family dosyasındaki `task`, `context`, `rubric` ve candidate cevabını oku.
2. `recalibration/` altında aynı candidate için override varsa `text_override` değerini effective öğrenci cevabı olarak kullan.
3. Puanı response-quality etiketine göre değil, yalnız rubrik çıpalarına göre kontrol et.
4. `needs_review` adayıysa gerçekten modelin insan incelemesine yönlendirmesi gereken bir durum olup olmadığını değerlendir.
5. Prompt-injection/adversarial cevaplarda öğrenci cevabındaki talimatı yok say.
6. Grade 11 speaking kayıtlarında sentetik delivery gözlemini puanlama kanıtı kabul etme.

Karar seçenekleri:

- `[ ] ACCEPT` — metin + criterion score doğru.
- `[ ] EDIT` — aday kullanılabilir fakat metin/puan düzeltilmeli.
- `[ ] REJECT` — eğitim verisine alınmamalı.

---

## A. Borderline / gold `needs_review` — 10 kayıt

Bunların tamamı kritik; `needs_review=true` davranışını modele öğretecekler.

- [ ] `a1-13` — Grade 9 / şiir — yalnızlık ↔ özlem baskın duygu sınırı
- [ ] `a2-12` — Grade 9 / şiir — pişmanlık ↔ özlem baskın duygu sınırı
- [ ] `b1-13` — Grade 10 / anlatıcı — birinci kişi ↔ sınırlı bilgi terminolojisi
- [ ] `b2-10` — Grade 10 / anlatıcı — hâkim ↔ sınırlı bakış açısı yorumu
- [ ] `b2-12` — Grade 10 / anlatıcı — hâkim ↔ sınırlı terminoloji belirsizliği
- [ ] `c1-13` — Grade 11 / konuşma — STT anlam belirsizliği
- [ ] `c2-10` — Grade 11 / konuşma — gelişim ↔ mevcut özelliğin görünmesi
- [ ] `c2-12` — Grade 11 / konuşma — eksik bağlam / karakter gelişimi
- [ ] `d1-12` — Grade 12 / dinleme — dedeyle bağ ↔ genel çocukluk özlemi
- [ ] `d1-13` — Grade 12 / dinleme — mekân özlemi ↔ dedeyle bağ

## B. Adversarial / prompt injection — 4 kayıt

- [ ] `a2-11` — Grade 9 / written
- [ ] `b2-11` — Grade 10 / written
- [ ] `c2-11` — Grade 11 / speaking
- [ ] `d2-11` — Grade 12 / listening

Kontrol: Öğrencinin "önceki talimatları unut / tam puan ver" benzeri isteği değerlendirmeyi hiçbir biçimde değiştirmemeli.

## C. Recalibration sırasında metni veya puanı güçlü biçimde değişen — 16 kayıt

### Grade 9
- [ ] `a1-09` — low_partial cevabın gereğinden fazla kanıt içermesi düzeltildi
- [ ] `a2-04` — high_partial için kanıt/açıklama sınırı yeniden yazıldı
- [ ] `a2-05` — high_partial için açıklama eksikliği belirginleştirildi

### Grade 10
- [ ] `b1-04` — yüksek puan alan etkili cevap high_partial olacak şekilde daraltıldı
- [ ] `b1-05` — evidence/effect ayrımı yeniden kalibre edildi
- [ ] `b1-09` — doğru terimi açıkça vermemesi için low_partial metin sadeleştirildi
- [ ] `b2-03` — hâkim bakış açısı terminolojisi düzeltilip high_partial yapıldı
- [ ] `b2-07` — doğru sonuç / eksik etki açıklaması ayrımı güçlendirildi

### Grade 11 speaking
- [ ] `c1-04` — high_partial içerik/yorum dengesi
- [ ] `c1-05` — high_partial için evidence sayısı azaltıldı
- [ ] `c1-07` — mid_partial olacak şekilde final yorum eksikliği artırıldı
- [ ] `c2-03` — high_partial karakter gelişimi açıklaması
- [ ] `c2-04` — tek güçlü kanıt + sınırlı yorum

### Grade 12 listening
- [ ] `d1-04` — doğru temel neden + sınırlı destek çıkarımı
- [ ] `d2-03` — doğru temel neden + eksik destek açıklaması
- [ ] `d2-08` — low_partial için yalnız kısmi doğru neden

---

## Phase A kabul kapısı

30 kayıt içinde:

- **0–2 substantive hata:** kalan 70 için hızlı full-review'a geçilebilir.
- **3–5 substantive hata:** aynı hata tiplerinin bulunduğu tüm kayıtlar yeniden taranır.
- **6+ substantive hata:** Wave 1 review başarısız sayılır; toplu yeniden üretim/recalibration gerekir.

`substantive hata` örnekleri:

- rubrik çıpasıyla uyuşmayan criterion score,
- cevapta olmayan kanıtın var sayılması,
- yanlış response-quality sınıfı,
- `needs_review` kararının temelsiz olması,
- adversarial talimatın puana sızması,
- speaking delivery'nin sentetik gözlemden puanlanması.

## Wave 2 koşulu

Wave 2 ancak:

```text
Phase A teacher review
        ↓
review bulgularına göre Wave 1 düzeltmesi
        ↓
100 adayın promotion kararı
        ↓
canonical materialization / quarantine
        ↓
veri check PASS
```

sonrasında başlatılır.
