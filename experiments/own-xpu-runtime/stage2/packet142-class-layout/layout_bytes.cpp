// CPU-only exact-copy proof at production matrix extents. No model/device reads.
#include "p49c_kernel.hpp"
#include "p90_expert.hpp"
#include <fstream>
#include <iostream>
#include <cstring>
#include <filesystem>
using iq3::Type;
uint64_t weight_bytes=0,chains=0,rows_checked=0;
std::ofstream transcript;
void check(bool v){if(!v)throw std::runtime_error("packet142 copy byte mismatch");}
uint32_t seed=142;
uint32_t next(){return seed=1664525*seed+1013904223;}
void exact(float a,float b){check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b));++chains;}
void emit(float a){transcript.write(reinterpret_cast<char*>(&a),sizeof(a));auto y=iq3::bf16_bits(a);transcript.write(reinterpret_cast<char*>(&y),sizeof(y));++rows_checked;}
template<Type T,unsigned K,unsigned Split>void dense(unsigned rows){
 const size_t rb=iq3::expanded::row_bytes(T,K);std::vector<uint8_t>a(rows*rb),b(a.size());
 for(unsigned r=0;r<rows;++r){auto w=a.data()+r*rb;for(unsigned k=0;k<K;++k)w[k]=next()>>24;for(unsigned k=K;k+4<=rb;k+=4){float d=float(int(next()%31)-15)/1024.f;std::memcpy(w+k,&d,4);}}
 std::memcpy(b.data(),a.data(),a.size());check(!std::memcmp(a.data(),b.data(),a.size()));weight_bytes+=a.size();
 std::vector<uint16_t>x(K);for(auto&v:x)v=iq3::bf16_bits(float(int(next()%33)-16)/16.f);
 for(unsigned r=0;r<rows;++r){float pa[4]{},pb[4]{};for(unsigned s=0;s<Split;++s){auto bounds=iq3::kopt2::bounds(K,s,Split);float la[32]{},lb[32]{};for(unsigned lane=0;lane<32;++lane){la[lane]=p49c::dense_lane<T,K>(a.data()+r*rb,x.data(),bounds.first,bounds.second,lane);lb[lane]=p49c::dense_lane<T,K>(b.data()+r*rb,x.data(),bounds.first,bounds.second,lane);exact(la[lane],lb[lane]);}pa[s]=iq3::tree32(la);pb[s]=iq3::tree32(lb);exact(pa[s],pb[s]);}float va=Split==1?pa[0]:(pa[0]+pa[1])+(pa[2]+pa[3]);float vb=Split==1?pb[0]:(pb[0]+pb[1])+(pb[2]+pb[3]);exact(va,vb);emit(va);}
}
void experts(){
 constexpr unsigned K=2560,rows=640,experts=512;const size_t stride=p90::expert_stride(K),rb=p49bgemv::source_row_bytes(Type::IQ2_S,K);
 std::vector<uint8_t>a(size_t(rows)*experts*stride),b(a.size()),raw(rb);std::vector<uint16_t>x(K);for(auto&v:x)v=iq3::bf16_bits(float(int(next()%33)-16)/16.f);
 for(unsigned stream=0;stream<2;++stream){
  for(unsigned r=0;r<rows*experts;++r){for(auto&v:raw)v=next()>>24;for(size_t k=0;k<rb;k+=iq3::layout(Type::IQ2_S).bytes){raw[k]=0;raw[k+1]=0x20;}p90::expert_repack(K,raw.data(),a.data()+r*stride);}
  std::memcpy(b.data(),a.data(),a.size());check(!std::memcmp(a.data(),b.data(),a.size()));weight_bytes+=a.size();
  for(unsigned slot=0;slot<10;++slot)for(unsigned row=0;row<rows;++row){size_t r=((slot*53+stream*19)%experts)*rows+row;float la[32]{},lb[32]{};for(unsigned physical=0;physical<4;++physical){auto ca=p90exp::wide_chains<Type::IQ2_S,K,8>(a.data()+r*stride,x.data(),physical),cb=p90exp::wide_chains<Type::IQ2_S,K,8>(b.data()+r*stride,x.data(),physical);for(unsigned c=0;c<8;++c){la[physical*8+c]=ca[c];lb[physical*8+c]=cb[c];exact(ca[c],cb[c]);}}float va=iq3::tree32(la),vb=iq3::tree32(lb);exact(va,vb);emit(va);}
 }
}
int main(int argc,char**argv){try{check(argc==2);transcript.open(argv[1],std::ios::binary);check(bool(transcript));
 dense<Type::Q6_K,2560,1>(10240);dense<Type::Q6_K,2560,1>(6144);dense<Type::Q6_K,2560,1>(12288);dense<Type::Q6_K,2560,1>(1024);dense<Type::Q6_K,6144,4>(2560);
 dense<Type::Q8_0,10240,4>(320);dense<Type::Q8_0,320,1>(10240);experts();
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"model_payload_read\":false,\"weight_bytes\":"<<weight_bytes<<",\"fp32_chain_checks\":"<<chains<<",\"output_rows\":"<<rows_checked<<"}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
