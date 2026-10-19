#include "demand_submit.hpp"
#include "../build/native/p100_down.hpp"
namespace p58am {
template<class K> integrated::Launch partition_impl(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const p39::Bindings& b,ownrt::Allocation half,ownrt::Allocation desc,ownrt::Allocation stage,unsigned part,bool down){
 const auto&a=m.at(0);const auto&peer=down?a:m.at(1);
 std::array<ownrt::Allocation,22> ids{a.w,peer.w,a.x,a.y,peer.y,a.routes,a.status,peer.status,a.workspace,a.x,a.y,a.y,a.x,a.x,a.x,a.x,b.error,b.active,b.position,half,desc,stage};
 if(a.type!=(down?iq3::Type::IQ4_NL:iq3::Type::IQ2_S)||peer.type!=a.type)throw std::logic_error("demand quantization layout mismatch");
 K k;k.indirect=true;k.partition=part;k.rows=a.rows;k.count=a.count;k.experts=a.experts;
 if(part<1||part>2||a.count!=10||a.experts!=512||a.rows!=(down?2560u:640u)||a.columns!=(down?640u:2560u))throw std::logic_error("demand shape/partition");
 std::array<void*,22> ptr{};
 for(size_t i=0;i<ids.size();++i){auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::logic_error("demand binding ownership");ptr[i]=r.pointer;}
 auto extent=[&](size_t i,size_t n){if(d.arena.row(ids[i]).bytes<n)throw std::logic_error("demand binding extent");};
 extent(0,512*sizeof(p58::Pointer));extent(1,512*sizeof(p58::Pointer));extent(2,(down?10*640:2560)*2);extent(3,a.rows*10*2);extent(4,peer.rows*10*2);extent(5,10*sizeof(iq3::Route));extent(6,40);extent(7,40);extent(16,4);extent(17,4);extent(18,4);extent(19,65536*4);extent(20,sizeof(Map));extent(21,sizeof(Map));
 auto bound=k.bind(ptr);bound.position=static_cast<const uint32_t*>(ptr[18]);bound.capacity=b.capacity;
 if constexpr(std::is_same_v<K,p58am_down::Kernel<2>>)p39::validate<iq3::Type::IQ4_NL,640,p39::Kind::down_status,1>(bound);
 else p39::validate<iq3::Type::IQ2_S,2560,p39::Kind::expert_checks,1>(bound);
 auto event=d.compute(k,ids,{});return {event,event,1};
}
integrated::Launch partition(ownrt::Device& d,const std::vector<integrated::Matrix>& m,const p39::Bindings& b,ownrt::Allocation half,ownrt::Allocation desc,ownrt::Allocation stage,unsigned part,bool down){
 if(down)return partition_impl<p58am_down::Kernel<2>>(d,m,b,half,desc,stage,part,true);
 return partition_impl<p58ag_exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true,0,true>>(d,m,b,half,desc,stage,part,false);
}
struct Descriptor final:p49b::Base {
 uint64_t cache=0,bytes=0;std::array<size_t,3> bank_bytes{};
 static void slot(unsigned i,const iq3::Route* routes,const p58::Pointer*g,const p58::Pointer*u,const p58::Pointer*d,Map*out,uint64_t cache,uint64_t bytes,std::array<size_t,3> bank_bytes){
  auto r=routes[i];Slot s{};s.expert=r.expert_id;s.valid=iq3::valid_route(r,512,640,640);
  if(s.valid){s.gate=g[r.expert_id].address;s.up=u[r.expert_id].address;s.down=d[r.expert_id].address;s.generation=g[r.expert_id].generation;
   auto inside=[=](uint64_t p,size_t n){return p>=cache&&p-cache<=bytes&&n<=bytes-(p-cache);};
   s.resident=inside(s.gate,bank_bytes[0])&&inside(s.up,bank_bytes[1])&&inside(s.down,bank_bytes[2]);
  }out->slots[i]=s;
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {for(unsigned i=0;i<10;++i)slot(i,static_cast<const iq3::Route*>(p[0]),static_cast<const p58::Pointer*>(p[1]),static_cast<const p58::Pointer*>(p[2]),static_cast<const p58::Pointer*>(p[3]),static_cast<Map*>(p[4]),cache,bytes,bank_bytes);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&)const override {
  auto r=static_cast<const iq3::Route*>(p[0]);auto g=static_cast<const p58::Pointer*>(p[1]);auto u=static_cast<const p58::Pointer*>(p[2]);auto d=static_cast<const p58::Pointer*>(p[3]);auto out=static_cast<Map*>(p[4]);auto base=cache,size=bytes;auto extents=bank_bytes;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.parallel_for(sycl::range<1>(10),[=](sycl::id<1>i){slot(i[0],r,g,u,d,out,base,size,extents);});});
 }
#endif
};
integrated::Launch descriptor(ownrt::Device&d,ownrt::Allocation routes,std::array<ownrt::Allocation,3> tables,ownrt::Allocation out,uint64_t cache,uint64_t bytes,std::array<size_t,3> bank_bytes){
 std::array<ownrt::Allocation,5> ids{routes,tables[0],tables[1],tables[2],out};
 for(size_t i=0;i<5;++i){auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<(i==0?10*sizeof(iq3::Route):i==4?sizeof(Map):512*sizeof(p58::Pointer)))throw std::logic_error("descriptor extent/ownership");}
 Descriptor op;op.cache=cache;op.bytes=bytes;op.bank_bytes=bank_bytes;auto e=d.compute(op,ids,{});return {e,e,1};
}
}
