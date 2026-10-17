#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/p49d_route.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Packet54: schedule independent exact route operations in fewer rank groups.
// Production arithmetic, scratch layout and admission belong to packet49c.
// Its selected p51 route body is namespace-identical; use the p45 type tree
// shared by the standalone fixture. The build verifies that source identity.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/p49c_kernel.hpp"

namespace p49droute {
using Args = route42::Args;

inline void control_host(Args a) {
  for (unsigned i = 0; i < 32; ++i) route42::phase<0,512,10>(a,i);
  p49c::route_exp_host(a);
  p49c::route_rank_host(a);
  route42::phase<4,512,10>(a,0);
}

// Mirrors the device's four independent rank accumulators, retaining each
// accumulator's lane walk and SG32 integer reduction. No early rank cutoff.
template<unsigned Reuse=4> inline void rank_host(Args a) {
  static_assert(Reuse==4);
  if (!*a.active || a.failed()) return;
  for (unsigned group=0; group<64/Reuse; ++group) {
    float cached[512];
    float den=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
    for (unsigned j=0;j<512;++j) cached[j]=a.scratch[64+j]/den;
    for (unsigned sg=0;sg<8;++sg) {
      unsigned ranks[Reuse][32]{};
      for(unsigned lane=0;lane<32;++lane)
        for(unsigned k=lane;k<512;k+=32)
          for(unsigned r=0;r<Reuse;++r) {
            unsigned index=group*(8*Reuse)+r*8+sg;
            ranks[r][lane]+=cached[k]>cached[index] ||
                              (cached[k]==cached[index] && k<index);
          }
      for(unsigned width=1;width<32;width*=2)
        for(unsigned lane=0;lane<32;lane+=2*width)
          for(unsigned r=0;r<Reuse;++r) ranks[r][lane]+=ranks[r][lane+width];
      for(unsigned r=0;r<Reuse;++r)
        route42::output<512,10>(a,group*(8*Reuse)+r*8+sg,ranks[r][0]);
    }
  }
}

template<unsigned Reuse=4,unsigned ExpWG=256> inline void host(Args a) {
  static_assert(Reuse==4 && (ExpWG==32 || ExpWG==256));
  for(unsigned i=0;i<32;++i) route42::phase<0,512,10>(a,i);
  // The same exp/sum arithmetic; geometry has no host analogue.
  p49c::route_exp_host(a);
  rank_host<Reuse>(a);
  route42::phase<4,512,10>(a,0);
}

template<unsigned Stage,unsigned Reuse=4,unsigned ExpWG=256>
struct Kernel final : p49c::Base {
  static_assert((Stage==1 || Stage==2) && Reuse==4 &&
                (ExpWG==32 || ExpWG==256));
  integrated::Spec spec;
#ifdef OWN_RT_HOST_ONLY
  void run(std::span<void*const> p) const override {
    auto a=route42::bind(spec,p);
    if constexpr(Stage==1) p49c::route_exp_host(a);
    else rank_host<Reuse>(a);
  }
#else
  sycl::event submit(sycl::queue& q,std::span<void*const> p,
                     const std::vector<sycl::event>& deps) const override {
    auto a=route42::bind(spec,p);
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(512,ExpWG),p35_range1=sycl::nd_range<1>((64/Reuse)*256,256)](sycl::handler& h) {
      
      if constexpr(Stage==1) {
        // Retain the production ordered maximum scan and 16-value subtree.
        // ExpWG=32 distributes the 16 expensive exp subgroups over 16 WGs;
        // ExpWG=256 is the identical production 2-WG stage.
        sycl::local_accessor<float,1> maximum(1,h);
        h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)
                         [[sycl::reqd_sub_group_size(32)]] {
          if(!*a.active || a.failed()) return;
          unsigned j=it.get_global_linear_id();
          if(it.get_local_linear_id()==0) {
            float value=-INFINITY;
            for(unsigned chunk=0;chunk<32;++chunk)
              value=std::max(value,a.scratch[chunk]);
            maximum[0]=value;
          }
          it.barrier(sycl::access::fence_space::local_space);
          float value=detmath::exp(a.in().get(j)-maximum[0]);
          a.scratch[64+j]=value;
          auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
          for(unsigned width=1;width<16;width*=2) {
            float rhs=sycl::select_from_group(sg,value,(lane+width)%32);
            if(lane%(2*width)==0) value=value+rhs;
          }
          if(lane%16==0) a.scratch[32+j/16]=value;
        }));
      } else {
        sycl::local_accessor<float,1> cached(513,h);
        h.parallel_for(p35_range1,
                       packet26::checked([=](sycl::nd_item<1> it)
                         [[sycl::reqd_sub_group_size(32)]] {
          if(!*a.active || a.failed()) return;
          unsigned local=it.get_local_linear_id(),lane=local%32;
          unsigned base=it.get_group_linear_id()*(8*Reuse)+local/32;
          if(local==0)
            cached[512]=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
          it.barrier(sycl::access::fence_space::local_space);
          for(unsigned j=local;j<512;j+=256)
            cached[j]=a.scratch[64+j]/cached[512];
          it.barrier(sycl::access::fence_space::local_space);
          float values[Reuse];unsigned ranks[Reuse]{};
          #pragma unroll
          for(unsigned r=0;r<Reuse;++r) values[r]=cached[base+r*8];
          // Load each competitor once, while preserving all 16 ordered
          // comparisons in each lane's original integer accumulator.
          for(unsigned k=lane;k<512;k+=32) {
            float other=cached[k];
            #pragma unroll
            for(unsigned r=0;r<Reuse;++r)
              ranks[r]+=other>values[r] || (other==values[r] && k<base+r*8);
          }
          auto sg=it.get_sub_group();
          for(unsigned width=1;width<32;width*=2) {
            #pragma unroll
            for(unsigned r=0;r<Reuse;++r) {
              unsigned rhs=sycl::select_from_group(sg,ranks[r],(lane+width)%32);
              if(lane%(2*width)==0) ranks[r]+=rhs;
            }
          }
          if(!lane) {
            #pragma unroll
            for(unsigned r=0;r<Reuse;++r)
              route42::output<512,10>(a,base+r*8,ranks[r]);
          }
        }));
      }
    });
  }
#endif
};

// The packet49c route ABI checks are reproduced without loosening any gate.
// Explicit ni=3 error/active inputs may intentionally alias their tail copies.
inline void validate(ownrt::Device& d,const integrated::Spec& s,
                     std::span<const ownrt::Allocation> a) {
  unsigned tail=s.ni+s.no+s.nw;
  if(s.op!=integrated::Op::route || s.special!=integrated::Special::normal ||
     s.sizes[0]!=512 || s.site.shape[1]!=10 || s.nw ||
     !(s.ni==1 || s.ni==3) || !(s.no==2 || s.no==4) || a.size()!=tail+5)
    throw std::invalid_argument("p54 route ABI");
  for(unsigned j=0;j<a.size();++j) {
    const auto& r=d.arena.row(a[j]);
    size_t n=j<tail?s.sizes[j]*flash::scalar_bytes(s.types[j]):
             j==tail?(64+1024)*4:j==tail+4?1:4;
    if(!r.live || r.memory!=ownrt::Memory::device || r.bytes<n || uintptr_t(r.pointer)%4)
      throw std::invalid_argument("p54 route extent/alignment");
  }
  for(unsigned j=0;j<s.no;++j) {
    if(s.sizes[s.ni+j]<(j<2?10u:30u)) throw std::invalid_argument("p54 route output extent");
    for(unsigned k=0;k<a.size();++k)
      if(k!=s.ni+j && a[s.ni+j]==a[k]) throw std::invalid_argument("p54 route output alias");
  }
  for(unsigned j=tail;j<tail+4;++j)
    for(unsigned k=tail;k<j;++k)
      if(a[j]==a[k]) throw std::invalid_argument("p54 route scratch/control alias");
  for(unsigned j=0;j<tail;++j)
    if(a[j]==a[tail]) throw std::invalid_argument("p54 route scratch alias");
}

template<unsigned Reuse=4,unsigned ExpWG=256>
inline integrated::Launch submit(ownrt::Device& d,const integrated::Spec& s,
                                std::span<const ownrt::Allocation> a,
                                std::span<const ownrt::Event> deps={}) {
  static_assert(Reuse==4 && (ExpWG==32 || ExpWG==256));
  validate(d,s,a);
  integrated::Launch result{};
  auto issue=[&]<unsigned Stage>() {
    // Keep stages 0/4 literally on production operations. In particular,
    // Stage0's sticky failure and partially written scratch are unchanged.
    using Op=std::conditional_t<Stage==0 || Stage==4,p49c::RouteKernel<Stage>,
                                Kernel<Stage,Reuse,ExpWG>>;
    Op op;op.spec=s;
    std::array after{result.last};
    auto e=d.compute(op,a,result.last?std::span<const ownrt::Event>(after):deps);
    if(!result.first) result.first=e;
    result.last=e;++result.passes;
  };
  issue.template operator()<0>();issue.template operator()<1>();
  issue.template operator()<2>();issue.template operator()<4>();
  return result;
}
} // namespace p49droute
