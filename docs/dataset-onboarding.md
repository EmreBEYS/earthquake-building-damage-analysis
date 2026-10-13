# Yeni veri seti ekleme sözleşmesi

Bu yapı ham kaynakları değiştirmeden, her veri setini tekrar üretilebilir bir ara katmana
dönüştürmek için kullanılır.

## Klasörler

```text
data/interim/
├── buildings/       # bina ayak izleri ve hasar etiketleri
├── earthquakes/     # deprem katalogları ve olay öznitelikleri
├── boundaries/      # idari/AOI sınırları
├── population/      # nüfus ve maruziyet verileri
└── imagery/         # uydu görüntüsü indeksleri ve türetilmiş özellikler
data/processed/
└── training/        # mekânsal olarak ayrılmış model tabloları
```

## Her veri setinde zorunlu kayıtlar

1. Sabit ve benzersiz `dataset_id`.
2. Kaynak sağlayıcı, indirme tarihi, lisans ve kaynak checksum.
3. Kaynak CRS ve dönüştürülmüş CRS.
4. Kayıt/özellik sayısı ve geometri türleri.
5. Eksik değer, geçersiz geometri ve aykırı değer sayıları.
6. Ham dosyayı değiştirmeyen tekrar üretilebilir hazırlama betiği.
7. Çıktı checksumlarını içeren manifest.

## Birleştirme kuralları

- Bina verileri doğrudan satır numarasıyla birleştirilmez; kararlı özellik kimliği veya
  belgelenmiş mekânsal eşleştirme kullanılır.
- Eğitim/test ayrımı rastgele bina bazında yapılmaz. Yakın binaların iki tarafa sızmasını
  önlemek için mekânsal blok veya bölge bazlı ayrım kullanılır.
- `Possibly damaged` sınıfının ikili etikette hasarlı gruba dahil edildiği açıkça kaydedilir.
- Uydu görüntüleri tarih, bulut/gölge ve kapsama açısından doğrulanmadan model girdisi sayılmaz.
- Alan ve mesafe hesapları WGS 84 dereceleri üzerinde değil, `EPSG:32637` gibi metrik CRS'de
  gerçekleştirilir.

## Mevcut CEMS katmanı

`cems_emsr648_aoi05_builtupa_2023`, 3.619 özellik içeren ilk hazırlanmış veri setidir.
Kaynak Shapefile geometrileri korunmuş, proje etiketleri eklenmiş ve 1 m² altındaki 11 geometri
silinmeden `geometry_review_flag=tiny_under_1m2` olarak işaretlenmiştir.
