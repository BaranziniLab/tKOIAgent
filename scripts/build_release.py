#!/usr/bin/env python3
"""Build the portable tKOI plugin ZIP and its SHA256 checksum."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile


RELEASE_FILES = (
    "plugin.json",
    "mcp.json",
    ".mcp.json",
    ".codex-plugin/plugin.json",
    ".codex-plugin/mcp.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "README.md",
    "LICENSE",
    "requirements.txt",
)
IDENTITY_MANIFESTS = (
    "plugin.json",
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
)
REQUIRED_SKILLS = (
    "skills/tkoi-analysis/SKILL.md",
    "skills/tkoi-knowledge-graph/SKILL.md",
)
SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def read_file(root: Path, relative: str) -> bytes:
    path = root / relative
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError(f"Release files must not be symlinks: {relative}")
    if not path.is_file():
        raise ValueError(f"Required release file is missing: {relative}")
    return path.read_bytes()


def collect_files(root: Path) -> dict[str, bytes]:
    files = {relative: read_file(root, relative) for relative in RELEASE_FILES}
    skills = root / "skills"
    if skills.is_symlink() or not skills.is_dir():
        raise ValueError("skills/ must be a regular directory")
    for path in sorted(skills.rglob("*")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts[1:]):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink():
            raise ValueError(f"Release files must not be symlinks: {relative}")
        if path.is_file():
            files[relative.as_posix()] = read_file(root, relative.as_posix())
    for relative in REQUIRED_SKILLS:
        if relative not in files:
            raise ValueError(f"Required skill is missing: {relative}")
    return files


def read_json(files: dict[str, bytes], relative: str) -> dict:
    try:
        value = json.loads(files[relative])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON in {relative}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return value


def validate_metadata(files: dict[str, bytes], tag: str | None) -> tuple[str, str]:
    portable = read_json(files, "plugin.json")
    if portable.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        raise ValueError("plugin.json must declare the supported Agent Plugins schema")
    name, version = portable.get("name"), portable.get("version")
    if name != "tkoi-agent":
        raise ValueError("The release plugin name must be tkoi-agent")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError("plugin.json must declare a semantic version")
    prerelease = version.split("+", 1)[0].partition("-")[2]
    if any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease.split(".")):
        raise ValueError("Numeric prerelease identifiers must not have leading zeros")
    for relative in IDENTITY_MANIFESTS[1:]:
        manifest = read_json(files, relative)
        if (manifest.get("name"), manifest.get("version")) != (name, version):
            raise ValueError(f"Name/version in {relative} must match plugin.json")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"Release tag {tag!r} must match manifest version v{version}")

    for relative in ("mcp.json", ".mcp.json", ".codex-plugin/mcp.json"):
        config = read_json(files, relative)
        if not isinstance(config.get("mcpServers"), dict) or not config["mcpServers"]:
            raise ValueError(f"{relative} must declare an MCP server")
    if read_json(files, "mcp.json").get("$schema") != "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json":
        raise ValueError("mcp.json must declare the supported Agent Plugins MCP schema")

    for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
        catalog = read_json(files, relative)
        if catalog.get("name") != "tkoi" or not isinstance(catalog.get("plugins"), list):
            raise ValueError(f"{relative} must declare the tkoi marketplace")
        entries = [entry for entry in catalog["plugins"] if isinstance(entry, dict) and entry.get("name") == name]
        if len(entries) != 1:
            raise ValueError(f"{relative} must contain one entry for {name}")
        source = entries[0].get("source")
        expected = "./" if relative.startswith(".claude-plugin/") else {"source": "local", "path": "./"}
        if source != expected:
            raise ValueError(f"{relative} must load the plugin from the repository root")
    return name, version


def build_release(root: Path, output_dir: Path, tag: str | None = None) -> tuple[Path, Path]:
    files = collect_files(root)
    name, version = validate_metadata(files, tag)
    basename = f"{name}-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{basename}.zip"
    checksum_path = output_dir / f"{basename}.zip.sha256"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".zip", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, content in sorted(files.items()):
                entry = zipfile.ZipInfo(f"{basename}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(entry, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        digest = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
        os.replace(temporary_path, archive_path)
        temporary_path = None
        checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return archive_path, checksum_path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=root / "dist")
    parser.add_argument("--tag", help="Require a release tag matching the manifests, e.g. v2.0.0")
    args = parser.parse_args()
    try:
        archive, checksum = build_release(root, args.output_dir, args.tag)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(archive)
    print(checksum)


if __name__ == "__main__":
    main()
