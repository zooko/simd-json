# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`

if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi

CPUTYPE="${CPUTYPE//[^[:alnum:]]/}"

echo CPU type:
echo $CPUTYPE
echo

echo OS type:
echo $OSTYPE
echo

cargo bench 2>&1 | tee default
for AL in jemalloc mimalloc rpmalloc snmalloc smalloc; do BLNAME=${AL}; cargo bench --features=${AL} 2>&1 | tee ${BLNAME} ; done
./critcmp.py default jemalloc mimalloc rpmalloc snmalloc smalloc
