#!/usr/bin/env python3
"""Generate a browser-friendly package manifest from a Homebrew tap."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def package_names(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []

    return sorted(
        path.relative_to(directory).with_suffix("").as_posix()
        for path in directory.rglob("*.rb")
    )


def brew_info(kind: str, tap: str, names: list[str]) -> list[dict[str, Any]]:
    if not names:
        return []

    command = [
        "brew",
        "info",
        "--json=v2",
        f"--{kind}",
        *(f"{tap}/{name}" for name in names),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"brew info failed for {kind}s:\n{result.stderr.strip()}"
        )

    key = "formulae" if kind == "formula" else "casks"
    return json.loads(result.stdout).get(key, [])


def normalize_package(
    item: dict[str, Any],
    kind: str,
    tap: str,
    repository: str,
    branch: str,
) -> dict[str, Any]:
    if kind == "formula":
        name = item["name"]
        version = item.get("versions", {}).get("stable")
        install = f"brew install {tap}/{name}"
    else:
        name = item.get("token") or item["name"]
        version = item.get("version")
        install = f"brew install --cask {tap}/{name}"

    package = {
        "name": name,
        "type": kind,
        "description": item.get("desc"),
        "version": version,
        "homepage": item.get("homepage"),
        "license": item.get("license"),
        "caveats": item.get("caveats"),
        "install": install,
    }

    source_path = item.get("ruby_source_path")
    if source_path:
        package["source"] = (
            f"https://github.com/{repository}/blob/{branch}/{source_path}"
        )

    return {key: value for key, value in package.items() if value is not None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tap", required=True, help="Homebrew tap name, e.g. owner/tap")
    parser.add_argument("--repository", required=True, help="GitHub repository owner/name")
    parser.add_argument("--branch", required=True, help="Git branch containing the tap")
    parser.add_argument("--revision", required=True, help="Source revision for the manifest")
    parser.add_argument("--output", default="packages.json")
    args = parser.parse_args()

    formula_names = package_names(Path("Formula"))
    cask_names = package_names(Path("Casks"))

    packages = [
        normalize_package(item, "formula", args.tap, args.repository, args.branch)
        for item in brew_info("formula", args.tap, formula_names)
    ]
    packages.extend(
        normalize_package(item, "cask", args.tap, args.repository, args.branch)
        for item in brew_info("cask", args.tap, cask_names)
    )
    packages.sort(key=lambda package: (package["type"], package["name"]))

    manifest = {
        "schemaVersion": 1,
        "repository": args.repository,
        "generatedFrom": args.revision,
        "packages": packages,
    }

    output = Path(args.output)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
