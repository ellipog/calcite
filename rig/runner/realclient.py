"""A real client's join: Mojang's own 26.3 client joins Calcite, walks, jumps and chats.

    py -I rig/runner/realclient.py [--server PATH] [--message TEXT] [--keep-open SECONDS]

The protocol suites and the tests play the client's side with Calcite's own code, so this is
the one check where the other end is the game itself. Calcite runs offline from its release
build, build/server/calcite.exe, in a fresh folder under build/rig/realclient/. The client runs
from the files of a launcher that has run 26.3 once: the official launcher's .minecraft, the
Modrinth App or Prism Launcher, each checked against the SHA-1 in 26.3's version file, with JDK
25, as player RealClient, in a game folder of its own beside the server's, with its sound off
and the first-run screens skipped. It joins with --quickPlayMultiplayer. Nothing of Mojang's is
copied: the client runs from the launcher's files.

On Windows, realclient_keys.ps1 then sends the client's window its keys: F3 for the debug
screen, F2 for a screenshot, W held for 2.5 seconds and Space, F2, then T, the message and
Enter, and F2. It sends a key only while the client's window is in front, and stops if it isn't,
so nothing is typed anywhere else. The three screenshots, in the game folder's screenshots/,
show the coordinates before and after the walk, and the message in the client's chat.

It passes if the server logged the join and the message, the client logged the message as it
came back, nobody was disconnected before the client was stopped, and the client logged no error
but the ones its offline account always gets, from Mojang's services and Realms. The client has
no account, so the server can't be in online mode and chat isn't signed: that half of G4.1 needs
a player with an account (rig/README.md, "A real client").
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
sys.path.insert(0, str(CALCITE / "oracle"))
from jdk import find_java_home, java  # noqa: E402

VERSION = "26.3"
NAME = "RealClient"
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


def client_command(spec, java_home, game):
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
    args = ["--username", NAME, "--version", VERSION, "--gameDir", str(game),
            "--assetsDir", str(asset_root), "--assetIndex", index,
            "--uuid", offline_uuid(NAME).hex, "--accessToken", "0", "--clientId", "0", "--xuid", "0",
            "--versionType", "release", "--width", "854", "--height", "480",
            "--quickPlayMultiplayer", f"127.0.0.1:{PORT}"]
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


def prepare(server_dir, game):
    for folder in (server_dir, game / "screenshots"):
        if folder.exists():
            shutil.rmtree(folder)
    server_dir.mkdir(parents=True)
    (server_dir / "server.properties").write_text(
        f"online-mode=false\nserver-ip=127.0.0.1\nserver-port={PORT}\ngamemode=creative\n"
        "white-list=false\nview-distance=8\nmotd=Calcite and a real client\n", encoding="utf-8")
    (server_dir / "calcite.properties").write_text("console-dashboard=off\n", encoding="utf-8")
    game.mkdir(parents=True, exist_ok=True)
    (game / "options.txt").write_text(
        "onboardAccessibility:false\njoinedFirstServer:true\nskipMultiplayerWarning:true\n"
        "pauseOnLostFocus:false\ntutorialStep:none\nrenderDistance:8\nnarrator:0\n"
        "soundCategory_master:0.0\n", encoding="utf-8")


def send_keys(client, message):
    if os.name != "nt":
        print("keys: sent only on Windows, so the client just joins")
        return False
    keys = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                           str(HERE / "realclient_keys.ps1"), "-ProcessId", str(client.p.pid), "-Message", message],
                          capture_output=True, text=True, timeout=120)
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
    parser.add_argument("--server", default=str(CALCITE / "build" / "server" / f"calcite{EXE}"))
    parser.add_argument("--message", default="hello from a real client",
                        help="what the client says: small letters and spaces")
    parser.add_argument("--keep-open", type=float, default=0, help="seconds to leave the client in the game at the end")
    args = parser.parse_args()
    if not args.message.strip() or not all(c in "abcdefghijklmnopqrstuvwxyz " for c in args.message):
        sys.exit("the message can only have small letters and spaces")
    server_exe = Path(args.server)
    if not server_exe.is_file():
        sys.exit(f"no {server_exe}: build Calcite's release build first (src/README.md)")

    spec = version_file()
    java_home = find_java_home()
    server_dir, game = OUT / "server", OUT / "game"
    command = client_command(spec, java_home, game)
    prepare(server_dir, game)

    server = Process([str(server_exe)], server_dir, OUT / "server.log")
    done = server.wait_for("Done (", 60)
    if not done:
        sys.exit("the server didn't start:\n" + "\n".join(server.lines[-20:]))
    print(f"server: {done.split(': ', 1)[1]}")
    client = Process(command, game, OUT / "client.log")
    keyed = False
    try:
        joined = server.wait_for(f"{NAME} joined the game", 180)
        if joined:
            time.sleep(4)
            keyed = send_keys(client, args.message)
            if keyed:
                server.wait_for(f"<{NAME}> {args.message}", 10)
                client.wait_for(f"[CHAT] <{NAME}> {args.message}", 5)
            time.sleep(args.keep_open)
        gone_early = server.find("lost connection") or client.find("Disconnected") or client.p.poll() is not None
    finally:
        stop(server, client)

    # Each check: what it is, and the line that shows it, or None.
    checks = [("the server logged the join", server.find(f"{NAME}[/127.0.0.1:"))]
    if os.name == "nt":
        checks += [
            ("the keys went to the client's window", keyed and "sent"),
            ("the server logged the message", server.find(f"<{NAME}> {args.message}")),
            ("the client got the message back", client.find(f"[CHAT] <{NAME}> {args.message}")),
        ]
    checks.append(("nobody was disconnected before the client was stopped", not gone_early and "-"))
    # With no account, the client's calls to Mojang's services and Realms fail on their threads.
    errors = [line for line in client.lines if "/ERROR]" in line and "[Download-" not in line]
    checks.append(("the client logged no error but its offline account's", not errors and "-"))
    for what, line in checks:
        shown = f": {line.split(']: ', 1)[-1]}" if line and line not in ("sent", "-") else ""
        print(f"{'ok  ' if line else 'FAIL'} {what}{shown}")
    for line in errors[:10]:
        print(f"     {line[:300]}")
    shots = sorted((game / "screenshots").glob("*.png")) if (game / "screenshots").is_dir() else []
    print(f"screenshots: {', '.join(str(p.relative_to(CALCITE)) for p in shots) or 'none'}")
    print(f"logs: {(OUT / 'server.log').relative_to(CALCITE)}, {(OUT / 'client.log').relative_to(CALCITE)}")
    sys.exit(0 if all(line for _, line in checks) else 1)


if __name__ == "__main__":
    main()
