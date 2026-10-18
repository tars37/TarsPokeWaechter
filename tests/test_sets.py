"""Set-Erkennung: feste Beispiele + Abdeckung über die gespeicherten echten Produkttitel.

Aufruf:  py tests/test_sets.py          (zeigt am Ende Titel ohne erkanntes Set)
"""
import collections
import sqlite3
import sys
from pathlib import Path

ORDNER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ORDNER))

import setliste  # noqa: E402

BEISPIELE = [
    ("Pokémon TCG | Mega Entwicklungen: Delta Herrschaft (ME06) | 36er Display (DE)", "me06"),
    ("Mega-Entwicklung Delta Herrschaft Display (36 Booster) (deutsch)", "me06"),
    ("Pokemon - Mega-Entwicklung Delta-Herrschaft Sammelkarten Booster Display", "me06"),
    ("Mega Evolution: Delta Reign Elite Trainer Box", "me06"),
    ("Mega-Entwicklung 18er Display (18 Booster) (deutsch)", "me01"),
    ("Mega Evolution Mini Tin Display sealed (englisch)", "me01"),
    ("Pokémon TCG: Erhabene Helden (ME2.5) - Mega Premium Poster Kollektion (DE)", "me025"),
    ("Pokémon - Mega-Entwicklung Fatale Flammen Booster Box - DE", "me02"),
    ("Pokémon TCG: Phantasmal Flames (ME02) - Display (EN)", "me02"),
    ("Pokemon 30 Jahre Ordner Kollektion", "30jahre"),
    ("Pokemon 30th Celebration (M6a) Display", "30jahre"),
    ("Pokémon TCG: Ewige Rivalen (KP10) - 36er Display (DE)", "sv10"),
    ("Karmesin & Purpur Reisegefährten Display (36 Booster) (deutsch)", "sv09"),
    ("Karmesin & Purpur Schwarze Blitze Booster (deutsch)", "sv105b"),
    ("Karmesin & Purpur Weiße Flammen Booster (deutsch)", "sv105w"),
    ("Pokémon - Ewige Rivalen & Obsidian Flammen 2-Pack-Blister - DE", "sv10"),
    ("Pokémon - Karmesin & Purpur: Paradox Rift Donnersichel Top Trainer Box - DE", "sv04"),
    ("Pokémon TCG: Prismatic Evolutions (SV8.5) - Super Premium Collection (EN)", "sv085"),
    ("Pokémon - Karmesin & Purpur: Entwicklungen in Paldea Booster Display - DE", "sv02"),
    ("Pokémon -  Karmesin & Purpur: Paldeas Schicksale Top Trainer Box - DE", "sv045"),
    ("Pokémon - Karmesin & Purpur Booster Display - DE", "sv01"),
    ("Pokemon Drachenwandel 3-Pack Blister", "swsh07"),
    ("Pokémon - 25th Anniversary Celebrations Elite Trainer Box - EN", "cel25"),
    ("Sonne & Mond Echo des Donners Display (18 Booster) (deutsch)", "sm"),
    ("Pokemon Storm Emeralda (M6) Display", "jp_m6"),
    ("Pokemon Mega Symphonia Display (Koreanisch)", "jp_m1"),
    ("Pokemon Terastal Gathering Display (csv9.5C) (CN)", "cn"),
    ("Pokémon TCG | Pokémon Day 2026 | Kollektion (DE)", None),
]


def main():
    fehler = 0
    for titel, soll in BEISPIELE:
        ist = setliste.set_von(titel)
        if ist != soll:
            fehler += 1
            print(f"FEHL  erwartet {soll}, erkannt {ist}: {titel}")
    print(f"{len(BEISPIELE) - fehler}/{len(BEISPIELE)} Beispiele richtig")

    eigene = [{"id": "eigen_test", "name": "Testset", "suchworte": "Nebel Kristall, Mist Crystal"}]
    ok = setliste.set_von("Pokémon Nebel-Kristall Display (DE)", eigene) == "eigen_test"
    print("eigenes Set wird erkannt:", "OK" if ok else "FEHL")
    fehler += not ok

    db = ORDNER / "tarspokewaechter.db"
    if db.exists():
        titel = [r[0] for r in sqlite3.connect(db).execute("SELECT titel FROM produkte")]
        verteilung = collections.Counter(setliste.set_von(t) for t in titel)
        ohne = sorted(t for t in titel if setliste.set_von(t) is None)
        print(f"\n{len(titel)} echte Titel, davon {len(titel) - len(ohne)} mit Set ({100 * (len(titel) - len(ohne)) // max(1, len(titel))} %)")
        print("Häufigste Sets:", ", ".join(f"{k}={v}" for k, v in verteilung.most_common(12) if k))
        if "-v" in sys.argv:
            print("\nOhne Set:")
            for t in ohne:
                print("  ", t[:110])
    return fehler == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
