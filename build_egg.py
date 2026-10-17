"""Build the standalone Pelican import artifact (no third-party dependencies)."""
import argparse
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

from installer import DEFAULTS

BASE = Path(__file__).resolve().parent


def export_egg(update_url=None):
    if update_url is not None:
        parsed = urlsplit(update_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("update_url must be an explicit public HTTPS artifact URL without credentials")
    installer = (BASE / "installer.py").read_text(encoding="utf-8")
    runtime = (BASE / "runtime.sh").read_text(encoding="utf-8")
    script = ("#!/bin/bash\nset -euo pipefail\nexport DEBIAN_FRONTEND=noninteractive\n"
              "apt-get update\napt-get install -y --no-install-recommends python3 ca-certificates\n"
              "python3 - <<'YOUER_INSTALL_PY'\n" + installer
              + "\nRUNTIME_SOURCE = " + repr(runtime)
              + '\ntry:\n    install(Path("/mnt/server"), os.environ, RUNTIME_SOURCE)\n'
              + 'except Exception as exc:\n    print(f"ERROR: Youer installation failed: {exc}", file=__import__("sys").stderr)\n    raise SystemExit(1)\n'
              + "YOUER_INSTALL_PY\n")
    specifications = [
        ("MINECRAFT_VERSION", "Minecraft Version", "Install/reinstall: explicit official Minecraft version; no fallback. Java 21 verified with 1.21.1.", ["required", "string", r"regex:/^1\.[0-9]{1,2}(\.[0-9]{1,2})?$/"]),
        ("YOUER_BUILD", "Youer Build", "Install/reinstall: latest selects highest advertised build for this Minecraft version; numeric pins exactly. Missing builds fail.", ["required", "string", r"regex:/^(latest|[1-9][0-9]{0,9})$/"]),
        ("SERVER_JARFILE", "Server Jar File", "Install and start: safe JAR basename. Changing this requires reinstall; only the selected JAR is replaced.", ["required", "string", r"regex:/^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.jar$/"]),
        ("SERVER_NAME", "Server Name", "First install only: server-name property (not displayed by all Minecraft clients). Existing server.properties is never replaced.", ["required", "string", "max:256", r"not_regex:/[\x00-\x1f\x7f]/"]),
        ("MOTD", "Message of the Day", "First install only: server-list MOTD. No line breaks; edit server.properties after installation.", ["required", "string", "max:256", r"not_regex:/[\x00-\x1f\x7f]/"]),
        ("MAX_PLAYERS", "Maximum Players", "First install only: max-players; edit server.properties for an existing server.", ["required", "integer", "between:1,10000"]),
        ("GAMEMODE", "Game Mode", "First install only: default mode for new players.", ["required", "string", "in:survival,creative,adventure,spectator"]),
        ("DIFFICULTY", "Difficulty", "First install only: default difficulty.", ["required", "string", "in:peaceful,easy,normal,hard"]),
        ("ONLINE_MODE", "Online Mode", "First install only: authenticate with Mojang/Microsoft. Keep true unless intentionally using a secured proxy configuration.", ["required", "string", "in:true,false"]),
        ("WHITELIST", "Whitelist Enabled", "First install only: toggles white-list; never adds identities or replaces whitelist.json.", ["required", "string", "in:true,false"]),
        ("VIEW_DISTANCE", "View Distance", "First install only: chunk radius (2..32). Larger values increase memory and CPU needs.", ["required", "integer", "between:2,32"]),
        ("LEVEL_NAME", "World Name", "First install only: safe world directory basename. Reinstall does not rename, delete, or replace worlds.", ["required", "string", r"regex:/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/"]),
        ("HEAP_MB", "Maximum Java Heap -Xmx (MiB)", "Every start: 0 = allocation minus native headroom. Explicit 512+ must fit that budget. With unlimited allocation, 0 uses Unlimited Heap.", ["required", "integer", "between:0,1048576", r"regex:/^(0|51[2-9]|5[2-9][0-9]|[6-9][0-9]{2}|[1-9][0-9]{3,6})$/"]),
        ("INITIAL_HEAP_MB", "Initial Java Heap -Xms (MiB)", "Every start: initial heap (default 128); 16+ and no greater than the effective maximum Java heap (-Xmx).", ["required", "integer", "between:16,1048576", r"regex:/^[1-9][0-9]{0,6}$/"]),
        ("GC_MODE", "Garbage Collector", "Every start: default (recommended) preserves JVM ergonomics. Optional g1, zgc, zgc-generational (Java 21), parallel or serial. No performance guarantee; use this field, not extra collector flags.", ["required", "string", "in:default,g1,zgc,zgc-generational,parallel,serial"]),
        ("EXTRA_JVM_ARGS", "Extra JVM Arguments", "Every start: optional space-separated JVM tuning (max 4096 characters). Quotes/backslash group arguments; no shell expansion. Heap/GC must use dedicated fields; no entrypoint, classpath, @argfile or JVM option-file overrides. See README.", ["nullable", "string", "max:4096", r"not_regex:/[\x00-\x1f\x7f]/"]),
        ("NATIVE_HEADROOM_MB", "Native Memory Headroom (MiB)", "Every start: reserve outside Java heap for metaspace, threads and native buffers (minimum 256, default 1024). Not an OS memory limit.", ["required", "integer", "between:256,1048576", r"regex:/^[1-9][0-9]{0,6}$/"]),
        ("UNLIMITED_HEAP_MB", "Unlimited Allocation Heap (MiB)", "Every start: bounded heap when SERVER_MEMORY=0 and Java Heap=0; default 4096. Size the host/container separately.", ["required", "integer", "between:512,1048576", r"regex:/^[1-9][0-9]{0,6}$/"]),
    ]
    variables = [{"sort": index, "name": name, "description": description, "env_variable": key,
                  "default_value": DEFAULTS[key], "user_viewable": True, "user_editable": True, "rules": rules}
                 for index, (key, name, description, rules) in enumerate(specifications, 1)]
    return {
        "_comment": "Generated by build_egg.py; no game binaries included. License applies only to this Egg's own source.\n\n" + (BASE / "LICENSE").read_text(encoding="utf-8"),
        "meta": {"version": "PLCN_v3", "update_url": update_url},
        "name": "Youer", "author": "61485115+keimag-dev@users.noreply.github.com",
        "icon": "data:image/webp;base64," + base64.b64encode((BASE / "assets/youer.webp").read_bytes()).decode("ascii"),
        "uuid": "9c54a900-d7c4-48d0-9ce3-9b9c2fb53017",
        "description": "Generic Youer (NeoForge + Paper/Purpur hybrid) on Java 21. Verified SHA-256 downloads, exact version/build selection, safe reinstall and explicit EULA consent. No modpack included.",
        "tags": ["minecraft", "java", "youer", "neoforge"],
        "features": ["eula", "java_version", "pid_limit"],
        "docker_images": {"Java 21": "ghcr.io/pelican-eggs/yolks:java_21"},
        "file_denylist": [], "startup_commands": {"Default": "exec bash .youer/start.sh"},
        "config": {"files": {"server.properties": {"parser": "properties", "find": {
            "server-ip": "", "server-port": "{{server.allocations.default.port}}",
            "query.port": "{{server.allocations.default.port}}"}}},
            "startup": {"done": ")! For help, type "}, "logs": {}, "stop": "stop"},
        "scripts": {"installation": {"script": script, "container": "debian:bookworm-slim", "entrypoint": "bash"}},
        "variables": variables,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-url", default=None, help="Only set after the artifact has a real public HTTPS URL")
    args = parser.parse_args()
    target = BASE / "egg-youer.json"
    target.write_text(json.dumps(export_egg(update_url=args.update_url), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(target)
