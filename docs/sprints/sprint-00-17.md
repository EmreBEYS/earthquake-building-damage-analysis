# Sprint 00-17 — Bina Bazlı Tahmin Haritası

## Model ve özellik sözleşmesi

Sprint 00-16 sonuçlarına göre bina düzeyi sınıflandırma için `random_forest` seçildi. Stratified
holdout macro-F1 değeri `0.3083` ile değerlendirilen modeller arasındaki en yüksek sonuçtur ve
model sınıf olasılığı üretir. Spatial holdout macro-F1 değeri yalnız `0.2388` olduğundan çıktı
operasyonel veya resmî hasar kararı olarak yorumlanamaz.

Model girdisi sırası değiştirilemez:

1. `building_area_m2`
2. `building_perimeter_m`
3. `shape_index`

Bu değerler Sprint 00-14 bina geometrilerinden EPSG:32637 içinde yeniden hesaplanır. Copernicus
`damage_grade`, bina kimliği, mahalle, kaynak ve kalite alanları model girdisi değildir. Gözlenen
hasar yalnız gerçek ve tahmin katmanlarını karşılaştırmak için çıktı özelliklerine eklenir.

## Çalıştırma

Depo, model artefaktlarını `.gitignore` ile dışarıda tutar. Sprint 00-16'da değerlendirilen dosyayı
`models/random_forest.joblib` konumuna geri yükleyin. Dosyanın SHA-256 değeri şu olmalıdır:

`ba7c5087b8bac2d283374934c3b75380a9c90bd1ffc409fc4c53e75e84922818`

```powershell
uv sync --locked --all-extras
uv run python scripts/15_generate_prediction_map.py
uv run streamlit run dashboard.py
```

Üretilen dosyalar:

- `data/dashboard/sprint_00-17/predicted_damage.geojson`
- `data/dashboard/sprint_00-17/manifest.json`

Manifest model ve girdi SHA-256 değerlerini, özellik sırasını, düşük güven sayısını ve veri sızıntısı
denetimini kaydeder. Model karması uyuşmazsa, özellik sırası değişirse, geometri geçersizse veya
olasılık matrisi geçersizse üretim durur; eksik alanlar sessizce sıfıra çevrilmez.

## Harita

Dashboard içindeki **Bina Tahmin Haritası** sayfası gerçek Copernicus sınıflarını ve model
tahminlerini ayrı açılıp kapanabilir katmanlar olarak gösterir. Hover bilgisi gözlenen sınıfı,
tahmini, maksimum sınıf olasılığını ve düşük güven işaretini birlikte verir.

## Doğrulama

```powershell
uv run pytest -q
uv run ruff check .
```

Model dosyası depoda olmadığı için gerçek `predicted_damage.geojson` temiz klonda yeniden üretilemez;
bu yüzden üretilmiş dosya ve manifest depoya eklendi (28 Kasım 2026). Yerel model ile yeniden üretim
bayt bayt aynı dosyayı verdi (SHA-256 `307a114c…1509`). Birim
testleri sentetik ve bağımsız bir modelle şema, olasılık, düşük güven, karma doğrulaması ve sızıntı
reddini sınar.
