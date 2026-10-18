"""HTTP-Zugriff: höflich (robots.txt, Mindestabstand je Host), ohne Fremdbibliotheken."""
import gzip
import json
import re
import threading
import time
import urllib.error
import urllib.request
import zlib
from urllib.parse import urlsplit

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")
ROBOTS_GUELTIG_S = 12 * 3600
MIN_ABSTAND_S = 3.0
MAX_CRAWL_DELAY_S = 30.0


class Blockiert(Exception):
    """Der Shop verweigert den Zugriff (Bot-Schutz, 403, 429 ...)."""


class Verboten(Exception):
    """robots.txt untersagt diese Adresse - wir halten uns daran."""


class Robots:
    """robots.txt-Regeln für 'User-agent: *' mit Platzhaltern (* und $), längste Regel gewinnt."""

    def __init__(self, text):
        self.regeln = []
        self.verzoegerung = 0.0
        gruppen, agenten, regeln, verz, vorher_regel = [], [], [], None, False
        for zeile in text.splitlines():
            zeile = zeile.split("#", 1)[0].strip()
            if ":" not in zeile:
                continue
            feld, wert = (t.strip() for t in zeile.split(":", 1))
            feld = feld.lower()
            if feld == "user-agent":
                if vorher_regel:
                    gruppen.append((agenten, regeln, verz))
                    agenten, regeln, verz = [], [], None
                agenten.append(wert.lower())
                vorher_regel = False
            elif feld in ("allow", "disallow"):
                vorher_regel = True
                if wert:
                    regeln.append((feld == "allow", wert))
            elif feld == "crawl-delay":
                vorher_regel = True
                try:
                    verz = float(wert)
                except ValueError:
                    pass
        gruppen.append((agenten, regeln, verz))
        for agenten, regeln, verz in gruppen:
            if "*" in agenten:
                for erlaubt, muster in regeln:
                    self.regeln.append((erlaubt, len(muster), self._regex(muster)))
                if verz:
                    self.verzoegerung = max(self.verzoegerung, verz)

    @staticmethod
    def _regex(muster):
        anker = muster.endswith("$")
        if anker:
            muster = muster[:-1]
        r = "".join(".*" if z == "*" else re.escape(z) for z in muster)
        return re.compile(r + ("$" if anker else ""))

    def erlaubt(self, pfad):
        bestes = None
        for erlaubt, laenge, rx in self.regeln:
            if rx.match(pfad) and (bestes is None or laenge > bestes[1] or (laenge == bestes[1] and erlaubt)):
                bestes = (erlaubt, laenge)
        return True if bestes is None else bestes[0]


_host_sperren: dict[str, threading.Lock] = {}
_host_zuletzt: dict[str, float] = {}
_robots: dict[str, tuple[float, Robots | None]] = {}
_global = threading.Lock()


def _sperre(host):
    with _global:
        return _host_sperren.setdefault(host, threading.Lock())


def _roh(url, timeout=25, accept="text/html,application/json;q=0.9,*/*;q=0.8"):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        "Accept-Encoding": "gzip, deflate",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            daten, kopf, status = r.read(), r.headers, r.status
    except urllib.error.HTTPError as e:
        try:
            daten = e.read()
        except Exception:
            daten = b""
        kopf, status = e.headers, e.code
    enc = ((kopf.get("Content-Encoding") if kopf else "") or "").lower()
    if enc == "gzip":
        daten = gzip.decompress(daten)
    elif enc == "deflate":
        daten = zlib.decompress(daten)
    ctype = (kopf.get("Content-Type") if kopf else "") or ""
    zeichensatz = "utf-8"
    if "charset=" in ctype:
        zeichensatz = ctype.split("charset=")[-1].split(";")[0].strip().strip('"') or "utf-8"
    try:
        text = daten.decode(zeichensatz, "replace")
    except LookupError:
        text = daten.decode("utf-8", "replace")
    return status, text


def _robots_fuer(url):
    teile = urlsplit(url)
    basis = f"{teile.scheme}://{teile.netloc}"
    jetzt = time.time()
    eintrag = _robots.get(basis)
    if eintrag and jetzt - eintrag[0] < ROBOTS_GUELTIG_S:
        return eintrag[1]
    try:
        status, text = _roh(basis + "/robots.txt", timeout=15, accept="text/plain,*/*")
        rob = Robots(text) if status == 200 else None
    except Exception:
        rob = None
    _robots[basis] = (jetzt, rob)
    return rob


def erlaubt(url):
    rob = _robots_fuer(url)
    if rob is None:
        return True
    teile = urlsplit(url)
    return rob.erlaubt((teile.path or "/") + ("?" + teile.query if teile.query else ""))


def hole(url, timeout=25, accept="text/html,application/json;q=0.9,*/*;q=0.8"):
    """Lädt eine Seite. Wirft Verboten/Blockiert, sonst (status, text)."""
    if not erlaubt(url):
        raise Verboten("robots.txt untersagt diese Adresse")
    rob = _robots_fuer(url)
    abstand = min(max(MIN_ABSTAND_S, rob.verzoegerung if rob else 0), MAX_CRAWL_DELAY_S)
    host = urlsplit(url).netloc
    with _sperre(host):
        warte = _host_zuletzt.get(host, 0) + abstand - time.time()
        if warte > 0:
            time.sleep(warte)
        try:
            status, text = _roh(url, timeout=timeout, accept=accept)
        finally:
            _host_zuletzt[host] = time.time()
    if status in (401, 403, 429) or (status == 503 and "cloudflare" in text[:5000].lower()):
        raise Blockiert(f"HTTP {status}")
    if status == 202 and len(text) < 5000:
        raise Blockiert("HTTP 202 (Bot-Prüfung)")
    kopf = text[:6000].lower()
    if (status == 200 and len(text) < 60000 and "<html" in kopf
            and ("cf-chl" in kopf or "challenge-platform" in kopf or "captcha" in kopf)):
        raise Blockiert("Bot-Prüfung (Captcha)")
    return status, text


def hole_json(url, timeout=25):
    status, text = hole(url, timeout=timeout, accept="application/json,*/*;q=0.5")
    if status != 200:
        raise RuntimeError(f"HTTP {status}")
    return json.loads(text)


def sende_json(url, nutzlast, kopf=None, timeout=15):
    """POST mit JSON-Körper (für Benachrichtigungsdienste)."""
    daten = json.dumps(nutzlast).encode("utf-8")
    k = {"Content-Type": "application/json", "User-Agent": "TarsPokeWaechter/1.0"}
    k.update(kopf or {})
    req = urllib.request.Request(url, data=daten, headers=k, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status
