// own_run_v41: decode DeepSeek-V4.1-Flash on B70 cards from a CPU reference
// state dump (cpu_run_v41 argv[7]: post-prefill rings, compress/index caches,
// group states, token history, first token).
//
//   own_run_v41 state.bin ndecode out_ids.txt [max_ctx]
//   OWN_PROMPT=ids.txt own_run_v41 - ndecode out_ids.txt [max_ctx]
//
// With OWN_PROMPT the cards read the prompt themselves, one token per decode
// step from an empty state (causal model: identical to a batched prompt
// pass), and no CPU reference state is needed. Prompt reading then runs at
// the decode rate.
//
// Environment:
//   OWN_LAYERS=a:b     run only layers [a,b) (default 0:40)
//   OWN_HEAD=0|1       output norm + logits + argmax (default: 1 iff b == 40)
//   OWN_DEVS=i,j,...   SYCL gpu indices for the cards this range needs
//   OWN_PROMPT=ids.txt read this prompt on the cards instead of loading a state dump
//   OWN_EOS=id         stop when this token is generated (default 1; -1 = never)
//   OWN_FORCED=ids.txt teacher-force these tokens (required without the head)
//   OWN_INJECT=cpu.trc reference trace: streams/pre-mix (and rows published by
//                      sources outside the range) enter at layer a
//   OWN_TRACE=dev.trc  write the device trace (OWN_TRACE_STEPS, default 2)
//   OWN_HOST_FLOOR_MIB abort the load below this MemAvailable (default 3072)
//   OWN_HC_LEGACY=1    old FFN pre-mix threading (A/B only)
//   OWN_LOAD_ONLY=1    stop after the upload (load/memory test)
//   OWN_GENERIC_KERNELS=1 runtime-type gemv kernels instead of one kernel per weight format
//   OWN_PACKED=0|1     packed device rows + packed kernels where available (default 1; f32 build)
//   OWN_KEEP_WARM=0|1|2 after each layer, ping the other cards with a tiny kernel so they stay at
//                      full clock (default 1; 2 = next card only; 0 = off, about 40 % slower)
//   OWN_PACE=0|1|2     extra queue waits (per layer / per operator group); no measured benefit
//   OWN_H2D_WAIT=0|1   wait after host->card state uploads (default 1; no measured difference)
//   OWN_PROF=1         per-op-group time shares (adds a queue wait at every mark)
//   OWN_DEBUG=1        progress output
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <unordered_map>
#include <sstream>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <tuple>
#include <unistd.h>
#include <vector>
#include "stage2/packet3/backend/backend_sycl_v41.hpp"

static void die(const std::string &m) { std::fprintf(stderr, "fatal: %s\n", m.c_str()); exit(1); }
static double now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
// bytes this process made the kernel read from disk, and its major page faults (the engram table is read through
// the page cache: rows that are not cached cost a disk read inside the step)
static std::pair<long, long> host_io() {
    long rb = -1;
    if (FILE *f = std::fopen("/proc/self/io", "r")) {
        char k[64];
        long v;
        while (std::fscanf(f, "%63s %ld", k, &v) == 2)
            if (!std::strcmp(k, "read_bytes:")) rb = v;
        std::fclose(f);
    }
    struct rusage ru {};
    getrusage(RUSAGE_SELF, &ru);
    return {rb, ru.ru_majflt};
}
static void host_io_line(own41::Backend41 &be, int tp, std::pair<long, long> io0) {
    const auto io1 = host_io();
    double tsum = 0, tmax = 0, tq = 0;
    long nsum = 0;
    for (int c = 0; c < std::max(1, tp); ++c) {
        tq += be.eng_tq[c];
        tsum += be.eng_t[c];
        nsum += be.eng_n[c];
        if (be.eng_n[c]) tmax = std::max(tmax, be.eng_t[c] / be.eng_n[c]);
    }
    std::fprintf(stderr, "host io during decode: %.1f MiB read from disk, %ld major page faults; engram rows %.1f us "
                 "per step and card (slowest card %.1f us; copy + decode launch calls %.1f us)\n",
                 (io1.first - io0.first) / 1048576.0, io1.second - io0.second, nsum ? 1e6 * tsum / nsum : 0.0, 1e6 * tmax,
                 nsum ? 1e6 * tq / nsum : 0.0);
}

// GGUF single-tensor table locator (from the validated CPU runner).
static const uint8_t *map_engram(const char *path, int li) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open engram"); exit(1); }
    struct stat st; fstat(fd, &st);
    auto rd = [&](void *dst, size_t n) { if (read(fd, dst, n) != (ssize_t)n) die("engram hdr"); };
    uint32_t magic, ver; uint64_t nt, nkv;
    rd(&magic, 4); rd(&ver, 4); rd(&nt, 8); rd(&nkv, 8);
    if (magic != 0x46554747) die("engram magic");
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
        case 9: {
            uint32_t et; uint64_t n; rd(&et, 4); rd(&n, 8);
            if (et == 8) for (uint64_t j = 0; j < n; ++j) skip_str();
            else lseek(fd, n * (et <= 1 || et == 7 ? 1 : (et <= 3 ? 2 : (et >= 10 ? 8 : 4))), SEEK_CUR);
            break;
        }
        default: die("engram kv type");
        }
    }
    std::map<std::string, uint64_t> offs;
    for (uint64_t i = 0; i < nt; ++i) {
        uint64_t nl; rd(&nl, 8);
        std::string name(nl, 0);
        rd(name.data(), nl);
        uint32_t nd; rd(&nd, 4);
        lseek(fd, 8 * nd, SEEK_CUR);
        uint32_t type; uint64_t toff;
        rd(&type, 4); rd(&toff, 8);
        (void)type;
        offs[name] = toff;
    }
    off_t ds = (lseek(fd, 0, SEEK_CUR) + 31) / 32 * 32;
    const uint8_t *m = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (m == MAP_FAILED) { perror("mmap engram"); exit(1); }
    // OWN_ENG_EARLY (default on): a row read that misses the page cache fetches its page only, not the 128 KiB
    // read-around
    if (const char *e = getenv("OWN_ENG_EARLY"); !e || atoi(e) != 0) madvise((void *)m, st.st_size, MADV_RANDOM);
    close(fd);
    auto it = offs.find("per_layer_token_embd.weight");
    if (it == offs.end()) die("engram table name");
    const uint8_t *base = m + ds + it->second;
    return li == 0 ? base : base + (size_t)384006168 * 176; // Q5_K row = 176B
}

using TraceKey = std::tuple<int, int, int>; // step, layer, tag
static std::map<TraceKey, std::vector<float>> read_trace(const char *path) {
    std::map<TraceKey, std::vector<float>> m;
    FILE *f = fopen(path, "rb");
    if (!f) die(std::string("trace unreadable: ") + path);
    uint32_t h[4];
    while (fread(h, 4, 4, f) == 4) {
        std::vector<float> v(h[3]);
        if (fread(v.data(), 4, h[3], f) != h[3]) break;
        if (h[2] == TT_LOGITS) continue; // large, not needed for injection
        m[{(int)h[0], (int)h[1], (int)h[2]}] = std::move(v);
    }
    fclose(f);
    return m;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: %s state.bin ndecode out_ids.txt [max_ctx]\n", argv[0]);
        return 2;
    }
    setenv("ZES_ENABLE_SYSMAN", "1", 0); // free-memory query; must precede SYCL startup
    // Driver switch (read at SYCL startup): no per-launch re-registration of all allocations for
    // kernels the compiler marks "indirect access". That work runs under a lock shared by every
    // card's host thread and cost the six-card path ~15 % (see Backend41::touch, which registers
    // each allocation once instead). OWN_INDIRECT_ACCESS=1 keeps the driver default.
    if (!(getenv("OWN_INDIRECT_ACCESS") && atoi(getenv("OWN_INDIRECT_ACCESS")) == 1)) {
        setenv("NEOReadDebugKeys", "1", 0);
        setenv("DisableIndirectAccess", "1", 0);
    }
    const char *state_path = argv[1];
    int ndecode = atoi(argv[2]);
    int max_ctx = argc > 4 ? atoi(argv[4]) : 16384;
    std::string root = "/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine";

    own41::Backend41::Options opt;
    opt.debug = getenv("OWN_DEBUG") != nullptr;
    opt.hc_legacy = getenv("OWN_HC_LEGACY") != nullptr;
    opt.generic_kernels = getenv("OWN_GENERIC_KERNELS") != nullptr;
    if (const char *e = getenv("OWN_PACKED")) opt.packed = atoi(e) != 0;
    opt.gprof = getenv("OWN_GPROF") != nullptr;
    opt.kprof = opt.gprof && atoi(getenv("OWN_GPROF")) >= 2;
    if (const char *e = getenv("OWN_SMALL")) opt.small_fast = atoi(e) != 0;
    if (const char *e = getenv("OWN_HOST_FLOOR_MIB")) opt.host_floor_mib = atol(e);
    if (const char *e = getenv("OWN_LAYERS"))
        if (sscanf(e, "%d:%d", &opt.layer_begin, &opt.layer_end) != 2) die("OWN_LAYERS=a:b");
    opt.head = opt.layer_end == 40;
    if (const char *e = getenv("OWN_HEAD")) opt.head = atoi(e) != 0;
    if (const char *e = getenv("OWN_DEVS")) {
        std::stringstream ss(e);
        std::string tok;
        while (std::getline(ss, tok, ',')) opt.devices.push_back(atoi(tok.c_str()));
    }
    if (const char *e = getenv("OWN_TP")) opt.tp = atoi(e); // every layer split across this many cards
    auto weights = [](const char *e, int *w) { // "w0,w1,...": relative row shares per card
        std::stringstream ss(e);
        std::string tok;
        for (int d = 0; d < 6 && std::getline(ss, tok, ','); ++d) w[d] = atoi(tok.c_str());
    };
    if (const char *e = getenv("OWN_TP_WEIGHTS")) weights(e, opt.tp_w);
    if (const char *e = getenv("OWN_TP_VWEIGHTS")) weights(e, opt.tp_vw);
    if (const char *e = getenv("OWN_TP_HEADS")) weights(e, opt.tp_heads);
    if (const char *e = getenv("OWN_TP_HEADS_DR")) opt.tp_heads_dr = atoi(e) != 0;
    if (const char *e = getenv("OWN_TP_HEADS_MIN")) opt.tp_heads_min = (unsigned)atoi(e);
    // qb-off-1: each 16-head card's two light neighbours compute this many of its query-b heads in one-token steps
    // (0 = off: today's launches); OWN_QB_OFF_WG: work-groups of each push
    if (const char *e = getenv("OWN_QB_OFF")) opt.qb_off = (unsigned)atoi(e);
    if (const char *e = getenv("OWN_QB_OFF_WG")) opt.qb_off_wg = (unsigned)atoi(e);
    // qb-off-2: the same in blocks of 2..6 tokens (guessing checks, small prompt blocks): OWN_QB_OFF_M=k (every size)
    // or k2,k3,k4,k5,k6 (one per block size; 0 = off for that size)
    if (const char *e = getenv("OWN_QB_OFF_M")) {
#ifndef OWN41_QBOFF_M
        if (strtoul(e, nullptr, 10) != 0) die("OWN_QB_OFF_M: qb-off is parked and not built (build with -DOWN41_QBOFF_M)");
#endif
        unsigned v[5] = {}, n = 0;
        for (const char *q = e; *q && n < 5;) {
            v[n++] = (unsigned)strtoul(q, nullptr, 10);
            q = strchr(q, ',');
            if (!q) break;
            ++q;
        }
        for (unsigned m = 2; m <= 6; ++m) opt.qb_off_m[m] = n == 1 ? v[0] : v[m - 2];
    }
    if (const char *e = getenv("OWN_GPROF_CARD")) opt.prof_card = atoi(e);
    if (const char *e = getenv("OWN_HC_RIDE")) opt.hc_ride = atoi(e) != 0;
    if (const char *e = getenv("OWN_ROUTER16")) opt.router16 = atoi(e) != 0;
    if (const char *e = getenv("OWN_DIET")) opt.diet = atoi(e) != 0;
    if (const char *e = getenv("OWN_PAIR_WG")) opt.pair_wg = atoi(e);
    // one-token norm launches: 64 (default since round 18 g81) / 128 / 512 (the old form) items per group
    if (const char *e = getenv("OWN_NORM_WG")) opt.norm_wg = atoi(e);
    if (const char *e = getenv("OWN_PAIR_WG_IQ1")) opt.pair_wg_iq1 = atoi(e);
    if (const char *e = getenv("OWN_PAIR_G128")) opt.pair_g128 = atoi(e) != 0; // xperm-1: IQ2_S gate+up at 128 registers
    if (const char *e = getenv("OWN_DR_FC_SPLIT")) opt.dr_fc_split = atoi(e) != 0;
    if (const char *e = getenv("OWN_DR_MXP")) opt.dr_mxp = atoi(e) != 0;
    if (const char *e = getenv("OWN_TP_PIN")) { // "c0,..,c5[,m]": CPUs for the six card threads and the main thread
        std::string v = e;
        int i = 0;
        for (size_t a = 0; a <= v.size() && i < 7; ++i) {
            const size_t b = v.find(',', a);
            opt.tp_pin[i] = atoi(v.substr(a, b == std::string::npos ? std::string::npos : b - a).c_str());
            if (b == std::string::npos) { ++i; break; }
            a = b + 1;
        }
        if (i < 6) die("OWN_TP_PIN: six CPU ids for the card threads (and optionally a seventh for the main thread)");
    }
    if (const char *e = getenv("OWN_Q2K_FAST")) opt.q2k_fast = atoi(e) != 0;
    if (const char *e = getenv("OWN_BF16_ROWS")) opt.bf16_rows = atoi(e) != 0;
    if (const char *e = getenv("OWN_DOWN_WG")) opt.down_wg = atoi(e);
    if (const char *e = getenv("OWN_ROPE_OUT")) opt.rope_out = atoi(e) != 0;
    if (const char *e = getenv("OWN_XTAIL")) opt.xtail = atoi(e) != 0;
    if (const char *e = getenv("OWN_XPULL")) opt.xpull = atoi(e) != 0;
    if (const char *e = getenv("OWN_XPULL_MIN")) opt.xpull_min = (unsigned)atoi(e);
    // xchg2-1: decode / check exchanges as peer-ordered pushes; default on (classes 0x0F) since tp109 (tg108: traces
    // identical, plain +3 %, guessing +3 %); OWN_XPUSH2=0: today's pulls / pushes; OWN_XPUSH2_MASK: the classes
    if (const char *e = getenv("OWN_XPUSH2")) opt.xpush2 = atoi(e) != 0 ? 0x0Fu : 0u;
    if (opt.xpush2)
        if (const char *m = getenv("OWN_XPUSH2_MASK")) opt.xpush2 = (unsigned)strtoul(m, nullptr, 0);
    if (opt.xpush2) std::fprintf(stderr, "OWN_XPUSH2: exchange classes 0x%x\n", opt.xpush2);
    // qkv-1 (default on since tp110, qsp110; /home/steve/dsv41-work/qkv/README.md): the q_a + kv rows split by card and all-gathered before their
    // norms. OWN_QKV_SPLIT=bits: 2 one-token steps, 4 blocks of 2-6 tokens, 8 larger (prompt) blocks; =1: all (14).
    // OWN_QKV_XQ (XchgQ from this many tokens, default 5), OWN_QKV_WG (128 / 512), OWN_QKV_FORM (blocks of 2-6 tokens:
    // 1 = DenseRowsG<1>, 2 = DenseRowsG<2>)
    if (const char *e = getenv("OWN_QKV_SPLIT")) {
        const unsigned v = (unsigned)strtoul(e, nullptr, 0);
        opt.qkv_split = v == 1 ? 14u : v & 14u;
    }
    if (const char *e = getenv("OWN_QKV_XQ")) opt.qkv_xq = (unsigned)atoi(e);
    if (const char *e = getenv("OWN_QKV_WG")) opt.qkv_wg = (unsigned)atoi(e);
    if (const char *e = getenv("OWN_QKV_FORM")) opt.qkv_form = (unsigned)atoi(e);
    if (const char *e = getenv("OWN_XPULL_LB")) opt.xpull_lb = atoi(e) != 0;
    if (const char *e = getenv("OWN_XPULL_GRF")) opt.xpull_grf = (unsigned)atoi(e); // default 128 (XPullK128); 0: auto (256)
    // px-1 (opt-in, /home/steve/dsv41-work/pb256/README-overlap.txt): prompt blocks as two halves with every exchange of
    // their layers on a second queue per card, each pull beside the other half's work. OWN_PX=1 (default 0: off, the
    // queue is not created); OWN_PX_MIN (halves of >= 128 tokens), OWN_PX_WG (16 work-groups per pull), OWN_PX_GRF
    // (eight register modes X1A,X1B,X2A,X2B,X3A,X3B,X4A,X4B: 128 / 256, 0 = the layer's routed-down mode), OWN_PX_SERIAL=1
    // (diagnostic: no overlap), OWN_PX_CHECK=1 (diagnostic: each block's exchange numbers and flag words checked)
    if (const char *e = getenv("OWN_PX")) opt.px = (unsigned)atoi(e);
    if (const char *e = getenv("OWN_PX_MIN")) opt.px_min = std::max(1u, (unsigned)atoi(e));
    if (const char *e = getenv("OWN_PX_WG")) opt.px_wg = std::max(1u, std::min(64u, (unsigned)atoi(e)));
    // px-move (opt-in, /home/steve/dsv41-work/pb256/pxmove/README.txt): OWN_PX_MOVE bit 1 X2(B) / X3(A) right before
    // the routed gate / up, bit 2 X4(B) before half A's q_a rows (X4(B)'s register mode then 256 unless OWN_PX_GRF says);
    // OWN_PX_WGS (eight work-group counts X1A .. X4B, 0 = OWN_PX_WG)
    if (const char *e = getenv("OWN_PX_MOVE")) {
        opt.px_move = (unsigned)atoi(e);
        if (opt.px_move > 3) die("OWN_PX_MOVE: 0 .. 3");
        if (opt.px_move & 2) opt.px_grf[7] = 256;
    }
    if (const char *e = getenv("OWN_PX_WGS")) {
        unsigned v[8] = {}, n = 0;
        for (const char *s = e; *s && n < 8;) {
            v[n++] = (unsigned)strtoul(s, nullptr, 10);
            const char *cm = std::strchr(s, ',');
            if (!cm) break;
            s = cm + 1;
        }
        if (n != 8) die("OWN_PX_WGS: eight values (X1A,X1B,X2A,X2B,X3A,X3B,X4A,X4B), each 0 .. 64");
        for (unsigned k = 0; k < 8; ++k) {
            if (v[k] > 64) die("OWN_PX_WGS: 0 .. 64");
            opt.px_wgs[k] = v[k];
        }
    }
    if (const char *e = getenv("OWN_PX_GRF")) {
        unsigned v[8] = {}, n = 0;
        for (const char *s = e; *s && n < 8;) {
            v[n++] = (unsigned)strtoul(s, nullptr, 10);
            const char *cm = std::strchr(s, ',');
            if (!cm) break;
            s = cm + 1;
        }
        if (n != 8) die("OWN_PX_GRF: eight values (X1A,X1B,X2A,X2B,X3A,X3B,X4A,X4B), each 128, 256 or 0");
        for (unsigned k = 0; k < 8; ++k) {
            if (v[k] != 0 && v[k] != 128 && v[k] != 256) die("OWN_PX_GRF: 128, 256 or 0");
            opt.px_grf[k] = v[k];
        }
    }
    if (const char *e = getenv("OWN_PX_SERIAL")) opt.px_serial = atoi(e) != 0;
    if (const char *e = getenv("OWN_PX_CHECK")) opt.px_check = atoi(e) != 0;
    // px-512 (opt-in): OWN_PX_BIG=1 with OWN_PX=1: OWN_PROMPT_BLOCK up to 2 x OWN41_MTX (512), each block two halves
    if (const char *e = getenv("OWN_PX_BIG")) opt.px_big = atoi(e) != 0;
    // bcs-1 (default 1 since tp108; OWN_PX_BCS=0 off; /home/steve/dsv41-work/bcs/README.md): with OWN_PX=1 the halves' exchanges as
    // copy-engine pushes (each card's copy engine writes its rows into every peer; a small wait launch before the reader)
    if (const char *e = getenv("OWN_PX_BCS")) opt.px_bcs = (unsigned)atoi(e);
    if (opt.px_bcs > 2) die("OWN_PX_BCS: 0, 1 or 2");
    // xll-1 (2026-11-11, /home/steve/dsv41-work/xll): the pull exchanges in one PCIe round trip; 1 = the default unit
    // (Options::XLL_DEFAULT_U bytes), 16 / 64: that unit, 0: off (the backend refuses anything else)
    if (const char *e = getenv("OWN_XLL")) opt.xll = atoi(e) == 1 ? (unsigned)own41::Backend41::Options::XLL_DEFAULT_U : (unsigned)atoi(e);
    if (const char *e = getenv("OWN_XLL_QUICK")) opt.xll_quick = (unsigned)atoi(e); // (default 0; at most 8)
    if (const char *e = getenv("OWN_NORM_DOTS")) opt.norm_dots = atoi(e) != 0;
    // smallk (2026-11-11, /home/steve/dsv41-work/smallk): one-work-group forms of the 5,120 norm, the q_a + kv norms,
    // the compressor pool and the engram gate (the same bits; bench-checked incl. forced fallbacks); default since tg89, =0: off
    if (const char *e = getenv("OWN_SMALLK")) opt.smallk = atoi(e) != 0;
    // the pre-norm + the stream mix's dot rows by a proven fast sum, block size K = 8 or 4 (the finish's outputs the
    // same bits; default 8 since tg89, =0: off): OWN_SMALLK_DOTS=8
    if (const char *e = getenv("OWN_SMALLK_DOTS")) opt.smallk_dots = atoi(e);
    // fl-1 (2026-11-11, /home/steve/dsv41-work/fl; off by default, the same bits): one-token tp steps fold a launch into
    // the next one; OWN_FL=bits: 1 the FFN pre-norm + the mix's dot rows into the router launch, 2 MoeCombineA into the
    // shared expert's down rows (3: both)
    if (const char *e = getenv("OWN_FL")) {
        opt.fl = (unsigned)atoi(e);
        if (opt.fl > 3) die("OWN_FL: 0..3");
    }
    // K7 (2026-11-11, /home/steve/dsv41-work/k7; off by default, the same bits): one-token steps compute the stream mix's
    // dot partials over each card's own model rows before the h exchange that gathers them; OWN_K7=bits: 1 the FFN mix
    // (output-b exchange), 2 the next attention mix (ffn-rows exchange), 3 both
    if (const char *e = getenv("OWN_K7")) {
        opt.k7 = (unsigned)atoi(e);
        if (opt.k7 > 3) die("OWN_K7: 0..3");
    }
    // prompt blocks: the stream mixes' dot rows split across the cards by tokens, gathered with the output-a and
    // expert-act pulls (pcd-1, prefill plan item C; default on since tg91, =0: off): OWN_MT_DSPLIT; the cards' token weights per mix
    // OWN_MT_DSPLIT_WA / OWN_MT_DSPLIT_WF="w0,w1,w2,w3,w4,w5" (unset: attention 4 on the cards with fewer heads, else 1)
    if (const char *e = getenv("OWN_MT_DSPLIT")) opt.mt_dsplit = atoi(e) != 0;
    for (int k = 0; k < 2; ++k)
        if (const char *e = getenv(k ? "OWN_MT_DSPLIT_WF" : "OWN_MT_DSPLIT_WA")) {
            int *w = k ? opt.dsplit_wf : opt.dsplit_wa;
            if (std::sscanf(e, "%d,%d,%d,%d,%d,%d", w, w + 1, w + 2, w + 3, w + 4, w + 5) != 6)
                die("OWN_MT_DSPLIT_WA / _WF: six weights w0,...,w5");
        }
    if (const char *e = getenv("OWN_PF")) opt.pf = atoi(e) != 0;
    // OWN_XL2=bits: while a card waits in a one-token exchange, a prefetch launch on its second queue pulls the next
    // matrix into the cache (1 output-b, 2 router + shared gate / up, 4 shared down, 8 next q_a + kv; 15 = all)
    if (const char *e = getenv("OWN_XL2")) opt.xl2 = (unsigned)atoi(e) & 15u;
    if (const char *e = getenv("OWN_XL2_MB")) opt.xl2_bytes = (size_t)std::max(1, atoi(e)) << 20;
    if (const char *e = getenv("OWN_XL2_WG")) opt.xl2_wg = (unsigned)std::clamp(atoi(e), 1, 256);
    if (const char *e = getenv("OWN_FIN_MOVE")) opt.fin_move = atoi(e) != 0;
    if (const char *e = getenv("OWN_DOWN_EX")) opt.down_ex = atoi(e) != 0;
    if (const char *e = getenv("OWN_EXP_PAIR")) opt.exp_pair = atoi(e) != 0;
    if (const char *e = getenv("OWN_ENG_SPLIT")) opt.eng_split = atoi(e) != 0;
    if (const char *e = getenv("OWN_ENG_DEV")) opt.eng_dev = atoi(e) != 0;
    if (const char *e = getenv("OWN_ENG_EARLY")) opt.eng_early = atoi(e) != 0;
    if (const char *e = getenv("OWN_ENG_LATE")) opt.eng_late = atoi(e) != 0;
    // default on since tg88 (traces identical, plain answers +0.3-0.5 %): =0 turns each off
    if (const char *e = getenv("OWN_ENG_CQ")) opt.eng_cq = atoi(e) != 0; // engram row copies on a copy queue
    if (const char *e = getenv("OWN_PRE_K")) opt.pre_k = atoi(e) != 0;   // pre-mix weights by the broadcast launch
    if (const char *e = getenv("OWN_HEAD_CQ")) opt.head_cq = atoi(e) != 0; // check argmax readback on the copy queue
    if (const char *e = getenv("OWN_TP_SPIN_US")) opt.tp_spin_us = atol(e);
    if (const char *e = getenv("OWN_DEV_INDEX")) opt.dev_index = atoi(e) != 0;
    if (const char *e = getenv("OWN_DEV_INDEX_CHECK")) opt.dev_index_check = atoi(e) != 0;
    if (const char *e = getenv("OWN_SCORE_B")) opt.score_b = atoi(e) != 0;
    if (const char *e = getenv("OWN_IDX_R")) opt.idx_r = (unsigned)atoi(e);
    // the index of layers 24-36 over layer 20's candidate rows past 16,384 rows (the same lists): default since
    // round 18 e84/e85 (OWN_IDX_CAND=0: all rows; 2: also the full one, compared bitwise)
    opt.idx_cand = getenv("OWN_IDX_CAND") ? atoi(getenv("OWN_IDX_CAND")) : 1;
    // idxsplit-1 (opt-in; /home/steve/dsv41-work/idxsplit/README.md): prompt blocks' index lists split across the cards by
    // tokens and gathered (the same lists): OWN_IDX_SPLIT=1 (the indexer's q_b / rope / proj rows, scores and selects of
    // the card's tokens), 2 (scores and selects only); OWN_IDX_SPLIT_MIN (blocks / halves of at least this many tokens,
    // default 32), OWN_IDX_SPLIT_W="w0,...,w5" (the cards' token weights; unset: equal), OWN_IDX_SPLIT_CHECK=1 (diagnostic:
    // also the full index, every list compared bitwise)
    if (const char *e = getenv("OWN_IDX_SPLIT")) opt.idx_split = (unsigned)atoi(e);
    if (opt.idx_split > 2) die("OWN_IDX_SPLIT: 0, 1 or 2");
    if (const char *e = getenv("OWN_IDX_SPLIT_MIN")) opt.idx_split_min = (unsigned)std::max(2, atoi(e));
    if (const char *e = getenv("OWN_IDX_SPLIT_W")) {
        int *w = opt.idx_split_w;
        if (std::sscanf(e, "%d,%d,%d,%d,%d,%d", w, w + 1, w + 2, w + 3, w + 4, w + 5) != 6)
            die("OWN_IDX_SPLIT_W: six weights w0,...,w5");
    }
    if (const char *e = getenv("OWN_IDX_SPLIT_CHECK")) opt.idx_split_check = atoi(e) != 0;
    // the top-512 picks' last walk by ranges of rows (plain, masked and candidate selects; the same lists) and,
    // below 512 compressed rows, attention over the window + the live rows only (the same sums): defaults since
    // round 18 e87 / r1 (=0 for the old forms)
    opt.topk_r = getenv("OWN_TOPK_R") ? atoi(getenv("OWN_TOPK_R")) != 0 : true;
    opt.att_trim = getenv("OWN_ATT_TRIM") ? atoi(getenv("OWN_ATT_TRIM")) != 0 : true;
    // the selects with every key in registers (rows >= 4,096, blocks > 2,048; the same lists): default since round 18
    // q4 / g75 (=0 for TopKSelR / TopKSelP / TopKSelC)
    opt.topk_q = getenv("OWN_TOPK_Q") ? atoi(getenv("OWN_TOPK_Q")) != 0 : true;
    // the attention output from local memory, a column per lane (the same outputs): default since round 18 s3 / g76
    // (=0 for SparseOutJB)
    opt.att_out_c = getenv("OWN_ATT_OUT_C") ? atoi(getenv("OWN_ATT_OUT_C")) != 0 : true;
    // the score's heads per sub-group (4, 2 or 1) and the trimmed lists' softmax built per slot count (the same
    // outputs; tools/bench/bench_attn_dec.cpp 2026-11-11): opt-in until gated
    if (getenv("OWN_ATT_HG")) opt.att_hg = (unsigned)atoi(getenv("OWN_ATT_HG"));
    if (const char *e = getenv("OWN_ATT_PK")) opt.att_pk = atoi(e) != 0;
    if (const char *e = getenv("OWN_ATT_M")) opt.att_m = atoi(e) != 0; // the attention forms in blocks too (default since tg88)
    if (const char *e = getenv("OWN_ATT_M_MAX")) opt.att_m_max = (unsigned)atoi(e); // ... in blocks up to this size
    if (const char *e = getenv("OWN_ATT_T")) opt.att_t = atoi(e) != 0; // sparse attention in one or two launches (attn a1)
    if (const char *e = getenv("OWN_ATT_T_M_MAX")) opt.att_t_m_max = (unsigned)atoi(e); // ... in blocks up to this size
    if (const char *e = getenv("OWN_ATT_T_HG")) opt.att_t_hg = (unsigned)atoi(e); // ... two launches: score heads per work-group
    if (const char *e = getenv("OWN_ATT_F")) opt.att_f = atoi(e) != 0; // ... =0: two launches only
    if (const char *e = getenv("OWN_ATT_WA")) opt.att_wa = (unsigned)std::max(0, atoi(e)); // ... blocks: the window append inside them (1 attn wa-1: everywhere, 2 wa-2: per shape)
    // RMS norms of 1,280+ columns take their scale from a fast bracket of the double chain (the same scale bit for
    // bit; round 18 n1-n5, tools/bench/bench_norm_ff.cpp; default since g81); =0 for the chain only. Read before any
    // norm kernel is built.
    ops41sycl::g_norm_ff = getenv("OWN_NORM_FF") ? atoi(getenv("OWN_NORM_FF")) != 0 : true;
    // the router's expert picks in two stages (the same ids and probabilities; round 18 rt1-rt5,
    // tools/bench/bench_route_rows.cpp); =0 for RouteP's all-pairs ranks. Read before any router kernel is built.
    ops41sycl::g_route_q = getenv("OWN_ROUTE_Q") ? atoi(getenv("OWN_ROUTE_Q")) != 0 : true;
    // the engram gate's three double sums from a fast bracket (the same gate bit for bit; round 18 eg1,
    // tools/bench/bench_engram_ff.cpp); =0 for the serial chains only. Read before the gate kernel is built.
    ops41sycl::g_eng_ff = getenv("OWN_ENG_FF") ? atoi(getenv("OWN_ENG_FF")) != 0 : true;
    // one host thread per card; trace runs submit phase by phase from one thread
    // (OWN_TP_THREADS=1 keeps the threads in a trace run: untraced steps, e.g. prompt blocks, use them)
    opt.tp_threads = getenv("OWN_TP_THREADS") ? atoi(getenv("OWN_TP_THREADS")) != 0 : !getenv("OWN_TRACE");
    std::vector<int> forced;
    if (const char *e = getenv("OWN_FORCED")) {
        std::ifstream ff(e);
        long long v;
        while (ff >> v) forced.push_back((int)v);
        if (forced.empty()) die("OWN_FORCED file empty");
    }
    std::map<TraceKey, std::vector<float>> inject;
    if (const char *e = getenv("OWN_INJECT")) inject = read_trace(e);
    if (opt.layer_begin > 0 && inject.empty()) die("a range that starts above layer 0 needs OWN_INJECT");
    if (!opt.head && forced.empty()) die("without the head the tokens must come from OWN_FORCED");
    const int trace_steps = getenv("OWN_TRACE_STEPS") ? atoi(getenv("OWN_TRACE_STEPS")) : 2;

    try {
        // ---- weights ----
        std::map<std::string, std::pair<std::string, long>> shards;
        {
            std::ifstream sj(root + "/planning/dsv41-fixtures/data/shards.tsv");
            if (!sj) die("shards.tsv missing");
            std::string name, path;
            long ds2;
            while (sj >> name >> path >> ds2) shards[name] = {path, ds2};
        }
        own41::WeightTab wt;
        own41::load_weights(wt, root + "/profiles/dsv41-iq2xxs/placement.tsv", shards);
        // OWN_DSPARK=<dspark gguf>: the official DSpark draft's tensors ("dsp." names, absolute offsets) in the
        // same table (profiles/dspark-q8/placement.tsv, tools/mk_dspark_placement.py)
        if (const char *dp = getenv("OWN_DSPARK"); dp && *dp) {
            std::string base = dp;
            base = base.substr(base.find_last_of('/') + 1);
            own41::load_weights(wt, root + "/profiles/dspark-q8/placement.tsv", {{base, {std::string(dp), 0L}}});
            opt.dspark = true;
        }
        std::fprintf(stderr, "store: %zu tensors\n", wt.w.size());

        flash::Directory d;
        {
            std::ifstream df(root + "/planning/dsv41-fixtures/data/dsv41-directory.tsv");
            if (!df) die("directory tsv missing");
            d = flash::read_directory(df);
        }
        flash41::Plan41 plan = flash41::model_plan_v41(d, max_ctx);

#ifndef OWN41_ACT_BF16
        // default since 2026-11-10 (note section 28, e81): six cards split the attention heads 12, 12, 12, 12, 8, 8
        // for blocks of >= 16 tokens (prompt reading); one-token steps, checks and the draft keep whole groups.
        // OWN_TP_HEADS=0 keeps whole groups everywhere.
        if (opt.tp == 6 && !opt.xtail && !getenv("OWN_TP_HEADS")) {
            const int dh[6] = {3, 3, 3, 3, 2, 2};
            for (int c = 0; c < 6; ++c) opt.tp_heads[c] = dh[c];
            if (!getenv("OWN_TP_HEADS_MIN")) opt.tp_heads_min = 16;
        }
#endif
        std::fprintf(stderr, "host MemAvailable %ld MiB (floor %ld MiB)\n",
                     own41::meminfo_kb("MemAvailable") / 1024, opt.host_floor_mib);
        own41::Backend41 be(plan, max_ctx, opt);
        for (int t = 0; t < own41::Backend41::TILES; ++t)
            if (be.tile_active(t))
                std::fprintf(stderr, "tile %d -> card %s, %.2f GiB free\n", t, be.tile_pci(t).c_str(),
                             be.free_bytes(t) / 1073741824.0);
        double t0 = now();
        be.upload(wt);
        std::fprintf(stderr, "upload: %.1f GB in %.1fs (%.2f GB/s); host MemAvailable %ld MiB\n",
                     be.uploaded_bytes / 1e9, now() - t0, be.uploaded_bytes / 1e9 / (now() - t0),
                     own41::meminfo_kb("MemAvailable") / 1024);
        std::fprintf(stderr, "packed rows: %zu tensors, %.2f GB on the cards\n", be.packed_tensors, be.packed_bytes / 1e9);
        for (int t = 0; t < own41::Backend41::TILES; ++t)
            if (be.tile_active(t))
                std::fprintf(stderr, "tile %d card %s: %.2f GiB free after load\n", t, be.tile_pci(t).c_str(),
                             be.free_bytes(t) / 1073741824.0);
        if (opt.tp_pin[6] >= 0) { // OWN_TP_PIN's seventh entry: the main thread, after the upload's threads are gone
            cpu_set_t cs;
            CPU_ZERO(&cs);
            CPU_SET(opt.tp_pin[6], &cs);
            if (pthread_setaffinity_np(pthread_self(), sizeof cs, &cs) != 0) die("OWN_TP_PIN: cannot pin the main thread");
        }
        if (getenv("OWN_LOAD_ONLY")) return 0;

        // ---- engram tables + prep ----
        const char *eng_path = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00006-of-00006.gguf";
        be.eng_base[0] = map_engram(eng_path, 0);
        be.eng_base[1] = map_engram(eng_path, 1);
        std::vector<int32_t> token_map(129280);
        {
            std::ifstream pf(root + "/../data/dsv41-reference/engram_prep.bin", std::ios::binary);
            if (!pf) die("engram_prep.bin missing");
            pf.read((char *)token_map.data(), 129280 * 4);
            pf.read((char *)be.eng_primes, sizeof(be.eng_primes));
            pf.read((char *)be.eng_off, sizeof(be.eng_off));
            pf.read((char *)be.eng_mult, sizeof(be.eng_mult));
            int64_t tail[2];
            pf.read((char *)tail, 16);
            be.eng_pad = tail[0];
        }

        // ---- state dump ----
        long pos;
        long lens[4];
        std::vector<std::vector<float>> rings(40), ckv(4), ik(4);
        float kv_state[4][1024], score_state[4][1024];
        int first = -1;
        std::vector<int> prompt;
        if (const char *pp = getenv("OWN_PROMPT")) {
            std::ifstream pf2(pp);
            long long v;
            while (pf2 >> v) prompt.push_back((int)v);
            if (prompt.empty()) die("OWN_PROMPT file empty");
            if (opt.layer_begin != 0 || !opt.head) die("OWN_PROMPT needs the whole model (no OWN_LAYERS)");
            if ((int)prompt.size() + ndecode > max_ctx) die("prompt + ndecode exceeds max_ctx");
        } else {
            std::ifstream sf(state_path, std::ios::binary);
            if (!sf) die("state unreadable");
            sf.read((char *)&pos, 8);
            sf.read((char *)lens, 32);
            for (int L = 0; L < 40; ++L) {
                rings[L].resize((size_t)128 * 512);
                sf.read((char *)rings[L].data(), (size_t)128 * 512 * 4);
            }
            for (int i = 0; i < 4; ++i) {
                ckv[i].resize((size_t)lens[i] * 512);
                ik[i].resize((size_t)lens[i] * 128);
                sf.read((char *)ckv[i].data(), (size_t)lens[i] * 512 * 4);
                sf.read((char *)ik[i].data(), (size_t)lens[i] * 128 * 4);
            }
            for (int i = 0; i < 4; ++i) {
                sf.read((char *)kv_state[i], 1024 * 4);
                sf.read((char *)score_state[i], 1024 * 4);
            }
            long nt;
            sf.read((char *)&nt, 8);
            std::vector<int32_t> toks(nt);
            std::vector<int64_t> cids(nt);
            sf.read((char *)toks.data(), nt * 4);
            sf.read((char *)cids.data(), nt * 8);
            sf.read((char *)&first, 4);
            if (!sf) die("state file truncated");
            be.comp_ids.assign(cids.begin(), cids.end());
            be.load_state(pos, lens, rings, ckv, ik, kv_state, score_state);
            std::fprintf(stderr, "state loaded: pos=%ld lens=%ld,%ld,%ld,%ld first=%d\n", pos, lens[0], lens[1],
                         lens[2], lens[3], first);
        }
        if (const char *tp = getenv("OWN_TRACE")) be.trace_f = fopen(tp, "wb");
        be.prof_on = getenv("OWN_PROF") != nullptr;
        if (const char *e = getenv("OWN_PACE")) be.pace = atoi(e);
        if (const char *e = getenv("OWN_H2D_WAIT")) be.h2d_wait = atoi(e) != 0;
        if (const char *e = getenv("OWN_KEEP_WARM")) be.keep_warm = atoi(e);
        if (const char *e = getenv("OWN_WARM_ITEMS")) be.warm_items = (size_t)atol(e) / 32 * 32;
#ifndef OWN41_ACT_BF16
        if (const char *e = getenv("OWN_MT_SMALL")) be.mt_small = atoi(e) != 0; // block steps: small launches per block
        if (const char *e = getenv("OWN_MT_XPUSH")) be.mt_xpush = atoi(e); // block exchanges: 0 one group, 1 many, 2 per peer
        if (const char *e = getenv("OWN_MT_XGPP")) be.mt_xgpp = (unsigned)std::max(1, atoi(e));
        if (const char *e = getenv("OWN_MT_IDSTAT")) be.mt_idstat = atoi(e) != 0;
        if (const char *e = getenv("OWN_MT_IDDUMP")) be.mt_iddump = std::fopen(e, "w");
        if (const char *e = getenv("OWN_MT_TG")) be.mt_tg = (unsigned)atoi(e); // dense token groups per sub-group
        if (const char *e = getenv("OWN_MT_TG_MAX")) be.mt_tg_max = (unsigned)atoi(e);
        if (const char *e = getenv("OWN_MT_EU")) be.mt_eu = (unsigned)atoi(e); // expert-major routed rows (6)
        // (with OWN_MT_EU) blocks of >= OWN_MT_EU_BIG_M tokens (128): groups of up to OWN_MT_EU_BIG slots (16; 0 off),
        // heaviest first (OWN_MT_EU_HEAVY=0: ascending first slot)
        if (const char *e = getenv("OWN_MT_EU_BIG")) be.mt_eu_big = (unsigned)atoi(e);
        if (const char *e = getenv("OWN_MT_EU_BIG_M")) be.mt_eu_big_m = (unsigned)atoi(e);
        if (const char *e = getenv("OWN_MT_EU_HEAVY")) be.mt_eu_heavy = atoi(e) != 0;
        if (be.mt_eu_big > 16) throw std::runtime_error("OWN_MT_EU_BIG: at most 16 slots per group");
        if (const char *e = getenv("OWN_MT_TGU")) be.mt_tgu = (unsigned)atoi(e); // unpacked rows in token groups
        // the per-block-size tables (OWN_MT_TGM / OWN_MT_TGR / OWN_MT_TGWM): an entry past MTF (16) tokens that no
        // option names takes the MTF entry (blocks of up to MTX tokens pick their forms as a block of 16)
        constexpr int MTX_ = own41::Backend41::MTX, MTF_ = own41::Backend41::MTF;
        bool set_tgm[MTX_ + 1] = {}, set_tgr[MTX_ + 1] = {}, set_tgwm[MTX_ + 1] = {};
        if (const char *e = getenv("OWN_MT_TGM")) { // per block size: "m:g,m:g"
            for (const char *s = e; *s;) {
                unsigned m = 0, gsz = 0;
                if (std::sscanf(s, "%u:%u", &m, &gsz) == 2 && m <= own41::Backend41::MTX && gsz <= 9) be.mt_tgm[m] = gsz, set_tgm[m] = true;
                const char *cm = std::strchr(s, ',');
                if (!cm) break;
                s = cm + 1;
            }
        }
        // default since 2026-11-10 (note section 28, e81): prompt blocks of 16 run 4-row blocks on matrices of >= 4,096
        // rows on the card (OWN_MT_TGR=16:0 turns it off; the row threshold also applies to other OWN_MT_TGR entries)
        be.mt_tgr[16] = 4;
        be.mt_tgr_rows = 4096;
        if (const char *e = getenv("OWN_MT_TGR")) { // per block size: "m:r,m:r" rows per sub-group (2 or 4)
            for (const char *s = e; *s;) {
                unsigned m = 0, rr = 0;
                if (std::sscanf(s, "%u:%u", &m, &rr) == 2 && m <= own41::Backend41::MTX && (rr == 0 || rr == 2 || rr == 4)) be.mt_tgr[m] = rr, set_tgr[m] = true;
                const char *cm = std::strchr(s, ',');
                if (!cm) break;
                s = cm + 1;
            }
        }
        if (const char *e = getenv("OWN_MT_TGR_ROWS")) be.mt_tgr_rows = (unsigned)atoi(e);
        if (const char *e = getenv("OWN_MT_TGR_FMT")) be.mt_tgr_fmt = (unsigned)atoi(e);
        if (const char *e = getenv("OWN_MT_TGR_DRAFT")) be.mt_tgr_draft = atoi(e) != 0;
        // default since round 18 d4 / g78: blocks of 9-16 tokens (and larger ones, as 16) pick their dense forms per
        // matrix shape (OWN_MT_W16=0: off)
        be.mt_w16 = getenv("OWN_MT_W16") ? atoi(getenv("OWN_MT_W16")) != 0 : true;
        // weight-stationary dense rows for the matrix shapes and block sizes ops41sycl::WsTab lists (default on since
        // tg90: 3K read 353 -> 416 tok/s at blocks of 64; OWN_MT_WS=0: off)
        be.mt_ws = getenv("OWN_MT_WS") ? atoi(getenv("OWN_MT_WS")) != 0 : true;
        // the guessing checks' blocks (2 .. 6 tokens) take WsTab's check picks (pa/ck, pa/ck2): OWN_MT_CK=1 every block
        // size, OWN_MT_CK=n (n != 1; 0x.. allowed) the sizes M whose bit M - 2 is set, OWN_MT_CK_MS="2,4,5,6" those
        // sizes; OWN_MT_CK_FIN (the same forms; default: OWN_MT_CK's sizes): q_b's WS forms with the mix's finish
        auto ck_mask = [](const char *v) {
            const unsigned long n = strtoul(v, nullptr, 0);
            return n == 1 ? 0x1fu : (unsigned)(n & 0x1fu);
        };
        if (const char *e = getenv("OWN_MT_CK")) ops41sycl::g_ws_ck_mask = ck_mask(e);
        if (const char *e = getenv("OWN_MT_CK_MS")) {
            unsigned m = 0;
            for (const char *c = e; *c; ++c)
                if (*c >= '2' && *c <= '6') m |= 1u << (*c - '2');
            ops41sycl::g_ws_ck_mask = m;
        }
        ops41sycl::g_ws_ckf_mask = ops41sycl::g_ws_ck_mask;
        if (const char *e = getenv("OWN_MT_CK_FIN")) ops41sycl::g_ws_ckf_mask = ck_mask(e);
        // dride-1 (default 4-6 since tp99; OWN_MT_DRIDE=0 off): OWN_MT_DSPLIT's two mix finishes ride output-b's and shared down's launches under OWN_MT_WS
        // too, their weight-stationary forms kept (WsTab WS_DOTS; OWN_MT_DSPLIT_FIN=2, the default, or 1).
        // OWN_MT_DRIDE=1: checks of 4, 5 and 6 tokens; OWN_MT_DRIDE=n (n != 1; 0x.. allowed): the sizes M = 2 .. 6
        // whose bit M - 2 is set; OWN_MT_DRIDE_MS="4,6": those sizes
        if (const char *e = getenv("OWN_MT_DRIDE")) {
            const unsigned long n = strtoul(e, nullptr, 0);
            ops41sycl::g_ws_dride_mask = n == 1 ? 0x1cu : (unsigned)(n & 0x1fu);
        }
        // pb-1 (opt-in, /home/steve/dsv41-work/pb256/README-pb1.txt): OWN_PB=mask (0x.. allowed; default 0x1e since tp102, 0 = off), each
        // bit gives the production outputs bit for bit: 2 the H16 rows (router, compressor, indexer q_b) weight-stationary,
        // 4 the parallel expert grouping, 8 Q6_K forms with per-segment scales (no private arrays), 16 blocks of 65-256
        // tokens in per-role forms with the positions in token chunks; OWN_PB=1: 2 + 4 + 8 + 16 (0x1e)
        if (const char *e = getenv("OWN_PB")) {
            const unsigned long n = strtoul(e, nullptr, 0);
            ops41sycl::g_pb_mask = n == 1 ? 0x1eu : (unsigned)(n & 0x1eu);
        }
        // pace-1 (opt-in, /home/steve/dsv41-work/attn/pace/README.txt): the 16-head cards' q_b and output-a rows at checks
        // in persistent, pipelined launches (bit for bit). OWN_MT_PACE=1: every check size 2-6; OWN_MT_PACE=n (n != 1;
        // 0x.. allowed) the sizes M whose bit M - 2 is set; default 0x1f (every size) since tp103; 0 = off. OWN_MT_PACE_ROLES (default 7): 1 Q8_0 q_b,
        // 2 Q6_K q_b, 4 Q8_0 output-a; pace-2 (every card; /home/steve/dsv41-work/attn/pace2/README.txt): 8 the q_a + kv
        // pair, 16 output-b, 32 shared down, 64 the shared expert's gate + up with the router (127: all)
        if (const char *e = getenv("OWN_MT_PACE")) ops41sycl::g_pace_mask = ck_mask(e);
        if (const char *e = getenv("OWN_MT_PACE_ROLES")) ops41sycl::g_pace_roles = (unsigned)strtoul(e, nullptr, 0) & 127u;
        // OWN_MT_SW (opt-in, /home/steve/dsv41-work/attn/sw/README.txt; 0x.. allowed): 1 the checks' forms re-picked with
        // the register-mode change counted (~1.7 us per 256-register launch; replaces OWN_MT_PACE's tables at 2-6
        // tokens), 2 the 16-head cards' one-token q_b and output-a in 128-register pace forms; 3 both. Bit for bit.
        if (const char *e = getenv("OWN_MT_SW")) ops41sycl::g_pace_sw = (unsigned)strtoul(e, nullptr, 0) & 3u;
        if (const char *e = getenv("OWN_MT_DRIDE_MS")) {
            unsigned m = 0;
            for (const char *c = e; *c; ++c)
                if (*c >= '2' && *c <= '6') m |= 1u << (*c - '2');
            ops41sycl::g_ws_dride_mask = m;
        }
        // ck2-1 (opt-in, /home/steve/dsv41-work/ck2/README.md; each a bit-identical form): OWN_CK2_FORMS=bits (default 3):
        // 1 a 2-token block's FFN pre-norm + the mix's dot rows + the router rows in one launch (ops41sycl::FlNormKM),
        // 2 the mixes' dot rows riding a dense launch (router, q_a + kv) as SkDotsFF work-groups in it (RowsDotsK).
        // OWN_CK2=1: blocks of 2 and 3 tokens; OWN_CK2=n (n != 1; 0x.. allowed) the sizes M = 2 .. 6 whose bit M - 2 is set;
        // OWN_CK2_MS="2,3": those sizes
        if (const char *e = getenv("OWN_CK2")) {
            const unsigned long n = strtoul(e, nullptr, 0);
            be.mt_ck2 = n == 1 ? 0x3u : (unsigned)(n & 0x1fu);
        }
        if (const char *e = getenv("OWN_CK2_FORMS")) be.mt_ck2_forms = (unsigned)strtoul(e, nullptr, 0) & 3u;
        if (const char *e = getenv("OWN_CK2_MS")) {
            unsigned m = 0;
            for (const char *c = e; *c; ++c)
                if (*c >= '2' && *c <= '6') m |= 1u << (*c - '2');
            be.mt_ck2 = m;
        }
        if (const char *e = getenv("OWN_MT_TGW_ROWS")) be.mt_tgw_rows = (unsigned)atoi(e); // head: own token groups
        if (const char *e = getenv("OWN_MT_TGWM")) { // per block size: "m:g,m:g" the head's token group (1-6)
            for (const char *s = e; *s;) {
                unsigned m = 0, gsz = 0;
                if (std::sscanf(s, "%u:%u", &m, &gsz) == 2 && m <= own41::Backend41::MTX && gsz <= 6) be.mt_tgwm[m] = gsz, set_tgwm[m] = true;
                const char *cm = std::strchr(s, ',');
                if (!cm) break;
                s = cm + 1;
            }
        }
        for (int m = MTF_ + 1; m <= MTX_; ++m) {
            if (!set_tgm[m]) be.mt_tgm[m] = be.mt_tgm[MTF_];
            if (!set_tgr[m]) be.mt_tgr[m] = be.mt_tgr[MTF_];
            if (!set_tgwm[m]) be.mt_tgwm[m] = be.mt_tgwm[MTF_];
        }
        if (const char *e = getenv("OWN_DR_MXN")) be.dr_mxn = atoi(e) != 0;
        if (const char *e = getenv("OWN_HC_FIN")) be.hc_fin_form = atoi(e);
        if (const char *e = getenv("OWN_MT_RIDE")) be.mt_ride = atoi(e) != 0; // mix dot rows inside q_a / router
        if (const char *e = getenv("OWN_MT_RWG")) be.mt_rwg = (unsigned)atoi(e); // small row launches spread over cores
        if (const char *e = getenv("OWN_MT_RFUSE")) be.mt_rfuse = atoi(e) != 0; // router + shared gate/up in one launch
        // the stream mixes' dot rows in prompt blocks (pcd-1; DSPLIT + SKDOTS=8 by default since tg91, from 4 tokens on since tune92; each a bit-identical form)
        if (const char *e = getenv("OWN_MT_DSPLIT_MIN")) be.mt_dsplit_min = (unsigned)atoi(e); // OWN_MT_DSPLIT from m tokens on
        if (const char *e = getenv("OWN_MT_DSPLIT_FIN")) be.mt_dsplit_fin = atoi(e);    // finishes: 0 own, 1 riding, 2 auto
        if (const char *e = getenv("OWN_MT_SKDOTS")) be.mt_skdots = (unsigned)atoi(e);  // dot rows as SkDotsWM<K> (8 or 4)
        if (be.mt_skdots && be.mt_skdots != 4 && be.mt_skdots != 8) die("OWN_MT_SKDOTS: 0, 4 or 8");
        if (const char *e = getenv("OWN_MT_SKDOTS_MIN")) be.mt_skdots_min = (unsigned)atoi(e); // OWN_MT_SKDOTS from m tokens on
        // skn-1 (OWN_MT_SKNORM=15 and OWN_MT_HCPP=1 by default since tg93; each a bit-identical form): the one-token path's one-work-group norms per token of a
        // block. OWN_MT_SKNORM=mask: 1 5,120 norms alone, 2 pre-norm + SKDOTS rows in one launch, 4 q_a + kv norms,
        // 8 compressor pools (ratio 2), 16 compressor 512 norm (ratio 1); 31 = all. OWN_MT_SKNORM_MIN / _MAX: block sizes
        // (MAX, default 64, limits bits 1, 2 and 16 only)
        if (const char *e = getenv("OWN_MT_SKNORM")) be.mt_sknorm = (unsigned)atoi(e);
        if (be.mt_sknorm > 31) die("OWN_MT_SKNORM: a mask of 1, 2, 4, 8, 16");
        if (const char *e = getenv("OWN_MT_SKNORM_MIN")) be.mt_sknorm_min = (unsigned)atoi(e);
        if (const char *e = getenv("OWN_MT_SKNORM_MAX")) be.mt_sknorm_max = (unsigned)atoi(e);
        // skn-1 (off by default; the same values): the block's HcPostPrePM with the item index split by work-group
        if (const char *e = getenv("OWN_MT_HCPP")) be.mt_hcpp = atoi(e) != 0;
        // the check path's fixed cost (ckpath-1; each a bit-identical form; CK1, KVPAIR, FIN_QB, RING_ONE, DR_NOWAIT on by
        // default since tg90 (=0: off), KVPAIR / FIN_QB only for blocks of <= OWN_MT_MS_MAX=16 tokens)
        if (const char *e = getenv("OWN_CK1")) be.ck1 = atoi(e) != 0;                     // a one-token check as the plain step
        if (const char *e = getenv("OWN_MT_RIDE_MIN")) be.mt_ride_min = (unsigned)atoi(e); // OWN_MT_RIDE from m tokens on
        if (const char *e = getenv("OWN_MT_KVPAIR")) be.mt_kvpair = atoi(e) != 0;         // q_a + kv rows in one launch
        if (const char *e = getenv("OWN_MT_FIN_QB")) be.mt_fin_qb = atoi(e) != 0;         // attention mix finish in q_b's launch
        if (const char *e = getenv("OWN_MT_MS_MAX")) be.mt_ms_max = (unsigned)atoi(e);    // KVPAIR / FIN_QB up to m tokens
        if (const char *e = getenv("OWN_MT_EU_MIN")) be.mt_eu_min = (unsigned)atoi(e);     // OWN_MT_EU from m tokens on
        // rux-1 (off by default): row-tiled routed rows from OWN_MT_RUX_MIN tokens (16), group cap OWN_MT_RUX_CAP there (0: as set)
        if (const char *e = getenv("OWN_MT_RUX")) be.mt_rux = atoi(e) != 0;
        if (const char *e = getenv("OWN_MT_RUX_MIN")) be.mt_rux_min = (unsigned)std::max(1, atoi(e));
        if (const char *e = getenv("OWN_MT_RUX_CAP")) be.mt_rux_cap = (unsigned)atoi(e);
        if (be.mt_rux_cap > 16) die("OWN_MT_RUX_CAP: at most 16 slots per group");
        // rux4-1 (default on since tp109; tg108: traces identical, 3K read -5 %): the OWN_MT_RUX blocks' cap-6 routed
        // launches on the pipelined forms (same bits); OWN_RUX4=0: today's forms
        if (const char *e = getenv("OWN_RUX4")) be.rux4 = atoi(e) != 0;
        // rux5-1 (default on since tp110, tg109): one-token and 2-6-token check routed launches on the gathers-first forms (same bits); OWN_RUX5=0: the tp109 forms
        if (const char *e = getenv("OWN_RUX5")) be.rux5 = atoi(e) != 0;
        // rux6-1 (default on since tp112, rx6ab; OWN_RUX6=0 restores tp111): the prompt blocks' cap-6 routed launches of rux4's picks with prefetches
        // of the x blocks ahead of use (same bits)
        if (const char *e = getenv("OWN_RUX6")) be.rux6 = atoi(e) != 0;
        if (be.rux6) std::fprintf(stderr, "OWN_RUX6: prompt-block routed launches with x prefetches (rux6-1)\n");
        if (const char *e = getenv("OWN_U3_NOPAIR")) be.u3_nopair = atoi(e) != 0;         // checks' IQ2_XXS / IQ2_XS without pair code
        if (const char *e = getenv("OWN_RING_ONE")) be.ring_one = atoi(e) != 0;           // commit_pending in one launch
        if (const char *e = getenv("OWN_DR_NOWAIT")) be.dr_nowait = atoi(e) != 0;         // the draft's embed without a wait
        // draft-head-1 (DR_ANCHOR_ARG + DR_WS on by default since tg91, the rest off; the draft only proposes, the check keeps the answers)
        if (const char *e = getenv("OWN_DR_TGW")) be.dr_tgw = (unsigned)atoi(e);          // the draft's dense rows in groups of g
        if (const char *e = getenv("OWN_DR_ANCHOR_ARG")) be.dr_anchor_arg = atoi(e) != 0; // the chain's anchor by value
        if (const char *e = getenv("OWN_DR_WS")) be.dr_ws = atoi(e) != 0;                 // OWN_MT_WS's table in the draft
        // OWN_DR_VOCAB=<file of "id [count]" lines, most useful first>: the draft head over its first
        // OWN_DR_VOCAB_N ids (default 32768) plus the prompt's ids (OWN_DR_VOCAB_PROMPT=0: not those)
        if (const char *vf = getenv("OWN_DR_VOCAB")) {
            const long vn = getenv("OWN_DR_VOCAB_N") ? atol(getenv("OWN_DR_VOCAB_N")) : 32768;
            const bool vp = !getenv("OWN_DR_VOCAB_PROMPT") || atoi(getenv("OWN_DR_VOCAB_PROMPT")) != 0;
            std::ifstream vfs(vf);
            if (!vfs) die("OWN_DR_VOCAB unreadable");
            std::vector<int32_t> vids;
            std::string line;
            while ((long)vids.size() < vn && std::getline(vfs, line)) {
                std::istringstream ls(line);
                long long v;
                if (ls >> v) vids.push_back((int32_t)v);
            }
            if (vids.empty()) die("OWN_DR_VOCAB: no ids");
            const size_t nfile = vids.size();
            if (vp)
                for (int t : prompt) vids.push_back((int32_t)t);
            be.dr_vocab_set(vids);
            int vmin = 1 << 30, vmax = 0;
            for (int c = 0; c < opt.tp; ++c) {
                vmin = std::min(vmin, be.dr_vocab_rows(c));
                vmax = std::max(vmax, be.dr_vocab_rows(c));
            }
            std::fprintf(stderr, "draft vocabulary: %zu ids from %s + %zu prompt tokens -> %d .. %d rows per card\n",
                         nfile, vf, vp ? prompt.size() : (size_t)0, vmin, vmax);
        }
#endif

        // ---- prompt on the cards (OWN_PROMPT): one decode step per prompt token ----
        const int eos = getenv("OWN_EOS") ? atoi(getenv("OWN_EOS")) : 1;
        const bool prompt_head = getenv("OWN_PROMPT_HEAD") && atoi(getenv("OWN_PROMPT_HEAD")) != 0;
        if (!prompt.empty()) {
            double tp0 = now(), t_first = 0;
            size_t first_n = 1; // tokens in the first step (timed apart: kernel warm-up)
            // OWN_PROMPT_BLOCK=m (OWN_TP > 1): m prompt tokens per step (decode_block_tp), the same values
            const int pblock = getenv("OWN_PROMPT_BLOCK") ? atoi(getenv("OWN_PROMPT_BLOCK")) : 0;
            if (pblock > 1 && opt.tp > 1) {
                // OWN_ENG_AHEAD=n (default 16, or the block size past 16 tokens: the whole next block; 0 off; needs
                // OWN_ENG_EARLY): the engram rows of the next n prompt tokens are asked from the disk (page-cache hints
                // only) while the cards run the current block
                const long ahead = getenv("OWN_ENG_AHEAD") ? atol(getenv("OWN_ENG_AHEAD")) : std::max(16, pblock);
                for (size_t i = 0; i < prompt.size();) {
                    const int m = be.px_block_take((int)std::min<size_t>((size_t)pblock, prompt.size() - i)); // (OWN_PX_BIG)
                    for (int k = 0; k < m; ++k) be.comp_ids.push_back(token_map[prompt[i + k]]);
#ifndef OWN41_ACT_BF16
                    be.eng_ahead.clear();
                    for (size_t k = i + m; k < prompt.size() && (long)(k - i - m) < ahead; ++k)
                        be.eng_ahead.push_back(token_map[prompt[k]]);
#endif
                    be.trace_on = false;
                    double t1 = now();
                    be.skip_head = i + m < prompt.size();
                    std::vector<int32_t> blk(prompt.begin() + i, prompt.begin() + i + m);
                    first = be.decode_block_tp(blk.data(), m);
                    be.gprof_collect(); // OWN_GPROF: the prompt blocks' kernels count too (run with few answer tokens)
                    if (i == 0) { t_first = now() - t1; first_n = (size_t)m; }
                    i += m;
                }
#ifndef OWN41_ACT_BF16
                be.eng_ahead.clear();
#endif
            } else {
                for (size_t i = 0; i < prompt.size(); ++i) {
                    be.comp_ids.push_back(token_map[prompt[i]]);
                    be.trace_on = false;
                    double t1 = now();
                    // the head only for the last prompt token (OWN_PROMPT_HEAD=1: for every one, as before)
                    be.skip_head = opt.tp > 1 && !prompt_head && i + 1 < prompt.size();
                    first = be.decode_step(prompt[i]);
                    if (i == 0) t_first = now() - t1;
                }
            }
            be.skip_head = false;
#ifndef OWN41_ACT_BF16
            if (be.mt_idstat && be.ids_picks)
                std::fprintf(stderr, "expert picks: %ld blocks, %ld picks, %ld distinct per (block, layer) summed (%.1f %%)\n",
                             be.ids_blocks, be.ids_picks, be.ids_unique, 100.0 * be.ids_unique / be.ids_picks);
#endif
            double dtp = now() - tp0;
            std::fprintf(stderr, "prompt: %zu tokens read on the cards in %.2fs (%.1f tok/s; first step %.2fs incl. kernel build), first token %d\n",
                         prompt.size(), dtp, prompt.size() > first_n ? (prompt.size() - first_n) / (dtp - t_first) : 0.0, t_first,
                         first);
        }

#ifndef OWN41_ACT_BF16
        // ---- draft checking test (OWN_VERIFY_TEST=k, OWN_VERIFY_REF=ids of a plain run): every cycle checks
        // [current token, k guesses] in one block step and keeps what the model agrees with. The guesses are
        // the reference continuation, each replaced by a wrong token with probability OWN_VERIFY_BAD percent
        // (fixed pseudo-random sequence). The kept text must equal the plain run's.
        if (const char *vt = getenv("OWN_VERIFY_TEST"); vt && !prompt.empty()) {
            const int k = std::max(1, std::min(atoi(vt), (int)own41::Backend41::MTX - 1));
            std::vector<int> ref;
            if (const char *rf = getenv("OWN_VERIFY_REF")) {
                std::ifstream f(rf);
                long long v;
                while (f >> v) ref.push_back((int)v);
            }
            if (ref.empty()) die("OWN_VERIFY_TEST needs OWN_VERIFY_REF");
            const int bad = getenv("OWN_VERIFY_BAD") ? atoi(getenv("OWN_VERIFY_BAD")) : 0;
            uint32_t rng = 12345u;
            std::vector<int> out{first};
            int cur = first;
            long cycles = 0, guessed = 0, accepted = 0;
            const double tv0 = now();
            while ((int)out.size() < ndecode) {
                const size_t i = out.size();
                const int kk = std::min(k, ndecode - (int)out.size());
                std::vector<int32_t> blk{cur};
                for (int j = 0; j < kk; ++j) {
                    int d = i + j < ref.size() ? ref[i + j] : 0;
                    rng = rng * 1664525u + 1013904223u;
                    if ((int)((rng >> 8) % 100) < bad) d = (d + 1) % 129280;
                    blk.push_back(d);
                }
                for (int32_t t : blk) be.comp_ids.push_back(token_map[t]);
                std::vector<int32_t> nx(blk.size());
                be.decode_verify_tp(blk.data(), (int)blk.size(), nx.data());
                int n = 1;
                while (n < (int)blk.size() && nx[n - 1] == blk[n]) ++n;
                be.commit_block(n);
                be.comp_ids.resize((size_t)be.pos);
                for (int j = 1; j < n; ++j) out.push_back(blk[j]);
                out.push_back(nx[n - 1]);
                cur = nx[n - 1];
                ++cycles;
                guessed += kk;
                accepted += n - 1;
                be.gprof_collect(); // OWN_GPROF=2: kernel time per verify cycle (the first cycle is dropped)
                if (cycles == 1) { be.gprof_t.clear(); be.gprof_n.clear(); be.kprof_t.clear(); be.kprof_n.clear(); }
            }
            out.resize(std::min<size_t>(out.size(), (size_t)ndecode));
            const double dt = now() - tv0;
            bool same = true;
            for (size_t j = 0; j < out.size(); ++j)
                if (j >= ref.size() || out[j] != ref[j]) { same = false; break; }
            std::fprintf(stderr, "verify test: %zu tokens in %ld cycles (%.2f per cycle; %ld of %ld guesses kept) in %.2fs "
                         "= %.2f tok/s; %s the plain run\n", out.size() - 1, cycles, (double)(out.size() - 1) / cycles,
                         accepted, guessed, dt, (out.size() - 1) / dt, same ? "SAME AS" : "DIFFERENT FROM");
            if (opt.kprof && cycles > 1) {
                std::vector<std::pair<double, std::string>> kv;
                double ktot = 0;
                const double nc = (double)(cycles - 1);
                for (auto &[kn, t] : be.kprof_t) { kv.push_back({t / nc, kn}); ktot += t / nc; }
                std::sort(kv.rbegin(), kv.rend());
                std::fprintf(stderr, "kernel time per type (ms per verify cycle, start to end; launches per cycle):\n");
                for (auto &[t, kn] : kv)
                    std::fprintf(stderr, "  %8.3f  %5.1f%%  %7.1f  %8.2f us  %s\n", t * 1e3, 100 * t / ktot,
                                 be.kprof_n[kn] / nc, t * 1e6 * nc / std::max(1L, be.kprof_n[kn]), kn.c_str());
                std::fprintf(stderr, "  kernels %.3f ms per cycle (wall %.3f ms per cycle)\n", ktot * 1e3, dt / cycles * 1e3);
            }
            std::ofstream of(argv[3]);
            for (int t : out) of << t << "\n";
            return same ? 0 : 3;
        }
        // ---- speculative decoding with the DSpark draft (OWN_DSPARK + OWN_SPEC=k, k = 1 .. 5 guesses per
        // cycle): the draft proposes k tokens after the current one, the target checks [current, guesses] in
        // one block step and keeps the guesses it agrees with plus its own next token. The text is the target's
        // greedy text by construction; OWN_VERIFY_REF (a plain run's ids) checks that.
        if (const char *sv = getenv("OWN_SPEC"); sv && !prompt.empty()) {
            if (!opt.dspark) die("OWN_SPEC needs OWN_DSPARK");
            const int k = std::max(1, std::min(atoi(sv), (int)own41::Backend41::DR_BLOCK));
            std::vector<int> ref;
            if (const char *rf = getenv("OWN_VERIFY_REF")) {
                std::ifstream f(rf);
                long long v;
                while (f >> v) ref.push_back((int)v);
            }
            std::vector<int> out{first};
            int cur = first;
            long cycles = 0, guessed = 0, accepted = 0;
            std::vector<long> hist(k + 2, 0);
            double t_draft = 0, t_check = 0;
            // OWN_SPEC_TAU=p: check only the leading guesses whose running product of the draft's probabilities
            // stays >= p (at least OWN_SPEC_KMIN, default 1; 0 = the anchor alone, a one-token block); OWN_SPEC_LOG=file: per round the 5 probabilities and
            // then: guesses checked, guesses kept, draft ms, check ms, 1 if the guesses came from OWN_SPEC_NGRAM
            const float tau = getenv("OWN_SPEC_TAU") ? (float)atof(getenv("OWN_SPEC_TAU")) : 0.0f;
            const int kmin = getenv("OWN_SPEC_KMIN") ? std::max(0, atoi(getenv("OWN_SPEC_KMIN"))) : 1; // 0: a round may check no guess
            FILE *slog = getenv("OWN_SPEC_LOG") ? std::fopen(getenv("OWN_SPEC_LOG"), "w") : nullptr;
            // OWN_SPEC_NGRAM=n (2..8; 2026-11-11): before each round the text's last n tokens (prompt + answer so
            // far) are looked up in the text before them; on a match, the tokens that followed their most recent
            // earlier occurrence are the round's guesses (up to OWN_SPEC_NGRAM_MAX, default 8, at most 63) and the
            // draft does not run that round (its windows still get every checked block's features, so its later
            // rounds see the same state). The check is the same full model: the answer cannot change.
            const int ngram = getenv("OWN_SPEC_NGRAM") ? std::clamp(atoi(getenv("OWN_SPEC_NGRAM")), 0, 8) : 0;
            const int ngmax = getenv("OWN_SPEC_NGRAM_MAX") ? std::clamp(atoi(getenv("OWN_SPEC_NGRAM_MAX")), 1, 63) : 8;
            std::vector<int> txt(prompt);
            txt.push_back(first);
            std::unordered_map<uint64_t, int> ngix; // hash of the n tokens ending at e -> the latest such e
            size_t ng_done = 0;                     // ends 0 .. ng_done - 1 are in ngix
            auto ng_key = [&](size_t e) {
                uint64_t h = 1469598103934665603ull;
                for (int i = 0; i < ngram; ++i) h = (h ^ (uint64_t)(uint32_t)txt[e - i]) * 1099511628211ull;
                return h;
            };
            long ng_rounds = 0, ng_guessed = 0, ng_kept = 0;
            hist.assign((size_t)std::max(k, ngram ? ngmax : 0) + 2, 0);
            for (int c = 0; c < own41::Backend41::TILES; ++c) be.eng_t[c] = be.eng_tq[c] = 0, be.eng_n[c] = 0;
            const auto io0 = host_io();
            const double ts0 = now();
            while ((int)out.size() < ndecode) {
                int32_t d[own41::Backend41::DR_BLOCK];
                float conf[own41::Backend41::DR_BLOCK];
                const double ta = now();
                int kk = std::min(k, ndecode - (int)out.size());
                std::vector<int32_t> ngg; // the lookup's guesses (empty: the draft's)
                if (ngram) {
                    const size_t len = txt.size();
                    for (; ng_done + 1 < len; ++ng_done)
                        if (ng_done + 1 >= (size_t)ngram) ngix[ng_key(ng_done)] = (int)ng_done;
                    if (len >= (size_t)ngram + 1) {
                        const auto it = ngix.find(ng_key(len - 1));
                        if (it != ngix.end()) {
                            const size_t e = (size_t)it->second;
                            bool eq = true;
                            for (int i = 0; i < ngram && eq; ++i) eq = txt[e - i] == txt[len - 1 - i];
                            const int lim = std::min(ngmax, ndecode - (int)out.size());
                            for (size_t j = e + 1; eq && j < len && (int)ngg.size() < lim; ++j) ngg.push_back(txt[j]);
                        }
                    }
                }
                if (ngg.empty()) be.draft_tp(cur, d, kk, conf, token_map[cur]);
                else
                    for (int j = 0; j < own41::Backend41::DR_BLOCK; ++j) conf[j] = 0.0f;
                const double tb = now();
                if (!ngg.empty()) {
                    kk = (int)ngg.size();
                } else if (tau > 0.0f) {
                    float run = 1.0f;
                    int kt = 0;
                    while (kt < kk && (run *= conf[kt]) >= tau) ++kt;
                    kk = std::max(std::min(kmin, kk), kt);
                }
                std::vector<int32_t> blk{cur};
                for (int j = 0; j < kk; ++j) blk.push_back(ngg.empty() ? d[j] : ngg[j]);
                for (int32_t t : blk) be.comp_ids.push_back(token_map[t]);
                std::vector<int32_t> nx(blk.size());
                be.decode_verify_tp(blk.data(), (int)blk.size(), nx.data());
                int n = 1;
                while (n < (int)blk.size() && nx[n - 1] == blk[n]) ++n;
                be.commit_block(n);
                be.comp_ids.resize((size_t)be.pos);
                const double tc = now();
                t_draft += tb - ta;
                t_check += tc - tb;
                if (slog) {
                    for (int j = 0; j < own41::Backend41::DR_BLOCK; ++j) std::fprintf(slog, "%.4f ", conf[j]);
                    std::fprintf(slog, "%d %d %.3f %.3f %d\n", kk, n - 1, (tb - ta) * 1e3, (tc - tb) * 1e3, ngg.empty() ? 0 : 1);
                }
                const size_t o0 = out.size();
                for (int j = 1; j < n; ++j) out.push_back(blk[j]);
                out.push_back(nx[n - 1]);
                cur = nx[n - 1];
                ++cycles;
                guessed += kk;
                accepted += n - 1;
                ++hist[n - 1];
                if (!ngg.empty()) ++ng_rounds, ng_guessed += kk, ng_kept += n - 1;
                for (size_t j = o0; j < out.size(); ++j) txt.push_back(out[j]);
                bool ended = false; // a kept guess can be the end of sentence: the text ends there, as a plain run's
                for (size_t j = o0; eos >= 0 && j < out.size(); ++j)
                    if (out[j] == eos) { out.resize(j + 1); ended = true; break; }
                if (ended) {
                    be.gprof_collect();
                    break;
                }
                be.gprof_collect(); // OWN_GPROF=2: kernel time per cycle, draft + check (the first cycle is dropped)
                if (cycles == 1) { be.gprof_t.clear(); be.gprof_n.clear(); be.kprof_t.clear(); be.kprof_n.clear(); }
                if (eos >= 0 && cur == eos) break;
            }
            if (opt.kprof && cycles > 1) {
                std::vector<std::pair<double, std::string>> kv;
                double ktot = 0;
                const double nc = (double)(cycles - 1);
                for (auto &[kn, t] : be.kprof_t) { kv.push_back({t / nc, kn}); ktot += t / nc; }
                std::sort(kv.rbegin(), kv.rend());
                std::fprintf(stderr, "kernel time per type (ms per spec cycle, draft + check, start to end; launches per cycle):\n");
                for (auto &[t, kn] : kv)
                    std::fprintf(stderr, "  %8.3f  %5.1f%%  %7.1f  %8.2f us  %s\n", t * 1e3, 100 * t / ktot,
                                 be.kprof_n[kn] / nc, t * 1e6 * nc / std::max(1L, be.kprof_n[kn]), kn.c_str());
                std::fprintf(stderr, "  kernels %.3f ms per cycle\n", ktot * 1e3);
            }
            if (slog) std::fclose(slog);
            out.resize(std::min<size_t>(out.size(), (size_t)ndecode));
            const double dt = now() - ts0;
            bool same = !ref.empty();
            for (size_t j = 0; same && j < out.size(); ++j)
                if (j >= ref.size() || out[j] != ref[j]) same = false;
            std::fprintf(stderr, "spec decode: %zu tokens in %ld cycles (%.2f per cycle; %ld of %ld guesses kept, %.1f %%) in "
                         "%.2fs = %.2f tok/s; draft %.2f ms + check %.2f ms per cycle; %s\n",
                         out.size() - 1, cycles, (double)(out.size() - 1) / cycles, accepted, guessed,
                         100.0 * accepted / std::max(1L, guessed), dt, (out.size() - 1) / dt, t_draft / cycles * 1e3,
                         t_check / cycles * 1e3,
                         ref.empty() ? "no reference" : same ? "SAME AS the plain run" : "DIFFERENT FROM the plain run");
            host_io_line(be, opt.tp, io0);
            std::fprintf(stderr, "kept guesses per cycle:");
            for (size_t j = 0; j + 1 < hist.size(); ++j) std::fprintf(stderr, " %zu:%ld", j, hist[j]);
            std::fprintf(stderr, "\n");
            if (ngram)
                std::fprintf(stderr, "lookup guesses (OWN_SPEC_NGRAM=%d, up to %d): %ld rounds, %ld of %ld guesses kept\n",
                             ngram, ngmax, ng_rounds, ng_kept, ng_guessed);
            std::ofstream of(argv[3]);
            for (int t : out) of << t << "\n";
            return ref.empty() || same ? 0 : 3;
        }
#endif
        // ---- decode ----
        static const int srcs[4] = {2, 8, 14, 20};
        std::vector<int> out_ids{forced.empty() ? first : forced[0]};
        int cur = out_ids[0];
        double t_dec = 0;
        int n_timed = 0;
        for (int c = 0; c < own41::Backend41::TILES; ++c) be.eng_t[c] = be.eng_tq[c] = 0, be.eng_n[c] = 0;
        const auto io0p = host_io();
        // OWN_GPROF_DECODE=1: the profile counts the answer steps only (the prompt blocks' kernels and the first
        // answer step are dropped; without it a prompt's kernels are divided over the answer steps)
        const bool gprof_dec = opt.gprof && getenv("OWN_GPROF_DECODE") && atoi(getenv("OWN_GPROF_DECODE")) > 0;
        int n_prof = 0;
        if (gprof_dec) { be.gprof_collect(); be.gprof_t.clear(); be.gprof_n.clear(); be.kprof_t.clear(); be.kprof_n.clear(); }
        for (int step = 1; step < ndecode; ++step) {
            if (!forced.empty()) {
                if (step - 1 >= (int)forced.size()) break;
                cur = forced[step - 1];
            }
            be.comp_ids.push_back(token_map[cur]);
            be.trace_step = step;
            be.trace_on = step <= trace_steps;
            if (opt.layer_begin > 0) {
                auto s = inject.find({step, opt.layer_begin - 1, TT_STREAMS_FFN});
                auto p = inject.find({step, opt.layer_begin - 1, TT_FFN_MIX_PRE});
                if (s == inject.end() || p == inject.end()) {
                    std::fprintf(stderr, "reference trace ends at step %d\n", step - 1);
                    break;
                }
                be.set_streams(s->second.data(), p->second.data());
                for (int i = 0; i < 4; ++i) {
                    if (srcs[i] >= opt.layer_begin) continue;
                    auto a = inject.find({step, srcs[i], TT_PUB_CKV});
                    auto b = inject.find({step, srcs[i], TT_PUB_IK});
                    if (a != inject.end() && b != inject.end())
                        be.append_published(i, a->second.data(), b->second.data());
                }
            }
            double t1 = now();
            int next = be.decode_step(cur);
            double dt = now() - t1;
            if (step > 1 || !prompt.empty()) { t_dec += dt; ++n_timed; } // a cold first step carries kernel compilation
            else be.prof_t.clear();
            be.gprof_collect();
            if (!(step > 1 || !prompt.empty()) || (gprof_dec && step == 1)) { be.gprof_t.clear(); be.gprof_n.clear(); be.kprof_t.clear(); be.kprof_n.clear(); }
            else ++n_prof;
            if (opt.head) {
                std::fprintf(stderr, "tok %d -> %d (%.3fs)", step, next, dt);
                if (opt.debug || step <= trace_steps) {
                    std::fprintf(stderr, " | top5:");
                    for (auto &[id, v] : be.top5()) std::fprintf(stderr, " %d:%.4f", id, v);
                }
                std::fprintf(stderr, "\n");
                out_ids.push_back(next);
                cur = next;
                if (forced.empty() && next == eos) {
                    std::fprintf(stderr, "end of sentence after %d generated tokens\n", (int)out_ids.size());
                    break;
                }
            } else {
                std::fprintf(stderr, "step %d layers %d:%d (%.3fs)\n", step, opt.layer_begin, opt.layer_end, dt);
            }
            if (be.trace_f) fflush(be.trace_f);
        }
        if (n_timed) {
            std::fprintf(stderr, "decode: %d steps after the first, %.3f s/step, %.2f tok/s\n", n_timed,
                         t_dec / n_timed, n_timed / t_dec);
            host_io_line(be, opt.tp, io0p);
        }
        if (be.prof_on && n_timed) {
            std::vector<std::pair<double, std::string>> v;
            double tot = 0;
            for (auto &[k, t] : be.prof_t) { v.push_back({t / n_timed, k}); tot += t / n_timed; }
            std::sort(v.rbegin(), v.rend());
            std::fprintf(stderr, "profile (ms per step, queue wait at every mark):\n");
            for (auto &[t, k] : v) std::fprintf(stderr, "  %-14s %8.2f  %5.1f%%\n", k.c_str(), t * 1e3, 100 * t / tot);
            std::fprintf(stderr, "  %-14s %8.2f\n", "total", tot * 1e3);
        }
        if (opt.gprof && n_prof) {
            const int n_pr = n_prof; // steps in the profile (== n_timed unless OWN_GPROF_DECODE drops the first)
            std::vector<std::pair<double, std::string>> v;
            double tot = 0;
            for (auto &[k, t] : be.gprof_t) { v.push_back({t / n_pr, k}); tot += t / n_pr; }
            std::sort(v.rbegin(), v.rend());
            std::fprintf(stderr, "GPU-time profile (ms per step; card time between marks, no waits):\n");
            for (auto &[t, k] : v)
                std::fprintf(stderr, "  %-14s %8.3f  %5.1f%%  (%ld marks/step)\n", k.c_str(), t * 1e3, 100 * t / tot,
                             be.gprof_n[k] / n_pr);
            std::fprintf(stderr, "  %-14s %8.3f   (wall %.3f)\n", "total", tot * 1e3, t_dec / n_timed * 1e3);
            if (opt.kprof) {
                std::vector<std::pair<double, std::string>> kv;
                double ktot = 0;
                for (auto &[k, t] : be.kprof_t) { kv.push_back({t / n_pr, k}); ktot += t / n_pr; }
                std::sort(kv.rbegin(), kv.rend());
                std::fprintf(stderr, "kernel time per type (ms per step, start to end; launches per step):\n");
                for (auto &[t, k] : kv)
                    std::fprintf(stderr, "  %8.3f  %5.1f%%  %5ld  %8.2f us  %s\n", t * 1e3, 100 * t / tot,
                                 be.kprof_n[k] / n_pr, t * 1e6 * n_pr / std::max(1L, be.kprof_n[k]), k.c_str());
                std::fprintf(stderr, "  kernels %8.3f ms, launches %ld per step; marks total %.3f -> gaps/copies %.3f ms\n",
                             ktot * 1e3, [&] { long n = 0; for (auto &[k, c] : be.kprof_n) n += c; return n / n_pr; }(),
                             tot * 1e3, (tot - ktot) * 1e3);
            }
        }
        std::ofstream of(argv[3]);
        for (int t : out_ids) of << t << "\n";
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "fatal: %s\n", ex.what());
        return 1;
    }
    return 0;
}
