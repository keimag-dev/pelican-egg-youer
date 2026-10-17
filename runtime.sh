#!/bin/bash
# MIT; managed by the Youer Egg installer. No Python dependency.
set -euo pipefail
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
number() {
    [[ $2 =~ ^(0|[1-9][0-9]{0,6})$ ]] || fail "$1 must be a decimal integer without leading zeros"
    (( $2 >= $3 && $2 <= $4 )) || fail "$1 must be in $3..$4 MiB"
}
for inherited in JAVA_TOOL_OPTIONS JDK_JAVA_OPTIONS _JAVA_OPTIONS; do
    [[ -z ${!inherited-} ]] || fail "$inherited must be empty; use the Egg JVM fields instead"
done
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
initial=${INITIAL_HEAP_MB-128}
number INITIAL_HEAP_MB "$initial" 16 1048576
(( initial <= heap )) || fail 'INITIAL_HEAP_MB (-Xms) exceeds effective HEAP_MB (-Xmx)'
gc_args=()
case ${GC_MODE-default} in
    default) ;;
    g1) gc_args=(-XX:+UseG1GC) ;;
    zgc) gc_args=(-XX:+UseZGC) ;;
    zgc-generational) gc_args=(-XX:+UseZGC -XX:+ZGenerational) ;;
    parallel) gc_args=(-XX:+UseParallelGC) ;;
    serial) gc_args=(-XX:+UseSerialGC) ;;
    *) fail 'GC_MODE must be default, g1, zgc, zgc-generational, parallel or serial' ;;
esac
# Launcher-like grouping only, never shell evaluation. Single quotes are literal;
# backslash escapes one following character outside single quotes (also in double quotes).
# Input and token count are bounded by 4096 characters; only ASCII spaces delimit.
parse_extra_args() {
    local input=$1 token='' state=plain escaped=0 started=0 char i
    (( ${#input} <= 4096 )) || fail 'EXTRA_JVM_ARGS must be at most 4096 characters'
    [[ ! $input =~ [[:cntrl:]] ]] || fail 'EXTRA_JVM_ARGS cannot contain control characters'
    for (( i=0; i<${#input}; i++ )); do
        char=${input:i:1}
        if (( escaped )); then
            token+=$char; escaped=0; continue
        fi
        if [[ $state == single ]]; then
            if [[ $char == "'" ]]; then state=plain; else token+=$char; fi
        elif [[ $char == '\' ]]; then
            escaped=1; started=1
        elif [[ $state == double ]]; then
            if [[ $char == '"' ]]; then state=plain; else token+=$char; fi
        else
            case $char in
                "'") state=single; started=1 ;;
                '"') state=double; started=1 ;;
                ' ') if (( started )); then extra_args+=("$token"); token=''; started=0; fi ;;
                *) token+=$char; started=1 ;;
            esac
        fi
    done
    (( escaped == 0 )) || fail 'EXTRA_JVM_ARGS has a dangling escape'
    [[ $state == plain ]] || fail 'EXTRA_JVM_ARGS has an unclosed quote'
    if (( started )); then extra_args+=("$token"); fi
}
validate_extra_arg() {
    local arg=$1 option
    case $arg in
        -Xmx*|-Xms*) fail 'EXTRA_JVM_ARGS cannot set heap: use HEAP_MB (-Xmx) and INITIAL_HEAP_MB (-Xms)' ;;
        -XX:*)
            option=${arg#-XX:}
            option=${option#[+-]}
            option=${option%%=*}
            case $option in
                MaxHeapSize|InitialHeapSize|MinHeapSize)
                    fail 'EXTRA_JVM_ARGS cannot set heap: use HEAP_MB and INITIAL_HEAP_MB' ;;
                Use*GC|ZGenerational) fail 'EXTRA_JVM_ARGS cannot select or negate collectors: use GC_MODE' ;;
                Flags|VMOptionsFile) fail 'EXTRA_JVM_ARGS cannot load JVM option files' ;;
                PrintFlagsInitial|PrintFlagsWithComments|IgnoreUnrecognizedVMOptions)
                    fail 'EXTRA_JVM_ARGS cannot request exit-only or ignore-unrecognized JVM behavior' ;;
            esac
            [[ $arg =~ ^-XX:([+-][A-Za-z][A-Za-z0-9_]*|[A-Za-z][A-Za-z0-9_]*=.*)$ ]] && return 0
            ;;
        -X|-Xinternalversion*|-Xshare:dump*|-Xlog:help*|-Xbootclasspath*)
            fail 'EXTRA_JVM_ARGS cannot request help, exit-only behavior or classpath changes' ;;
        -D*) [[ $arg =~ ^-D[^=[:space:]]+(=.*)?$ ]] && return 0 ;;
        -X?*) return 0 ;;
        --add-opens=?*|--add-exports=?*|--add-reads=?*|--enable-native-access=?*) return 0 ;;
    esac
    # Never print the argument: system properties can contain secrets.
    fail 'EXTRA_JVM_ARGS contains an unsupported option; use -D, -XX:, -X tuning or supported --option=value forms (not main/classpath/module selectors or @argfiles)'
}
extra_args=()
parse_extra_args "${EXTRA_JVM_ARGS-}"
for arg in "${extra_args[@]}"; do validate_extra_arg "$arg"; done
printf 'Youer Java heap: %s MiB; native reserve: %s MiB; allocation: %s MiB (0=unlimited).\n' "$heap" "$headroom" "$memory"
# exec preserves console stdin, delivers signals directly, and propagates Java's exit status.
exec java "-Xms${initial}M" "-Xmx${heap}M" -Dterminal.jline=false -Dterminal.ansi=true "${gc_args[@]}" "${extra_args[@]}" -jar "$jar" nogui
