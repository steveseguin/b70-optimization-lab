#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p105_submit.cpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/prepared_submission.hpp"
#endif
#line 1
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/p105_submit.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p105 {
struct Pack final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 unsigned rows=0,offset=0;
 static void write(const uint16_t* logits,const int32_t* index,const uint32_t* error,Best* best,unsigned n,unsigned off){
  int32_t i=*index;uint32_t bad=*error;if(i<0||unsigned(i)>=n){i=0;bad|=1;}
  *best={iq3::bits_float(uint32_t(logits[i])<<16),int32_t(off)+i,bad,0};
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{write(static_cast<const uint16_t*>(p[0]),static_cast<const int32_t*>(p[1]),static_cast<const uint32_t*>(p[2]),static_cast<Best*>(p[3]),rows,offset);}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  auto x=static_cast<const uint16_t*>(p[0]);auto i=static_cast<const int32_t*>(p[1]);auto e=static_cast<const uint32_t*>(p[2]);auto b=static_cast<Best*>(p[3]);auto n=rows,off=offset;
  return ownrt::prepared_submit(q,[=](sycl::handler& h){h.single_task(packet26::checked([=]{write(x,i,e,b,n,off);}));});
 }
#endif
};
ownrt::Event pack(ownrt::Device& d,ownrt::Allocation x,ownrt::Allocation i,ownrt::Allocation e,ownrt::Allocation b,unsigned n,unsigned off){
 if(!n||off+n>vocab)throw std::invalid_argument("p105 pack range");
 std::array ids{x,i,e,b};size_t sizes[]={size_t(n)*2,4,4,16};
 for(unsigned j=0;j<4;++j){const auto&r=d.arena.row(ids[j]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<sizes[j]||uintptr_t(r.pointer)%4)throw std::invalid_argument("p105 pack binding");for(unsigned k=0;k<j;++k)if(ids[j]==ids[k])throw std::invalid_argument("p105 pack alias");}
 Pack op;op.rows=n;op.offset=off;return d.compute(op,ids,{});
}
}
