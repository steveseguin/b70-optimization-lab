// Host only (no GPU): how long the 48 engram rows of one step (24 per engram layer, 176-byte Q5_K rows at random
// ids of the 135 GB table) take to read, the engine's way (every card thread memcpy's the same rows from the
// mmap'd table: six threads) against one thread, and against pread() from the file. Rows "warm" = in the page
// cache (read once before through pread), "cold" = fresh random ids (disk). Per form: median and p90 us per step.
//   g++ -O2 -std=c++20 -pthread tools/bench/engram_rows_host_bench.cpp -o $S/engb && $S/engb   (host only, no GPU)
#include <algorithm>
#include <barrier>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <map>
#include <random>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <vector>
static void die(const char *m) { std::fprintf(stderr, "%s\n", m); std::exit(1); }
static int fd_g;
static size_t base_off; // file offset of layer 0's table
static const uint8_t *map_base;
static void open_table(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) die("open");
    struct stat st; fstat(fd, &st);
    auto rd = [&](void *dst, size_t n) { if (read(fd, dst, n) != (ssize_t)n) die("hdr"); };
    uint32_t magic, ver; uint64_t nt, nkv;
    rd(&magic, 4); rd(&ver, 4); rd(&nt, 8); rd(&nkv, 8);
    if (magic != 0x46554747) die("magic");
    auto skip_str = [&] { uint64_t n; rd(&n, 8); lseek(fd, n, SEEK_CUR); };
    for (uint64_t i = 0; i < nkv; ++i) {
        skip_str();
        uint32_t vt; rd(&vt, 4);
        switch (vt) {
        case 0: case 1: case 7: lseek(fd, 1, SEEK_CUR); break;
        case 2: case 3: lseek(fd, 2, SEEK_CUR); break;
        case 4: case 5: case 6: lseek(fd, 4, SEEK_CUR); break;
        case 8: skip_str(); break;
        case 10: case 11: case 12: lseek(fd, 8, SEEK_CUR); break;
        case 9: { uint32_t et; uint64_t n; rd(&et, 4); rd(&n, 8);
            if (et == 8) for (uint64_t j = 0; j < n; ++j) skip_str();
            else lseek(fd, n * (et <= 1 || et == 7 ? 1 : (et <= 3 ? 2 : (et >= 10 ? 8 : 4))), SEEK_CUR);
            break; }
        default: die("kv type");
        }
    }
    std::map<std::string, uint64_t> offs;
    for (uint64_t i = 0; i < nt; ++i) {
        uint64_t nl; rd(&nl, 8);
        std::string name(nl, 0); rd(name.data(), nl);
        uint32_t nd; rd(&nd, 4); lseek(fd, 8 * nd, SEEK_CUR);
        uint32_t type; uint64_t toff; rd(&type, 4); rd(&toff, 8);
        offs[name] = toff;
    }
    off_t ds = (lseek(fd, 0, SEEK_CUR) + 31) / 32 * 32;
    auto it = offs.find("per_layer_token_embd.weight");
    if (it == offs.end()) die("name");
    base_off = ds + it->second;
    const uint8_t *m = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (m == MAP_FAILED) die("mmap");
    madvise((void *)m, st.st_size, MADV_RANDOM);
    map_base = m;
    fd_g = fd;
}
static constexpr size_t RB = 176, NROW = 384006168;
static double us(std::chrono::steady_clock::time_point a, std::chrono::steady_clock::time_point b) {
    return std::chrono::duration<double, std::micro>(b - a).count();
}
int main() {
    open_table("/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00006-of-00006.gguf");
    std::mt19937_64 rng(5);
    constexpr int STEPS = 60;
    auto ids_for = [&](int step_seed) {
        std::mt19937_64 r(1000 + step_seed);
        std::vector<size_t> v(48);
        for (int k = 0; k < 48; ++k) v[k] = (k < 24 ? 0 : NROW) + r() % NROW;
        return v;
    };
    auto warm = [&](const std::vector<size_t> &ids) { uint8_t b[RB]; for (size_t id : ids) if (pread(fd_g, b, RB, base_off + id * RB) != (ssize_t)RB) die("pread"); };
    // form: 0 mmap x6 threads, 1 mmap x1, 2 pread x6, 3 pread x1
    const char *fn[4] = {"mmap memcpy, 6 threads", "mmap memcpy, 1 thread ", "pread, 6 threads      ", "pread, 1 thread        "};
    for (int cold = 0; cold < 2; ++cold)
        for (int f = 0; f < 4; ++f) {
            std::vector<double> t;
            for (int s = 0; s < STEPS; ++s) {
                // fresh ids per (form, step); warm: read through pread once first (page cache, not mapped here)
                const auto ids = ids_for((cold * 4 + f) * 1000 + s);
                if (!cold) warm(ids);
                const int nt = (f == 0 || f == 2) ? 6 : 1;
                std::vector<std::vector<uint8_t>> out(nt, std::vector<uint8_t>(48 * RB));
                std::barrier bar(nt + 1);
                std::vector<double> per(nt);
                std::vector<std::thread> th;
                for (int i = 0; i < nt; ++i)
                    th.emplace_back([&, i] {
                        bar.arrive_and_wait();
                        const auto a = std::chrono::steady_clock::now();
                        for (int k = 0; k < 48; ++k) {
                            if (f < 2) std::memcpy(out[i].data() + k * RB, map_base + base_off + ids[k] * RB, RB);
                            else if (pread(fd_g, out[i].data() + k * RB, RB, base_off + ids[k] * RB) != (ssize_t)RB) die("pread");
                        }
                        per[i] = us(a, std::chrono::steady_clock::now());
                    });
                bar.arrive_and_wait();
                for (auto &x : th) x.join();
                t.push_back(*std::max_element(per.begin(), per.end()));
            }
            std::sort(t.begin(), t.end());
            std::printf("%s %s: median %7.1f us, p90 %7.1f us per step (slowest thread)\n", cold ? "cold" : "warm", fn[f],
                        t[t.size() / 2], t[t.size() * 9 / 10]);
            std::fflush(stdout);
        }
    return 0;
}
