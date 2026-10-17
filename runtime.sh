#!/bin/bash
# MIT; managed by the Youer Egg installer. No Python dependency.
set -euo pipefail
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
number() {
    [[ $2 =~ ^(0|[1-9][0-9]{0,6})$ ]] || fail "$1 must be a decimal integer without leading zeros"
    (( $2 >= $3 && $2 <= $4 )) || fail "$1 must be in $3..$4 MiB"
}
jar=${SERVER_JARFILE-server.jar}
[[ $jar =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.jar$ ]] || fail 'Invalid SERVER_JARFILE (safe basename ending .jar required)'
[[ -f $jar && ! -L $jar ]] || fail "JAR missing or symlink: $jar. Install/reinstall the selected JAR first."
memory=${SERVER_MEMORY-0}
heap=${HEAP_MB-0}
headroom=${NATIVE_HEADROOM_MB-1024}
unlimited=${UNLIMITED_HEAP_MB-4096}
number SERVER_MEMORY "$memory" 0 1048576
number HEAP_MB "$heap" 0 1048576
number NATIVE_HEADROOM_MB "$headroom" 256 1048576
number UNLIMITED_HEAP_MB "$unlimited" 512 1048576
if (( memory > 0 )); then
    budget=$(( memory - headroom ))
    (( budget >= 512 )) || fail 'SERVER_MEMORY must leave at least 512 MiB heap after native headroom'
    if (( heap == 0 )); then heap=$budget; fi
    (( heap <= budget )) || fail 'HEAP_MB exceeds SERVER_MEMORY minus NATIVE_HEADROOM_MB'
else
    if (( heap == 0 )); then heap=$unlimited; fi
fi
(( heap >= 512 )) || fail 'HEAP_MB must be 0 (automatic) or at least 512 MiB'
printf 'Youer Java heap: %s MiB; native reserve: %s MiB; allocation: %s MiB (0=unlimited).\n' "$heap" "$headroom" "$memory"
# exec preserves console stdin, delivers signals directly, and propagates Java's exit status.
exec java -Xms128M "-Xmx${heap}M" -Dterminal.jline=false -Dterminal.ansi=true -jar "$jar" nogui
