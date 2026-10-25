#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/specialised_submit.hpp"
#include "stage2/packet194-expert-diet-engine/mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace specialised {
#ifdef OWN_RT_HOST_ONLY
template<ng::Op Code,int Stage,int FixedWidth=0,int FixedHeads=0> struct Kernel final:integrated::HostOperation {
 ng::Shape shape;explicit Kernel(ng::Shape s):shape(s){}
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());a.f32=(shape.flags&ng::f32_activations_flag)!=0;float* scratch=static_cast<float*>(p[19]);packet24::mock_items(work_items(shape,Stage),[&](size_t i){body<Code,Stage,FixedWidth,FixedHeads>(shape,a,i,scratch,HostGuard{});});}
};
#else
struct Guard {
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
};
// QSA select with one 32-lane subgroup per block item (body<select,Stage>'s values; work items -> subgroups).
// Stage 0: the 128-leaf adjacent tree of each head's score with lane l holding leaves 4l..4l+3 (in-lane levels 1-2,
// shuffles for 3-7), heads accumulated in order. Stage 1: the finiteness test and the rank count split across lanes
// and combined with all-of and an integer sum, both independent of order.
template<int Stage,class Guard> inline void select_rows(ng::Shape s,ng::Args a,sycl::nd_item<1> it,float* scratch,Guard guard){
 s.op=ng::select;auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id());const size_t index=it.get_global_linear_id()/32;
 if(index>=work_items(s,Stage)||!a.i(18)[0]||guard.error(a))return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(index==0&&lane==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),L=ceildiv(ng::launch_extent(s),4),S=slots(s),per=Stage==0?std::max(L,S):L;
 const int r=int(index)/per,b=int(index)%per,n=(pos+r+1)/4,count=std::min(n,s.budget/4);
 auto tree32=[&](float x){for(int width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,x,(lane+width)%32);if(lane%(2*width)==0)x=x+rhs;}return sycl::group_broadcast(sg,x,0);};
 if constexpr(Stage==0){
  if(b<S&&lane==0)a.i(2)[r*S+b]=-1;
  if(b<n){float score=0.f;
   for(int h=0;h<4;++h){float v[4];
    #pragma unroll
    for(int i=0;i<4;++i){const int k=4*lane+i;v[i]=a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);}
    const float d=tree32((v[0]+v[1])+(v[2]+v[3]));score=score+std::max(0.f,d);}
   if(lane==0)scratch[r*cap+b]=score/detmath::sqrt(float(128));}
 }else{
  if(b>=n&&b!=0)return;bool finite=true;int rank=0;const float v=b<n?scratch[r*cap+b]:0.f;
  for(int k=lane;k<n;k+=32){const float other=scratch[r*cap+k];finite=finite&&std::isfinite(other);rank+=other>v||(other==v&&k<b);}
  if(!sycl::all_of_group(sg,finite)){if(b==0&&lane==0)guard.fail(a);return;}
  rank=sycl::reduce_over_group(sg,rank,sycl::plus<int>());
  if(lane==0){if(b<n&&rank<count)for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=b*4+j;
   if(b==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;}
 }
}
inline bool select_subgroups(){static const bool on=[]{const char* e=std::getenv("OWNRT_SELECT_SG");return !e||e[0]!='0';}();return on;}
template<ng::Op Code,int Stage,int FixedWidth=0,int FixedHeads=0> struct Kernel final:ownrt::SyclOperation {
 ng::Shape shape;explicit Kernel(ng::Shape s):shape(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());float* scratch=static_cast<float*>(p[19]);auto s=shape;a.f32=(s.flags&ng::f32_activations_flag)!=0;auto n=work_items(s,Stage);
  if constexpr(Code==ng::select)if(select_subgroups())
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(n*32),sycl::range<1>(32))](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{select_rows<Stage>(s,a,it,scratch,Guard{});}));});
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(n)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> i){body<Code,Stage,FixedWidth,FixedHeads>(s,a,i[0],scratch,Guard{});}));});
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
