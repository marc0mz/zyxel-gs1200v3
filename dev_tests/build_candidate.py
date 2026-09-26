"""Build a manual-install ZIP for the 0.1.25 PoE/Ethernet baseline."""
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

repository = Path(__file__).resolve().parents[1]
workspace = repository.parent
source = repository / "custom_components"
output = workspace / "outputs" / "zyxel_gs1200v3_0.1.25_poe_ethernet_baseline.zip"
manifest = json.loads(
    (source / "zyxel_gs1200v3" / "manifest.json").read_text(encoding="utf-8")
)
if manifest["version"] != "0.1.25":
    raise SystemExit("Unexpected integration version")

with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        archive.write(path, Path("custom_components") / path.relative_to(source))

with ZipFile(output) as archive:
    names = archive.namelist()
    if "custom_components/zyxel_gs1200v3/manifest.json" not in names:
        raise SystemExit("ZIP is missing the integration manifest")
    if any("__pycache__" in name or name.endswith(".pyc") for name in names):
        raise SystemExit("ZIP contains unexpected bytecode")

print(f"Built {output} ({len(names)} files, version {manifest['version']})")
