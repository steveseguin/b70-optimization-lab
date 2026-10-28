// SOURCE ONLY: actual CPU backend/scheduler, no model, no device.
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <set>
#include <string>
#include <vector>
#include <cmath>
#include "router-capture.hpp"
struct Result {std::vector<char> weights;std::set<std::string> seen;bool failed=false;};
static Result run(const std::string&out,int layer,int rows,bool observe){
 assert(std::filesystem::create_directory(out));
 auto*backend=ggml_backend_cpu_init();assert(backend);ggml_backend_cpu_set_n_threads(backend,2);
 auto*sched=ggml_backend_sched_new(&backend,nullptr,1,2048,false,true);assert(sched);
 ggml_init_params ip{4*1024*1024,nullptr,true};auto*ctx=ggml_init(ip);assert(ctx);
 auto*x=ggml_new_tensor_2d(ctx,GGML_TYPE_F32,2560,rows);
 auto*w=ggml_new_tensor_2d(ctx,GGML_TYPE_F32,2560,512);
 ggml_set_input(x);ggml_set_input(w);
 auto*logits=ggml_mul_mat(ctx,w,x);auto*prob=ggml_soft_max(ctx,logits);
 auto*ids=ggml_argsort_top_k(ctx,prob,10);
 auto*p3=ggml_reshape_3d(ctx,prob,1,512,rows);
 auto*selected=ggml_get_rows(ctx,p3,ids);auto*flat=ggml_reshape_2d(ctx,selected,10,rows);
 auto*sum=ggml_sum_rows(ctx,flat);auto*clamp=ggml_clamp(ctx,sum,6.103515625e-5f,INFINITY);
 auto*norm=ggml_div(ctx,flat,clamp);
 for(auto pair:{std::pair{logits,"ffn_moe_logits"},std::pair{prob,"ffn_moe_probs"},std::pair{ids,"ffn_moe_topk"},std::pair{norm,"ffn_moe_weights_norm"}}){
  char name[80];std::snprintf(name,sizeof name,"%s-%d",pair.second,layer);ggml_set_name(pair.first,name);
 }
 assert(ids->op==GGML_OP_VIEW&&ids->nb[1]==2048);
 ggml_set_output(norm);auto*g=ggml_new_graph_custom(ctx,2048,false);ggml_build_forward_expand(g,norm);
 RouterCapture capture;capture.out=out;capture.batch_tokens=244;capture.output_positions={243};
 if(observe)ggml_backend_sched_set_eval_callback(sched,capture_router,&capture);
 assert(ggml_backend_sched_alloc_graph(sched,g));
 std::vector<float> xv(size_t(2560)*rows),wv(size_t(2560)*512);
 for(size_t i=0;i<xv.size();++i)xv[i]=float(int(i%31)-15)/32.f;
 for(size_t i=0;i<wv.size();++i)wv[i]=float(int(i%43)-21)/64.f;
 ggml_backend_tensor_set(x,xv.data(),0,xv.size()*4);ggml_backend_tensor_set(w,wv.data(),0,wv.size()*4);
 assert(ggml_backend_sched_graph_compute(sched,g)==GGML_STATUS_SUCCESS);
 ggml_backend_sched_synchronize(sched);
 Result result;result.weights.resize(size_t(rows)*40);
 ggml_backend_tensor_get(norm,result.weights.data(),0,result.weights.size());
 result.seen=capture.seen;result.failed=capture.failed;
 std::ofstream f(out+"/graph-output.f32",std::ios::binary);f.write(result.weights.data(),result.weights.size());assert(f);
 ggml_backend_sched_free(sched);ggml_backend_free(backend);ggml_free(ctx);return result;
}
int main(int argc,char**argv){assert(argc==2);assert(std::filesystem::create_directory(argv[1]));std::string root=argv[1];
 for(int layer:{0,47}){
  int rows=layer==0?244:1;auto stem=root+"/layer"+std::to_string(layer);
  auto off=run(stem+"-off",layer,rows,false);auto on=run(stem+"-on",layer,rows,true);
  assert(off.weights==on.weights);assert(!on.failed);
  // Fixture intentionally covers only one layer per graph. Production remains 192 observations.
  std::set<std::string> expected;for(const char*field:{"ffn_moe_logits","ffn_moe_probs","ffn_moe_topk","ffn_moe_weights_norm"})expected.insert(std::to_string(layer)+":"+field);
  if(on.seen!=expected){std::fprintf(stderr,"Missing actual scheduler observations, layer %d:\n",layer);for(auto&s:on.seen)std::fprintf(stderr," observed %s\n",s.c_str());return 3;}
  for(auto field:{"input.f32","logits.f32","probabilities.f32","ids.i32","weights.f32"}){
   char prefix[64];std::snprintf(prefix,sizeof prefix,"/layer-%02d-",layer);assert(std::filesystem::is_regular_file(stem+"-on"+prefix+field));
  }
 }
 std::puts("PASS actual scheduler callback nodes, strided top-k, final crop, OFF/ON graph-output byte equality (two synthetic graphs only)");
}
