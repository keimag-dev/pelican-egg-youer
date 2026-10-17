"""Standalone Youer installer (stdlib only); embedded by build_egg.py."""


import re
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
import zipfile


def open_https(url):
    """Bounded public HTTPS transport with certificate verification and no downgrade."""
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS is permitted")
    request = urllib.request.Request(url, headers={"User-Agent": "pelican-youer-egg/1.0", "Accept": "*/*"})
    response = urllib.request.urlopen(request, timeout=60)
    if not response.url.startswith("https://"):
        response.close()
        raise ValueError("Refusing non-HTTPS redirect")
    return response


def download_jar(target, url, expected_sha256, opener=open_https):
    """Stream to same-filesystem temporary file, verify, then atomically replace."""
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError(f"Refusing non-regular JAR destination: {target.name}")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("Missing or invalid SHA-256")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".youer-download-", delete=False) as out:
            temp_path = Path(out.name)
            digest = hashlib.sha256()
            size = 0
            deadline = time.monotonic() + 900
            with opener(url) as response:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 1024 * 1024 * 1024 or time.monotonic() > deadline:
                        raise ValueError("Download exceeded 1 GiB or 15-minute safety budget")
                    out.write(chunk)
                    digest.update(chunk)
            out.flush()
            os.fsync(out.fileno())
        if digest.hexdigest() != expected_sha256.lower():
            raise ValueError("JAR SHA-256 mismatch; previous JAR left untouched")
        try:
            with zipfile.ZipFile(temp_path) as jar:
                if "META-INF/MANIFEST.MF" not in jar.namelist():
                    raise ValueError("Downloaded ZIP is not a runnable JAR (no manifest)")
        except zipfile.BadZipFile as exc:
            raise ValueError("Downloaded file is not a JAR/ZIP") from exc
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

DEFAULTS = {
    "MINECRAFT_VERSION": "1.21.1", "YOUER_BUILD": "latest",
    "SERVER_JARFILE": "server.jar", "SERVER_NAME": "Youer Server",
    "MOTD": "A Youer Minecraft Server", "MAX_PLAYERS": "20",
    "GAMEMODE": "survival", "DIFFICULTY": "normal", "ONLINE_MODE": "true",
    "WHITELIST": "false", "VIEW_DISTANCE": "10", "LEVEL_NAME": "world",
    "HEAP_MB": "0", "NATIVE_HEADROOM_MB": "1024", "UNLIMITED_HEAP_MB": "4096",
}


def parse_config(env):
    """Validate before networking or mutation. Gameplay fields are first-install only."""
    cfg = {key: env.get(key, default) for key, default in DEFAULTS.items()}
    patterns = {
        "MINECRAFT_VERSION": r"1\.[0-9]{1,2}(?:\.[0-9]{1,2})?",
        "YOUER_BUILD": r"latest|[1-9][0-9]{0,9}",
        "SERVER_JARFILE": r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.jar",
        "LEVEL_NAME": r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
        "GAMEMODE": r"survival|creative|adventure|spectator",
        "DIFFICULTY": r"peaceful|easy|normal|hard",
        "ONLINE_MODE": r"true|false", "WHITELIST": r"true|false",
    }
    for key, pattern in patterns.items():
        if not re.fullmatch(pattern, cfg[key]):
            raise ValueError(f"Invalid {key}: does not match {pattern}")
    ranges = {"MAX_PLAYERS": (1, 10000), "VIEW_DISTANCE": (2, 32),
              "HEAP_MB": (0, 1048576), "NATIVE_HEADROOM_MB": (256, 1048576),
              "UNLIMITED_HEAP_MB": (512, 1048576)}
    for key, (low, high) in ranges.items():
        if not re.fullmatch(r"0|[1-9][0-9]{0,6}", cfg[key]) or not low <= int(cfg[key]) <= high:
            raise ValueError(f"Invalid {key}: expected integer {low}..{high} without leading zeros")
    if 0 < int(cfg["HEAP_MB"]) < 512:
        raise ValueError("Invalid HEAP_MB: use 0 (automatic) or at least 512 MiB")
    for key in ("SERVER_NAME", "MOTD"):
        if not 1 <= len(cfg[key]) <= 256 or any(ord(c) < 32 or ord(c) == 127 for c in cfg[key]):
            raise ValueError(f"Invalid {key}: expected 1..256 printable characters, no line breaks")
    return cfg


def properties_text(cfg):
    def escape(value):
        result = []
        for index, char in enumerate(value):
            if char == " " and not value[:index].strip(" "):
                result.append("\\ ")
            elif char == "\\":
                result.append("\\\\")
            elif ord(char) > 127:
                encoded = char.encode("utf-16-be")
                result.extend("\\u" + encoded[i:i + 2].hex() for i in range(0, len(encoded), 2))
            else:
                result.append(char)
        return "".join(result)
    fields = {"server-name": "SERVER_NAME", "motd": "MOTD", "max-players": "MAX_PLAYERS",
              "gamemode": "GAMEMODE", "difficulty": "DIFFICULTY", "online-mode": "ONLINE_MODE",
              "white-list": "WHITELIST", "view-distance": "VIEW_DISTANCE", "level-name": "LEVEL_NAME"}
    return ("# Initial defaults only. Edit this file after first installation.\n"
            + "server-ip=\nserver-port=25565\nquery.port=25565\n"
            + "".join(f"{key}={escape(cfg[value])}\n" for key, value in fields.items()))


def resolve_build(rows, requested):
    """Resolve only an advertised numeric build; never silently fall back."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("Official API returned no builds for this Minecraft version")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or type(row.get("id")) is not int
                or row["id"] < 1 or row["id"] in seen
                or not re.fullmatch(r"[0-9a-fA-F]{64}", str(row.get("file_sha256", "")))):
            raise ValueError("Invalid or duplicate build/checksum in official API response")
        seen.add(row["id"])
    if requested == "latest":
        return max(rows, key=lambda row: row["id"])
    if not re.fullmatch(r"[1-9][0-9]{0,9}", requested):
        raise ValueError("YOUER_BUILD must be latest or a positive numeric build (no leading zeros)")
    for row in rows:
        if row["id"] == int(requested):
            return row
    raise ValueError(f"Youer build {requested} is not advertised for the selected Minecraft version")


def atomic_text(path, text, mode=0o644):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".youer-write-", delete=False) as out:
            temp_path = Path(out.name)
            out.write(text.encode("utf-8"))
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def install(root, env, runtime_source, opener=open_https):
    """Change only selected JAR and owned helpers; create defaults only if absent."""
    cfg = parse_config(env)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    managed = root / ".youer"
    for path in (root / cfg["SERVER_JARFILE"], root / "server.properties", root / "eula.txt",
                 managed / "start.sh", managed / "install.json"):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"Refusing non-regular installer destination: {path.name}")
    if managed.is_symlink() or (managed.exists() and not managed.is_dir()):
        raise ValueError("Refusing unsafe .youer managed directory")
    if managed.exists() and any(managed.iterdir()) and not (managed / "start.sh").exists():
        raise ValueError("Existing .youer directory is not owned by this installer; rename it first")
    if (managed / "start.sh").exists():
        try:
            previous = json.loads((managed / "install.json").read_text(encoding="utf-8"))
            actual = hashlib.sha256((managed / "start.sh").read_bytes()).hexdigest()
            if previous["runtime_sha256"] != actual:
                raise ValueError("Managed runtime was modified; back it up and remove .youer before reinstall")
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("Existing .youer/start.sh is not owned by this installer") from exc
    base = "https://api.mohistmc.com/project/youer/" + cfg["MINECRAFT_VERSION"] + "/builds"
    with opener(base) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Official build metadata exceeded 4 MiB safety budget")
    row = resolve_build(json.loads(raw), cfg["YOUER_BUILD"])
    url = base + f"/{row['id']}/download"
    download_jar(root / cfg["SERVER_JARFILE"], url, row["file_sha256"], opener)
    for name, text in (("server.properties", properties_text(cfg)), ("eula.txt", "eula=false\n")):
        path = root / name
        if not path.exists():
            with path.open("x", encoding="utf-8", newline="\n") as out:
                out.write(text)
    managed.mkdir(exist_ok=True)
    atomic_text(managed / "start.sh", runtime_source, 0o755)
    metadata = {"minecraft_version": cfg["MINECRAFT_VERSION"], "build": row["id"],
                "jar": cfg["SERVER_JARFILE"], "sha256": row["file_sha256"].lower(),
                "download_url": url, "runtime_sha256": hashlib.sha256(runtime_source.encode()).hexdigest()}
    atomic_text(managed / "install.json", json.dumps(metadata, indent=2) + "\n")
    print(f"Installed Youer {cfg['MINECRAFT_VERSION']} build {row['id']} as {cfg['SERVER_JARFILE']} (SHA-256 verified).")
    print("Existing user files preserved. EULA is NOT accepted by this installer.")
    return metadata
