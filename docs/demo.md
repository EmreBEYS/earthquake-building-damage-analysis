# Demo kılavuzu (Windows ve MacBook)

## 1. Kurulum

Ortak gereksinimler: Git, Python 3.11 ve [uv](https://docs.astral.sh/uv/).

### Windows (PowerShell)

```powershell
winget install --id astral-sh.uv -e        # uv yoksa
git clone https://github.com/EmreBEYS/earthquake-building-damage-analysis.git
cd earthquake-building-damage-analysis
uv sync --locked --all-extras
uv run python scripts/demo_check.py
uv run python -m streamlit run dashboard.py
```

Windows'ta `uv run streamlit ...` "uv trampoline failed to canonicalize script path" hatası
verebilir. Bu yüzden her zaman `uv run python -m streamlit ...` kullanın. Aynı nedenle testler
de `uv run python -m pytest -q` ile çalıştırılır.

### macOS (MacBook, Apple Silicon veya Intel)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv yoksa; ya da: brew install uv
git clone https://github.com/EmreBEYS/earthquake-building-damage-analysis.git
cd earthquake-building-damage-analysis
uv sync --locked --all-extras
uv run python scripts/demo_check.py
uv run python -m streamlit run dashboard.py
```

`geopandas`, `pyogrio`, `rasterio` ve `shapely` macOS arm64 için hazır derlenmiş paketlerle
gelir; ek sistem kütüphanesi gerekmez. Tarayıcı otomatik açılmazsa <http://localhost:8501>
adresine gidin.

## 2. Demo öncesi kontrol

`scripts/demo_check.py` şunları denetler:

- Python sürümü
- 11 zorunlu paket
- 12 zorunlu veri dosyası
- yerel OSM katmanları (isteğe bağlı)
- dashboard'un derlenip derlenmediği
- 8501 portunun boş olup olmadığı

Çıktının sonunda o sistem için doğru başlatma komutu yazar. Port doluysa
`--server.port 8502` ekler. Çıkış kodu 0 ise demo çalışır.

**Temiz klonda ne değişir:** `data/external/` altındaki OSM kesitleri Git'te yoktur.
Dashboard bunlarsız da açılır; yalnız "OSM binaları 2022/2023/2026" harita katmanları "yerel
OSM kesiti yok" notu gösterir. Bu katmanları da göstermek için 00-19 edinimini çalıştırın:
`uv run python scripts/18_analyze_reconstruction_change.py acquire`. Overpass yoğunsa bu saatler
sürebilir.

## 3. Önerilen sunum akışı (≈ 12 dakika)

1. **Ana Sayfa (2 dk):**
   - 46.563 resmî kayıt ve altı sınıfın payları.
   - Dönem seçici 2023'te: resmî ağır hasar oranı haritası.
   - İlçe dağılımı.
2. **Dönem değişimi (1 dk):** üst bantta 2026'ya geçin. Net OSM bina kaybı haritası merkezde
   yoğunlaşır.
3. **Harita Analizi → İnteraktif Harita (3 dk):**
   - Mahalle odağı: Dabakhane Mahallesi.
   - EMSR648 katmanını açın ve bir poligona tıklayın; bina panelinde sınıf, tahmin, olasılıklar
     ve 2026 durumu görünür.
   - "Yan yana karşılaştırma → Dönemler" ile 2023 ve 2026'yı yan yana gösterin.
4. **İstatistikler → Mekânsal Analiz (2 dk):**
   - "Gi* sıcak nokta" gösterimini açın; FDR filtresini işaretleyin.
   - Merkez çekirdeği gösterin.
   - Spearman tablosunda hasar ile kayıp arasındaki ρ ≈ 0,6'yı gösterin.
5. **Model Tahmini → Model performansı (2 dk):** doğruluk 0,91 ama macro-F1 dummy ile aynı.
   Rapor & İndirme → Model performans raporu altında karışıklık matrisini gösterin: azınlık
   sınıfları hiç bulunamıyor. Bu, dürüst bir negatif sonuçtur.
6. **Rapor & İndirme (1 dk):** Dabakhane için mahalle raporunu PDF ve Excel olarak indirin.
7. **Sınırlılıklar (1 dk):** [`limitations.md`](limitations.md) özetini anlatın.

## 4. Demo testi kontrol listesi

| Adım | Windows 11 (geliştirme) | MacBook (demo) |
|---|---|---|
| `uv sync --locked --all-extras` | ✅ | ☐ |
| `scripts/demo_check.py` "Demo hazır" | ✅ | ☐ |
| `python -m pytest -q` tamamı geçer | ✅ | ☐ |
| Dashboard açılır, 16 sayfa hatasız | ✅ AppTest + gözle (ana sayfa, harita, rapor) | ☐ gözle |
| Dönem seçici 2022/2023/2026 | ✅ AppTest | ☐ gözle |
| İnteraktif harita: tıklama → bina paneli | ✅ fare ile ve AppTest | ☐ fare ile |
| PDF/Excel/CSV/PNG indirme | ✅ birim testi | ☐ tarayıcıdan |
| Koyu tema (1440 px) | ✅ gözle | ☐ gözle |
| Dar ekran yerleşimi | ☐ gözle | ☐ gözle |

Windows sütunu bu depoda otomatik testlerle doğrulandı. Gözle yapılacak kontroller ve
MacBook sütunu demo öncesinde elle işaretlenmelidir.
