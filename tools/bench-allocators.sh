#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

cd "$REPO_ROOT"
source "$SCRIPT_DIR/tools.sh"

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
echo "smalloc version: $(get_smalloc_dep_version .)" 2>&1 | tee -a $RESF

# Run benchmarks

TMPALLOS=()

echo benchmarking with default allocator…
BLNAME="tmp/default"
cargo --locked --offline bench 2>&1 | tee $BLNAME
TMPALLOS+=("${BLNAME}")

# the rest
for AL in "${ALLOCATOR_LIST[@]}" ; do
    echo benchmarking with ${AL}…
    BLNAME="tmp/$AL"
    cargo --locked --offline bench --features=${AL} 2>&1 | tee $BLNAME
    TMPALLOS+=("${BLNAME}")
done

echo benchmarking with smalloc…
BLNAME="tmp/smalloc"
cargo --locked --offline bench --features=smalloc 2>&1 | tee $BLNAME
TMPALLOS+=("${BLNAME}")

# Generate comparison with metadata passed as arguments
./tools/critcmp.py "${TMPALLOS[@]}" --graph $GRAPHF "${METADATA_ARGS_TO_PASS_TO_PYTHON_SCRIPT[@]}" --smalloc-dep-version $(get_smalloc_dep_version .) 2>&1 | tee -a $RESF

echo "# Results are in \"${RESF}\" ."
