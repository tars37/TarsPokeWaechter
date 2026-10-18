"""Benachrichtigungen: ntfy (Handy-Push), Windows-Meldung, Telegram, Discord."""
import base64
import datetime as dt
import logging
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from netz import sende_json

log = logging.getLogger("melder")

_PS_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
APP_ID = "TarsPokeWaechter"
APP_NAME = "TarsPokeWächter"
_app_id = _PS_APP_ID  # wird zu APP_ID, sobald die App bei Windows eingetragen ist


def app_registrieren(ordner):
    """Trägt die App unter HKCU ein, damit Windows-Meldungen mit Name und Symbol der App erscheinen."""
    global _app_id
    if sys.platform != "win32":
        return False
    try:
        import winreg
        symbol = Path(ordner).resolve() / "web" / "icon-256.png"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{APP_ID}") as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            if symbol.exists():
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, str(symbol))
        _app_id = APP_ID
        return True
    except OSError as e:
        log.warning("App-Eintrag für Windows-Meldungen fehlgeschlagen: %s", e)
        return False


def _in_ruhezeit(ruhe):
    if not ruhe or not ruhe.get("aktiv"):
        return False
    jetzt = dt.datetime.now().strftime("%H:%M")
    von, bis = ruhe.get("von", "23:00"), ruhe.get("bis", "07:00")
    return (von <= jetzt < bis) if von < bis else (jetzt >= von or jetzt < bis)


def _windows_meldung(titel, text, url=None):
    if sys.platform != "win32":
        return
    subprocess.Popen(_toast_befehl(titel, text, url), creationflags=0x08000000,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _toast_befehl(titel, text, url=None):
    start =f' activationType="protocol" launch={quoteattr(url)}' if url else ""
    knopf = (f'<actions><action content="Zum Shop" activationType="protocol" arguments={quoteattr(url)}/></actions>'
             if url else "")
    xml = (f"<toast{start}><visual><binding template=\"ToastGeneric\"><text>{escape(titel)}</text>"
           f"<text>{escape(text)}</text></binding></visual>{knopf}</toast>")
    skript = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null\n"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        f"$x.LoadXml(@'\n{xml}\n'@)\n"
        "$t = New-Object Windows.UI.Notifications.ToastNotification $x\n"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{_app_id}').Show($t)\n"
    )
    kodiert = base64.b64encode(skript.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", kodiert]


class Melder:
    def __init__(self, konfig):
        self.konfig = konfig

    def senden(self, titel, text, url=None, prio=3, tags=None, bild=None):
        """prio: 1 (leise) .. 5 (dringend). Gibt [(kanal, ok, fehler)] zurück."""
        k = self.konfig.daten["benachrichtigung"]
        ruhe = _in_ruhezeit(k.get("ruhezeit"))
        ergebnisse = []

        ntfy = k.get("ntfy", {})
        if ntfy.get("aktiv") and ntfy.get("thema"):
            nutz = {"topic": ntfy["thema"], "title": titel, "message": text,
                    "priority": min(prio, 2) if ruhe else prio, "tags": tags or []}
            if url:
                nutz["click"] = url
                nutz["actions"] = [{"action": "view", "label": "Zum Shop", "url": url, "clear": True}]
            if bild and ntfy.get("bilder", True):
                nutz["attach"] = bild
            try:
                kopf = {"Authorization": f"Bearer {ntfy['token']}"} if ntfy.get("token") else None
                sende_json(ntfy.get("server", "https://ntfy.sh").rstrip("/") + "/", nutz, kopf)
                ergebnisse.append(("ntfy", True, ""))
            except Exception as e:  # noqa: BLE001
                ergebnisse.append(("ntfy", False, str(e)))

        if k.get("windows", {}).get("aktiv", True) and not (ruhe and k.get("windows", {}).get("in_ruhezeit_still", True)):
            try:
                _windows_meldung(titel, text, url)
                ergebnisse.append(("windows", True, ""))
            except Exception as e:  # noqa: BLE001
                ergebnisse.append(("windows", False, str(e)))

        tg = k.get("telegram", {})
        if tg.get("aktiv") and tg.get("bot_token") and tg.get("chat_id"):
            nachricht = f"<b>{escape(titel)}</b>\n{escape(text)}" + (f"\n{escape(url)}" if url else "")
            try:
                sende_json(f"https://api.telegram.org/bot{tg['bot_token']}/sendMessage",
                           {"chat_id": tg["chat_id"], "text": nachricht, "parse_mode": "HTML",
                            "disable_notification": ruhe})
                ergebnisse.append(("telegram", True, ""))
            except Exception as e:  # noqa: BLE001
                ergebnisse.append(("telegram", False, str(e)))

        dc = k.get("discord", {})
        if dc.get("aktiv") and dc.get("webhook"):
            try:
                sende_json(dc["webhook"], {"content": f"**{titel}**\n{text}" + (f"\n{url}" if url else ""),
                                           "allowed_mentions": {"parse": []}})
                ergebnisse.append(("discord", True, ""))
            except Exception as e:  # noqa: BLE001
                ergebnisse.append(("discord", False, str(e)))

        for kanal, ok, fehler in ergebnisse:
            if not ok:
                log.warning("Benachrichtigung über %s fehlgeschlagen: %s", kanal, fehler)
        return ergebnisse
