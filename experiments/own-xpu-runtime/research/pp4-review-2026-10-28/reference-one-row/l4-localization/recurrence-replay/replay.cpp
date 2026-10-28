#include "ggml.h"
#include "ggml-cpu.h"
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <cassert>
#include <cstring>
#include <cmath>
constexpr int T=244,H=48,D=128,KEYS=16,Y=H*D,S=H*D*D;
static std::vector<float>read(const std::string&p,size_t n){std::ifstream f(p,std::ios::binary);std::vector<float>x(n);f.read((char*)x.data(),n*4);assert(size_t(f.gcount())==n*4&&f.peek()==std::char_traits<char>::eof());return x;}
static void save(const std::string&p,const float*x,size_t n){std::ofstream f(p,std::ios::binary);f.write((const char*)x,n*4);assert(f);}
struct Metric{int unequal=0;double max=0,rms=0;};
static Metric metric(const float*a,const float*b,int n){Metric m;double sum=0;for(int i=0;i<n;++i){assert(std::isfinite(a[i])&&std::isfinite(b[i]));double d=double(a[i])-b[i];m.unequal+=std::memcmp(a+i,b+i,4)!=0;m.max=std::max(m.max,std::abs(d));sum+=d*d;}m.rms=std::sqrt(sum/n);return m;}
static void fields(std::ostream&o,const Metric&m){o<<"{\"unequal_words\":"<<m.unequal<<",\"max_abs\":"<<m.max<<",\"rms\":"<<m.rms<<"}";}
int main(int argc,char**argv){assert(argc==3);std::string in=argv[1],out=argv[2];assert(std::filesystem::create_directory(out));std::cout<<std::setprecision(17);
 auto q=read(in+"/q_conv_predelta-4.f32",T*KEYS*D),k=read(in+"/k_conv_predelta-4.f32",T*KEYS*D),v=read(in+"/v_conv_predelta-4.f32",T*Y),g=read(in+"/gate-4.f32",T*H),beta=read(in+"/beta_sigmoid-4.f32",T*H),initial=read(in+"/state_predelta-4.f32",S),captured=read(in+"/recurrent-output.f32",Y);
 for(float x:initial)assert(x==0);
 ggml_init_params ip{128*1024*1024,nullptr,false};auto*c=ggml_init(ip);assert(c);
 auto tensor=[&](int a,int b,int e,int d,const float*x){auto*t=ggml_new_tensor_4d(c,GGML_TYPE_F32,a,b,e,d);if(x)std::memcpy(t->data,x,size_t(a)*b*e*d*4);return t;};
 auto*qt=tensor(D,KEYS,T,1,q.data()),*kt=tensor(D,KEYS,T,1,k.data()),*vt=tensor(D,H,T,1,v.data()),*gt=tensor(1,H,T,1,g.data()),*bt=tensor(1,H,T,1,beta.data()),*st=tensor(D,D,H,1,initial.data());
 auto*result=ggml_gated_delta_net(c,qt,kt,vt,gt,bt,st,1);auto*graph=ggml_new_graph(c);ggml_build_forward_expand(graph,result);
 assert(ggml_graph_compute_with_ctx(c,graph,2)==GGML_STATUS_SUCCESS);auto*all=(float*)result->data;
 save(out+"/ggml-batch-output.f32",all,T*Y);save(out+"/ggml-batch-final-state.f32",all+T*Y,S);
 Metric qualification=metric(all+(T-1)*Y,captured.data(),Y);{std::ofstream f(out+"/qualification.json");f<<std::setprecision(17)<<"{\"captured_last_row\":";fields(f,qualification);f<<",\"bitwise_pass\":"<<(qualification.unequal?"false":"true")<<"}\n";}
 std::cout<<"captured last-row qualification ";fields(std::cout,qualification);std::cout<<"\n";
 if(qualification.unequal){std::cerr<<"STOP: pinned operator does not reproduce actual captured boundary; no native comparison\n";return 3;}
 // Production stage1 accepts prepared q/k/decay/beta scratch; stage0 is deliberately bypassed.
 // CPU q is normalized but unscaled: divide by sqrt128 at the native pre-dot location.
 // Gate capture is log-decay, so native scratch receives detmath::exp(g); beta already sigmoid.
 std::vector<float>scratch(T*4192),packed(T*10240,0),native(T*Y),state(initial),batch_state(S);
 for(int r=0;r<T;++r){float*p=scratch.data()+r*4192;
  for(int j=0;j<KEYS*D;++j){p[j]=q[r*KEYS*D+j]/detmath::sqrt(float(D));p[2048+j]=k[r*KEYS*D+j];}
  for(int h=0;h<H;++h){p[4096+h]=detmath::exp(g[r*H+h]);p[4144+h]=beta[r*H+h];}
  std::memcpy(packed.data()+r*10240+4096,v.data()+r*Y,Y*4);
 }
 ng::Shape ns;ns.op=ng::gdn;ns.tokens=T;ns.capacity=4096;ns.flags=2|4|8|16|ng::f32_activations_flag;
 ng::Args a;a.f32=true;int32_t error=0,position=0,active=1;a.p[0]=packed.data();a.p[5]=initial.data();a.p[6]=native.data();a.p[7]=batch_state.data();a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;
 for(size_t j=0;j<specialised::work_items(ns,1);++j)specialised::body<ng::gdn,1>(ns,a,j,scratch.data(),specialised::HostGuard{});assert(error==0);
 save(out+"/native-stage1-batch-output.f32",native.data(),T*Y);save(out+"/native-stage1-batch-final-state.f32",batch_state.data(),S);
 // Actual ggml one-row operator reconstructs states without allocating244 full state snapshots.
 auto*q1=tensor(D,KEYS,1,1,nullptr),*k1=tensor(D,KEYS,1,1,nullptr),*v1=tensor(D,H,1,1,nullptr),*g1=tensor(1,H,1,1,nullptr),*b1=tensor(1,H,1,1,nullptr),*s1=tensor(D,D,H,1,initial.data());
 auto*one=ggml_gated_delta_net(c,q1,k1,v1,g1,b1,s1,1);auto*onegraph=ggml_new_graph(c);ggml_build_forward_expand(onegraph,one);
 std::vector<float>reference_step(T*Y),native_step(T*Y);std::ofstream rows(out+"/per-row.jsonl");rows<<std::setprecision(17);
 ns.tokens=1;a.p[5]=state.data();a.p[7]=state.data();
 for(int r=0;r<T;++r){
  std::memcpy(q1->data,q.data()+r*KEYS*D,KEYS*D*4);std::memcpy(k1->data,k.data()+r*KEYS*D,KEYS*D*4);std::memcpy(v1->data,v.data()+r*Y,Y*4);std::memcpy(g1->data,g.data()+r*H,H*4);std::memcpy(b1->data,beta.data()+r*H,H*4);
  assert(ggml_graph_compute_with_ctx(c,onegraph,2)==GGML_STATUS_SUCCESS);auto*yr=(float*)one->data;auto*sr=yr+Y;std::memcpy(reference_step.data()+r*Y,yr,Y*4);
  a.p[0]=packed.data()+r*10240;a.p[6]=native_step.data()+r*Y;position=r;
  for(size_t j=0;j<specialised::work_items(ns,1);++j)specialised::body<ng::gdn,1>(ns,a,j,scratch.data()+r*4192,specialised::HostGuard{});assert(error==0);
  auto outputs=metric(yr,native_step.data()+r*Y,Y),states=metric(sr,state.data(),S);rows<<"{\"position\":"<<r<<",\"output\":";fields(rows,outputs);rows<<",\"state\":";fields(rows,states);rows<<"}\n";
  std::memcpy(s1->data,sr,S*4);
 }
 assert(std::memcmp(reference_step.data(),all,T*Y*4)==0);assert(std::memcmp((float*)s1->data,all+T*Y,S*4)==0);
 assert(std::memcmp(native_step.data(),native.data(),T*Y*4)==0);assert(std::memcmp(state.data(),batch_state.data(),S*4)==0);
 std::ofstream final(out+"/result.json");final<<std::setprecision(17)<<"{\"same_input_boundary_qualified\":true,\"step_vs_batch_bitwise\":true,\"output\":";fields(final,metric(all,native.data(),T*Y));final<<",\"final_state\":";fields(final,metric(all+T*Y,batch_state.data(),S));final<<"}\n";
 ggml_free(c);return 0;
}
