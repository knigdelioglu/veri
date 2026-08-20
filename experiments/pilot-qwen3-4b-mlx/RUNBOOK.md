# Pilot Qwen3 4B — Çalıştırma Runbook'u

Bu runbook `dataset_factory.pilot_mlx_runner` üzerinden deney adımlarını sıraya ve güvenlik kapılarına bağlar.

## Kurulum

```bash
python -m pip install -e .
python -m pip install -r experiments/pilot-qwen3-4b-mlx/requirements-mlx.txt
```

Runner `mlx-lm==0.31.3` dışında bir sürüm görürse eğitimi başlatmaz.

## 1. Train/valid paketini üret

```bash
python -m dataset_factory.pilot_mlx_runner prepare
```

Bu adım yalnız:

- `train.jsonl` = 380,
- `valid.jsonl` = 60

üretir. `test.jsonl` eğitim dizinine yazılmaz.

## 2. Fine-tune öncesi base validation

```bash
python -m dataset_factory.pilot_mlx_runner base-validation
```

Çıktılar:

```text
reports/pilot-qwen3-4b/base-validation-predictions.jsonl
reports/pilot-qwen3-4b/base-validation.json
```

Bu rapor fine-tune kazancının referansıdır.

## 3. QLoRA eğitimi

```bash
python -m dataset_factory.pilot_mlx_runner train
```

Runner:

1. Apple Silicon macOS kontrolü yapar,
2. `mlx-lm==0.31.3` kontrolü yapar,
3. frozen train/valid verisini yeniden üretir,
4. testin daha önce açılmadığını doğrular,
5. `mlx_lm.lora --config ... --mask-prompt` çağrısını çalıştırır.

Varsayılan adapter:

```text
experiments/pilot-qwen3-4b-mlx/adapters/
```

## 4. Fine-tuned validation

```bash
python -m dataset_factory.pilot_mlx_runner tuned-validation
```

Çıktılar:

```text
reports/pilot-qwen3-4b/qlora-validation-predictions.jsonl
reports/pilot-qwen3-4b/qlora-validation.json
```

Bu noktada base ↔ QLoRA farkı incelenir. Gerekirse **yalnız validation bilgisiyle** yeni deney yapılabilir; test hâlâ kapalıdır.

## 5. Konfigürasyonu kilitle

Model/checkpoint ve hyperparameter seçimleri bittikten sonra:

```bash
python -m dataset_factory.pilot_mlx_runner lock
```

Oluşur:

```text
reports/pilot-qwen3-4b/CONFIG_LOCKED.json
```

Lock aşağıdakilerin SHA-256 hashlerini içerir:

- `experiment.json`,
- `lora.yaml`,
- `adapter_config.json`,
- `adapters.safetensors`,
- base validation raporu,
- QLoRA validation raporu.

Lock sonrasında bunlardan biri değişirse final test çalışmaz.

## 6. Final test — yalnız bir kez model seçimi bittikten sonra

```bash
python -m dataset_factory.pilot_mlx_runner final-test
```

Runner önce lock hashlerini doğrular, ardından:

```text
reports/pilot-qwen3-4b/FINAL_TEST_OPENED.json
```

oluşturur ve ancak bundan sonra test splitini `--unlock-test` ile açar.

Final çıktılar:

```text
reports/pilot-qwen3-4b/final-test-predictions.jsonl
reports/pilot-qwen3-4b/final-test.json
```

`FINAL_TEST_OPENED.json` oluştuktan sonra aynı pilot test skoruna bakarak model, prompt, adapter veya hyperparameter tuning yapılmaz. Bir sonraki değişiklik 1.500 kayıt iterasyonuna taşınır.

## Özel adapter seçimi

Varsayılan adapter dışında bir checkpoint/dizin seçilecekse validation ve lock adımlarında aynı yolu açıkça ver:

```bash
python -m dataset_factory.pilot_mlx_runner tuned-validation \
  --adapter-path /tam/yol/secili-adapter

python -m dataset_factory.pilot_mlx_runner lock \
  --adapter-path /tam/yol/secili-adapter
```

Final test lock dosyasında yazılı adapter yolunu kullanır; sonradan başka adapter verilemez.
