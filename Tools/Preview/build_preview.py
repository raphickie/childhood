"""Build an offline, single-file browser preview from the Unity project assets."""
import argparse
import base64
import hashlib
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESOURCES = HERE.parent.parent / "Assets" / "Resources"
THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.min.js"
THREE_HASH = "170c6789f43217c96b3170f4b42fafe135de7f7cd48497a4218f9757ee1d49fa"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--three", type=Path, help="Use a local copy of the pinned Three.js file.")
args = parser.parse_args()

if args.three:
    three = args.three.read_bytes()
else:
    with urllib.request.urlopen(THREE_URL, timeout=30) as response:
        three = response.read()

if hashlib.sha256(three).hexdigest() != THREE_HASH:
    raise SystemExit("Three.js checksum mismatch")

replacements = {
    "@@LAYOUT@@": (RESOURCES / "VillageLayout.json").read_text(),
    "@@MESHES@@": base64.b64encode((RESOURCES / "VillageMeshes.bytes").read_bytes()).decode(),
    "@@HOUSE_SURFACES@@": base64.b64encode((RESOURCES / "HouseSurfaces.bytes").read_bytes()).decode(),
    "@@AUTO_PANELS@@": base64.b64encode((RESOURCES / "AutoPanels.bytes").read_bytes()).decode(),
    "@@CRY@@": base64.b64encode((RESOURCES / "Crying.wav").read_bytes()).decode(),
    "@@SWAT@@": base64.b64encode((RESOURCES / "Swat.wav").read_bytes()).decode(),
    "@@THREE@@": three.decode(),
    "@@THREE_LICENSE@@": (HERE / "THREE-LICENSE").read_text(),
    "@@GAME@@": (HERE / "game.js").read_text(),
}

html = (HERE / "index.template.html").read_text()
for marker, value in replacements.items():
    html = html.replace(marker, value)
args.output.write_text(html)
