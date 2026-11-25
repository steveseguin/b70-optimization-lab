// ref_vision: the llama.cpp CPU reference's image path for Inkling-2 (our oracle, never part of the engine).
//   ref_vision <model.gguf> <mmproj.gguf> <image> <prompt.txt> <out_dir> [n_gen] [prefix ...]
// prompt.txt: the rendered prompt (special tokens as text) with mtmd_default_marker() where the image goes.
// Writes to out_dir:
//   chunks.txt   one line per chunk: "text <ids...>" or "image <n_tokens> <n_pos> <nx> <ny>"
//   embd<k>.f32  the projected rows of image chunk k (n_tokens x n_embd floats), shapes in chunks.txt
//   gen.ids      greedy continuation (n_gen tokens; 0 = the text model is not run: encoder only)
//   <name>.f32 + index.tsv  encoder tensors whose names start with a prefix (cb_eval, as ref_dump)
// Precision switches as for ref_dump (GGML_CPU_F32_ACT=1 with the oracle patch; REF_FA=0 no flash attention).
#include "ggml-backend.h"
#include "ggml.h"
#include "llama.h"
#include "mtmd-helper.h"
#include "mtmd.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
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
    if (!ggml_is_contiguous(t)) { std::fprintf(stderr, "skip non-contiguous %s\n", t->name); return true; }
    std::vector<float> f(ggml_nelements(t));
    std::vector<uint8_t> raw(ggml_nbytes(t));
    ggml_backend_tensor_get(t, raw.data(), 0, raw.size());
    if (t->type == GGML_TYPE_F32) std::memcpy(f.data(), raw.data(), raw.size());
    else if (t->type == GGML_TYPE_F16 || t->type == GGML_TYPE_BF16) ggml_get_type_traits(t->type)->to_float(raw.data(), f.data(), f.size());
    else if (t->type == GGML_TYPE_I32) { for (size_t i = 0; i < f.size(); ++i) f[i] = (float)((int32_t *)raw.data())[i]; }
    else { std::fprintf(stderr, "skip %s of type %s\n", t->name, ggml_type_name(t->type)); return true; }
    std::string name = t->name;
    const int n = c.seen[name]++;
    if (n) name += "#" + std::to_string(n);
    std::ofstream o(c.dir + "/" + name + ".f32", std::ios::binary);
    o.write((const char *)f.data(), f.size() * 4);
    std::fprintf(c.index, "%s\t%s\t%lld\t%lld\t%lld\t%lld\n", name.c_str(), ggml_type_name(t->type), (long long)t->ne[0],
                 (long long)t->ne[1], (long long)t->ne[2], (long long)t->ne[3]);
    ++c.saved;
    return true;
}

int main(int argc, char **argv) {
    if (argc < 6) {
        std::fprintf(stderr, "usage: ref_vision <model.gguf> <mmproj.gguf> <image> <prompt.txt> <out_dir> [n_gen] [prefix ...]\n");
        return 2;
    }
    Ctx c;
    c.dir = argv[5];
    const int n_gen = argc > 6 ? std::atoi(argv[6]) : 0;
    for (int i = 7; i < argc; ++i) c.prefixes.push_back(argv[i]);
    std::string prompt;
    { std::ifstream f(argv[4]); std::stringstream ss; ss << f.rdbuf(); prompt = ss.str(); }
    if (prompt.find(mtmd_default_marker()) == std::string::npos) {
        std::fprintf(stderr, "the prompt has no %s\n", mtmd_default_marker());
        return 2;
    }
    c.index = std::fopen((c.dir + "/index.tsv").c_str(), "w");
    if (!c.index) { std::fprintf(stderr, "cannot write %s\n", c.dir.c_str()); return 2; }

    llama_backend_init();
    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    if (std::getenv("REF_NO_REPACK")) mp.use_extra_bufts = false;
    llama_model *model = llama_model_load_from_file(argv[1], mp);
    if (!model) { std::fprintf(stderr, "model load failed\n"); return 1; }

    mtmd_context_params vp = mtmd_context_params_default();
    vp.use_gpu = false;
    vp.n_threads = 8;
    vp.print_timings = true;
    vp.warmup = false;
    if (const char *e = std::getenv("REF_FA")) vp.flash_attn_type = std::atoi(e) ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
    if (!c.prefixes.empty()) { vp.cb_eval = cb; vp.cb_eval_user_data = &c; }
    mtmd_context *vc = mtmd_init_from_file(argv[2], model, vp);
    if (!vc) { std::fprintf(stderr, "mmproj load failed\n"); return 1; }

    mtmd_helper_init_opt io = mtmd_helper_init_opt_default();
    auto bw = mtmd_helper_bitmap_init_from_file(vc, argv[3], false, io);
    mtmd_bitmap *bm = bw.bitmap;
    if (!bm) { std::fprintf(stderr, "cannot read the image %s\n", argv[3]); return 1; }
    std::fprintf(stderr, "image %u x %u\n", mtmd_bitmap_get_nx(bm), mtmd_bitmap_get_ny(bm));

    mtmd_input_chunks *chunks = mtmd_input_chunks_init();
    mtmd_input_text txt{prompt.c_str(), prompt.size(), /*add_special*/ false, /*parse_special*/ true};
    const mtmd_bitmap *bms[1] = {bm};
    if (mtmd_tokenize(vc, chunks, &txt, bms, 1) != 0) { std::fprintf(stderr, "mtmd_tokenize failed\n"); return 1; }

    const int n_embd = llama_model_n_embd(model);
    FILE *cf = std::fopen((c.dir + "/chunks.txt").c_str(), "w");
    int k = 0;
    for (size_t i = 0; i < mtmd_input_chunks_size(chunks); ++i) {
        const mtmd_input_chunk *ch = mtmd_input_chunks_get(chunks, i);
        if (mtmd_input_chunk_get_type(ch) == MTMD_INPUT_CHUNK_TYPE_TEXT) {
            size_t n = 0;
            const llama_token *t = mtmd_input_chunk_get_tokens_text(ch, &n);
            std::fprintf(cf, "text");
            for (size_t j = 0; j < n; ++j) std::fprintf(cf, " %d", t[j]);
            std::fprintf(cf, "\n");
        } else {
            const mtmd_image_tokens *it = mtmd_input_chunk_get_tokens_image(ch);
            const size_t nt = mtmd_input_chunk_get_n_tokens(ch);
            if (mtmd_encode_chunk(vc, ch) != 0) { std::fprintf(stderr, "encode failed\n"); return 1; }
            const float *e = mtmd_get_output_embd(vc);
            std::ofstream o(c.dir + "/embd" + std::to_string(k) + ".f32", std::ios::binary);
            o.write((const char *)e, sizeof(float) * nt * (size_t)n_embd);
            std::fprintf(cf, "image %zu %d %zu %zu\n", nt, (int)mtmd_input_chunk_get_n_pos(ch),
                         (size_t)mtmd_image_tokens_get_nx(it), (size_t)mtmd_image_tokens_get_ny(it));
            ++k;
        }
    }
    std::fclose(cf);
    std::fclose(c.index);
    std::fprintf(stderr, "chunks %zu, images %d, saved %ld tensors\n", mtmd_input_chunks_size(chunks), k, c.saved);

    if (n_gen > 0) {
        llama_context_params cp = llama_context_default_params();
        cp.n_ctx = (uint32_t)(mtmd_helper_get_n_tokens(chunks) + n_gen + 64);
        cp.n_batch = cp.n_ubatch = 2048;
        cp.n_threads = cp.n_threads_batch = 8;
        if (const char *e = std::getenv("REF_FA")) cp.flash_attn_type = std::atoi(e) ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
        llama_context *ctx = llama_init_from_model(model, cp);
        if (!ctx) { std::fprintf(stderr, "context failed\n"); return 1; }
        llama_pos n_past = 0;
        if (mtmd_helper_eval_chunks(vc, ctx, chunks, 0, 0, (int32_t)cp.n_batch, true, &n_past) != 0) {
            std::fprintf(stderr, "eval failed\n");
            return 1;
        }
        const llama_vocab *voc = llama_model_get_vocab(model);
        const int nv = llama_vocab_n_tokens(voc);
        FILE *gf = std::fopen((c.dir + "/gen.ids").c_str(), "w");
        llama_batch b = llama_batch_init(1, 0, 1);
        for (int g = 0; g < n_gen; ++g) {
            const float *lg = llama_get_logits_ith(ctx, -1);
            int best = 0;
            for (int v = 1; v < nv; ++v) if (lg[v] > lg[best]) best = v;
            std::fprintf(gf, "%d ", best);
            std::fflush(gf);
            if (llama_vocab_is_eog(voc, best)) break;
            b.token[0] = best; b.pos[0] = n_past++; b.n_seq_id[0] = 1; b.seq_id[0][0] = 0; b.logits[0] = 1; b.n_tokens = 1;
            if (llama_decode(ctx, b)) { std::fprintf(stderr, "decode failed\n"); return 1; }
        }
        std::fprintf(gf, "\n");
        std::fclose(gf);
        llama_batch_free(b);
        llama_free(ctx);
    }
    mtmd_input_chunks_free(chunks);
    mtmd_bitmap_free(bm);
    mtmd_free(vc);
    llama_model_free(model);
    return 0;
}
