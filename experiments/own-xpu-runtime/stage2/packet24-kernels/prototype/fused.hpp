#pragma once
#include "snapshot/kernels.hpp"
namespace fusion {
struct Site {ng::Shape shape;ng::Args args;int groups;Site(ng::Shape s,ng::Args a):shape(s),args(a),groups(ng::groups(s)) {ng::validate(s);}};
// Exact construction for rule (i). ONE work-group owns every phase and every
// original group. A work-group barrier is therefore also a whole-launch barrier.
// This is a correctness prototype, not a claim that serializing GDN is fast.
template<class Team> void chain(const Site* sites,int count,Team t){
 for(int j=0;j<count;++j){const auto s=sites[j];
  for(int g=0;g<s.groups;++g){ng::group(s.shape,s.args,g,t);t.barrier();}
 }
}
inline void cpu_chain(const Site* sites,int count){
 int local=1;for(int j=0;j<count;++j){ng::validate(sites[j].shape);local=std::max(local,ng::local_floats(sites[j].shape));}
 std::vector<float> scratch(local);chain(sites,count,ng::HostTeam{scratch.data()});
}
// Two launches, rank sharded across four groups per token. Each rank group
// recomputes the original maximum/exp/adjacent sum (no changed arithmetic).
// This deliberate duplication removes a synchronization launch. No input row
// is copied. p4 stays untouched; downstream GEMV reads input row r directly.
template<class Team> void route_rank(ng::Shape s,ng::Args a,float* selected,int gid,Team t){
 const int r=gid/4,shard=gid%4,n=s.width,top=s.extra;
 t.each(1,[&](int){t.x[0]=float(!a.i(15)[1]||t.error(a));});t.barrier();if(t.x[0])return;t.barrier();
 if(a.i(15)[0]<0||a.i(15)[0]>s.capacity-s.tokens){if(gid==0)t.each(1,[&](int){t.fail(a);});return;}
 float maximum=-INFINITY;bool finite=true;
 for(int j=0;j<n;++j){float v=a.b(0,r*n+j);finite=finite&&std::isfinite(v);maximum=std::max(maximum,v);}
 if(!finite){t.each(1,[&](int){t.fail(a);});return;}
 t.each(n,[&](int j){t.x[j]=detmath::exp(a.b(0,r*n+j)-maximum);t.x[512+j]=t.x[j];});t.barrier();
 float den=t.sum(n);t.barrier();t.each(n,[&](int j){t.x[512+j]=t.x[512+j]/den;});t.barrier();
 t.each((n+3)/4,[&](int offset){int j=offset*4+shard;if(j>=n)return;
  int rank=0;float v=t.x[512+j];for(int k=0;k<n;++k)rank+=t.x[512+k]>v||(t.x[512+k]==v&&k<j);
  if(rank<top){a.i(2)[r*top+rank]=j;selected[r*top+rank]=v;
   a.i(5)[(r*top+rank)*3]=j;a.i(5)[(r*top+rank)*3+1]=0;a.i(5)[(r*top+rank)*3+2]=640;
   a.i(6)[(r*top+rank)*3]=j;a.i(6)[(r*top+rank)*3+1]=0;a.i(6)[(r*top+rank)*3+2]=2560;}
 });
}
template<class Team> void route_finish(ng::Shape s,ng::Args a,const float* selected,int r,Team t){
 t.each(1,[&](int){t.x[0]=float(!a.i(15)[1]||t.error(a));});t.barrier();if(t.x[0])return;t.barrier();
 t.each(s.extra,[&](int j){t.x[j]=selected[r*s.extra+j];});t.barrier();float den=t.sum(s.extra);t.barrier();
 t.each(s.extra,[&](int j){a.f(3)[r*s.extra+j]=selected[r*s.extra+j]/den;});
}
inline void cpu_route(ng::Shape s,ng::Args a){ng::validate(s);if(s.op!=ng::route_gather)throw std::invalid_argument("route only");
 std::vector<float> scratch(2048),selected(s.tokens*s.extra);
 for(int g=0;g<4*s.tokens;++g)route_rank(s,a,selected.data(),g,ng::HostTeam{scratch.data()});
 for(int r=0;r<s.tokens;++r)route_finish(s,a,selected.data(),r,ng::HostTeam{scratch.data()});
}
// Fused score/softmax/value: per-head work-group owns all its scratch. Exactly
// the original ng::group trees are reused, including unselected-slot writes.
template<class Team> void attention(ng::Shape s,ng::Args a,int head,Team t){
 int slots=std::min(s.capacity,s.budget+3);
 // Every work-group checks every row before producing anything. There is no
 // dependence on another group discovering a bad slot late. Invalid requests
 // fail closed; partially written diagnostic score scratch is not an oracle.
 t.each(1,[&](int){bool bad=false;for(int r=0;r<s.tokens;++r)for(int j=0;j<slots;++j){int id=a.i(4)[r*(s.budget+3)+j];bad=bad||id>=s.capacity||id>a.i(15)[0]+r;}t.x[0]=float(bad);if(bad&&a.i(15)[1])t.fail(a);});t.barrier();if(t.x[0])return;t.barrier();
 s.op=ng::attention_score;
 for(int j=0;j<slots;++j){ng::group(s,a,head*slots+j,t);t.barrier();}
 s.op=ng::attention_softmax;ng::group(s,a,head,t);t.barrier();
 s.op=ng::attention_value;for(int k=0;k<256;++k){ng::group(s,a,head*256+k,t);t.barrier();}
}
inline void cpu_attention(ng::Shape s,ng::Args a){std::vector<float>x(std::max(1024,s.budget+3));for(int h=0;h<s.tokens*24;++h)attention(s,a,h,ng::HostTeam{x.data()});}
}
