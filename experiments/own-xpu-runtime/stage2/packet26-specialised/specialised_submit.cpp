#include "specialised_submit.hpp"
#include "mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace specialised {
#ifdef OWN_RT_HOST_ONLY
template<ng::Op Code,int Stage,int FixedWidth=0,int FixedHeads=0> struct Kernel final:integrated::HostOperation {
 ng::Shape shape;explicit Kernel(ng::Shape s):shape(s){}
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());float* scratch=static_cast<float*>(p[19]);packet24::mock_items(work_items(shape,Stage),[&](size_t i){body<Code,Stage,FixedWidth,FixedHeads>(shape,a,i,scratch,HostGuard{});});}
};
#else
struct Guard {
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
};
template<ng::Op Code,int Stage,int FixedWidth=0,int FixedHeads=0> struct Kernel final:ownrt::SyclOperation {
 ng::Shape shape;explicit Kernel(ng::Shape s):shape(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());float* scratch=static_cast<float*>(p[19]);auto s=shape;auto n=work_items(s,Stage);
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){body<Code,Stage,FixedWidth,FixedHeads>(s,a,i[0],scratch,Guard{});});});
 }
};
#endif
template<ng::Op Code,int FixedWidth=0,int FixedHeads=0> integrated::Launch submit_class(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){
 integrated::Launch result{};
 auto issue=[&]<int Stage>(){Kernel<Code,Stage,FixedWidth,FixedHeads> op(s);std::array<ownrt::Event,1> after{result.last};auto e=d.compute(op,a,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};
 issue.template operator()<0>();if constexpr(Code!=ng::attention_score)issue.template operator()<1>();if constexpr(Code==ng::attention_softmax||Code==ng::route_gather)issue.template operator()<2>();if constexpr(Code==ng::route_gather){issue.template operator()<3>();issue.template operator()<4>();}return result;
}
integrated::Launch submit(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,ownrt::Allocation scratch,std::span<const ownrt::Event> deps){
 ng::validate(s);if(a.size()!=19)throw std::invalid_argument("specialised requires 19 bindings");
 if(d.arena.row(scratch).bytes<scratch_floats(s)*sizeof(float))throw std::invalid_argument("specialised scratch extent");
 std::array<ownrt::Allocation,20> bound{};std::copy(a.begin(),a.end(),bound.begin());bound[19]=scratch;
 if(s.width==2560&&s.heads==4){
  if(s.op==ng::norm)return submit_class<ng::norm,2560,4>(d,s,bound,deps);
  if(s.op==ng::combine_norm)return submit_class<ng::combine_norm,2560,4>(d,s,bound,deps);
 }
 if(s.op==ng::route_gather&&s.width==512&&s.extra==10)return submit_class<ng::route_gather,512>(d,s,bound,deps);
 switch(s.op){
 case ng::route_gather:return submit_class<ng::route_gather>(d,s,bound,deps);
 case ng::norm:return submit_class<ng::norm>(d,s,bound,deps);
 case ng::combine_norm:return submit_class<ng::combine_norm>(d,s,bound,deps);
 case ng::gated_norm:return submit_class<ng::gated_norm>(d,s,bound,deps);
 case ng::gdn:return submit_class<ng::gdn>(d,s,bound,deps);
 case ng::prepare:return submit_class<ng::prepare>(d,s,bound,deps);
 case ng::pool:return submit_class<ng::pool>(d,s,bound,deps);
 case ng::select:return submit_class<ng::select>(d,s,bound,deps);
 case ng::attention_score:return submit_class<ng::attention_score>(d,s,bound,deps);
 case ng::attention_softmax:return submit_class<ng::attention_softmax>(d,s,bound,deps);
 case ng::attention_value:return submit_class<ng::attention_value>(d,s,bound,deps);
 default:throw std::invalid_argument("unsupported specialised class");}
}
}
