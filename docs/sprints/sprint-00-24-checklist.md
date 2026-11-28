# Sprint 00-24 kontrol listesi — Test, akademik doğrulama ve demo

## Fonksiyonel ve CBS kalite testleri

- [x] Depodaki her GeoJSON katmanı için kontroller: WGS84, geçerli ve boş olmayan geometri,
      Malatya zarfı içinde (`tests/test_gis_quality.py`).
- [x] Mahalle topolojisi: komşu mahalleler arasında küçük mahallenin %1'inden büyük örtüşme yok.
- [x] Sprintler arası tutarlılık:
  - 87 mahalle kimliği tüm tablolarda aynı
  - 46.563 resmî kayıt korunuyor
  - EMSR648, tahmin ve bina detayları aynı 3.617 kimliği paylaşıyor
- [x] Rapor ve manifestlerdeki SHA-256 değerleri depodaki dosyalarla eşleşiyor.
- [x] Değişim çıktılarında hasar alanı yok; sıcak nokta sınıfları z/p/FDR ile tutarlı.
- [x] Her betik derleniyor; `demo_check.py` iyi ve eksik ortamda test edildi.
- [x] Dashboard'un 16 sayfası, 3 dönemi, harita modları ve 4 rapor türü AppTest ile açılıyor.

## Belgeler

- [x] Belirsizlikler, sınırlılıklar ve atıflar: [`docs/limitations.md`](../limitations.md).
- [x] README: güncel klasör yapısı, Windows ve macOS kurulumu, V4 bağlantıları.
- [x] V4 final raporu: [`docs/final-report.md`](../final-report.md).
- [x] Demo kılavuzu ve 12 dakikalık sunum akışı: [`docs/demo.md`](../demo.md).

## Demo testi

- [x] Windows 11 geliştirme ortamında:
  - `uv sync --locked --all-extras`
  - `demo_check.py` "Demo hazır"
  - tüm testler, Ruff ve `check_project`
- [ ] MacBook demo testi: `docs/demo.md` §4 tablosu demo öncesinde elle doldurulacak.
- [x] Tarayıcıda gözle kontrol (1440 px): ana sayfa, interaktif harita, rapor sayfası. Bulunan
      ve düzeltilen sorunlar:
  - menü radyo düğmeleri ve seçili öğe vurgusu
  - dönem seçicinin satır kırması
  - KPI kartlarının taşması
  - kırpılan metrikler
  - halka grafiği etiketleri
  - haritada tıklamanın paneli güncellememesi
  - seçimden sonra katmanların soluklaşması
  - görünmeyen poligon merkezleri
- [ ] Dar ekran (mobil) yerleşiminin gözle kontrolü.
