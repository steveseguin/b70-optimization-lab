#include "dflash-target-trace.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>

static void write_control(const std::filesystem::path & dir, int ordinal, char prompt_hex,
        const char * target, const char * draft, const char * commit, const char * patch) {
    const std::string prompt_sha(64, prompt_hex);
    std::ofstream ctl(dir / "next-request.json");
    ctl << "{\"schema\":\"qwen27_dflash_native_request_control_v1\","
           "\"ordinal\":" << ordinal << ",\"split\":\"train\",\"prompt_sha256\":\"" << prompt_sha <<
           "\",\"request_id\":\"native-smoke-" << ordinal << "\",\"max_generated_tokens\":2,"
           "\"target_model_sha256\":\"" << target << "\",\"draft_model_sha256\":\"" << draft <<
           "\",\"runtime_commit\":\"" << commit << "\",\"runtime_dirty_patch_sha256\":\"" << patch << "\"}\n";
}

int main(int argc, char ** argv) {
    if (argc != 6) {
        std::cerr << "usage: smoke DIR TARGET_SHA DRAFT_SHA COMMIT PATCH_SHA\n";
        return 2;
    }
    namespace fs = std::filesystem;
    fs::path dir = argv[1];
    fs::create_directories(dir);
    write_control(dir,0,'4',argv[2],argv[3],argv[4],argv[5]);

    dflash_target_trace_config cfg;
    cfg.capture_dir=dir.string(); cfg.target_model_sha256=argv[2]; cfg.draft_model_sha256=argv[3];
    cfg.runtime_commit=argv[4]; cfg.runtime_dirty_patch_sha256=argv[5]; cfg.target_layer_ids={2,17,32,47,62};
    cfg.n_seq=1; cfg.n_max=0; cfg.n_min=0; cfg.p_min=0; cfg.hidden_size=5120; cfg.draft_cache_f16=true;
    cfg.parallel=1; cfg.ctx_checkpoints=0; cfg.reasoning=0;
    auto trace=dflash_target_trace::create(cfg);
    std::vector<float> features(4ull*5*5120);
    for(size_t i=0;i<features.size();++i)features[i]=(float(i%997)-498.0f)/997.0f;
    llama_token prompt_tokens[2]={101,102}; llama_pos prompt_pos[2]={0,1};
    if(!trace->process(0,prompt_tokens,prompt_pos,features.data(),2)||!trace->begin(0,{101,102}))return 3;
    llama_token generated[2]={103,104}; llama_pos generated_pos[2]={2,3};
    if(!trace->process(0,generated,generated_pos,features.data()+2ull*5*5120,2))return 4;
    trace->end(0,true);
    if(!fs::is_regular_file(dir/"request-000000.qdft")||!fs::is_regular_file(dir/"request-000000.json"))return 5;
    // The same native trace object must capture subsequent sequential requests;
    // callback_on_release calls end(false) once more after successful publish.
    trace->end(0,false);
    write_control(dir,1,'5',argv[2],argv[3],argv[4],argv[5]);
    if(!trace->process(0,prompt_tokens,prompt_pos,features.data(),2)||!trace->begin(0,{101,102}))return 6;
    if(!trace->process(0,generated,generated_pos,features.data()+2ull*5*5120,2))return 7;
    trace->end(0,true);
    if(!fs::is_regular_file(dir/"request-000001.qdft")||!fs::is_regular_file(dir/"request-000001.json"))return 8;
    return 0;
}
