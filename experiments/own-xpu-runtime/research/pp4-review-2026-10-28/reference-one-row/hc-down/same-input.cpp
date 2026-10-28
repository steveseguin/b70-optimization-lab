#include "ggml.h"
#include "ggml-cpu.h"
#include "stage2/packet6-kopt/reference.hpp"
#include <fstream>
#include <vector>
#include <iostream>
#include <iomanip>
#include <filesystem>
#include <cassert>
#include <cstring>
#include <cmath>
int main(int argc,char**argv){assert(argc==3);std::string in=argv[1],out=argv[2];assert(std::filesystem::create_directory(out));std::vector<uint8_t>w(6553600);std::vector<float>x(10240),host(320),ref(320);{std::ifstream f(in+"/weight.bf16",std::ios::binary);f.read((char*)w.data(),w.size());assert(f.gcount()==w.size());}{std::ifstream f(in+"/input.f32",std::ios::binary);f.read((char*)x.data(),40960);assert(f.gcount()==40960);}
 ggml_init_params p{16*1024*1024,nullptr,false};auto*c=ggml_init(p);auto*tw=ggml_new_tensor_2d(c,GGML_TYPE_BF16,10240,320);auto*tx=ggml_new_tensor_2d(c,GGML_TYPE_F32,10240,1);std::memcpy(tw->data,w.data(),w.size());std::memcpy(tx->data,x.data(),40960);auto*ty=ggml_mul_mat(c,tw,tx);auto*g=ggml_new_graph(c);ggml_build_forward_expand(g,ty);assert(ggml_graph_compute_with_ctx(c,g,1)==GGML_STATUS_SUCCESS);std::memcpy(ref.data(),ty->data,1280);
 for(int r=0;r<320;++r)host[r]=iq3::kopt::gemv_row(iq3::Type::BF16,w.data()+r*20480,reinterpret_cast<const uint16_t*>(x.data()),iq3::Type::F32,10240,32);
 int unequal=0;double max=0,rms=0;for(int i=0;i<320;++i){unequal+=std::memcmp(&ref[i],&host[i],4)!=0;double d=double(ref[i])-host[i];max=std::max(max,std::abs(d));rms+=d*d;}std::cout<<"rows=320 unequal="<<unequal<<" max_abs="<<std::setprecision(17)<<max<<" rms="<<std::sqrt(rms/320)<<"\n";
 for(auto row:{std::pair{"ggml-f64.f32",&ref},std::pair{"native-host.f32",&host}}){std::ofstream f(out+"/"+row.first,std::ios::binary);f.write((char*)row.second->data(),1280);assert(f);}ggml_free(c);
}
