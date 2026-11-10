// Host cost of the engram row reads: 240 rows of 176 bytes (2 layers x 24 rows x 5 tokens) from the 135 GB shard
// through mmap, as the engine does. (a) madvise(WILLNEED) on rows already cached; (b) new (likely uncached) rows
// touched one after another without a prefetch; (c) new rows with madvise on all of them first, then touched.
// Usage: bench_eng_io <shard> <rounds>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <random>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
int main(int argc, char **argv) {
    if (argc < 3) return 2;
    int fd = open(argv[1], O_RDONLY);
    struct stat st;
    fstat(fd, &st);
    const size_t len = (size_t)st.st_size;
    const uint8_t *base = (const uint8_t *)mmap(nullptr, len, PROT_READ, MAP_SHARED, fd, 0);
    if (base == MAP_FAILED) return 3;
    const long page = sysconf(_SC_PAGESIZE);
    const int rounds = atoi(argv[2]), N = 240;
    std::mt19937_64 rng(12345 + (unsigned)getpid());
    const size_t rows = (len - 4096) / 176;
    volatile unsigned sink = 0;
    auto pick = [&](std::vector<size_t> &v) { for (auto &x : v) x = (rng() % rows) * 176; };
    auto madv = [&](const std::vector<size_t> &v) {
        for (size_t o : v) {
            uintptr_t a = (uintptr_t)(base + o), a0 = a & ~(uintptr_t)(page - 1);
            madvise((void *)a0, (size_t)(a + 176 - a0), MADV_WILLNEED);
        }
    };
    auto touch = [&](const std::vector<size_t> &v) { unsigned s = 0; for (size_t o : v) s += base[o] + base[o + 175]; sink += s; };
    std::vector<size_t> v(N);
    // (a) cached rows
    pick(v);
    touch(v);
    double ta = 0, tt = 0;
    for (int r = 0; r < rounds; ++r) {
        double t0 = now(); madv(v); double t1 = now(); touch(v); double t2 = now();
        ta += t1 - t0; tt += t2 - t1;
    }
    std::printf("cached rows: madvise of %d rows %.1f us, touching them %.1f us\n", N, 1e6 * ta / rounds, 1e6 * tt / rounds);
    // (b) new rows, no prefetch
    double tb = 0;
    for (int r = 0; r < rounds; ++r) { pick(v); double t0 = now(); touch(v); tb += now() - t0; }
    std::printf("new rows, touched in turn: %.1f us per %d rows\n", 1e6 * tb / rounds, N);
    // (c) new rows, madvise all then touch
    double tc1 = 0, tc2 = 0;
    for (int r = 0; r < rounds; ++r) {
        pick(v); double t0 = now(); madv(v); double t1 = now(); touch(v); double t2 = now();
        tc1 += t1 - t0; tc2 += t2 - t1;
    }
    std::printf("new rows, madvise first: madvise %.1f us + touching %.1f us per %d rows\n", 1e6 * tc1 / rounds,
                1e6 * tc2 / rounds, N);
    return sink == 12345 ? 1 : 0;
}
