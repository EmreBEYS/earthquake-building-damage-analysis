# Sprint 00-21 — Yeni Streamlit dashboard

Durum: **Tamamlandı.** `dashboard.py` koyu tema, sol menü, KPI kartları, dönem seçimi ve veri
kaynağı göstergeleriyle yeniden tasarlandı. Örnek tasarımdaki düzen izlendi, ama **örnekteki
sayılar kullanılmadı**: ana sayfadaki her değer depodaki çıktılardan hesaplanır.

## Çalıştırma

```bash
uv run python scripts/20_prepare_dashboard_overview.py   # mahalle → ilçe tablosu (bir kez)
uv run python -m streamlit run dashboard.py
```

Windows'ta `uv run streamlit` "uv trampoline" hatası verebilir; `python -m streamlit` kullanın.

## Tasarım

- **Tema:** `.streamlit/config.toml` koyu temeli tanımlar (arka plan `#0B1220`, yüzey `#111A2E`,
  vurgu `#2F6FDE`). `src/earthquake_damage/ui/theme.py` kartları, menüyü ve rozetleri biçimler.
- **Üst bant:** başlık, alt başlık, dönem seçimi (2022 deprem öncesi / 2023 deprem sonrası /
  2026 güncel) ve "Proje hakkında" penceresi.
- **Sol menü:** Ana Sayfa, Harita Analizi, Model Tahmini, Veri Setleri, İstatistikler,
  Karşılaştırma ve Yöntem. Önceki sprintlerin 13 sayfası bu başlıkların altında alt sekmelerdir;
  içerikleri korunmuştur.
- **Ana Sayfa:**
  - KPI kartları: resmî kayıt toplamı (46.563) ve altı resmî hasar sınıfının sayısı ve payı.
  - Mahalle haritası: Esri uydu altlığı üzerinde. Dönem seçimine göre değişir:
    - 2022: 2022→2023 spektral değişim payı
    - 2023: resmî ağır hasar oranı
    - 2026: 2023→2026 kaldırılan yapı payı
  - Hasar sınıfı halka grafiği ve ilçelere göre dağılım.
  - 2023/2026 bina sayılarıyla zaman içinde değişim.
  - Mekânsal doğrulamalı model performansı.
- **Model performansı dürüst gösterilir:** random forest mekânsal testte doğruluk 0,91,
  macro-F1 0,24 alır. Bu, sabit tahmin yapan dummy modelle aynı düzeydir ve kartta açıkça
  yazılır. Örnek tasarımdaki 0,87/0,84/0,82 gibi değerler bu projenin sonucu değildir.
- **Veri kaynağı göstergeleri:** her sayfanın başında okuduğu veri setleri rozet olarak
  görünür. Yeşil: depoda; sarı: yalnız yerel, Git dışında; kırmızı: eksik. Üzerine gelince rol,
  koşullar ve sprint görünür. "Veri Setleri → Veri kaynakları" tam tabloyu verir: durum, boyut,
  güncelleme tarihi, koşullar, dosya.
- **Duyarlı yerleşim:** KPI ızgarası `auto-fit` ile sarar. 760 px altında iki sütuna iner,
  başlık küçülür, kenar boşlukları daralır. Streamlit sütunları dar ekranda alt alta dizilir.
- **Harita altyapısı:** tüm haritalar Plotly'nin MapLibre tabanlı `Choroplethmap` izine taşındı;
  kullanımdan kalkan `Choroplethmapbox` ve `use_container_width` uyarıları giderildi.

## Mahalle → ilçe eşleşmesi

İlçe grafiği için 87 mahalle, sabitlenmiş geoBoundaries ADM2 poligonlarına (Battalgazi
`54988432B75263721717029`, Yeşilyurt `54988432B29488154081251`) EPSG:32637'de en büyük kesişim
alanıyla atanır. Sonuç: 47 Battalgazi, 40 Yeşilyurt. En düşük kesişim payı %99,79'dur.
Çıktı `data/dashboard/sprint_00-21/neighborhood_districts.csv`, yöntem ve kaynak bilgisi yan
dosyadadır.

## Testler

- `tests/test_dashboard_app.py` tüm 14 sayfayı ve üç dönemi Streamlit AppTest ile açar. Ana
  sayfadaki 46.563 değerinin veri dosyasından geldiğini doğrular.
- `tests/test_ui_overview.py` sınıf toplamlarını, ilçe atamasını, kaynak kayıt defterini, Türkçe
  sayı biçimini ve HTML kaçışlarını sınar.

## Sınırlılıklar

- Görsel kontrol bu oturumda tarayıcıda yapılamadı. İşlevsel doğrulama AppTest iledir; renk ve
  yerleşim gözle kontrol edilmelidir (00-24 demo testi).
- Uydu altlığı (Esri World Imagery) görsel bağlamdır; hasar kanıtı değildir.
