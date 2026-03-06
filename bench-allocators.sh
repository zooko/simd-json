#!/bin/bash
set -e

source "$(dirname "$0")/gather-metadata.sh"

BNAME="simd-json"

ARGS=$*

OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
mkdir -p tmp
rm -f $RESF $GRAPHF

echo "TIMESTAMP: ${TIMESTAMP}" 2>&1 | tee -a $RESF
gather_and_print_git_metadata 2>&1 | tee -a $RESF
print_machine_metadata 2>&1 | tee -a $RESF

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
./critcmp.py tmp/default $TMPALLOS --graph $GRAPHF "${METADATA_ARGS_TO_PASS_TO_PYTHON_SCRIPT[@]}" 2>&1 | tee -a $RESF

echo "# Results are in \"${RESF}\" ."
