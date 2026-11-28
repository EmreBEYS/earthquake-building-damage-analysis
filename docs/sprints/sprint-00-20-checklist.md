# Sprint 00-20 kontrol listesi

- [x] Mahalle bazlı hasar yoğunluğu: resmî kayıt ve ağır hasar km² başına, ağır hasar oranı.
- [x] EMSR648 ve 00-17 tahmin payları yalnız yeterli AOI kapsamı olan 72 mahallede hesaplandı.
- [x] Yapı yoğunluğu ve 00-18/00-19 değişim göstergeleri aynı tabloya eklendi.
- [x] Net OSM bina kaybı eklendi; belirsiz (bölünme/birleşme) eşleşmelerin gizlediği dönüşümü yakalar.
- [x] Queen komşuluk (1 m tampon, ada yok) ile küresel Moran's I, LISA ve Getis-Ord Gi*.
- [x] 999 permütasyon, sabit tohum; Gi* için Benjamini–Hochberg FDR bayrağı.
- [x] 500 m grid sıcak noktaları: EMSR648 ağır hasar payı ve kaldırılan yapı payı.
- [x] `neighborhood_comparison.csv`, mahalle GeoJSON'u, grid GeoJSON'u ve Moran özeti.
- [x] Dashboard sayfası: değer, Gi* ve LISA gösterimi, FDR filtresi, grid, tablolar, indirme.
- [x] İstatistikler elle hesaplanmış değerlere karşı test edildi; uçtan uca sentetik test.
- [x] Resmî kayıt toplamı (46.563) korunumu, tekrar okuma ve geometri geçerliliği kontrol edildi.
- [x] 91 test, Ruff ve `check_project` geçti.
- [ ] Mahalle sınırları tarihsel idari sınır kanıtı değil; MAUP duyarlılığı alternatif
      bölümlemeyle test edilmedi.
