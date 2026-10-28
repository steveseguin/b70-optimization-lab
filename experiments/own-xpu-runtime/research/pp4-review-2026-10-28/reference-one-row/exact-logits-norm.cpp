// Own-runtime reference tool: teacher-forced logits for a fixed token sequence (CPU only).
// Usage: exact-logits MODEL INPUT.json OUT_DIR THREADS
// INPUT.json: {"tokens":[...], "score_from": k, "full_rows": [positions...]}
//   scores every position p >= score_from-1 (the prediction of token p+1); writes rows.jsonl and,
//   for positions listed in full_rows, the complete F32 logit row to logits-<p>.f32.
#include "llama.h"
#include "ggml-backend.h"
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>
#include <set>
static std::vector<long> ints(const std::string& s, const std::string& key) {
    std::vector<long> v; auto p = s.find("\"" + key + "\""); if (p == std::string::npos) return v;
    p = s.find('[', p); auto q = s.find(']', p); std::stringstream ss(s.substr(p + 1, q - p - 1)); std::string x;
    while (std::getline(ss, x, ',')) { if (x.find_first_of("0123456789") != std::string::npos) v.push_back(std::stol(x)); }
    return v;
}
static long scalar(const std::string& s, const std::string& key, long def) {
    auto p = s.find("\"" + key + "\""); if (p == std::string::npos) return def; p = s.find(':', p); return std::stol(s.substr(p + 1));
}

struct NormCapture {
    std::string out; int position=243,batch_start=0,batch_tokens=0;
    bool seen=false,failed=false;
};
static bool capture_norm(ggml_tensor * t,bool ask,void * opaque){
    auto &c=*static_cast<NormCapture*>(opaque);
    bool named=std::strcmp(t->name,"hc_norm-0")==0 && c.position>=c.batch_start && c.position<c.batch_start+c.batch_tokens;
    if(ask)return named&&!c.seen;
    if(!named)return true;
    if(c.seen){c.failed=true;return true;} // never cancel graph evaluation
    c.seen=true;
    auto bad=[&]{c.failed=true;return true;};
    auto *m=t->src[0];auto *r=m?m->src[0]:nullptr;auto *g=m?m->src[1]:nullptr;auto *x=r?r->src[0]:nullptr;
    auto f32=[](ggml_tensor*q){return q&&q->type==GGML_TYPE_F32&&q->nb[0]==4;};
    if(t->op!=GGML_OP_RESHAPE||!m||m->op!=GGML_OP_MUL||!r||r->op!=GGML_OP_RMS_NORM||
       !f32(t)||!f32(x)||!f32(g)||t->ne[0]!=10240||t->ne[1]!=c.batch_tokens||t->ne[2]!=1||t->ne[3]!=1||
       x->ne[0]!=2560||x->ne[1]!=4||x->ne[2]!=c.batch_tokens||x->ne[3]!=1||
       g->ne[0]!=2560||g->ne[1]!=4||g->ne[2]!=1||g->ne[3]!=1)return bad();
    float eps;std::memcpy(&eps,r->op_params,4);if(eps!=1e-6f)return bad();
    const int row=c.position-c.batch_start;
    std::vector<float> input(10240),gain(10240),output(10240);
    for(int stream=0;stream<4;++stream){
      ggml_backend_tensor_get(x,input.data()+stream*2560,size_t(row)*x->nb[2]+stream*x->nb[1],10240);
      ggml_backend_tensor_get(g,gain.data()+stream*2560,stream*g->nb[1],10240);
    }
    ggml_backend_tensor_get(t,output.data(),size_t(row)*t->nb[1],40960);
    auto save=[&](const char*name,const std::vector<float>&v){std::ofstream f(c.out+name,std::ios::binary);f.write((const char*)v.data(),40960);return bool(f);};
    if(!save("/hc-a-input.f32",input)||!save("/hc-a-gain.f32",gain)||!save("/hc-a-output.f32",output))return bad();
    std::ofstream meta(c.out+"/norm-capture.json");
    meta<<"{\"position\":"<<c.position<<",\"dtype\":\"F32\",\"shape\":[4,2560],\"bytes_each\":40960,\"epsilon\":1e-6,\"chain\":\"RESHAPE(MUL(RMS_NORM(input),gain))\",\"occurrence\":1}";
    if(!meta)return bad();
    return true;
}

int main(int argc, char** argv) {
    if (argc != 5) { fprintf(stderr, "usage: %s MODEL INPUT.json OUT_DIR THREADS\n", argv[0]); return 2; }
    std::ifstream in(argv[2]); std::stringstream buf; buf << in.rdbuf(); std::string js = buf.str();
    auto toks = ints(js, "tokens"); long score_from = scalar(js, "score_from", 1); auto fr = ints(js, "full_rows");
    std::set<long> full(fr.begin(), fr.end());
    std::string out = argv[3]; int threads = atoi(argv[4]);
    llama_backend_init();
    auto mp = llama_model_default_params(); mp.n_gpu_layers = 0;
    llama_model* model = llama_model_load_from_file(argv[1], mp); if (!model) { fprintf(stderr, "load failed\n"); return 1; }
    NormCapture capture;capture.out=out;
    const bool capture_enabled=getenv("EXACT_CAPTURE_NORM")&&std::string(getenv("EXACT_CAPTURE_NORM"))=="1";
    auto cp = llama_context_default_params();
    if(capture_enabled){cp.cb_eval=capture_norm;cp.cb_eval_user_data=&capture;}
    cp.n_ctx = 4096; cp.n_batch = 512; cp.n_ubatch = 512; cp.n_seq_max = 1; cp.n_threads = threads; cp.n_threads_batch = threads;
    { const char* kv=getenv("EXACT_KV"); ggml_type t=(kv&&std::string(kv)=="bf16")?GGML_TYPE_BF16:GGML_TYPE_F32; cp.type_k=t; cp.type_v=t; fprintf(stderr,"kv type %s\n", t==GGML_TYPE_BF16?"bf16":"f32"); } cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED; cp.no_perf = true;
    llama_context* ctx = llama_init_from_model(model, cp); if (!ctx) { fprintf(stderr, "context failed\n"); return 1; }
    const int nv = llama_vocab_n_tokens(llama_model_get_vocab(model));
    const int n = (int) toks.size(); if (n < 2 || n > 4096) { fprintf(stderr, "bad token count\n"); return 2; }
    FILE* rows = fopen((out + "/rows.jsonl").c_str(), "w");
    llama_batch batch = llama_batch_init(512, 0, 1);
    for (int start = 0; start < n; start += 256) {
        int end = std::min(n, start + 256); batch.n_tokens = 0;
        for (int p = start; p < end; ++p) {
            int i = batch.n_tokens++; batch.token[i] = (llama_token) toks[p]; batch.pos[i] = p; batch.n_seq_id[i] = 1; batch.seq_id[i][0] = 0;
            batch.logits[i] = (p >= score_from - 1 && p < n) ? 1 : 0;
        }
        capture.batch_start=start;capture.batch_tokens=end-start;
        if (llama_decode(ctx, batch) != 0) { fprintf(stderr, "decode failed at %d\n", start); return 1; }
        for (int p = start; p < end; ++p) {
            if (p < score_from - 1) continue;
            const float* lg = llama_get_logits_ith(ctx, p - start);
            double mx = -1e300; int arg = 0; for (int v = 0; v < nv; ++v) if (lg[v] > mx) { mx = lg[v]; arg = v; }
            double z = 0; for (int v = 0; v < nv; ++v) z += std::exp((double) lg[v] - mx); double lz = mx + std::log(z);
            std::vector<int> idx(nv); for (int v = 0; v < nv; ++v) idx[v] = v;
            std::partial_sort(idx.begin(), idx.begin() + 20, idx.end(), [&](int a, int b) { return lg[a] > lg[b] || (lg[a] == lg[b] && a < b); });
            fprintf(rows, "{\"position\":%d,\"argmax\":%d,\"top\":[", p, arg);
            for (int k = 0; k < 20; ++k) fprintf(rows, "%s[%d,%.9g,%.9g]", k ? "," : "", idx[k], (double) lg[idx[k]], (double) lg[idx[k]] - lz);
            fprintf(rows, "]");
            if (p + 1 < n) fprintf(rows, ",\"next\":%ld,\"next_logit\":%.9g,\"next_logprob\":%.9g", toks[p + 1], (double) lg[toks[p + 1]], (double) lg[toks[p + 1]] - lz);
            fprintf(rows, "}\n");
            if (full.count(p)) { FILE* f = fopen((out + "/logits-" + std::to_string(p) + ".f32").c_str(), "wb"); fwrite(lg, 4, nv, f); fclose(f); }
        }
        fflush(rows);
    }
    fclose(rows); llama_batch_free(batch); llama_free(ctx); llama_model_free(model); llama_backend_free();
    if(capture_enabled&&(!capture.seen||capture.failed)){fprintf(stderr,"norm capture failed\n");return 3;}
    return 0;
}
