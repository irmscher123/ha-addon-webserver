# Home Assistant Add-on: Webserver

nginx + PHP 8.3 als Home-Assistant-Add-on.

- Webinhalte liegen in `/share/web` (direkt per FTP/Samba bearbeitbar)
- Port 80
- Aufruf per IP oder `*.local` → eigene Website
- Jeder andere Hostname → Sperrseite (`/share/web/_blocked/index.html`), gedacht für AdGuard Home im Blockierungsmodus „Benutzerdefinierte IP“

## Installation

Home Assistant → Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories →
`https://github.com/irmscher123/ha-addon-webserver` hinzufügen, dann **Webserver** installieren.

## HTTPS (Port 443)

Gesperrte Domains werden meist per `https://` aufgerufen. Das Add-on erzeugt beim ersten Start
eine lokale CA (gespeichert im Add-on unter `/data/ca`) und signiert für jede aufgerufene Domain
automatisch ein Zertifikat.

- Ohne installiertes CA-Zertifikat: Zertifikatswarnung im Browser
- Mit installiertem CA-Zertifikat: Sperrseite ohne Warnung

Zertifikat + Anleitung: `http://<HA-IP>/zertifikat.html`

⚠️ Der private Schlüssel der CA liegt in `/data/ca/ca.key` des Add-ons. Wer ihn besitzt, könnte
für Geräte mit installiertem Zertifikat beliebige Seiten fälschen – nicht weitergeben.
