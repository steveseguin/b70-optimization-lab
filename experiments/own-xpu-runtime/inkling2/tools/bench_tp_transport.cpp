// bench_tp_transport: measure the balanced whole-expert TP2 transport, before changing the engine.
// Each direction carries four complete E-float expert outputs per token. Both cards read/write in parallel through
// ordinary host memory, with two queue-drain rounds per layer and no direct peer access. This is a transport screen,
// not an engine result or an arithmetic test.
#include "../src/device.hpp"
#include <cstdio>
#include <cstring>
#include <vector>

int main(int argc, char **argv) {
    using namespace ink;
    const int ca = argc > 1 ? std::atoi(argv[1]) : 1, cb = argc > 2 ? std::atoi(argv[2]) : 2;
    const int ntok = argc > 3 ? std::atoi(argv[3]) : 1;
    constexpr int E = 2304, SLOTS = 4, LAYERS = 48;
    if (ca == cb || ntok < 1 || ntok > 8) {
        std::fprintf(stderr, "usage: bench_tp_transport <cardA> <cardB> [tokens 1-8]\n");
        return 2;
    }
    try {
        Device a(ca), b(cb);
        const size_t count = (size_t)SLOTS * E * ntok, bytes = count * sizeof(float);
        std::vector<float> va(count), vb(count), ha(count), hb(count);
        for (size_t i = 0; i < count; ++i) { va[i] = (float)(i % 1024) + 0.25f; vb[i] = -(float)(i % 2048) - 0.5f; }
        float *ao = a.alloc<float>(count), *bo = b.alloc<float>(count);
        float *ai = a.alloc<float>(count), *bi = b.alloc<float>(count);
        a.put(ao, va.data(), count); b.put(bo, vb.data(), count);
        auto step = [&] {
            for (int l = 0; l < LAYERS; ++l) {
                // A -> B and B -> A: both source reads are in flight before either host wait; the paired writes likewise.
                a.q.memcpy(ha.data(), ao, bytes);
                b.q.memcpy(hb.data(), bo, bytes);
                a.q.wait(); b.q.wait();
                b.q.memcpy(bi, ha.data(), bytes);
                a.q.memcpy(ai, hb.data(), bytes);
                b.q.wait(); a.q.wait();
            }
        };
        for (int i = 0; i < 2; ++i) step();
        const double t0 = now_s();
        const int reps = 50;
        for (int i = 0; i < reps; ++i) step();
        const double ms = (now_s() - t0) / reps * 1e3;
        std::vector<float> cao(count), cbo(count);
        a.get(cao.data(), ai, count); b.get(cbo.data(), bi, count);
        const bool ok = !std::memcmp(cao.data(), vb.data(), bytes) && !std::memcmp(cbo.data(), va.data(), bytes);
        const double payload = (double)bytes * LAYERS * 2;
        std::printf("cards %d+%d, tokens %d: %.3f ms/step, %.3f us/layer, %.2f GB/s host-staged payload; copies %s\n",
                    ca, cb, ntok, ms, ms * 1000 / LAYERS, payload / ms / 1e6, ok ? "same" : "DIFFER");
        std::printf("planning only: 2.005 ms ideal expert saving - %.3f ms transport = %.3f ms before replicated work\n",
                    ms, 2.005 - ms);
        return ok ? 0 : 1;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "error: %s\n", e.what());
        return 1;
    }
}
