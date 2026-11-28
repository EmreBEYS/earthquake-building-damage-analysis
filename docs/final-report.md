# Final raporu — V4

**Malatya Deprem Projesi: Açık coğrafi veriler ile bina hasar seviyelerinin makine öğrenmesiyle
tahmini ve 2022–2026 kentsel dönüşüm analizi**

Sürüm V4 · Sprint 00-24 · 28 Kasım 2026

## Özet

6 Şubat 2023 depremlerinden sonra Malatya'nın Battalgazi ve Yeşilyurt ilçelerinde, 87 mahallede
(207 km²) bina hasarı ve kent dönüşümü açık ve tekrar üretilebilir verilerle incelendi. Dört
bağımsız kaynak birbirine dönüştürülmeden yan yana konuldu:

- 46.563 Bakanlık hasar tespit kaydı
- Copernicus EMSR648 hasar haritası (3.617 yapı alanı)
- OpenStreetMap'in 2022, 2023 ve 2026 tarihli bina kesitleri
- Sentinel-2 uydu görüntüleri

Başlıca bulgular:

1. **Hasar mekânsal olarak kümelenir.** Resmî ağır hasar oranında Moran's I 0,49'dur
   (p = 0,001). FDR ile doğrulanmış sıcak noktalar tarihî merkezde bitişik bir çekirdek
   oluşturur: Dabakhane, İsmetiye, Kavaklıbağ, Yenihamam, Cirikpınar ve Salköprü.
2. **Hasar, sonraki yıkımla uyumludur.** Resmî ağır hasar oranı yüksek mahallelerde 2023–2026
   arasında daha çok bina kaybolmuştur (Spearman ρ = 0,62). EMSR648'de "yıkılmış" poligonlardaki
   OSM binalarının %29'u 2026'ya kadar kaldırılmıştır; "hasar yok" olanlarda bu oran %5'tir.
3. **Net bina kaybı aynı merkezde toplanır.** Moran's I 0,43'tür ve 10 FDR sıcak noktası vardır.
   Çalışma alanındaki OSM ayak izi sayısı 49.842'den 47.043'e iner. 2.414 yapı kaldırılmış,
   166 yapı yeni aday olarak bulunur; yeni yapılaşma OSM'de eksik ölçülür.
4. **Yalnız geometriyle bina düzeyi hasar tahmini başarısızdır.** Random forest mekânsal testte
   %91 doğruluk alır, ama macro-F1'i 0,24'tür ve dummy modelle aynıdır. Hiçbir hasar sınıfını
   doğru bulmaz. Bu dürüst bir negatif sonuçtur ve gerekçesi belgelenmiştir.

## 1. Amaç ve araştırma soruları

- Hasar şiddeti mahalleler arasında nasıl dağılır ve kümelenir mi?
- Resmî kayıtlar, uydu tabanlı hasar haritası ve model tahmini ne ölçüde uyuşur?
- Depremden bu yana fiziksel kent dönüşümü nerede ve ne ölçüde gerçekleşti?
- Resmî tespitten bağımsız, açık verilerle bina düzeyinde hasar tahmin edilebilir mi?

## 2. Veri

| Kaynak | Kapsam | Sprint |
|---|---|---|
| Bakanlık hasar tespit PDF'leri | 87 PDF → 46.563 kayıt, 6 sınıf | 00-08/09/15 |
| Copernicus EMSR648 AOI05 | 3.617 yapı alanı poligonu, 4 sınıf | 00-12/14 |
| OSM bina kesitleri (Overpass attic) | 2023-02-24: 60.598 · 2026-07-27: 57.468 · 2022-12-31: indiriliyor | 00-18/19 |
| Sentinel-2 L2A | 2022-12-31, 2023-02-24, 2026-03-05 | 00-13/18/19 |
| Mahalle ve ilçe sınırları | 87 mahalle (OSM), 2 ilçe (geoBoundaries) | 00-12/21 |

Resmî hasar sınıflarının dağılımı:

| Sınıf | Kayıt | Pay |
|---|---:|---:|
| Hasarsız | 10.131 | %21,8 |
| Az hasarlı | 20.706 | %44,5 |
| Orta hasarlı | 1.593 | %3,4 |
| Ağır hasarlı | 12.276 | %26,4 |
| Acil yıkılacak | 955 | %2,1 |
| Yıkık | 902 | %1,9 |

Ayrıntılar ve lisanslar: [`data-sources.md`](data-sources.md), `data/inventory.csv`.

## 3. Yöntem (aşamalar)

**Aşama 1 — Veri hattı (00-01…00-15).**

- PDF çıkarımı ve doğrulama
- Mahalle eşleştirmesi
- EMSR648 ve OSM katmanlarının denetimi
- Sentinel-2 edinimi
- Metrik geometri özellikleri (EPSG:32637)
- Resmî ve uydu kaynaklı hasarın ayrı katmanlarda gösterimi

**Aşama 2 — Makine öğrenmesi ve zamansal analiz (00-16…00-20).**

- **00-16:** Kayıtlı modellerin rastgele tabakalı ve 1 km mekânsal gruplu testle yeniden
  değerlendirilmesi; sızıntı ve sınıf dengesizliği denetimi.
- **00-17:** Bina düzeyi tahmin katmanı (3.617 poligon, 171 düşük güven).
- **00-18:** 2022→2023 Sentinel-2 spektral değişim taraması, ofset düzeltmeli.
- **00-19:** 2023→2026 tarihli OSM ayak izlerinin IoU ile bire bir eşleştirilmesi ve mevsim
  eşli Sentinel-2 kanıtı.
- **00-20:** Mahalle karşılaştırma tablosu; queen komşulukla Moran's I, LISA ve Getis-Ord Gi*;
  999 permütasyon ve FDR.

**Aşama 3 — Arayüz, doğrulama ve teslim (00-21…00-24).**

- **00-21:** Koyu temalı dashboard; KPI'lar depodaki çıktılardan hesaplanır.
- **00-22:** İnteraktif harita, dönem seçimi, yan yana karşılaştırma ve bina paneli.
- **00-23:** Raporlama: CSV, Excel, PNG ve PDF.
- **00-24:** CBS kalite testleri, sınırlılıklar ve demo.

## 4. Bulgular

### 4.1 Mekânsal kümelenme (87 mahalle)

| Gösterge | Moran's I | p | FDR sıcak nokta |
|---|---:|---:|---:|
| Resmî ağır hasar oranı | 0,489 | 0,001 | 6 |
| Resmî ağır hasar yoğunluğu | 0,521 | 0,001 | 9 |
| Bina yoğunluğu 2023 | 0,436 | 0,001 | 11 |
| Kaldırılan yapı payı 2023→2026 | 0,180 | 0,006 | 2 |
| Net OSM bina kaybı 2023→2026 | 0,430 | 0,001 | 10 |

### 4.2 Kaynaklar arası uyum (Spearman ρ)

| Karşılaştırma | ρ |
|---|---:|
| Resmî ağır hasar oranı ↔ net OSM bina kaybı | 0,62 |
| Resmî ağır hasar oranı ↔ kaldırılan yapı payı | 0,61 |
| Bina yoğunluğu ↔ resmî ağır hasar yoğunluğu | 0,72 |
| Resmî ağır hasar oranı ↔ EMSR648 ağır pay (72 mahalle) | 0,30 |
| Resmî ağır hasar oranı ↔ 2022→2023 spektral değişim | 0,17 |

Resmî kayıt ile EMSR648 arasındaki zayıf uyumun iki nedeni var: EMSR648 yalnız görüntüden
görülebilen hasarı ölçer ve alanın bir kısmını kapsar.

### 4.3 Kent dönüşümü 2023→2026

- OSM ayak izleri 49.842'den 47.043'e iner; taban alanı 12,68 km²'den 12,01 km²'ye düşer.
- 2.414 yapı kaldırılmış, 166 yeni, 119 değişmiş, 3.409 belirsiz olarak sınıflanır.
- Kaldırılan adayların %44'ünü, değişmeyen binaların ise %25,7'sini uydu verisi de destekler.
- En yüksek net kayıp merkezdedir: Kavaklıbağ %84, Dabakhane %79, Şıkşık %75, Akpınar %71.

### 4.4 Model performansı

| Bölme | Model | Doğruluk | Macro-F1 (%95 GA) |
|---|---|---:|---:|
| Rastgele tabakalı | Random forest | 0,901 | 0,308 (0,257–0,366) |
| Mekânsal 1 km | Random forest | 0,914 | 0,239 (0,236–0,242) |
| Mekânsal 1 km | Dummy | 0,921 | 0,240 |

Mekânsal test karışıklık matrisi: 583 test poligonundan 579'u "görünür hasar yok" olarak
tahmin edilir. Hasarlı (26), olası hasarlı (13) ve yıkılmış (7) poligonların hiçbiri doğru
sınıflanmaz. Yalnız alan, çevre ve şekil bilgisi hasarı ayırt etmeye yetmez. Zemin, yapı yaşı,
kat sayısı ve yer hareketi gibi değişkenler gerekir.

## 5. Doğrulama ve tekrar üretilebilirlik

- **Otomatik testler:** 193 test her push'ta GitHub CI'da (Ubuntu) ve yerelde (Windows 11)
  çalışır. Kapsamı:
  - istatistikler elle hesaplanmış değerlere karşı
  - uçtan uca sentetik analizler
  - 16 dashboard sayfası (AppTest)
  - dışa aktarıcılar
  - CBS kalitesi: CRS, geometri geçerliliği, Malatya sınırı, mahalle topolojisi, sprintler
    arası kimlik ve toplam tutarlılığı, sağlama değerleri
- **Sağlama:** her sprint girdi ve çıktılarının SHA-256 değerlerini rapora yazar. Testler
  depodaki dosyaların bu değerlerle eşleştiğini doğrular. `.gitattributes` satır sonu
  dönüşümünü kapatır; Windows'ta da karmalar değişmez.
- **Hata kayıtları:** başarısız çalıştırmalar `blocked.json` yazar. Sonuç üretilmiş gibi
  davranılmaz.
- **Düzeltilen hatalar:**
  - 00-18'de eksik yansıtım offseti
  - 00-19'da dosya adı hatası
  - depoda olmayan 00-17 çıktısı
  - EMSR648 poligonlarının tek bina sanılması
  - belirsiz eşleşmelerin gizlediği dönüşüm

## 6. Sınırlılıklar

Tam liste: [`limitations.md`](limitations.md). Özetle:

- Resmî kayıtlar koordinatsızdır ve isimle mahalleye bağlanır.
- OSM haritalama durumudur; 2022 kesiti çok seyrektir.
- Spektral eşikler kalibre edilmemiştir.
- Sonuçlar mahalle ölçeğine bağlıdır (MAUP).
- Model operasyonel değildir.
- **Bu çalışma resmî hasar veya bina güvenliği kararı için kullanılamaz.**

## 7. Gelecek çalışmalar

- Yer hareketi (USGS ShakeMap/AFAD), zemin sınıfı, bina yaşı ve kat sayısıyla model özelliklerini
  zenginleştirmek.
- Kaldırılan ve yeni yapı adaylarını çok yüksek çözünürlüklü görüntü veya saha örneklemesiyle
  doğrulamak ve spektral eşikleri kalibre etmek.
- Resmî kayıtları adres düzeyinde konumlandırmanın lisans ve gizlilik koşullarını araştırmak.
- Alternatif bölümlemelerle (grid, H3) MAUP duyarlılık analizi yapmak.
- 2022 OSM kesiti tamamlandığında 00-18 bina değişim analizini çalıştırmak; sonucu
  haritalama artışı olarak yorumlamak.

## 8. Demo

Kurulum, demo öncesi kontrol ve 12 dakikalık sunum akışı: [`demo.md`](demo.md).
