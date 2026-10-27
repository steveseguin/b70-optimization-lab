// CPU-device bitwise test for token-one BF16 HC-low + silu_div4 fusion. GPU access is blocked by nodri.so.
#include <sycl/sycl.hpp>
#include "stage2/packet6-kopt/dense_v2.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include <algorithm>
#include <bit>
#include <cstdio>
#include <random>
#include <vector>

static uint32_t bits(float x){return std::bit_cast<uint32_t>(x);}
int main(){
 auto dev=sycl::device(sycl::cpu_selector_v);sycl::queue q(dev,sycl::property::queue::in_order{});
 std::printf("device: %s\n",dev.get_info<sycl::info::device::name>().c_str());
 constexpr uint32_t rows=37,extra=4,K=10240,total=rows+extra,guard=64;
 std::mt19937 rng(918273);std::uniform_real_distribution<float> weight(-4.f,4.f),input(-1.f,1.f);
 std::vector<uint16_t> w(size_t(total)*K);for(auto& v:w)v=iq3::bf16_bits(weight(rng));
 std::vector<float>x(K);for(auto& v:x)v=input(rng);
 const uint16_t special_w[]{0x0000,0x8000,0x0001,0x8001,0x007f,0x807f,0x0080,0x8080,0x3f80,0xbf80,0x7f7f,0xff7f};
 for(unsigned i=0;i<12;++i){w[i]=special_w[i];x[i]=(i&1)?-0.f:0.f;}
 auto* wd=sycl::malloc_shared<uint16_t>(w.size(),q);auto* xd=sycl::malloc_shared<float>(K,q);
 auto* y=sycl::malloc_shared<float>(total+guard,q);auto* inject=sycl::malloc_shared<float>(extra+guard,q);auto* act=sycl::malloc_shared<float>(rows+guard,q);
 auto* want=sycl::malloc_shared<float>(total,q);auto* want_act=sycl::malloc_shared<float>(rows+guard,q);
 auto* error=sycl::malloc_shared<int32_t>(1,q);auto* ref_error=sycl::malloc_shared<int32_t>(1,q);
 auto* active=sycl::malloc_shared<int32_t>(1,q);auto* position=sycl::malloc_shared<int32_t>(1,q);
 std::copy(w.begin(),w.end(),wd);std::copy(x.begin(),x.end(),xd);
 // Baseline: the original two-matrix GEMV with no activation epilogue.
 std::array<iq3::kopt::dense_v2::Mat,4> baseline{};
 baseline[0]=iq3::kopt::dense_v2::Mat{reinterpret_cast<const uint8_t*>(wd),xd,want,rows,K,K*2,0};
 baseline[1]=iq3::kopt::dense_v2::Mat{reinterpret_cast<const uint8_t*>(wd+size_t(rows)*K),xd,want+rows,extra,K,K*2,rows};
 q.parallel_for(sycl::nd_range<1>((size_t(total)*32+127)/128*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   iq3::kopt::dense_v2::bf16_multi<1,8>(baseline,2,it);
  }).wait();
 size_t fails=0;
 auto run=[&](const char* name,int32_t av,int32_t ev,int32_t pos,bool paired){
  std::vector<float> sentinel(total+guard,-777.f),sentinel_i(extra+guard,-888.f),sentinel_a(rows+guard,-999.f);
  std::copy(sentinel.begin(),sentinel.end(),y);std::copy(sentinel_i.begin(),sentinel_i.end(),inject);std::copy(sentinel_a.begin(),sentinel_a.end(),act);std::copy(sentinel_a.begin(),sentinel_a.end(),want_act);
  *active=av;*position=pos;*ref_error=ev;
  // Baseline epilogue: the separate detmath launch with the original active/error/position behavior.
  q.parallel_for(sycl::range<1>(rows),[=](sycl::id<1> id){
    auto error_ref=sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*ref_error);
    if(!*active||error_ref.load())return;
    const int32_t p=*position;if(p<0||p>=128){if(id[0]==0)error_ref.store(1);return;}
    want_act[id[0]]=detmath::silu_div4(want[id[0]]);
   }).wait();
  *error=ev;
  std::array<iq3::kopt::dense_v2::Mat,4> m{};
  m[0]=iq3::kopt::dense_v2::Mat{reinterpret_cast<const uint8_t*>(wd),xd,y,rows,K,K*2,0,
   iq3::kopt::dense_v2::LowAct{act,error,position,active,128}};
  const unsigned count=paired?2:1;
  if(paired)m[1]=iq3::kopt::dense_v2::Mat{reinterpret_cast<const uint8_t*>(wd+size_t(rows)*K),xd,inject,extra,K,K*2,rows};
  const uint32_t groups=paired?total:rows;const size_t global=(size_t(groups)*32+127)/128*128;
  q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    iq3::kopt::dense_v2::bf16_multi<1,8>(m,count,it);
   }).wait();
  size_t bad=0;
  for(uint32_t r=0;r<rows;++r){
   if(bits(y[r])!=bits(want[r]))++bad;
   if(bits(act[r])!=bits(want_act[r])){if(bad<3)std::printf("%s row %u low %08x/%08x act %08x/%08x\n",name,r,bits(y[r]),bits(want[r]),bits(act[r]),bits(want_act[r]));++bad;}
  }
  for(uint32_t r=0;r<extra;++r)if(paired&&bits(inject[r])!=bits(want[rows+r]))++bad;
  for(unsigned i=0;i<guard;++i){if(y[total+i]!=-777.f||act[rows+i]!=-999.f||inject[extra+i]!=-888.f)++bad;}
  if(*error!=*ref_error)++bad;
  std::printf("%-22s low+act+guards mismatches %zu (error %d)\n",name,bad,*error);fails+=bad;
 };
 run("single valid",1,0,17,false);
 run("paired valid",1,0,127,true);
 run("paired inactive",0,0,17,true);
 run("paired sticky error",1,1,17,true);
 run("paired negative pos",1,0,-1,true);
 run("paired capacity pos",1,0,128,true);
 std::printf("%s\n",fails?"FAILED":"ALL PASSED");
 sycl::free(wd,q);sycl::free(xd,q);sycl::free(y,q);sycl::free(inject,q);sycl::free(act,q);sycl::free(want,q);sycl::free(want_act,q);
 sycl::free(error,q);sycl::free(ref_error,q);sycl::free(active,q);sycl::free(position,q);
 return fails?1:0;
}
