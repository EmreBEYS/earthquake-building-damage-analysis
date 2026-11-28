# Sprint 00-23 — Raporlama ve indirme sistemi

Durum: **Tamamlandı.** Teslim `src/earthquake_damage/reporting.py`. Dashboard'da
**Rapor & İndirme** sayfasındadır.

## Çalıştırma

```bash
uv run python scripts/22_generate_reports.py                       # model + veri kalitesi
uv run python scripts/22_generate_reports.py --neighborhood "Dabakhane Mahallesi"
uv run python -m streamlit run dashboard.py                        # Rapor & İndirme
```

## Rapor türleri

| Rapor | İçerik |
|---|---|
| Mahalle analiz raporu | İlçe ve alan; resmî kayıt, ağır hasar oranı/yoğunluğu ve sırası; EMSR648 ve model payları; OSM 2023/2026; kaldırılan pay ve net kayıp; yeni yapı; spektral değişim; Gi*/LISA sınıfları. Ek olarak 87 mahalle medyanıyla karşılaştırma, mahalledeki EMSR648 poligonları, sınıf grafiği ve konum haritası. |
| Yapı alanı raporu | Bir EMSR648 poligonu: sınıf, model tahmini, güven ve olasılıklar; içindeki 2023 OSM binaları ve kaldırılan/yeni sayıları; spektral pay. Ek olarak mahalledeki sınıf dağılımı ve konum haritası. |
| Model performans raporu | 00-16 metrikleri (iki bölme, %95 GA) ve random forest için mekânsal test karışıklık matrisi. Sınıf bazında F1, sınıf dengesizliği ve 00-16 sınırlılıkları. |
| Veri kalitesi raporu | Kayıt defterindeki her veri seti için durum, satır, sütun, doluluk, yinelenen satır, geçersiz/boş/yinelenen geometri ve SHA-256. Ek olarak doğrulama raporlarının durumu. |

## Dışa aktarma

| Biçim | Ne içerir |
|---|---|
| CSV | UTF-8 BOM'lu (Excel'de Türkçe karakterler bozulmaz) uzun tablo: `Tablo, Bölüm, Alan, Değer` |
| Excel | Özet sayfası, her tablo için bir sayfa ve Notlar sayfası; sütun genişlikleri ayarlı |
| PNG | Raporun herhangi bir grafiği, 150 dpi |
| PDF | A4: kapak ve özet, sayfalara bölünmüş tablolar, grafikler, notlar ve sınırlılıklar |

PNG ve PDF yalnız Matplotlib ile üretilir; tarayıcı veya Kaleido gerekmez. Excel için tek yeni
bağımlılık `openpyxl` eklendi.

## Model performansı: karışıklık matrisi

Matris, 00-16'nın kendi bölme fonksiyonuyla yeniden hesaplandı: `GroupShuffleSplit`, 1 km
ızgara, tohum 42. Kayıtlı model klonlanıp eğitim kısmında yeniden eğitildi; kayıtlı model
dosyası değişmedi. Sonuçtaki macro-F1 0,2388'dir ve 00-16 raporuyla birebir aynıdır.

| Gerçek \ Tahmin | Görünür hasar yok | Olası hasarlı | Hasarlı | Yıkılmış |
|---|---:|---:|---:|---:|
| Görünür hasar yok | 533 | 0 | 1 | 3 |
| Olası hasarlı | 13 | 0 | 0 | 0 |
| Hasarlı | 26 | 0 | 0 | 0 |
| Yıkılmış | 7 | 0 | 0 | 0 |

Model mekânsal testte hasarlı sınıfların hiçbirini doğru bulmuyor; azınlık sınıflarında F1
sıfır. %91 doğruluk tamamen çoğunluk sınıfından gelir. Rapor ve dashboard bunu açıkça yazar.
Model dosyaları depoda olmadığı için sonuç `reports/sprint_00-23/spatial_confusion_matrix.json`
olarak saklanır. Temiz klonda ve CI'da rapor bu dosyayı kullanır.

## Bu sprintte bulunan ve düzeltilen sorunlar

- **Gizlenen dönüşüm:** 00-19'un temkinli eşleştirmesi, bölünen veya birleşen ayak izlerini
  "belirsiz" bırakıp kaldırılmış saymıyor. Örneğin Dabakhane'de 185 bina 38'e iniyor ama
  kaldırılan payı %5,9 görünüyor. Bu yüzden 00-20'ye **net OSM bina kaybı** göstergesi
  eklendi (Moran's I 0,43; 10 FDR sıcak noktası). Ana sayfanın 2026 haritası ve raporlar artık
  bunu kullanıyor.
- **Yinelenen geometriler:** veri kalitesi raporu yeniden yapılanma haritasında 847 yinelenen
  geometri buldu. Bunlar tasarım gereğidir: kabul edilmeyen eşleşmelerde 2023 ve 2026 tarafları
  ayrı belirsiz birimlerdir. Rapor notunda açıklanır. 2023 OSM kesitindeki 16 yinelenen ayak
  izi OSM'nin kendisindendir.
- **Eksik değer:** pandas 3 metin sütunlarında eksik değerler PDF/CSV üretimini bozuyordu;
  hepsi "—" olarak yazılır.
- **Sabit sütunlar:** Spearman, sabit sütunlarda NaN döndürür; numpy uyarısı vermez.

## Çıktılar

`reports/sprint_00-23/`:

- `model_performance_report.{pdf,xlsx,csv}` ve grafik PNG'leri
- `data_quality_report.{pdf,xlsx,csv}` ve grafik PNG'si
- `spatial_confusion_matrix.json`

## Testler

- `tests/test_reporting.py`: biçimlendirme, dört dışa aktarıcının geçerli dosya üretmesi, mahalle
  raporu değerlerinin tabloyla tutarlılığı, macro-F1'in yeniden üretimi, model dosyası yokken
  önbelleğin kullanılması, veri kalitesi kapsamı.
- `tests/test_dashboard_app.py`: dört rapor türü sayfada hatasız üretilir.
