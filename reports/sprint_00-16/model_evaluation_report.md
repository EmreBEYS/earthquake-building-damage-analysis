# Sprint 00-16 — Mevcut Modellerin Değerlendirilmesi

## Sonuç

Spatial değerlendirmede en yüksek macro-F1 dummy için 0.2397. Hiçbir model operasyonel hasar sınıflandırması için yeterli kanıt sunmuyor; azınlık sınıfları ve coğrafi genelleme zayıf.

## Model karşılaştırması

| split | model | accuracy | macro_f1 | weighted_f1 | macro_f1_ci_lower | macro_f1_ci_upper |
| --- | --- | --- | --- | --- | --- | --- |
| stratified_random | dummy | 0.9033 | 0.2373 | 0.8574 | 0.2344 | 0.2401 |
| stratified_random | logistic_regression | 0.2693 | 0.1828 | 0.3614 | 0.1574 | 0.2115 |
| stratified_random | random_forest | 0.9006 | 0.3083 | 0.8637 | 0.2575 | 0.3656 |
| spatial_1km_groups | dummy | 0.9211 | 0.2397 | 0.8833 | 0.2364 | 0.2428 |
| spatial_1km_groups | logistic_regression | 0.2762 | 0.1679 | 0.3863 | 0.1440 | 0.1947 |
| spatial_1km_groups | random_forest | 0.9142 | 0.2388 | 0.8798 | 0.2356 | 0.2418 |

## Veri sızıntısı denetimi

- Özellik sözleşmesi geçti: `True`
- Random split kimlik kesişimi: `0`
- Spatial split kimlik kesişimi: `0`
- Spatial grup kesişimi: `0`
- Model artefaktları değişmedi: `True`

## Sınıf dengesizliği ve belirsizlik

- Çoğunluk/azınlık oranı: `35.13`
- Sınıf sayısı: `4`
- Macro-F1 güven aralıkları 300 bootstrap tekrarından türetilmiştir.
- Tahmin entropisi ve düşük güven oranı tanılayıcıdır; kalibrasyon garantisi değildir.

## Yorum sınırları

- Copernicus sınıfları resmî bina güvenliği kararı değildir.
- Spatial split genelleme stres testidir; tek bir coğrafi bölme nihai kanıt değildir.
- Düşük macro-F1, çoğunluk sınıfı doğruluğunun azınlık sınıflarındaki zayıflığı gizlediğini gösterir.

