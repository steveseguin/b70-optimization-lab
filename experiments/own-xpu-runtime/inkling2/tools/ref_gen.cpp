// ref_gen: greedy continuation with the llama.cpp CPU reference, as token ids (our engine's target).
//   ref_gen <model.gguf> <tokens.txt> <n_gen> [ubatch]
// Prints one line "ids: ..." with the generated ids (stops at EOS) and the time per phase on stderr.
// The prompt is read in ubatches of [ubatch] tokens (default 512); greedy = argmax over the unpadded vocabulary.
#include "llama.h"
#include <chrono>
#include <cstdlib>
#include <cstdio>
#include <fstream>
#include <vector>

int main(int argc, char **argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: ref_gen <model.gguf> <tokens.txt> <n_gen> [ubatch]\n"); return 2; }
    std::vector<llama_token> toks;
    { std::ifstream f(argv[2]); long v; while (f >> v) toks.push_back((llama_token)v); }
    int n_gen = std::atoi(argv[3]), ub = argc > 4 ? std::atoi(argv[4]) : 512;
    llama_backend_init();
    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    // REF_NO_REPACK=1: keep the weights in their file layout (needed for the high-precision build)
    if (std::getenv("REF_NO_REPACK")) mp.use_extra_bufts = false;
    llama_model *model = llama_model_load_from_file(argv[1], mp);
    if (!model) return 1;
    const llama_vocab *vocab = llama_model_get_vocab(model);
    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = (uint32_t)(toks.size() + n_gen + 16);
    cp.n_batch = cp.n_ubatch = (uint32_t)ub;
    cp.n_threads = cp.n_threads_batch = 8;
    // REF_FA=0: no flash attention (the dense path keeps the bias mask in F32)
    if (const char *e = std::getenv("REF_FA")) cp.flash_attn_type = std::atoi(e) ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
    llama_context *ctx = llama_init_from_model(model, cp);
    if (!ctx) return 1;
    auto t0 = std::chrono::steady_clock::now();
    llama_batch b = llama_batch_init(ub, 0, 1);
    size_t pos = 0;
    while (pos < toks.size()) {
        int n = (int)std::min<size_t>(ub, toks.size() - pos);
        b.n_tokens = n;
        for (int i = 0; i < n; ++i) { b.token[i] = toks[pos + i]; b.pos[i] = (llama_pos)(pos + i); b.n_seq_id[i] = 1; b.seq_id[i][0] = 0; b.logits[i] = pos + i + 1 == toks.size(); }
        if (llama_decode(ctx, b)) { std::fprintf(stderr, "decode failed\n"); return 1; }
        pos += n;
    }
    auto t1 = std::chrono::steady_clock::now();
    const int nv = llama_vocab_n_tokens(vocab);
    std::vector<llama_token> out;
    int last = b.n_tokens - 1;
    for (int g = 0; g < n_gen; ++g) {
        const float *lg = llama_get_logits_ith(ctx, last);
        int best = 0;
        for (int i = 1; i < nv; ++i) if (lg[i] > lg[best]) best = i;
        out.push_back(best);
        if (llama_vocab_is_eog(vocab, best)) break;
        b.n_tokens = 1; b.token[0] = best; b.pos[0] = (llama_pos)(toks.size() + g); b.n_seq_id[0] = 1; b.seq_id[0][0] = 0; b.logits[0] = 1;
        if (llama_decode(ctx, b)) { std::fprintf(stderr, "decode failed\n"); return 1; }
        last = 0;
    }
    auto t2 = std::chrono::steady_clock::now();
    std::printf("ids:");
    for (auto t : out) std::printf(" %d", t);
    std::printf("\n");
    double pp = std::chrono::duration<double>(t1 - t0).count(), tg = std::chrono::duration<double>(t2 - t1).count();
    std::fprintf(stderr, "prompt %zu tokens %.2f s; generated %zu in %.2f s (%.2f tok/s)\n", toks.size(), pp, out.size(), tg, out.size() / tg);
    return 0;
}
