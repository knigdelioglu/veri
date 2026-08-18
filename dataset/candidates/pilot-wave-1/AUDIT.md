# Pilot Wave 1 — Üretim Kalite Denetimi

Durum: **AI-VERIFIED — READY FOR CANONICAL MATERIALIZATION**

İlk 100 sentetik aday üretildikten sonra iki ayrı AI kalite geçişi yapıldı. İnsan/öğretmen doğrulaması kullanılmıyor. Bu nedenle canonical promotion sırasında `teacher_verified` değil, açık provenance taşıyan `ai_verified` statüsü kullanılacaktır.

## Üretim kontrolleri

- 100 aday üretildi.
- Modalite: 50 written / 25 speaking / 25 listening.
- Sınıf: 9–12 her biri 25.
- `response_quality`: 20 full_correct / 20 high_partial / 20 mid_partial / 15 low_partial / 10 incorrect / 5 blank_irrelevant / 10 borderline.
- 18 hard-case adayı.
- 4 adversarial/prompt-injection adayı.
- 4 question family, 8 exact task; family başına 25, task başına 12–13 cevap.
- 98 dolu öğrenci cevabında birebir tekrar yok.

## Birinci AI kalite geçişi — recalibration

Rubrik çıpaları tekrar esas alınarak bütün family'ler yeniden tarandı.

- **62 adayda** puan/değerlendirme override'ı oluşturuldu.
- **27 adayın metni**, hedef profile gerçekten uyması için yeniden yazıldı.
- Puan hiçbir adayda kota uğruna düşürülmedi veya yükseltilmedi.
- Grade 9'da metinsel kanıt çıpaları düzeltildi.
- Grade 10'da viewpoint/evidence/effect ayrımı yeniden kalibre edildi.
- Grade 11 speaking adaylarında sentetik delivery gözlemleri gold olmaktan çıkarıldı.
- Grade 12 dinlemede temel nedeni açıkça söyleyen cevapların comprehension puanları rubriğe göre düzeltildi.

## İkinci AI kalite geçişi — yüksek riskli örnekler

30 yüksek riskli aday yeniden incelendi:

- 10 başlangıç `needs_review` adayı,
- 4 adversarial/prompt-injection adayı,
- 16 güçlü metin/puan değişikliği alan aday.

Sonuç:

- Rubrik puanı/metin uyumsuzluğu: **0**
- Prompt injection etkisi: **0**
- Sentetik delivery'nin gold olarak kullanılması: **0**
- Yanlış `needs_review=true`: **9**
- Gerçek `needs_review=true`: **1**

## Kritik öğrenim: borderline ≠ needs_review

İlk üretimde 10 borderline adayın tamamına `needs_review=true` verilmişti. Bu ikinci denetimde yanlış bulundu.

Rubrik bir belirsizliği mevcut anchor ile çözebiliyorsa modelin görevi puan vermektir. `needs_review` yalnızca mevcut kanıt güvenilir bir puan üretmeye yetmediğinde kullanılmalıdır.

Bu nedenle 9 escalation kaldırıldı. Yalnız `c1-13` kaldı; STT belirsizliği tek bir kelimeyle anlamı tersine çevirebildiğinden doğrulanmış ses olmadan güvenilir puan üretilemez.

## Konuşma için sentetik veri politikası

Sentetik speaking örneklerinde gerçek ses yoktur. Bu nedenle canonical promotion sırasında `delivery` criterion'u çıkarılır. Sentetik speaking rubric yalnız:

```text
content_accuracy
interpretation
evidence
organization
```

ölçütlerini kullanır.

Gerçek audio/STT örnekleri ileride ayrı veri grubunda `audio_delivery` kriteriyle üretilebilir. Olmayan ses niteliği hiçbir zaman sentetik gold olarak uydurulmaz.

## Verification provenance

Sentetik pilot kayıtları:

```json
{
  "status": "ai_verified",
  "verification_source": "ai"
}
```

olarak canonical'a girer.

`teacher_verified` statüsü yalnız ileride gerçekten insan tarafından doğrulanmış kayıtlar eklenirse kullanılır.

## Override önceliği

Canonical materialization sırasında:

```text
source candidate
  ↓
recalibration/<family>.json
  ↓
recalibration/ai-review-phase-a-overrides.json
  ↓
canonical record
```

uygulanır.

## Değişmeyen temel ilke

**Gold puan, kota hedefinden türetilmez.**

1. Önce cevap rubriğe göre puanlanır.
2. Cevap hedef kalite sınıfına uymuyorsa gold puan zorlanmaz.
3. Bunun yerine öğrenci cevabı yeniden yazılır veya yeni cevap üretilir.
4. Rewritten cevap tekrar rubriğe göre puanlanır.
5. `needs_review` oranı hedefin altında kalırsa sahte escalation üretilmez; sonraki dalgada gerçekten kanıt yetersizliği yaratan örnekler tasarlanır.

## Sıradaki adım

Wave 1'in 100 kaydı canonical `dataset/records` içine `ai_verified` olarak materialize edilecek; ardından:

```text
veri check
veri split
veri check
veri export-sft
```

kalite zinciri çalıştırılacaktır. Bu zincir PASS olmadan Wave 2 başlamaz.
