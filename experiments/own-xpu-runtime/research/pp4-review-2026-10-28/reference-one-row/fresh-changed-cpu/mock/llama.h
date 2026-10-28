#pragma once
#include <cassert>
#include <cstdlib>
#include <vector>
using llama_token=int;
enum ggml_type{GGML_TYPE_BF16,GGML_TYPE_F32};enum{LLAMA_FLASH_ATTN_TYPE_DISABLED};
struct llama_model{};struct llama_vocab{};
struct llama_model_params{int n_gpu_layers;};
struct llama_context_params{int n_ctx,n_batch,n_ubatch,n_seq_max,n_threads,n_threads_batch,type_k,type_v,flash_attn_type;bool no_perf;};
struct llama_context{int next=0;std::vector<float>logits;};
struct llama_batch{int n_tokens;int*token;int*pos;int*n_seq_id;int**seq_id;signed char*logits;};
inline int loads=0,contexts=0,frees=0,model_frees=0;
inline void llama_backend_init(){}inline void llama_backend_free(){assert(loads==1&&contexts==2&&frees==2&&model_frees==1);}
inline llama_model_params llama_model_default_params(){return {};}
inline llama_model*llama_model_load_from_file(const char*,llama_model_params p){assert(p.n_gpu_layers==0&&loads++==0);return new llama_model;}
inline llama_context_params llama_context_default_params(){return {};}
inline llama_context*llama_init_from_model(llama_model*,llama_context_params p){assert(p.n_ctx==4096&&p.n_batch==512&&p.n_ubatch==512&&p.n_seq_max==1&&p.n_threads==8&&p.n_threads_batch==8&&p.type_k==GGML_TYPE_F32&&p.type_v==GGML_TYPE_F32);++contexts;return new llama_context;}
inline const llama_vocab*llama_model_get_vocab(llama_model*){static llama_vocab v;return &v;}
inline int llama_vocab_n_tokens(const llama_vocab*){return 32;}
inline llama_batch llama_batch_init(int n,int,int){llama_batch b{};b.token=new int[n];b.pos=new int[n];b.n_seq_id=new int[n];b.seq_id=new int*[n];b.logits=new signed char[n];for(int i=0;i<n;++i)b.seq_id[i]=new int[1];return b;}
inline int llama_decode(llama_context*c,llama_batch b){c->logits.resize(b.n_tokens*32);for(int i=0;i<b.n_tokens;++i){assert(b.pos[i]==c->next++&&b.n_seq_id[i]==1&&b.seq_id[i][0]==0);for(int v=0;v<32;++v)c->logits[i*32+v]=v==(b.token[i]+1)%32?2.f:float(-v);}return 0;}
inline float*llama_get_logits_ith(llama_context*c,int i){return c->logits.data()+i*32;}
inline void llama_batch_free(llama_batch b){for(int i=0;i<512;++i)delete[]b.seq_id[i];delete[]b.token;delete[]b.pos;delete[]b.n_seq_id;delete[]b.seq_id;delete[]b.logits;}
inline void llama_free(llama_context*c){++frees;delete c;}inline void llama_model_free(llama_model*m){++model_frees;delete m;}
