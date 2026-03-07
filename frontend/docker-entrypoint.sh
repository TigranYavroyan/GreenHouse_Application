#!/bin/sh
set -eu

DEFAULT_CMD="python3 main.py"

if [ "$#" -gt 0 ]; then
  APP_CMD="$*"
else
  APP_CMD="$DEFAULT_CMD"
fi

# Try host display first (Linux X11 or Windows X server like VcXsrv/Xming).
if [ -n "${DISPLAY:-}" ] && xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
  echo "Using host display: ${DISPLAY}"
  exec sh -c "$APP_CMD"
fi

echo "Host display unavailable. Starting Xvfb virtual display on :99"
export DISPLAY=:99
Xvfb :99 -screen 0 "${XVFB_SCREEN:-1920x1080x24}" -ac +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 &
sleep 1

if [ "${ENABLE_VNC:-false}" = "true" ]; then
  echo "Starting VNC server on 0.0.0.0:${VNC_PORT:-5900}"
  x11vnc \
    -display :99 \
    -forever \
    -shared \
    -rfbport "${VNC_PORT:-5900}" \
    -nopw \
    >/tmp/x11vnc.log 2>&1 &
fi

exec sh -c "$APP_CMD"
