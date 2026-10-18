#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p74_submit.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet114-draft-prefix/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p74_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet114-draft-prefix/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p49c_kernel.hpp"
namespace p74 {
template<Type T,unsigned K,unsigned Split,bool Attention>integrated::Launch issue(ownrt::Device& d,const integrated::Matrix& m,const p39::Bindings& b){
 constexpr auto E=Attention?p39::Kind::attention_combine:p39::Kind::expert_checks;
 if(m.type!=T||m.columns!=K||!m.rows||m.rows>248320||m.count!=1||m.experts!=1)throw std::invalid_argument("p74 shape");
 auto extent=[&](ownrt::Allocation a,size_t n,unsigned align){const auto&r=d.arena.row(a);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n||uintptr_t(r.pointer)%align)throw std::invalid_argument("p74 allocation extent/alignment");};
 extent(m.w,size_t(m.rows)*row_bytes(T,K),2);extent(m.x,K*2,2);extent(m.y,m.rows*2,2);extent(m.workspace,m.rows*32,4);
 if(m.w==m.x||m.w==m.y||m.x==m.y||m.workspace==m.y||m.workspace==m.w||m.workspace==m.x)throw std::invalid_argument("p74 aliases");
 // Non-epilogue functors never dereference control bindings; keep their ABI.
 auto error=Attention?b.error:m.workspace,active=Attention?b.active:m.workspace,position=Attention?b.position:m.workspace;
 std::array<ownrt::Allocation,19> ids{m.w,m.w,m.x,m.y,m.y,m.x,m.y,m.y,m.workspace,m.x,m.y,Attention?b.streams:m.y,Attention?b.inject:m.x,m.x,m.x,m.x,error,active,position};
 p49c::DenseKernel<T,K,Split,E,0,true> op;op.shape.rows=m.rows;op.shape.count=1;op.shape.experts=1;op.shape.capacity=b.capacity;op.shape.rb=row_bytes(T,K);
 if constexpr(Attention){
  extent(b.error,4,4);extent(b.active,4,4);extent(b.position,4,4);extent(b.streams,m.rows*8,2);extent(b.inject,8,2);
  std::array<ownrt::Allocation,8> unique{m.w,m.x,m.y,m.workspace,b.error,b.active,b.streams,b.inject};
  for(size_t i=0;i<unique.size();++i)for(size_t j=0;j<i;++j)if(unique[i]==unique[j])throw std::invalid_argument("p74 attention alias");
  for(auto id:unique)if(id==b.position)throw std::invalid_argument("p74 position alias");
 }
 auto first=d.compute(op,ids,{});integrated::Launch result{first,first,1};
#ifndef OWN_RT_HOST_ONLY
 if constexpr(Attention){p49c::DenseKernel<T,K,Split,E,1,true> finish;finish.shape=op.shape;std::array after{first};result.last=d.compute(finish,ids,after);result.passes=2;}
#endif
 return result;
}
template<Type T,unsigned K>integrated::Launch split(ownrt::Device&d,const integrated::Matrix&m,unsigned v){
 if(v==6)return issue<T,K,1,false>(d,m,{});if(v==7)return issue<T,K,4,false>(d,m,{});throw std::invalid_argument("p74 expanded arithmetic required");
}
integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,unsigned v,p39::Kind kind,const p39::Bindings&b){
 if(kind==p39::Kind::attention_combine){if(m.type==Type::Q6_K&&m.columns==6144&&v==7)return issue<Type::Q6_K,6144,4,true>(d,m,b);throw std::invalid_argument("p74 attention identity");}
 if(kind!=p39::Kind::expert_checks)throw std::invalid_argument("p74 unsupported epilogue");
#define P74(T,K) if(m.type==Type::T&&m.columns==K)return split<Type::T,K>(d,m,v)
 P74(Q6_K,2560);P74(Q8_0,2560);P74(Q6_K,6144);P74(Q8_0,6144);P74(Q8_0,640);P74(Q6_K,10240);P74(Q8_0,10240);
#undef P74
 throw std::invalid_argument("p74 unregistered packed shape");
}
}
