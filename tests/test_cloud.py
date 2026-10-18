"""Cloud-Lauf: Einstellungen lesen (Namen statt IDs) und Geheimhaltung des ntfy-Themas. Ruft keine Shops ab.

Aufruf:  py tests/test_cloud.py
"""
import os
import sys
import tempfile
from pathlib import Path

ORDNER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ORDNER))

import cloud_lauf  # noqa: E402
import dashboard  # noqa: E402
from melder import Melder  # noqa: E402
from speicher import Speicher  # noqa: E402
from waechter import Waechter  # noqa: E402

fehler = []


def pruefe(bedingung, text):
    print(("OK   " if bedingung else "FEHL ") + text)
    if not bedingung:
        fehler.append(text)


def main():
    dateien = {
        "einstellungen.json": {"shops": {"gate": False, "gibtsnicht": True}, "sprachen": ["DE"],
                               "preisgrenzen": {"display": 199}, "merkliste": ["https://example.org/x"]},
        "auswahl.json": {"sets": ["Delta-Herrschaft", "Destined Rivals", "KP09", "quatsch"],
                         "reihen": ["Schwert & Schild"], "produktarten": ["Display (36er)", "etb"],
                         "produkte_ohne_set_melden": True,
                         "eigene_sets": [{"name": "Nebelkristall", "suchworte": "Nebelkristall, Mist Crystal"}]},
    }
    cloud_lauf._json_laden = lambda name: dateien.get(name, {})

    os.environ.pop("NTFY_THEMA", None)
    k = cloud_lauf.CloudKonfig()
    d = k.daten
    pruefe({"me06", "sv10", "sv09"} <= set(d["sets"]), "Sets per deutschem/englischem Namen und Kürzel erkannt")
    pruefe("swsh07" in d["sets"] and "swsh01" in d["sets"], "ganze Reihe „Schwert & Schild“ übernommen")
    pruefe(d["arten"] == ["display", "etb"], "Produktarten per Anzeigename und Kürzel erkannt")
    pruefe(any("quatsch" in h for h in k.hinweise), "unbekanntes Set wird als Hinweis gemeldet")
    pruefe(any("gibtsnicht" in h for h in k.hinweise), "unbekannter Shop wird als Hinweis gemeldet")
    pruefe(not k.shop("gate")["aktiv"] and k.shop("tcgviert")["aktiv"], "Shops an/aus aus einstellungen.json")
    pruefe(d["preisgrenzen"]["display"] == 199 and d["preisgrenzen"]["etb"] == 75, "Preisgrenzen ergänzt statt ersetzt")
    pruefe(d["merkliste"] == [{"url": "https://example.org/x", "name": ""}], "Merkliste als einfache Links möglich")
    pruefe(d["set_unbekannt_melden"] is True and d["eigene_sets"][0]["id"] == "eigen_nebelkristall", "eigene Sets übernommen")
    pruefe(not d["benachrichtigung"]["ntfy"]["aktiv"] and any("NTFY_THEMA" in h for h in k.hinweise),
           "ohne Geheimnis keine Pushes, mit Hinweis")
    pruefe(not d["benachrichtigung"]["windows"]["aktiv"], "keine Windows-Meldungen in der Cloud")

    os.environ["NTFY_THEMA"] = "geheimes-testthema-4711"
    k = cloud_lauf.CloudKonfig()
    tmp = Path(tempfile.mkdtemp())
    s = Speicher(tmp / "z.db")
    w = Waechter(k, s, Melder(k))
    app = dashboard.App(k, s, Melder(k), w)
    cloud_lauf.seite_bauen(app, k, tmp / "site")
    texte = "".join(p.read_text(encoding="utf-8") for p in (tmp / "site").rglob("*") if p.is_file() and p.suffix in {".json", ".html"})
    pruefe("geheimes-testthema-4711" not in texte, "ntfy-Thema landet nicht auf der öffentlichen Seite")
    pruefe((tmp / "site" / "api" / "modus.json").exists() and (tmp / "site" / "index.html").exists(), "Statusseite erzeugt")
    os.environ.pop("NTFY_THEMA", None)

    print("\nAlles in Ordnung." if not fehler else f"\n{len(fehler)} Prüfung(en) fehlgeschlagen.")
    return not fehler


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
