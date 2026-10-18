// CPU-only exact-copy proof at production matrix extents. No model/device reads.
#include "p49c_kernel.hpp"
#include "p90_expert.hpp"
#include "p49d_small.hpp"
#include "p30_small.hpp"
#include <fstream>
#include <iostream>
#include <cstring>
#include <filesystem>
using iq3::Type;
uint64_t weight_bytes=0,chains=0,rows_checked=0;
std::ofstream transcript;
void check(bool v){if(!v)throw std::runtime_error("packet145 copy byte mismatch");}
uint32_t seed=142;
uint32_t next(){return seed=1664525*seed+1013904223;}
void exact(float a,float b){check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b));++chains;}
void emit(float a){transcript.write(reinterpret_cast<char*>(&a),sizeof(a));auto y=iq3::bf16_bits(a);transcript.write(reinterpret_cast<char*>(&y),sizeof(y));++rows_checked;}
template<Type T,unsigned K,unsigned Split>void dense(unsigned rows){
 const size_t rb=iq3::expanded::row_bytes(T,K);std::vector<uint8_t>a(rows*rb),b(a.size());
 for(unsigned r=0;r<rows;++r){auto w=a.data()+r*rb;
  if constexpr(T==Type::F32){for(unsigned k=0;k<K;++k){float v=float(int(next()%33)-16)/1024.f;std::memcpy(w+k*4,&v,4);}}
  else {for(unsigned k=0;k<K;++k)w[k]=next()>>24;for(unsigned k=K;k+4<=rb;k+=4){float d=float(int(next()%31)-15)/1024.f;std::memcpy(w+k,&d,4);}}}

 std::memcpy(b.data(),a.data(),a.size());check(!std::memcmp(a.data(),b.data(),a.size()));weight_bytes+=a.size();
 std::vector<uint16_t>x(K);for(auto&v:x)v=iq3::bf16_bits(float(int(next()%33)-16)/16.f);
 for(unsigned r=0;r<rows;++r){float pa[4]{},pb[4]{};for(unsigned s=0;s<Split;++s){auto bounds=iq3::kopt2::bounds(K,s,Split);float la[32]{},lb[32]{};for(unsigned lane=0;lane<32;++lane){la[lane]=p49c::dense_lane<T,K>(a.data()+r*rb,x.data(),bounds.first,bounds.second,lane);lb[lane]=p49c::dense_lane<T,K>(b.data()+r*rb,x.data(),bounds.first,bounds.second,lane);exact(la[lane],lb[lane]);}pa[s]=iq3::tree32(la);pb[s]=iq3::tree32(lb);exact(pa[s],pb[s]);}float va=Split==1?pa[0]:(pa[0]+pa[1])+(pa[2]+pa[3]);float vb=Split==1?pb[0]:(pb[0]+pb[1])+(pb[2]+pb[3]);exact(va,vb);
 if constexpr(Split==4){check((p49dvirtual::dense_host<T,K,Split,4>(a.data()+r*rb,x.data())==iq3::bf16_bits(va)));check((p49dvirtual::dense_host<T,K,Split,4>(b.data()+r*rb,x.data())==iq3::bf16_bits(vb)));}
 emit(va);}
}
int main(int argc,char**argv){try{check(argc==2);transcript.open(argv[1],std::ios::binary);check(bool(transcript));
 dense<Type::F32,2560,4>(512);dense<Type::Q6_K,2560,4>(640);dense<Type::Q6_K,2560,4>(640);dense<Type::F32,2560,4>(1);
 dense<Type::Q8_0,2560,1>(640);dense<Type::Q8_0,2560,1>(640);
 dense<Type::Q6_K,2560,1>(6144);dense<Type::Q8_0,2560,1>(6144);
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"model_payload_read\":false,\"weight_bytes\":"<<weight_bytes<<",\"fp32_chain_checks\":"<<chains<<",\"output_rows\":"<<rows_checked<<"}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
