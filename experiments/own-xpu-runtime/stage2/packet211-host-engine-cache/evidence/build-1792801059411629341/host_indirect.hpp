#pragma once
#ifndef OWN_RT_HOST_ONLY
#error P211 indirect adapter is HOST_ONLY synthetic mini only
#endif
// Binding-only adapter for the exact inherited performance.cpp Multiply loop.
// arithmetic::row(v2), route status and BF16 conversion are unchanged. Pointer
// resolution and table/owned-span validation are explicit new behavior.
namespace p211 {
struct Span {uint64_t begin=0,bytes=0;};
struct IndirectMultiply final:integrated::HostOperation {
 std::vector<integrated::Matrix> matrices;std::vector<Span> pinned;Span cache;bool shared=false;
 static bool contains(Span s,uint64_t p,size_t n){return p>=s.begin&&p-s.begin<=s.bytes&&n<=s.bytes-(p-s.begin);}
 void run(std::span<void*const> p)const override {
  for(size_t i=0;i<matrices.size();++i){const auto&m=matrices[i];auto b=p.data()+i*5;
   auto w=static_cast<const uint8_t*>(b[0]);auto x=static_cast<const uint16_t*>(b[1]);auto y=static_cast<uint16_t*>(b[2]);
   auto routes=static_cast<const iq3::Route*>(b[3]);auto status=static_cast<uint32_t*>(b[4]);
   size_t rb=integrated::arithmetic::row_bytes(m.type,m.columns,2),expert_bytes=size_t(m.rows)*rb;
   for(unsigned j=0;j<m.count;++j){auto r=routes[j];bool valid=iq3::valid_route(r,m.experts,m.rows,m.rows);status[j]=valid?0:1;
    if(valid){const auto&entry=reinterpret_cast<const p58::Pointer*>(w)[r.expert_id];
     if(!entry.generation||entry.address%alignof(float)||!(contains(pinned.at(i),entry.address,expert_bytes)||contains(cache,entry.address,expert_bytes)))throw std::runtime_error("p211 indirect payload outside retained owned span");}
    #pragma omp parallel for schedule(static) num_threads(2)
    for(size_t row=0;row<m.rows;++row){float v=iq3::bits_float(0x7fc00000);
     if(valid&&row<r.row_count){size_t offset=(size_t(r.expert_id)*m.rows+r.row_begin+row)*rb;
      v=integrated::arithmetic::row(m.type,p58::resolve(w,offset,expert_bytes,true),x+(shared?0:size_t(j)*m.columns),m.columns,2);}
     y[size_t(j)*m.rows+row]=iq3::bf16_bits(v);
    }
   }
  }
 }
};
inline integrated::Launch indirect_experts(ownrt::Device&d,const std::vector<integrated::Matrix>&ms,bool shared,const std::vector<Span>&pinned,Span cache){
 if(ms.empty()||ms.size()>2||ms.size()!=pinned.size()||(shared&&ms.size()!=2))throw std::runtime_error("p211 indirect matrix tuple");
 if(ms.size()==2){const auto&a=ms[0];const auto&b=ms[1];
  if(a.type!=b.type||a.rows!=b.rows||a.columns!=b.columns||a.count!=b.count||a.experts!=b.experts||a.routes!=b.routes||a.x!=b.x||a.w==b.w||a.y==b.y||a.status==b.status)throw std::runtime_error("p211 gate/up tuple identity");}
 std::set<ownrt::Allocation> writable;
 for(const auto&m:ms)for(auto id:{m.y,m.status})if(!writable.insert(id).second)throw std::runtime_error("p211 cross-output alias");
 for(size_t i=0;i<ms.size();++i)for(auto output:{ms[i].y,ms[i].status}){
  for(const auto&other:ms)for(auto input:{other.w,other.x,other.routes})if(output==input)throw std::runtime_error("p211 writable/input alias");
  if(ms[i].y==ms[i].status)throw std::runtime_error("p211 output/status alias");
 }
 IndirectMultiply op;op.matrices=ms;op.shared=shared;op.pinned=pinned;op.cache=cache;std::vector<ownrt::Allocation> ids;
 for(const auto&m:ms){
  if(m.type!=iq3::Type::F32||!m.rows||!m.columns||m.rows>64||m.columns>64||!m.count||m.count>16||!m.experts||m.experts>32||!m.routes||!m.status)throw std::runtime_error("p211 mini F32 indirect shape");
  auto extent=[&](ownrt::Allocation id,size_t n){const auto&r=d.arena.row(id);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n)throw std::runtime_error("p211 indirect table/matrix extent");};
  extent(m.w,size_t(m.experts)*sizeof(p58::Pointer));extent(m.x,size_t(shared?1:m.count)*m.columns*2);extent(m.y,size_t(m.count)*m.rows*2);extent(m.routes,m.count*sizeof(iq3::Route));extent(m.status,m.count*4);
  ids.insert(ids.end(),{m.w,m.x,m.y,m.routes,m.status});
 }
 auto event=d.compute(op,ids,{});return {event,event,1};
}
}
