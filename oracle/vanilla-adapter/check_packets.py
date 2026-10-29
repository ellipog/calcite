"""Reads the packets Calcite's tests were sent with vanilla's own codecs (D145).

src/test/play.calx and src/test/configuration.calx write every packet their clients are sent to
build/packets/. This runs PacketCheck, from the adapter build.py makes, on those files: each
packet must decode, leave nothing over and encode back to the same bytes. Then ChatCheck reads
the signed chat test's clients' chat, in build/packets/chat/, as a 26.3 client takes it in: each
chat session must check out against the key standing in for Mojang's, and each message against
its sender's key, in its chain, with its last-seen list unpacked from the client's cache. It
exits with 1 if any packet fails, and with 2 if the adapter isn't built or there's nothing to
check.

    py -I oracle/vanilla-adapter/check_packets.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]
PLATFORM = "windows" if os.name == "nt" else sys.platform
ADAPTER = HERE / "build" / PLATFORM / "adapter.json"
PACKETS = CALCITE / "build" / "packets"
CHAT = PACKETS / "chat"


def main():
    if not ADAPTER.is_file():
        print(f"check_packets: the vanilla adapter isn't built; run py -I {(HERE / 'build.py').relative_to(CALCITE)}")
        return 2
    files = sorted(PACKETS.glob("*.bin"))
    if not files:
        print(f"check_packets: no packets in {PACKETS.relative_to(CALCITE)}; run the tests first")
        return 2
    adapter = json.loads(ADAPTER.read_text(encoding="utf-8"))
    packets = run(adapter, "PacketCheck", [str(f) for f in files], "kinds failed")
    if not (CHAT / "services.der").is_file():
        return packets.returncode
    chat = run(adapter, "ChatCheck", [str(CHAT)], "refused")
    # The last line sums up both, for src/test/run.py.
    last = [packets.stdout.strip().splitlines()[-1:], chat.stdout.strip().splitlines()[-1:]]
    print("; ".join(line for lines in last for line in lines))
    return packets.returncode or chat.returncode


def run(adapter, main_class, args, done):
    """Runs one of the adapter's checks, with it in place of the adapter's main class."""
    argv = adapter["argv"][:-1] + [f"calcite.rig.vanilla.{main_class}"] + args
    r = subprocess.run(argv, cwd=adapter["cwd"], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout, end="")
    # Vanilla's log goes to stderr, and matters only if the check itself broke.
    if r.returncode != 0 and done not in r.stdout:
        print(r.stderr[-4000:], end="")
    return r


if __name__ == "__main__":
    sys.exit(main())
