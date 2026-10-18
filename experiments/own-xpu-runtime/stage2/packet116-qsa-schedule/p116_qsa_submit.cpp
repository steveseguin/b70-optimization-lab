#include "p116_qsa_submit.hpp"
#include "p116_qsa_host.hpp"
#include "p49_qsa_submit.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#include "p116_qsa_kernel.hpp"
#endif
namespace p116 {
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<bool Select,int Stage>struct Kernel final:Base {
 ng::Shape s;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  if constexpr(Select)selection_host<Stage>(s,a,static_cast<float*>(p[19]));
  else if constexpr(Stage==0){if(!a.i(18)[0]||a.i(15)[0])return;if(a.i(17)[0]<0||a.i(17)[0]>ng::launch_extent(s)-s.tokens){a.i(15)[0]=1;return;}try{attention_host(s,a);}catch(const std::invalid_argument&){a.i(15)[0]=1;}}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const> p,const std::vector<sycl::event>&deps)const override {ng::Args a;std::copy_n(p.begin(),19,a.p.begin());
  if constexpr(Select)return selection_device<Stage>(q,s,a,static_cast<float*>(p[19]),deps);
  else {auto counts=static_cast<int*>(p[19]);auto partial=reinterpret_cast<float*>(static_cast<uint8_t*>(p[19])+16);
   if constexpr(Stage==0)return p47::admit(q,s,a,counts,deps);
   if constexpr(Stage==1)return tiles(q,s,a,counts,partial,deps);
   if constexpr(Stage==2)return p47::combine<true>(q,s,a,counts,partial,deps);
  }
 }
#endif
};
integrated::Launch submit(ownrt::Device&d,const integrated::Spec&s,std::span<const ownrt::Allocation>b,ownrt::Allocation control,ownrt::Allocation score,ownrt::Allocation probability,std::span<const ownrt::Event>deps){
 bool select=s.op==integrated::Op::qsa_select;int tail=s.ni+s.no+s.nw;
 if(s.special!=integrated::Special::normal||s.fused_combine_norm||s.g.h!=2560||(!select&&s.op!=integrated::Op::qsa_attention)||b.size()!=size_t(tail+5)||b.size()>31||s.nw||s.no!=1||s.ni<(select?2:5))throw std::invalid_argument("p116 QSA binding/geometry");
 ng::Shape shape{};shape.capacity=s.g.context;shape.extent=s.extent;shape.budget=s.g.budget;shape.op=select?ng::select:ng::attention_score;ng::validate(shape);
 std::array<ownrt::Allocation,20>a;a.fill(control);a[15]=b[tail+1];a[16]=b.back();a[17]=b[tail+2];a[18]=b[tail+3];a[19]=b[tail];
 if(select){a[0]=b[0];a[1]=b[1];a[2]=b[s.ni];}else{for(int i=0;i<5;++i)a[i]=b[i];a[5]=b[s.ni];a[6]=score;a[7]=probability;}
 auto need=ng::required_bytes(shape);for(int j=0;j<19;++j){const auto&r=d.arena.row(a[j]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<need[j])throw std::invalid_argument("p116 QSA allocation extent/lifetime");}
 const auto&scratch=d.arena.row(a[19]);size_t bytes=select?round2::scratch_floats(shape)*4:p49::scratch_bytes(shape);
 if(!scratch.live||scratch.memory!=ownrt::Memory::device||scratch.bytes<bytes||uintptr_t(scratch.pointer)%4)throw std::invalid_argument("p116 QSA scratch extent/alignment");
 for(int j=0;j<19;++j)if(a[j]==a[19])throw std::invalid_argument("p116 scratch aliases binding");
 for(int j:{0,1,2,3,4,15,17,18}){if(select&&(j==2||j==3||j==4))continue;if(a[j]==a[select?2:5])throw std::invalid_argument("p116 output alias");}
 for(int j:{0,1,2,15,17,18})if(select&&uintptr_t(d.arena.row(a[j]).pointer)%4)throw std::invalid_argument("p116 selection binding alignment");
 integrated::Launch out{};auto issue=[&]<bool Select,int Stage>(){Kernel<Select,Stage> k;k.s=shape;std::array<ownrt::Event,1>after{out.last};auto e=d.compute(k,a,out.last?std::span<const ownrt::Event>(after):deps);if(!out.first)out.first=e;out.last=e;++out.passes;};
 if(select){issue.template operator()<true,0>();issue.template operator()<true,1>();}else{issue.template operator()<false,0>();issue.template operator()<false,1>();issue.template operator()<false,2>();}return out;
}
}
