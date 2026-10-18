"""Ein Durchlauf für die Cloud (GitHub Actions, alle ~10 Minuten).

Prüft die fälligen Shops, meldet Neues per ntfy und baut die Statusseite (Ordner site/) für GitHub Pages.
Einstellungen: einstellungen.json (allgemein) und auswahl.json (Sets, Produktarten) im Repository.
Das ntfy-Thema kommt nur aus dem GitHub-Geheimnis NTFY_THEMA und landet nie auf der Statusseite.

Lokal testen:  py cloud_lauf.py --zustand <ordner> --seite <ordner>
"""
import argparse
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ORDNER = Path(__file__).resolve().parent
sys.path.insert(0, str(ORDNER))

import dashboard  # noqa: E402
import kalender  # noqa: E402
import konfig as konfig_modul  # noqa: E402
import setliste  # noqa: E402
from filter import ART_NAMEN  # noqa: E402
from melder import Melder  # noqa: E402
from speicher import Speicher  # noqa: E402
from waechter import Waechter  # noqa: E402

log = logging.getLogger("cloud")
GEHEIME_SCHLUESSEL = {"thema", "token", "bot_token", "chat_id", "webhook", "schluessel", "wlan"}


def _norm(s):
    return re.sub(r"[^a-z0-9äöüß]+", "", str(s).lower())


def _json_laden(name):
    pfad = ORDNER / name
    if not pfad.exists():
        return {}
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"{name} ist kein gültiges JSON (Komma oder Anführungszeichen vergessen?): {e}")


class CloudKonfig:
    """Wie konfig.Konfig, aber aus einstellungen.json + auswahl.json + Geheimnissen; speichert nichts."""

    def __init__(self):
        self.sperre = threading.RLock()
        self.hinweise = []
        d = konfig_modul._standard()
        e, a = _json_laden("einstellungen.json"), _json_laden("auswahl.json")

        for schluessel, ziel in [("sprachen", "sprachen"), ("preisgrenze_aktiv", "preisgrenze_aktiv"),
                                 ("marktplatz_ignorieren", "marktplatz_ignorieren"),
                                 ("pflicht_stichworte", "stichworte_pflicht"), ("sperr_stichworte", "stichworte_sperre"),
                                 ("abklingzeit_minuten", "abklingzeit_min"), ("merkliste", "merkliste")]:
            if schluessel in e:
                d[ziel] = e[schluessel]
        d["preisgrenzen"].update(e.get("preisgrenzen", {}))
        d["melden"].update(e.get("melden", {}))
        if "ruhezeit" in e:
            d["benachrichtigung"]["ruhezeit"].update(e["ruhezeit"])
        for sid, an in (e.get("shops") or {}).items():
            shop = next((s for s in d["shops"] if s["id"] == sid), None)
            if shop:
                shop["aktiv"] = bool(an)
            elif not sid.startswith("_"):
                self.hinweise.append(f"Shop „{sid}“ aus einstellungen.json gibt es nicht.")
        d["merkliste"] = [m if isinstance(m, dict) else {"url": m, "name": ""} for m in d.get("merkliste") or []]

        # Auswahl: Sets und Reihen dürfen als Namen (deutsch/englisch), Kürzel oder ID angegeben werden
        d["eigene_sets"] = dashboard._eigene_sets_pruefen(a.get("eigene_sets", []))
        reihen = setliste.reihen(d["eigene_sets"])
        nach_name = {}
        for r in reihen:
            for s in r["sets"]:
                kuerzel = [t.strip() for t in re.split(r"[/,]", s.get("code") or "")]
                for name in [s["id"], s["de"], s.get("en"), *kuerzel]:
                    if name:
                        nach_name.setdefault(_norm(name), s["id"])
        gewaehlt = []
        for name in a.get("sets", []):
            sid = nach_name.get(_norm(name))
            if sid:
                gewaehlt.append(sid)
            else:
                self.hinweise.append(f"Set „{name}“ aus auswahl.json nicht gefunden.")
        for name in a.get("reihen", []):
            reihe = next((r for r in reihen if _norm(r["name"]) == _norm(name)), None)
            if reihe:
                gewaehlt += [s["id"] for s in reihe["sets"]]
            else:
                self.hinweise.append(f"Reihe „{name}“ aus auswahl.json nicht gefunden.")
        d["sets"] = sorted(set(gewaehlt))
        d["set_unbekannt_melden"] = bool(a.get("produkte_ohne_set_melden", False))
        arten = {_norm(k): k for k in ART_NAMEN} | {_norm(v): k for k, v in ART_NAMEN.items()}
        d["arten"] = []
        for name in a.get("produktarten", []):
            if _norm(name) in arten:
                d["arten"].append(arten[_norm(name)])
            else:
                self.hinweise.append(f"Produktart „{name}“ aus auswahl.json nicht gefunden.")

        ntfy = d["benachrichtigung"]["ntfy"]
        ntfy["thema"] = os.environ.get("NTFY_THEMA", "").strip()
        ntfy["server"] = os.environ.get("NTFY_SERVER", "").strip() or "https://ntfy.sh"
        ntfy["aktiv"] = bool(ntfy["thema"])
        if not ntfy["thema"]:
            self.hinweise.append("Das GitHub-Geheimnis NTFY_THEMA fehlt – es werden keine Pushes verschickt.")
        d["benachrichtigung"]["windows"]["aktiv"] = False
        self.daten = d

    def speichern(self):
        pass

    def shop(self, sid):
        return next((s for s in self.daten["shops"] if s["id"] == sid), None)


def _bereinigen(o):
    """Entfernt alles Geheime (ntfy-Thema, Tokens, Schlüssel) aus Daten für die öffentliche Seite."""
    if isinstance(o, dict):
        return {k: _bereinigen(v) for k, v in o.items() if k not in GEHEIME_SCHLUESSEL}
    if isinstance(o, list):
        return [_bereinigen(v) for v in o]
    return o


def seite_bauen(app, konfig, ziel):
    ziel = Path(ziel)
    if ziel.exists():
        shutil.rmtree(ziel)
    shutil.copytree(ORDNER / "web", ziel)
    (ziel / "api").mkdir()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    zweig = os.environ.get("GITHUB_REF_NAME", "main")
    einst = app.einstellungen()
    einst.pop("benachrichtigung", None)
    einst["ruhezeit"] = konfig.daten["benachrichtigung"]["ruhezeit"]
    dateien = {
        "zustand": app.zustand(),
        "produkte": app.produkte(),
        "ereignisse": app.s.ereignisse(300),
        "releases": kalender.releases_laden(),
        "news": app.s.news(80),
        "einstellungen": einst,
        "sets": app.sets(),
        "modus": {
            "statisch": True, "erzeugt": time.time(), "repo": repo,
            "repo_url": f"https://github.com/{repo}" if repo else "",
            "auswahl_bearbeiten": f"https://github.com/{repo}/edit/{zweig}/auswahl.json" if repo else "",
            "einstellungen_bearbeiten": f"https://github.com/{repo}/edit/{zweig}/einstellungen.json" if repo else "",
            "laeufe_url": f"https://github.com/{repo}/actions" if repo else "",
            "push_aktiv": bool(konfig.daten["benachrichtigung"]["ntfy"]["thema"]),
            "hinweise": konfig.hinweise,
        },
    }
    thema = konfig.daten["benachrichtigung"]["ntfy"]["thema"]
    for name, inhalt in dateien.items():
        text = json.dumps(_bereinigen(inhalt), ensure_ascii=False)
        if thema and thema in text:
            raise RuntimeError("Sicherheitsstopp: Das ntfy-Thema wäre auf der öffentlichen Seite gelandet.")
        (ziel / "api" / f"{name}.json").write_text(text, encoding="utf-8")
    (ziel / ".nojekyll").write_text("", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="TarsPokeWächter – ein Cloud-Durchlauf")
    ap.add_argument("--zustand", default=str(ORDNER / "zustand"), help="Ordner für die Zustands-Datenbank")
    ap.add_argument("--seite", default=str(ORDNER / "site"), help="Ausgabeordner der Statusseite")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(levelname)-7s %(name)s: %(message)s")

    konfig = CloudKonfig()
    for h in konfig.hinweise:
        log.warning(h)
    Path(args.zustand).mkdir(parents=True, exist_ok=True)
    speicher = Speicher(Path(args.zustand) / "tarspokewaechter.db")
    melder = Melder(konfig)
    waechter = Waechter(konfig, speicher, melder)

    if os.environ.get("TEST_PUSH", "").lower() == "true":
        for kanal, ok, fehler in melder.senden("✅ TarsPokeWächter-Test aus der Cloud",
                                               "Wenn du das liest, kommen die Restock-Meldungen von GitHub bei dir an.",
                                               prio=4):
            log.info("Test-Push über %s: %s", kanal, "OK" if ok else f"FEHLER {fehler}")

    jetzt = time.time()
    faellig = [s for s in waechter.shops_aktiv() if (speicher.shop(s["id"])["naechster"] or 0) <= jetzt + 120]
    log.info("%d Shops fällig: %s", len(faellig), ", ".join(s["id"] for s in faellig))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(waechter._shop_sicher, faellig))

    news_zuletzt = [speicher.shop("news:" + q["name"])["zuletzt"] or 0 for q in konfig.daten["news_quellen"] if q.get("aktiv")]
    if not news_zuletzt or min(news_zuletzt) < jetzt - 25 * 60:
        waechter._news_und_releases_sicher()
    else:
        waechter.releases_pruefen()

    app = dashboard.App(konfig, speicher, melder, waechter)
    seite_bauen(app, konfig, args.seite)
    fehler = [s for s in faellig if speicher.shop(s["id"])["ok"] != 1]
    log.info("Fertig in %.0f s, %d Shops ok, %d mit Problemen.", time.time() - jetzt, len(faellig) - len(fehler), len(fehler))


if __name__ == "__main__":
    main()
