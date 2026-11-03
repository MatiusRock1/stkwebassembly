"""WebSocket to UDP relay between browser players and the SuperTuxKart servers.

Emscripten emulates the game's UDP sockets with WebSockets: every browser
socket opens one WebSocket per destination and sends each datagram as a binary
message, after a 10-byte "port" announcement. The player names the destination
in the path, /<address>/<port>; the relay only serves the ports of its own
servers and always sends to this machine. Each WebSocket gets its own UDP
socket, so a server sees every browser player as a separate client.

Browsers cannot host a server, so the game's "create server" asks the relay
for a room: GET /rooms/create starts a LAN server process on a free port and
answers with that port. LAN discovery (port 2757) reaches the main server, and
the relay adds one answer per room, so the game's LAN list shows them all.
Rooms that stay empty for --room-idle seconds are stopped.

The relay is public, so it only serves the pages of --origins and limits what
each client can use. Behind Cloudflare, CF-Connecting-IP names the client; this
is only reliable if nothing reaches the relay without going through Cloudflare.

  python3 relay.py --origins https://example.com [--listen 0.0.0.0:8081]
                   [--server 127.0.0.1:2759] [--discovery 2757] [--room-base 2760]
                   [--max-rooms 5] [--room-idle 300] [--room-max-age 7200]
                   [--room-interval 60] [--max-connections 200]
                   [--max-client-connections 16] [--idle-timeout 60]
"""
import argparse
import asyncio
import http
import ipaddress
import logging
import re
import struct
import time
from collections import Counter
from urllib.parse import parse_qs, urlsplit

import websockets

PORT_MESSAGE = bytes([255, 255, 255, 255]) + b'port'
DISCOVERY_QUERY = bytes([10]) + b'stk-server'
# Game modes of the create server screen and their ServerConfig::m_server_mode.
SERVER_MODES = {0: 3, 1: 4, 2: 7, 3: 6}
PASSWORD = re.compile(r'^[A-Za-z0-9_]{0,255}$')
# The game's default name is "<player>'s server".
ROOM_NAME = re.compile(r"^[\w '’.-]+$")
RESPONSE_HEADERS = [('Cross-Origin-Resource-Policy', 'cross-origin'), ('Content-Type', 'text/plain'),
                    ('Cache-Control', 'no-store'), ('Vary', 'Origin')]
# A UDP datagram never exceeds 64 KiB.
MAX_MESSAGE = 65536
MAX_QUEUE = 16
# Datagrams beyond these limits are dropped; the game's protocol resends what it needs.
MAX_MESSAGES_PER_SECOND = 200
MAX_PENDING_SENDS = 256


def client_of(headers):
    address = headers.get('CF-Connecting-IP') or ''
    try:
        # An IPv6 client controls its whole /64.
        if ':' in address:
            return str(ipaddress.ip_network(f'{address}/64', strict=False))
        return str(ipaddress.ip_address(address))
    except ValueError:
        return 'direct'


class Room:
    def __init__(self, port, name, max_players, difficulty, mode, password, process, owner):
        self.port, self.name, self.max_players, self.owner = port, name, max_players, owner
        self.difficulty, self.mode, self.password, self.process = difficulty, mode, password, process
        self.players = 0
        self.created = self.empty_since = time.monotonic()

    def discovery_answer(self, version):
        name = self.name.encode('utf-8')[:255]
        return (struct.pack('>I', version) + bytes([len(name)]) + name
                + bytes([self.max_players, min(self.players, self.max_players)]) + struct.pack('>H', self.port)
                + bytes([self.difficulty, SERVER_MODES.get(self.mode, 3), 1 if self.password else 0, 0, 0]))


class Relay:
    def __init__(self, args):
        self.args = args
        self.rooms = {}
        self.room_requests = {}
        self.connections = Counter()
        self.version = 6  # updated from the main server's discovery answers

    def destination(self, path):
        parts = [part for part in urlsplit(path).path.split('/') if part]
        if not parts:
            return self.args.server[1]
        port = int(parts[-1]) if parts[-1].isdigit() else -1
        if port in (self.args.server[1], self.args.discovery) or port in self.rooms:
            return port
        return None

    async def create_room(self, query, client):
        def value(key, default=''):
            return query.get(key, [default])[0]
        name = ' '.join(value('name').split())
        password = value('password')
        try:
            max_players = min(max(int(value('players', '8')), 2), 16)
            difficulty = min(max(int(value('difficulty', '0')), 0), 3)
            mode = int(value('mode', '0'))
            ai = min(max(int(value('ai', '0')), 0), 8)
        except ValueError:
            return http.HTTPStatus.BAD_REQUEST, 'bad parameters'
        if (not 4 <= len(name) <= 30 or not ROOM_NAME.match(name) or not PASSWORD.match(password)
                or mode not in SERVER_MODES):
            return http.HTTPStatus.BAD_REQUEST, 'bad parameters'
        now = time.monotonic()
        self.room_requests = {key: at for key, at in self.room_requests.items()
                              if now - at < self.args.room_interval}
        if client in self.room_requests:
            return http.HTTPStatus.TOO_MANY_REQUESTS, 'wait before creating another room'
        # One room per client. An empty one gives way, so that a player who
        # left it can create another without waiting for it to close.
        own = next((room for room in self.rooms.values() if room.owner == client), None)
        if own and own.players:
            return http.HTTPStatus.TOO_MANY_REQUESTS, 'you already have a room'
        if len(self.rooms) - bool(own) >= self.args.max_rooms:
            return http.HTTPStatus.SERVICE_UNAVAILABLE, 'too many rooms'
        self.room_requests[client] = now
        if own:
            self.stop_room(own)
        # The stopped room may still hold its port while it shuts down.
        port = next(p for p in range(self.args.room_base, self.args.room_base + 100)
                    if p not in self.rooms and not (own and p == own.port))
        command = ['supertuxkart', f'--server-config=/config/rooms/{port}.xml', f'--lan-server={name}',
                   f'--port={port}', f'--mode={mode}', f'--difficulty={difficulty}',
                   f'--max-players={max_players}', '--log=nocolor']
        if password:
            command.append(f'--server-password={password}')
        if ai:
            command.append(f'--server-ai={ai}')
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                       stderr=asyncio.subprocess.STDOUT)
        room = Room(port, name, max_players, difficulty, mode, password, process, client)
        self.rooms[port] = room
        try:
            await asyncio.wait_for(self.wait_listening(process), 60)
        except asyncio.TimeoutError:
            self.stop_room(room)
            return http.HTTPStatus.SERVICE_UNAVAILABLE, 'room did not start'
        asyncio.ensure_future(self.drain(room))
        logging.info('room %r started on port %d', name, port)
        return http.HTTPStatus.OK, str(port)

    @staticmethod
    async def wait_listening(process):
        async for line in process.stdout:
            if b'Listening has been started' in line:
                return

    async def drain(self, room):
        async for _ in room.process.stdout:
            pass
        if self.rooms.get(room.port) is room:
            del self.rooms[room.port]
            logging.info('room %r on port %d ended', room.name, room.port)

    def stop_room(self, room):
        self.rooms.pop(room.port, None)
        if room.process.returncode is None:
            room.process.terminate()

    async def close_idle_rooms(self):
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            for room in list(self.rooms.values()):
                idle = room.players == 0 and now - room.empty_since > self.args.room_idle
                if idle or now - room.created > self.args.room_max_age:
                    logging.info('closing %s room %r on port %d', 'idle' if idle else 'old', room.name, room.port)
                    self.stop_room(room)

    async def process_request(self, path, headers):
        if not urlsplit(path).path.rstrip('/').endswith('/rooms/create'):
            return None
        origin = headers.get('Origin')
        if origin not in self.args.origins:
            return http.HTTPStatus.FORBIDDEN, RESPONSE_HEADERS, b'origin not allowed'
        status, body = await self.create_room(parse_qs(urlsplit(path).query), client_of(headers))
        return status, [('Access-Control-Allow-Origin', origin), *RESPONSE_HEADERS], body.encode()

    async def handle(self, websocket, path):
        client = client_of(websocket.request_headers)
        if (sum(self.connections.values()) >= self.args.max_connections
                or self.connections[client] >= self.args.max_client_connections):
            logging.info('too many connections, refused %s', client)
            await websocket.close(1013, 'too many connections')
            return
        self.connections[client] += 1
        try:
            await self.relay_datagrams(websocket, path, client)
        finally:
            self.connections[client] -= 1
            if not self.connections[client]:
                del self.connections[client]

    async def relay_datagrams(self, websocket, path, peer):
        port = self.destination(path)
        if port is None:
            logging.info('refused %s for %s', peer, path)
            await websocket.close(1008, 'unknown port')
            return
        relay = self
        room = self.rooms.get(port)

        class ServerSide(asyncio.DatagramProtocol):
            pending = 0
            # A connection counts as a player once the game server answers it,
            # so that an open socket alone cannot keep a room alive.
            is_player = False

            def datagram_received(self, data, addr):
                if port == relay.args.discovery and len(data) >= 4:
                    relay.version = struct.unpack('>I', data[:4])[0]
                if room and not self.is_player:
                    self.is_player = True
                    room.players += 1
                if self.pending < MAX_PENDING_SENDS:
                    self.pending += 1
                    asyncio.ensure_future(websocket.send(data)).add_done_callback(self.sent)

            def sent(self, future):
                self.pending -= 1
                if not future.cancelled():
                    future.exception()

        loop = asyncio.get_running_loop()
        transport, side = await loop.create_datagram_endpoint(
            ServerSide, remote_addr=(self.args.server[0], port))
        logging.info('player connected from %s to port %d', peer, port)
        window, messages = time.monotonic(), 0
        try:
            while True:
                message = await asyncio.wait_for(websocket.recv(), self.args.idle_timeout)
                if isinstance(message, str):
                    continue
                if len(message) == 10 and message.startswith(PORT_MESSAGE):
                    continue
                now = time.monotonic()
                if now - window >= 1:
                    window, messages = now, 0
                messages += 1
                if messages > MAX_MESSAGES_PER_SECOND:
                    continue
                transport.sendto(message)
                if port == self.args.discovery and message == DISCOVERY_QUERY:
                    for other in list(self.rooms.values()):
                        await websocket.send(other.discovery_answer(self.version))
        except (websockets.ConnectionClosed, asyncio.TimeoutError):
            pass
        finally:
            transport.close()
            if side.is_player:
                room.players -= 1
                if room.players == 0:
                    room.empty_since = time.monotonic()
            logging.info('player disconnected from %s', peer)


def address(text):
    host, port = text.rsplit(':', 1)
    return host, int(port)


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--origins', nargs='+', required=True, help='pages that may use the relay')
    parser.add_argument('--listen', type=address, default=('0.0.0.0', 8081))
    parser.add_argument('--server', type=address, default=('127.0.0.1', 2759))
    parser.add_argument('--discovery', type=int, default=2757)
    parser.add_argument('--room-base', type=int, default=2760)
    parser.add_argument('--max-rooms', type=int, default=5)
    parser.add_argument('--room-idle', type=int, default=300)
    parser.add_argument('--room-max-age', type=int, default=7200)
    parser.add_argument('--room-interval', type=int, default=60, help='seconds between rooms of one client')
    parser.add_argument('--max-connections', type=int, default=200)
    parser.add_argument('--max-client-connections', type=int, default=16)
    parser.add_argument('--idle-timeout', type=int, default=60, help='seconds a silent connection lives')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s relay: %(message)s')
    relay = Relay(args)
    asyncio.ensure_future(relay.close_idle_rooms())
    async with websockets.serve(relay.handle, *args.listen, subprotocols=['binary'], origins=args.origins,
                                max_size=MAX_MESSAGE, max_queue=MAX_QUEUE, process_request=relay.process_request):
        logging.info('listening on %s:%d for server %s:%d (discovery %d, up to %d rooms)',
                     *args.listen, *args.server, args.discovery, args.max_rooms)
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
