# Sprint 00-18 kontrol listesi

- [x] GitHub `main`, Sprint 00–17 ve Sprint 18 commit zinciri doğrulandı.
- [x] Masaüstündeki izlenmeyen Sprint 17 çıktıları korundu; destructive reset yapılmadı.
- [x] Öncesi/sonrası Sentinel-2 L2A ürün kimliği ve UTC çekim tarihi sabitlendi.
- [x] AOI kapsamı, EPSG:32637, 10 m çözünürlük, boyut ve affine hizalama doğrulandı.
- [x] SCL bulut, gölge, cirrus, kar, no-data ve doygun piksel maskesi uygulandı.
- [x] NDVI, NDBI ve NBR farkları gerçek yüzey yansıtım bantlarından hesaplandı.
- [x] Yapılı çevre bağlamı ve çoklu indeks eşiğiyle aday değişim alanları vektörleştirildi.
- [x] `pre_post_change_map.geojson` harita katmanına ve indirme düğmesine bağlandı.
- [x] EMSR648 AOI05 poligonlarıyla mekânsal örtüşme ve piksel ölçümleri üretildi.
- [x] Büyük/ara rasterlar Git dışında tutuldu; kaynak URL, tarih, lisans ve SHA-256 kaydedildi.
- [x] 56 algoritma/regresyon testi, Ruff, çıplak dashboard açılışı ve proje kontrolü geçti.
- [x] Tam pytest paketi ve iki Streamlit AppTest GitHub CI Linux ortamında geçti.
- [x] Yöntem, yeniden üretim, kaynak, sınırlılık ve gerçek ölçümler belgelendi.
- [ ] Tarihli ohsome 2022/2023 bina kesitleri edinilemedi; OSM değişim alt iş akışı engelli.
- [ ] Spektral eşikler bağımsız saha/çok yüksek çözünürlüklü görüntüyle kalibre edilmedi.
- [ ] 10 m Sentinel-2 çıktısı bina güvenliği veya bina bazlı hasar kararı olarak doğrulanmadı.
