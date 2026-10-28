// Own-runtime reference tool: teacher-forced logits for a fixed token sequence (CPU only).
// Usage: exact-logits MODEL INPUT.json OUT_DIR THREADS
// INPUT.json: {"tokens":[...], "score_from": k, "full_rows": [positions...]}
//   scores every position p >= score_from-1 (the prediction of token p+1); writes rows.jsonl and,
//   for positions listed in full_rows, the complete F32 logit row to logits-<p>.f32.
#include "llama.h"
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
#include <filesystem>
// Outer lifecycle extension only. Each call creates/frees its own ctx and batch.
static int score_case(llama_model* model,const char* input,const std::string& out,int threads){
    std::ifstream in(input); std::stringstream buf; buf << in.rdbuf(); std::string js = buf.str();
    auto toks = ints(js, "tokens"); long score_from = scalar(js, "score_from", 1); auto fr = ints(js, "full_rows");
    std::set<long> full(fr.begin(), fr.end());
    auto cp = llama_context_default_params();
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
    fclose(rows); llama_batch_free(batch); llama_free(ctx);
    return 0;
}
int main(int argc,char**argv){
    if(argc!=5){fprintf(stderr,"usage: %s MODEL TWELVE_INPUT_PATHS.txt OUT_DIR THREADS\n",argv[0]);return 2;}
    std::vector<std::string> inputs;std::ifstream manifest(argv[2]);std::string path;
    if(!manifest){fprintf(stderr,"missing suite input list\n");return 2;}
    while(std::getline(manifest,path)){
        if(path.empty()||!std::filesystem::path(path).is_absolute()||
           std::find(inputs.begin(),inputs.end(),path)!=inputs.end())return 2;
        inputs.push_back(path);
    }
    if(inputs.size()!=12||atoi(argv[4])!=8)return 2;
    const std::string root=argv[3];
    if(!std::filesystem::is_directory(root))return 2;
    llama_backend_init();
    auto mp=llama_model_default_params();mp.n_gpu_layers=0;
    llama_model* model=llama_model_load_from_file(argv[1],mp);
    if(!model){fprintf(stderr,"load failed\n");return 1;}
    int completed=0,rc=0;
    for(size_t i=0;i<inputs.size();++i){
        char suffix[32];std::snprintf(suffix,sizeof suffix,"/case-%02zu",i);
        const std::string out=root+suffix;
        if(!std::filesystem::create_directory(out)){rc=2;break;}
        rc=score_case(model,inputs[i].c_str(),out,8);if(rc)break;
        ++completed;
    }
    llama_model_free(model);llama_backend_free();
    std::ofstream lifecycle(root+"/lifecycle.json");
    lifecycle<<"{\"loaded_models\":1,\"completed_fresh_contexts\":"<<completed<<",\"returncode\":"<<rc<<"}\n";
    if(!lifecycle)return 1;
    return rc;
}
