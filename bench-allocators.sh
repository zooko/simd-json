#!/bin/bash

BNAME="simd-json"

# Collect metadata
GITCOMMIT="$(git log -1 | head -1 | cut -d' ' -f2)"
GITCLEANSTATUS=$( [ -z "$( git status --porcelain )" ] && echo \"Clean\" || echo \"Uncommitted changes\" )
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`
if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi
CPUTYPESTR="${CPUTYPE//[^[:alnum:]]/}"
OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"
ARGS=$*
CPUSTR_DOT_OSSTR="${CPUTYPESTR}.${OSTYPESTR}"
OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}

echo "# Saving result into \"${RESF}\""
echo "# Saving graph into \"${GRAPHF}\""
rm -f $RESF $GRAPHF
mkdir -p tmp

if [ "x${OSTYPE}" = "xmsys" ]; then
    # no jemalloc or snmalloc on windows
    ALLOCATORS="mimalloc rpmalloc smalloc"
else
    ALLOCATORS="jemalloc snmalloc mimalloc rpmalloc smalloc"
fi

TMPALLOS="tmp/${ALLOCATORS// / tmp/}"

set -e
# Run benchmarks
cargo --locked bench 2>&1 | tee tmp/default
for AL in ${ALLOCATORS} ; do 
    BLNAME=${AL}
    cargo --locked bench --features=${AL} 2>&1 | tee tmp/${BLNAME}
done

# Generate comparison with metadata passed as arguments
./critcmp.py tmp/default $TMPALLOS \
    --commit "$GITCOMMIT" \
    --git-status "$GITCLEANSTATUS" \
    --cpu "$CPUTYPE" \
    --os "$OSTYPE" \
    --graph "$GRAPHF" \
    2>&1 | tee -a $RESF

echo "# Results are in \"${RESF}\" ."
echo "# Graph is in \"${GRAPHF}\" ."
