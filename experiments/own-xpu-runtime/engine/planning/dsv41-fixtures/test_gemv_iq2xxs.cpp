// Differential + perf fixture for the packed IQ2_XXS row dot contract:
//   fused gemv_iq2xxs_row  ==  dequantize_iq2_xxs + sequential fmaf dot
// bit-exact on synthetic and real GGUF bytes; then a CPU timing comparison
// (indicative only — the target is the device kernel).
#include <chrono>
#include <cmath>
#include <cstdio>
#include "iq2xxs_gemv.hpp"
#include "test_common.hpp"

static float ref_dot_via_dequant(const dsv41::block_iq2_xxs *row, const float *x, long long nb) {
    std::vector<float> w(nb * 256);
    dsv41::dequantize_iq2_xxs(row, w.data(), nb);
    float acc = 0.f;
    for (long long i = 0; i < nb * 256; ++i) acc = std::fmaf(w[i], x[i], acc);
    return acc;
}

static bool check(const char *what, const dsv41::block_iq2_xxs *row, const float *x, long long nb) {
    float a = dsv41::gemv_iq2xxs_row(row, x, nb);
    float b = ref_dot_via_dequant(row, x, nb);
    if (!std::isfinite(a) || !std::isfinite(b)) {
        std::fprintf(stderr, "FAIL %s: non-finite dot (fused=%a ref=%a)\n", what, a, b);
        return false;
    }
    if (std::memcmp(&a, &b, 4) != 0) {
        std::fprintf(stderr, "FAIL %s: fused=%a ref=%a\n", what, a, b);
        return false;
    }
    { uint32_t ua,ub; std::memcpy(&ua,&a,4); std::memcpy(&ub,&b,4); std::printf("OK   %s: dot over %lld elems bit-exact (%g fused=%08x ref=%08x)\n", what, nb * 256, a, ua, ub); }
    return true;
}

int main(int argc, char **argv) {
    const long long nb = 512;  // 131072 elems — one large fused span
    std::vector<dsv41::block_iq2_xxs> syn(nb);
    for (auto &b : syn) {
        auto *raw = (uint16_t *)&b;
        for (size_t i = 0; i < sizeof(b) / 2; ++i) raw[i] = (uint16_t)dsv41fix::rng();
        b.d = (uint16_t)(0x1400 | (dsv41fix::rng() & 0x3ff));  // finite scale; NaN must not mask
    }
    std::vector<float> x(nb * 256);
    for (auto &v : x) v = (float)(dsv41fix::rng() & 0xffff) * 0.0001f - 3.2768f;
    if (!check("synthetic", syn.data(), x.data(), nb)) return 1;

    const char *path = argc > 1 ? argv[1]
        : "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00002-of-00006.gguf";
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st; fstat(fd, &st);
    const uint8_t *map = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }
    long long rnb = 0;
    const uint8_t *t = dsv41fix::find_first_of_type(map, st.st_size, 16, 256, 66, &rnb);
    if (!t) { std::fprintf(stderr, "no iq2_xxs tensor\n"); return 1; }
    if (rnb > nb) rnb = nb;
    if (!check("real gguf", (const dsv41::block_iq2_xxs *)t, x.data(), rnb)) return 1;

    // CPU timing, indicative only
    const int iters = 200;
    volatile float sink = 0.f;
    auto t0 = std::chrono::steady_clock::now();
    for (int i = 0; i < iters; ++i) sink += dsv41::gemv_iq2xxs_row((const dsv41::block_iq2_xxs *)t, x.data(), rnb);
    auto t1 = std::chrono::steady_clock::now();
    for (int i = 0; i < iters; ++i) sink += ref_dot_via_dequant((const dsv41::block_iq2_xxs *)t, x.data(), rnb);
    auto t2 = std::chrono::steady_clock::now();
    double fused = std::chrono::duration<double>(t1 - t0).count();
    double two   = std::chrono::duration<double>(t2 - t1).count();
    std::printf("CPU indicative: fused %.1f ms/iter, dequant+dot %.1f ms/iter (%.2fx)\n",
                fused / iters * 1e3, two / iters * 1e3, two / fused);
    munmap((void *)map, st.st_size);
    close(fd);
    std::printf("FIXTURE_PASS gemv_iq2xxs\n");
    return 0;
}
