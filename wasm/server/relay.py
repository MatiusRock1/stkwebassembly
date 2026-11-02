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

  python3 relay.py [--listen 0.0.0.0:8081] [--server 127.0.0.1:2759] [--discovery 2757]
                   [--room-base 2760] [--max-rooms 5] [--room-idle 300]
"""
import argparse
import asyncio
import http
import logging
import re
import struct
import time
from urllib.parse import parse_qs, urlsplit

import websockets

PORT_MESSAGE = bytes([255, 255, 255, 255]) + b'port'
DISCOVERY_QUERY = bytes([10]) + b'stk-server'
# Game modes of the create server screen and their ServerConfig::m_server_mode.
SERVER_MODES = {0: 3, 1: 4, 2: 7, 3: 6}
PASSWORD = re.compile(r'^[A-Za-z0-9_]{0,255}$')
CORS = [('Access-Control-Allow-Origin', '*'), ('Cross-Origin-Resource-Policy', 'cross-origin'),
        ('Content-Type', 'text/plain'), ('Cache-Control', 'no-store')]


class Room:
    def __init__(self, port, name, max_players, difficulty, mode, password, process):
        self.port, self.name, self.max_players = port, name, max_players
        self.difficulty, self.mode, self.password, self.process = difficulty, mode, password, process
        self.players = 0
        self.empty_since = time.monotonic()

    def discovery_answer(self, version):
        name = self.name.encode('utf-8')[:255]
        return (struct.pack('>I', version) + bytes([len(name)]) + name
                + bytes([self.max_players, self.players]) + struct.pack('>H', self.port)
                + bytes([self.difficulty, SERVER_MODES.get(self.mode, 3), 1 if self.password else 0, 0, 0]))


class Relay:
    def __init__(self, args):
        self.args = args
        self.rooms = {}
        self.version = 6  # updated from the main server's discovery answers

    def destination(self, path):
        parts = [part for part in urlsplit(path).path.split('/') if part]
        if not parts:
            return self.args.server[1]
        port = int(parts[-1]) if parts[-1].isdigit() else -1
        if port in (self.args.server[1], self.args.discovery) or port in self.rooms:
            return port
        return None

    async def create_room(self, query):
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
        if not 4 <= len(name) <= 30 or not PASSWORD.match(password) or mode not in SERVER_MODES:
            return http.HTTPStatus.BAD_REQUEST, 'bad parameters'
        if len(self.rooms) >= self.args.max_rooms:
            return http.HTTPStatus.SERVICE_UNAVAILABLE, 'too many rooms'
        port = next(p for p in range(self.args.room_base, self.args.room_base + 100) if p not in self.rooms)
        command = ['supertuxkart', f'--server-config=/config/rooms/{port}.xml', f'--lan-server={name}',
                   f'--port={port}', f'--mode={mode}', f'--difficulty={difficulty}',
                   f'--max-players={max_players}', '--log=nocolor']
        if password:
            command.append(f'--server-password={password}')
        if ai:
            command.append(f'--server-ai={ai}')
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                       stderr=asyncio.subprocess.STDOUT)
        room = Room(port, name, max_players, difficulty, mode, password, process)
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
                if room.players == 0 and now - room.empty_since > self.args.room_idle:
                    logging.info('closing idle room %r on port %d', room.name, room.port)
                    self.stop_room(room)

    async def process_request(self, path, headers):
        if not urlsplit(path).path.rstrip('/').endswith('/rooms/create'):
            return None
        status, body = await self.create_room(parse_qs(urlsplit(path).query))
        return status, CORS, body.encode()

    async def handle(self, websocket, path):
        port = self.destination(path)
        peer = websocket.remote_address
        if port is None:
            logging.info('refused %s for %s', peer, path)
            await websocket.close(1008, 'unknown port')
            return
        relay = self

        class ServerSide(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                if port == relay.args.discovery and len(data) >= 4:
                    relay.version = struct.unpack('>I', data[:4])[0]
                asyncio.ensure_future(websocket.send(data))

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            ServerSide, remote_addr=(self.args.server[0], port))
        room = self.rooms.get(port)
        if room:
            room.players += 1
        logging.info('player connected from %s to port %d', peer, port)
        try:
            async for message in websocket:
                if isinstance(message, str):
                    continue
                if len(message) == 10 and message.startswith(PORT_MESSAGE):
                    continue
                transport.sendto(message)
                if port == self.args.discovery and message == DISCOVERY_QUERY:
                    for other in list(self.rooms.values()):
                        await websocket.send(other.discovery_answer(self.version))
        except websockets.ConnectionClosed:
            pass
        finally:
            transport.close()
            if room:
                room.players -= 1
                if room.players == 0:
                    room.empty_since = time.monotonic()
            logging.info('player disconnected from %s', peer)


def address(text):
    host, port = text.rsplit(':', 1)
    return host, int(port)


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--listen', type=address, default=('0.0.0.0', 8081))
    parser.add_argument('--server', type=address, default=('127.0.0.1', 2759))
    parser.add_argument('--discovery', type=int, default=2757)
    parser.add_argument('--room-base', type=int, default=2760)
    parser.add_argument('--max-rooms', type=int, default=5)
    parser.add_argument('--room-idle', type=int, default=300)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s relay: %(message)s')
    relay = Relay(args)
    asyncio.ensure_future(relay.close_idle_rooms())
    async with websockets.serve(relay.handle, *args.listen, subprotocols=['binary'], max_size=None,
                                process_request=relay.process_request):
        logging.info('listening on %s:%d for server %s:%d (discovery %d, up to %d rooms)',
                     *args.listen, *args.server, args.discovery, args.max_rooms)
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
