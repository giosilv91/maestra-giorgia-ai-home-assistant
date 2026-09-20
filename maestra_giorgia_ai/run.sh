#!/usr/bin/with-contenv bashio
set -e
bashio::log.info "Avvio Maestra Giorgia AI..."
exec python3 /app/server.py
