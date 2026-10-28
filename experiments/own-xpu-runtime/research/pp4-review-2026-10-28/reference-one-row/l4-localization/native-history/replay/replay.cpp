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
constexpr int T=244,H=48,D=128,K=16,Y=6144,S=786432,STEP=4192;
std::vector<float>read(const std::string&p,size_t n){std::ifstream f(p,std::ios::binary);std::vector<float>v(n);f.read((char*)v.data(),n*4);assert(size_t(f.gcount())==n*4&&f.peek()==std::char_traits<char>::eof());return v;}
void save(const std::string&p,const float*x,size_t n){std::ofstream f(p,std::ios::binary);f.write((const char*)x,n*4);assert(f);}
struct M{size_t n=0;double max=0,rms=0;};
M delta(const float*a,const float*b,size_t n){M m;double sum=0;for(size_t i=0;i<n;++i){assert(std::isfinite(a[i])&&std::isfinite(b[i]));double d=double(a[i])-b[i];m.n+=std::memcmp(a+i,b+i,4)!=0;m.max=std::max(m.max,std::abs(d));sum+=d*d;}m.rms=std::sqrt(sum/n);return m;}
void show(std::ostream&o,const M&m){o<<"{\"unequal_words\":"<<m.n<<",\"max_abs\":"<<m.max<<",\"rms\":"<<m.rms<<"}";}
std::vector<float>native(const std::vector<float>&conv,const std::vector<float>&prep,std::vector<float>&state){
 ng::Shape s;s.op=ng::gdn;s.tokens=T;s.capacity=4096;s.flags=94;ng::Args a;a.f32=true;
 std::vector<float>initial(S),out(T*Y);state.resize(S);int32_t error=0,position=0,active=1;
 a.p[0]=const_cast<float*>(conv.data());a.p[5]=initial.data();a.p[6]=out.data();a.p[7]=state.data();a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;
 for(size_t j=0;j<specialised::work_items(s,1);++j)specialised::body<ng::gdn,1>(s,a,j,const_cast<float*>(prep.data()),specialised::HostGuard{});assert(!error);return out;
}
int main(int argc,char**argv){assert(argc==5);std::string history=argv[1],controls=argv[2],cpu=argv[3],out=argv[4];assert(std::filesystem::create_directory(out));
 auto raw=read(history,T*65920/4),weights=read(controls,96);std::vector<float>conv(T*10240),alpha(T*48),beta(T*48),actual(T*Y);
 for(int r=0;r<T;++r){auto*p=raw.data()+r*(65920/4);std::memcpy(conv.data()+r*10240,p,40960);p+=10240;std::memcpy(alpha.data()+r*48,p,192);p+=48;std::memcpy(beta.data()+r*48,p,192);p+=48;std::memcpy(actual.data()+r*Y,p,24576);}
 ng::Shape s;s.op=ng::gdn;s.tokens=T;s.capacity=4096;s.flags=94;ng::Args a;a.f32=true;int32_t error=0,position=0,active=1;
 a.p[0]=conv.data();a.p[1]=alpha.data();a.p[2]=beta.data();a.p[3]=weights.data();a.p[4]=weights.data()+48;a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;
 std::vector<float>prep(T*STEP),state;for(size_t j=0;j<specialised::work_items(s,0);++j)specialised::body<ng::gdn,0>(s,a,j,prep.data(),specialised::HostGuard{});assert(!error);
 auto ny=native(conv,prep,state);save(out+"/native-host-y.f32",ny.data(),ny.size());save(out+"/native-host-final-state.f32",state.data(),state.size());save(out+"/native-prepared.f32",prep.data(),prep.size());
 M qualification=delta(ny.data(),actual.data(),actual.size());std::ofstream qf(out+"/qualification.json");qf<<std::setprecision(17)<<"{\"native_capture_vs_host\":";show(qf,qualification);qf<<",\"bitwise_pass\":"<<(qualification.n?"false":"true")<<"}\n";qf.close();
 std::cout<<std::setprecision(17)<<"Native raw qualification ";show(std::cout,qualification);std::cout<<"\n";
 if(qualification.n){std::cerr<<"STOP: production host raw stage0+1 does not reproduce actual GPU history; no crossed attribution\n";return 3;}
 // Real reference stage0 chain on IDENTICAL native raw conv/alpha/beta + exact controls.
 ggml_init_params ip{128*1024*1024,nullptr,false};auto*c=ggml_init(ip);assert(c);
 auto tensor=[&](int n,int m,const float*p){auto*t=ggml_new_tensor_2d(c,GGML_TYPE_F32,n,m);if(p)std::memcpy(t->data,p,size_t(n)*m*4);return t;};
 auto*cv=tensor(10240,T,conv.data());auto*av=tensor(48,T,alpha.data());auto*bv=tensor(48,T,beta.data());auto*wa=tensor(48,1,weights.data());auto*dt=tensor(48,1,weights.data()+48);
 auto*qv=ggml_view_4d(c,cv,128,16,T,1,512,40960,40960*T,0);auto*kv=ggml_view_4d(c,cv,128,16,T,1,512,40960,40960*T,8192);auto*vv=ggml_view_4d(c,cv,128,48,T,1,512,40960,40960*T,16384);
 auto norm=[&](ggml_tensor*t){return ggml_scale(c,ggml_rms_norm(c,t,1e-6f/128),1.f/std::sqrt(128.f));};auto*qn=norm(qv);auto*kn=norm(kv);
 auto*gate=ggml_mul(c,ggml_softplus(c,ggml_add(c,av,dt)),wa);auto*sigmoid=ggml_sigmoid(c,bv);
 auto*zero=ggml_new_tensor_4d(c,GGML_TYPE_F32,128,128,48,1);std::memset(zero->data,0,S*4);
 auto*ref=ggml_gated_delta_net(c,qn,kn,vv,ggml_reshape_4d(c,gate,1,48,T,1),ggml_reshape_4d(c,sigmoid,1,48,T,1),zero,1);
 auto*g=ggml_new_graph(c);ggml_build_forward_expand(g,ref);assert(ggml_graph_compute_with_ctx(c,g,2)==GGML_STATUS_SUCCESS);auto*ry=(float*)ref->data;
 save(out+"/ggml-on-native-raw-y.f32",ry,T*Y);save(out+"/ggml-on-native-raw-final-state.f32",ry+T*Y,S);
 std::vector<float>gp(T*STEP);for(int r=0;r<T;++r){float*p=gp.data()+r*STEP;
  for(int j=0;j<K*D;++j){p[j]=((float*)qn->data)[r*K*D+j]/detmath::sqrt(float(D));p[2048+j]=((float*)kn->data)[r*K*D+j];}
  for(int h=0;h<H;++h){p[4096+h]=detmath::exp(((float*)gate->data)[r*H+h]);p[4144+h]=((float*)sigmoid->data)[r*H+h];}}
 std::vector<float>cross_state;auto cross=native(conv,gp,cross_state);save(out+"/ggml-prepared-native-stage1-y.f32",cross.data(),cross.size());
 auto cq=read(cpu+"/q_conv_predelta-4.f32",T*K*D),ck=read(cpu+"/k_conv_predelta-4.f32",T*K*D),cvv=read(cpu+"/v_conv_predelta-4.f32",T*Y),cg=read(cpu+"/gate-4.f32",T*H),cb=read(cpu+"/beta_sigmoid-4.f32",T*H),cy=read(cpu+"/recurrent-output.f32",Y);
 std::vector<float>cp(T*STEP),cconv(T*10240);for(int r=0;r<T;++r){float*p=cp.data()+r*STEP;for(int j=0;j<K*D;++j){p[j]=cq[r*K*D+j]/detmath::sqrt(float(D));p[2048+j]=ck[r*K*D+j];}for(int h=0;h<H;++h){p[4096+h]=detmath::exp(cg[r*H+h]);p[4144+h]=cb[r*H+h];}std::memcpy(cconv.data()+r*10240+4096,cvv.data()+r*Y,Y*4);}
 auto cpu_native=native(cconv,cp,cross_state);save(out+"/cpu-prepared-native-stage1-y.f32",cpu_native.data(),cpu_native.size());
 std::ofstream boundaries(out+"/stage0-boundaries.jsonl");boundaries<<std::setprecision(17);
 for(int r=0;r<T;++r){boundaries<<"{\"position\":"<<r;
  auto field=[&](const char*name,int offset,int count){boundaries<<",\""<<name<<"\":{\"same_native_raw_stage0\":";show(boundaries,delta(prep.data()+r*STEP+offset,gp.data()+r*STEP+offset,count));boundaries<<",\"different_native_cpu_histories\":";show(boundaries,delta(prep.data()+r*STEP+offset,cp.data()+r*STEP+offset,count));boundaries<<"}";};
  field("q_scaled",0,2048);field("k",2048,2048);field("decay",4096,48);field("beta",4144,48);
  boundaries<<",\"v_different_native_cpu_histories\":";show(boundaries,delta(conv.data()+r*10240+4096,cvv.data()+r*Y,Y));boundaries<<"}\n";
 }
 std::ofstream rows(out+"/per-row.jsonl");rows<<std::setprecision(17);for(int r=0;r<T;++r){rows<<"{\"position\":"<<r<<",\"native_vs_ggml_same_raw\":";show(rows,delta(ny.data()+r*Y,ry+r*Y,Y));rows<<",\"native_vs_ggml_prep_same_raw\":";show(rows,delta(ny.data()+r*Y,cross.data()+r*Y,Y));rows<<",\"ggml_prep_recurrence_arithmetic\":";show(rows,delta(cross.data()+r*Y,ry+r*Y,Y));rows<<",\"upstream_different_histories_native_recurrence\":";show(rows,delta(cross.data()+r*Y,cpu_native.data()+r*Y,Y));rows<<"}\n";}
 std::ofstream result(out+"/result.json");result<<std::setprecision(17)<<"{\"native_raw_qualified\":true,\"last_native_vs_ggml_same_raw\":";show(result,delta(ny.data()+(T-1)*Y,ry+(T-1)*Y,Y));result<<",\"last_cpu_prepared_native_vs_cpu_capture\":";show(result,delta(cpu_native.data()+(T-1)*Y,cy.data(),Y));result<<"}\n";ggml_free(c);return 0;
}
