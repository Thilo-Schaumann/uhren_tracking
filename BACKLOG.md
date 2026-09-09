# Uhren-Tracker – Backlog & Entscheidungen

Lebendes Dokument. Wird von Claude bei jeder neuen Anforderung aktualisiert —
neue Wünsche werden unter "Offen" ergänzt, erledigte Punkte wandern nach
"Erledigt", und wenn sich eine frühere Entscheidung ändert, wird das unter
"Entscheidungen" korrigiert (nicht stillschweigend überschrieben).

## Erledigt

**Rolex Zifferblatt-/Lünettenfarben-Pilot (2026-09-09)**
- Ursprünglich als Bilderkennungs-Pilot geplant — stattdessen entschieden
  (Nutzerwunsch): keine automatische Bilderkennung, sondern Claude zeigt die
  Fotos, der Nutzer bestimmt die Farbe selbst. Kein Bilderkennungs-Kosten
  anfall damit; die eigentliche Arbeit war Text-/Referenz-Recherche
- 63 aktive Rolex Submariner/GMT-Master II/Daytona-Angebote geprüft, 42
  einzigartige Referenzen. Für ~20 Referenzen (Hulk, Batman, Pepsi, Kermit,
  Sprite, Root Beer etc.) ist Zifferblatt-/Lünettenfarbe technisch fix und
  per Fachwissen bestimmbar → `data/color_variants_rolex.json`
  (Referenz-Ebene, `color_source: "text"`)
- Für 8 Angebote, bei denen die Farbe genuin von Uhr zu Uhr variiert (nicht
  aus der Referenz ableitbar), hat der Nutzer die zugeschickten Fotos
  geprüft und die Farbe bestimmt → `data/color_overrides_listings.json`
  (Angebots-Ebene, `color_source: "user"`, höchste Priorität)
- Referenz "55130" (ein Angebot) bewusst freigelassen — weder Nutzer noch
  Text-Recherche konnten sie sicher zuordnen (vintage, vermutlich 1970er)
- Dabei zwei echte Fehlextraktionen gefunden und korrigiert: Referenz
  116610LV ("Hulk") hatte "Blau" aus "blaue Leuchtmasse" statt dem
  tatsächlich grünen Zifferblatt; GMT-Master 16700 hatte "Weiß" aus
  "Weißgold-Indizes" statt dem tatsächlich schwarzen Zifferblatt
  (Referenz-Extraktion generell etwas störanfällig für Farbwörter, die
  Nebensächliches statt das Zifferblatt beschreiben — nicht systematisch
  behoben, nur die konkret gefundenen Fälle)
- Neue Dashboard-Spalte **"Quelle"** zeigt pro Zeile 📝 Text / 👁
  Nutzer-Check / 📷 Bild — Nachvollziehbarkeit wie vom Nutzer gefordert
- Neuer Filter "Lünettenfarbe" (getrennt von "Lünette" = Material)
- Referenz-Extraktions-Regex zweimal weiter nachgeschärft: Buchstaben-Suffix
  war bei 3 Zeichen gedeckelt (verschluckte 4-stellige Suffixe wie "BLNR"
  komplett), und Jahrzehnts-Angaben wie "1980er" rutschten am Jahres-Filter
  vorbei durch — beide Fixes wirken markenübergreifend, nicht nur bei Rolex

**Datenqualitäts-Fixes (2026-09-09)**
- Referenz-Extraktion war bei 7+-stelligen Nummern komplett blind (Regex kappte
  bei 6 Ziffern) und Shopify-Scraper (Rothfuss/Cologne Watch) durchsuchten nur
  den Titel, nicht die Beschreibung — behoben in `scrapers/reference.py` +
  `scrapers/shopify.py`. Fixt u.a. 6 Omega-Angebote, bei denen statt der
  echten Referenz ein Kaliber-/Kollektionsname (321, 300M, 300) gespeichert war
- `scrapers/model_line.py`: "Clé" zu Cartier ergänzt, neue Einträge für
  "Heuer" (Montreal, Monaco, Autavia, Camaro) und "Glashütte Original"
  (Senator Karrée/Excellence, Pano-Familie) — vorher fiel model_line dort auf
  den rohen, oft langen Scraper-Titel zurück
- Neuer Mechanismus `scrapers/overrides.py` + `data/manual_overrides.json`
  für Fälle, die keine Regel lösen kann (Vendor-Fehletikettierung, Ersatzteile
  statt komplette Uhren) — wird in `run.py` auf jeden Scrape angewendet, bleibt
  also auch nach künftigen Läufen bestehen. Aktuell 5 Einträge:
  - Rolex "Explorer II" 116610 → korrigiert zu Submariner (Vendor-Beschreibung:
    "Explorer II Orange von Bamford" — ein Bamford-Umbau, 116610 ist eine
    echte Submariner-Referenz)
  - Cartier "Ballon Bleu" 3803 → korrigiert zu Clé (Referenz 3803 ist
    dokumentiert als Cartier Clé, Roségold, Brillant-Lünette, ~32mm)
  - Glashütte Original "1845" → Referenznummer auf null gesetzt (ist das
    Gründungsjahr in der Modellbezeichnung, keine echte Referenz — kein
    echter Code irgendwo im Text auffindbar, daher Lücke statt Rateversuch)
  - 2x Rolex-Ersatzteile ausgeschlossen ("Zifferblatt Sternenhimmel" =
    Daydate-Ersatzzifferblatt, "Oysterband" = Ersatzarmband für Ref. 16613) —
    waren keine kompletten Uhren, sondern einzelne Ersatzteile

**Kern-Infrastruktur**
- 3 Scraper: Grimmeissen (crawlt alle 51 Marken-Seiten — `/de/uhren` zeigt nur
  die ~35 neuesten, nicht den vollen Katalog), Rothfuss + Cologne Watch
  (store-weites `/products.json`, nicht die kuratierte Collection — beide
  Shops hatten dort echte, verfügbare Uhren fehlen)
- SQLite-Schema: `listings`, `price_snapshots`, `favorites`
- Tägliche GitHub Action (05:00 CEST) scraped und committet `data/watches.db`
- Wöchentliches Backup (Sonntag 18:00, lokaler Scheduled Task) kopiert
  `watches.db` + Stammdaten nach `data/backup/`, inkl. CSV-Export jeder
  Tabelle — reine Dateikopie, kein Git
- Ordnerstruktur: `data/` (Daten + Stammdaten), `scripts/` (Build + Pflege),
  Root (Kern-Pipeline: `run.py`, `db.py`, `scrapers/`)
- Vendor-Fehletikettierungen korrigiert: Cologne Watch/Rothfuss trugen sich
  teils selbst als "Marke" ein; "Martini Racing" war eigentlich Porsche Design

**Dashboard**
- Seite 1 Favoriten: Kacheln für Modell- und Marken-Favoriten,
  "+ Favorit hinzufügen"-Formular für nicht gelistete Uhren, Top-10-Chart
  (zählt nach Cluster, über alle Zeit — aktiv + verkauft)
- Seite 2 Marken: Marken-Kacheln (Logo-dominant) → Klick → Marke-Modelle-Seite
  (eine Kachel je Cluster) → Klick → **eigene Subseite** mit Balkendiagramm +
  Referenzliste (kein Inline-Aufklappen)
- Seite 3 Tabelle: durchsuchbar, sortierbar, Spalten inkl. Gehäuse-/
  Lünettenmaterial, Komplikation, Papiere/Box, Angebot-Link
- **Komplikation als SSOT-Feld**: `listings.complication` (neue Spalte),
  befüllt für alle aktiven Angebote — Grimmeissen aus dem strukturierten
  "Funktionen"-Feld, Rothfuss/Cologne Watch per Stichwortsuche im Freitext
  (Chronograph/GMT/Tourbillon/Mondphase/Ewiger Kalender/etc., Liste in
  `scrapers/specs.py::COMPLICATIONS`)
- **Alle Filter aus der Diskussion umgesetzt**, auf Marken-/Modell-Ansicht UND
  Tabelle: Modellfamilie (rohe Modelllinie vor Cluster-Bildung, damit z.B.
  "Royal Oak" markenübergreifend über alle Materialvarianten gefiltert werden
  kann), Gehäusematerial, Lünettenmaterial, Armbandtyp, Zifferblattfarbe,
  Zustand, Komplikation, Papiere (ja/nein), Box (ja/nein); Preisspanne
  (<10k/10-25k/25-50k/50-100k/>100k) nur auf der Tabelle (Cluster-Kacheln
  zeigen ohnehin schon eine Preisspanne, ein einzelner Bucket pro Kachel wäre
  nicht sinnvoll). Auf Cluster-Ebene (Marken-Seite) wird pro Filterfeld der
  erste bekannte Wert innerhalb des Clusters als Repräsentant verwendet
- Favoriten persistieren live über die `db`-Capability der Artifact-Seite
  (nicht in `watches.db` — siehe Entscheidungen)
- Balkendiagramme: adaptive Preisskala (nice-rounded Schritte), Balken sind
  echte `<a>`-Links (öffnen Angebot im neuen Tab), schwarze Linie für
  Herstellerpreis wenn recherchiert vorhanden
- Cluster-Bildung: Modelllinie + Gehäuse-/Lünette-/Armband-Spezifikation →
  eigene Kachel/Vergleichseinheit (z.B. "GMT-Master II Edelstahl/Keramik/Oyster")
- Mobile: Touch-Ziele der Sterne vergrößert (Rest nie abschließend selbst
  auf echtem iPhone geprüft)

**Stammdaten** (`data/*.json`, alle einzeln committet, siehe Git-Historie für
Details je Marke)
- `model_variants.json`: 80 recherchierte Spitznamen (Rolex/Omega/AP; Girard
  Perregaux hat keine etablierten — bewusst leer gelassen statt erfunden)
- `brand_logos.json`: 35/39 Marken (4 ohne sauberes Logo gefunden, nicht geraten)
- `official_prices.json`: 43 Referenzen mit Herstellerpreis (Rolex 26,
  Patek 9, Omega/Sinn/Tudor/Breitling/IWC je einzeln, AP 0 — alle unsere
  AP-Referenzen sind bei AP selbst nicht mehr im Katalog)
- `cluster_specs_*.json`: 375 Referenzen über 18 Marken (Rolex 108,
  Breitling 41, Omega 35, AP 32, Patek 26, IWC 20, Panerai 21, Tudor 21,
  Cartier 14, JLC 15, Hublot 8, Chopard 8, A. Lange & Söhne 7, Girard
  Perregaux 4, Sinn 4, Heuer 4, TAG Heuer 4, Glashütte Original 3)

## Entscheidungen / Konfiguration

Diese Punkte wurden explizit besprochen und festgelegt — bei Unsicherheit
gilt das hier, nicht eine Vermutung:

- **"Bilderkennung" für Zifferblatt-/Lünettenfarbe bedeutet keine automatische
  KI-Bildanalyse** (Korrektur einer früheren Annahme) — Claude schickt die
  Fotos der offenen Fälle an den Nutzer, der Nutzer bestimmt die Farbe visuell
  selbst. Kein Bilderkennungs-Kostenanfall dadurch
- **Favoriten-Matching-Key**: `brand + model_line + reference_number`
  (reference_number optional — ohne sie ist der Favorit modell-/cluster-weit)
- **Cluster-Label-Format**: `"{Modelllinie} {Gehäuse}/{Lünette}/{Armband}"`,
  nur vorhandene Teile, Fallback = bloße Modelllinie wenn keine Recherche
  für diese Referenz existiert
- **Recherche-Scope**: nur real in unseren Scrapes vorkommende Referenzen,
  nicht der komplette Marken-Katalog (80/20-Prinzip, iterativ nachschärfen)
- **Recherche gilt für alle Marken mit Varianz**, nicht nur Rolex/AP —
  aber diese 26 Marken bewusst **ohne** weitere Recherche (nur
  Scraper-Rohdaten nutzen): Breguet, Parmigiani Fleurier, Montblanc,
  Longines, Zenith, Piaget, Ulysse Nardin, Harry Winston, Corum, Graham,
  Hermès, Eberhard & Co., Richard Mille, Gérald Genta, Baume & Mercier,
  Bruno Söhnle, Carl F. Bucherer, Chronoswiss, Franck Muller, Ingersoll,
  Jacques Lemans, Maurice Lacroix, Mido, Porsche Design, Revue Thommen,
  Vulcain, Wempe
- **Top-10 zählt nach Cluster**, nicht nach grober Modelllinie
- **Backup**: reine Dateikopie (kein Git-Pull/Push), wöchentlich Sonntag 18:00
- **Scrape-Zeit**: 05:00 CEST (GitHub Actions Cron in UTC — driftet bei
  Zeitumstellung im Oktober um 1h, bewusst akzeptiert statt automatisch
  nachgeführt)
- **Hintergrund-Agenten**: nie mehr als 1 gleichzeitig, keine
  selbst-startenden Unteragenten (nach einem Ratenlimit-Vorfall mit zu
  vielen parallelen Agenten)
- **Datenqualität allgemein**: "erst starten, dann nachschärfen" — lieber
  eine Lücke lassen als raten/erfinden

## Offen

- **7-Modell-Tiefenrecherche (Varianten-Erkennung)**: von den 3 Rolex-Modellen
  (Submariner, GMT-Master II, Daytona) ist die Zifferblatt-/Lünettenfarbe
  jetzt erledigt (siehe Erledigt-Sektion). Noch offen: AP Royal Oak, Patek
  Nautilus, Omega Speedmaster (Panda-Zifferblätter), Tudor Black Bay
  (Lünettenfarben) — reine Text-Recherche, kein Bild-/Nutzer-Check vorgesehen
- **Täglicher Dashboard-Auto-Refresh**: einmal besprochen, aber nie
  eingerichtet. Aktuell aktualisiert sich das Dashboard nur, wenn Claude es
  manuell neu baut und veröffentlicht — der tägliche GitHub-Scrape läuft
  automatisch, aber niemand zieht das automatisch ins Dashboard.
- **Cluster-Abdeckung ausbauen**: aktuell 59% der aktiven Angebote einem
  konkreten Cluster zugeordnet, Rest fällt auf die grobe Modelllinie zurück
  (erwartbar durch 80/20-Scope, kein Fehler — aber ausbaufähig)
- **Heuer Montreal 110.501/110.503**: Stahl-/PVD-Zuordnung in den Quellen
  uneinheitlich — model_line ist jetzt sauber ("Montreal"), aber die
  Material-Frage selbst noch nicht recherchiert
- **model_line-Qualität bei nicht-recherchierten/kleineren Marken**: bleibt
  oft der rohe Scraper-Titel statt eines sauberen Modellnamens (MODEL_LINES-
  Stichwortliste in `scrapers/model_line.py` deckt nur größere Marken ab —
  Heuer/Glashütte Original wurden ergänzt, andere kleinere Marken evtl. noch
  betroffen, nicht systematisch geprüft)
- **iPhone-Ansicht**: vom Nutzer noch nicht selbst final bestätigt
