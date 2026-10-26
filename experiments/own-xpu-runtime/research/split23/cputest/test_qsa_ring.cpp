// CPU check of OWNRT_QSA_RAW_RING (split23 lab, 2026-10-26): the engine's own qsa_append_pool group code (ng::cpu, the
// same function the device kernel runs with a device team) over a long position sequence, once with the full raw buffer
// and once with the 512-row ring. After every launch the keys, values and pooled buffers must be bitwise equal, and at
// the end every ring slot must hold the newest full-buffer row with that slot index.
// Build: g++ -std=c++20 -O2 -fno-fast-math -ffp-contract=off -DOWN_RT_HOST_ONLY -I engine/src test_qsa_ring.cpp
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
int main(int argc,char**){
 const bool negative=argc>1; // negative control: corrupt the ring row of the open pool before one launch
 const int C=65536,ID=128,KV=512;std::mt19937 g(7);std::uniform_real_distribution<float> u(-2.f,2.f);
 std::vector<float> rope(size_t(rope_constants::bytes)*2/4);for(auto& x:rope)x=u(g);
 std::vector<float> weight(ID);for(auto& x:weight)x=u(g);
 struct Bank{std::vector<float> keys,values,raw,pooled;};
 Bank full{std::vector<float>(size_t(C)*KV),std::vector<float>(size_t(C)*KV),std::vector<float>(size_t(C)*ID),std::vector<float>(size_t((C+3)/4)*ID)};
 Bank ring{std::vector<float>(size_t(C)*KV),std::vector<float>(size_t(C)*KV),std::vector<float>(size_t(qsaring::rows)*ID),std::vector<float>(size_t((C+3)/4)*ID)};
 int32_t error=0,active=1,position=0;
 // Launch sizes: 256-row chunks, a partial chunk, decode rows, odd sizes that start pools mid-block.
 std::vector<int> launches;for(int i=0;i<16;++i)launches.push_back(256);launches.push_back(44);for(int i=0;i<48;++i)launches.push_back(1);
 for(int t:{3,2,256,7,1,1,5,256,255,1,2})launches.push_back(t);
 int pos=0;size_t failures=0,checks=0;
 for(int T:launches){
  std::vector<float> kn(size_t(T)*KV),v(size_t(T)*KV),ik(size_t(T)*ID);for(auto& x:kn)x=u(g);for(auto& x:v)x=u(g);for(auto& x:ik)x=u(g);
  if(negative&&pos==4143)ring.raw[size_t(qsaring::row(pos-1,qsaring::flag))*ID]+=1.f; // row 4142 of the pool 4140..4143 that this launch completes
  for(int mode=0;mode<2;++mode){Bank& b=mode?ring:full;
   ng::Shape s{};s.op=ng::pool;s.tokens=T;s.capacity=C;s.flags=ng::f32_activations_flag|8|(mode?qsaring::flag:0);
   ng::Args a{};a.f32=true;a.p[0]=kn.data();a.p[1]=v.data();a.p[2]=ik.data();a.p[3]=weight.data();a.p[4]=b.keys.data();a.p[5]=b.values.data();
   a.p[6]=b.raw.data();a.p[7]=b.pooled.data();a.p[15]=&error;a.p[16]=rope.data();position=pos;a.p[17]=&position;a.p[18]=&active;
   ng::cpu(s,a);
  }
  if(error){std::printf("engine error flag at pos %d\n",pos);return 1;}
  ++checks;failures+=std::memcmp(full.keys.data(),ring.keys.data(),full.keys.size()*4)!=0;failures+=std::memcmp(full.values.data(),ring.values.data(),full.values.size()*4)!=0;
  failures+=std::memcmp(full.pooled.data(),ring.pooled.data(),full.pooled.size()*4)!=0;
  pos+=T;
 }
 size_t slots_bad=0;
 for(int slot=0;slot<qsaring::rows;++slot){int r=pos-1-((pos-1-slot)%qsaring::rows+qsaring::rows)%qsaring::rows;
  slots_bad+=std::memcmp(ring.raw.data()+size_t(slot)*ID,full.raw.data()+size_t(r)*ID,ID*4)!=0;}
 std::printf("launches %zu positions %d: keys/values/pooled mismatching launches %zu, ring slots differing from the newest full row %zu of %d\n",checks,pos,failures,slots_bad,qsaring::rows);
 std::printf("%s\n",failures||slots_bad?"FAILED":"PASSED");return failures||slots_bad;
}
