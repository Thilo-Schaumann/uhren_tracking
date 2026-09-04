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

## Projektstruktur

- `run.py`, `db.py`, `scrapers/` — täglicher Scrape-Lauf (Kern)
- `data/` — `watches.db` + Stammdaten (`model_variants.json`, `brand_logos.json`,
  `official_prices.json`, `cluster_specs_*.json` — ein File pro recherchierter
  Marke); `thumbnails_cache.json` und `backup/` sind generiert (git-ignoriert)
- `scripts/` — Dashboard-Build (`export_dashboard_data.py`, `build_dashboard.py`,
  `dashboard_template.html`) und Pflege-Skripte (`fetch_thumbnails.py`,
  `fetch_brand_logos.py`, `fetch_ap_prices.py`, `backup_data.py`)

Alle Skripte werden vom Projekt-Root aus aufgerufen (`python3 scripts/…`), nicht
aus dem `scripts/`-Ordner heraus.

## Nutzung

```bash
pip install -r requirements.txt
python run.py
```

Legt/aktualisiert `data/watches.db` (SQLite) mit drei Tabellen:

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

## Modell-Cluster

Eine Modelllinie (z.B. "GMT-Master II") ist keine sinnvolle Vergleichseinheit —
Stahl/Keramik/Oyster- und Weißgold/Jubilee-Varianten sind völlig
unterschiedliche, nicht vergleichbare Uhren. `data/cluster_specs_*.json`
enthält recherchierte Gehäuse-/Lünette-/Armband-Spezifikationen pro
Referenznummer (18 Marken, siehe Git-Historie für den Recherchestand).
`scripts/export_dashboard_data.py` fasst Modelllinie + diese Spezifikation zu
einem Cluster-Label zusammen (z.B. "GMT-Master II Edelstahl/Keramik/Oyster"),
das im Dashboard als eigene Kachel erscheint. Referenzen ohne recherchierte
Spezifikation fallen auf die bloße Modelllinie zurück.

## Automatisierung

`.github/workflows/daily.yml` läuft täglich um 05:00 CEST, aktualisiert
`data/watches.db` und committet die Änderung zurück ins Repo.

Ein wöchentlicher lokaler Task (Sonntag 18:00) sichert `data/watches.db` +
Stammdaten sowie CSV-Exports jeder Tabelle nach `data/backup/` — unabhängig
von Git, reine Dateikopie.
