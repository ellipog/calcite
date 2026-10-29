"""Reads the packets Calcite's tests were sent with vanilla's own codecs (D145).

src/test/play.calx and src/test/configuration.calx write every packet their clients are sent to
build/packets/. This runs PacketCheck, from the adapter build.py makes, on those files: each
packet must decode, leave nothing over and encode back to the same bytes. It exits with 1 if
any packet fails, and with 2 if the adapter isn't built or there's nothing to check.

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


def main():
    if not ADAPTER.is_file():
        print(f"check_packets: the vanilla adapter isn't built; run py -I {(HERE / 'build.py').relative_to(CALCITE)}")
        return 2
    files = sorted(PACKETS.glob("*.bin"))
    if not files:
        print(f"check_packets: no packets in {PACKETS.relative_to(CALCITE)}; run the tests first")
        return 2
    adapter = json.loads(ADAPTER.read_text(encoding="utf-8"))
    # The adapter's command line, with PacketCheck in place of the adapter's main class.
    argv = adapter["argv"][:-1] + ["calcite.rig.vanilla.PacketCheck"] + [str(f) for f in files]
    r = subprocess.run(argv, cwd=adapter["cwd"], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout, end="")
    # Vanilla's log goes to stderr, and matters only if the check itself broke.
    if r.returncode != 0 and "kinds failed" not in r.stdout:
        print(r.stderr[-4000:], end="")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
