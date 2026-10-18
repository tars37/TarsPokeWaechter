"""Zeichnet das App-Symbol (Pokéball auf dunklem Grund) als PNG und ICO – nur Standardbibliothek.

Aufruf:  py werkzeuge/symbol_bauen.py   → web/icon-256.png, web/icon-192.png, web/icon.ico
"""
import struct
import zlib
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
DUNKEL, ROT, WEISS, GELB = (22, 24, 29), (227, 53, 13), (255, 255, 255), (255, 203, 5)


def _farbe(x, y):
    """Farbe im 64er-Raster des SVG-Symbols (None = durchsichtig)."""
    r = 14  # abgerundete Ecken
    ex = max(r - x, 0, x - (64 - r))
    ey = max(r - y, 0, y - (64 - r))
    if ex * ex + ey * ey > r * r:
        return None
    gx, gy = x - 50, y - 14
    if gx * gx + gy * gy <= 8 * 8:
        return GELB if gx * gx + gy * gy <= 6 * 6 else DUNKEL
    dx, dy = x - 32, y - 32
    d2 = dx * dx + dy * dy
    if d2 > 24 * 24:
        return DUNKEL
    if d2 <= 5.5 * 5.5:
        return WEISS
    if d2 <= 9.5 * 9.5 or 30 <= y <= 34:
        return DUNKEL
    return ROT if y < 32 else WEISS


def png(groesse, stufen=4):
    zeilen = bytearray()
    for py in range(groesse):
        zeilen.append(0)
        for px in range(groesse):
            summe, deckend = [0, 0, 0], 0
            for sy in range(stufen):
                for sx in range(stufen):
                    f = _farbe((px + (sx + 0.5) / stufen) * 64 / groesse, (py + (sy + 0.5) / stufen) * 64 / groesse)
                    if f:
                        deckend += 1
                        summe = [a + b for a, b in zip(summe, f)]
            n = stufen * stufen
            if deckend:
                zeilen += bytes(round(c / deckend) for c in summe) + bytes([round(255 * deckend / n)])
            else:
                zeilen += b"\0\0\0\0"

    def block(art, daten):
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)

    kopf = struct.pack(">IIBBBBB", groesse, groesse, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + block(b"IHDR", kopf) + block(b"IDAT", zlib.compress(bytes(zeilen), 9)) + block(b"IEND", b"")


def ico(bilder):
    """ICO mit eingebetteten PNGs (ab Windows Vista unterstützt)."""
    kopf = struct.pack("<HHH", 0, 1, len(bilder))
    versatz = 6 + 16 * len(bilder)
    eintraege, daten = b"", b""
    for groesse, roh in bilder:
        g = 0 if groesse >= 256 else groesse
        eintraege += struct.pack("<BBBBHHII", g, g, 0, 0, 1, 32, len(roh), versatz + len(daten))
        daten += roh
    return kopf + eintraege + daten


if __name__ == "__main__":
    gross, mittel, klein = png(256), png(192), png(48)
    (WEB / "icon-256.png").write_bytes(gross)
    (WEB / "icon-192.png").write_bytes(mittel)
    (WEB / "icon.ico").write_bytes(ico([(256, gross), (48, klein)]))
    print("Symbole geschrieben nach", WEB)
