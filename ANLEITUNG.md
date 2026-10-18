# TarsPokeWächter – Restock-Wecker für Pokémon-Karten

Der TarsPokeWächter läuft auf deinem PC und prüft alle paar Minuten seriöse Shops. Sobald ein Pokémon-Produkt
(Display, Top-Trainer-Box, Bundle, Blister, Kollektion …) **wieder da**, **neu gelistet** oder **vorbestellbar** ist,
bekommst du eine Push-Nachricht aufs Handy und eine Meldung am PC. Ein Tipp darauf öffnet direkt die Shopseite.

## Starten

- **`TarsPokeWaechter starten.bat`** doppelklicken. Der Wächter läuft dann still im Hintergrund, und das Dashboard
  öffnet sich im Browser: http://127.0.0.1:8787/
- **`Autostart einrichten.bat`**: Danach startet der Wächter bei jeder Windows-Anmeldung automatisch.
  Rückgängig machen geht mit `Autostart entfernen.bat`.
- **`Shops einmal pruefen.bat`**: Prüft alle Shops einmal und zeigt das Ergebnis. Dabei wird nichts gesendet.

Benötigt wird nur Python (ist installiert), keine weiteren Pakete.

## Ohne PC: Cloud-Version auf GitHub

Dieselbe App läuft auch kostenlos auf GitHub, etwa alle 10 Minuten. Dann muss der PC nicht an sein.

- `cloud_lauf.py` macht einen Durchlauf, `.github/workflows/waechter.yml` startet ihn regelmäßig.
- Die **Statusseite** liegt unter `https://<dein-name>.github.io/TarsPokeWaechter/` und lässt sich auf dem Handy wie eine App
  auf den Startbildschirm legen.
- **Sets** wählst du dort im Reiter „Meine Sets“ und übernimmst sie mit „Kopieren“ und „auswahl.json bearbeiten“.
- **Sonstige Einstellungen** stehen in `einstellungen.json`.
- Das **ntfy-Thema** liegt als GitHub-Geheimnis `NTFY_THEMA` und erscheint nie auf der öffentlichen Seite.
- MediaMarkt, Proshop und Spiele Max sperren GitHub-Server (getestet am 18.10.2026). Deshalb ist die Arbeit aufgeteilt:
  **Die Cloud** prüft Gate, Card-Corner, TCGViert, CardCosmos, Elbenwald, Müller, die News und die Termine.
  **Der PC** prüft, wenn er an ist, nur MediaMarkt, Proshop und Spiele Max. So kommt keine Meldung doppelt.
  Schaltest du am PC wieder mehr Shops an, bekommst du deren Meldungen doppelt.
- GitHub startet geplante Läufe nicht minutengenau. Meist liegen 10 bis 15 Minuten dazwischen.

## Push aufs Handy (einmalig, 2 Minuten)

1. App **ntfy** installieren (kostenlos, ohne Konto):
   [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) ·
   [iPhone](https://apps.apple.com/app/ntfy/id1625396347)
2. Im Dashboard den Reiter **„Handy & Einstellungen“** öffnen und den QR-Code scannen,
   oder in der App auf **+** tippen und das dort angezeigte Thema abonnieren. In der App kannst du dem Abo den Anzeigenamen „TarsPokeWächter“ geben.
3. **„Test-Push senden“** drücken. Das Handy sollte sofort klingeln.

Das Thema ist dein privater Kanal. Wer den Namen kennt, kann mitlesen, also nicht öffentlich posten.
Optional gehen Meldungen auch an Telegram oder Discord (Einstellungen).

## Was wird gemeldet?

| Meldung | Bedeutung |
|---|---|
| 🔔 Wieder da | War ausverkauft und ist jetzt wieder bestellbar (Restock) |
| 🆕 Neu & bestellbar | Neues Produkt im Shop, sofort bestellbar |
| 📅 Vorverkauf offen | Vorbestellung möglich (oft Tage oder Wochen vor dem Release) |
| 👀 Neu gelistet | Neues Produkt im Shop, aber noch nicht bestellbar. Es kommt also bald |
| 🗓️ Release-Erinnerung | 7 Tage vorher, 1 Tag vorher und am Erscheinungstag |
| 📰 News & Deals | Passende Beiträge von mydealz (Pokémon-Gruppe), Pokézentrum, PokeBeach |

### Nur bestimmte Sets oder Reihen

Im Reiter **„Meine Sets“** wählst du aus, was dich interessiert:

- **einzelne Sets**, z. B. nur *Delta-Herrschaft*, oder **eine ganze Reihe** mit einem Haken
  (Mega-Entwicklung, Karmesin & Purpur, Schwert & Schild, Sonne & Mond, japanische Sets, China-Sets).
  Deutsche und englische Ausgabe zählen zum selben Set („Fatale Flammen“ = „Phantasmal Flames“).
- **Produkte ohne festes Set** (Kollektionen, Tins, Blister, „Erste Partner“) kannst du extra dazunehmen.
- **Produktarten**, z. B. nur Displays und Top-Trainer-Boxen.
- **Eigene Sets** für Neuankündigungen, die noch nicht in der Liste stehen: Name und Suchworte eintragen, fertig.

Ist nichts ausgewählt, wird alles gemeldet. Die Auswahl gilt auch für News und Release-Erinnerungen.
Unter „Verfügbar“ kannst du per Auswahlfeld nach Set filtern. Die Set-Liste selbst steht in `sets.json`.

Schutz vor Nerv-Meldungen:

- **Preisgrenzen**: Angebote über deiner Grenze werden nicht gemeldet, z. B. ein 36er-Display über 230 €.
  Damit fallen Scalper-Preise raus. Die Grenzen sind einstellbar.
- **Sprachen**: Standard ist Deutsch, Englisch und „unbekannt“. Japanisch, Chinesisch und Koreanisch lassen sich zuschalten.
- **Marktplatz-Händler** (Drittanbieter bei MediaMarkt) werden standardmäßig ignoriert.
- **Abklingzeit**: Dasselbe Produkt wird höchstens alle 60 Minuten gemeldet.
- **Erster Durchlauf**: Beim allerersten Prüfen merkt sich der Wächter nur den Ist-Zustand. Gemeldet werden erst Änderungen danach.
- Im Reiter **„Meldungen“** steht bei jeder Änderung, ob sie gesendet wurde und warum nicht.

## Überwachte Shops

| Shop | Art | Wie |
|---|---|---|
| Gate to the Games | TCG-Fachhandel | Kategorieseiten (Displays, Booster, Sonderboxen, Tins) |
| Card-Corner | TCG-Fachhandel | Kategorien „Pokémon Deutsch/Englisch“ |
| TCGViert | TCG-Fachhandel | kompletter Katalog (Shop-Datenschnittstelle) |
| CardCosmos | TCG-Fachhandel | Pokémon-Kategorien (Shop-Datenschnittstelle) |
| Elbenwald | große Kette | Kategorie Sammelkarten |
| Müller | große Kette | Suche „Pokémon Sammelkartenspiel/Booster/Top-Trainer-Box“ |
| MediaMarkt | große Kette | Suche (Marktplatz-Händler werden markiert) |
| Proshop | großer Händler | Suche |
| Spiele Max | große Kette | Suche |
| Card Knights, Pokitrio, Shophotep | kleine Shops | **standardmäßig aus**, Ruf nicht geprüft. Unter „Shops“ zuschaltbar |

**Nicht automatisch prüfbar** (Bot-Schutz oder per robots.txt gesperrt): Pokémon Center, Amazon, Smyths, Thalia,
Kaufland, Fantasywelt, Trader Online, Rossmann, Otto, Galeria, Saturn. Diese stehen als Linkliste im Reiter „Shops“.
Für Amazon und das Pokémon Center helfen oft die **mydealz-Meldungen**, weil die Community dort Restocks schnell postet.

**Games Island** steht ebenfalls in der Linkliste. Die Hauptseite soll nicht maschinell abgefragt werden, und die
angebotene Datenquelle `crawlme.games-island.eu` sperrt automatische Abrufe per robots.txt. Bewusst entschieden am
18.10.2026: nicht einbauen.

### Eigene Produktlinks (Merkliste)

Unter **„Shops → Eigene Produktlinks“** kannst du jede Produktseite eintragen, z. B. ein bestimmtes Display.
Der Wächter liest dann die Verfügbarkeit, die der Shop im Seitencode angibt. Das klappt bei den meisten Shops,
aber nicht bei gesperrten.

## Fair Play

- Jeder Shop wird nur alle paar Minuten abgefragt, mit Zufallsabstand und mindestens 3 Sekunden Pause pro Server.
- Die robots.txt jedes Shops wird beachtet. Was dort gesperrt ist, wird nicht abgefragt.
- Bei Fehlern oder Sperren wartet der Wächter automatisch länger, bis zu einer Stunde.
- Es wird **nichts automatisch gekauft**. Der Wächter sagt nur Bescheid, kaufen musst du selbst.

## Termine pflegen

Die Release-Termine stehen in `releases.json` (Stand 18.10.2026, Quelle: pokezentrum.de, tcgradar.eu).
Neue Termine einfach im gleichen Format ergänzen:
`{"datum": "2027-01-23", "name": "…", "sprache": "DE", "art": "Hauptset", "produkte": "…"}`

## Dateien

| Datei | Inhalt |
|---|---|
| `config.json` | deine Einstellungen (wird vom Dashboard geschrieben) |
| `tarspokewaechter.db` | gemerkte Produktzustände, Meldungen, News |
| `tarspokewaechter.log` | Protokoll (was wann geprüft wurde, Fehler) |
| `shops.py` | die Shop-Leser – falls ein Shop seinen Seitenaufbau ändert, muss hier nachgebessert werden |
| `sets.json` | Set-Liste nach Reihen mit Suchmustern für die Set-Erkennung |
| `cloud_lauf.py`, `.github/workflows/waechter.yml` | Cloud-Version auf GitHub |
| `einstellungen.json`, `auswahl.json` | Einstellungen und Set-Auswahl der Cloud-Version |
| `tests/test_cloud.py` | prüft Cloud-Einstellungen und dass das ntfy-Thema geheim bleibt |
| `tests/test_logik.py` | prüft Restock-Erkennung und Meldefilter (`py tests/test_logik.py`) |
| `tests/test_sets.py` | prüft die Set-Erkennung, mit `-v` auch an allen gespeicherten Shop-Titeln |

Wenn ein Shop im Reiter „Shops“ dauerhaft **„0 Produkte – Seitenaufbau geändert?“** zeigt, hat der Shop seine Seite
umgebaut. Dann muss der passende Leser angepasst werden.
