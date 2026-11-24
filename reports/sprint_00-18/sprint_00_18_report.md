# Sprint 00-18 çalışma raporu — 24 Kasım 2026

**Kısmi tamamlandı: yöntem, kod ve arayüz hazır; gerçek dönem karşılaştırması engelli.**

## Doğrulanmış durum

- GitHub ana dalı `57e18087a98a50b09005a224687a024c38026e1d` üzerinden çalışıldı.
  İlk yerel kopya `6e2a7c0` seviyesindeydi; 00-17 ana dala alınmıştı.
- `predicted_damage.geojson` depoda ve incelenen yerel kopyada yok.
  `models/random_forest.joblib` da yok. Önceki sprintin kodu ve SHA-256 sözleşmesi korundu;
  model yerine başka model eğitilmedi ve tahmin sonuçları uydurulmadı.
- Mevcut Copernicus katmanı 3.617 poligon; mahalle katmanı 87 sınır içeriyor.
- Gerçek 2022 ve 2023 tarihli bina kesitleri mevcut değil. Edinim komutu çalıştırıldı:
  ağ/DNS `ConnectError` ile durdu. Detay: `validation_report.json`, `acquisition_attempt.txt`.
- GeoPandas, pyproj, pytest ve ruff yerel Python ortamında yok; bağımlılık indirme denemesi de
  başarısız. Bu nedenle tüm coğrafi işlem zinciri ve tam pytest/ruff yerelde doğrulanamadı.

## Gerçekleştirilen kontroller

- Depodaki gerçek Copernicus geometrileriyle 7 algoritma testi başarılı.
  Kapsam: aynı geometri, değişen örtüşme, düşük IoU, rakip aday/bölünme/birleşme,
  eşleşmeyen/yeni haritalanan ayrımı, kayıt korunumu, eşik ve tarih/kimlik reddi.
- Streamlit AppTest: genel açılış, 2022–2023 sayfası, Harita · Katmanlar,
  Bina Tahmin Haritası ve Gerçek Hasar Haritası exception olmadan açıldı.
- Yeni Python kodu derleme kontrolünden geçti.
- Test geometrileri kontrollü algoritma girdileridir; tarihli gerçek 2022/2023 gözlemi sayılmaz.

## Üretilmeyen bilimsel sonuçlar

`building_change_2022_2023.geojson`, `.parquet` ve `neighborhood_change_summary.csv`
üretilmedi. Bu dosyalara boş veya kurgusal sonuç yazılmadı. Değişen bina sayısı, mahalle
istatistiği ve Copernicus karşılaştırma sonucu şu aşamada raporlanamaz.

## Devam koşulları

Ağ erişimi ve kilitli coğrafi bağımlılıklarla veri edinim komutunu yeniden çalıştırın.
Kesit tarihlerini ve ilçe sınırı karmasını doğrulayın; ardından çıktı sayımı/geometri/CRS,
GeoJSON–GeoParquet tekrar okuma, mahalle kapsama ve IoU duyarlılık raporlarını inceleyin.
Bu kesitler OSM haritalama değişimini gösterir; fiziksel deprem etkisini doğrulamak için
bağımsız görüntü veya saha örneklemi gerekir.

Yöntem ve komutlar: `docs/sprints/sprint-00-18.md`.

## GitHub CI doğrulaması

İlk geliştirme commit'i `1e3379e` için tam kilitli ortam doğrulandı:
**55 test geçti**, Ruff başarılı ve `scripts/check_project.py` hatasız.
Çalıştırma: https://github.com/EmreBEYS/earthquake-building-damage-analysis/actions/runs/45361012331

Ayrı veri edinme iş akışı gerçek kaynaklara erişimi GitHub ortamında da dener;
başarılı sonuçları veya engel kanıtlarını indirilebilir artifact olarak saklar.
İş akışı başarısızsa veri çıktılarının doğrulandığı anlamına gelmez.
