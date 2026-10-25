// Records the MoE expert selection (ffn_moe_topk, top-10 ids per token) of every layer for a fixed token sequence.
// Output: one JSON line per (layer, position). Statistics only; CPU, no logits.
#include "llama.h"
#include "ggml.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
static std::vector<long> ints(const std::string& s,const std::string& key){
    std::vector<long> v;auto p=s.find("\""+key+"\"");if(p==std::string::npos)return v;p=s.find('[',p);auto e=s.find(']',p);
    std::stringstream ss(s.substr(p+1,e-p-1));std::string x;while(std::getline(ss,x,','))if(x.find_first_of("0123456789")!=std::string::npos)v.push_back(std::stol(x));return v;}
struct State {FILE* out;int base;};
static bool capture(ggml_tensor* t,bool ask,void* user){
    if(std::strncmp(t->name,"ffn_moe_topk",12)!=0)return ask?false:true;
    if(ask)return true;
    auto* s=static_cast<State*>(user);int layer=std::atoi(t->name+13);
    const int top=int(t->ne[0]),n=int(t->ne[1]);const int32_t* d=static_cast<const int32_t*>(t->data);
    for(int i=0;i<n;++i){std::fprintf(s->out,"{\"layer\":%d,\"pos\":%d,\"experts\":[",layer,s->base+i);
        for(int j=0;j<top;++j)std::fprintf(s->out,"%s%d",j?",":"",d[i*(t->nb[1]/sizeof(int32_t))+j]);std::fprintf(s->out,"]}\n");}
    return true;
}
int main(int argc,char** argv){
    if(argc!=5){std::fprintf(stderr,"usage: %s MODEL INPUT.json OUT.jsonl THREADS\n",argv[0]);return 2;}
    std::ifstream in(argv[2]);std::stringstream buf;buf<<in.rdbuf();auto toks=ints(buf.str(),"tokens");
    State st{std::fopen(argv[3],"w"),0};
    llama_backend_init();auto mp=llama_model_default_params();mp.n_gpu_layers=0;
    llama_model* model=llama_model_load_from_file(argv[1],mp);if(!model)return 1;
    auto cp=llama_context_default_params();cp.n_ctx=4096;cp.n_batch=256;cp.n_ubatch=256;cp.n_seq_max=1;cp.n_threads=cp.n_threads_batch=std::atoi(argv[4]);
    cp.cb_eval=capture;cp.cb_eval_user_data=&st;cp.flash_attn_type=LLAMA_FLASH_ATTN_TYPE_DISABLED;
    llama_context* ctx=llama_init_from_model(model,cp);if(!ctx)return 1;
    const int n=int(toks.size());llama_batch batch=llama_batch_init(256,0,1);
    for(int start=0;start<n;start+=256){int end=std::min(n,start+256);batch.n_tokens=0;st.base=start;
        for(int p=start;p<end;++p){int i=batch.n_tokens++;batch.token[i]=llama_token(toks[p]);batch.pos[i]=p;batch.n_seq_id[i]=1;batch.seq_id[i][0]=0;batch.logits[i]=p==end-1;}
        if(llama_decode(ctx,batch)!=0){std::fprintf(stderr,"decode failed\n");return 1;}}
    std::fclose(st.out);return 0;
}
