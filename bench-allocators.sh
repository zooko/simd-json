echo CPU type:

# print out CPU type on macos
sysctl -n machdep.cpu.brand_string 2>/dev/null

# print out CPU type on linux
grep "model name" /proc/cpuinfo 2>/dev/null | uniq

cargo bench 2>&1 | tee default
for AL in jemalloc mimalloc rpmalloc snmalloc smalloc; do BLNAME=${AL}; cargo bench --features=${AL} 2>&1 | tee ${BLNAME} ; done
./critcmp.py default jemalloc mimalloc rpmalloc snmalloc smalloc
