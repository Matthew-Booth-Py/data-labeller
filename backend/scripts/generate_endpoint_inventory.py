#!/usr/bin/env python
"""Generate migration endpoint inventory from FastAPI routes."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROUTES_DIR = Path(__file__).resolve().parents[1] / "src" / "uu_backend" / "api" / "routes"
OUTPUT_JSON = Path(__file__).resolve().parents[1] / "tests" / "migration" / "endpoint_inventory.json"
OUTPUT_MD = Path(__file__).resolve().parents[2] / "docs" / "migration" / "endpoint-inventory.md"

DECORATOR_RE = re.compile(r"@router\.(get|post|put|delete|patch)\(\"([^\"]+)\"")


def derive_group(file_name: str) -> str:
    return file_name.replace(".py", "")


def load_inventory() -> dict:
    inventory = {"total_endpoints": 0, "groups": {}}
    for file_path in sorted(ROUTES_DIR.glob("*.py")):
        if file_path.name == "__init__.py":
            continue

        group = derive_group(file_path.name)
        endpoints = []

        text = file_path.read_text(encoding="utf-8")
        for method, path in DECORATOR_RE.findall(text):
            endpoints.append({"method": method.upper(), "path": path})

        inventory["groups"][group] = {
            "file": str(file_path),
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
        }
        inventory["total_endpoints"] += len(endpoints)

    return inventory


def write_markdown(inventory: dict) -> None:
    lines = [
        "# Endpoint Inventory",
        "",
        f"Total endpoints discovered: **{inventory['total_endpoints']}**",
        "",
        "| Group | Count |",
        "|---|---:|",
    ]

    for group, info in sorted(inventory["groups"].items()):
        lines.append(f"| `{group}` | {info['endpoint_count']} |")

    lines.append("")
    lines.append("## Per Group")

    for group, info in sorted(inventory["groups"].items()):
        lines.append("")
        lines.append(f"### `{group}`")
        for endpoint in info["endpoints"]:
            lines.append(f"- `{endpoint['method']}` `{endpoint['path']}`")

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    inventory = load_inventory()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    write_markdown(inventory)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")


if __name__ == "__main__":
    main()
