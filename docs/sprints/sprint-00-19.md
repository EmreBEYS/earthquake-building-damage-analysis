# Sprint 00-19 — 2023–2026 yeniden yapılanma analizi

Durum: **Gerçek verilerle tamamlandı.** Deprem sonrasından günümüze fiziksel şehir dönüşümü,
tarihli OSM bina kesitleri ve Sentinel-2 L2A spektral farkıyla ölçüldü. Teslim
`reconstruction_change_map` katmanıdır. Değişim sınıfları **hasar sınıfı değildir**; EMSR648
yalnız ayrı bir bağlam dosyasında, açıklayıcı örtüşme olarak raporlanır.

## Tekrar üretim

```bash
uv sync --locked --all-extras
uv run python scripts/18_analyze_reconstruction_change.py screen   # 2026 aday sahne taraması
uv run python scripts/18_analyze_reconstruction_change.py acquire  # Sentinel kırpıntıları + OSM
uv run python scripts/18_analyze_reconstruction_change.py analyze
uv run python -m pytest -q
uv run ruff check .
uv run streamlit run dashboard.py   # "2023–2026 Yeniden Yapılanma" sayfası
```

`all`, `acquire` ve `analyze` adımlarını sırayla çalıştırır. Yapılandırma:
[`configs/sprint_00_19.json`](../../configs/sprint_00_19.json). Bir adım başarısız olursa
`reports/sprint_00-19/blocked.json` yazılır ve sonuç üretilmiş gibi gösterilmez.

## Kaynaklar

### Tarihli OSM bina kesitleri

| Rol | Zaman damgası | Kaynak kayıt | AOI içinde seçilen |
|---|---|---:|---:|
| Deprem sonrası | 2023-02-24T00:00:00Z | 60.598 | 49.842 |
| Güncel | 2026-07-27T00:00:00Z | 57.468 | 47.043 |

- Kaynak: Overpass API attic sorgusu, `[date:"…"]; way[building](bbox); out tags geom meta;`.
  Uç noktalar: `overpass.private.coffee` ve `overpass-api.de`. Lisans ODbL 1.0,
  © OpenStreetMap contributors.
- 00-18'de kullanılan ohsome `elements/geometry` uç noktası 25 Kasım 2026'da her veri
  çıkarma isteğine HTTP 403 verdi; bu yüzden reddedildi ve yapılandırmada kayıtlıdır.
- Sunucu yükü nedeniyle bbox 4×4 = 16 karoya bölündü. Her karo
  `data/external/reconstruction/osm/tiles/` altında önbelleğe alınır; kesilen indirme kaldığı
  karodan sürer. İndirme 25–28 Kasım 2026 arasında, çok sayıda 502/504 yeniden denemesiyle
  tamamlandı. Karolar `(type, id)` ile tekilleştirilip birleştirilir; kapanmayan bir çizgi
  (2023'te 1) atılır.
- Birleşik kesitler ve `.source.json` yan dosyaları (sorgu, `osm_base`, SHA-256) Git dışında
  kalır. Kesitler **haritalama durumudur**, fiziksel gözlem tarihi değildir.

### Sentinel-2 L2A

| Rol | Ürün | Çekim | İşleme | AOI geçersiz (SCL) |
|---|---|---|---|---:|
| Deprem sonrası | `S2B_37SDC_20230224_0_L2A` | 24 Şubat 2023 08:29 UTC | 05.09 | %19,14 |
| Güncel | `S2C_37SDC_20260305_0_L2A` | 5 Mart 2026 08:29 UTC | 05.12 | %8,96 |

Ortak geçerli AOI oranı %80,72'dir. Güncel sahne için dört aday tarandı
(`reports/sprint_00-19/scene_screening.json`). İlk çalıştırma en az bulutlu 12 Kasım 2026
sahnesiyle yapıldı ve **reddedildi**: spektral değişim geçerli alanın %22'sini kaplıyor,
değişmeyen ayak izlerinin %50'sini de "destekliyordu"; yani mevsim farkını yeniden yapılanmadan
ayıramıyordu. 5 Mart 2026, 24 Şubat 2023'e yılın günü olarak 9 gün uzaktır. Bu sahneyle aday
alan %14,65'e, değişmeyen binalardaki destek %25,7'ye indi (aşağıdaki tablo).

Yansıtım `DN × 0,0001 − 0,1` ile hesaplanır (işleme sürümü ≥ 04.00 için offset). B02, B03,
B04, B08, B11, B12 ve SCL yalnız AOI için kırpılır; kırpıntılar ve kaynak karma manifesti
`data/external/sentinel_2/reconstruction/` altında Git dışında kalır. Türetilmiş çıktılar
`Contains modified Copernicus Sentinel data 2023–2026` atfını taşır.

AOI ve mahalleler: 00-12'deki 87 gözden geçirilmiş OSM mahalle sınırı ve bunların birleşimi.
Metrik işlemler EPSG:32637, 10 m ızgarada yapılır.

## Yöntem

### 1. Kaldırılan ve yeni görünen yapılar

İki kesit, 00-18'deki `match_buildings` ile bire bir IoU eşleştirmesinden geçer (alt eşik 0,50,
değişmedi eşiği 0,90; açgözlü eşleştirme yok, bölünme/birleşme belirsiz kalır). OSM durumu
yeniden yapılanma sınıfına şöyle çevrilir:

| OSM durumu | Yeniden yapılanma sınıfı | Türkçe etiket |
|---|---|---|
| unmatched | `removed_candidate` | Kaldırılmış yapı adayı |
| newly_mapped | `new_candidate` | Yeni yapı adayı |
| geometry_changed | `modified_candidate` | Değişmiş yapı adayı |
| unchanged | `persistent` | Kalıcı yapı |
| uncertain | `uncertain` | Belirsiz |
| — | `spectral_only_change` | Yalnız uyduda değişim |

"Aday" kelimesi bilinçlidir: 2026'da olmayan bir ayak izi edit düzeltmesi, yeni bir ayak izi
de geç çizilmiş eski bir bina olabilir.

### 2. Spektral kanıt

Her tarih için NDVI, NDBI ve BSI hesaplanır. Bir piksel, geçerliyse ve üç mutlak fark
eşiğinden (`|ΔNDVI| ≥ 0,20`, `|ΔNDBI| ≥ 0,15`, `|ΔBSI| ≥ 0,15`) en az ikisini aşıyorsa
değişim adayıdır; dört pikselden küçük bileşenler atılır. Her ayak izi için `all_touched` ile
temiz piksel ve değişim pikseli sayılır:

- değişim oranı ≥ 0,50 → `osm_and_spectral`;
- daha düşük → `osm_only`;
- temiz piksel yok → `osm_only_no_clear_pixels`.

Hiçbir OSM değişim birimine dokunmayan spektral bileşenler `spectral_only_change` olur.
Ortalama indeks farkları bir `direction_hint` üretir (ör. `bare_soil_index_increase`); bu
yalnız yön ipucudur.

### 3. Mahalle göstergeleri

Her birim temsilî noktasıyla mahalleye atanır; hiçbir mahalleye düşmeyenler `unknown` olur
(17 birim, hepsi belirsiz). `neighborhood_reconstruction_indicators.csv` mahalle başına şunları
verir: 2023/2026 bina sayısı ve taban alanı, net alan değişimi, kaldırılan/yeni aday sayısı,
alanı, payı ve spektral destekli sayısı, yeni yapı yoğunluğu (km² başına), değişmiş/kalıcı/
belirsiz sayıları, yenilenme devri (`renewal_turnover_pct`) ve spektral değişim alanı payı.

### 4. Değişimi hasarla karıştırmama

- `assert_no_damage_fields`, değişim çıktılarında `damage`, `hasar`, `grade`, `emsr`,
  `severity`, `collapsed` veya `yikik` içeren bir sütun varsa çalıştırmayı durdurur.
- EMSR648 hasar sınıfları yalnız `reconstruction_vs_emsr648_context.csv` içinde, birim
  sayısıyla ve "spatial co-occurrence only; not a damage label or accuracy" notuyla yer alır.
- Dashboard'da yeniden yapılanma sayfası hasar katmanlarından ayrıdır; EMSR648 bağlamı ayrı bir
  açılır bölümde, uyarı metniyle gösterilir.

## Sonuçlar (gerçek çalıştırma, 28 Kasım 2026)

| Sınıf | Birim | Uydu destekli |
|---|---:|---:|
| Kaldırılmış yapı adayı | 2.414 | %44,0 |
| Yeni yapı adayı | 166 | %51,8 |
| Değişmiş yapı adayı | 119 | %26,1 |
| Kalıcı yapı | 45.309 | %25,7 |
| Belirsiz | 3.409 | %30,1 |
| Yalnız uyduda değişim | 8.981 bileşen | — |

- Taban alanı 12,68 km²'den 12,01 km²'ye indi; AOI'deki ayak izi sayısı 2.799 azaldı.
- Spektral aday alan 24,48 km², ortak geçerli alanın %14,65'i.
- Haritada 15.089 öğe vardır (kalıcı yapılar haritaya konmaz, CSV'de sayılır).
- IoU alt eşiği 0,30/0,50/0,70 için kaldırılan (2.415) ve yeni (166) aday sayısı değişmez;
  yalnız değişmiş/belirsiz ayrımı kayar (166/119/55 değişmiş).
- En çok kaldırılan adayı olan mahalleler: Zaviye (165), Yıldıztepe (135), Hamidiye (110),
  Karakavak (108), Tecde (97). Ferhadiye'de 2023'teki 133 binanın 78'i kaldırılan aday.
- En çok yeni aday: Çamurlu (34) ve Topsöğüt (32; 32'si de uydu destekli).
- Yeni aday sayısının düşüklüğü, yeni yapıların OSM'ye geç işlenmesiyle uyumludur; yeni yapılaşma
  bu veride **eksik ölçülmektedir**.

## Çıktılar

`data/dashboard/sprint_00-19/`:

- `reconstruction_change_map.geojson` (WGS84; dashboard ve indirme katmanı)
- `reconstruction_change_map.parquet` (GeoParquet, EPSG:32637, tam hassasiyet)
- `neighborhood_reconstruction_indicators.csv` (87 mahalle + `unknown`)
- `reconstruction_vs_emsr648_context.csv` (yalnız bağlam)

`reports/sprint_00-19/reconstruction_validation.json`: sınıf ve kanıt sayıları, IoU eşik
duyarlılığı, bulut istatistikleri, tüm girdi/çıktı SHA-256 değerleri, tekrar okuma ve korunum
kontrolleri (her kesitteki her ayak izi tam bir kez temsil edilir) ve sınırlılıklar.

## Sınırlılıklar

- OSM kesitleri haritalama durumudur; kaldırılan/yeni adaylar edit düzeltmesi veya geç çizim
  olabilir. Saha ya da çok yüksek çözünürlüklü görüntü doğrulaması yapılmadı.
- 2026 OSM kesiti (27 Temmuz) ile 2026 Sentinel-2 sahnesi (5 Mart) eş zamanlı değildir; aradaki
  dönemde değişen binalar yanlış etiketlenebilir.
- 10 m pikseller çoğu ayak izinde birkaç karışık pikseldir. Mevsim eşleştirmesinden sonra da
  spektral fark fenoloji, toprak nemi ve kar etkisi içerir: kalıcı binaların %25,7'si de "uydu
  destekli" görünür. Spektral destek doğrulayıcı kanıttır, kanıt değildir.
- Eşikler saha etiketiyle kalibre edilmemiş tarama kurallarıdır.
- 00-18 hattındaki eksik −0,1 yansıtım offseti 28 Kasım 2026'da düzeltildi; iki hat artık aynı
  `reflectance` fonksiyonunu kullanır.

Kontrol listesi: [`sprint-00-19-checklist.md`](sprint-00-19-checklist.md).
