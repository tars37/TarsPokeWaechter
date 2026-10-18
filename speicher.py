"""SQLite-Speicher: Produktzustände, Ereignisse, Shop-Gesundheit, News, Erinnerungen."""
import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS produkte(
  schluessel TEXT PRIMARY KEY, shop TEXT, titel TEXT, url TEXT, preis REAL, status TEXT,
  sprache TEXT, art TEXT, haendler TEXT, bild TEXT, merkliste INT DEFAULT 0,
  erstmals REAL, zuletzt_gesehen REAL, status_seit REAL, zuletzt_lieferbar REAL, zuletzt_gemeldet REAL);
CREATE TABLE IF NOT EXISTS ereignisse(
  id INTEGER PRIMARY KEY AUTOINCREMENT, zeit REAL, art TEXT, schluessel TEXT, shop TEXT, titel TEXT,
  url TEXT, preis REAL, status TEXT, sprache TEXT, produktart TEXT, gemeldet INT, grund TEXT);
CREATE TABLE IF NOT EXISTS shops(
  shop TEXT PRIMARY KEY, zuletzt REAL, ok INT, meldung TEXT, anzahl INT, relevant INT,
  basis_fertig INT DEFAULT 0, fehler_in_folge INT DEFAULT 0, naechster REAL DEFAULT 0, dauer REAL);
CREATE TABLE IF NOT EXISTS news(
  link TEXT PRIMARY KEY, titel TEXT, quelle TEXT, zeit REAL, treffer INT, gemeldet INT);
CREATE TABLE IF NOT EXISTS erinnerungen(schluessel TEXT PRIMARY KEY, zeit REAL);
CREATE INDEX IF NOT EXISTS ix_ereignisse_zeit ON ereignisse(zeit);
"""


class Speicher:
    def __init__(self, pfad):
        self.db = sqlite3.connect(pfad, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.sperre = threading.RLock()
        with self.sperre:
            self.db.executescript(_SCHEMA)
            self.db.commit()

    def _q(self, sql, args=()):
        with self.sperre:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def _x(self, sql, args=()):
        with self.sperre:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    # --- Produkte
    def produkt(self, schluessel):
        r = self._q("SELECT * FROM produkte WHERE schluessel=?", (schluessel,))
        return r[0] if r else None

    def produkt_speichern(self, p):
        felder = list(p.keys())
        self._x(f"INSERT OR REPLACE INTO produkte({','.join(felder)}) VALUES({','.join('?' * len(felder))})",
                [p[f] for f in felder])

    def produkte(self, shops=None):
        sql = "SELECT * FROM produkte"
        if shops is not None:
            if not shops:
                return []
            sql += f" WHERE shop IN ({','.join('?' * len(shops))})"
            return self._q(sql + " ORDER BY status_seit DESC", list(shops))
        return self._q(sql + " ORDER BY status_seit DESC")

    def produkt_loeschen(self, schluessel):
        self._x("DELETE FROM produkte WHERE schluessel=?", (schluessel,))

    # --- Ereignisse
    def ereignis(self, e):
        felder = list(e.keys())
        cur = self._x(f"INSERT INTO ereignisse({','.join(felder)}) VALUES({','.join('?' * len(felder))})",
                      [e[f] for f in felder])
        return cur.lastrowid

    def ereignisse(self, limit=200):
        return self._q("SELECT * FROM ereignisse ORDER BY zeit DESC, id DESC LIMIT ?", (limit,))

    # --- Shops
    def shop(self, sid):
        r = self._q("SELECT * FROM shops WHERE shop=?", (sid,))
        return r[0] if r else {"shop": sid, "zuletzt": None, "ok": None, "meldung": "", "anzahl": 0,
                               "relevant": 0, "basis_fertig": 0, "fehler_in_folge": 0, "naechster": 0, "dauer": None}

    def shop_speichern(self, s):
        felder = list(s.keys())
        self._x(f"INSERT OR REPLACE INTO shops({','.join(felder)}) VALUES({','.join('?' * len(felder))})",
                [s[f] for f in felder])

    def shops(self):
        return {r["shop"]: r for r in self._q("SELECT * FROM shops")}

    # --- News
    def news_neu(self, link):
        return not self._q("SELECT 1 FROM news WHERE link=?", (link,))

    def news_speichern(self, n):
        self._x("INSERT OR IGNORE INTO news(link,titel,quelle,zeit,treffer,gemeldet) VALUES(?,?,?,?,?,?)",
                (n["link"], n["titel"], n["quelle"], n["zeit"], n["treffer"], n["gemeldet"]))

    def news(self, limit=60):
        return self._q("SELECT * FROM news ORDER BY zeit DESC LIMIT ?", (limit,))

    # --- Erinnerungen (Release-Termine)
    def erinnert(self, schluessel):
        return bool(self._q("SELECT 1 FROM erinnerungen WHERE schluessel=?", (schluessel,)))

    def erinnerung_merken(self, schluessel):
        self._x("INSERT OR IGNORE INTO erinnerungen VALUES(?,?)", (schluessel, time.time()))
