#include "expert_dispatch.hpp"
#include "../packet103-record-bundle/p49d_submit.hpp"
#include "../packet103-record-bundle/p49b_expert_kernel.hpp"
#include "../packet103-record-bundle/p90_layout.hpp"
#ifdef OWN_RT_HOST_ONLY
#include "kernels/candidates.hpp"
#else
#include "expert_image.hpp"
#endif
namespace p115 {
struct Expert final:p49b::Base {
 unsigned arm,rows,count,experts;bool down;
#ifdef OWN_RT_HOST_ONLY
 template<class K>void issue(std::span<void*const>p)const{K k;k.rows=rows;k.count=count;k.experts=experts;k.run(p);}
 void run(std::span<void*const>p)const override {
  if(down){if(arm==2)issue<p115down::Kernel<>>(p);else issue<p100::Kernel<2>>(p);return;}
  switch(arm){case 1:issue<p115e3::Kernel<>>(p);break;case 3:issue<p102::Kernel<2,true>>(p);break;case 4:issue<p115e5::Kernel<>>(p);break;default:issue<p90exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true>>(p);}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d)const override {
  return (arm?p115_image::large:p115_image::normal)(arm,down,q,p,d,rows,count,experts);
 }
#endif
};
integrated::Launch expert(ownrt::Device&d,const std::vector<integrated::Matrix>&m,p39::Kind kind,const p39::Bindings&b,std::string_view layout,std::string_view choice){
 using p39::Kind;using iq3::Type;
 if(layout!="exp-halfcache+down-tile16")throw std::invalid_argument("packet115 requires fixed halfcache/tile16 layout");
 const bool down=kind==Kind::down_status;
 if(!(down||kind==Kind::expert_checks)||m.size()!=(down?1u:2u))throw std::invalid_argument("packet115 expert tuple");
 const auto&a=m[0];const auto&peer=down?a:m[1];
 if(a.type!=(down?Type::IQ4_NL:Type::IQ2_S)||a.columns!=(down?640u:2560u)||a.rows!=(down?2560u:640u)||a.count!=10||a.experts!=512)throw std::invalid_argument("packet115 full shape required");
 if(!down&&(peer.type!=a.type||peer.columns!=a.columns||peer.rows!=a.rows||peer.count!=a.count||peer.experts!=a.experts))throw std::invalid_argument("packet115 peer shape");
 unsigned arm=5;const char* names[]={"production","e3-next","iq4-bytepair","v4-batch2-shared","e5-shared"};
 for(unsigned i=0;i<5;++i)if(choice==names[i])arm=i;
 if(arm==5)throw std::invalid_argument("packet115 unregistered expert kernel");
 std::array<ownrt::Allocation,19> ids{a.w,peer.w,a.x,a.y,peer.y,a.routes,a.status,peer.status,a.workspace,b.other?b.other:a.x,b.out?b.out:a.y,b.streams?b.streams:a.y,b.inject?b.inject:a.x,b.mixture?b.mixture:a.x,b.shared_gate?b.shared_gate:a.x,b.one?b.one:a.x,b.error,b.active,b.position};
 std::array<void*,19>p{};
 for(unsigned i=0;i<19;++i){const auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("packet115 dead/nondevice allocation");p[i]=r.pointer;}
 auto extent=[&](ownrt::Allocation id,size_t n){if(d.arena.row(id).bytes<n)throw std::invalid_argument("packet115 allocation extent");};
 size_t stride=down?360:840,n=size_t(a.rows)*a.count;
 extent(a.w,size_t(a.experts)*a.rows*stride);extent(peer.w,size_t(a.experts)*a.rows*stride);extent(a.x,size_t(a.columns)*(down?a.count:1)*2);extent(a.y,n*2);extent(peer.y,n*2);
 extent(a.routes,a.count*sizeof(iq3::Route));extent(a.status,a.count*4);extent(peer.status,a.count*4);extent(b.error,4);extent(b.active,4);extent(b.position,4);
 if(uintptr_t(p[0])%(down?16:4)||uintptr_t(p[1])%4)throw std::invalid_argument("packet115 weight alignment");
 Expert k;k.arm=arm;k.down=down;k.rows=a.rows;k.count=a.count;k.experts=a.experts;
 auto e=d.compute(k,ids,{});return {e,e,1};
}
}
