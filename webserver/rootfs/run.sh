#!/bin/sh
set -e
WEB=/share/web
mkdir -p "$WEB/_blocked"
# Startdateien nur anlegen, wenn noch nichts da ist – eigene Dateien werden nie überschrieben
[ -e "$WEB/index.html" ] || [ -e "$WEB/index.php" ] || cp /defaults/index.php "$WEB/index.php"
B="$WEB/_blocked/index.html"
# Sperrseite anlegen bzw. aktualisieren, solange sie nicht selbst angepasst wurde
# (Markierung "auto-blockpage" oder alte Standardversion 1.0.x)
if [ ! -e "$B" ] || grep -q "auto-blockpage" "$B" || grep -q "background: #14171c; color: #e6e8eb" "$B"; then
  cp /defaults/_blocked/index.html "$B"
fi

Z="$WEB/zertifikat.html"
if [ ! -e "$Z" ] || grep -q "auto-blockpage" "$Z"; then
  cp /defaults/zertifikat.html "$Z"
fi

echo "[webserver] Webroot: $WEB"
# HTTPS-Sperrseite (Port 443) mit lokaler CA; Fehler hier stoppen den Webserver nicht
python3 /tls_blockproxy.py &
php-fpm83 -D
exec nginx -g 'daemon off;'
