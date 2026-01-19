# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`
if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi
CPUTYPE="${CPUTYPE//[^[:alnum:]]/}"
OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"
ARGS=$*
ARGSSTR="${ARGS//[^[:alnum:]]/}"
BNAME="simd-json"
FNAME="${BNAME}.result.${CPUTYPE}.${OSTYPESTR}.${ARGSSTR}.txt"
RESF="tmp/${FNAME}"
GRAPHF="tmp/${BNAME}.graph.${CPUTYPE}.${OSTYPESTR}.${ARGSSTR}.svg"

echo "# Saving result into \"${RESF}\""
echo "# Saving graph into \"${GRAPHF}\""
rm -f $RESF $GRAPHF
mkdir -p tmp

# Collect metadata
echo "# git log -1 | head -1" 2>&1 | tee -a $RESF
git log -1 | head -1 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF
echo "( [ -z \"$(git status --porcelain)\" ] && echo \"Clean\" || echo \"Uncommitted changes\" )" 2>&1 | tee -a $RESF
( [ -z "$(git status --porcelain)" ] && echo "Clean" || echo "Uncommitted changes" ) 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF
echo "CPU type:" 2>&1 | tee -a $RESF
echo $CPUTYPE 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF
echo "OS type:" 2>&1 | tee -a $RESF
echo $OSTYPE 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF

# Detect which allocators to build (skip snmalloc on Windows)
if [ "x${OSTYPE}" = "xmsys" ]; then
    # no jemalloc or snmalloc on windows
    ALLOCATORS="mimalloc rpmalloc smalloc"
else
    ALLOCATORS="mimalloc rpmalloc jemalloc snmalloc smalloc"
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
    --commit "$(git log -1 --format=%H)" \
    --git-status "$([ -z "$(git status --porcelain)" ] && echo "Clean" || echo "Uncommitted changes")" \
    --cpu "$CPUTYPE" \
    --os "$OSTYPE" \
    --graph "$GRAPHF" \
    2>&1 | tee -a $RESF

echo "# Results are in \"${RESF}\" ."
echo "# Graph is in \"${GRAPHF}\" ."
