"""Der eigentliche Wächter: prüft Shops nach Zeitplan, erkennt Restocks und meldet sie."""
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import kalender
import setliste
from filter import ART_NAMEN, art, ist_relevant, sprache
from netz import Blockiert, Verboten
from shops import LESER, VERFUEGBAR

log = logging.getLogger("waechter")

STATUS_TEXT = {"lieferbar": "lieferbar", "knapp": "nur noch wenige", "vorbestellbar": "vorbestellbar",
               "ausverkauft": "ausverkauft", "unbekannt": "Status unklar"}
EREIGNIS_TITEL = {
    "wieder_da": "🔔 Wieder da",
    "neu_bestellbar": "🆕 Neu & bestellbar",
    "vorverkauf": "📅 Vorverkauf offen",
    "neu_gelistet": "👀 Neu gelistet (noch nicht bestellbar)",
    "preis_runter": "💶 Preis gesenkt",
}
WICHTIGE_ARTEN = {"display", "display18", "etb", "bundle", "minitin_display"}
MAX_EINZELMELDUNGEN = 4


def _euro(x):
    return "Preis ?" if x is None else f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class Waechter:
    def __init__(self, konfig, speicher, melder):
        self.k, self.s, self.m = konfig, speicher, melder
        self.wecker = threading.Event()
        self.laeuft = True
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="shop")
        self.in_arbeit = set()
        self.sperre = threading.Lock()
        self.gestartet = time.time()
        self.naechste_news = 0.0

    # ------------------------------------------------------------ Zeitplan
    def shops_aktiv(self):
        shops = [s for s in self.k.daten["shops"] if s.get("aktiv")]
        if self.k.daten.get("merkliste"):
            shops.append({"id": "merkliste", "name": "Merkliste", "typ": "einzelseiten", "aktiv": True,
                          "quellen": self.k.daten["merkliste"], "intervall_min": max(5, self.k.daten["intervall_min"])})
        return shops

    def jetzt_pruefen(self):
        for shop in self.shops_aktiv():
            st = self.s.shop(shop["id"])
            st["naechster"] = 0
            self.s.shop_speichern(st)
        self.naechste_news = 0
        self.wecker.set()

    def schleife(self):
        log.info("Wächter läuft.")
        while self.laeuft:
            jetzt = time.time()
            for shop in self.shops_aktiv():
                with self.sperre:
                    if shop["id"] in self.in_arbeit:
                        continue
                    if jetzt < (self.s.shop(shop["id"])["naechster"] or 0):
                        continue
                    self.in_arbeit.add(shop["id"])
                self.pool.submit(self._shop_sicher, shop)
            if jetzt >= self.naechste_news:
                self.naechste_news = jetzt + 30 * 60
                self.pool.submit(self._news_und_releases_sicher)
            self.wecker.wait(5)
            self.wecker.clear()

    def einmal(self, melden=False):
        """Alle aktiven Shops einmal nacheinander prüfen (für Tests). Gibt Shop-Zustände zurück."""
        for shop in self.shops_aktiv():
            self._shop_pruefen(shop, melden=melden)
        return self.s.shops()

    # ------------------------------------------------------------ Shop prüfen
    def _shop_sicher(self, shop):
        try:
            self._shop_pruefen(shop)
        except Exception:  # noqa: BLE001
            log.exception("Unerwarteter Fehler bei %s", shop["id"])
        finally:
            with self.sperre:
                self.in_arbeit.discard(shop["id"])

    def _shop_pruefen(self, shop, melden=True):
        sid = shop["id"]
        st = self.s.shop(sid)
        beginn = time.time()
        ereignisse = []
        try:
            roh = LESER[shop["typ"]](shop)
            if roh:
                ereignisse, relevant = self._verarbeiten(shop, roh, basis=not st["basis_fertig"])
                st.update(ok=1, anzahl=len(roh), relevant=relevant, basis_fertig=1, fehler_in_folge=0,
                          meldung=f"{len(roh)} Produkte gelesen, {relevant} relevant")
            else:
                st.update(ok=2, anzahl=0, fehler_in_folge=st["fehler_in_folge"] + 1,
                          meldung="0 Produkte gefunden – Seitenaufbau geändert?")
        except Verboten as e:
            st.update(ok=0, fehler_in_folge=st["fehler_in_folge"] + 1, meldung=f"Nicht erlaubt: {e}")
        except Blockiert as e:
            st.update(ok=0, fehler_in_folge=st["fehler_in_folge"] + 1, meldung=f"Blockiert ({e}) – bitte manuell prüfen")
        except Exception as e:  # noqa: BLE001
            st.update(ok=0, fehler_in_folge=st["fehler_in_folge"] + 1, meldung=f"Fehler: {type(e).__name__}: {e}"[:300])
        intervall = float(shop.get("intervall_min") or self.k.daten["intervall_min"]) * 60
        if st["ok"] != 1:
            intervall = min(intervall * (2 ** min(st["fehler_in_folge"], 4)), 3600)
        st.update(zuletzt=time.time(), dauer=round(time.time() - beginn, 1),
                  naechster=time.time() + intervall * random.uniform(0.85, 1.15))
        self.s.shop_speichern(st)
        log.info("%-12s %s", sid, st["meldung"])
        if melden and ereignisse:
            self._melden(shop, ereignisse)
        return ereignisse

    def _verarbeiten(self, shop, roh, basis):
        sid, jetzt = shop["id"], time.time()
        ereignisse, relevant = [], 0
        for p in roh:
            if not p.get("merkliste") and not ist_relevant(p["titel"], p.get("pokemon_quelle")):
                continue
            relevant += 1
            schluessel = f"{sid}:{p['id']}"
            alt = self.s.produkt(schluessel)
            status = p["status"]
            neu = {
                "schluessel": schluessel, "shop": sid, "titel": p["titel"], "url": p["url"], "preis": p["preis"],
                "status": status, "sprache": sprache(p["titel"]), "art": art(p["titel"]),
                "haendler": p.get("haendler"), "bild": p.get("bild"), "merkliste": int(bool(p.get("merkliste"))),
                "erstmals": alt["erstmals"] if alt else jetzt,
                "zuletzt_gesehen": jetzt,
                "status_seit": alt["status_seit"] if alt and alt["status"] == status else jetzt,
                "zuletzt_lieferbar": jetzt if status in VERFUEGBAR else (alt["zuletzt_lieferbar"] if alt else None),
                "zuletzt_gemeldet": alt["zuletzt_gemeldet"] if alt else None,
            }
            e_art = None
            if alt is None:
                if not basis:
                    e_art = ("vorverkauf" if status == "vorbestellbar" else
                             "neu_bestellbar" if status in VERFUEGBAR else "neu_gelistet")
            elif status != alt["status"]:
                if status in VERFUEGBAR and alt["status"] == "ausverkauft":
                    e_art = "vorverkauf" if status == "vorbestellbar" else "wieder_da"
                elif status == "ausverkauft" and alt["status"] in VERFUEGBAR:
                    e_art = "ausverkauft"
            elif (status in VERFUEGBAR and p["preis"] and alt["preis"]
                  and p["preis"] <= alt["preis"] * 0.9):
                e_art = "preis_runter"
            if e_art:
                ereignisse.append((e_art, neu, alt))
            self.s.produkt_speichern(neu)
        return ereignisse, relevant

    # ------------------------------------------------------------ Melden
    def set_grund(self, titel, unbekannt_ok=None):
        """None, wenn das Set des Titels zur Auswahl passt (oder nichts ausgewählt ist), sonst der Grund."""
        d = self.k.daten
        gewaehlt = set(d.get("sets") or [])
        if not gewaehlt:
            return None
        sid = setliste.set_von(titel, d.get("eigene_sets"))
        if sid is None:
            ok = d.get("set_unbekannt_melden", False) if unbekannt_ok is None else unbekannt_ok
            return None if ok else "kein gewähltes Set erkannt"
        if sid not in gewaehlt:
            return f"Set {setliste.namen(d.get('eigene_sets')).get(sid, sid)} nicht gewählt"
        return None

    def _grund_gegen_meldung(self, e_art, p):
        d = self.k.daten
        if e_art == "ausverkauft":
            return "nur Protokoll"
        if not d["melden"].get(e_art, False):
            return "Ereignisart abgeschaltet"
        if p["merkliste"]:
            return None
        if p["sprache"] not in d["sprachen"]:
            return f"Sprache {p['sprache']} nicht gewählt"
        grund = self.set_grund(p["titel"])
        if grund:
            return grund
        if d.get("arten") and p["art"] not in d["arten"]:
            return f"Produktart {ART_NAMEN.get(p['art'], p['art'])} nicht gewählt"
        if p["haendler"] and p["haendler"].startswith("Marktplatz") and d.get("marktplatz_ignorieren", True):
            return "Marktplatz-Händler"
        grenze = d["preisgrenzen"].get(p["art"])
        if d.get("preisgrenze_aktiv") and grenze and p["preis"] and p["preis"] > grenze:
            return f"über Preisgrenze ({_euro(grenze)})"
        titel = p["titel"].lower()
        pflicht = [w.lower() for w in d.get("stichworte_pflicht") or [] if w.strip()]
        if pflicht and not any(w in titel for w in pflicht):
            return "Pflicht-Stichwort fehlt"
        if any(w.lower() in titel for w in d.get("stichworte_sperre") or [] if w.strip()):
            return "Sperr-Stichwort"
        if p["zuletzt_gemeldet"] and time.time() - p["zuletzt_gemeldet"] < d["abklingzeit_min"] * 60:
            return "Abklingzeit"
        return None

    def _melden(self, shop, ereignisse):
        zu_melden = []
        for e_art, p, alt in ereignisse:
            grund = self._grund_gegen_meldung(e_art, p)
            self.s.ereignis({"zeit": time.time(), "art": e_art, "schluessel": p["schluessel"], "shop": p["shop"],
                             "titel": p["titel"], "url": p["url"], "preis": p["preis"], "status": p["status"],
                             "sprache": p["sprache"], "produktart": p["art"], "gemeldet": int(grund is None),
                             "grund": grund or ""})
            if grund is None:
                zu_melden.append((e_art, p))
                p["zuletzt_gemeldet"] = time.time()
                self.s.produkt_speichern(p)
        if not zu_melden:
            return
        name = shop.get("name", shop["id"])
        if len(zu_melden) > MAX_EINZELMELDUNGEN:
            zeilen = [f"• {p['titel']} – {_euro(p['preis'])} ({STATUS_TEXT[p['status']]})" for _, p in zu_melden[:12]]
            if len(zu_melden) > 12:
                zeilen.append(f"… und {len(zu_melden) - 12} weitere")
            self.m.senden(f"🔔 {len(zu_melden)} Pokémon-Produkte bei {name}", "\n".join(zeilen),
                          url=shop.get("basis"), prio=5)
            return
        for e_art, p in zu_melden:
            wichtig = p["art"] in WICHTIGE_ARTEN
            prio = {"wieder_da": 5 if wichtig else 4, "neu_bestellbar": 5 if wichtig else 4,
                    "vorverkauf": 4, "neu_gelistet": 3, "preis_runter": 3}.get(e_art, 3)
            text = (f"{name} · {_euro(p['preis'])} · {STATUS_TEXT[p['status']]} · "
                    f"{ART_NAMEN.get(p['art'], p['art'])} · {p['sprache']}")
            self.m.senden(f"{EREIGNIS_TITEL[e_art]}: {p['titel']}", text, url=p["url"], prio=prio, bild=p["bild"])

    # ------------------------------------------------------------ News & Releases
    def _news_und_releases_sicher(self):
        try:
            self.news_pruefen()
        except Exception:  # noqa: BLE001
            log.exception("News-Prüfung fehlgeschlagen")
        try:
            self.releases_pruefen()
        except Exception:  # noqa: BLE001
            log.exception("Release-Prüfung fehlgeschlagen")

    def news_pruefen(self):
        d = self.k.daten
        for q in d.get("news_quellen", []):
            if not q.get("aktiv"):
                continue
            sid = "news:" + q["name"]
            st = self.s.shop(sid)
            try:
                eintraege = list(kalender.news_holen(q))
                st.update(ok=1, anzahl=len(eintraege), meldung=f"{len(eintraege)} Einträge")
            except Exception as e:  # noqa: BLE001
                st.update(ok=0, meldung=f"Fehler: {e}"[:300], zuletzt=time.time())
                self.s.shop_speichern(st)
                continue
            for e in eintraege:
                if not self.s.news_neu(e["link"]):
                    continue
                # News ohne erkennbares Set (z. B. allgemeiner Restock) bleiben erlaubt
                melden = (st["basis_fertig"] and e["treffer"] and d["melden"].get("news")
                          and time.time() - e["zeit"] < 3 * 86400
                          and self.set_grund(e["titel"], unbekannt_ok=True) is None)
                self.s.news_speichern({**e, "treffer": int(e["treffer"]), "gemeldet": int(bool(melden))})
                if melden:
                    self.m.senden(f"📰 {e['quelle']}", e["titel"], url=e["link"], prio=2)
            st.update(basis_fertig=1, zuletzt=time.time())
            self.s.shop_speichern(st)

    def releases_pruefen(self):
        d = self.k.daten
        if not d["melden"].get("releases"):
            return
        gewaehlt = set(d.get("sets") or [])
        for schluessel, text, r in kalender.faellige_erinnerungen(kalender.releases_laden(), d["sprachen"]):
            if self.s.erinnert(schluessel):
                continue
            if gewaehlt and r.get("set") not in gewaehlt and (r.get("set") or not d.get("set_unbekannt_melden")):
                continue
            self.s.erinnerung_merken(schluessel)
            self.m.senden(f"🗓️ {text}", f"{r.get('art', '')} · {r.get('sprache', '')} · {r.get('produkte', '')}",
                          prio=3)
