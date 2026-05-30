#!/bin/bash
set -e

source "$(dirname "$0")/tools.sh"

BNAME="simd-json"

# Output files
RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
mkdir -p tmp
rm -f $RESF $GRAPHF

echo "TIMESTAMP: ${TIMESTAMP}" 2>&1 | tee -a $RESF
gather_and_print_git_metadata 2>&1 | tee -a $RESF
print_machine_metadata 2>&1 | tee -a $RESF
gather_and_print_smalloc_dep_version 2>&1 | tee -a $RESF

# Run benchmarks

TMPALLOS=()

echo benchmarking with default allocator…
BLNAME="tmp/default"
cargo --offline bench 2>&1 | tee $BLNAME
TMPALLOS+=("${BLNAME}")

echo benchmarking with smalloc…
BLNAME="tmp/smalloc"
cargo --offline bench --features=smalloc 2>&1 | tee $BLNAME
TMPALLOS+=("${BLNAME}")

# the rest
for AL in "${ALLOCATOR_LIST[@]}" ; do
    echo benchmarking with ${AL}…
    BLNAME="tmp/$AL"
    cargo --offline bench --features=${AL} 2>&1 | tee $BLNAME
    TMPALLOS+=("${BLNAME}")
done

# Generate comparison with metadata passed as arguments
./critcmp.py "${TMPALLOS[@]}" --graph $GRAPHF "${METADATA_ARGS_TO_PASS_TO_PYTHON_SCRIPT[@]}" 2>&1 | tee -a $RESF

echo "# Results are in \"${RESF}\" ."
