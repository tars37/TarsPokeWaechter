# TarsPokeWächter ☁️

Restock-Wecker für Pokémon-Karten. Läuft hier auf GitHub etwa alle 10 Minuten, prüft seriöse deutsche Shops
und schickt eine Push-Nachricht aufs Handy (App **ntfy**), sobald ein Display, eine Top-Trainer-Box, ein Bundle
oder eine Kollektion wieder da, neu gelistet oder vorbestellbar ist.

- **Statusseite:** `https://<dein-name>.github.io/TarsPokeWaechter/` – was gerade verfügbar ist, Meldungen, Termine.
- **Sets auswählen:** auf der Statusseite im Reiter „Meine Sets“, dann in `auswahl.json` übernehmen.
- **Einstellungen:** `einstellungen.json` (Sprachen, Preisgrenzen, Shops an/aus, eigene Produktlinks).
- **Push-Kanal:** das ntfy-Thema liegt als Geheimnis `NTFY_THEMA` in *Settings → Secrets and variables → Actions*.

Es wird nichts automatisch gekauft. Jeder Shop wird höchstens alle paar Minuten abgefragt, und die robots.txt
der Shops wird beachtet.

Die gleiche App läuft auch auf dem PC (`tarspokewaechter.py`). Details stehen in [ANLEITUNG.md](ANLEITUNG.md).
