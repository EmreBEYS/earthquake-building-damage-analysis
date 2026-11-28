# Belirsizlikler, sınırlılıklar ve kaynaklar

Bu belge projedeki bütün belirsizlik kaynaklarını tek yerde toplar. Sprint belgelerindeki
ayrıntılı notlar burada kaynak, yöntem ve model başlıklarında özetlenir. Lisans ve sağlama
(SHA-256) bilgisi için [`data-sources.md`](data-sources.md) ve `data/inventory.csv`'ye bakın.

## 1. Veri kaynakları

| Kaynak | Ne ölçer | Başlıca belirsizlik |
|---|---|---|
| Bakanlık hasar tespit kayıtları (46.563) | Saha tespitine dayalı 6 sınıflı hasar | Koordinat yok; mahalleye isimle bağlanır. Tüm bina stokunun rastgele örneklemi değildir. PDF'ten çıkarılmıştır; çıkarım sırasında elenen statüler kapsamı etkiler. Kayıt–bina bire bir değildir. |
| Copernicus EMS EMSR648 AOI05 (3.617) | Uydu/hava görüntüsünden hasar yorumu | Poligonlar tek bina değil, yapı alanıdır (medyan 5.111 m²). Yalnız çatıdan görünen hasarı yakalar. AOI çalışma alanının yalnız bir kısmını kapsar (72/87 mahalle yeterli). %90'ı "görünür hasar yok"tur. |
| OpenStreetMap tarihli kesitleri | Haritalama durumu | Fiziksel gözlem tarihi değildir. 2022 sonunda Malatya çok az haritalanmıştı; şubat 2023'teki toplu haritalama kampanyası, 2022→2023 OSM farkını fiziksel değişimden çok haritalama artışına çevirir. Yeni yapılar geç çizilir; 2026'daki yeni yapılaşma eksik ölçülür. Kesitlerde 16 yinelenen ayak izi vardır. |
| Sentinel-2 L2A (10 m) | Yüzey yansıtımı farkı | Çoğu bina birkaç karışık pikseldir. Mevsim, güneş açısı, nem ve kar farkları değişim gibi görünür. Bulut/gölge maskesi kusursuz değildir (24 Şubat 2023 sahnesinde AOI'nin %19'u maskeli). |
| Mahalle sınırları (OSM) | Analiz birimi | Tarihsel idari sınır kanıtı değildir. 1 m tolerans dışında örtüşme yoktur, ama sınırlar resmî değildir. |
| İlçe sınırları (geoBoundaries ADM2) | Battalgazi / Yeşilyurt ataması | 2021 sürümüdür. Mahallelerin %99,8'inden fazlası tek ilçede kalır. |
| Esri World Imagery altlığı | Görsel bağlam | Çekim tarihi belirsizdir; analizde kullanılmaz, kanıt değildir. |

## 2. Yöntem kaynaklı belirsizlikler

- **Bire bir eşleştirme (00-18/00-19):** IoU ≥ 0,5 ve iki yönde tek aday şartı temkinlidir.
  Bölünen veya birleşen ayak izleri "belirsiz" kalır. Bu yüzden kaldırılan yapı payı
  dönüşümü olduğundan az gösterebilir. Örneğin Dabakhane'de 185 bina 38'e iner, ama
  kaldırılan payı %5,9'dur. Net OSM bina kaybı (00-20) bunu tamamlar. Eşik duyarlılığı
  (0,3/0,5/0,7) kaldırılan/yeni sayılarını değiştirmez, değişmiş/belirsiz ayrımını değiştirir.
- **Spektral eşikler (00-18/00-19):** Saha etiketiyle kalibre edilmemiş tarama kurallarıdır.
  00-18'de −0,1 yansıtım offseti eksikti; düzeltildikten sonra aday alan %2,75'ten %13'e
  çıktı. Eşikler EMSR648'e göre yeniden ayarlanmadı; bu, değerlendirmeyi değerlendirme
  verisine uydurmak olurdu.
- **Mevsim eşleştirme (00-19):** Kasım 2026 sahnesi değişmeyen binaların %50'sini "değişmiş"
  gösterdi ve reddedildi. Mart 2026 sahnesiyle bu oran %25,7'ye indi, ama sıfır değildir.
- **Mahalle ölçeği (00-20):** Sonuçlar değiştirilebilir alansal birim sorununa (MAUP) ve
  komşuluk tanımına bağlıdır. 87 eşzamanlı yerel test yanlış pozitif üretebilir. Doğrulayıcı
  ifadeler Benjamini–Hochberg FDR bayrağına dayanmalıdır.
- **Atama:** Bina düzeyindeki katmanlar mahalleye temsilî noktayla atanır. 19 EMSR648
  poligonu hiçbir mahalleye düşmez.
- **Korelasyonlar:** Spearman ρ kaynaklar arası uyumu anlatır; nedensellik değildir.

## 3. Model belirsizliği

- Bina düzeyi model yalnız geometriyi kullanır: alan, çevre, şekil indeksi. Zemin, yapı yaşı,
  kat sayısı, taşıyıcı sistem ve yer hareketi bilgisi yoktur.
- Mekânsal testte (1 km gruplar) random forest doğruluğu 0,91, macro-F1'i 0,24'tür. Bu, sabit
  tahmin yapan dummy modelle aynı düzeydir. Karışıklık matrisine göre hasarlı, olası hasarlı
  ve yıkılmış sınıflarının hiçbiri doğru bulunmaz.
- Olasılıklar kalibre edilmemiştir. 0,6 altı güven "düşük güven" olarak işaretlenir (3.617
  tahminin 171'i).
- 00-17 tahminleri modelin eğitildiği EMSR648 poligonları üzerindedir. EMSR648 ile uyumları
  (ρ = 0,93) örneklem içidir ve doğrulama değildir.

## 4. Kullanım sınırı

Bu proje araştırma amaçlıdır. Hiçbir çıktı bina güvenliği, tahliye, güçlendirme, yıkım veya
resmî hasar kararı için kullanılamaz. Operasyonel kullanım, yetkin inşaat ve deprem
mühendislerinin bağımsız doğrulamasını gerektirir.

## 5. Atıflar

- Hasar kayıtları: T.C. Çevre, Şehircilik ve İklim Değişikliği Bakanlığı hasar tespit
  listeleri (PDF), işlenmiş biçimde.
- Copernicus Emergency Management Service, EMSR648 AOI05 grading product, r1 v1.
  <https://mapping.emergency.copernicus.eu/activations/EMSR648/>
- © OpenStreetMap katkıcıları, ODbL 1.0, Overpass API attic sorguları.
- Contains modified Copernicus Sentinel data 2022–2026; Earth Search STAC kamu COG arşivi.
- geoBoundaries (gbOpen TUR ADM2), ODbL.
- Uydu altlığı: Esri, Maxar, Earthstar Geographics, and the GIS User Community.
