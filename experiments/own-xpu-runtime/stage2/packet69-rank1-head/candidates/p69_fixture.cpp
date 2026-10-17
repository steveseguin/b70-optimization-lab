#ifndef OWN_RT_HOST_ONLY
#error CPU fixture only
#endif
#include "p69_head.hpp"
#include "p49_qsa_reference.hpp"
#include <fstream>
#include <bit>
#include <cassert>
int main(int argc,char**argv){
 if(argc!=3)return 1;std::ofstream expected(argv[1],std::ios::binary),actual(argv[2],std::ios::binary);
 uint32_t rng=694901;auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
 std::vector<uint8_t>w(3200);std::vector<uint16_t>x(2560);
 for(unsigned test=0;test<512;++test){
  for(unsigned k=0;k<2560;++k){w[k]=uint8_t(next());x[k]=iq3::bf16_bits(float(int(next()%257)-128)/64);}
  for(unsigned k=0;k<160;++k){float sc=float(int(next()%127)-63)/512;if(test%8==0)sc=0;if(test%8==1)sc=iq3::bits_float((next()%2?0x80000000:0)|1);std::memcpy(w.data()+2560+k*4,&sc,4);}
  if(test%8==2)for(auto&v:x)v=0;if(test%8==3)for(auto&v:x)v=0x8000;
  float ref[32],got[32];
  for(unsigned lane=0;lane<32;++lane){ref[lane]=p33::dense_lane<iq3::Type::Q6_K,2560>(w.data(),x.data(),0,2560,lane);got[lane]=p69::lane(w.data(),x.data(),lane);assert(std::bit_cast<uint32_t>(ref[lane])==std::bit_cast<uint32_t>(got[lane]));}
  expected.write((char*)ref,sizeof(ref));actual.write((char*)got,sizeof(got));
  float a=iq3::tree32(ref),b=p69::row(w.data(),x.data());assert(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b));
  expected.write((char*)&a,4);actual.write((char*)&b,4);uint16_t aa=iq3::bf16_bits(a),bb=iq3::bf16_bits(b);assert(aa==bb);expected.write((char*)&aa,2);actual.write((char*)&bb,2);
 }
 // Padded grids must write every valid row exactly once, with no tail store.
 for(unsigned wg:{64u,128u})for(unsigned rows:{1u,2u,3u,63u,64u,65u,91392u,248320u}){
  std::vector<unsigned>seen(rows);for(size_t gid=0;gid<((size_t(rows)*32+wg-1)/wg)*wg;++gid)if(gid%32==0&&gid/32<rows)++seen[gid/32];for(auto n:seen)assert(n==1);
 }
 // Draft arithmetic has its own fixed split32 tree. Repeat hashes, not parity
 // against the previous draft. These are operator fixtures, no model inference.
 for(int context:{2,31,33,65})for(int rows:{1,2}){
  p47ref::Fixture f(context,rows,6949+context,0);p47ref::cpu_split(f.shape,f.args());
  expected.write((char*)f.data[5].data(),f.data[5].size()*4);actual.write((char*)f.data[5].data(),f.data[5].size()*4);
 }
 return expected&&actual?0:2;
}
