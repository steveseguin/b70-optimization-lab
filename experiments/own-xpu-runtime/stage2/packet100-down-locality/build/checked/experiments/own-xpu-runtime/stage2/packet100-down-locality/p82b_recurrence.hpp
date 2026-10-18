#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/p82b_recurrence.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/build/checked/experiments/own-xpu-runtime/stage2/packet100-down-locality/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/build/checked/experiments/own-xpu-runtime/stage2/packet100-down-locality/p49d_recurrence.hpp"
namespace p82brec {
// 0: run, 1: preserve inactive/sticky-error bytes, 2: record invalid position.
// This integer-only predicate is also exercised by the host fixture.
inline int entry_decision(int active,int error,int pos,int capacity,int tokens) {
 if(!active||error)return 1;
 return pos<0||pos>capacity-tokens?2:0;
}
// CPU scheduling mirror separately computes the two independent norm trees and
// gates, then the unchanged four-row update. Token state always rereads BF16.
template<bool SplitNorm> inline void host(ng::Shape s,ng::Args a) {
 const int decision=entry_decision(a.i(18)[0],a.i(15)[0],a.i(17)[0],s.capacity,s.tokens);
 if(decision){if(decision==2)a.i(15)[0]=1;return;}
 for(unsigned base=0;base<6144;base+=4)for(int r=0;r<s.tokens;++r) {
  const unsigned h=base/128,key=(s.flags&4)?h%16:h/3,qb=r*10240+key*128,kb=qb+2048;
  float shared[258];
  // Same operations as each device producer, evaluated in dependency order on CPU.
  for(unsigned role=0;role<2;++role){float val[128],leaf[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=4*lane+z;val[x]=a.b(0,(role?kb:qb)+x);leaf[lane]=leaf[lane]+val[x]*val[x];}
   const float norm=detmath::sqrt(p49drec::recurrence_tree(leaf)+1e-6f);
   for(unsigned x=0;x<128;++x)shared[role*128+x]=role?val[x]/norm:(val[x]/norm)/detmath::sqrt(float(128));
  }
  const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
  const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
  const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
  shared[256]=detmath::exp(av*sp);shared[257]=ng::sigmoid(a.b(2,r*48+h));
  for(unsigned row=0;row<4;++row){unsigned g=base+row,state=g*128;float v[128],pred[32]{},y[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=a.b(r?7:5,state+x)*shared[256];pred[lane]=pred[lane]+v[x]*shared[128+x];}
   const float delta=(a.b(0,r*10240+4096+g)-p49drec::recurrence_tree(pred))*shared[257];
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=v[x]+delta*shared[128+x];y[lane]=y[lane]+v[x]*shared[x];}
   a.put(6,r*6144+g,p49drec::recurrence_tree(y));for(unsigned x=0;x<128;++x)a.put(7,state+x,v[x]);
  }
 }
}
#ifndef OWN_RT_HOST_ONLY
template<bool SplitNorm> inline void device(ng::Shape s,ng::Args a,
 sycl::nd_item<1> it,float* shared) {
 const unsigned lid=it.get_local_linear_id(),lane=lid%32,row=lid/32;
 const unsigned base=it.get_group_linear_id()*4,g=base+row;
 const unsigned h=base/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
 const auto sg=it.get_sub_group();
 // Position/active are immutable for this submission. The only writer of
 // sticky error in this kernel is the invalid-position path, which returns
 // before any rendezvous on every subgroup. For a valid position, no writer
 // exists, so all subgroup leaders observe the same entry decision. Prior
 // operations complete through the unchanged submission dependencies.
 // Thus no workgroup-wide SLM exchange/barrier is needed for the guard.
 int decision=0;
 if(lane==0)decision=entry_decision(a.i(18)[0],p49drec::recurrence_error(a),a.i(17)[0],s.capacity,s.tokens);
 decision=sycl::select_from_group(sg,decision,sycl::id<1>(0));
 if(decision){if(decision==2&&base==0&&lid==0)p49drec::recurrence_fail(a);return;}
 for(int r=0;r<s.tokens;++r) {
  const unsigned qb=r*10240+key*128,kb=qb+2048;
  if constexpr(SplitNorm) {
   if(row<2) {
    float values[4],sum=0.f;
    for(unsigned z=0;z<4;++z){values[z]=a.b(0,(row?kb:qb)+4*lane+z);sum=sum+values[z]*values[z];}
    sum=p49drec::recurrence_tree_device(sg,sum);
    const float norm=detmath::sqrt(sum+1e-6f);
    for(unsigned z=0;z<4;++z)shared[row*128+4*lane+z]=row?values[z]/norm:(values[z]/norm)/detmath::sqrt(float(128));
   }
  } else {
  if(row==0) {
   float q[4],k[4],qs=0.f,ks=0.f;
   for(unsigned z=0;z<4;++z) {
    q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);
    qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];
   }
   p49drec::recurrence_norm_trees(sg,qs,ks);
   const float qn=detmath::sqrt(qs+1e-6f),kn=detmath::sqrt(ks+1e-6f);
   for(unsigned z=0;z<4;++z) {
    shared[4*lane+z]=(q[z]/qn)/detmath::sqrt(float(128));
    shared[128+4*lane+z]=k[z]/kn;
   }
  }
  }
  // Independent producer subgroups; every expression and FP32 boundary is unchanged.
  if(row==(SplitNorm?2u:1u)&&lane==0) {
   const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
   const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   shared[256]=detmath::exp(av*sp);
  }
  if(row==(SplitNorm?3u:2u)&&lane==0)shared[257]=ng::sigmoid(a.b(2,r*48+h));
  it.barrier(sycl::access::fence_space::local_space);
  float q[4],k[4],v[4],pred=0.f;
  const float decay=shared[256],beta=shared[257];
  sycl::vec<uint16_t,4> raw;
  raw.load(0,static_cast<const uint16_t*>(a.p[r?7:5])+state+lane*4);
  for(unsigned z=0;z<4;++z) {
   q[z]=shared[lane*4+z];k[z]=shared[128+lane*4+z];
   v[z]=std::bit_cast<float>(uint32_t(raw[z])<<16)*decay;
   pred=pred+v[z]*k[z];
  }
  pred=p49drec::recurrence_tree_device(sg,pred);
  const float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*beta;
  float y=0.f;
  for(unsigned z=0;z<4;++z) {
   v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];raw[z]=ng::Args::bits(v[z]);
  }
  y=p49drec::recurrence_tree_device(sg,y);if(lane==0)a.put(6,(r*48+h)*128+j,y);
  raw.store(0,static_cast<uint16_t*>(a.p[7])+state+lane*4);
  // Token r+1 consumes the rounded BF16 bytes. Never carry FP32 state across
  // token rows. This also prevents the producer SG overwriting shared q/k while
  // another SG still consumes the previous token's shared values.
  if(r+1<s.tokens)it.barrier(sycl::access::fence_space::global_and_local);
 }
}
#endif
template<bool SplitNorm> struct Kernel final:p49drec::RecurrenceBase {

 ng::Shape shape{};
 static ng::Args bind(std::span<void*const> p) {
  if(p.size()!=19)throw std::invalid_argument("p54 recurrence binding count");
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());return a;
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {host<SplitNorm>(shape,bind(p));}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const auto a=bind(p);const auto s=shape;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(6144*32,128)](sycl::handler& handler) {
   sycl::local_accessor<float,1> shared(258,handler);
   handler.parallel_for(p35_range0,
    packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]] {
     device<SplitNorm>(s,a,it,shared.get_multi_ptr<sycl::access::decorated::no>().get());
    }));
  });
 }
#endif
};

}
