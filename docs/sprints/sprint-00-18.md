# Sprint 00-18 — 2022–2023 mekânsal değişim

Durum: **Sentinel-2 spektral değişim taraması gerçek verilerle tamamlandı; tarihli OSM bina
kesitlerinin edinimi engelli.** Uydu sonucu bina hasar sınıfı veya nedensellik sonucu değildir.

## Tekrar üretim

```bash
uv sync --locked --all-extras
uv run python scripts/16_analyze_building_change.py --acquire
uv run python scripts/17_analyze_satellite_change.py all
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

## Sentinel-2 öncesi/sonrası taraması

Gerçek L2A yüzey yansıtım sahneleri Earth Search kamu COG arşivinden alınır:

| Rol | Ürün | Çekim | Depreme uzaklık | Katalog bulutu |
|---|---|---|---:|---:|
| Öncesi | `S2A_37SDC_20221231_0_L2A` | 31 Aralık 2022 08:29 UTC | −37 gün | %8,63 |
| Hemen sonrası | `S2B_37SDC_20230224_0_L2A` | 24 Şubat 2023 08:29 UTC | +18 gün | %2,46 |

9, 11, 14 ve 16 Şubat sahnelerinin AOI05 alanının yaklaşık %99'u SCL bulut/gölge/kar
sınıflarında; 21 Şubat için bu oran %88'dir. 24 Şubat, AOI'ye özgü maskeli oranı %19,14'e
inen ilk kullanılabilir sahnedir. Ürün-geneli katalog bulutu tek başına seçim ölçütü değildir.

AOI, önceki sprintteki 87 doğrulanmış mahalle sınırının birleşimidir; özgün CEMS AOI05
poligonunun birebir kopyası değildir. B02, B03, B04, B08, B11, B12 ve SCL yalnız bu kapsam için
kırpılır. Tüm bantlar EPSG:32637, 10 m, 2.014 × 1.901 piksel ve aynı affine ızgaraya getirilir.
SCL 0, 1, 3, 8, 9, 10 ve 11 geçersizdir. Ortak geçerli AOI oranı %80,86'dır.

NDVI, NDBI ve NBR her tarihte hesaplanır. Bir pikselin aday olması için geçerli ve yapılı çevre
bağlamında bulunması, üç mutlak fark eşiğinden (`0,20`, `0,15`, `0,20`) en az ikisini aşması
gerekir. Sekiz komşulukta dört pikselden küçük bileşenler çıkarılır. Bu eşikler yerel saha
etiketiyle kalibre edilmemiş temkinli tarama kurallarıdır.

Yansıtım `DN × 0,0001 − 0,1` ile hesaplanır (işleme sürümü 05.09; ≥ 04.00 ürünlerde −0,1
offset vardır). İlk sürüm bu offseti uygulamıyordu; 28 Kasım 2026'da düzeltildi ve sonuçlar
yeniden üretildi:

| Ölçüm | Offset'siz (hatalı) | Düzeltilmiş |
|---|---:|---:|
| Aday bileşen | 6.017 | 22.048 |
| Aday alan | 4,6082 km² | 21,7564 km² |
| Ortak geçerli alana oranı | %2,75 | %13,00 |
| En az bir aday pikseli olan EMSR648 poligonu | 1.414 / 3.617 | 3.276 / 3.617 |
| Ortalama aday oranı: Destroyed / No visible damage | 0,104 / 0,040 | 0,428 / 0,240 |

Önceki düşük oran offset hatasının yan etkisiydi: offset'siz yansıtım normalize indeks farklarını
küçültüyordu. Aynı eşikler doğru yansıtımla çok daha az seçicidir; Aralık–Şubat arasındaki
mevsim, güneş açısı ve nem farkını da yakalar. Destroyed poligonları hâlâ belirgin olarak daha
yüksek aday oranı taşır (0,43'e karşı 0,24), ama tarama artık geniş bir "değişmiş olabilir"
maskesidir. Eşikler EMSR648 etiketine göre yeniden ayarlanmadı; bu, karşılaştırmayı değerlendirme
verisine uydurmak olurdu. Kalibrasyon bağımsız saha/çok yüksek çözünürlüklü etiket gerektirir.

Bu sayılar hasarlı bina veya yıkım sayısı değildir. Hasar sınıfına göre ayrıntılı
ölçümler `satellite_emsr648_comparison.csv` içindedir; ilişki doğruluk/duyarlılık ölçüsü değildir.

Teslimler:

- `data/dashboard/sprint_00-18/pre_post_change_map.geojson`;
- `data/dashboard/sprint_00-18/satellite_emsr648_comparison.csv`; ve
- `reports/sprint_00-18/satellite_change_validation.json`.

Kırpılmış rasterlar ve kaynak karma manifesti `data/external/sentinel_2/spectral/` altında
Git dışında kalır. Yeniden üretimde kaynak COG erişimi gerekir. Kontrol listesi:
[`sprint-00-18-checklist.md`](sprint-00-18-checklist.md).
