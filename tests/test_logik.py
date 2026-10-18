"""Prüft Restock-Erkennung und Meldefilter mit einer Wegwerf-Datenbank (sendet nichts).

Aufruf:  py tests/test_logik.py
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shops  # noqa: E402
from konfig import Konfig  # noqa: E402
from speicher import Speicher  # noqa: E402
from waechter import Waechter  # noqa: E402


class StummerMelder:
    def __init__(self):
        self.gesendet = []

    def senden(self, titel, text, url=None, prio=3, tags=None, bild=None):
        self.gesendet.append((titel, text, url, prio))
        return [("test", True, "")]


def lauf():
    tmp = Path(tempfile.mkdtemp())
    konfig = Konfig(tmp / "config.json")
    speicher = Speicher(tmp / "test.db")
    melder = StummerMelder()
    w = Waechter(konfig, speicher, melder)
    shop = {"id": "testshop", "name": "Testshop", "typ": "test", "aktiv": True, "basis": "https://example.org"}

    zustand = {"status": "ausverkauft", "preis": 179.99, "extra": False}

    def leser(_shop):
        liste = [{"id": "1", "titel": "Pokémon Delta-Herrschaft 36er Display (DE)", "url": "https://example.org/1",
                  "preis": zustand["preis"], "status": zustand["status"], "haendler": None, "bild": None,
                  "pokemon_quelle": False},
                 {"id": "2", "titel": "Pokémon Plüsch Pikachu 30 cm", "url": "https://example.org/2",
                  "preis": 20, "status": "lieferbar", "haendler": None, "bild": None, "pokemon_quelle": False}]
        if zustand["extra"]:
            liste.append({"id": "3", "titel": "Pokémon Delta Reign Elite Trainer Box (EN)", "url": "https://example.org/3",
                          "preis": 59.99, "status": "vorbestellbar", "haendler": None, "bild": None,
                          "pokemon_quelle": False})
            liste.append({"id": "4", "titel": "Pokémon Mega Evolution Display (EN)", "url": "https://example.org/4",
                          "preis": 399.0, "status": "lieferbar", "haendler": None, "bild": None, "pokemon_quelle": False})
        return liste

    shops.LESER["test"] = leser
    fehler = []

    def pruefe(bedingung, text):
        print(("OK   " if bedingung else "FEHL ") + text)
        if not bedingung:
            fehler.append(text)

    # 1. Erster Lauf: nur Ist-Zustand merken, nichts melden
    w._shop_pruefen(shop)
    pruefe(not melder.gesendet, "erster Lauf meldet nichts (Grundzustand)")
    pruefe(speicher.produkt("testshop:2") is None, "Plüschtier wird als irrelevant aussortiert")

    # 2. Restock: ausverkauft -> lieferbar
    zustand["status"] = "lieferbar"
    w._shop_pruefen(shop)
    pruefe(len(melder.gesendet) == 1 and "Wieder da" in melder.gesendet[0][0], "Restock wird gemeldet")
    pruefe(melder.gesendet and melder.gesendet[0][3] == 5, "Display-Restock hat höchste Priorität")

    # 3. Kurz ausverkauft und gleich wieder da -> Abklingzeit verhindert Doppelmeldung
    zustand["status"] = "ausverkauft"
    w._shop_pruefen(shop)
    zustand["status"] = "lieferbar"
    w._shop_pruefen(shop)
    pruefe(len(melder.gesendet) == 1, "Abklingzeit verhindert Doppelmeldung")

    # 4. Neue Produkte: Vorverkauf (EN) wird gemeldet, Scalper-Preis nicht
    zustand["extra"] = True
    w._shop_pruefen(shop)
    titel = [g[0] for g in melder.gesendet]
    pruefe(any("Vorverkauf offen" in t and "Elite Trainer" in t for t in titel), "neues vorbestellbares Produkt wird als Vorverkauf gemeldet")
    pruefe(not any("Mega Evolution Display" in t for t in titel), "Display für 399 € wird wegen Preisgrenze nicht gemeldet")
    gruende = {e["titel"]: e["grund"] for e in speicher.ereignisse()}
    pruefe("Preisgrenze" in gruende.get("Pokémon Mega Evolution Display (EN)", ""), "Grund 'Preisgrenze' wird protokolliert")

    # 5. Sprache abwählen -> keine Meldung
    konfig.daten["sprachen"] = ["DE"]
    konfig.daten["abklingzeit_min"] = 0
    speicher.produkt_speichern({**speicher.produkt("testshop:3"), "status": "ausverkauft"})
    vorher = len(melder.gesendet)
    w._shop_pruefen(shop)
    pruefe(len(melder.gesendet) == vorher, "englisches Produkt wird bei Sprache nur DE nicht gemeldet")

    # 6. Set-Auswahl: nur gewählte Sets werden gemeldet
    konfig.daten["sprachen"] = ["DE", "EN", "?"]
    konfig.daten["sets"] = ["sv10"]
    zustand["status"] = "ausverkauft"
    w._shop_pruefen(shop)
    zustand["status"] = "lieferbar"
    vorher = len(melder.gesendet)
    w._shop_pruefen(shop)
    pruefe(len(melder.gesendet) == vorher, "Delta-Herrschaft wird nicht gemeldet, wenn nur Ewige Rivalen gewählt ist")
    gruende = [e["grund"] for e in speicher.ereignisse() if e["schluessel"] == "testshop:1"]
    pruefe(gruende and "nicht gewählt" in gruende[0], "Grund 'Set nicht gewählt' wird protokolliert")
    konfig.daten["sets"] = ["me06"]
    zustand["status"] = "ausverkauft"
    w._shop_pruefen(shop)
    zustand["status"] = "lieferbar"
    w._shop_pruefen(shop)
    pruefe(len(melder.gesendet) == vorher + 1, "Delta-Herrschaft wird gemeldet, wenn Delta-Herrschaft gewählt ist")

    # 7. Produktart-Auswahl: nur Top-Trainer-Boxen
    konfig.daten["sets"] = []
    konfig.daten["arten"] = ["etb"]
    zustand["status"] = "ausverkauft"
    w._shop_pruefen(shop)
    zustand["status"] = "lieferbar"
    vorher = len(melder.gesendet)
    w._shop_pruefen(shop)
    pruefe(len(melder.gesendet) == vorher, "Display wird nicht gemeldet, wenn nur Top-Trainer-Boxen gewählt sind")

    print("\nAlles in Ordnung." if not fehler else f"\n{len(fehler)} Prüfung(en) fehlgeschlagen.")
    return not fehler


if __name__ == "__main__":
    t = time.time()
    ok = lauf()
    print(f"Dauer {time.time() - t:.1f} s")
    sys.exit(0 if ok else 1)
