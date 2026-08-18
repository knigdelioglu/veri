# 500 Örnek Pilot Veri Üretim Planı

Bu plan, Türk Dili ve Edebiyatı rubrik notlandırma modeli için ilk **500 teacher-verified canonical örneğin** nasıl üretileceğini tanımlar. Amaç yalnızca sayıya ulaşmak değil; ilk fine-tune sonrasında modelin hangi karar sınırlarında başarısız olduğunu güvenilir biçimde görebilecek kadar dengeli ve denetlenebilir bir pilot veri seti oluşturmaktır.

Pilot, üretim stratejisindeki genel ilkeleri uygular fakat küçük veri hacmi nedeniyle validation/test tarafında **diagnostic-stratified** yaklaşım kullanır. Gerçek sınıf dağılımını temsil eden kalıcı benchmark, pilot sonuçları görüldükten sonra `iteration_1` aşamasında ayrıca genişletilir.

---

## 1. Pilot çıkış hedefi

Pilot tamamlandığında aşağıdakiler sağlanmış olmalıdır:

- [ ] 500 canonical kayıt
- [ ] 500 kaydın tamamı `teacher_verified`
- [ ] 500 kaydın tamamı `pii_reviewed=true`
- [ ] 250 yazılı + 125 konuşma + 125 dinleme
- [ ] 9, 10, 11 ve 12. sınıfların her birinden 125 kayıt
- [ ] 24 `question_family`
- [ ] 48 exact `task_id`
- [ ] Her `question_family` içinde 20–25 cevap
- [ ] Her exact `task_id` için 10–13 cevap
- [ ] 90 distinct hard-case kayıt
- [ ] 20 adversarial kayıt
- [ ] 50 teacher-verified gold `needs_review=true` kayıt
- [ ] Tüm validation/test kayıtları çift review
- [ ] Tüm borderline ve gold `needs_review` kayıtları çift review
- [ ] `veri check` → 0 error
- [ ] Split leakage → 0
- [ ] Pilot fine-tune tamamlandıktan sonra hata taksonomisi çıkarılmış

Pilotun amacı production-ready model elde etmek değildir. Pilotun başarı ölçütü, **veri sözleşmesinin çalışması ve model hatalarının hangi örnek türlerinde yoğunlaştığının ölçülebilmesidir.**

---

## 2. Toplam 500 kaydın ana dağılımı

### Modalite

| Modalite | Kayıt |
|---|---:|
| `written` | 250 |
| `speaking` | 125 |
| `listening` | 125 |
| **Toplam** | **500** |

### Sınıf

| Sınıf | Kayıt |
|---|---:|
| 9 | 125 |
| 10 | 125 |
| 11 | 125 |
| 12 | 125 |
| **Toplam** | **500** |

Sınıf × modalite hücrelerinin birebir eşit olması zorunlu değildir. Ana kural her sınıfın toplamda 125, her modalitenin de yukarıdaki toplamda olmasıdır.

---

## 3. Cevap profili — kesin kota

| `response_quality` | Kayıt | Pay |
|---|---:|---:|
| `full_correct` | 100 | %20 |
| `high_partial` | 100 | %20 |
| `mid_partial` | 100 | %20 |
| `low_partial` | 75 | %15 |
| `incorrect` | 50 | %10 |
| `blank_irrelevant` | 25 | %5 |
| `borderline` | 50 | %10 |
| **Toplam** | **500** | **%100** |

Pilotun özellikle **275 kaydı kısmi doğru** (`high_partial + mid_partial + low_partial`) olacaktır. Bu oran bilinçlidir: modelin asıl öğrenmesi gereken şey tam doğru ile tam yanlışı ayırmak değil, rubrik içindeki kısmi puan kararlarını tutarlı vermektir.

### Modalite bazlı cevap profili

| Profil | Written 250 | Speaking 125 | Listening 125 | Toplam |
|---|---:|---:|---:|---:|
| full_correct | 50 | 25 | 25 | 100 |
| high_partial | 50 | 25 | 25 | 100 |
| mid_partial | 50 | 25 | 25 | 100 |
| low_partial | 38 | 19 | 18 | 75 |
| incorrect | 25 | 12 | 13 | 50 |
| blank_irrelevant | 12 | 6 | 7 | 25 |
| borderline | 25 | 13 | 12 | 50 |

Bu tablo pilot sonunda mümkün olduğunca birebir karşılanmalıdır.

---

## 4. Question-family ve exact-task mimarisi

Pilot veri seti birkaç soruya yığılmayacaktır.

### Hedef yapı

```text
24 question_family
        ×
2 exact task varyantı
        =
48 exact task_id
```

Aile boyutları:

- Written: **12 question family**
  - 10 aile × 20 cevap
  - 2 aile × 25 cevap
  - toplam 250
- Speaking: **6 question family**
  - 5 aile × 20 cevap
  - 1 aile × 25 cevap
  - toplam 125
- Listening: **6 question family**
  - 5 aile × 20 cevap
  - 1 aile × 25 cevap
  - toplam 125

Exact task dağılımı:

- 20 cevaplık family → `task-A: 10` + `task-B: 10`
- 25 cevaplık family → `task-A: 12` + `task-B: 13`

Böylece her exact task 8–20 aralığında, her question family 20–40 aralığında kalır.

### Kural

Aynı family içindeki iki exact task:

- aynı temel beceriyi ölçmeli,
- aynı veya eşdeğer rubrik mantığını kullanmalı,
- yüzeysel kelime değişimi olmaktan fazlasını içermeli,
- fakat farklı bir beceriye dönüşmemelidir.

Örneğin aynı family içinde iki farklı şiir parçası üzerinde `ana duygu + metinsel kanıt` sorusu kullanılabilir.

---

## 5. 24 question-family'nin beceri dağılımı

### Written — 12 family

1. Doğrudan bilgi + kısa açıklama
2. Kavramı örnek üzerinden açıklama
3. Metinde ana düşünce/tema belirleme
4. Metinden kanıt gösterme
5. Çıkarım yapma ve gerekçelendirme
6. İki metni/unsuru karşılaştırma
7. Şiir inceleme — anlam/duygu
8. Şiir inceleme — yapı/söz sanatı/işlev
9. Anlatıcı/bakış açısı/kurgu çözümleme
10. Edebî dönem/akım özelliğini metne uygulama
11. Dil-anlatım/üslup değerlendirmesi
12. Çok ölçütlü karma yorum sorusu

### Speaking — 6 family

1. Edebî eser/karakter tanıtma
2. Metin veya tema hakkında yapılandırılmış yorum
3. Karşılaştırmalı sözlü açıklama
4. Görüş savunma + gerekçe + örnek
5. Hazırlıklı kısa konuşma düzeni
6. İçerik + düzen + uygun kanıt varsa akıcılık gözlemi içeren karma rubrik

Konuşma family'lerinde telaffuz, vurgu, gerçek akıcılık vb. yalnız `teacher_observation` / uygun ses kanıtı varsa değerlendirilir.

### Listening — 6 family

1. Ana düşünce/temel mesaj
2. Açık bilgi/detail retrieval
3. Neden-sonuç ilişkisi
4. Çıkarım
5. Konuşmacı/anlatıcı tutumu veya amacı
6. Dinlenen içeriği kısa yapılandırılmış biçimde özetleme

---

## 6. Rubrik çeşitliliği

24 family aynı rubrik şablonunu kullanmamalıdır.

Hedef criterion-count dağılımı:

| Rubrik ölçüt sayısı | Family |
|---|---:|
| 2 kriter | 10 |
| 3 kriter | 8 |
| 4 kriter | 4 |
| 5 kriter | 2 |
| **Toplam** | **24** |

Rubriklerde şu puan çıpası biçimleri karışık kullanılmalıdır:

- `0/1`
- `0/1/2`
- `0/2/4`
- `0/1/2/3`
- `0/1/2/3/4`
- farklı kriterlerin farklı maksimum puan taşıdığı karma yapılar

Aynı question family içindeki iki exact task, mümkün olduğunca **aynı rubric_id/version mantığını** kullanmalıdır. Pilot sırasında soru ve rubriği aynı anda değiştirip iki değişkeni birbirine karıştırmamak tercih edilir.

---

## 7. Gerçek ve sentetik veri karışımı

Pilot hedefi:

| Kaynak | Kayıt | Pay |
|---|---:|---:|
| `real_anonymized` | 300 | %60 |
| `synthetic` | 200 | %40 |

Modalite bazında önerilen hedef:

| Modalite | Gerçek | Sentetik |
|---|---:|---:|
| Written | 150 | 100 |
| Speaking | 75 | 50 |
| Listening | 75 | 50 |
| **Toplam** | **300** | **200** |

Sentetik örneklerin ana kullanım amacı normal cevap üretmek değil, gerçek veride seyrek görülen karar sınırlarını tamamlamaktır:

- borderline,
- adversarial,
- kısa ama doğru,
- uzun ama ilgisiz,
- anahtar kelime tuzağı,
- çelişkili cevap,
- missing evidence,
- rubrik ambiguity.

Sentetik öğrenci cevabının gold puanı yine öğretmen tarafından doğrulanmadan `teacher_verified` yapılamaz.

---

## 8. Hard-case kotası — 90 distinct kayıt

Pilotun **90 kaydı (%18)** deliberate hard-case olacaktır.

Bir kayıt birden fazla etiket taşıyabilir; ancak aşağıdaki sayıların her biri öncelikli/primary örnek sayısı olarak planlanır:

| Hard-case | Primary kayıt |
|---|---:|
| `short_correct` | 10 |
| `long_irrelevant` | 8 |
| `keyword_decoy` | 8 |
| `paraphrase_equivalent` | 10 |
| `contradictory_answer` | 8 |
| `mixed_criterion_performance` | 12 |
| `correct_result_wrong_reason` | 5 |
| `wrong_result_valid_method` | 5 |
| `rubric_extra_info` | 4 |
| `prompt_injection` | 10 |
| `ocr_ambiguity` | 3 |
| `stt_ambiguity` | 3 |
| `missing_evidence` | 2 |
| `rubric_ambiguity` | 2 |
| **Toplam** | **90** |

Hard-case dağılımı yaklaşık:

- Written: 50
- Speaking: 20
- Listening: 20

olmalıdır.

---

## 9. Adversarial kota — 20 kayıt

Pilotun **20 kaydı (%4)** `adversarial=true` olacaktır.

Önerilen dağılım:

- 10 `prompt_injection`
- 5 puan/rubrik anahtar kelimelerini manipülatif biçimde taklit eden `keyword_decoy`
- 5 rubriği kandırmaya yönelik `rubric_extra_info` / benzeri grading-gaming örneği

Modalite:

- Written: 10
- Speaking: 5
- Listening: 5

Adversarial örnekler gerçek öğrenci davranışını temsil etmek zorunda değildir; güvenlik ve kestirme davranış testi için deliberate üretilebilir.

---

## 10. Gold `needs_review` — 50 kayıt

Tam **50 kayıt (%10)**, öğretmenler tarafından doğrulanmış biçimde:

```text
status = teacher_verified
needs_review = true
review_count >= 2
```

olmalıdır.

Bunlar çözülmemiş annotation değildir. Modelin gerçekten insan incelemesine yönlendirmesi gereken örneklerdir.

Kaynak nedenler dengelenmelidir:

- puan çıpası sınırı,
- eksik/okunamayan kritik kanıt,
- OCR belirsizliği,
- STT belirsizliği,
- rubrik ambiguity,
- gerekli metin dışı konuşma kanıtının eksikliği,
- iki makul değerlendirmenin mümkün olması.

`needs_review=true` örneklerin tamamı `borderline` olmak zorunda değildir. Modelin `borderline == review` gibi basit bir kestirme öğrenmesini önlemek için en az **20 needs_review kaydı farklı response_quality sınıflarında** bulunmalıdır.

---

## 11. İnsan review planı

Pilot küçük olduğu için insan denetimini V1'den daha yoğun tutmak uygundur.

### Zorunlu çift review

- validation kayıtlarının %100'ü
- test kayıtlarının %100'ü
- tüm `borderline`
- tüm gold `needs_review=true`

Bu kümeler örtüşeceğinden unique çift-review sayısı değişebilir; pilot hedefi **en az 175 distinct kayıt** için `review_count >= 2` olmasıdır.

Uyuşmazlık varsa:

```text
review_count >= 2
adjudicated = true
```

ve nihai gold değerlendirme ortak karar sonrası kaydedilir.

### İkinci öğretmen yoksa

Aynı öğretmenin farklı zamanda, ilk puanını görmeden yaptığı kör ikinci değerlendirme ayrı kalite kontrolü olarak kullanılabilir. Bunun aynı anda yapılan sıradan tekrar kontrolünden ayrılması gerekir.

---

## 12. Pilot split planı

Pilot split'i küçük veri setinde her değerlendirme setinin üç modaliteyi de içermesi için varsayılan 80/10/10'dan biraz farklı tutulur:

| Split | Kayıt | Pay |
|---|---:|---:|
| train | 380 | %76 |
| validation | 60 | %12 |
| test | 60 | %12 |
| **Toplam** | **500** | **%100** |

### Evaluation family'leri önceden dondur

Validation için:

- 1 written family × 20
- 1 speaking family × 20
- 1 listening family × 20

Test için:

- 1 written family × 20
- 1 speaking family × 20
- 1 listening family × 20

Bu 6 family üretim başlamadan `validation/test` için ayrılır ve hiçbir:

```text
task_id
subject_group_id
exam_family
question_family
```

train ile paylaşılmaz.

Kalan 18 family train'e gider.

Pilot split komutu:

```bash
veri split --train 0.76 --validation 0.12 --seed tde-pilot-v1
```

Ancak validation/test için seçilen family'lerin metadata.split değerleri **önceden sabitlenmeli**; splitter mevcut atamaları koruyacaktır. Seed yalnız geri kalan train adayları için deterministik davranış sağlar.

### Neden 60/60?

50 kayıtlık validation/test, family başına minimum 20 kuralı altında her split'e üç modaliteyi birden koymayı zorlaştırır. 60 kayıt = üç adet 20'lik family ile her değerlendirme split'inde yazılı, konuşma ve dinleme bulunmasını sağlar.

---

## 13. Subject/exam leakage üretim kuralı

Gerçek öğrenciler birden fazla soruya cevap veriyorsa aynı `subject_group_id` kullanılmalıdır; split kolaylığı için kimlik değiştirilmemelidir.

Bunun sonucu olarak aynı öğrencinin cevapları birbirine bağlanabilir. Bu yüzden pilot veri baştan **bağımsız öğrenci/oturum blokları** şeklinde toplanmalıdır.

Kurallar:

- validation öğrencisi train'de bulunmaz,
- test öğrencisi train/validation'da bulunmaz,
- aynı gerçek sınav formu farklı split'lere dağıtılmaz,
- `exam_family` yalnız gerçekten aynı sınav/form ise paylaşılır,
- sentetik kayıtlarda sahte öğrenci kimliği üretmek gerekmez; `subject_group_id=null` olabilir.

Split'i kolaylaştırmak için semantik olarak yanlış metadata yazmak yasaktır.

---

## 14. Beş üretim dalgası

Her dalga **100 kayıt** üretir.

Her 100 kayıtlık dalganın temel kotası:

### Modalite

```text
50 written
25 speaking
25 listening
```

### Sınıf

```text
25 grade 9
25 grade 10
25 grade 11
25 grade 12
```

### Response quality

```text
20 full_correct
20 high_partial
20 mid_partial
15 low_partial
10 incorrect
 5 blank_irrelevant
10 borderline
```

Bu sayede 5 dalga sonunda toplam hedef matematiksel olarak otomatik kapanır.

### Dalga 1 — Kalibrasyon / normal örnek tabanı

Hedef:

- veri giriş akışını denemek,
- rubriklerin yeterince açık olup olmadığını görmek,
- normal doğru/kısmi/yanlış cevap varyasyonlarını oluşturmak.

Özel kota:

- hard case: 10
- adversarial: 0
- gold needs_review: 5

Dalga sonunda:

```bash
veri check
veri quota --phase pilot
```

çalıştırılır. Şema veya annotation kuralı sorunu varsa Dalga 2'ye geçmeden düzeltilir.

### Dalga 2 — Kısmi puan sınırları

Odak:

- high ↔ mid partial,
- mid ↔ low partial,
- bir kriter doğru diğer kriter yanlış,
- sonuç doğru fakat gerekçe eksik/yanlış,
- farklı doğru ifade biçimleri.

Özel kota:

- hard case: 20
- adversarial: 0
- gold needs_review: 15

### Dalga 3 — Hard-case + adversarial

Odak:

- keyword decoy,
- long irrelevant,
- short correct,
- prompt injection,
- contradictory answer,
- rubric gaming.

Özel kota:

- hard case: 30
- adversarial: 10
- gold needs_review: 10

### Dalga 4 — Modaliteye özgü hata alanları

Written:

- OCR ambiguity,
- kanıt eksikliği,
- kısa/uzun cevap yanlılığı.

Speaking:

- STT ambiguity,
- transkript ile puanlanamayacak akıcılık/telaffuz ölçütleri,
- teacher observation kullanımı.

Listening:

- explicit detail ↔ inference,
- ana düşünce ↔ yüzeysel anahtar kelime,
- eksik bağlam.

Özel kota:

- hard case: 20
- adversarial: 5
- gold needs_review: 10

### Dalga 5 — Kota kapatma / kör nokta tamamlama

Dalga 5 sabit içerik listesinden değil, ilk 400 kaydın gerçek açığından üretilir.

Önce:

```bash
veri quota --phase pilot
veri next-batch --phase pilot --count 100
```

çalıştırılır.

Son 100 kayıtta öncelik:

1. Eksik modality
2. Eksik sınıf
3. Eksik response_quality
4. Eksik hard-case türleri
5. Eksik adversarial
6. Eksik needs_review
7. 20 cevaba ulaşmamış question family
8. 8 cevaba ulaşmamış exact task
9. Yetersiz rubrik criterion-count çeşitliliği

Başlangıç hedefi:

- hard case: 10
- adversarial: 5
- gold needs_review: 10

ancak quota raporu gerektirirse bu sayılar yukarı ayarlanabilir.

---

## 15. Her 100 kayıtta kalite kapısı

Bir dalga bitmeden sonraki dalgaya geçilmez.

Kontrol sırası:

```bash
veri check
veri quota --phase pilot
```

Manuel kontrol:

- [ ] `teacher_verified` örneklerde gold gerçekten öğretmen tarafından doğrulanmış mı?
- [ ] response_quality gerçek puan seviyesine uyuyor mu?
- [ ] hard_case etiketi örnekte gerçekten var mı?
- [ ] synthetic cevaplar aşırı steril/LLM-benzeri mi?
- [ ] kısa doğru cevaplar gereksiz düşük puanlanmış mı?
- [ ] uzun cevaplar yalnız uzun oldukları için yüksek puan almış mı?
- [ ] speaking ölçütü olmayan ses özelliği transkriptten uydurulmuş mu?
- [ ] evidence literal olarak cevaptan/gözlemden destekleniyor mu?
- [ ] student identity / okul bilgisi sızmış mı?

Error varsa düzeltilmeden sonraki üretim dalgasına geçilmez.

---

## 16. Pilot fine-tune öncesi son gate

Aşağıdaki sıralama uygulanır:

```bash
veri check
veri quota --phase pilot
veri split --train 0.76 --validation 0.12 --seed tde-pilot-v1
veri check
veri export-sft
```

Ardından export sayıları doğrulanır.

Beklenti yaklaşık:

```text
train       380
validation   60
test         60
```

Group-aware component yapısı nedeniyle sayılar beklenmedik biçimde sapıyorsa split zorla yapılmaz; hangi `task_id / subject_group_id / exam_family / question_family` bağlantısının büyük bileşen oluşturduğu incelenir.

---

## 17. Pilot model değerlendirmesi

İlk fine-tune sonrasında yalnız toplam puana bakılmaz.

Minimum rapor:

### Genel

- total-score MAE
- normalize edilmiş puan sapması
- over-score / under-score bias

### Criterion

- criterion-level MAE
- exact criterion agreement
- kısmi puan sınırı hata matrisi

### Review

- `needs_review` precision
- `needs_review` recall
- false confident grading sayısı

### Slice

Performans ayrı ayrı:

- written / speaking / listening
- grade 9 / 10 / 11 / 12
- 7 response_quality sınıfı
- normal / hard-case
- adversarial / non-adversarial

### Hard-case özel

Özellikle ölçülür:

- short_correct under-scoring
- long_irrelevant over-scoring
- keyword_decoy etkisi
- paraphrase rejection
- contradiction handling
- prompt-injection override rate
- OCR/STT ambiguity handling

---

## 18. Error-mining çıktısı

Pilot fine-tune bittikten sonra ikinci aşamaya geçmeden önce en az şu rapor üretilir:

```text
TOP 10 hata kümesi
│
├── hata tipi
├── modality
├── grade
├── response_quality
├── question_family
├── rubric criterion
├── modelin tipik hatası
└── iteration_1 için üretilecek yeni örnek sayısı
```

Örneğin:

```text
1. short_correct → sistematik düşük puan → +80 örnek
2. mid_partial ↔ high_partial karışıyor → +150 örnek
3. prompt injection model skorunu yükseltiyor → +50 örnek
4. speaking missing evidence durumunda puan uyduruyor → +70 örnek
```

`iteration_1 = 1.500` veri hedefinin kalan 1.000 örneği bu rapor tarafından yönlendirilmelidir.

---

## 19. Pilot için kabul edilmeyecek kestirmeler

- Aynı soru metnini küçük kelime değişiklikleriyle onlarca `task_id` yapmak.
- Bir question family'yi 40'ın çok üstüne taşımak.
- Tam doğru sentetik cevaplarla sayıyı hızlı doldurmak.
- Model çıktısını öğretmen kontrolü olmadan gold kabul etmek.
- `response_quality` etiketini toplam puandan otomatik türetip kör biçimde kabul etmek.
- Validation/test öğrenci veya soru ailesini train'e sızdırmak.
- Konuşma akıcılığı/telaffuzu yalnız transkriptten uydurmak.
- Test sonucunu gördükten sonra test gold etiketlerini modele göre değiştirmek.

---

## 20. Operasyon özeti

```text
24 question family
        ↓
48 exact task
        ↓
5 × 100 kayıtlık dalga
        ↓
500 teacher-verified canonical kayıt
        ↓
380 train / 60 validation / 60 test
        ↓
Pilot fine-tune
        ↓
Slice + hard-case + needs_review analizi
        ↓
Error mining
        ↓
1.500 örneklik iteration_1
```

Pilotun temel ilkesi şudur:

> Son 100 kayıt, ilk 400 kaydın kotasını tamamlamak için; sonraki 1.000 kayıt ise ilk modelin gerçek hatalarını kapatmak için üretilir.
