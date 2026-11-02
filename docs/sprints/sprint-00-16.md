# Sprint 00-16 — Mevcut Modellerin Değerlendirilmesi

## Amaç

Bu sprint, Sprint 00-10'da eğitilen `dummy`, `logistic_regression` ve `random_forest` model
artefaktlarını değiştirmeden yeniden değerlendirir. Değerlendirme, kayıtlı modellerin SHA-256 ve
dosya değiştirilme zamanlarını işlem öncesi/sonrası karşılaştırır. Spatial split için modellerin
yalnız bellekte oluşturulan klonları eğitilir; `models/` altındaki dosyalara yazılmaz.

## Değerlendirme düzeni

- Orijinal `%80/%20` stratified random holdout aynı seed ile yeniden oluşturulur.
- Sprint 00-14 geometrileriyle eşleşen 3.617 kayıt, 1 km UTM grid gruplarıyla spatial holdout'a
  ayrılır.
- Eğitim ve test bina kimlikleri ile spatial gruplarının kesişimi sıfır olmalıdır.
- Accuracy, macro-F1, weighted-F1 ve 300 tekrarlı bootstrap macro-F1 aralığı raporlanır.
- Olasılık üreten modeller için normalize entropi, medyan en yüksek olasılık, `%60` altı güven
  oranı ve multiclass log-loss hesaplanır.

## Ana sonuçlar

| Split | Model | Accuracy | Macro-F1 | Weighted-F1 |
| --- | --- | ---: | ---: | ---: |
| Stratified random | Dummy | 0.9033 | 0.2373 | 0.8574 |
| Stratified random | Logistic Regression | 0.2693 | 0.1828 | 0.3614 |
| Stratified random | Random Forest | 0.9006 | 0.3083 | 0.8637 |
| Spatial 1 km | Dummy | 0.9211 | 0.2397 | 0.8833 |
| Spatial 1 km | Logistic Regression | 0.2762 | 0.1679 | 0.3863 |
| Spatial 1 km | Random Forest | 0.9142 | 0.2388 | 0.8798 |

Spatial sonuçlarda yüksek accuracy, test kümesindeki 537 `no_visible_damage` kaydının baskınlığıyla
oluşur. Dört sınıfın toplam dağılımında çoğunluk/azınlık oranı 35,13:1'dir. Bu nedenle karar metriği
olarak macro-F1 öne çıkar; hiçbir model operasyonel hasar sınıflandırması için yeterli değildir.

## Veri sızıntısı ve belirsizlik

- Özellik kümesi yalnız alan, çevre ve şekil indeksidir; hedef, kimlik ve kaynak alanları yoktur.
- Random ve spatial holdout'larda bina kimliği kesişimi sıfırdır.
- Spatial eğitim/test grup kesişimi sıfırdır.
- Spatial split'te aynı üç geometrik değere sahip bir özellik vektörü iki tarafta bulunur; bu açıkça
  raporlanır ve kimlik/grup sızıntısı değildir, ancak geometrik tekrar hassasiyetidir.
- Lojistik regresyon spatial tahminlerinin yaklaşık `%89,4`'ü `0,60` güvenin altındadır.
- Dummy model kesin çoğunluk tahmini yaparak aşırı güvenli görünür fakat log-loss'u yüksektir; bu,
  confidence değerinin tek başına model kalitesi olmadığını gösterir.

## Çıktılar ve tekrar üretim

- `model_evaluation_report.json`: makine-okunur tam kanıt.
- `model_evaluation_report.md`: insan-okunur teslim raporu.
- `model_comparison.csv`: altı split/model satırı.
- `uncertainty_summary.csv`: olasılık belirsizliği ölçümleri.
- `class_distribution.csv`: sınıf sayıları ve payları.

```powershell
uv sync --locked --all-extras
uv run python scripts/14_evaluate_existing_models.py
uv run pytest -q
uv run ruff check .
```

Copernicus etiketleri resmî bina güvenliği kararı değildir. Spatial holdout bir genelleme stres
testidir; tek bölme dış geçerlilik veya saha performansı kanıtı sayılmaz.

