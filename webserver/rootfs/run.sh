#!/bin/sh
set -e
WEB=/share/web
mkdir -p "$WEB/_blocked"
# Startdateien nur anlegen, wenn noch nichts da ist – eigene Dateien werden nie überschrieben
[ -e "$WEB/index.html" ] || [ -e "$WEB/index.php" ] || cp /defaults/index.php "$WEB/index.php"
[ -e "$WEB/_blocked/index.html" ] || cp /defaults/_blocked/index.html "$WEB/_blocked/index.html"

echo "[webserver] Webroot: $WEB"
php-fpm83 -D
exec nginx -g 'daemon off;'
