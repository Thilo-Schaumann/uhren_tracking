"""Best-effort model-line extraction (e.g. 'Speedmaster') from brand + free-text title."""

MODEL_LINES = {
    "rolex": ["GMT-Master II", "GMT-Master", "Sea-Dweller", "Submariner", "Daytona",
              "Datejust", "Day-Date", "Explorer II", "Explorer", "Milgauss",
              "Yacht-Master II", "Yacht-Master", "Air-King", "Oyster Perpetual", "Sky-Dweller", "Cellini"],
    "omega": ["Speedmaster", "Seamaster", "Constellation", "De Ville", "Railmaster"],
    "patek philippe": ["Nautilus", "Aquanaut", "Calatrava", "Grand Complications",
                        "Golden Ellipse", "Twenty~4", "Twenty-4", "Complications"],
    "audemars piguet": ["Royal Oak Offshore", "Royal Oak Concept", "Royal Oak", "Code 11.59"],
    "panerai": ["Luminor Marina", "Luminor Due", "Luminor", "Radiomir"],
    "iwc": ["Portugieser", "Pilot", "Fliegeruhr", "Aquatimer", "Ingenieur", "Da Vinci"],
    "jaeger-lecoultre": ["Reverso", "Master Control", "Master Grande", "Polaris", "Master"],
    "breitling": ["Navitimer", "Superocean", "Chronomat", "Avenger", "Premier"],
    "cartier": ["Tank", "Santos", "Ballon Bleu", "Pasha"],
    "chopard": ["L.U.C", "Happy Sport", "Mille Miglia", "Alpine Eagle"],
    "a. lange & söhne": ["Lange 1", "Saxonia", "Datograph", "Zeitwerk"],
    "sinn": ["Flieger", "U1", "U50", "104", "356"],
    "tudor": ["Black Bay", "Pelagos", "Royal"],
    "vacheron constantin": ["Overseas", "Patrimony", "Traditionnelle"],
    "hublot": ["Big Bang", "Classic Fusion"],
    "tag heuer": ["Carrera", "Monaco", "Aquaracer", "Formula 1"],
    "zenith": ["El Primero", "Defy", "Chronomaster"],
    "blancpain": ["Fifty Fathoms", "Villeret"],
    "girard-perregaux": ["Laureato"],
    "longines": ["Master Collection", "HydroConquest", "Heritage"],
}


def extract_model_line(brand: str, title: str) -> str:
    """Returns a known model line if found, otherwise the title with the brand prefix stripped."""
    candidates = MODEL_LINES.get((brand or "").strip().lower(), [])
    for line in sorted(candidates, key=len, reverse=True):
        if line.lower() in title.lower():
            return line

    fallback = title
    if brand and fallback.lower().startswith(brand.lower()):
        fallback = fallback[len(brand):].strip()
    return fallback
