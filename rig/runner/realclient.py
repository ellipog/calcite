"""A real client's join: Mojang's own 26.3 client joins Calcite, walks, jumps and chats.

    py -I rig/runner/realclient.py [--online NAME] [--server PATH] [--world PATH] [--view N] [--message TEXT] [--dimension ID] [--watch [--mbit N] [--ms N] [--dump FILE]] [--set KEY=VALUE]... [--command TEXT]... [--keep-open SECONDS]

The protocol suites and the tests play the client's side with Calcite's own code, so this is
the one check where the other end is the game itself. Calcite runs from its release build,
build/server/calcite.exe, in a fresh folder under build/rig/realclient/. The client runs from
the files of a launcher that has run 26.3 once: the official launcher's .minecraft, the Modrinth
App or Prism Launcher, each checked against the SHA-1 in 26.3's version file, with JDK 25, in a
game folder of its own beside the server's, with its sound off and the first-run screens
skipped. It joins with --quickPlayMultiplayer. Nothing of Mojang's is copied: the client runs
from the launcher's files.

The client's render distance and the server's view distance are both 32, or --view N, so
what's measured is what a player who sees as far as the client lets them gets.

With --world PATH, the server's world is a copy of the world folder at PATH, such as one vanilla
saved in the rig's scratch folders, so the client is sent the chunks it saved, read from its
region files. Without it, the world is new, and the server generates its chunks as they're asked
for.

--set KEY=VALUE gives the server a calcite.properties setting, such as chunk-send-multiplier=2,
and can be given any number of times.

--command TEXT is typed into the server's console once it's ready, before the client starts, such
as `pregen start` to have the client join while the server pregenerates (CAL-71). It can be given
any number of times, and they're typed in order.

Without --online, the server is offline and the client is player RealClient, with no account.
With --online NAME, the server is in online mode, and the client plays as the Modrinth App's
account NAME, which must be the player's own: its session is renewed from the launcher's
Microsoft refresh token, as the launcher renews it, and kept in memory. No token is printed or
written, and nothing is written back to the launcher. The client then signs its chat, and the
message must come through signed, without [Not Secure], on both sides.

On Windows, realclient_keys.ps1 then sends the client's window its keys: F3 for the debug
screen, F2 for a screenshot, W held for 2.5 seconds and Space, F2, then T, the message and
Enter, and F2. It sends a key only while the client's window is in front, and stops if it isn't,
so nothing is typed anywhere else. The three screenshots, in the game folder's screenshots/,
show the coordinates before and after the walk, and the message in the client's chat.

With --dimension ID, such as the_nether, the server's console then runs `calcite dimension ID`
for the player, which takes them to that dimension where they are, as vanilla's respawn packet
takes a player to another (CAL-69), and, once its chunks have had 8 seconds to come, the keys
take a last screenshot with the debug screen on, which names the dimension.

With --watch, the client joins through chunkwatch.py's relay, which reads the frames each way and
times the chunks: for the join, and for each dimension it goes to, how many it was sent, their
bytes, and when the client had them all, by its `chunk_batch_received` after the last (CAL-99).
--mbit N caps what the server sends at N megabits a second, and --ms N makes each way N
milliseconds late, as a home link would. --dump FILE writes each chunk packet the client was
sent to FILE, as it was before it was compressed. The relay reads frames only in offline mode;
online, they're encrypted, and it only passes them on.

It passes if the server logged the join and the message, with --dimension that it moved the
player and the screenshot was taken, the client logged the message as it came back, nobody was disconnected before the client was stopped, and the client logged no error
but the ones on its download threads, which, with no account, Mojang's services and Realms
always give (rig/README.md, "A real client").
"""

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
sys.path.insert(0, str(CALCITE / "oracle"))
sys.path.insert(0, str(HERE))
from jdk import find_java_home, java  # noqa: E402

VERSION = "26.3"
PORT = 25600
OUT = CALCITE / "build" / "rig" / "realclient"
EXE = ".exe" if os.name == "nt" else ""
OS = {"nt": "windows", "darwin": "osx"}.get(os.name, "linux")


def launcher_roots():
    """Each launcher's folders: where it keeps version files, libraries and assets."""
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", home / ".config"))
    mc = appdata / ".minecraft" if os.name == "nt" else home / ".minecraft"
    modrinth = appdata / "ModrinthApp" / "meta" if os.name == "nt" else home / ".local/share/ModrinthApp/meta"
    prism = appdata / "PrismLauncher" if os.name == "nt" else home / ".local/share/PrismLauncher"
    return [
        ("the official launcher", mc / "versions", mc / "libraries", mc / "assets"),
        ("the Modrinth App", modrinth / "versions", modrinth / "libraries", modrinth / "assets"),
        ("Prism Launcher", None, prism / "libraries", prism / "assets"),
    ]


def sha1(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def version_file():
    for _, versions, _, _ in launcher_roots():
        path = versions / VERSION / f"{VERSION}.json" if versions else None
        if path and path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    sys.exit(f"no {VERSION}.json: run {VERSION} once from the official launcher")


def client_jar(spec):
    want = spec["downloads"]["client"]["sha1"]
    places = []
    for label, versions, libraries, _ in launcher_roots():
        if versions and versions.is_dir():
            places += [(label, p) for d in sorted(versions.glob(f"{VERSION}*")) for p in d.glob("*.jar")]
        places.append((label, libraries / "com" / "mojang" / "minecraft" / VERSION / f"minecraft-{VERSION}-client.jar"))
    for label, path in places:
        if path.is_file() and path.stat().st_size == spec["downloads"]["client"]["size"] and sha1(path) == want:
            return label, path
    sys.exit(f"no {VERSION} client jar with SHA-1 {want}: run {VERSION} once from a launcher")


def allowed(lib):
    allow = True
    for rule in lib.get("rules", []):
        if "os" not in rule or rule["os"].get("name") == OS:
            allow = rule["action"] == "allow"
        elif rule["action"] == "allow":
            allow = False
    # Natives for another processor, such as natives-windows-arm64, have no rule of their own.
    machine = platform.machine().lower()
    if lib["name"].endswith("-arm64") and machine not in ("arm64", "aarch64"):
        return False
    if lib["name"].endswith("-x86") and machine not in ("x86", "i386", "i686"):
        return False
    return allow


def libraries(spec):
    found, missing = [], []
    for lib in spec["libraries"]:
        art = lib.get("downloads", {}).get("artifact")
        if not art or not allowed(lib):
            continue
        for _, _, root, _ in launcher_roots():
            path = root / art["path"]
            if path.is_file() and path.stat().st_size == art["size"] and sha1(path) == art["sha1"]:
                found.append(path)
                break
        else:
            missing.append(art["path"])
    if missing:
        sys.exit(f"{len(missing)} of {VERSION}'s libraries aren't in any launcher, such as {missing[0]}: run {VERSION} once from a launcher")
    return found


def assets(spec):
    index = spec["assetIndex"]["id"]
    for _, _, _, root in launcher_roots():
        path = root / "indexes" / f"{index}.json"
        if not path.is_file():
            continue
        objects = json.loads(path.read_text(encoding="utf-8"))["objects"].values()
        if all((root / "objects" / o["hash"][:2] / o["hash"]).is_file() for o in objects):
            return root, index
    sys.exit(f"no launcher has all of asset index {index}: run {VERSION} once from a launcher")


def offline_uuid(name):
    """The UUID an offline server gives a name, as Java's UUID.nameUUIDFromBytes makes it."""
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode()).digest())
    digest[6] = digest[6] & 0x0F | 0x30
    digest[8] = digest[8] & 0x3F | 0x80
    return uuid.UUID(bytes=bytes(digest))


@dataclass
class Player:
    """Who the client plays as. The token never shows in a repr."""
    name: str
    uuid: str
    token: str = field(repr=False)


def offline_player():
    return Player("RealClient", offline_uuid("RealClient").hex, "0")


def post(url, body, form=False):
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    kind = "application/x-www-form-urlencoded" if form else "application/json"
    request = urllib.request.Request(url, data=data, headers={"Content-Type": kind, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        # An error's body names the problem; only its error fields are kept, to be shown.
        try:
            body = json.loads(e.read())
            return e.code, {k: body[k] for k in ("error", "error_description", "XErr", "errorMessage") if k in body}
        except ValueError:
            return e.code, {}


def online_player(name):
    """The Modrinth App's account `name`, with a session renewed as the launcher renews one: its
    Microsoft refresh token gives an Xbox Live token, that an XSTS token for Minecraft's services,
    and that a Minecraft access token. Every token stays in memory."""
    db = Path(os.environ.get("APPDATA", Path.home() / ".local/share")) / "ModrinthApp" / "app.db"
    if not db.is_file():
        sys.exit("--online needs the Modrinth App, signed in to the account")
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
        row = con.execute("select refresh_token from minecraft_users where username = ?", (name,)).fetchone()
    if not row:
        sys.exit(f"the Modrinth App has no account {name}")
    # The Minecraft launcher's Microsoft account client, which the Modrinth App signs in with.
    status, answer = post("https://login.live.com/oauth20_token.srf", {
        "client_id": "00000000402b5328", "grant_type": "refresh_token", "refresh_token": row[0],
        "redirect_uri": "https://login.live.com/oauth20_desktop.srf",
        "scope": "service::user.auth.xboxlive.com::MBI_SSL"}, form=True)
    if status == 200:
        status, answer = post("https://user.auth.xboxlive.com/user/authenticate", {
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                           "RpsTicket": f"t={answer['access_token']}"},
            "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"})
    if status == 200:
        status, answer = post("https://xsts.auth.xboxlive.com/xsts/authorize", {
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [answer["Token"]]},
            "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"})
    if status == 200:
        uhs = answer["DisplayClaims"]["xui"][0]["uhs"]
        status, answer = post("https://api.minecraftservices.com/authentication/login_with_xbox",
                              {"identityToken": f"XBL3.0 x={uhs};{answer['Token']}"})
    if status != 200:
        sys.exit(f"couldn't renew {name}'s session: {status} {answer}. Sign in again in the Modrinth App")
    request = urllib.request.Request("https://api.minecraftservices.com/minecraft/profile",
                                     headers={"Authorization": f"Bearer {answer['access_token']}"})
    with urllib.request.urlopen(request, timeout=20) as r:
        profile = json.load(r)
    return Player(profile["name"], profile["id"], answer["access_token"])


def client_command(spec, java_home, game, player, port):
    natives = OUT / "natives"
    jar_label, jar = client_jar(spec)
    asset_root, index = assets(spec)
    classpath = [str(p) for p in libraries(spec)] + [str(jar)]
    print(f"client: {VERSION}'s jar from {jar_label}, {len(classpath) - 1} libraries, assets from {asset_root}")
    jvm = ["-Xmx2G", "-XX:StackShadowPages=32", "--enable-native-access=ALL-UNNAMED",
           "--add-exports", "java.base/jdk.internal.misc=ALL-UNNAMED",
           f"-Djava.library.path={natives / 'java'}", f"-Djna.tmpdir={natives / 'jna'}",
           f"-Dorg.lwjgl.system.SharedLibraryExtractPath={natives / 'lwjgl'}",
           f"-Dio.netty.native.workdir={natives / 'netty'}",
           "-Dminecraft.launcher.brand=calcite-rig", "-Dminecraft.launcher.version=1",
           "-cp", os.pathsep.join(classpath)]
    args = ["--username", player.name, "--version", VERSION, "--gameDir", str(game),
            "--assetsDir", str(asset_root), "--assetIndex", index,
            "--uuid", player.uuid, "--accessToken", player.token, "--clientId", "0", "--xuid", "0",
            "--versionType", "release", "--width", "854", "--height", "480",
            "--quickPlayMultiplayer", f"127.0.0.1:{port}"]
    return [str(java(java_home))] + jvm + [spec["mainClass"]] + args


class Process:
    """A child whose output goes to a file and is kept, line by line, to wait on."""

    def __init__(self, argv, cwd, log):
        self.lines = []
        self.log = open(log, "w", encoding="utf-8")
        self.p = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            self.log.write(line)
            self.log.flush()
            self.lines.append(line.rstrip("\n"))

    def find(self, text):
        return next((line for line in self.lines if text in line), None)

    def wait_for(self, text, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            line = self.find(text)
            if line or self.p.poll() is not None:
                return line
            time.sleep(0.2)
        return None


def prepare(server_dir, game, online, world, view, settings=()):
    for folder in (server_dir, game / "screenshots"):
        if folder.exists():
            shutil.rmtree(folder)
    server_dir.mkdir(parents=True)
    (server_dir / "server.properties").write_text(
        f"online-mode={str(online).lower()}\nserver-ip=127.0.0.1\nserver-port={PORT}\ngamemode=creative\n"
        f"white-list=false\nview-distance={view}\nmotd=Calcite and a real client\n", encoding="utf-8")
    (server_dir / "calcite.properties").write_text("console-dashboard=off\n" + "".join(f"{s}\n" for s in settings),
                                                    encoding="utf-8")
    if world:
        shutil.copytree(world, server_dir / "world", ignore=shutil.ignore_patterns("session.lock"))
    game.mkdir(parents=True, exist_ok=True)
    (game / "options.txt").write_text(
        "onboardAccessibility:false\njoinedFirstServer:true\nskipMultiplayerWarning:true\n"
        f"pauseOnLostFocus:false\ntutorialStep:none\nrenderDistance:{view}\nnarrator:0\n"
        "soundCategory_master:0.0\n", encoding="utf-8")


def send_keys(client, message, shot=False):
    if os.name != "nt":
        print("keys: sent only on Windows, so the client just joins")
        return False
    argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(HERE / "realclient_keys.ps1"), "-ProcessId", str(client.p.pid), "-Message", message]
    keys = subprocess.run(argv + (["-Shot"] if shot else []), capture_output=True, text=True, timeout=120)
    said = (keys.stdout.strip() or keys.stderr.strip())
    print(f"keys: {said}")
    return keys.returncode == 0


def stop(server, client):
    client.p.kill()
    client.p.wait()
    try:
        server.p.stdin.write("stop\n")
        server.p.stdin.flush()
        server.p.wait(30)
    except (OSError, subprocess.TimeoutExpired):
        server.p.kill()


def main():
    parser = argparse.ArgumentParser(description="Mojang's 26.3 client joins Calcite, walks and chats.")
    parser.add_argument("--online", metavar="NAME", help="play as the Modrinth App's account NAME, in online mode")
    parser.add_argument("--server", default=str(CALCITE / "build" / "server" / f"calcite{EXE}"))
    parser.add_argument("--world", help="a world folder to copy in as the server's world")
    parser.add_argument("--view", type=int, default=32, help="the client's render distance and the server's view distance, 2 to 32")
    parser.add_argument("--message", default="hello from a real client",
                        help="what the client says: small letters and spaces")
    parser.add_argument("--dimension", metavar="ID", help="a dimension to take the client to after it chats, such as the_nether")
    parser.add_argument("--watch", action="store_true", help="join through chunkwatch.py's relay and report the chunks it timed")
    parser.add_argument("--mbit", type=float, help="with --watch, the most the server sends, in megabits a second")
    parser.add_argument("--ms", type=float, default=0, help="with --watch, milliseconds each way is late")
    parser.add_argument("--dump", help="with --watch, a file each chunk packet's written to, as it was before it was compressed")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="a calcite.properties setting for the server, such as chunk-send-multiplier=2")
    parser.add_argument("--command", action="append", default=[], metavar="TEXT",
                        help="a console command typed once the server's ready, before the client starts")
    parser.add_argument("--keep-open", type=float, default=0, help="seconds to leave the client in the game at the end")
    args = parser.parse_args()
    dimension = args.dimension if not args.dimension or ":" in args.dimension else f"minecraft:{args.dimension}"
    if not args.message.strip() or not all(c in "abcdefghijklmnopqrstuvwxyz " for c in args.message):
        sys.exit("the message can only have small letters and spaces")
    server_exe = Path(args.server)
    if not server_exe.is_file():
        sys.exit(f"no {server_exe}: build Calcite's release build first (src/README.md)")

    spec = version_file()
    java_home = find_java_home()
    server_dir, game = OUT / "server", OUT / "game"
    player = online_player(args.online) if args.online else offline_player()
    print(f"player: {player.name}, {'online, with a renewed session' if args.online else 'offline'}")
    relay = None
    if args.watch:
        from chunkwatch import Relay
        relay = Relay(PORT + 1, ("127.0.0.1", PORT), args.mbit, args.ms, args.dump)
        link = f"{args.mbit} Mbit/s" if args.mbit else "no cap"
        print(f"watch: the client joins through a relay on {PORT + 1}, {link}, {args.ms:g} ms each way")
    command = client_command(spec, java_home, game, player, PORT + 1 if relay else PORT)
    if args.world and not (Path(args.world) / "level.dat").is_file():
        sys.exit(f"no level.dat in {args.world}")
    if not 2 <= args.view <= 32:
        sys.exit("the view distance is from 2 to 32")
    prepare(server_dir, game, bool(args.online), args.world, args.view, args.set)

    server = Process([str(server_exe)], server_dir, OUT / "server.log")
    done = server.wait_for("Done (", 60)
    if not done:
        sys.exit("the server didn't start:\n" + "\n".join(server.lines[-20:]))
    print(f"server: {done.split(': ', 1)[1]}")
    for line in args.command:
        server.p.stdin.write(f"{line}\n")
        server.p.stdin.flush()
        print(f"console: {line}")
    client = Process(command, game, OUT / "client.log")
    keyed = False
    moved = shot = None
    try:
        joined = server.wait_for(f"{player.name} joined the game", 180)
        if joined:
            time.sleep(4)
            keyed = send_keys(client, args.message)
            if keyed:
                server.wait_for(f"<{player.name}> {args.message}", 10)
                client.wait_for(f"[CHAT] <{player.name}> {args.message}", 5)
            if dimension:
                server.p.stdin.write(f"calcite dimension {dimension} {player.name}\n")
                server.p.stdin.flush()
                moved = server.wait_for(f"Moved {player.name} to {dimension}", 10)
                time.sleep(8)
                shot = keyed and send_keys(client, args.message, shot=True) and "sent"
            time.sleep(args.keep_open)
        gone_early = server.find("lost connection") or client.find("Disconnected") or client.p.poll() is not None
    finally:
        stop(server, client)

    # Each check: what it is, and the line that shows it, or None.
    checks = [("the server logged the join", server.find(f"{player.name}[/127.0.0.1:"))]
    if os.name == "nt":
        said = server.find(f"<{player.name}> {args.message}")
        back = client.find(f"[CHAT] <{player.name}> {args.message}")
        checks += [
            ("the keys went to the client's window", keyed and "sent"),
            ("the server logged the message", said),
            ("the client got the message back", back),
        ]
        if args.online:
            checks += [
                ("the server took it as signed", said and "[Not Secure]" not in said and said),
                ("the client took it as signed", back and "[Not Secure]" not in back and back),
            ]
    if dimension:
        checks.append((f"the server moved the player to {dimension}", moved))
        if os.name == "nt":
            checks.append(("the keys took a screenshot there", shot))
    checks.append(("nobody was disconnected before the client was stopped", not gone_early and "-"))
    # With no account, the client's calls to Mojang's services and Realms fail on these threads.
    errors = [line for line in client.lines if "/ERROR]" in line and "[Download-" not in line]
    checks.append(("the client logged no error but its download threads'", not errors and "-"))
    for what, line in checks:
        shown = f": {line.split(']: ', 1)[-1]}" if line and line not in ("sent", "-") else ""
        print(f"{'ok  ' if line else 'FAIL'} {what}{shown}")
    for line in errors[:10]:
        print(f"     {line[:300]}")
    shots = sorted((game / "screenshots").glob("*.png")) if (game / "screenshots").is_dir() else []
    print(f"screenshots: {', '.join(str(p.relative_to(CALCITE)) for p in shots) or 'none'}")
    print(f"logs: {(OUT / 'server.log').relative_to(CALCITE)}, {(OUT / 'client.log').relative_to(CALCITE)}")
    if relay:
        report = relay.report()
        relay.close()
        (OUT / "watch.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        for connection in report:
            for p in connection:
                print(f"watch: {p['phase']}: {p['chunks']} chunks, {p['chunk_kib']} KiB, {p['bytes_a_chunk']} B a chunk, "
                      f"{p['batches']} batches, last sent at {p['last_chunk_s']} s, the client had half at {p['client_had_half_s']} s, "
                      f"90% at {p['client_had_90_s']} s, 95% at {p['client_had_95_s']} s, all at {p['client_had_all_s']} s, "
                      f"asked {p['asked_a_tick']} a tick, {p['forgotten']} forgotten, waited for the link {p['link_wait_ms']} ms")
        print(f"watch: {(OUT / 'watch.json').relative_to(CALCITE)}")
    sys.exit(0 if all(line for _, line in checks) else 1)


if __name__ == "__main__":
    main()
