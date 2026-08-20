# Pilot 01 — Qwen3 4B / MLX QLoRA

Bu klasör 500 kayıtlık frozen pilotun **ilk gerçek fine-tune baseline** deneyidir.

Amaç en güçlü modeli hemen seçmek değil; 16 GB Apple Silicon üzerinde düşük riskli bir modelle bütün zinciri ölçmektir:

```text
base model validation
        ↓
QLoRA / train 380
        ↓
validation 60
        ↓
checkpoint + inference ayarı kilitle
        ↓
sealed test 60
        ↓
error mining → 1.500 kayıt fazı
```

## Neden Qwen3 4B 4-bit?

İlk baseline için `mlx-community/Qwen3-4B-4bit` kullanılır.

- MLX-LM Apple Silicon üzerinde LoRA/QLoRA destekler.
- Quantized model üzerinde eğitim QLoRA olarak çalışır.
- 4B / 4-bit profil, 16 GB bellekte 12B sınıfına göre daha güvenli ilk deney marjı verir.
- Pilot yalnız 380 training kaydıdır; ilk amaç kapasite yarışından önce rubric-following ve evaluation zincirini ölçmektir.

Gemma 4 12B ilk baseline değildir. 4B deneyinin hız/bellek/kalite profili ölçüldükten sonra daha büyük karşılaştırma adayı olarak tutulur.

## 1. Kurulum

Repo kökünde:

```bash
python -m pip install -e .
python -m pip install "mlx-lm[train]"
```

## 2. MLX train/valid verisini hazırla

```bash
python -m dataset_factory.prepare_mlx_pilot
```

Oluşan dizin:

```text
experiments/pilot-qwen3-4b-mlx/data/
├── train.jsonl   # 380
├── valid.jsonl   # 60
└── manifest.json
```

**`test.jsonl` oluşturulmaz.** Hazırlayıcı aynı dizinde eski bir `test.jsonl` bulursa siler. Böylece sealed-test protokolü yalnız dokümana değil dosya sistemine de uygulanır.

MLX-LM `chat/messages` JSONL formatını doğrudan desteklediği için başka prompt dönüşümü yapılmaz. Eğitim dosyalarına `id`, provenance veya üretim metadata'sı taşınmaz; yalnız `messages` kalır.

## 3. Önce base model validation baseline

Fine-tune öncesinde aynı 60 validation kaydını ölç:

```bash
python -m dataset_factory.mlx_predict \
  --split validation \
  --model mlx-community/Qwen3-4B-4bit \
  --output reports/pilot-qwen3-4b/base-validation-predictions.jsonl

veri evaluate reports/pilot-qwen3-4b/base-validation-predictions.jsonl \
  --split validation \
  --output reports/pilot-qwen3-4b/base-validation.json
```

Bu sonuç ilk gerçek referanstır. Fine-tune kazancı bununla karşılaştırılır.

## 4. QLoRA eğitimi

```bash
mlx_lm.lora \
  --config experiments/pilot-qwen3-4b-mlx/lora.yaml \
  --mask-prompt
```

Quantized model kullanıldığı için bu LoRA koşusu QLoRA olarak çalışır. `--mask-prompt`, loss'u sistem/user promptuna değil final assistant cevabına odaklar.

Başlangıç profili:

| Ayar | Değer |
|---|---:|
| model | Qwen3 4B 4-bit |
| train | 380 |
| valid | 60 |
| batch | 1 |
| grad accumulation | 4 |
| LoRA layer | son 8 |
| rank | 8 |
| learning rate | 1e-5 |
| iterations | 160 |
| max sequence | 2048 |
| gradient checkpointing | açık |

Bu değerler production optimumu değildir; 16 GB bellek için muhafazakâr **baseline recipe**'dir. İlk koşudaki loss, peak memory ve validation metriğine göre sonraki deneyde değiştirilir.

## 5. Fine-tuned validation

Adapter üretildikten sonra:

```bash
python -m dataset_factory.mlx_predict \
  --split validation \
  --model mlx-community/Qwen3-4B-4bit \
  --adapter-path experiments/pilot-qwen3-4b-mlx/adapters \
  --output reports/pilot-qwen3-4b/qlora-validation-predictions.jsonl

veri evaluate reports/pilot-qwen3-4b/qlora-validation-predictions.jsonl \
  --split validation \
  --output reports/pilot-qwen3-4b/qlora-validation.json
```

Karar yalnız overall loss ile verilmez. Özellikle:

- criterion exact agreement,
- criterion MAE,
- normalized total MAE,
- `needs_review` F1,
- written/speaking/listening slice,
- hard-case,
- adversarial

karşılaştırılır.

## 6. Final test kapısı

Test spliti model veya hyperparameter seçimi için kullanılmaz.

Model/checkpoint ve generation ayarı validation üzerinde kilitlendikten **sonra yalnız bir final koşu**:

```bash
python -m dataset_factory.mlx_predict \
  --split test \
  --unlock-test \
  --model mlx-community/Qwen3-4B-4bit \
  --adapter-path experiments/pilot-qwen3-4b-mlx/adapters \
  --output reports/pilot-qwen3-4b/final-test-predictions.jsonl

veri evaluate reports/pilot-qwen3-4b/final-test-predictions.jsonl \
  --split test \
  --output reports/pilot-qwen3-4b/final-test.json
```

Test sonucu görüldükten sonra aynı test skorunu iyileştirmek için tuning yapılırsa yeni sonuç bağımsız final test sayılamaz.

## 7. Parse hataları

`mlx_predict` model cevabını canonical `gold_evaluation` JSON biçiminden prediction contract'a dönüştürür. Model JSON üretemezse:

```text
<output>.errors.jsonl
```

oluşur ve komut başarısız exit code ile biter. Resmî validation/test değerlendirmesinde parse hataları gizlenmez veya elle tamamlanmaz.

## 8. İlk deney çıktısı

Deney sonunda tutulacak minimum dosyalar:

```text
reports/pilot-qwen3-4b/
├── base-validation-predictions.jsonl
├── base-validation.json
├── qlora-validation-predictions.jsonl
├── qlora-validation.json
├── final-test-predictions.jsonl   # yalnız final gate sonrası
└── final-test.json                # yalnız final gate sonrası
```

Bu raporlar 500 → 1.500 veri üretiminin error-mining girdisidir.
