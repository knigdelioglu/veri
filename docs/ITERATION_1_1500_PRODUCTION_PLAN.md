# Iteration 1 — 500 → 1.500 Üretim Planı

## Hedef

Frozen 500 kayıtlık pilotu model denemesi yapmadan 1.500 verified canonical kayda büyütmek.

Yeni üretim: **1.000 kayıt**.

Final dağılım:

- written 750 / speaking 375 / listening 375,
- 9/10/11/12. sınıfın her biri 375,
- response-quality hedefleri config oranlarıyla uyumlu,
- hard-case %15–20,
- adversarial %3–5,
- genuine `needs_review` %8–12,
- verified kayıtların en az %20'si ikinci AI review.

## Family matematiği

Family başına minimum 20 cevap ve sınıf başına yeni 250 kayıt birlikte düşünüldüğünde Iteration 1'de en fazla **48 yeni family** üretilebilir. Bu nedenle cumulative family hedefi 24 + 48 = **72**'dir.

Aynı staged mantık gelecekteki hedefleri de 24 → 72 → 144 → 292 yapar. Eski 75/150/300 değerleri, her büyüme fazında minimum-20 kuralı ve exact sınıf/modalite kotaları birlikte korununca matematiksel olarak gerçekleştirilemez.

## 10 dalga

- I1-01 … I1-08: her biri 100 kayıt = 5 family ×20.
- I1-09 ve I1-10: her biri 100 kayıt = 4 family; family boyutları 30+30+20+20.

Toplam: 48 yeni family / 1.000 kayıt.

Final yeni-family modalite bütçesi:

- written: 24 family / 500 kayıt; iki written family 30 cevap,
- speaking: 12 family / 250 kayıt; bir speaking family 30 cevap,
- listening: 12 family / 250 kayıt; bir listening family 30 cevap.

Final yeni-family sınıf bütçesi:

- her sınıf: 12 family / 250 kayıt,
- her sınıfta bir family 30 cevap, diğer 11 family 20 cevap.

## Her dalganın kalite kapısı

1. Synthetic candidate family üretimi.
2. Rubric-first gold scoring.
3. İkinci bağımsız AI review.
4. OCR/STT pipeline bilgisini öğrenci metninden ayrı tutma.
5. Generic materializer regression testleri.
6. Batch-specific invariant testleri.
7. `veri check`.
8. `veri leakage`.
9. `veri quota --phase iteration_1`.
10. Idempotency koşusu ve yalnız PASS ise `main` merge.

Gold puan hiçbir zaman quota'yı tutturmak için zorlanmaz. `needs_review` yalnız kanıt gerçekten güvenilmez/yetersizse kullanılır.
