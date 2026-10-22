#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p93_submit.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p93_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p93_kernel.hpp"
namespace p93 {
integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,const std::string&choice){
 if(m.type!=iq3::Type::Q6_K||m.columns!=K||!m.rows||m.rows>248320||m.count!=1||m.experts!=1||m.routes)throw std::invalid_argument("p93 head shape");
 auto extent=[&](ownrt::Allocation id,size_t bytes,unsigned alignment){const auto&r=d.arena.row(id);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes||uintptr_t(r.pointer)%alignment)throw std::invalid_argument("p93 head allocation extent/alignment");};
 extent(m.w,size_t(m.rows)*2100,choice=="head-transpose"?4:2);extent(m.x,K*2,2);extent(m.y,size_t(m.rows)*2,2);
 if(m.w==m.x||m.w==m.y||m.x==m.y)throw std::invalid_argument("p93 head alias");
 std::array ids{m.w,m.x,m.y};ownrt::Event e;
 if(choice=="head-plane"){Kernel<1>op;op.rows=m.rows;e=d.compute(op,ids,{});}
 else if(choice=="head-transpose"){Kernel<2>op;op.rows=m.rows;e=d.compute(op,ids,{});}
 else throw std::invalid_argument("p93 head selection");
 return {e,e,1};
}
}
