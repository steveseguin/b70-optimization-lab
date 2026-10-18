#include "p129_fp8.hpp"
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>

// Independent scalar publisher decoding, then the registered reduction tree.
static float reference(uint8_t code){
 unsigned e=(code>>3)&15,m=code&7;
 float x=e?float(8+m)*std::ldexp(1.f,int(e)-10):float(m)*std::ldexp(1.f,-9);
 return code&128?-x:x;
}
static void require_equal(float a,float b){
 if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b))throw std::runtime_error("FP8 decode differs");
}
template<unsigned K>static void test(std::ofstream& out){
 constexpr unsigned rows=128,batch=3,experts=2;constexpr size_t rb=K+K/128*2;
 std::vector<uint8_t> w(experts*rows*rb),peer(w.size());
 std::vector<uint16_t> x(batch*K),y(batch*rows),py(y.size()),expected(y.size()),expected_peer(y.size());
 uint32_t status[batch]{},ps[batch]{};
 iq3::Route routes[batch]={{1,0,rows},{0,0,rows},{1,0,rows}};
 for(size_t r=0;r<experts*rows;++r){
  for(unsigned k=0;k<K;++k){uint8_t a=uint8_t(r*17+k*13),b=uint8_t(r*5+k*19);if((a&127)==127)--a;if((b&127)==127)--b;w[r*rb+k]=a;peer[r*rb+k]=b;}
  for(unsigned block=0;block<K/128;++block){uint16_t scale=iq3::bf16_bits((block%5==0)?0.f:std::ldexp(1.125f,int((r+block)%9)-7));std::memcpy(w.data()+r*rb+K+2*block,&scale,2);std::memcpy(peer.data()+r*rb+K+2*block,&scale,2);}
 }
 for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%37)-18)/32.f);
 for(bool pair:{false,true}){
  for(unsigned slot=0;slot<batch;++slot)for(unsigned row=0;row<rows;++row){float sums[2][32]{};
   for(unsigned which=0;which<2;++which){const auto* raw=(which?peer:w).data()+(routes[slot].expert_id*rows+row)*rb;
    for(unsigned lane=0;lane<32;++lane)for(unsigned k=lane*8;k<K;k+=256)for(unsigned j=0;j<8&&k+j<K;++j){uint16_t scale;std::memcpy(&scale,raw+K+(k+j)/128*2,2);float value=reference(raw[k+j])*iq3::bits_float(uint32_t(scale)<<16);float product=value*iq3::bits_float(uint32_t(x[(pair?0:slot*K)+k+j])<<16);sums[which][lane]=sums[which][lane]+product;}
    // Spell the reference tree independently of iq3::tree32.
    for(unsigned width=1;width<32;width*=2)for(unsigned lane=0;lane<32;lane+=2*width)sums[which][lane]=sums[which][lane]+sums[which][lane+width];
   }
   expected[slot*rows+row]=iq3::bf16_bits(sums[0][0]);expected_peer[slot*rows+row]=iq3::bf16_bits(sums[1][0]);
  }
  mtp36::Linear a;a.rows=rows;a.batch=batch;a.experts=experts;a.routes=1;
  std::array<void*,8> pointers{w.data(),peer.data(),x.data(),y.data(),py.data(),routes,status,ps};
  if(pair){p129::Dense<K,true,true> op;op.a=a;op.run(pointers);}else{p129::Dense<K,true,false> op;op.a=a;op.run(pointers);}
  if(y!=expected||(pair&&py!=expected_peer))throw std::runtime_error("FP8 routed dot bytes differ");
  for(auto s:status)if(s)throw std::runtime_error("valid route rejected");
  out.write(reinterpret_cast<const char*>(y.data()),y.size()*2);if(pair)out.write(reinterpret_cast<const char*>(py.data()),py.size()*2);
 }
 // Bounds must still poison invalid routes and flag their status.
 routes[0].expert_id=experts;
 p129::Dense<K,true,true> bad;bad.a.rows=rows;bad.a.batch=batch;bad.a.experts=experts;bad.a.routes=1;
 std::array<void*,8> pointers{w.data(),peer.data(),x.data(),y.data(),py.data(),routes,status,ps};bad.run(pointers);
 if(status[0]!=1||ps[0]!=1||y[0]!=0x7fc0||py[0]!=0x7fc0)throw std::runtime_error("invalid route not poisoned");
}
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("output path required");
 for(unsigned i=0;i<256;++i)if((i&127)!=127)require_equal(p129::decode(uint8_t(i)),reference(uint8_t(i)));
 std::ofstream out(argv[1],std::ios::binary);test<640>(out);test<2560>(out);
 if(!out)throw std::runtime_error("fixture write");std::cout<<"254 codes, both routed widths, paired/unpaired, repeated routes, invalid bounds PASS\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
