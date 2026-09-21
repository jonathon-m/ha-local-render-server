#!/usr/bin/with-contenv bashio
set -euo pipefail

URL=$(bashio::config 'url')
DISPLAY=$(bashio::config 'display')

bashio::log.info "Serving ${DISPLAY} from ${URL}"

ARGS=(--url "${URL}" --display "${DISPLAY}" --port 8080)

TOKEN=$(bashio::config 'token')
if [ -n "${TOKEN}" ]; then
    ARGS+=(--token "${TOKEN}")
fi

exec python3 /server.py "${ARGS[@]}"
