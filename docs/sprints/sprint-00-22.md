# Sprint 00-22 — İnteraktif harita ve zaman paneli

Durum: **Tamamlandı.** Teslim `src/earthquake_damage/interactive_map.py`. Dashboard'da
**Harita Analizi → İnteraktif Harita** sekmesindedir.

## Çalıştırma

```bash
uv run python scripts/21_prepare_interactive_map.py   # building_details.csv
uv run python -m streamlit run dashboard.py
```

## Özellikler

- **Altlık:** Uydu (Esri World Imagery), Sokak (OpenStreetMap) veya Koyu (CARTO Dark Matter).
- **GIS katmanları:** her biri sol panelden açılıp kapanır.
  - Mahalle sınırları
  - Resmî ağır hasar oranı
  - Gi* sıcak noktaları
  - EMSR648 hasar sınıfı
  - Model tahmini
  - 2022→2023 spektral değişim
  - 2023→2026 yeniden yapılanma
  - OSM binaları 2022 / 2023 / 2026
- **Dönem seçimi:** üst banttaki 2022 / 2023 / 2026 seçimi, haritada yalnız o döneme ait
  katmanları sunar. Her dönemin varsayılan katmanları vardır.
- **Mahalle odağı:** seçilen mahalleye yakınlaşır ve katmanları o mahalleyle sınırlar. Yoğun
  katmanlar (OSM binaları ve 22.048 spektral poligon) yalnız odakla çizilir; tüm şehirde
  tarayıcıyı kilitlemezler.
- **Yan yana karşılaştırma:**
  - Dönemler: sol ve sağ dönem seçilir; iki harita aynı merkez ve yakınlaştırmayı kullanır.
  - Gerçek ↔ Tahmin: EMSR648 ile model tahmini yan yana gösterilir. Model aynı poligonlarda
    eğitildiği için bu görünüm örneklem içi uyumu gösterir, doğrulama değildir; ekranda da
    yazılır.
- **Bina detay paneli:** 2023 döneminde haritadaki bir poligon merkezine tıklanınca ya da
  listeden seçilince şunlar gösterilir:
  - ilçe ve mahalle
  - EMSR648 sınıfı
  - model tahmini, güveni ve düşük güven uyarısı
  - alan ve çevre
  - 2022→2023 spektral değişim payı
  - içindeki 2023 OSM binaları ve 2026'ya kadar kaldırılan / yeni olanlar
  - sınıf olasılıkları grafiği

## Önemli düzeltme: EMSR648 poligonları tek bina değildir

EMSR648 AOI05 `builtUpA` poligonları yapı alanlarıdır. Medyan alanları 5.111 m²'dir ve çoğu
birden fazla OSM binası içerir. İlk denemede her poligona tek bir OSM binası eşlendi; 3.617
poligonun 3.260'ı eşleşmedi. Bu yaklaşım bırakıldı. Panel artık poligonun içindeki OSM ayak
izlerini (temsilî nokta ile) sayar ve kaldırılan payına göre özetler:

| Durum | Poligon |
|---|---:|
| Kaldırılan OSM binası yok | 2.913 |
| Bir kısmı kaldırılmış (< %50) | 386 |
| Çoğu kaldırılmış (≥ %50) | 150 |
| 2023 OSM'de içinde bina yok | 168 |

Kaldırılma EMSR648 sınıfıyla tutarlı bir eğim gösterir. 2023 OSM binalarının 2026'ya kadar
kaldırılan payı:

| EMSR648 sınıfı | Kaldırılan pay |
|---|---:|
| Destroyed | %29 |
| Damaged | %15 |
| Possibly damaged | %13 |
| No visible damage | %5 |

Bu bir bağlam ölçüsüdür, doğrulama değildir.

## Veri

`data/dashboard/sprint_00-22/building_details.csv` 3.617 satırdan oluşur. Sütunlar: kimlik,
mahalle, ilçe, EMSR648 sınıfı, alan, çevre, merkez koordinatı, spektral kaplama, OSM sayıları,
durum, tahmin, güven ve olasılıklar. Yan dosyada SHA-256 ve kullanılan 2023 OSM kesitinin karması
vardır. OSM sayıları Git dışındaki 2023 kesitini gerektirir. Kesit yoksa sütunlar `-1` ve
`snapshot_unavailable` olur; panel bunları "—" ve "OSM kesiti yerelde yok" olarak gösterir.

## Testler

- `tests/test_interactive_map.py`: sayım, durum eşikleri, spektral pay, yakınlaştırma, panel
  metinleri, seçim olayı ve teslim edilen tablonun bütünlüğü.
- `tests/test_dashboard_app.py`: her dönem için odak, yoğun katmanlar ve iki karşılaştırma
  modu; panelde seçilen poligonun gösterilmesi.

## Sınırlılıklar

- Haritada tıklama seçimi yalnız 2023 döneminde, poligon merkezleri için açıktır; liste her
  zaman çalışır.
- 2022 OSM katmanı, 00-18 Overpass indirmesi tamamlanınca dolar; o zamana kadar not gösterilir.
- Uydu altlığı görsel bağlamdır; tarihi belirsizdir ve hasar kanıtı değildir.
