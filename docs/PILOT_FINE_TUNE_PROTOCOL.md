# Pilot Fine-Tune ve Evaluation Protokolü

Bu belge 500 kayıtlık sentetik `ai_verified` pilot veri setinin ilk fine-tune ve değerlendirme döngüsünü tanımlar. Amaç belirli bir model veya training framework seçmek değil, **veri sızıntısını önleyen ve model performansını karşılaştırılabilir kılan sabit deney sözleşmesini** tanımlamaktır.

## 1. Frozen pilot

Kaynak: `dataset/evaluation/pilot-evaluation-freeze.json`

Frozen dağılım:

| Split | Kayıt | Rol |
|---|---:|---|
| train | 380 | optimizer/fine-tune verisi |
| validation | 60 | checkpoint, prompt ve hyperparameter seçimi |
| test | 60 | seçilmiş tek konfigürasyonun final değerlendirmesi |

İstenen 80/10/10 oranı family component granülaritesi nedeniyle fiilen 76/12/12 olmuştur. Bu bilinçli bir tercihtir: aynı `task_id`, `question_family`, `exam_family` veya anonim `subject_group_id` bağlantısındaki kayıtlar farklı splitlere bölünmez.

Validation ve test ayrı ayrı:

- 20 written,
- 20 speaking,
- 20 listening

kayıt içerir. Validation/test kayıtlarının tamamı en az iki AI review geçişine sahiptir.

## 2. Test seti mühürlüdür

İlk pilot deneyinde test seti model seçmek için kullanılmaz.

Doğru sıra:

```text
train 380
   ↓
fine-tune/checkpointler
   ↓
validation 60
   ↓
tek checkpoint + tek inference ayarı seç
   ↓
test 60 (bir kez final rapor)
```

Test sonucuna bakıldıktan sonra aynı test skorunu yükseltmek amacıyla prompt, loss, hyperparameter veya veri seçimi değiştirilirse bu test artık kör final test değildir. Böyle bir durumda değişiklik yeni iterasyona taşınmalı; sonuç “aynı pilot test üzerinde bağımsız final sonuç” olarak sunulmamalıdır.

## 3. SFT girdi formatı

`veri export-sft --split all` komutu üç Chat/messages JSONL üretir:

```text
exports/sft/train.jsonl
exports/sft/validation.jsonl
exports/sft/test.jsonl
```

JSONL dosyaları `.gitignore` ile version-control dışında tutulur; canonical kayıtlar source of truth'tur. Evaluation workflow'u bunları yeniden üretir ve `pilot-sft-v1` artifact'i olarak yayınlar.

Fine-tune sırasında **yalnız `train.jsonl` optimizer'a verilir**. `validation.jsonl` validation/loss/checkpoint seçimi için kullanılabilir. `test.jsonl` eğitim veya checkpoint seçimi sürecine verilmez.

## 4. Model-agnostik prediction contract

Model çıktısı evaluator'a dönüştürülürken her satır şu minimal JSONL sözleşmesine uymalıdır:

```json
{
  "id": "tde11-speaking-000123",
  "criterion_scores": {
    "claim": 3,
    "reasoning": 0,
    "counterargument": 0,
    "organization": 1
  },
  "needs_review": false
}
```

Sözleşme: `schemas/prediction-record.schema.json`.

- `id` frozen canonical kayıt ID'sidir.
- `criterion_scores` ilgili rubriğin criterion ID'lerini **eksiksiz ve fazlasız** taşır.
- Her puan ilgili criterion aralığında olmalıdır.
- `needs_review` boolean olmak zorundadır.
- Toplam puan evaluator tarafından criterion puanlarından yeniden hesaplanır; modelin ayrı total alanına güvenilmez.

Bu katman sayesinde Gemma/Qwen/başka bir model veya farklı inference framework'leri aynı evaluation sözleşmesine dönüştürülebilir.

## 5. Evaluator

Kullanım:

```bash
python -m dataset_factory.evaluate_predictions predictions-validation.jsonl \
  --split validation \
  --output reports/validation.json
```

Final checkpoint seçildikten sonra:

```bash
python -m dataset_factory.evaluate_predictions predictions-test.jsonl \
  --split test \
  --output reports/test.json
```

Varsayılan mod strict'tir: splitteki her kayıt için tam bir prediction bulunmalıdır. Eksik, duplicate veya split dışı ID hata verir. Keşif sırasında kısmi dosya değerlendirmek için açıkça `--allow-partial` kullanılabilir; resmi validation/test raporu strict olmalıdır.

## 6. Ölçülen metrikler

### Criterion puanlama

Gold `needs_review=false` kayıtlarında:

- criterion exact agreement,
- criterion ±1 puan agreement,
- criterion MAE,
- total exact agreement,
- total MAE,
- max puana normalize total MAE

hesaplanır.

### `needs_review`

Bütün kayıtlarda:

- precision,
- recall,
- F1,
- accuracy,
- TP / FP / FN / TN

hesaplanır.

### Neden gold escalation kayıtları score MAE'ye girmez?

`needs_review=true` canonical kayıtlarında saklanan criterion puanları, mevcut eksik/bozuk girdiye göre **provisional** değerlerdir. Gold davranış “bu puan kesin” değil, “kaynak doğrulanmadan final puan verme”dir.

Bu nedenle evaluator:

```text
gold needs_review=true
    → review precision/recall hesabına dahil
    → criterion/total score agreement hesabından hariç
```

tutar.

Bu ayrım yapılmazsa doğru biçimde escalation yapan model yanlışlıkla puan hatasıyla cezalandırılır.

## 7. Slice raporları

Evaluator otomatik olarak şu kırılımları verir:

- modality,
- grade,
- response_quality,
- question_family,
- hard-case genel,
- adversarial genel,
- her `hard_case_type` ayrı.

İlk fine-tune kararları yalnız overall skorla verilmemelidir. Özellikle aşağıdaki failure mode'lar ayrı incelenmelidir:

- prompt injection'a puan kaptırma,
- keyword decoy,
- paraphrase eşdeğerini kaçırma,
- karşı görüşü savunan öğrenciyi yanlış cezalandırma,
- OCR/STT belirsizliğinde gereksiz puan verme,
- çözülebilir borderline cevabı gereksiz `needs_review` yapma,
- gerçek `needs_review` vakasında aşırı güvenli puan üretme.

## 8. Stance-neutrality kuralı

Pilot evaluation ikinci geçişinde Wave 4/5 argumentative speaking gold'larında bir hata sınıfı bulundu: bazı cevaplar yalnız beklenen görüşün tersini savundukları için düşük `claim` puanı almıştı.

Düzeltme kuralı:

> Tartışma sorusunda rubrik `claim = görüşün açıklığı/tutarlılığı` diyorsa öğrencinin hangi tarafı seçtiği claim puanını belirlemez.

Karşı görüş yanlış gerekçelendirilmiş olabilir; bu `reasoning`, `evidence` veya `counterargument` puanını düşürebilir. Fakat açık bir görüş sırf yönü nedeniyle `claim=0` alamaz.

Audit: `dataset/evaluation/pilot-evaluation-review.json`.

## 9. İlk deneyde performans eşiği koyma

Bu 500 kayıt pilotun ilk gerçek baseline'ıdır. Bu nedenle henüz keyfî bir “%90 olursa başarılı” production eşiği tanımlanmaz.

Önce:

1. base model validation baseline,
2. ilk SFT validation sonucu,
3. slice bazlı hata dağılımı

ölçülür.

Sonra Iteration 1 (1.500 kayıt) için gerçekçi acceptance gate'leri dondurulur. Veri bütünlüğü gate'leri ise şimdiden zorunludur:

- prediction coverage %100,
- JSON/criterion contract PASS,
- leakage PASS,
- validation/test dual-review %100,
- test seti training/model-selection dışında.

## 10. Error mining çıkışı

Her deney sonunda en az şu tablo üretilmelidir:

```text
failure_type
count
modality
grade
question_family
hard_case_type
gold_needs_review
predicted_needs_review
criterion_error
```

Yeni 1.000 kayıt (500 → 1.500) yalnız mevcut kota açığını doldurmak için değil, **ilk modelin gerçek hata dağılımına göre** yönlendirilmelidir.

Örneğin model paraphrase örneklerinde iyi fakat OCR negasyonunda zayıfsa Iteration 1'in hard-case bütçesi OCR/STT decision-boundary örneklerine kaydırılmalıdır.

## 11. Pilotun sınırı

Bu pilot tamamen sentetik `ai_verified` veridir. İlk fine-tune için rubric-following davranışını kalibre etmeye uygundur; gerçek öğretmen/öğrenci dağılımında nihai üretim doğruluğu iddiası için yeterli değildir.

İleride gerçek, anonimleştirilmiş ve gerçekten human-verified bir benchmark geldiğinde ayrı provenance slice olarak tutulmalı ve sentetik test setiyle karıştırılmamalıdır.
