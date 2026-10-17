# JVM tuning verification — v1.1.0

## What's configurable

- Existing `HEAP_MB` still controls `-Xmx`;0 retains the allocation-minus-native-reserve policy. Its UI label now explicitly names `-Xmx`.
- `INITIAL_HEAP_MB` controls `-Xms`, default128MiB, never larger than effective maximum heap.
- `GC_MODE` defaults to JVM ergonomics; optional G1, non-generational ZGC, Java21 Generational ZGC, Parallel or Serial.
- `EXTRA_JVM_ARGS` supports bounded launcher-like quote/backslash grouping without `eval`, shell expansion or runtime Python. Dedicated heap/collector settings, entrypoint selectors, nested option files and conflicting inherited Java options are rejected. See README for the precise supported syntax, not a claim of accepting every Java launcher option.

## Real JVM acceptance, not a game benchmark

The real Bash runtime was executed with a generated tiny Java probe JAR and **Temurin HotSpot21.0.12.1+1** on Windows x64. The portable JRE archive was verified against official SHA256 metadata/checksum; it was not installed system-wide. The probe was compiled for Java21 using `javac --release21`.

For all six modes (`default`, `g1`, `zgc`, `zgc-generational`, `parallel`, `serial`) the test checks actual HotSpotDiagnosticMXBean values, not just printed command arguments:

- `MaxHeapSize` matches requested512MiB and `InitialHeapSize` matches128MiB.
- The requested collector flag is active, with `ZGenerational` enabled only for the generational ZGC option.
- A quoted property value containing a space arrives intact.
- Console stdin and application exit code propagate through the actual launcher.

**44 local tests passed, no skips** with the portable Java21 explicitly selected. Other tests cover malformed/oversized inputs, shell-substitution payloads not executing, protected heap/collector aliases, option files, hidden Java option variables, defaults, download preservation and generated exports. An environment with no Java21 may skip only the real-JVM probe locally; CI sets `REQUIRE_REAL_JAVA=1` so that absence is a failure. CI installs pinned-action Temurin21 on the existing native ARM64/x64 × Python3.11/3.13 matrix and runs the same real probe.

These tests **do not measure Minecraft tick times, mod compatibility or GC performance**. Full real Youer lifecycle observations for the earlier v1.0.x payload remain in [INTEGRATION.md](INTEGRATION.md). The new runtime's missing/new-field defaults are tested to produce the exact previous argv; that is backward-compatibility evidence, not a fresh game/soak test of every collector.

## Updating an existing installation

Updating/importing the Egg definition adds the UI fields, but does not replace an installed `.youer/start.sh`. Existing users need a stopped, backed-up reinstall to refresh the managed helper before the new controls can take effect. Pin the existing Minecraft version/build when only updating the helper to avoid an unintended upstream game upgrade. Once on the new helper, tuning changes apply at the next restart. Do not automatically migrate a different older Youer+Create Egg or touch a running server.

## Java21 references

- [Oracle: available collectors and selecting a collector](https://docs.oracle.com/en/java/javase/21/gctuning/available-collectors.html)
- [Oracle: ZGC / Generational ZGC and heap sizing](https://docs.oracle.com/en/java/javase/21/gctuning/z-garbage-collector.html)

JVM ergonomics is the recommended starting point. A collector change is not a guaranteed speedup; compare memory, CPU and pause behavior for the actual workload. No host huge-page, kernel, firewall or service changes are performed by this feature.
