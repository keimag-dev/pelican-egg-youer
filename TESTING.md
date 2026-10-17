# Verification / handoff

## v1.1.0 JVM tuning

**44 tests passed with real Java21, no skips**, including actual collector/heap/property/stdin/exit checks through the Bash wrapper in all six GC modes. CI requires Java21 rather than silently skipping that probe; native ARM64/x64 × Python3.11/3.13 run the same suite. See [JVM-VERIFICATION.md](JVM-VERIFICATION.md). The earlier full-game results below remain historical v1.0.x payload evidence, not new GC performance measurements.

Publication integration: the standalone repository adds stable-identity and publication guards; **27 local tests passed** (including exact embedded upstream-logo bytes). GitHub's first main-branch CI also passed all four native ARM64/x64 × Python 3.11/3.13 jobs. Real ARM64 game install/start/console/save/normal-stop/SIGTERM/restart/reinstall-preservation and post-reinstall restart passed; see [INTEGRATION.md](INTEGRATION.md) for exact payload hashes and limitations. The older worker-only notes below are retained as provenance, not the current integration status.

## Local automated result

```sh
python -W error -m unittest discover -s youer/tests -v
bash -n youer/runtime.sh
```

2026-10-17: **13 tests passed** on Python 3.14.7 / Windows Git Bash. No pip dependencies. The embedded Python heredoc was separately parsed with `ast.parse`; Bash syntax passed. Test network responses and tiny generated ZIP/JARs are **explicit test fixtures**, not claims of a live server run. Runtime tests execute the actual Bash wrapper with a small stand-in `java` executable to inspect argv, stdin, and exit status.

Coverage:
- numeric latest selection independent of list order; exact pin; missing build and invalid/duplicate metadata fail closed;
- invalid version / JAR path / shell fragments / gameplay enums / numeric ranges / multiline values;
- escaped Unicode, backslashes, leading spaces in Java properties;
- real temporary filesystem, verified atomic replacement, checksum/JAR failures, interrupted transport cleanup;
- first-install defaults, EULA false, reinstall byte preservation of custom properties/EULA/world/mod/plugin/custom file;
- managed directory ownership and deterministic self-contained native PLCN_v3 export;
- bounded / explicit / unlimited heap, oversized heap refusal, integer validation before Bash arithmetic;
- console stdin delivery and executed-process exit-code propagation;
- optional HTTPS update_url with null default.

### Incremental RED → GREEN evidence

Each production behavior below was added after running its specific new failing test. Full-suite runs followed each GREEN. This is the observed sequence, not a claim that all assertions existed at once.

| Slice | Observed RED | GREEN implementation |
|---|---|---|
| latest resolution | missing `resolve_build` | numeric max (1 passing test) |
| exact build / strict metadata | requested7 returned920 | exact match + metadata validation (2) |
| configuration / properties | missing `parse_config` | validated defaults and property escaping (3) |
| verified JAR replacement | missing `download_jar` | stream/hash/JAR check + atomic replace (4) |
| install + reinstall preservation | missing `install` | create-only config/EULA, owned helpers (5) |
| Bash runtime / exit status | missing runtime file (after fixing Windows test-launch path) | `exec java` and bounded heap (6) |
| explicit / unlimited heap + bad values | 13 subcases failed | validated Bash heap policy (7) |
| standalone export | missing `export_egg` | native objects, embedded source, CLI (8) |
| unowned `.youer` collision | attempted network instead of refusing | reject before network/write (9) |
| properties leading spaces | literal spaces were unescaped | preserve leading spaces (10) |
| heap1..511 rejection at install | HEAP_MB511 accepted | installer validation + matching UI rule (still10) |
| opt-in update URL | keyword argument unsupported | optional HTTPS parameter/CLI (11) |
| standalone MIT notice | permission/copyright text missing from export | embed own LICENSE in `_comment` (13, after regression additions) |

Finally, regression-only tests exercised existing stdin and interrupted-transport guarantees without new production behavior (13 passing). Early Windows harness failures were not treated as feature verification: native subprocess lookup selected the Windows system Bash before PATH; the harness now resolves Git Bash explicitly with `shutil.which`, and passes POSIX drive paths only to Bash scripts. Native Python/file paths remain native.

## Read-only upstream checks (actually performed)

- TinyFish first: official Youer README and current Pelican repository discovery; official API build-list content.
- Structured HTTPS GET with `User-Agent: pelican-youer-egg/1.0`: `https://api.mohistmc.com/project/youer/1.21.1/builds` returned595 entries. The actual production resolver accepted the complete list and selected920.
- `HEAD https://api.mohistmc.com/project/youer/1.21.1/builds/920/download`: HTTP200, Content-Length128324527, binary attachment.
- SHA-256 of an already-present build920 JAR was recomputed read-only and matched live API: `ccb6e44668919d6a5a69aeffbe3fefb71f7c9c6127cc01ea1febc3f20f32fca1`.
- Existing JAR manifest: runnable `Main-Class: com.mohistmc.launcher.youer.Main`, implementation `1.21.1-e3158632`.
- Official current Paper YAML confirmed `meta.version=PLCN_v3`, `startup_commands`, native config objects, `rules` arrays and `features: eula/java_version/pid_limit`.
- Initial optional project-root API lookup returned403; it is **not** used by the installer. The exact version/build endpoint above succeeded. No unverified version fallback was introduced.

## Isolated Linux integration gate — parent/integrator

**Not performed by this worker.** No Panel import, OCI operation, public exposure, existing-game modification, or Git write was made. ARM64 full install/start/stop/restart/reinstall, model/importer validation, and actual Java signal behavior remain the integrator's gates. AMD64 needs its own real smoke test; multiarch images alone do not prove every mod/plugin is portable.

Use a new empty owned directory only. No existing game volume, host package installation, Docker daemon setting, firewall, or Panel state change is needed.

### Exact installer procedure

1. Load `egg-youer.json`; write `scripts.installation.script` to a QA-side `install.sh` **outside** the mounted server directory. Convert `qa-env.json` string entries to a Docker env file (`KEY=value` per line).
2. Run the exact declared installation container `debian:bookworm-slim`, entrypoint `bash`, mount the empty server directory at `/mnt/server`, the QA script read-only at `/qa/install.sh`, and run `/qa/install.sh`. Root is required **only inside this disposable installer** for apt. Suggested resource budget:2CPUs,1536MiB RAM,30-minute outer timeout,10GiB free disk. The download itself has a15-minute safety deadline. Normal network egress is required for apt and official API.
3. Verify JAR SHA-256 from `.youer/install.json`, `server.properties` defaults and `eula=false`. Verify invalid version/build errors do not replace the old JAR. Keep logs outside server state if comparing preservation.

### Exact runtime procedure

1. User must explicitly accept Minecraft EULA for this QA run. The integrator has separately obtained QA consent; this document is **not** consent for others. Set `eula=true` only in the new disposable QA volume after checking authorization.
2. Mount the server directory at `/home/container` with working directory `/home/container` in `ghcr.io/pelican-eggs/yolks:java_21`. Use the image's nonroot UID/GID (integrator observed1001:1001 on its ARM64 digest), writable volume ownership, and `qa-env.json` values. Run through the standard image entrypoint with `STARTUP=bash .youer/start.sh`, or invoke `bash .youer/start.sh` directly as that user when deliberately bypassing the entrypoint for the harness. **No runtime Python.**
3. Budget:2CPUs,6144MiB container RAM, HEAP_MB4096, native reserve1024, disk10GiB+,60-minute outer allowance for first library download, normal stdout/stderr and attached stdin. Do not enforce a gameplay lifetime timeout from within the runtime wrapper.
4. Wait for actual `)! For help, type ` readiness. Send `list` then `stop` via stdin; verify responses, process exit, saved world, no orphan Java. Restart; test SIGTERM separately and verify graceful game shutdown/exit propagation. This signal gate needs Linux, not a Windows Ctrl-C emulation.
5. Before reinstall snapshot hashes of properties, EULA, worlds, mods, plugins, whitelist/ops/bans and sentinel custom files. Stop first. Re-run the exact installer (optionally change initial-default variables) and compare user-state hashes **before starting Java again**. Managed helper files and selected JAR may change; gameplay files must not. Re-start and verify readiness.
6. For a plain Docker harness, native Pelican `config.files` does not run automatically. For allocation testing, reproduce only its documented port/bind changes or use the real parser in a non-persistent validation harness. Do not silently claim this proves a Panel-managed server lifecycle.

### CI / publication

Independent-repo commands after copying this directory's contents to a repo root:

```sh
python -W error -m unittest discover -s tests -v
python -m compileall -q installer.py build_egg.py tests
bash -n runtime.sh
python build_egg.py
# Integrator may now compare the regenerated artifact with the tracked artifact.
```

When the artifact actually exists at a public HTTPS URL, set it explicitly using `python build_egg.py --update-url "$PUBLISHED_EGG_URL"`. Run this same command after tests in CI because the exporter unit test intentionally verifies the default-null artifact. No URL/repository/publication is invented here. Parent owns repository creation, Actions configuration and publication.
