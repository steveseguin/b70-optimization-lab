#pragma once
#include "../packet33-codegen/candidates.hpp"
#include "../packet29-merged/p28/submit.hpp"
#include "../packet29-merged/specialised_submit.hpp"
#include "../packet29-merged/round2_submit.hpp"
namespace p42parallel {
template<iq3::Type T,unsigned K=6144> inline std::array<float,4> dense_parts(const uint8_t* __restrict w,const uint16_t* __restrict x,unsigned lane){
 std::array<float,4> out{};
 #pragma unroll
 for(unsigned p=0;p<4;++p){auto b=iq3::kopt2::bounds(K,p,4);out[p]=p33::dense_lane<T,K>(w,x,unsigned(b.first),unsigned(b.second),lane);}return out;
}
// Normalization retains exactly the incumbent rounded FP32 division before
// comparing. Integer comparison counts may be partitioned without changing rank.
template<unsigned N=512> inline unsigned rank_lane(const float* ex,float den,unsigned j,unsigned lane){
 float v=ex[j]/den;unsigned rank=0;
 for(unsigned k=lane;k<N;k+=32){float x=ex[k]/den;rank+=x>v||(x==v&&k<j);}return rank;
}
template<class Guard> inline void route_host(ng::Shape s,ng::Args a,float* scratch,Guard guard){
 for(size_t i=0;i<specialised::work_items(s,0);++i)specialised::body<ng::route_gather,0>(s,a,i,scratch,guard);
 for(size_t i=0;i<specialised::work_items(s,1);++i)specialised::body<ng::route_gather,1>(s,a,i,scratch,guard);
 if(a.i(18)[0]&&!guard.error(a))for(int r=0;r<s.tokens;++r){int C=specialised::ceildiv(s.width,32);float* sums=scratch+r*(2*C+2*s.width+s.extra)+C;float* ex=sums+C;float* selected=ex+2*s.width;float den=specialised::upper(sums,C);
  for(int j=0;j<s.width;++j){float v=ex[j]/den;unsigned rank=0;
   for(int lane=0;lane<32;++lane)for(int k=lane;k<s.width;k+=32){float x=ex[k]/den;rank+=x>v||(x==v&&k<j);}
   if(rank<unsigned(s.extra)){a.i(2)[r*s.extra+rank]=j;selected[rank]=v;for(int k=0;k<3;++k){a.i(5)[(r*s.extra+rank)*3+k]=k==0?j:k==1?0:640;a.i(6)[(r*s.extra+rank)*3+k]=k==0?j:k==1?0:2560;}}
  }
 }
 for(size_t i=0;i<specialised::work_items(s,4);++i)specialised::body<ng::route_gather,4>(s,a,i,scratch,guard);
}
inline void gdn_host(ng::Shape s,ng::Args a){
 if(s.tokens!=1)throw std::invalid_argument("gdn token1 gate");
 if(!a.i(18)[0]||a.i(15)[0])return;int pos=a.i(17)[0];if(pos<0||pos>s.capacity-1){a.i(15)[0]=1;return;}
 for(int g=0;g<6144;++g){int h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128,qb=key*128,kb=qb+2048;float q[32][4],k[32][4],v[32][4],qs[32]{},ks[32]{},pred[32]{},y[32]{};
  for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z){q[lane][z]=a.b(0,qb+4*lane+z);k[lane][z]=a.b(0,kb+4*lane+z);qs[lane]=qs[lane]+q[lane][z]*q[lane][z];ks[lane]=ks[lane]+k[lane][z]*k[lane][z];}
  float qn=detmath::sqrt(iq3::tree32(qs)+1e-6f),kn=detmath::sqrt(iq3::tree32(ks)+1e-6f);float gate=a.b(1,h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));float decay=detmath::exp(av*sp);
  for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z){q[lane][z]=(q[lane][z]/qn)/detmath::sqrt(float(128));k[lane][z]=k[lane][z]/kn;v[lane][z]=a.b(5,state+4*lane+z)*decay;pred[lane]=pred[lane]+v[lane][z]*k[lane][z];}
  float delta=(a.b(0,4096+h*128+j)-iq3::tree32(pred))*ng::sigmoid(a.b(2,h));
  for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z){v[lane][z]=v[lane][z]+delta*k[lane][z];y[lane]=y[lane]+v[lane][z]*q[lane][z];}
  a.put(6,h*128+j,iq3::tree32(y));for(int lane=0;lane<32;++lane)for(int z=0;z<4;++z)a.put(7,state+4*lane+z,v[lane][z]);
 }
}
integrated::Launch submit_dense(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned);
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
