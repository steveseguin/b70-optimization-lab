// CPU-device bitwise test (OpenCL CPU, GPU blocked) of OWNRT_DRAFT_MERGE (rank0-lab 2026-10-26): p59::DenseBatch4<2560>
// against a host replica of the production draft projection p59::Dense<2560,false,false,1,1> for batch 4 (p59::lane per
// lane on the host, adjacent-pair tree, p59::tail with the merge_add tail and with no tail).
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/p59_draft.hpp"
#include <atomic>
#include <cstdio>
#include <random>
#include <vector>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
int main(){
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 constexpr unsigned K=2560,rows=2560,B=4;std::mt19937 g(5);std::normal_distribution<float> nd(0.f,0.05f),xd(0.f,1.f);int failures=0;
 for(p59::Tail tl:{p59::merge_add,p59::none}){
  std::vector<uint16_t> w(size_t(rows)*K),x(size_t(B)*K),other(rows);
  for(auto& v:w)v=iq3::bf16_bits(nd(g));for(auto& v:x)v=iq3::bf16_bits(xd(g));for(auto& v:other)v=iq3::bf16_bits(xd(g));
  w[7]=0x7fc0;x[K+9]=0xff80; // a NaN weight and a -inf input propagate as in the reference
  // host reference
  std::vector<uint16_t> ry(size_t(B)*rows),rout(size_t(B)*rows,0xbeef);
  p59::Bound hb{reinterpret_cast<const uint8_t*>(w.data()),nullptr,x.data(),ry.data(),nullptr,rout.data(),other.data(),nullptr,nullptr,nullptr,nullptr,rows,B,1,tl};
  for(unsigned i=0;i<B*rows;++i){unsigned row=i%rows,slot=i/rows;float s[32];for(unsigned l=0;l<32;++l)s[l]=p59::lane<K,false>(reinterpret_cast<const uint8_t*>(w.data()+size_t(row)*K),x.data()+size_t(slot)*K,l);
   for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];p59::tail(hb,i,iq3::bf16_bits(s[0]),0);}
  // device
  auto* dw=sycl::malloc_device<uint16_t>(w.size(),q);auto* dx=sycl::malloc_device<uint16_t>(x.size(),q);auto* dy=sycl::malloc_device<uint16_t>(ry.size(),q);
  auto* dout=sycl::malloc_device<uint16_t>(rout.size(),q);auto* doth=sycl::malloc_device<uint16_t>(other.size(),q);
  q.memcpy(dw,w.data(),w.size()*2).wait();q.memcpy(dx,x.data(),x.size()*2).wait();q.memcpy(doth,other.data(),other.size()*2).wait();
  q.memset(dy,0xff,ry.size()*2).wait();std::vector<uint16_t> beef(rout.size(),0xbeef);q.memcpy(dout,beef.data(),beef.size()*2).wait();
  p59::DenseBatch4<K> op;op.a.rows=rows;op.a.columns=K;op.a.batch=B;op.a.experts=1;op.a.tail=tl;
  std::vector<void*> ptrs{dw,dw,dx,dy,dy,dx,dy,dy,dout,doth,dx};op.submit(q,ptrs,{}).wait();
  std::vector<uint16_t> gy(ry.size()),gout(rout.size());q.memcpy(gy.data(),dy,gy.size()*2).wait();q.memcpy(gout.data(),dout,gout.size()*2).wait();
  size_t bad=0;for(size_t i=0;i<gy.size();++i){bad+=gy[i]!=ry[i];bad+=gout[i]!=rout[i];}
  std::printf("  tail %s: outputs %zu, mismatches %zu %s\n",tl==p59::merge_add?"merge_add":"none",gy.size()*2,bad,bad?"FAIL":"ok");failures+=bad!=0;
  for(void* p:{(void*)dw,(void*)dx,(void*)dy,(void*)dout,(void*)doth})sycl::free(p,q);
 }
 std::printf("%s\n",failures?"FAILED":"ALL PASSED");return failures;
}
