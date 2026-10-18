"""Kleiner Webserver fürs Dashboard (PC-Browser, optional Handy im selben WLAN)."""
import ipaddress
import json
import logging
import mimetypes
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import kalender
import setliste
from filter import ART_NAMEN

log = logging.getLogger("dashboard")
WEB = Path(__file__).resolve().parent / "web"

_ERLAUBTE_EINSTELLUNGEN = {"intervall_min", "sprachen", "melden", "preisgrenze_aktiv", "preisgrenzen",
                           "marktplatz_ignorieren", "stichworte_pflicht", "stichworte_sperre", "abklingzeit_min",
                           "sets", "set_unbekannt_melden", "arten"}


def _eigene_sets_pruefen(liste):
    sauber, ids = [], set()
    for e in liste if isinstance(liste, list) else []:
        name = str(e.get("name", "")).strip()[:60]
        worte = str(e.get("suchworte", "")).strip()[:200]
        if not name or not worte:
            continue
        sid = str(e.get("id") or "eigen_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))[:40]
        while sid in ids:
            sid += "_"
        ids.add(sid)
        sauber.append({"id": sid, "name": name, "suchworte": worte})
    return sauber


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # es wird nichts gesendet
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _mischen(ziel, quelle):
    for k, v in quelle.items():
        if isinstance(v, dict) and isinstance(ziel.get(k), dict):
            _mischen(ziel[k], v)
        else:
            ziel[k] = v


class App:
    def __init__(self, konfig, speicher, melder, waechter):
        self.k, self.s, self.m, self.w = konfig, speicher, melder, waechter

    def zustand(self):
        d = self.k.daten
        st = self.s.shops()
        shops = []
        for s in d["shops"] + ([{"id": "merkliste", "name": "Merkliste", "typ": "einzelseiten", "aktiv": True,
                                 "ruf": "eigene Links"}] if d.get("merkliste") else []):
            z = st.get(s["id"], {})
            shops.append({"id": s["id"], "name": s["name"], "typ": s["typ"], "aktiv": s.get("aktiv", False),
                          "ruf": s.get("ruf", ""), "basis": s.get("basis", ""), "ok": z.get("ok"),
                          "meldung": z.get("meldung", ""), "zuletzt": z.get("zuletzt"),
                          "naechster": z.get("naechster"), "anzahl": z.get("anzahl", 0),
                          "relevant": z.get("relevant", 0), "dauer": z.get("dauer")})
        news = [{"name": q["name"], "aktiv": q.get("aktiv"), **{k: st.get("news:" + q["name"], {}).get(k)
                                                               for k in ("ok", "meldung", "zuletzt")}}
                for q in d.get("news_quellen", [])]
        port = d["dashboard"]["port"]
        return {
            "gestartet": self.w.gestartet, "jetzt": time.time(),
            "ntfy": {"server": d["benachrichtigung"]["ntfy"].get("server"),
                     "thema": d["benachrichtigung"]["ntfy"].get("thema"),
                     "aktiv": d["benachrichtigung"]["ntfy"].get("aktiv")},
            "wlan": {"aktiv": d["dashboard"].get("im_wlan"),
                     "url": f"http://{lan_ip()}:{port}/?k={d['dashboard']['schluessel']}"},
            "shops": shops, "manuell": d.get("manuell", []), "news_quellen": news,
            "art_namen": ART_NAMEN, "merkliste": d.get("merkliste", []),
        }

    def einstellungen(self):
        d = self.k.daten
        aus = {k: d[k] for k in _ERLAUBTE_EINSTELLUNGEN}
        aus["eigene_sets"] = d.get("eigene_sets", [])
        aus["benachrichtigung"] = d["benachrichtigung"]
        aus["im_wlan"] = d["dashboard"].get("im_wlan", False)
        return aus

    def einstellungen_setzen(self, neu):
        d = self.k.daten
        with self.k.sperre:
            for k, v in neu.items():
                if k in _ERLAUBTE_EINSTELLUNGEN:
                    if isinstance(v, dict) and isinstance(d.get(k), dict):
                        _mischen(d[k], v)
                    else:
                        d[k] = v
                elif k == "benachrichtigung" and isinstance(v, dict):
                    _mischen(d["benachrichtigung"], v)
                elif k == "im_wlan":
                    d["dashboard"]["im_wlan"] = bool(v)
                elif k == "eigene_sets":
                    d["eigene_sets"] = _eigene_sets_pruefen(v)
                elif k == "shops_aktiv" and isinstance(v, dict):
                    for s in d["shops"]:
                        if s["id"] in v:
                            s["aktiv"] = bool(v[s["id"]])
                elif k == "news_aktiv" and isinstance(v, dict):
                    for q in d["news_quellen"]:
                        if q["name"] in v:
                            q["aktiv"] = bool(v[q["name"]])
            d["intervall_min"] = max(2, float(d.get("intervall_min") or 4))
            self.k.speichern()
        return self.einstellungen()

    def produkte(self):
        namen = {s["id"]: s["name"] for s in self.k.daten["shops"]}
        namen["merkliste"] = "Merkliste"
        aktiv = {s["id"] for s in self.k.daten["shops"] if s.get("aktiv")} | {"merkliste"}
        eigene = self.k.daten.get("eigene_sets")
        liste = self.s.produkte()
        for p in liste:
            p["shopname"] = namen.get(p["shop"], p["shop"])
            p["shop_aktiv"] = p["shop"] in aktiv
            p["set_id"] = setliste.set_von(p["titel"], eigene)
            grenze = self.k.daten["preisgrenzen"].get(p["art"])
            p["ueber_grenze"] = bool(self.k.daten.get("preisgrenze_aktiv") and grenze and p["preis"] and p["preis"] > grenze)
        return liste

    def sets(self):
        """Reihen mit ihren Sets und wie viele Produkte je Set gerade bestellbar sind."""
        zaehler = {}
        for p in self.produkte():
            if not p["shop_aktiv"] or (p["haendler"] or "").startswith("Marktplatz"):
                continue
            z = zaehler.setdefault(p["set_id"], {"verfuegbar": 0, "gesamt": 0})
            z["gesamt"] += 1
            if p["status"] in ("lieferbar", "knapp", "vorbestellbar"):
                z["verfuegbar"] += 1
        reihen = []
        for r in setliste.reihen(self.k.daten.get("eigene_sets")):
            reihen.append({**r, "sets": [{**s, **zaehler.get(s["id"], {"verfuegbar": 0, "gesamt": 0})}
                                         for s in r["sets"]]})
        return {"reihen": reihen, "ohne_set": zaehler.get(None, {"verfuegbar": 0, "gesamt": 0})}

    def merkliste(self, aktion, url, name=""):
        url = (url or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("Bitte eine vollständige Adresse mit https:// eingeben.")
        with self.k.sperre:
            liste = self.k.daten.setdefault("merkliste", [])
            liste[:] = [e for e in liste if e["url"] != url]
            if aktion == "hinzu":
                liste.append({"url": url, "name": name.strip()})
            else:
                self.s.produkt_loeschen(f"merkliste:{url}")
            self.k.speichern()
        if aktion == "hinzu":
            st = self.s.shop("merkliste")
            st["naechster"] = 0
            self.s.shop_speichern(st)
            self.w.wecker.set()
        return self.k.daten["merkliste"]


def _handler(app):
    class H(BaseHTTPRequestHandler):
        server_version = "TarsPokeWaechter/1.0"

        def log_message(self, *args):
            pass

        def _lokal(self):
            try:
                return ipaddress.ip_address(self.client_address[0]).is_loopback
            except ValueError:
                return False

        def _berechtigt(self):
            if self._lokal():
                return True
            schluessel = app.k.daten["dashboard"]["schluessel"]
            q = parse_qs(urlsplit(self.path).query)
            return q.get("k", [""])[0] == schluessel or self.headers.get("X-Schluessel") == schluessel

        def _json(self, daten, code=200):
            roh = json.dumps(daten, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def _datei(self, name):
            pfad = (WEB / name).resolve()
            if WEB not in pfad.parents or not pfad.is_file():
                self.send_error(404)
                return
            roh = pfad.read_bytes()
            self.send_response(200)
            typ = mimetypes.guess_type(pfad.name)[0] or "application/octet-stream"
            if pfad.suffix == ".webmanifest":
                typ = "application/manifest+json"
            self.send_header("Content-Type", typ + ("; charset=utf-8" if typ.startswith("text") else ""))
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def do_GET(self):
            pfad = urlsplit(self.path).path
            if pfad in ("/", "/index.html"):
                if not self._berechtigt():
                    self.send_error(403, "Zugangsschlüssel fehlt")
                    return
                return self._datei("index.html")
            if pfad in ("/manifest.webmanifest", "/icon.svg", "/icon-192.png", "/icon-256.png", "/icon.ico",
                        "/favicon.ico"):
                if pfad == "/favicon.ico":
                    pfad = "/icon.ico"
                return self._datei(pfad.lstrip("/"))
            if not self._berechtigt():
                return self._json({"fehler": "Zugangsschlüssel fehlt"}, 403)
            if pfad == "/api/zustand":
                return self._json(app.zustand())
            if pfad == "/api/produkte":
                return self._json(app.produkte())
            if pfad == "/api/ereignisse":
                return self._json(app.s.ereignisse(300))
            if pfad == "/api/releases":
                return self._json(kalender.releases_laden())
            if pfad == "/api/news":
                return self._json(app.s.news(80))
            if pfad == "/api/einstellungen":
                return self._json(app.einstellungen())
            if pfad == "/api/sets":
                return self._json(app.sets())
            self.send_error(404)

        def do_POST(self):
            if not self._berechtigt() or self.headers.get("X-TarsPokeWaechter") != "1":
                return self._json({"fehler": "nicht erlaubt"}, 403)
            laenge = int(self.headers.get("Content-Length") or 0)
            try:
                daten = json.loads(self.rfile.read(laenge) or b"{}") if laenge else {}
            except ValueError:
                return self._json({"fehler": "ungültiges JSON"}, 400)
            pfad = urlsplit(self.path).path
            try:
                if pfad == "/api/pruefen":
                    app.w.jetzt_pruefen()
                    return self._json({"ok": True})
                if pfad == "/api/test":
                    erg = app.m.senden("✅ TarsPokeWächter-Test", "Wenn du das liest, kommen Restock-Meldungen bei dir an.",
                                       prio=4)
                    return self._json({"ergebnisse": [{"kanal": k, "ok": o, "fehler": f} for k, o, f in erg]})
                if pfad == "/api/einstellungen":
                    return self._json(app.einstellungen_setzen(daten))
                if pfad == "/api/merkliste":
                    return self._json(app.merkliste(daten.get("aktion", "hinzu"), daten.get("url"), daten.get("name", "")))
            except ValueError as e:
                return self._json({"fehler": str(e)}, 400)
            self.send_error(404)

    return H


def starten(app):
    d = app.k.daten["dashboard"]
    adresse = "0.0.0.0" if d.get("im_wlan") else "127.0.0.1"
    server = ThreadingHTTPServer((adresse, int(d["port"])), _handler(app))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="dashboard", daemon=True).start()
    log.info("Dashboard: http://127.0.0.1:%s/", d["port"])
    return server
