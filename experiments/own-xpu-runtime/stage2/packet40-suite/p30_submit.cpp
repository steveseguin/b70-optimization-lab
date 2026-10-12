// Packet30 arithmetic and kernels, bound through packet37's prepared owner API.
#include "p30_submit.hpp"
#include "p30_attention.hpp"
#include "p30_small.hpp"
#include "p28/submit.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
// Included once: exposes the stage launchers within this translation unit.
#include "p30_attention.cpp"
#include "p30_small.cpp"
#endif
namespace p30integrated {
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<int Stage> struct Attention final:Base {
 ng::Shape shape{};unsigned variant{};
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  // CPU computes the same complete three-stage result on the first launch.
  // Subsequent events are no-ops; CPU timestamps are never device evidence.
  if constexpr(Stage==0||Stage==3)p30::attention::cpu(shape,a,variant);
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  constexpr size_t groups=Stage==2?6144:24;
  return p30::attention::issue<Stage>(q,shape,a,Stage==0?24u*shape.extra:groups,deps);
 }
#endif
};
integrated::Launch attention(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,unsigned variant,std::span<const ownrt::Event> deps){
 if(a.size()!=19)throw std::invalid_argument("p30 attention binding count");
 // No device position readback and no mutable capture: capacity is a safe
 // admitted-slot bound for every replay position. Selection remains on device.
 s.extra=std::min(s.capacity,s.budget+3);p30::attention::validate(s,int(variant));
 ng::Args pointers;std::array<size_t,19> extents{};
 for(int j=0;j<19;++j){const auto& r=d.arena.row(a[j]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p30 attention binding lifetime/memory");pointers.p[j]=r.pointer;extents[j]=r.bytes;}
 p30::attention::validate(s,pointers,extents,int(variant));
 integrated::Launch result{};
 auto issue=[&]<int Stage>(){Attention<Stage> op;op.shape=s;op.variant=variant;std::array<ownrt::Event,1> prior{result.last};auto e=d.compute(op,a,result.last?std::span<const ownrt::Event>(prior):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};
 if(variant==0){issue.template operator()<0>();issue.template operator()<1>();}else issue.template operator()<3>();
 issue.template operator()<2>();return result;
}
struct Small final:Base {
 std::string family;std::array<p30::small::Bound,4> metadata{};unsigned count{};
 std::array<p30::small::Bound,4> bind(std::span<void*const> p)const{auto b=metadata;for(unsigned j=0;j<count;++j){b[j].w=static_cast<const uint8_t*>(p[j*3]);b[j].x=static_cast<const uint16_t*>(p[j*3+1]);b[j].y=static_cast<uint16_t*>(p[j*3+2]);}return b;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto b=bind(p);p30::small::cpu(family,std::span<const p30::small::Bound>(b.data(),count),"rows4");}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto b=bind(p);return p30::small::submit(q,family,std::span<const p30::small::Bound>(b.data(),count),"rows4",deps).back();}
#endif
};
integrated::Launch small(ownrt::Device& d,std::string_view name,std::span<const integrated::Matrix> ms,std::span<const unsigned> variants){
 if(name.starts_with("small."))packet27::small::validate(d,name,ms,variants);
 else {
  if(ms.size()!=1||variants.size()!=1)throw std::invalid_argument("p30 single small member count");
  p28::validate(d,std::vector<integrated::Matrix>(ms.begin(),ms.end()),"p28.dense.rows4",false,variants[0]);
 }
 auto shapes=p30::small::shapes(name);if(shapes.size()!=ms.size())throw std::invalid_argument("p30 small count");Small op;op.family=name;op.count=unsigned(ms.size());std::array<ownrt::Allocation,12> ids{};
 for(unsigned j=0;j<ms.size();++j){const auto& m=ms[j];const auto& sh=shapes[j];
  if(m.type!=sh.type||m.rows!=sh.rows||m.columns!=sh.cols||((sh.type==iq3::Type::F32)?(sh.split==4?4u:0u):(sh.split==4?7u:6u))!=variants[j])throw std::invalid_argument("p30 small compiled shape/arithmetic");
  auto& b=op.metadata[j];b={static_cast<const uint8_t*>(d.arena.row(m.w).pointer),static_cast<const uint16_t*>(d.arena.row(m.x).pointer),static_cast<uint16_t*>(d.arena.row(m.y).pointer),d.arena.row(m.w).bytes,d.arena.row(m.x).bytes/2,d.arena.row(m.y).bytes/2};ids[j*3]=m.w;ids[j*3+1]=m.x;ids[j*3+2]=m.y;
 }
 p30::small::validate(name,std::span<const p30::small::Bound>(op.metadata.data(),op.count),"rows4");
 auto e=d.compute(op,std::span<const ownrt::Allocation>(ids.data(),ms.size()*3),{});return {e,e,1};
}
}
