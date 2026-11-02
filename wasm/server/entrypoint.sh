#!/bin/sh
# Starts the SuperTuxKart LAN server and the WebSocket relay for browsers,
# which also starts the rooms that players create.
#   STK_SERVER_NAME  name shown in the lobby (default: Demos-Games)
#   STK_SERVER_PORT  UDP port of the game server (default: 2759)
#   STK_RELAY_PORT   WebSocket port for browser players (default: 8081)
#   STK_MAX_ROOMS    rooms players may create at once (default: 5)
#   STK_ROOM_IDLE    seconds an empty room lives (default: 300)
set -eu

NAME=${STK_SERVER_NAME:-Demos-Games}
PORT=${STK_SERVER_PORT:-2759}
RELAY=${STK_RELAY_PORT:-8081}
mkdir -p /config/rooms

supertuxkart --server-config=/config/server_config.xml \
    --lan-server="$NAME" --port="$PORT" --log=nocolor &
exec python3 /opt/stk/relay.py --listen "0.0.0.0:$RELAY" --server "127.0.0.1:$PORT" \
    --max-rooms "${STK_MAX_ROOMS:-5}" --room-idle "${STK_ROOM_IDLE:-300}"
