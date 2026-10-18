"""Was ist ein relevantes Pokémon-Produkt (versiegelt), in welcher Sprache, welche Art?"""
import re

_POKEMON = re.compile(r"pok[eé]mon", re.I)

_ANDERE_TCG = re.compile(
    r"one piece|magic:? the gathering|\bmtg\b|yu-?gi-?oh|lorcana|dragon ?ball|digimon|flesh and blood|"
    r"star wars unlimited|weiss schwarz|union arena|riftbound|gundam|altered|sorcery|metazoo|grand archive",
    re.I)

_VERSIEGELT = re.compile(
    r"display|booster|bundle|top[- ]?trainer|elite[- ]?trainer|\betb\b|\btins?\b|tin-?box|blister|"
    r"kollektion|collection|premium|build\s*(&|and|und)\s*battle|kampfdeck|battle[- ]deck|liga|"
    r"deck\b|starter|sleeved|\bpacks?\b|\bupc\b|gem pack|special set|card set|box\b|"
    r"adventskalender|advent calendar|ordner-kollektion|binder collection|sammelkoffer|geschenk",
    re.I)

_AUSSCHLUSS = re.compile(
    r"einzelkarte|single card|\bpsa\b|\bcgc\b|\bbgs\b|\baog\b|graded|gegradet|\b\d{1,3}/\d{1,3}\b|#\d{2,}|"
    r"sleeves?\b|kartenh(ü|ue)llen|h(ü|ue)llen|deck[- ]?box|deck[- ]?case|spielmatte|playmat|toploader|"
    r"\balbum\b|protector|4d build|battle spinner|battle disc|clip ?'?n'? ?go|bettw(ä|ae)sche|toniebox|memory|"
    r"\bbinder\b|\bportfolio\b|pl(ü|ue)sch|kuscheltier|figur(?!en-kollektion)|sticker|\bbuch\b|puzzle|lego|"
    r"mega construx|t-shirt|tasse|gl(ä|ae)ser|rucksack|kostüm|nintendo switch|lampe|"
    r"mystery|repack|\bleer(e|es|er)?\b|empty box|proxy|fake|nachdruck|"
    r"magnetic|acryl|acrylic|case\b|schutzbox|aufbewahrung|storage|ultra pro|dragon shield|"
    r"spielzeug|battle figure|clip ?n ?go|malblock|kreativblock|enzyklop(ä|ae)die|socken|m(ü|ue)tze|"
    r"tasche|shopper|funko|bitty pop|sandwich|brotdose|lunchbox|fan-box|\bglass?\b|trinkflasche",
    re.I)

_SPRACHEN = [
    ("CN", re.compile(r"chines|\(cn\)|\bcn\b|\bchn\b|simplified|csv\d|\bcs\d|cbb\d|gem pack", re.I)),
    ("KR", re.compile(r"korean|koreanisch|\(kr\)|\bkr\b|\bkor\b", re.I)),
    ("TH", re.compile(r"thai|\(th\)", re.I)),
    ("JP", re.compile(r"japan|japanisch|\(jp\)|\bjp\b|\bjap\b|\(m\d+[a-z]?\)|\bm\d+[a-z]?\b|\bsv\d+[a-z]?\b|"
                      r"storm emeralda|munikis|ninja spinner|abyss eye|aura seeker|mega dream|mega brave|mega symphonia", re.I)),
    ("DE", re.compile(r"deutsch|\(de\)|\bde\b|german|karmesin|purpur|mega[- ]?entwicklung|delta[- ]herrschaft|"
                      r"entwicklungen in paldea|obsidianflammen|paradoxrift|gewalten der zeit|nacht in flammen|"
                      r"stunde der w(ä|ae)chter|welten im wandel|drachenwandel|schwarze flamme|wei(ß|ss)e blitze|"
                      r"wachsendes chaos|optimale ordnung|fatale flammen|erhabene helden|dunkelnacht|ewige rivalen|"
                      r"reisegef(ä|ae)hrten|prismatische|stellarkrone|st(ü|ue)rmische funken|30 jahre|top[- ]trainer|"
                      r"kollektion|sammelkartenspiel|boosterbundle|kampfdeck|nebel der sagen|maskerade", re.I)),
    ("EN", re.compile(r"englisch|english|\(en\)|\ben\b|\(eng\)|\beng\b|scarlet|violet|mega evolution|delta reign|"
                      r"perfect order|first partner|\bcollection\b|twilight masquerade|rebel clash|paldea evolved|"
                      r"obsidian flames|paradox rift|temporal forces|shrouded fable|"
                      r"chaos rising|phantasmal|ascended heroes|destined rivals|journey together|prismatic|"
                      r"30th celebration|pitch black|elite trainer|booster bundle|black bolt|white flare|"
                      r"surging sparks|stellar crown|trading card game", re.I)),
]

_ARTEN = [
    ("minitin_display", re.compile(r"mini[- ]?tin.*display|display.*mini[- ]?tin", re.I)),
    ("display18", re.compile(r"display.*\b18\b|\b18er\b|18 booster", re.I)),
    ("display", re.compile(r"display|booster[- ]?box|36 booster|36er", re.I)),
    ("etb", re.compile(r"top[- ]?trainer|elite[- ]?trainer|\betb\b", re.I)),
    ("bundle", re.compile(r"bundle", re.I)),
    ("blister", re.compile(r"blister|checklane|sleeved", re.I)),
    ("tin", re.compile(r"\btins?\b|tin-?box", re.I)),
    ("deck", re.compile(r"deck|build\s*(&|and|und)\s*battle|starter", re.I)),
    ("kollektion", re.compile(r"kollektion|collection|premium|\bupc\b|box|set\b|geschenk|adventskalender|advent", re.I)),
    ("booster", re.compile(r"booster|\bpacks?\b", re.I)),
]

ART_NAMEN = {
    "display": "Display (36er)", "display18": "Display (18er)", "minitin_display": "Mini-Tin-Display",
    "etb": "Top-Trainer-Box", "bundle": "Booster-Bundle", "blister": "Blister", "tin": "Tin-Box",
    "deck": "Deck", "kollektion": "Kollektion", "booster": "Booster", "sonstiges": "Sonstiges",
}

STANDARD_PREISGRENZEN = {
    "display": 230, "display18": 130, "minitin_display": 140, "etb": 75, "bundle": 50,
    "blister": 25, "tin": 35, "deck": 40, "kollektion": 160, "booster": 8, "sonstiges": 200,
}


_TCG_BELEG = re.compile(
    r"tcg|sammelkarten|trading card|karten|booster|display|top[- ]?trainer|elite[- ]?trainer|\betb\b|blister|"
    r"kollektion|collection|\btins?\b|tin-?box|bundle|kampfdeck|battle deck|build\s*(&|and|und)\s*battle|"
    r"premium|sleeved|\bupc\b", re.I)


def ist_relevant(titel, pokemon_quelle=False):
    """pokemon_quelle: die Liste stammt aus einer reinen Pokémon-Karten-Kategorie des Shops."""
    if not titel or _ANDERE_TCG.search(titel):
        return False
    if not (pokemon_quelle or _POKEMON.search(titel)):
        return False
    if _AUSSCHLUSS.search(titel) or not _VERSIEGELT.search(titel):
        return False
    return pokemon_quelle or bool(_TCG_BELEG.search(titel))


def sprache(titel):
    for kuerzel, rx in _SPRACHEN:
        if rx.search(titel):
            return kuerzel
    return "?"


def art(titel):
    for name, rx in _ARTEN:
        if rx.search(titel):
            return name
    return "sonstiges"
