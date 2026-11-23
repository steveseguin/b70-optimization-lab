// ref_dump: run the llama.cpp CPU reference on a token sequence and save chosen intermediate tensors in full.
// Built against the reference tree only (it is our oracle, not part of the engine).
//   ref_dump <model.gguf> <tokens.txt> <out_dir> [name-prefix ...]
// tokens.txt: whitespace-separated token ids. The whole sequence is decoded in one batch with logits for every
// position (n_ubatch = n_batch = length), then greedy continuation is not run: this is a forward-pass oracle.
// Each saved tensor goes to <out_dir>/<name>.f32 (float32, ggml layout) and a line in <out_dir>/index.tsv:
//   name  type  ne0 ne1 ne2 ne3
// Default prefixes: inp_embd, attn_out, ffn_inp, ffn_out, l_out, result_norm, result_output, Qcur, Kcur, Vcur, Rcur.
#include "ggml-backend.h"
#include "ggml.h"
#include "llama.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <string>
#include <vector>

struct Ctx {
    std::string dir;
    std::vector<std::string> prefixes;
    std::map<std::string, int> seen;
    FILE *index = nullptr;
    long saved = 0;
};

static bool wanted(const Ctx &c, const char *name) {
    for (auto &p : c.prefixes)
        if (std::strncmp(name, p.c_str(), p.size()) == 0) return true;
    return false;
}

static bool cb(ggml_tensor *t, bool ask, void *ud) {
    Ctx &c = *(Ctx *)ud;
    if (ask) return wanted(c, t->name);
    if (!wanted(c, t->name)) return true;
    std::vector<float> f(ggml_nelements(t));
    std::vector<uint8_t> raw(ggml_nbytes(t));
    ggml_backend_tensor_get(t, raw.data(), 0, raw.size());
    if (!ggml_is_contiguous(t)) { std::fprintf(stderr, "skip non-contiguous %s\n", t->name); return true; }
    if (t->type == GGML_TYPE_F32) std::memcpy(f.data(), raw.data(), raw.size());
    else if (t->type == GGML_TYPE_F16 || t->type == GGML_TYPE_BF16) ggml_get_type_traits(t->type)->to_float(raw.data(), f.data(), f.size());
    else if (t->type == GGML_TYPE_I32) { for (size_t i = 0; i < f.size(); ++i) f[i] = (float)((int32_t *)raw.data())[i]; }
    else { std::fprintf(stderr, "skip %s of type %s\n", t->name, ggml_type_name(t->type)); return true; }
    std::string name = t->name;
    int n = c.seen[name]++;
    if (n) name += "#" + std::to_string(n); // a name computed twice (chunked paths) keeps every copy
    std::ofstream o(c.dir + "/" + name + ".f32", std::ios::binary);
    o.write((const char *)f.data(), f.size() * 4);
    std::fprintf(c.index, "%s\t%s\t%lld\t%lld\t%lld\t%lld\n", name.c_str(), ggml_type_name(t->type), (long long)t->ne[0],
                 (long long)t->ne[1], (long long)t->ne[2], (long long)t->ne[3]);
    ++c.saved;
    return true;
}

int main(int argc, char **argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: ref_dump <model.gguf> <tokens.txt> <out_dir> [prefix ...]\n"); return 2; }
    Ctx c;
    c.dir = argv[3];
    for (int i = 4; i < argc; ++i) c.prefixes.push_back(argv[i]);
    if (c.prefixes.empty())
        c.prefixes = {"inp_embd", "attn_out", "ffn_inp", "ffn_out", "l_out", "result_norm", "result_output",
                      "Qcur", "Kcur", "Vcur", "Rcur"};
    std::vector<llama_token> toks;
    { std::ifstream f(argv[2]); long v; while (f >> v) toks.push_back((llama_token)v); }
    if (toks.empty()) { std::fprintf(stderr, "no tokens\n"); return 2; }
    c.index = std::fopen((c.dir + "/index.tsv").c_str(), "w");
    if (!c.index) { std::fprintf(stderr, "cannot write %s\n", c.dir.c_str()); return 2; }

    llama_backend_init();
    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    // REF_NO_REPACK=1: keep the weights in their file layout (the CPU repacked kernels bypass type_traits)
    if (std::getenv("REF_NO_REPACK")) mp.use_extra_bufts = false;
    llama_model *model = llama_model_load_from_file(argv[1], mp);
    if (!model) { std::fprintf(stderr, "model load failed\n"); return 1; }
    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = (uint32_t)std::max<size_t>(toks.size() + 16, 512);
    cp.n_batch = cp.n_ubatch = (uint32_t)toks.size();
    cp.n_threads = cp.n_threads_batch = 8;
    // REF_FA=0: no flash attention (the dense path keeps the bias mask in F32)
    if (const char *e = std::getenv("REF_FA")) cp.flash_attn_type = std::atoi(e) ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
    cp.cb_eval = cb;
    cp.cb_eval_user_data = &c;
    llama_context *ctx = llama_init_from_model(model, cp);
    if (!ctx) { std::fprintf(stderr, "context failed\n"); return 1; }
    llama_batch b = llama_batch_init((int32_t)toks.size(), 0, 1);
    for (size_t i = 0; i < toks.size(); ++i) {
        b.token[i] = toks[i]; b.pos[i] = (llama_pos)i; b.n_seq_id[i] = 1; b.seq_id[i][0] = 0; b.logits[i] = 1;
    }
    b.n_tokens = (int32_t)toks.size();
    if (llama_decode(ctx, b)) { std::fprintf(stderr, "decode failed\n"); return 1; }
    std::fclose(c.index);
    std::fprintf(stderr, "saved %ld tensors for %zu tokens to %s\n", c.saved, toks.size(), c.dir.c_str());
    llama_batch_free(b);
    llama_free(ctx);
    llama_model_free(model);
    return 0;
}
