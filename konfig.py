"""Einstellungen (config.json) mit Standardwerten; neue Standardwerte werden bei Updates ergänzt."""
import copy
import json
import secrets
import threading
from pathlib import Path

from filter import STANDARD_PREISGRENZEN

ORDNER = Path(__file__).resolve().parent
PFAD = ORDNER / "config.json"

# ruf: "bekannt" = große Kette / lange etablierter Händler, "fachhandel" = TCG-Fachshop,
#      "ungeprueft" = kleiner Shop, Ruf nicht geprüft (standardmäßig aus)
SHOPS = [
    {"id": "gate", "name": "Gate to the Games", "typ": "jtl", "basis": "https://www.gate-to-the-games.de",
     "quellen": ["/Pokemon-Karten/Pokemon-Displays/", "/Pokemon-Karten/Pokemon-Booster/",
                 "/Pokemon-Karten/Sonderboxen/", "/Pokemon-Karten/Pokemon-Tin-Boxen/"],
     "pokemon_quelle": True, "ruf": "bekannt", "aktiv": True},
    {"id": "cardcorner", "name": "Card-Corner", "typ": "jtl", "basis": "https://www.card-corner.de",
     "quellen": ["/Pokemon-Karten-Deutsch", "/Pokemon-Karten-Englisch"],
     "pokemon_quelle": True, "ruf": "bekannt", "aktiv": True},
    {"id": "tcgviert", "name": "TCGViert", "typ": "shopify", "basis": "https://tcgviert.com",
     "quellen": ["*"], "max_seiten": 6, "ruf": "fachhandel", "aktiv": True},
    {"id": "cardcosmos", "name": "CardCosmos", "typ": "shopify", "basis": "https://cardcosmos.de",
     "quellen": ["pokemon-display-deutsch", "pokemon-display-englisch", "pokemon-elite-trainer-box-deutsch",
                 "pokemon-etb-englisch", "pokemon-booster-bundle", "pokemon-blister", "pokemon-kollektionen",
                 "pokemon-tin-box-deutsch"],
     "pokemon_quelle": True, "ruf": "fachhandel", "aktiv": True, "intervall_min": 8},
    {"id": "elbenwald", "name": "Elbenwald", "typ": "shopify", "basis": "https://elbenwald.de",
     "quellen": ["sammelkarten"], "max_seiten": 3, "ruf": "bekannt", "aktiv": True},
    {"id": "mueller", "name": "Müller", "typ": "mueller", "basis": "https://www.mueller.de",
     "quellen": ["pokemon sammelkartenspiel", "pokemon booster", "pokemon top trainer box"], "ruf": "bekannt", "aktiv": True},
    {"id": "mediamarkt", "name": "MediaMarkt", "typ": "mediamarkt", "basis": "https://www.mediamarkt.de",
     "quellen": ["pokemon sammelkarten", "pokemon display", "pokemon top trainer box"], "ruf": "bekannt", "aktiv": True},
    {"id": "proshop", "name": "Proshop", "typ": "proshop", "basis": "https://www.proshop.de",
     "quellen": ["pokemon booster", "pokemon display", "pokemon top trainer box"], "ruf": "bekannt", "aktiv": True},
    {"id": "spielemax", "name": "Spiele Max", "typ": "woocommerce", "basis": "https://www.spielemax.de",
     "quellen": ["pokemon"], "ruf": "bekannt", "aktiv": True, "intervall_min": 15},
    {"id": "cardknights", "name": "Card Knights", "typ": "shopify", "basis": "https://www.card-knights.de",
     "quellen": ["*"], "ruf": "ungeprueft", "aktiv": False, "max_seiten": 2},
    {"id": "pokitrio", "name": "Pokitrio", "typ": "shopify", "basis": "https://www.pokitrio.de",
     "quellen": ["*"], "ruf": "ungeprueft", "aktiv": False, "max_seiten": 2},
    {"id": "shophotep", "name": "Shophotep", "typ": "woocommerce", "basis": "https://shophotep.com",
     "quellen": ["pokemon"], "ruf": "ungeprueft", "aktiv": False},
]

MANUELL = [
    {"name": "Pokémon Center (offiziell)", "url": "https://www.pokemoncenter.com/de-de/category/trading-card-game",
     "grund": "Bot-Schutz (HTTP 403)"},
    {"name": "Amazon.de", "url": "https://www.amazon.de/s?k=pokemon+sammelkarten+display",
     "grund": "Bot-Prüfung; neue Sets oft nur per Einladung"},
    {"name": "Smyths Toys", "url": "https://www.smythstoys.com/de/de-de/search/?text=pokemon%20karten",
     "grund": "Seite lädt Produkte nur per JavaScript"},
    {"name": "Thalia", "url": "https://www.thalia.de/suche?sq=pokemon+sammelkarten", "grund": "Bot-Schutz (HTTP 403)"},
    {"name": "Kaufland", "url": "https://www.kaufland.de/s/?search_value=pokemon%20display", "grund": "Bot-Schutz (HTTP 403)"},
    {"name": "Fantasywelt", "url": "https://www.fantasywelt.de/", "grund": "Bot-Schutz (HTTP 403)"},
    {"name": "Trader Online", "url": "https://www.trader-online.de/", "grund": "Bot-Schutz; Suche per robots.txt gesperrt"},
    {"name": "Rossmann", "url": "https://www.rossmann.de/de/search/?text=pokemon", "grund": "Suche per robots.txt gesperrt"},
    {"name": "Otto", "url": "https://www.otto.de/suche/pokemon%20sammelkarten/", "grund": "Suche per robots.txt gesperrt"},
    {"name": "Saturn", "url": "https://www.saturn.de/de/search.html?query=pokemon%20sammelkarten",
     "grund": "Suche per robots.txt gesperrt (gleiches Sortiment wie MediaMarkt)"},
    {"name": "Galeria", "url": "https://www.galeria.de/search?q=pokemon%20karten", "grund": "Suche per robots.txt gesperrt"},
    {"name": "Games Island", "url": "https://games-island.eu/c/Pokemon",
     "grund": "Shop untersagt automatische Abfragen (Hauptseite und crawlme-Datenquelle per robots.txt gesperrt)"},
]

NEWS = [
    {"name": "mydealz (Pokémon-Deals)", "url": "https://www.mydealz.de/rss/gruppe/pokemon", "nur_tcg": True, "aktiv": True},
    {"name": "Pokézentrum", "url": "https://pokezentrum.de/feed/", "nur_tcg": False, "aktiv": True},
    {"name": "PokeBeach (EN)", "url": "https://www.pokebeach.com/forums/forums/front-page-news.18/index.rss",
     "nur_tcg": False, "aktiv": True},
]


def _standard():
    return {
        "intervall_min": 4,
        "sprachen": ["DE", "EN", "?"],
        "sets": [],                     # gewählte Set-IDs aus sets.json; leer = alle Sets
        "set_unbekannt_melden": False,  # bei Set-Auswahl: auch Produkte ohne erkanntes Set melden?
        "eigene_sets": [],              # [{"id", "name", "suchworte": "wort1, wort2"}]
        "arten": [],                    # gewählte Produktarten (display, etb, ...); leer = alle
        "melden": {"wieder_da": True, "neu_bestellbar": True, "vorverkauf": True, "neu_gelistet": True,
                   "preis_runter": False, "news": True, "releases": True},
        "preisgrenze_aktiv": True,
        "preisgrenzen": dict(STANDARD_PREISGRENZEN),
        "marktplatz_ignorieren": True,
        "stichworte_pflicht": [],
        "stichworte_sperre": [],
        "abklingzeit_min": 60,
        "dashboard": {"port": 8787, "im_wlan": False, "schluessel": secrets.token_urlsafe(12)},
        "benachrichtigung": {
            "ntfy": {"aktiv": True, "server": "https://ntfy.sh", "thema": "tarspokewaechter-" + secrets.token_hex(6),
                     "token": "", "bilder": True},
            "windows": {"aktiv": True, "in_ruhezeit_still": True},
            "telegram": {"aktiv": False, "bot_token": "", "chat_id": ""},
            "discord": {"aktiv": False, "webhook": ""},
            "ruhezeit": {"aktiv": False, "von": "23:00", "bis": "07:00"},
        },
        "shops": copy.deepcopy(SHOPS),
        "manuell": copy.deepcopy(MANUELL),
        "news_quellen": copy.deepcopy(NEWS),
        "merkliste": [],
    }


def _ergaenzen(ziel, standard):
    for k, v in standard.items():
        if k not in ziel:
            ziel[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(ziel[k], dict):
            _ergaenzen(ziel[k], v)


class Konfig:
    def __init__(self, pfad=PFAD):
        self.pfad = Path(pfad)
        self.sperre = threading.RLock()
        std = _standard()
        if self.pfad.exists():
            self.daten = json.loads(self.pfad.read_text(encoding="utf-8"))
            _ergaenzen(self.daten, std)
            # Technische Shop-Angaben kommen immer aus dem Programm (Updates), An/Aus bleibt deine Wahl.
            vorhanden = {s["id"]: s for s in self.daten["shops"]}
            neu = []
            for s in std["shops"]:
                alt = vorhanden.pop(s["id"], None)
                neu.append({**s, "aktiv": alt.get("aktiv", s["aktiv"])} if alt else s)
            self.daten["shops"] = neu + list(vorhanden.values())
            aktiv_news = {q["name"]: q.get("aktiv", True) for q in self.daten.get("news_quellen", [])}
            self.daten["news_quellen"] = [{**q, "aktiv": aktiv_news.get(q["name"], q["aktiv"])} for q in std["news_quellen"]]
            self.daten["manuell"] = std["manuell"]
        else:
            self.daten = std
        self.speichern()

    def speichern(self):
        with self.sperre:
            tmp = self.pfad.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.daten, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.pfad)

    def shop(self, sid):
        return next((s for s in self.daten["shops"] if s["id"] == sid), None)
