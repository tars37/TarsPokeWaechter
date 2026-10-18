"""Release-Kalender (releases.json) und News-/Deal-Feeds (RSS)."""
import datetime as dt
import email.utils
import html
import json
import re
import time
from pathlib import Path

from netz import hole

ORDNER = Path(__file__).resolve().parent

# Nur kaufrelevante Meldungen: Restock, Vorverkauf, Termine, Deals mit Preis.
NEWS_STICHWORTE = re.compile(
    r"restock|nachschub|wieder (verfügbar|erhältlich|da|auf lager|im handel)|vorverkauf|vorbestell|pre-?order|"
    r"erscheint|erscheinungs|release date|veröffentlichungstermin|angekündigt|ankündig|announced|"
    r"neue erweiterung|pokémon center|pokemon center|\d+[,.]\d{2} ?€|€ ?\d", re.I)
NEWS_SPERRE = re.compile(r"tcg pocket|pokémon go\b|pokemon go\b|videospiel|nintendo switch|anime|plüsch|"
                         r"wertvollsten|teuersten|top 10|kolumne|enthüllt|revealed|illustrationskarte|"
                         r"turnier|championship|meisterschaft|deckliste|decklist|in china|chinese|korea|"
                         r"thailand|indonesia|taiwan", re.I)


def releases_laden():
    try:
        daten = json.loads((ORDNER / "releases.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    heute = dt.date.today()
    liste = []
    for r in daten.get("releases", []):
        try:
            tag = dt.date.fromisoformat(r["datum"])
        except (KeyError, ValueError):
            continue
        r = dict(r)
        r["tage_bis"] = (tag - heute).days
        liste.append(r)
    liste.sort(key=lambda r: r["datum"])
    return liste


def faellige_erinnerungen(releases, sprachen):
    """Erinnerungen 7 Tage vorher, 1 Tag vorher und am Erscheinungstag (ab 8 Uhr)."""
    jetzt = dt.datetime.now()
    for r in releases:
        if r.get("sprache") not in sprachen and "?" not in sprachen and r.get("sprache") != "ALLE":
            continue
        tage = r["tage_bis"]
        stufe = {7: "7", 1: "1", 0: "0"}.get(tage)
        if stufe is None or (stufe == "0" and jetzt.hour < 8):
            continue
        schluessel = f"{r['datum']}|{r['name']}|{stufe}"
        if stufe == "0":
            text = f"Heute erscheint: {r['name']}"
        elif stufe == "1":
            text = f"Morgen erscheint: {r['name']}"
        else:
            text = f"In 7 Tagen erscheint: {r['name']}"
        yield schluessel, text, r


def _rss_eintraege(text):
    for block in re.findall(r"<item\b.*?</item>|<entry\b.*?</entry>", text, re.S | re.I):
        titel = re.search(r"<title[^>]*>(.*?)</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block, re.S) or re.search(r'<link[^>]+href="([^"]+)"', block)
        datum = (re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
                 or re.search(r"<(?:updated|published)>(.*?)</(?:updated|published)>", block, re.S))
        if not titel or not link:
            continue
        t = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", titel.group(1), flags=re.S)
        t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        lk = html.unescape(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", link.group(1)).strip())
        zeit = time.time()
        if datum:
            d = datum.group(1).strip()
            try:
                zeit = email.utils.parsedate_to_datetime(d).timestamp()
            except (TypeError, ValueError):
                try:
                    zeit = dt.datetime.fromisoformat(d.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    pass
        yield {"titel": t, "link": lk, "zeit": zeit}


def news_holen(quelle):
    """quelle: {"name", "url", "nur_tcg": bool}"""
    _, text = hole(quelle["url"], accept="application/rss+xml,application/xml,text/xml,*/*;q=0.5")
    for e in _rss_eintraege(text):
        treffer = bool(NEWS_STICHWORTE.search(e["titel"])) and not NEWS_SPERRE.search(e["titel"])
        if quelle.get("nur_tcg") and not re.search(r"karte|tcg|booster|display|trainer|kollektion|collection|"
                                                    r"tin|blister|bundle|sammelkarten|pack", e["titel"], re.I):
            treffer = False
        e["quelle"] = quelle["name"]
        e["treffer"] = treffer
        yield e
