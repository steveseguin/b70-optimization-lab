#include "ggml.h"
#include "ggml-cpu.h"
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <fstream>
#include <iostream>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <cassert>
using V=std::vector<float>;
static V read(std::string p){std::ifstream f(p,std::ios::binary);V v(10240);f.read((char*)v.data(),40960);assert(f.gcount()==40960);return v;}
static void save(std::string p,V v){std::ofstream f(p,std::ios::binary);f.write((char*)v.data(),40960);assert(f);}
static void compare(const char*name,const V&a,const V&b){size_t unequal=0;double max=0,rms=0;for(int i=0;i<10240;++i){unequal+=std::memcmp(&a[i],&b[i],4)!=0;double d=double(a[i])-b[i];max=std::max(max,std::abs(d));rms+=d*d;}std::cout<<name<<" unequal="<<unequal<<" max_abs="<<std::setprecision(17)<<max<<" rms="<<std::sqrt(rms/10240)<<"\n";}
int main(int argc,char**argv){assert(argc==3);std::string in=argv[1],out=argv[2];std::filesystem::create_directory(out);auto x=read(in+"/hc-a-input.f32"),g=read(in+"/hc-a-gain.f32"),captured=read(in+"/hc-a-output.f32");
 ggml_init_params p{16*1024*1024,nullptr,false};auto*ctx=ggml_init(p);assert(ctx);auto*tx=ggml_new_tensor_3d(ctx,GGML_TYPE_F32,2560,4,1);auto*tg=ggml_new_tensor_2d(ctx,GGML_TYPE_F32,2560,4);std::memcpy(tx->data,x.data(),40960);std::memcpy(tg->data,g.data(),40960);auto*ty=ggml_mul(ctx,ggml_rms_norm(ctx,tx,1e-6f),tg);auto*graph=ggml_new_graph(ctx);ggml_build_forward_expand(graph,ty);assert(ggml_graph_compute_with_ctx(ctx,graph,1)==GGML_STATUS_SUCCESS);V ref(10240);std::memcpy(ref.data(),ty->data,40960);
 V native(10240);int32_t error=0,active=1,position=243;ng::Args a;a.f32=true;a.p[0]=x.data();a.p[1]=g.data();a.p[2]=native.data();a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;ng::Shape s;s.op=ng::norm;s.tokens=1;s.width=2560;s.heads=4;s.flags=ng::f32_activations_flag|8;s.capacity=4096;specialised::cpu(s,a);assert(error==0);
 compare("ggml_vs_captured",ref,captured);compare("native_host_vs_ggml",native,ref);save(out+"/ggml.f32",ref);save(out+"/native-host.f32",native);
 // Diagnostic source intermediates: no substitute operator implementation.
 for(int row=0;row<4;++row){double dsum=0;float partial[80];for(int i=0;i<2560;++i){float v=x[row*2560+i];dsum+=double(v*v);}for(int c=0;c<80;++c)partial[c]=specialised::subtree(2560,c,[&](int i){float v=x[row*2560+i];return v*v;});float fs=specialised::upper(partial,80),dm=float(dsum/2560);float fi=detmath::rsqrt(fs/2560.f+1e-6f),di=1.f/::sqrtf(dm+1e-6f);std::cout<<"stream="<<row<<" cpu_mean="<<dm<<" native_mean="<<fs/2560.f<<" cpu_inv="<<di<<" native_inv="<<fi<<"\n";}
 ggml_free(ctx);
}
