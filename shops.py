"""Shop-Leser. Jeder liefert eine Liste von Produkten:
{"id", "titel", "url", "preis", "status", "haendler", "bild", "pokemon_quelle"}
status: lieferbar | knapp | vorbestellbar | ausverkauft | unbekannt
"""
import html
import json
import re
from urllib.parse import quote_plus, urljoin, urlsplit

from netz import hole, hole_json

VERFUEGBAR = ("lieferbar", "knapp", "vorbestellbar")
_VORVERKAUF = re.compile(r"vorbestell|vorverkauf|pre-?order|verfügbar ab|erscheint am|erscheinungstermin", re.I)


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _preis_de(s):
    """'1.234,56' oder '209.90' -> float"""
    if s is None:
        return None
    s = str(s).strip().replace("\xa0", "").replace("€", "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        wert = round(float(s), 2)
    except ValueError:
        return None
    return wert if wert > 0 else None


# ---------------------------------------------------------------- Shopify
def shopify(shop):
    basis = shop["basis"].rstrip("/")
    seiten = shop.get("max_seiten", 3)
    produkte, gesehen = [], set()
    for quelle in shop["quellen"]:
        pfad = "/products.json" if quelle == "*" else f"/collections/{quote_plus(quelle)}/products.json"
        for seite in range(1, seiten + 1):
            daten = hole_json(f"{basis}{pfad}?limit=250&page={seite}")
            liste = daten.get("products", [])
            for p in liste:
                pid = str(p["id"])
                if pid in gesehen:
                    continue
                gesehen.add(pid)
                varianten = p.get("variants") or []
                verf = any(v.get("available") for v in varianten)
                preise = [_preis_de(v.get("price")) for v in varianten if v.get("price")]
                tags = p.get("tags") or []
                tags = tags if isinstance(tags, list) else str(tags).split(",")
                vorverkauf = _VORVERKAUF.search(p.get("title", "") + " " + " ".join(tags))
                status = ("vorbestellbar" if vorverkauf else "lieferbar") if verf else "ausverkauft"
                bilder = p.get("images") or []
                produkte.append({
                    "id": pid,
                    "titel": html.unescape(p.get("title", "")).strip(),
                    "url": f"{basis}/products/{p['handle']}",
                    "preis": min(preise) if preise else None,
                    "status": status,
                    "haendler": None,
                    "bild": bilder[0].get("src") if bilder else None,
                    "pokemon_quelle": bool(shop.get("pokemon_quelle")) and quelle != "*",
                })
            if len(liste) < 250:
                break
    return produkte


# ---------------------------------------------------------------- WooCommerce (Store-API)
def woocommerce(shop):
    basis = shop["basis"].rstrip("/")
    produkte = []
    for suche in shop["quellen"]:
        for seite in range(1, shop.get("max_seiten", 2) + 1):
            liste = hole_json(f"{basis}/wp-json/wc/store/v1/products?search={quote_plus(suche)}&per_page=100&page={seite}")
            for p in liste:
                pr = p.get("prices") or {}
                preis = None
                if pr.get("price"):
                    preis = int(pr["price"]) / (10 ** int(pr.get("currency_minor_unit", 2)))
                if p.get("is_in_stock") and p.get("is_purchasable", True):
                    status = "vorbestellbar" if p.get("is_on_backorder") or _VORVERKAUF.search(p.get("name", "")) else "lieferbar"
                    if p.get("low_stock_remaining"):
                        status = "knapp"
                else:
                    status = "ausverkauft"
                bilder = p.get("images") or []
                produkte.append({
                    "id": str(p["id"]),
                    "titel": _text(p.get("name", "")),
                    "url": p.get("permalink"),
                    "preis": preis,
                    "status": status,
                    "haendler": None,
                    "bild": bilder[0].get("src") if bilder else None,
                    "pokemon_quelle": False,
                })
            if len(liste) < 100:
                break
    return produkte


# ---------------------------------------------------------------- JTL-Shop (Gate to the Games, Card-Corner ...)
_JTL_TEILER = re.compile(r'itemtype="https?://schema\.org/Product"')


def _jtl_status(stueck):
    sig = re.search(r'signal_image\s+status-(\d)', stueck)
    if sig:
        return {"0": "ausverkauft", "1": "knapp", "2": "lieferbar"}.get(sig.group(1), "unbekannt")
    band = re.search(r'productbox-ribbon[^>]*>\s*([^<]+)', stueck)
    band = (band.group(1) if band else "").lower()
    if "ausverkauft" in band or "nicht verfügbar" in band:
        return "ausverkauft"
    if "vorbestell" in band or "vorverkauf" in band:
        return "vorbestellbar"
    if "auf lager" in band or "sofort" in band or "lieferbar" in band:
        return "lieferbar"
    text = _text(stueck).lower()
    knopf = "in den warenkorb" in text or "vorbestellen" in text
    if knopf and _VORVERKAUF.search(text):
        return "vorbestellbar"
    if "ausverkauft" in text or "nicht verfügbar" in text or "nicht lieferbar" in text:
        return "ausverkauft"
    if knopf:
        return "lieferbar"
    return "unbekannt"


def jtl(shop):
    basis = shop["basis"].rstrip("/")
    host = urlsplit(basis).netloc
    produkte, gesehen = [], set()
    for quelle in shop["quellen"]:
        url = urljoin(basis + "/", quelle)
        _, seite = hole(url)
        stuecke = _JTL_TEILER.split(seite)[1:]
        for st in stuecke:
            st = st[:20000]
            link = re.search(r'itemprop="url"\s+content="([^"]+)"', st)
            if not link:
                link = re.search(r'href="(https?://' + re.escape(host) + r'/[^"#?]+)"', st)
            if not link:
                continue
            purl = html.unescape(link.group(1))
            if purl in gesehen:
                continue
            gesehen.add(purl)
            name = re.search(r'itemprop="name"[^>]*>(.*?)</(?:div|h\d|span|a)>', st, re.S)
            titel = _text(name.group(1)) if name else ""
            if not titel:
                t = re.search(r'productbox-title[^>]*>(.*?)</div>', st, re.S)
                titel = _text(t.group(1)) if t else purl.rsplit("/", 1)[-1].replace("-", " ")
            preis = re.search(r'itemprop="price"\s+content="([\d.]+)"', st)
            if preis:
                preis = _preis_de(preis.group(1))
            else:
                p2 = re.search(r'(\d{1,4}(?:\.\d{3})*,\d{2})\s*(?:&nbsp;|\s)*(?:€|&euro;)', st)
                preis = _preis_de(p2.group(1)) if p2 else None
            bild = re.search(r'itemprop="image"\s+content="([^"]+)"', st)
            produkte.append({
                "id": purl.rsplit("/", 1)[-1],
                "titel": titel,
                "url": purl,
                "preis": preis,
                "status": _jtl_status(st),
                "haendler": None,
                "bild": bild.group(1) if bild else None,
                "pokemon_quelle": bool(shop.get("pokemon_quelle")),
            })
    return produkte


# ---------------------------------------------------------------- Müller (Next.js-Daten im Quelltext)
_MUELLER_PRODUKT = re.compile(
    r'"name":"((?:[^"\\]|\\.)*)","ownBrand":(?:true|false),"path":"(/p/[^"]+)",'
    r'"preOrderSettings":(null|\{[^{}]*\})')


def mueller(shop):
    basis = shop["basis"].rstrip("/")
    produkte, gesehen = [], set()
    for suche in shop["quellen"]:
        _, seite = hole(f"{basis}/search/?q={quote_plus(suche)}")
        daten = seite.replace('\\"', '"').replace("\\\\", "\\")
        for m in _MUELLER_PRODUKT.finditer(daten):
            pfad = m.group(2)
            if pfad in gesehen:
                continue
            gesehen.add(pfad)
            try:
                titel = json.loads('"' + m.group(1) + '"')
            except ValueError:
                titel = m.group(1)
            danach = daten[m.end():m.end() + 1500]
            lager = re.search(r'"stockLevelIndication":"(\w+)"', danach)
            davor = daten[max(0, m.start() - 2500):m.start()]
            preise = re.findall(r'"currentPrice":\{"currencyIso":"EUR","valueWithoutTax":[\d.]+,"valueWithTax":([\d.]+)', davor)
            bilder = re.findall(r'"image":\{"height":\d+,"url":"([^"]+)"', davor)
            lager = lager.group(1) if lager else ""
            status = {"IN_STOCK": "lieferbar", "LOW_IN_STOCK": "knapp", "OUT_OF_STOCK": "ausverkauft"}.get(lager, "unbekannt")
            if m.group(3) != "null" and status in ("lieferbar", "knapp"):
                status = "vorbestellbar"
            produkte.append({
                "id": pfad.rstrip("/").rsplit("-", 1)[-1],
                "titel": titel,
                "url": basis + pfad,
                "preis": float(preise[-1]) if preise else None,
                "status": status,
                "haendler": None,
                "bild": bilder[-1] if bilder else None,
                "pokemon_quelle": False,
            })
    return produkte


# ---------------------------------------------------------------- MediaMarkt / Saturn (Apollo-Zustand)
def _vorgeladen(seite):
    i = seite.find("__PRELOADED_STATE__")
    if i < 0:
        return {}
    s = seite.find("{", i)
    e = seite.find("</script>", s)
    roh = seite[s:e].rstrip().rstrip(";")
    roh = re.sub(r'(?<=[:\[,])undefined(?=[,\]}])', 'null', roh)
    try:
        return json.loads(roh).get("apolloState", {})
    except ValueError:
        return {}


def mediamarkt(shop):
    basis = shop["basis"].rstrip("/")
    produkte, gesehen = [], set()
    for suche in shop["quellen"]:
        _, seite = hole(f"{basis}/de/search.html?query={quote_plus(suche)}")
        zustand = _vorgeladen(seite)
        nach_id = {}
        for schluessel, wert in zustand.items():
            if not isinstance(wert, dict) or ":" not in schluessel:
                continue
            art, rest = schluessel.split(":", 1)
            if art.startswith("CofrPriceFeature"):
                rest = wert.get("id", rest)
            nach_id.setdefault(rest, {})[art] = wert
        for pid, teile in nach_id.items():
            kern = teile.get("CofrCoreFeature")
            if not kern or pid in gesehen:
                continue
            gesehen.add(pid)
            preis_t = teile.get("CofrPriceFeature") or {}
            online = teile.get("CofrOnlineStatusFeature") or {}
            verkaeufer = (preis_t.get("marketplaceSeller") or {}).get("sellerName")
            kaufbar = online.get("isAvailableAndBuyable")
            ostatus = (online.get("onlineStatus") or "").upper()
            if kaufbar:
                status = "vorbestellbar" if "PRE" in ostatus or online.get("releaseDate") else "lieferbar"
            elif kaufbar is False or ostatus:
                status = "ausverkauft"
            else:
                status = "unbekannt"
            medien = teile.get("CofrMediaAssetsFeature") or {}
            bild = (medien.get("productMainImage") or {}).get("link")
            produkte.append({
                "id": pid.rsplit(":", 1)[-1],
                "titel": kern.get("productName", ""),
                "url": urljoin(basis, kern.get("urlRelative") or ""),
                "preis": ((preis_t.get("price") or {}).get("amount")),
                "status": status,
                "haendler": f"Marktplatz: {verkaeufer}" if (verkaeufer or kern.get("isProductOfTypeMarketplace")) else None,
                "bild": bild,
                "pokemon_quelle": False,
            })
    return produkte


# ---------------------------------------------------------------- Proshop
def proshop(shop):
    basis = shop["basis"].rstrip("/")
    produkte, gesehen = [], set()
    for suche in shop["quellen"]:
        _, seite = hole(f"{basis}/?s={quote_plus(suche)}")
        for st in re.split(r'<li class="site-productlist-item', seite)[1:]:
            st = st[:15000]
            name = re.search(r'product-display-name>([^<]+)', st)
            link = re.search(r'<a class="show" href="([^"]+)"', st)
            if not name or not link:
                continue
            purl = urljoin(basis, html.unescape(link.group(1)))
            if purl in gesehen:
                continue
            gesehen.add(purl)
            icon = re.search(r'site-icon-stock-(\w+)', st)
            lagertext = re.search(r'site-stock-text">([^<]+)', st)
            lagertext = (lagertext.group(1) if lagertext else "").lower()
            if _VORVERKAUF.search(lagertext):
                status = "vorbestellbar"
            elif icon and icon.group(1) == "in":
                status = "lieferbar"
            elif icon:
                status = "ausverkauft"
            else:
                status = "unbekannt"
            preis = re.search(r'site-currency-lg">([\d.,]+)', st)
            produkte.append({
                "id": purl.rstrip("/").rsplit("/", 1)[-1],
                "titel": _text(name.group(1)),
                "url": purl,
                "preis": _preis_de(preis.group(1)) if preis else None,
                "status": status,
                "haendler": None,
                "bild": None,
                "pokemon_quelle": False,
            })
    return produkte


# ---------------------------------------------------------------- Einzelne Produktseiten (eigene Links)
_VERF_SCHEMA = {
    "instock": "lieferbar", "limitedavailability": "knapp", "onlineonly": "lieferbar",
    "preorder": "vorbestellbar", "presale": "vorbestellbar", "backorder": "vorbestellbar",
    "outofstock": "ausverkauft", "soldout": "ausverkauft", "discontinued": "ausverkauft",
    "instoreonly": "ausverkauft",
}


def _ld_objekte(seite):
    for roh in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', seite, re.S | re.I):
        try:
            daten = json.loads(roh.strip())
        except ValueError:
            continue
        stapel = [daten]
        while stapel:
            o = stapel.pop()
            if isinstance(o, list):
                stapel.extend(o)
            elif isinstance(o, dict):
                yield o
                stapel.extend(v for v in o.values() if isinstance(v, (dict, list)))


def produktseite(url):
    _, seite = hole(url)
    titel, preis, status = None, None, "unbekannt"
    for o in _ld_objekte(seite):
        typ = o.get("@type")
        typ = typ if isinstance(typ, list) else [typ]
        if "Product" in typ and not titel:
            titel = o.get("name")
        if "Offer" in typ or "AggregateOffer" in typ:
            v = str(o.get("availability") or "").rsplit("/", 1)[-1].lower()
            if v in _VERF_SCHEMA and status == "unbekannt":
                status = _VERF_SCHEMA[v]
            if preis is None:
                preis = _preis_de(o.get("price") or o.get("lowPrice"))
    if status == "unbekannt":
        m = re.search(r'itemprop="availability"[^>]*(?:href|content)="([^"]+)"', seite)
        if m:
            status = _VERF_SCHEMA.get(m.group(1).rsplit("/", 1)[-1].lower(), "unbekannt")
    if status == "unbekannt":
        t = _text(seite[:400000]).lower()
        if re.search(r"ausverkauft|nicht (mehr )?verfügbar|nicht lieferbar|currently unavailable|out of stock|sold out", t):
            status = "ausverkauft"
        elif re.search(r"in den warenkorb|add to cart|jetzt kaufen", t):
            status = "vorbestellbar" if _VORVERKAUF.search(t) else "lieferbar"
    if not titel:
        m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', seite) or re.search(r"<title>(.*?)</title>", seite, re.S)
        titel = _text(m.group(1)) if m else url
    if preis is None:
        m = re.search(r'itemprop="price"[^>]*content="([\d.,]+)"', seite)
        preis = _preis_de(m.group(1)) if m else None
    return {"titel": html.unescape(titel), "preis": preis, "status": status}


def einzelseiten(shop):
    produkte = []
    for eintrag in shop["quellen"]:
        url = eintrag["url"] if isinstance(eintrag, dict) else eintrag
        try:
            info = produktseite(url)
        except Exception as e:  # noqa: BLE001 - ein gesperrter Link soll die anderen nicht aufhalten
            info = {"titel": url, "preis": None, "status": "unbekannt", "fehler": f"{type(e).__name__}: {e}"}
        produkte.append({
            "id": url,
            "titel": (eintrag.get("name") if isinstance(eintrag, dict) and eintrag.get("name") else info["titel"]),
            "url": url,
            "preis": info["preis"],
            "status": info["status"],
            "haendler": urlsplit(url).netloc.removeprefix("www.") + (f" – {info['fehler']}" if info.get("fehler") else ""),
            "bild": None,
            "pokemon_quelle": True,
            "merkliste": True,
        })
    return produkte


LESER = {
    "shopify": shopify,
    "woocommerce": woocommerce,
    "jtl": jtl,
    "mueller": mueller,
    "mediamarkt": mediamarkt,
    "proshop": proshop,
    "einzelseiten": einzelseiten,
}
