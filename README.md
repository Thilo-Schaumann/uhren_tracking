# Uhren-Tracker

Tägliche Datenbank zu Uhrenmodellen über mehrere Online-Händler, um Verweildauer
(Zeit bis verkauft) und Preiskorridore über Zeit auszuwerten.

## Quellen

| Quelle | Methode |
|---|---|
| Grimmeissen (grimmeissen.de) | Statisches HTML, Listing + Detailseite je Uhr (Referenznummer) |
| Rothfuss Watch Boutique (rothfuss-watches.de) | Shopify `/collections/alle-uhren/products.json` |
| Cologne Watch (colognewatch.de) | Shopify `/collections/herrenuhren/products.json` |

Ein Angebot gilt als verkauft, sobald es in einem täglichen Lauf nicht mehr
auftaucht bzw. bei Shopify `available: false` wird.

## Nutzung

```bash
pip install -r requirements.txt
python run.py
```

Legt/aktualisiert `watches.db` (SQLite) mit drei Tabellen:

- `listings` (brand, model, model_line, reference_number, condition, year, has_papers,
  has_box, band_material, dial_color, image_url, seller, platform, url,
  first_seen, last_seen, status)
- `price_snapshots` (listing_id, date, price, currency)
- `favorites` (brand, model_line, reference_number, display_name, image_url, added_at) —
  frei anlegbare Merkliste, unabhängig davon ob gerade ein Angebot existiert

Datenqualität pro Feld ist je Quelle unterschiedlich: Grimmeissen liefert
condition/year/papers/box/band/dial strukturiert von der Detailseite.
Rothfuss und Cologne Watch liefern diese Felder nur best-effort per Regex aus
Titel/Beschreibung (Cologne Watch am unzuverlässigsten, v.a. bei `condition`).

## Automatisierung

`.github/workflows/daily.yml` läuft täglich um 06:00 UTC, aktualisiert
`watches.db` und committet die Änderung zurück ins Repo.
