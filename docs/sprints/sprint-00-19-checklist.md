# Sprint 00-19 kontrol listesi

- [x] Tarihli OSM bina kesitleri (2023-02-24 ve 2026-07-27) Overpass attic sorgusuyla, 16 karoda
      gerçek veriyle edinildi; sorgu, `osm_base` ve SHA-256 yan dosyalara kaydedildi.
- [x] ohsome 403 reddi ve Overpass'a geçiş yapılandırmada belgelendi.
- [x] İki kesit 00-18 bire bir IoU kurallarıyla eşleştirildi; kaldırılan, yeni, değişmiş, kalıcı
      ve belirsiz adaylar üretildi.
- [x] Sentinel-2 L2A 24 Şubat 2023 / 5 Mart 2026 sahneleri hizalandı, SCL maskelendi, −0,1
      offset uygulandı; NDVI/NDBI/BSI farkları hesaplandı.
- [x] Mevsim uyumsuz 12 Kasım 2026 sahnesi denendi, ölçülen gerekçeyle reddedildi.
- [x] Her ayak izi için spektral kanıt (`osm_and_spectral` / `osm_only`) ve yalnız uydu
      bileşenleri üretildi.
- [x] 87 mahalle için yapılaşma göstergeleri (`neighborhood_reconstruction_indicators.csv`).
- [x] Değişim çıktılarında hasar alanı olmadığı otomatik kontrol edildi; EMSR648 yalnız ayrı
      bağlam CSV'sinde.
- [x] `reconstruction_change_map` GeoJSON/GeoParquet, dashboard sayfası ve indirme düğmeleri.
- [x] Tekrar okuma ve ayak izi korunum kontrolleri geçti.
- [x] 76 test (17'si yeni), Ruff ve `check_project` geçti.
- [ ] Kaldırılan/yeni adaylar saha veya çok yüksek çözünürlüklü görüntüyle doğrulanmadı.
- [ ] Spektral eşikler kalibre edilmedi; kalıcı binaların %25,7'si de spektral destekli.
- [ ] 00-18 hattındaki eksik −0,1 yansıtım offseti ayrı işte düzeltilmeli.
