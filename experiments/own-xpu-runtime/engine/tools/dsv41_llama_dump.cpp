// Out-of-tree reference dump: run the pinned llama.cpp CPU build over a token
// list and write every named graph tensor we ask for (raw f32) to a file.
// Record: u32 name_len, name, i64 ne[4], u64 n_f32, f32 data.
// Built against ~/src/llama.cpp-dsv41-20261108/build-cpu; llama.cpp sources untouched.
//
//   L=~/src/llama.cpp-dsv41-20261108
//   g++ -O2 -std=c++17 tools/dsv41_llama_dump.cpp -I$L/include -I$L/common -I$L/ggml/include \
//     -I$L/vendor -I$L/src -L$L/build-cpu/bin -lllama-common -lllama -lggml -lggml-base -lggml-cpu \
//     -o llama_dump
//   LD_LIBRARY_PATH=$L/build-cpu/bin DUMP_IDS=ids.txt DUMP_OUT=llama_dump.bin \
//     DUMP_NAMES=hc_init,engram_out,hc_pre,hc_post,hc_comb,hc_attn_pre,attn_norm,qr_norm,q,kv,comp_latent,attn_derope,attn_wo_a,attn_out,hc_attn_post,hc_ffn_pre,ffn_norm,ffn_moe_logits,ffn_moe_out,ffn_shexp,ffn_out,l_out,hc_out,result_norm,result_output \
//     ./llama_dump -m <shard 1> -c 4096 -fa on -t 16 -b 512 -ub 128
// CPU only (about 30 s for 36 tokens, 2.4 GB of output). Compare with
// tools/dsv41_llama_diff.py against cpu_run_v41's OWN_PDUMP output.
#include "arg.h"
#include "common.h"
#include "log.h"
#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"
#include <clocale>
#include <cstdio>
#include <fstream>
#include <set>
#include <string>
#include <vector>

struct Dump {
    FILE *f = nullptr;
    std::set<std::string> want;
    size_t n = 0;
};
static std::string base_name(const char *nm) {
    std::string s(nm);
    size_t p = s.rfind('-');
    if (p != std::string::npos && p + 1 < s.size() && isdigit((unsigned char)s[p + 1])) s.resize(p);
    return s;
}
static bool cb(struct ggml_tensor *t, bool ask, void *ud) {
    Dump *d = (Dump *)ud;
    bool match = d->want.count(base_name(t->name)) > 0;
    if (ask) return match;
    if (!match) return true;
    if (t->type != GGML_TYPE_F32 && t->type != GGML_TYPE_F16) return true;
    size_t nb = ggml_nbytes(t);
    std::vector<uint8_t> buf(nb);
    ggml_backend_tensor_get(t, buf.data(), 0, nb);
    size_t ne = ggml_nelements(t);
    std::vector<float> v(ne);
    if (t->type == GGML_TYPE_F32) memcpy(v.data(), buf.data(), ne * 4);
    else ggml_fp16_to_fp32_row((const ggml_fp16_t *)buf.data(), v.data(), ne);
    uint32_t nl = (uint32_t)strlen(t->name);
    fwrite(&nl, 4, 1, d->f);
    fwrite(t->name, 1, nl, d->f);
    int64_t dims[4] = {t->ne[0], t->ne[1], t->ne[2], t->ne[3]};
    fwrite(dims, 8, 4, d->f);
    uint64_t n64 = ne;
    fwrite(&n64, 8, 1, d->f);
    fwrite(v.data(), 4, ne, d->f);
    d->n++;
    return true;
}

int main(int argc, char **argv) {
    std::setlocale(LC_NUMERIC, "C");
    Dump d;
    const char *ids_path = getenv("DUMP_IDS"), *out_path = getenv("DUMP_OUT"), *names = getenv("DUMP_NAMES");
    if (!ids_path || !out_path || !names) { fprintf(stderr, "set DUMP_IDS DUMP_OUT DUMP_NAMES\n"); return 2; }
    {
        std::string s(names), cur;
        for (char c : s) { if (c == ',') { d.want.insert(cur); cur.clear(); } else cur += c; }
        if (!cur.empty()) d.want.insert(cur);
    }
    std::vector<llama_token> tokens;
    { std::ifstream f(ids_path); long long v; while (f >> v) tokens.push_back((llama_token)v); }
    d.f = fopen(out_path, "wb");
    common_params params;
    common_init();
    if (!common_params_parse(argc, argv, params, LLAMA_EXAMPLE_COMMON)) return 1;
    llama_backend_init();
    params.cb_eval = cb;
    params.cb_eval_user_data = &d;
    params.warmup = false;
    auto init = common_init_from_params(params);
    auto *ctx = init->context();
    if (!init->model() || !ctx) { fprintf(stderr, "init failed\n"); return 1; }
    fprintf(stderr, "tokens: %zu\n", tokens.size());
    common_batch batch = common_batch_get_one(ctx, tokens);
    if (llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch.get())) { fprintf(stderr, "eval failed\n"); return 1; }
    fclose(d.f);
    fprintf(stderr, "dumped %zu tensors\n", d.n);
    llama_backend_free();
    return 0;
}
