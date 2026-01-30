#!/bin/bash
set -e

BNAME="simd-json"

# Collect metadata
GITSOURCE=$(git remote get-url origin)
GITCOMMIT=$(git rev-parse HEAD)
GITCLEANSTATUS=$( [ -z "$( git status --porcelain )" ] && echo \"Clean\" || echo \"Uncommitted changes\" )
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Detect CPU type
# try Linux first
if command -v lscpu >/dev/null 2>&1; then
    CPUTYPE=$(lscpu 2>/dev/null | grep -i "model name" | cut -d':' -f2-)
elif command -v sysctl >/dev/null 2>&1; then
    # macOS
    CPUTYPE=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)
fi
CPUTYPE=${CPUTYPE:-Unknown}
CPUTYPE=${CPUTYPE## }  # Trim leading space

CPUTYPESTR="${CPUTYPE//[^[:alnum:]]/}"
OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"

CPUCOUNT=$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo "${NUMBER_OF_PROCESSORS:-unknown}")

ARGS=$*

CPUSTR_DOT_OSSTR="${CPUTYPESTR}.${OSTYPESTR}"
OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
mkdir -p tmp
rm -f $RESF $GRAPHF

echo "GITCOMMIT: ${GITCOMMIT}" 2>&1 | tee -a $RESF
echo "GITCLEANSTATUS: ${GITCLEANSTATUS}" 2>&1 | tee -a $RESF
echo "CPUTYPE: ${CPUTYPE}" 2>&1 | tee -a $RESF
echo "OSTYPE: ${OSTYPE}" 2>&1 | tee -a $RESF
echo "CPUCOUNT: ${CPUCOUNT}" 2>&1 | tee -a $RESF

mkdir -p ${OUTPUT_DIR}

if [ "x${OSTYPE}" = "xmsys" ]; then
    # no jemalloc or snmalloc on windows
    ALLOCATORS="mimalloc rpmalloc smalloc"
else
    ALLOCATORS="jemalloc snmalloc mimalloc rpmalloc smalloc"
fi

TMPALLOS="tmp/${ALLOCATORS// / tmp/}"

# Run benchmarks
cargo --locked bench 2>&1 | tee tmp/default
for AL in ${ALLOCATORS} ; do 
    BLNAME=${AL}
    cargo --locked bench --features=${AL} 2>&1 | tee tmp/${BLNAME}
done

# Generate comparison with metadata passed as arguments
./critcmp.py tmp/default $TMPALLOS \
    --source "$GITSOURCE" \
    --commit "$GITCOMMIT" \
    --git-status "$GITCLEANSTATUS" \
    --cpu "$CPUTYPE" \
    --os "$OSTYPE" \
    --cpucount "$CPUCOUNT" \
    --graph "$GRAPHF" \
    2>&1 | tee -a $RESF

echo "# Results are in \"${RESF}\" ."
