# Home Assistant Add-on: Webserver

nginx + PHP 8.3 als Home-Assistant-Add-on.

- Webinhalte liegen in `/share/web` (direkt per FTP/Samba bearbeitbar)
- Port 80
- Aufruf per IP oder `*.local` → eigene Website
- Jeder andere Hostname → Sperrseite (`/share/web/_blocked/index.html`), gedacht für AdGuard Home im Blockierungsmodus „Benutzerdefinierte IP“

## Installation

Home Assistant → Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories →
`https://github.com/irmscher123/ha-addon-webserver` hinzufügen, dann **Webserver** installieren.
