# Sprint 00-18 — 2022–2023 mekânsal değişim

Durum: **Kod ve yerel algoritma/arayüz kontrolleri hazır; tarihli veri edinimi engelli.**
İki gerçek tarihli kesit elde edilmeden sprint bilimsel analiz bakımından tamamlanmış sayılmaz.

## Tekrar üretim

```bash
uv sync --locked --all-extras
uv run python scripts/16_analyze_building_change.py --acquire
uv run pytest -q
uv run ruff check .
uv run streamlit run dashboard.py
```

İndirmeyi tekrar etmeden çalışmak için `--acquire` kaldırılabilir. OSM dosyaları
`data/external/building_change/buildings_2022.geojson` ve `buildings_2023.geojson` olmalıdır.
Her özellik gerçek `@snapshotTimestamp` ve kaynak kimliğini taşımalıdır. İsim veya OSM son
edit tarihi, tarihli kesit kanıtı yerine geçmez. Boş kesitler ve yinelenen kimlikler reddedilir.
Edinim komutu istek parametrelerini, kaynak atfını ve SHA-256 değerlerini yan dosyaya kaydeder.

## Kaynak seçimi ve kapsam

- Planlanan tarihler: 2022-12-31T00:00:00Z ve 2023-12-31T00:00:00Z.
- Kaynak: https://api.ohsome.org/v1/elements/geometry ; OpenStreetMap geçmişi, ODbL 1.0.
- API sözleşmesi: https://docs.ohsome.org/ohsome-api/development/endpoints.html
- Kesitler haritalama durumudur. Geometrinin fiziksel gözlem tarihi veya deprem etkisi değildir.
- 5 Şubat 2023 tarihli önceki OSM örneklemi **2022 kesiti olarak kullanılmaz**.
- Sentinel-2 10 m görüntüleri bina ayak izi vektörleri yerine geçirilmez.
- Battalgazi ve Yeşilyurt: `configs/datasets.json` içindeki iki sabit geoBoundaries shapeID ve
  SHA-256 ile doğrulanan ilçe sınırları kullanılır. Bunlar projenin AOI05 bounding box'ıyla kesiştirilir.
  Bu kutu, özgün Copernicus AOI poligonunun birebir yeniden üretimi değildir.
- Mahalle sınırları: önceki sprintin 87 gözden geçirilmiş OSM sınırı; tarihsel idari sınır kanıtı değildir.
- Copernicus karşılaştırma kaynağı: depodaki EMSR648 AOI05 GRA builtUpA r1 v1 katmanı,
  3.617 görüntülenebilir poligon. Başka bir v2 haritasının görüntü tarihi v1'e aktarılmaz.
  Aktivasyon: https://mapping.emergency.copernicus.eu/activations/EMSR648/

## Yöntem

Kaynak GeoJSON WGS84 kabul edilir, geçersiz geometriler `make_valid` ile onarılır;
poligon olmayan parçalar alınmaz. Çökerek kaybolan kaynak geometriler varsa sınıflandırma
inceleme için durur. Tam ayak izleri kapsamla kesişmeye göre seçilir, sınırda kesilmez.
Alan ve IoU işlemleri EPSG:32637'de yapılır. Onarım gerektiren ve kapsam sınırını aşan
geometrilerin sonuçları belirsiz işaretlenir.

IoU = kesişim alanı / birleşim alanı. STRtree aday aramasından sonra pozitif alanlı
örtüşmeler incelenir. Yalnız iki yönde de tek adayı olan eşleşmeler kabul edilir:

| Kod | Anlam |
|---|---|
| unchanged | IoU >= 0,90; eşik altında geometrik fark olmadığı iddiası değildir |
| geometry_changed | 0,50 <= IoU < 0,90; harita geometrisi değişimi |
| newly_mapped | Son kesitte örtüşen aday yok; yeni inşaat kanıtı değildir |
| unmatched | İlk kesitte örtüşen aday yok; yıkılmış anlamına gelmez |
| uncertain | Düşük IoU, rakip aday, bölünme/birleşme, onarım veya sınır belirsizliği |

Açgözlü eşleştirme kullanılmaz. Bölünme ve birleşmeler tek binaya zorlanmaz. Her girdi kaydı
kendi tarafında tam bir kez temsil edilir. Kabul edilmeyen eşleşmelerde iki taraf ayrı belirsiz
birimlerdir; toplam çıktı satırı fiziksel benzersiz bina sayısı değildir.

Mahalle ataması maksimum kesişim alanıyla yapılır; yakın eşitlik ve kapsanmama `unknown`
olur. CSV bu analiz birimlerini sayar; resmî stok veya net inşaat/yıkım sayısı değildir.
Copernicus için tüm pozitif alanlı örtüşmeler ayrı CSV'ye yazılır. Bunlar mekânsal ilişkidir;
etiket aktarımı, confusion matrix veya doğruluk iddiası üretilmez. Hiçbir model yeniden eğitilmez;
değişim ve hasar alanları model girdilerine eklenmez. Tahmin katmanı mevcut 00-17 dosyasını okur.

IoU alt eşiği 0,30/0,50/0,70 için ham eşleşme duyarlılığı raporlanır. Bu bir konumsal doğruluk
kalibrasyonu değildir. Kayıt dışı binalar, OSM edit gecikmesi, georeferans hatası, mevsimsellik ve
2023 boyunca yapılan deprem dışı değişiklikler bağımsız görüntü/saha doğrulaması gerektirir.

## Üretilecek çıktılar

Başarılı gerçek veri çalıştırmasında `data/dashboard/sprint_00-18/`:

- `building_change_2022_2023.geojson` (WGS84)
- `building_change_2022_2023.parquet` (GeoParquet, EPSG:32637)
- `neighborhood_change_summary.csv`
- `copernicus_overlap_comparison.csv`
- `buildings_2022.geojson`, `buildings_2023.geojson`

`reports/sprint_00-18/validation_report.json` girdi karmalarını, onarım/dışlama sayılarını,
eşik duyarlılığını ve çıktı tekrar okuma kontrolünü kaydeder. Dosyaların var olması tek başına
bilimsel doğrulama değildir; kaynak ve saha değerlendirmesi ayrıca gereklidir.

Dashboard ayrı açılıp kapanan beş katman sunar: 2022, 2023, değişim, Copernicus ve tahmin.
Eksik katmanlar devre dışıdır; boş veri gerçek sıfır değişim olarak gösterilmez.
