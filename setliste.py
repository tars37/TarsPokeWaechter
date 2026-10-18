"""Erkennt anhand des Produktnamens, zu welchem Set (Erweiterung) ein Produkt gehört.

Die Liste steht in sets.json (nach Reihen geordnet); eigene Sets aus der Konfiguration kommen dazu.
"""
import json
import re
import threading
from pathlib import Path

PFAD = Path(__file__).resolve().parent / "sets.json"

_sperre = threading.Lock()
_stand = {"mtime": None, "reihen": [], "eigene_key": None, "regeln": []}


def _eigene_als_reihe(eigene):
    sets = []
    for e in eigene or []:
        woerter = [w.strip() for w in str(e.get("suchworte", "")).split(",") if w.strip()]
        if not e.get("id") or not woerter:
            continue
        sets.append({"id": e["id"], "de": e.get("name") or woerter[0], "en": "", "code": "eigen",
                     "muster": [r"[\s-]?".join(re.escape(t) for t in w.split()) for w in woerter]})
    return {"name": "Eigene Sets", "jahre": "", "sets": sets} if sets else None


def reihen(eigene=None):
    """Alle Reihen inkl. eigener Sets, neu geladen, wenn sets.json geändert wurde."""
    with _sperre:
        mtime = PFAD.stat().st_mtime if PFAD.exists() else None
        key = json.dumps(eigene or [], sort_keys=True)
        if mtime != _stand["mtime"] or key != _stand["eigene_key"]:
            try:
                daten = json.loads(PFAD.read_text(encoding="utf-8"))["reihen"]
            except (OSError, ValueError, KeyError):
                daten = []
            eigen = _eigene_als_reihe(eigene)
            if eigen:
                daten = [eigen] + daten
            genau, basis = [], []
            for r in daten:
                for s in r["sets"]:
                    try:
                        rx = re.compile("|".join(f"(?:{m})" for m in s["muster"]), re.I)
                    except re.error:
                        continue
                    (basis if s.get("basis") else genau).append((s["id"], rx))
            _stand.update(mtime=mtime, reihen=daten, eigene_key=key, regeln=genau + basis)
        return _stand["reihen"]


def set_von(titel, eigene=None):
    """Set-ID des Produkts oder None. Eigene Sets und genaue Sets gehen vor Grundsets."""
    reihen(eigene)
    for sid, rx in _stand["regeln"]:
        if rx.search(titel or ""):
            return sid
    return None


def namen(eigene=None):
    """{set_id: "Delta-Herrschaft"}"""
    return {s["id"]: s["de"] for r in reihen(eigene) for s in r["sets"]}
