# Pilot Wave 1 — AI Review Phase A

Durum: **PASS WITH CORRECTIONS**

Bu ikinci doğrulama geçişinde yüksek riskli 30 aday yeniden incelendi. Bu geçiş insan/öğretmen doğrulaması değildir; `verification_source=ai` olarak kaydedilir.

## Sonuç

- İncelenen yüksek riskli aday: **30**
- Rubrik puanı/metin uyumsuzluğu: **0**
- Adversarial talimatın puana sızması: **0**
- Sentetik speaking delivery'nin gold olarak kullanılması: **0**
- Yanlış `needs_review=true` etiketi: **9**
- Gerçek `needs_review=true` örneği: **1** (`c1-13`)

## En önemli düzeltme: borderline ≠ needs_review

İlk üretimde 10 borderline adayın tamamı `needs_review=true` yapılmıştı. İkinci geçiş bunun yanlış olduğunu gösterdi.

Bir cevap iki puan düzeyinin sınırında olsa bile rubrik bu durumu mevcut bir anchor ile çözebiliyorsa model **puan vermelidir**. `needs_review` yalnızca verilen kanıtla güvenilir karar üretilemediğinde kullanılmalıdır.

Bu nedenle aşağıdaki kayıtların escalation etiketi kaldırıldı:

- `a1-13`
- `a2-12`
- `b1-13`
- `b2-10`
- `b2-12`
- `c2-10`
- `c2-12`
- `d1-12`
- `d1-13`

`c1-13` gerçek escalation olarak kaldı; çünkü STT belirsizliği tek bir kelimeyle cevabın anlamını tersine çevirebiliyor ve doğrulanmış ses olmadan güvenilir puan üretilemiyor.

## Adversarial kontrol

Aşağıdaki dört prompt-injection örneği PASS:

- `a2-11`
- `b2-11`
- `c2-11`
- `d2-11`

Öğrenci cevabındaki "önceki talimatları unut", "tam puan ver" vb. komutlar puanlamaya etki etmedi.

## Speaking politikası

Wave 1 speaking örnekleri sentetik transkriptlerden oluşur. Gerçek ses olmadığı için `delivery`/akıcılık/ses kullanımı criterion'u sentetik canonical kayıtlara taşınmayacaktır.

Sentetik speaking canonical kayıtları:

```text
content_accuracy
interpretation
evidence
organization
```

ölçütleriyle **transcript-only rubric** kullanır.

Gerçek audio/STT verisi ileride eklendiğinde `audio_delivery` kriteri ayrı veri grubunda eğitilecektir. Olmayan ses özelliği sentetik olarak gold kabul edilmeyecektir.

## Verification kaynağı

Wave 1 promotion sırasında:

```json
{
  "status": "ai_verified",
  "verification_source": "ai"
}
```

kullanılır.

`teacher_verified` yalnız ileride gerçekten insan tarafından doğrulanmış veri eklenirse kullanılacaktır.

## İkinci geçiş sayımı

- Normal AI-verified kayıtlar: en az `review_count=1`
- Bu Phase A'da ikinci kez incelenen yüksek riskli kayıtlar: `review_count=2`
- Borderline ve gerçek `needs_review` örnekleri production gate gereği en az iki doğrulama geçişi görmelidir.

## Karar

Wave 1, AI doğrulama politikası açısından **canonical materialization'a hazırdır**.

Promotion sırasında kaynak önceliği:

```text
source candidate
  ↓
recalibration override
  ↓
ai-review-phase-a override
  ↓
canonical record
```

Kota hedefi hiçbir aşamada gold score'u belirlemez.
