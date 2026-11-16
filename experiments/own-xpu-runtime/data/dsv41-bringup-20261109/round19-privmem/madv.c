// madv.c: cost of the answer step's engram row requests on this host (CPU only). mmap the engram shard read-only
// (MADV_RANDOM as the engine), pick 48 random 176-byte rows per "step" in its last 100 GB, and time: (1) 48
// madvise(WILLNEED) calls (main thread today), (2) then touching the 48 rows (the card thread's copy waits for any
// read still in flight), for cold rows (random) and warm rows (the same rows again).
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
int main(int argc, char **argv) {
    const char *p = argv[1];
    int steps = argc > 2 ? atoi(argv[2]) : 50;
    int fd = open(p, O_RDONLY); struct stat st; fstat(fd, &st);
    const uint8_t *m = mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (m == MAP_FAILED) { perror("mmap"); return 1; }
    madvise((void *)m, st.st_size, MADV_RANDOM);
    const long pg = sysconf(_SC_PAGESIZE);
    const size_t lo = st.st_size - (size_t)100e9, rb = 176;
    srand(12345);
    double tm[2] = {0}, tt[2] = {0}; long mj[2] = {0}, mn[2] = {0}, vc[2] = {0};
    uint8_t buf[176]; unsigned sink = 0;
    for (int s = 0; s < steps; ++s) {
        size_t off[48];
        for (int k = 0; k < 48; ++k) off[k] = lo + ((((size_t)rand() << 31) ^ (size_t)rand()) % ((size_t)100e9 / rb)) * rb;
        for (int w = 0; w < 2; ++w) { // w 0: cold, 1: the same rows again (warm)
            struct rusage a, b; getrusage(RUSAGE_THREAD, &a);
            double t0 = now();
            for (int k = 0; k < 48; ++k) {
                uintptr_t x = (uintptr_t)(m + off[k]), x0 = x & ~(uintptr_t)(pg - 1);
                madvise((void *)x0, x + rb - x0, MADV_WILLNEED);
            }
            double t1 = now();
            for (int k = 0; k < 48; ++k) { memcpy(buf, m + off[k], rb); sink += buf[0] + buf[175]; }
            double t2 = now();
            getrusage(RUSAGE_THREAD, &b);
            tm[w] += t1 - t0; tt[w] += t2 - t1;
            mj[w] += b.ru_majflt - a.ru_majflt; mn[w] += b.ru_minflt - a.ru_minflt; vc[w] += b.ru_nvcsw - a.ru_nvcsw;
        }
        usleep(10000);
    }
    for (int w = 0; w < 2; ++w)
        printf("%s rows: 48 madvise %.1f us, then 48 row copies %.1f us per step; per step %.1f major %.1f minor faults, %.1f sleeps\n",
               w ? "warm" : "cold", 1e6 * tm[w] / steps, 1e6 * tt[w] / steps, (double)mj[w] / steps, (double)mn[w] / steps,
               (double)vc[w] / steps);
    return sink == 12345678u;
}
