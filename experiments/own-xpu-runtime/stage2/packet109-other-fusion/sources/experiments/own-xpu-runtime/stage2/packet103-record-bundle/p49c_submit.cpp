#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p49c_submit.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet109-other-fusion/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p49c_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet109-other-fusion/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p49c_kernel.hpp"
namespace p49c {
template<Type T,unsigned K,unsigned Split,p39::Kind E>
integrated::Launch issue(ownrt::Device& d,const integrated::Matrix& m,const p39::Bindings& b){
 p28::validate(d,{m},"p28.dense.wg32",false,Split==4?7:6);
 // All controls remain live bindings even when a dense gate has no epilogue.
 std::array<ownrt::Allocation,19> ids{m.w,m.w,m.x,m.y,m.y,m.x,m.y,m.y,m.workspace,m.x,b.out?b.out:m.y,b.streams?b.streams:m.y,b.inject?b.inject:m.x,m.x,m.x,m.x,b.error,b.active,b.position};
 DenseKernel<T,K,Split,E> op;op.shape.rows=m.rows;op.shape.count=m.count;op.shape.experts=m.experts;op.shape.capacity=b.capacity;op.shape.rb=integrated::arithmetic::row_bytes(T,K,Split==4?7:6);
 std::array<void*,19> pointers;
 for(size_t i=0;i<ids.size();++i){const auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p49c dead/nondevice binding");pointers[i]=r.pointer;}
 auto bound=op.bind(pointers);
 auto extent=[&](ownrt::Allocation id,size_t bytes){if(d.arena.row(id).bytes<bytes)throw std::invalid_argument("p49c allocation extent");};
 extent(b.error,4);extent(b.active,4);extent(b.position,4);
 if constexpr(E!=p39::Kind::expert_checks)p39::validate<T,K,E,Split>(bound);
 else {
  if(!b.capacity||b.capacity>INT32_MAX)throw std::invalid_argument("p49c context capacity");
  for(auto control:{b.error,b.active,b.position}){if(uintptr_t(d.arena.row(control).pointer)%4||control==m.y||control==m.w||control==m.x)throw std::invalid_argument("p49c gate control alias/alignment");}
  if(b.error==b.active||b.error==b.position||b.active==b.position)throw std::invalid_argument("p49c gate control alias");
 }
 if constexpr(E==p39::Kind::silu_div4)extent(b.out,size_t(m.rows)*2);
 if constexpr(E==p39::Kind::attention_combine){extent(b.streams,size_t(m.rows)*8);extent(b.inject,8);}
 auto first=d.compute(op,ids,{});integrated::Launch result{first,first,1};
#ifndef OWN_RT_HOST_ONLY
 if constexpr(E==p39::Kind::attention_combine){DenseKernel<T,K,Split,E,1> finish;finish.shape=op.shape;std::array after{first};result.last=d.compute(finish,ids,after);result.passes=2;}
#endif
 return result;
}
integrated::Launch dense_submit(ownrt::Device&d,const integrated::Matrix&m,p39::Kind kind,const p39::Bindings&b){
 if(kind==p39::Kind::silu_div4&&m.type==Type::Q8_0&&m.columns==10240)return issue<Type::Q8_0,10240,4,p39::Kind::silu_div4>(d,m,b);
 if(kind==p39::Kind::expert_checks&&m.type==Type::Q8_0&&m.columns==320)return issue<Type::Q8_0,320,1,p39::Kind::expert_checks>(d,m,b);
 if(kind==p39::Kind::attention_combine&&m.type==Type::Q6_K&&m.columns==6144)return issue<Type::Q6_K,6144,4,p39::Kind::attention_combine>(d,m,b);
 throw std::invalid_argument("p49c unqualified dense shape");
}
integrated::Launch route(ownrt::Device&d,const integrated::Spec&s,std::span<const ownrt::Allocation>a){return route_submit(d,s,a);}
}
