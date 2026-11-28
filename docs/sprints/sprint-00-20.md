# Sprint 00-20 — Mekânsal analiz ve mahalle karşılaştırması

Durum: **Gerçek verilerle tamamlandı.** Hasar dağılımı, yapı yoğunluğu ve değişim göstergeleri
87 mahallede bir karşılaştırma tablosunda birleştirildi. Kümelenme küresel Moran's I ile,
sıcak noktalar Getis-Ord Gi* ve yerel Moran (LISA) ile ölçüldü. Kaynaklar **yan yana konur,
birbirine dönüştürülmez**: resmî kayıt, EMSR648 ve model tahmini ayrı sütunlarda kalır.

## Tekrar üretim

```bash
uv run python scripts/19_analyze_spatial_neighborhoods.py
uv run python -m pytest -q tests/test_spatial_analysis.py
uv run streamlit run dashboard.py   # "Mekânsal Analiz ve Mahalle Karşılaştırması" sayfası
```

Yapılandırma: [`configs/sprint_00_20.json`](../../configs/sprint_00_20.json). Hata durumunda
`reports/sprint_00-20/blocked.json` yazılır. 500 m grid'deki kaldırılan yapı payı, Git dışındaki
00-19 OSM kesitini (`buildings_post_event.geojson`) gerektirir. Bu dosya yoksa o grid değişkeni
"veri yok" olur ve raporda `osm_post_event_snapshot_sha256: null` görünür.

## Girdiler

| Kaynak | Sprint | Düzey | Rol |
|---|---|---|---|
| Bakanlık hasar tespit kayıtları (46.563) | 00-15 | Mahalle (isimle eşleşmiş, koordinatsız) | Hasar yoğunluğu |
| Copernicus EMSR648 AOI05 (3.617 poligon) | 00-12 | Bina | Bağımsız uzaktan algılama hasarı |
| Random forest tahminleri (3.617) | 00-17 | Bina | Yalnız karşılaştırma |
| OSM 2023/2026 bina kesitleri | 00-19 | Bina → mahalle | Yoğunluk ve değişim |
| Sentinel-2 2022→2023 spektral aday alanlar | 00-18 | Poligon | Deprem dönemi değişim |

Tüm girdilerin SHA-256 değerleri `reports/sprint_00-20/spatial_analysis_validation.json`
içindedir.

## Yöntem

### Mahalle göstergeleri

- **Hasar yoğunluğu:** resmî kayıt ve ağır hasar (ağır + acil yıkım + yıkık) sayısı km² başına;
  ağır hasar oranı.
- **EMSR648 ağır hasar payı:** Damaged + Destroyed / tüm EMSR648 binaları. Yalnız alanının en az
  %50'si aktivasyon AOI'si içinde kalan mahallelerde hesaplanır (72 mahalle). Diğerlerinde boş
  bırakılır, sıfır yazılmaz.
- **Model tahmini payı:** aynı ölçütle 00-17'de damaged/destroyed tahmin edilen bina payı.
- **Yapı yoğunluğu:** 2023 OSM bina sayısı / km² ve taban alanı kaplama yüzdesi.
- **Net OSM bina kaybı:** (2023 − 2026) / 2023 OSM bina sayısı. Kaldırılan yapı payını
  tamamlar. 00-19'un temkinli bire bir eşleştirmesi, 2026'da bölünen ya da birleşen ayak
  izlerini "belirsiz" bırakır ve kaldırılmış saymaz. Örneğin Dabakhane'de 185 bina 38'e iner,
  ama 211 birim belirsiz olduğu için kaldırılan payı yalnız %5,9 görünür. Net kayıp burada
  %79'dur.
- **Değişim:** 00-19 kaldırılan yapı payı, yeni yapı yoğunluğu, yenilenme devri ve spektral
  değişim payı. Buna 00-18'in 2022→2023 spektral aday alanının mahalle alanına oranı eklenir.

Bina düzeyindeki katmanlar mahalleye temsilî nokta ile atanır. 19 EMSR648 binası hiçbir mahalleye
düşmez ve mahalle tablolarında sayılmaz. Her gösterge için sıralama sütunları (`rank_*`) da
yazılır.

### Mekânsal ağırlıklar ve istatistikler

- **Komşuluk:** queen komşuluk. 1 m tamponla kesişen mahalleler komşudur; bağımsız sayısallaştırılmış
  sınırlardaki boşluklar böylece kapanır. Ada (komşusuz mahalle) yoktur; ortalama komşu sayısı
  5,7'dir.
- **Küresel Moran's I:** satır standardize ağırlıklar ve 999 permütasyonla (tohum 20) pseudo p.
- **LISA:** koşullu permütasyonla yerel Moran ve HH / LL / HL / LH sınıfları (p < 0,05).
- **Getis-Ord Gi\*:** birimin kendisini de içeren ikili ağırlıklar, analitik z ve normal p ile
  %90/%95/%99 güven sınıfları. 87 eşzamanlı test yapıldığı için ayrıca Benjamini–Hochberg FDR
  (α = 0,05) bayrağı yazılır.
- **Grid:** 500 m'lik grid'de Gi\*. EMSR648 ağır hasar payı en az 5 binalı hücrelerde (222 hücre),
  kaldırılan yapı payı en az 10 binalı hücrelerde (554 hücre) hesaplanır.

İstatistikler NumPy ile yazıldı ve elle hesaplanmış değerlere karşı test edildi: 4 birimlik bir
dizide Moran I = 0,4, Gi\* z = 1,549, BH adım-yukarı ve LISA kadranları. Yeni bağımlılık eklenmedi.

## Sonuçlar (28 Kasım 2026)

### Küresel Moran's I (87 mahalle, 999 permütasyon)

| Gösterge | Moran I | z | p | Gi* sıcak (≥%95) | Gi* soğuk (≥%95) | FDR anlamlı | LISA HH / LL |
|---|---:|---:|---:|---:|---:|---:|---:|
| Resmî ağır hasar oranı | 0,489 | 7,90 | 0,001 | 11 | 14 | 6 | 11 / 20 |
| Resmî ağır hasar yoğunluğu | 0,521 | 8,31 | 0,001 | 16 | 6 | 9 | 14 / 20 |
| Bina yoğunluğu 2023 | 0,436 | 6,92 | 0,001 | 13 | 10 | 11 | 11 / 10 |
| Kaldırılan yapı payı 2023→2026 | 0,180 | 3,23 | 0,006 | 10 | 0 | 2 | 8 / 16 |
| Net OSM bina kaybı 2023→2026 | 0,430 | 7,00 | 0,001 | 13 | 0 | 10 | 8 / 12 |

Beş göstergenin hepsi rastgele dağılımdan anlamlı biçimde kümelenmiştir.

- **Ağır hasar oranı:** FDR ile doğrulanan sıcak noktalar Dabakhane, İsmetiye, Kavaklıbağ,
  Yenihamam, Cirikpınar ve Salköprü'dür. LISA Yüksek-Yüksek kümesi bunlara Niyazi, Akpınar,
  B.Hüseyinbey, Saray ve Nuriye'yi ekler. Bu mahalleler tarihî kent merkezinde bitişik bir
  çekirdek oluşturur.
- **Ağır hasar yoğunluğu:** FDR sıcak noktaları aynı çekirdeğe Akpınar, B.Hüseyinbey, Saray ve
  İstiklal'i ekler.
- **Net OSM bina kaybı:** FDR sıcak noktaları Niyazi, Şıkşık, Cirikpınar, Yenihamam, Dabakhane,
  Saray, İstiklal, İsmetiye, Kavaklıbağ ve Nuriye'dir. Bu, hasar çekirdeğiyle büyük ölçüde örtüşen
  bitişik bir kayıp kümesidir.
- **Kaldırılan yapı payı:** FDR sıcak noktaları Kavaklıbağ ve Şıkşık'tır. LISA HH kümesi
  Niyazi, Kırçuval, Yenihamam, B.Hüseyinbey, İsmetiye ve Nuriye'yi de içerir. Yani yıkım/temizlik,
  hasarın yoğunlaştığı merkez çekirdekte toplanmıştır.

### Kaynaklar arası uyum (Spearman ρ)

| Karşılaştırma | n | ρ |
|---|---:|---:|
| Resmî ağır hasar oranı ↔ kaldırılan yapı payı | 87 | 0,61 |
| Resmî ağır hasar oranı ↔ net OSM bina kaybı | 87 | 0,62 |
| Kaldırılan yapı payı ↔ net OSM bina kaybı | 87 | 0,90 |
| Bina yoğunluğu ↔ resmî ağır hasar yoğunluğu | 87 | 0,72 |
| Resmî ağır hasar oranı ↔ EMSR648 ağır hasar payı | 72 | 0,30 |
| Resmî ağır hasar oranı ↔ model tahmini payı | 72 | 0,35 |
| EMSR648 ↔ model tahmini payı | 72 | 0,93 |
| Resmî ağır hasar oranı ↔ 2022–2023 spektral değişim | 87 | 0,17 |

- İki bağımsız kaynak arasında açık bir uyum var: resmî hasar oranı yüksek mahallelerde 2023–2026
  arasında daha çok yapı kaldırılmış (ρ = 0,61).
- Resmî kayıt ile EMSR648 arasındaki uyum zayıftır (ρ = 0,30). EMSR648 binaların yalnız bir
  kısmını ve yalnız görüntüden görülebilen hasarı kapsar.
- EMSR648 ile model tahmini arasındaki 0,93 **doğrulama değildir**: model aynı EMSR648 binalarında
  eğitildi, sonuç büyük ölçüde örneklem içidir.
- 2022–2023 spektral değişim hasarla zayıf ilişkilidir; 00-18'deki düşük seçicilikle uyumludur.

### Grid (500 m)

| Değişken | Analiz edilen hücre | Sıcak nokta %99 / %95 / %90 | FDR anlamlı |
|---|---:|---:|---:|
| EMSR648 ağır hasar payı | 222 | 18 / 13 / 5 | 15 |
| Kaldırılan yapı payı | 554 | 52 / 24 / 14 | 43 |

## Çıktılar

`data/dashboard/sprint_00-20/`:

- `neighborhood_comparison.csv`: 87 mahalle, 75 sütun; göstergeler, sıralar ve her değişken için
  Gi\* z/p/FDR/sınıf ile LISA p/sınıf.
- `neighborhood_spatial_analysis.geojson`: aynı tablo; WGS84, Türkçe sınıf etiketleriyle.
- `hotspot_grid.geojson`: 500 m grid Gi\* sonuçları.
- `spatial_autocorrelation_summary.csv`: küresel Moran özeti.

`reports/sprint_00-20/spatial_analysis_validation.json`: ağırlık tanımı, permütasyon/tohum, tüm
sonuçlar, girdi/çıktı SHA-256 değerleri, tekrar okuma ve resmî kayıt toplamı korunum kontrolü
(46.563) ve sınırlılıklar.

## Sınırlılıklar

- Resmî kayıtlar koordinatsız, isimle eşleşmiş mahalle toplamlarıdır. Yoğunluklar kayıtların
  mahalle poligonunun tamamına ait olduğunu varsayar.
- Mahalleler alan ve kayıt sayısında çok farklıdır (değiştirilebilir alansal birim sorunu, MAUP);
  sıcak noktalar bu bölümlemeye ve komşuluk tanımına bağlıdır.
- 87 eşzamanlı yerel testte yanlış pozitifler artar. %90/%95/%99 sınıfları keşif içindir;
  doğrulayıcı ifadeler FDR bayrağına dayanmalıdır.
- 00-17 tahminleri keşif amaçlıdır (mekânsal macro-F1 0,24) ve hiçbir zaman yer gerçeği olarak
  kullanılmaz.
- Korelasyonlar kaynaklar arası uyumu anlatır, nedensellik değildir.

Kontrol listesi: [`sprint-00-20-checklist.md`](sprint-00-20-checklist.md).
