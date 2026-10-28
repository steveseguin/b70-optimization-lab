// Source-only actual CPU ggml scheduler/layout fixture. Synthetic arithmetic, no model.
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <set>
#include <string>
#include <vector>
#include "l4-capture.hpp"
struct Observed{L4Capture capture;int observations=0;};
static bool callback(ggml_tensor*t,bool ask,void*p){auto&o=*static_cast<Observed*>(p);if(!ask)++o.observations;return capture_l4(t,ask,&o.capture);}
struct Result{std::vector<std::vector<char>>outputs;bool complete=false,failed=false;int observations=0;};
static Result run(const std::string&out,int mode,int qheads){
 assert(std::filesystem::create_directory(out));auto*b=ggml_backend_cpu_init();assert(b);ggml_backend_cpu_set_n_threads(b,2);
 auto*s=ggml_backend_sched_new(&b,nullptr,1,2048,false,true);assert(s);
 ggml_init_params ip{4*1024*1024,nullptr,true};auto*c=ggml_init(ip);assert(c);
 auto*g=ggml_new_graph_custom(c,2048,false);std::vector<ggml_tensor*>inputs,roots;
 auto input=[&](int64_t a,int64_t e=1,int64_t f=1,int64_t h=1){auto*t=ggml_new_tensor_4d(c,GGML_TYPE_F32,a,e,f,h);ggml_set_input(t);inputs.push_back(t);return t;};
 auto keep=[&](ggml_tensor*t,const char*name){ggml_set_name(t,name);ggml_set_output(t);ggml_build_forward_expand(g,t);roots.push_back(t);return t;};
 // HC uses the actual RMS_NORM -> MUL -> RESHAPE chain, twice under duplicate names.
 auto hc=[&](){auto*x=input(2560,4,244);auto*gain=input(2560,4);auto*n=ggml_mul(c,ggml_rms_norm(c,x,1e-6f),gain);
  keep(ggml_reshape_2d(c,n,10240,244),"hc_norm-4");
  auto*v=ggml_view_2d(c,n,2560,244,n->nb[2],0);return keep(ggml_scale(c,ggml_cont(c,v),0.25f),"hc_mixed-4");};
 hc();
 // Skinny K=1 projections deliberately test callback op/layout, not production GEMV math.
 auto*token=input(1,244);
 auto project=[&](int width){return ggml_mul_mat(c,input(1,width),token);};
 keep(ggml_reshape_3d(c,input(10240,244),10240,244,1),"linear_attn_qkv_mixed-4");
 keep(project(6144),"z-4");
 auto*alpha=keep(ggml_reshape_3d(c,project(48),48,244,1),"alpha-4");
 auto*beta=keep(ggml_reshape_4d(c,project(48),1,48,244,1),"beta-4");
 keep(ggml_sigmoid(c,beta),"beta_sigmoid-4");
 keep(ggml_mul(c,alpha,input(48,1)),"gate-4");
 keep(ggml_reshape_3d(c,input(3*10240),3,10240,1),"conv_state_at-4");
 keep(ggml_reshape_4d(c,input(128*128*48),128,128,48,1),"state_predelta-4");
 auto*conv=keep(ggml_ssm_conv(c,input(247,10240,1),input(4,10240)),"conv_output_raw-4");
 auto*silu=keep(ggml_silu(c,conv),"conv_output_silu-4");
 auto*rawq=ggml_view_4d(c,silu,128,16,244,1,128*4,10240*4,10240*244*4,0);
 auto*rawk=ggml_view_4d(c,silu,128,16,244,1,128*4,10240*4,10240*244*4,2048*4);
 auto*v=ggml_view_4d(c,silu,128,48,244,1,128*4,10240*4,10240*244*4,4096*4);
 auto normq=[&](ggml_tensor*t){auto*n=ggml_scale(c,ggml_rms_norm(c,t,1e-6f/128),1/std::sqrt(128.f));if(qheads==48)n=ggml_repeat_4d(c,n,128,48,244,1);return n;};
 keep(normq(rawq),"q_conv_predelta-4");keep(normq(rawk),"k_conv_predelta-4");keep(v,"v_conv_predelta-4");
 // Recurrence is a synthetic supplied tensor: this fixture checks callback/layout, not GDN math.
 auto*recurrent=input(128,48,244,1);auto*normalized=keep(ggml_rms_norm(c,recurrent,1e-6f),"norm-4");
 keep(ggml_reshape_3d(c,ggml_mul(c,normalized,ggml_sigmoid(c,input(128,48,244))),6144,244,1),"final_output-4");
 keep(project(2560),"linear_attn_out-4");hc();
 Observed o;o.capture.out=out;o.capture.batch_tokens=mode==2?245:244;
 if(mode)ggml_backend_sched_set_eval_callback(s,callback,&o);
 // Pure ASK on REAL descriptors before allocation must not copy/read/mutate observer state.
 if(mode==1)for(auto*t:roots){for(int i=0;i<3;++i)assert(capture_l4(t,true,&o.capture));assert(o.capture.seen.empty());}
 assert(ggml_backend_sched_alloc_graph(s,g));
 for(size_t k=0;k<inputs.size();++k){auto*t=inputs[k];std::vector<float>v(size_t(ggml_nelements(t)));for(size_t i=0;i<v.size();++i)v[i]=float(int((i+k)%29)-14)/64.f;ggml_backend_tensor_set(t,v.data(),0,v.size()*4);}
 assert(ggml_backend_sched_graph_compute(s,g)==GGML_STATUS_SUCCESS);ggml_backend_sched_synchronize(s);
 Result result;result.complete=l4_complete(o.capture);result.failed=o.capture.failed;result.observations=o.observations;
 for(auto*t:roots){std::vector<char>v;v.reserve(size_t(ggml_nelements(t))*4);
  for(int64_t n=0;n<t->ne[3];++n)for(int64_t j=0;j<t->ne[2];++j)for(int64_t h=0;h<t->ne[1];++h){
   size_t old=v.size();v.resize(old+t->ne[0]*4);ggml_backend_tensor_get(t,v.data()+old,n*t->nb[3]+j*t->nb[2]+h*t->nb[1],t->ne[0]*4);
  }result.outputs.push_back(std::move(v));
 }
 if(mode==1){
  auto check=[&](ggml_tensor*t,const char*file){std::ifstream f(out+"/"+file,std::ios::binary);std::vector<char>got((std::istreambuf_iterator<char>(f)),{}),expected;
   for(int64_t j=0;j<t->ne[2];++j)for(int64_t h=0;h<t->ne[1];++h){size_t old=expected.size();expected.resize(old+t->ne[0]*4);ggml_backend_tensor_get(t,expected.data()+old,j*t->nb[2]+h*t->nb[1],t->ne[0]*4);}assert(got==expected);};
  check(v,"v_conv_predelta-4.f32");
  for(auto*t:roots){std::string name=t->name;
   if(name=="q_conv_predelta-4"||name=="k_conv_predelta-4"||name=="state_predelta-4"||name=="conv_state_at-4"||name=="gate-4"||name=="beta_sigmoid-4")check(t,(name+".f32").c_str());
  }
  for(int n:{1,2}){assert(std::filesystem::file_size(out+"/hc-input-"+std::to_string(n)+".f32")==40960);assert(std::filesystem::file_size(out+"/hc_mixed-4-"+std::to_string(n)+".f32")==10240);}

 }
 ggml_backend_sched_free(s);ggml_backend_free(b);ggml_free(c);return result;
}
int main(int argc,char**argv){assert(argc==2);assert(std::filesystem::create_directory(argv[1]));std::string root=argv[1];
 for(int heads:{16,48}){auto prefix=root+"/heads"+std::to_string(heads);auto off=run(prefix+"-off",0,heads);auto on=run(prefix+"-on",1,heads);auto error=run(prefix+"-error",2,heads);
  assert(off.outputs==on.outputs&&off.outputs==error.outputs);assert(on.complete&&!on.failed&&on.observations==20);assert(error.failed&&!error.complete&&error.observations==20);
 }
 std::puts("PASS real scheduler18 node names/20 observations, duplicate HC,16/48 heads, whole-history strides, initial-state layouts, pure ASK, error continuation and OFF/ON output equality; synthetic arithmetic only");
}
