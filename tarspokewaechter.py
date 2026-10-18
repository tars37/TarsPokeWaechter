"""TarsPokeWächter – überwacht Pokémon-TCG-Shops und meldet Restocks, Vorverkäufe und neue Produkte.

Start:  py tarspokewaechter.py            (Wächter + Dashboard, öffnet den Browser)
        py tarspokewaechter.py --einmal   (alle Shops einmal prüfen, Ergebnis ausgeben, nichts senden)
        py tarspokewaechter.py --test     (Test-Benachrichtigung senden)
"""
import argparse
import logging
import logging.handlers
import socket
import sys
import webbrowser
from pathlib import Path

ORDNER = Path(__file__).resolve().parent
sys.path.insert(0, str(ORDNER))

import dashboard  # noqa: E402
from konfig import Konfig  # noqa: E402
from melder import Melder, app_registrieren  # noqa: E402
from speicher import Speicher  # noqa: E402
from waechter import Waechter  # noqa: E402


def _logging(konsole):
    handler = [logging.handlers.RotatingFileHandler(ORDNER / "tarspokewaechter.log", maxBytes=1_000_000,
                                                    backupCount=2, encoding="utf-8")]
    if konsole and sys.stdout:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
        handler.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, handlers=handler,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%d.%m. %H:%M:%S")


def _port_belegt(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    ap = argparse.ArgumentParser(description="TarsPokeWächter")
    ap.add_argument("--einmal", action="store_true", help="alle aktiven Shops einmal prüfen und Ergebnis zeigen")
    ap.add_argument("--test", action="store_true", help="Test-Benachrichtigung senden")
    ap.add_argument("--kein-browser", action="store_true", help="Dashboard nicht automatisch öffnen")
    args = ap.parse_args()
    _logging(konsole=sys.stdout is not None)

    konfig = Konfig()
    app_registrieren(ORDNER)
    speicher = Speicher(ORDNER / "tarspokewaechter.db")
    melder = Melder(konfig)
    waechter = Waechter(konfig, speicher, melder)
    port = int(konfig.daten["dashboard"]["port"])

    if args.test:
        for kanal, ok, fehler in melder.senden("✅ TarsPokeWächter-Test", "Wenn du das liest, kommen Restock-Meldungen an.", prio=4):
            print(f"{kanal:9s} {'OK' if ok else 'FEHLER ' + fehler}")
        return

    if args.einmal:
        zustaende = waechter.einmal(melden=False)
        for sid, z in sorted(zustaende.items()):
            if not sid.startswith("news:"):
                print(f"{sid:12s} {'OK ' if z['ok'] == 1 else 'XX '} {z['meldung']}")
        verfuegbar = [p for p in speicher.produkte() if p["status"] in ("lieferbar", "knapp", "vorbestellbar")]
        print(f"\n{len(verfuegbar)} relevante Produkte gerade bestellbar.")
        return

    if _port_belegt(port):
        print("TarsPokeWächter läuft schon – öffne das Dashboard.")
        webbrowser.open(f"http://127.0.0.1:{port}/")
        return

    app = dashboard.App(konfig, speicher, melder, waechter)
    dashboard.starten(app)
    if not args.kein_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    try:
        waechter.schleife()
    except KeyboardInterrupt:
        waechter.laeuft = False


if __name__ == "__main__":
    main()
