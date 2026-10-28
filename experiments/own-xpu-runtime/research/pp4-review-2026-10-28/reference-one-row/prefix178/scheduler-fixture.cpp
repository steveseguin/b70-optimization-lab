#define main prefix178_tool_main
#include "exact-logits-prefix178.cpp"
#undef main
#include "ggml-cpu.h"
#include <cassert>
#include <filesystem>
struct Result {std::vector<char> weights;std::set<std::string> seen;bool failed=false;std::set<int> layer_seen;std::vector<char> layer_output;};
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
 CombinedCapture capture;capture.layers.out=out;capture.routers.out=out;capture.layers.batch_tokens=178;capture.routers.batch_tokens=178;capture.layers.output_positions={177};capture.routers.output_positions={177};capture.routers.position=177;
 auto*li=ggml_new_tensor_3d(ctx,GGML_TYPE_F32,2560,4,rows);ggml_set_input(li);auto*lo=ggml_add(ctx,li,li);char lname[64];std::snprintf(lname,64,"l_last-%d",layer);ggml_set_name(lo,lname);ggml_set_output(lo);ggml_build_forward_expand(g,lo);
 if(observe)ggml_backend_sched_set_eval_callback(sched,capture_both,&capture);
 assert(ggml_backend_sched_alloc_graph(sched,g));
 std::vector<float> xv(size_t(2560)*rows),wv(size_t(2560)*512);
 for(size_t i=0;i<xv.size();++i)xv[i]=float(int(i%31)-15)/32.f;
 for(size_t i=0;i<wv.size();++i)wv[i]=float(int(i%43)-21)/64.f;
 std::vector<float> lv(size_t(10240)*rows);for(size_t i=0;i<lv.size();++i)lv[i]=float(int(i%127)-63)/64.f;ggml_backend_tensor_set(li,lv.data(),0,lv.size()*4);
 ggml_backend_tensor_set(x,xv.data(),0,xv.size()*4);ggml_backend_tensor_set(w,wv.data(),0,wv.size()*4);
 assert(ggml_backend_sched_graph_compute(sched,g)==GGML_STATUS_SUCCESS);
 ggml_backend_sched_synchronize(sched);
 Result result;result.weights.resize(size_t(rows)*40);
 ggml_backend_tensor_get(norm,result.weights.data(),0,result.weights.size());
 result.layer_output.resize(size_t(rows)*40960);ggml_backend_tensor_get(lo,result.layer_output.data(),0,result.layer_output.size());result.layer_seen=capture.layers.seen;result.seen=capture.routers.seen;result.failed=capture.routers.failed||capture.layers.failed;
 std::ofstream f(out+"/graph-output.f32",std::ios::binary);f.write(result.weights.data(),result.weights.size());assert(f);
 ggml_backend_sched_free(sched);ggml_backend_free(backend);ggml_free(ctx);return result;
}
int main(int argc,char**argv){assert(argc==2);assert(std::filesystem::create_directory(argv[1]));std::string root=argv[1];
 for(int layer:{0,47}){
  int rows=layer==0?178:1;auto stem=root+"/layer"+std::to_string(layer);
  auto off=run(stem+"-off",layer,rows,false);auto on=run(stem+"-on",layer,rows,true);
  assert(off.weights==on.weights);assert(off.layer_output==on.layer_output);assert(on.layer_seen==std::set<int>{layer});assert(!on.failed);
  // Fixture intentionally covers only one layer per graph. Production remains 192 observations.
  std::set<std::string> expected;for(const char*field:{"ffn_moe_logits","ffn_moe_probs","ffn_moe_topk","ffn_moe_weights_norm"})expected.insert(std::to_string(layer)+":"+field);
  if(on.seen!=expected){std::fprintf(stderr,"Missing actual scheduler observations, layer %d:\n",layer);for(auto&s:on.seen)std::fprintf(stderr," observed %s\n",s.c_str());return 3;}
  for(auto field:{"input.f32","logits.f32","probabilities.f32","ids.i32","weights.f32"}){
   char prefix[64];std::snprintf(prefix,sizeof prefix,"/layer-%02d-",layer);assert(std::filesystem::is_regular_file(stem+"-on"+prefix+field));
  }
 }
 std::puts("PASS actual scheduler callback nodes, strided top-k, final crop, OFF/ON graph-output byte equality (two synthetic graphs only)");
}
