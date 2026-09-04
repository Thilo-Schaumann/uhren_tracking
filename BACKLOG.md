# Uhren-Tracker – Backlog & Entscheidungen

Lebendes Dokument. Wird von Claude bei jeder neuen Anforderung aktualisiert —
neue Wünsche werden unter "Offen" ergänzt, erledigte Punkte wandern nach
"Erledigt", und wenn sich eine frühere Entscheidung ändert, wird das unter
"Entscheidungen" korrigiert (nicht stillschweigend überschrieben).

## Erledigt

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

- **Bilderkennungs-Pilot für Zifferblatt-/Lünettenfarbe**: Text-Recherche
  bleibt Methode Nr. 1, Bilderkennung nur als Fallback wenn Text nichts
  liefert. Pilot **ausschließlich Rolex** (Submariner, GMT-Master II,
  Daytona) — erst Zeit-/Token-Kosten messen und dem Nutzer berichten, bevor
  über eine Ausweitung entschieden wird. Muss pro Wert nachvollziehbar
  machen, ob er aus Text oder Bilderkennung stammt (Spalte/Kennzeichnung,
  Umsetzung noch offen)
- **7-Modell-Tiefenrecherche (Varianten-Erkennung, z.B. Sub mit grüner
  Lünette + grünem Zifferblatt)**: Rolex Submariner/GMT-Master II/Daytona,
  AP Royal Oak, Patek Nautilus, Omega Speedmaster (Panda-Zifferblätter),
  Tudor Black Bay (Lünettenfarben) — freigegeben, noch nicht begonnen.
  Bilderkennung dabei nur für die 3 Rolex-Modelle, die anderen 4 vorerst
  nur Text-Recherche
- **Täglicher Dashboard-Auto-Refresh**: einmal besprochen, aber nie
  eingerichtet. Aktuell aktualisiert sich das Dashboard nur, wenn Claude es
  manuell neu baut und veröffentlicht — der tägliche GitHub-Scrape läuft
  automatisch, aber niemand zieht das automatisch ins Dashboard.
- **Cluster-Abdeckung ausbauen**: aktuell 59% der aktiven Angebote einem
  konkreten Cluster zugeordnet, Rest fällt auf die grobe Modelllinie zurück
  (erwartbar durch 80/20-Scope, kein Fehler — aber ausbaufähig)
- **Bekannte Datenqualitäts-Funde, noch nicht behoben**:
  - Rolex "Explorer II 116610" ist tatsächlich eine Submariner (Vendor-Fehletikettierung)
  - Cartier "3803" als "Ballon Bleu" gelistet, ist vermutlich eine Cartier Clé
  - Omega: einzelne extrahierte "Referenznummern" sind eigentlich Kaliber-
    oder Kollektionsnamen (321, 300M, 300) — Referenz-Extraktions-Regex
    müsste nachgeschärft werden
  - Heuer Montreal 110.501/110.503: Stahl-/PVD-Zuordnung in Quellen uneinheitlich
  - Glashütte "1845" ist vermutlich kein echter Referenzcode, sondern eine
    Marketing-Bezeichnung (Gründungsjahr)
  - Vereinzelte model_line-Werte sehen wie Extraktions-Artefakte aus
    ("Oysterband", "Zifferblatt Sternenhimmel") — nicht untersucht
- **model_line-Qualität bei nicht-recherchierten/kleineren Marken**: bleibt
  oft der rohe Scraper-Titel statt eines sauberen Modellnamens (MODEL_LINES-
  Stichwortliste in `scrapers/model_line.py` deckt nur größere Marken ab)
- **iPhone-Ansicht**: vom Nutzer noch nicht selbst final bestätigt
