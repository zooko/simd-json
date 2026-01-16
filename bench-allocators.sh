# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`

if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi

CPUTYPE="${CPUTYPE//[^[:alnum:]]/}"

OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"

RESF=simd-json.bench-allocators.result.${CPUTYPE}.${OSTYPESTR}.txt

echo "# Saving result into a file named \"${RESF}\" ..."

rm -f $RESF

echo CPU type: 2>&1 | tee -a $RESF
echo $CPUTYPE 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF

echo OS type: 2>&1 | tee -a $RESF
echo $OSTYPE 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF

cargo bench 2>&1 | tee default
for AL in jemalloc mimalloc rpmalloc snmalloc smalloc; do BLNAME=${AL}; cargo bench --features=${AL} 2>&1 | tee ${BLNAME} ; done
./critcmp.py default jemalloc mimalloc rpmalloc snmalloc smalloc 2>&1 | tee -a $RESF
