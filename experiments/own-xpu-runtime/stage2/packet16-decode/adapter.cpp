#include "adapter.hpp"
#include "../packet15-nongemv/kernels.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "../packet15-nongemv/native.hpp"
#include "sycl_operation.hpp"
#endif
namespace packet16 {
using namespace integrated;
namespace {
struct Bound {
 Spec s;std::array<void*,32> p;
 View in(int j)const{return {p[j],s.sizes[j],s.types[j]};}
 View out(int j)const{int k=s.ni+j;return {p[k],s.sizes[k],s.types[k]};}
 int tail()const{return s.ni+s.no+s.nw;}
 uint32_t* error()const{return static_cast<uint32_t*>(p[tail()+1]);}
 uint32_t* position()const{return static_cast<uint32_t*>(p[tail()+2]);}
 uint32_t* active()const{return static_cast<uint32_t*>(p[tail()+3]);}
};
// Tiny geometry has the same equations, with dimensions taken from its plan.
// Keep these parallel as well: synthetic integration tests do not silently
// select the single_task exactness control.
template<class Team> void tiny(Bound b,int group,Team t) {
 const auto s=b.s;const auto g=s.g;if(!*b.active()||*b.error())return;
 auto bf=[](float x){return ng::Args::bf(x);};
 auto weight=[&](int w,int k){return iq3::element(s.grids[w],static_cast<const uint8_t*>(b.p[s.ni+s.no+w]),k);};
 auto tree=[&](int n,auto value){return ng::tree(t,n,value);};
 auto rope=[&](auto value,auto store,int width,int w,int pos){
  float inv=1.f/std::sqrt(tree(width,[&](int k){float v=value(k);return v*v;})/float(width)+1e-6f);t.barrier();
  t.each(width,[&](int k){t.x[k]=bf((value(k)*inv)*weight(w,k));});t.barrier();
  t.each(width,[&](int k){float v=t.x[k];if(k<g.rotary){int j=k%(g.rotary/2);float angle=float(pos)*std::pow(1e7f,-float(2*j)/float(g.rotary)),c=bf(std::cos(angle)),z=bf(std::sin(angle));v=k<g.rotary/2?t.x[j]*c-t.x[j+g.rotary/2]*z:t.x[j]*z+t.x[j+g.rotary/2]*c;}store(k,v);});t.barrier();
 };
 if(s.op==Op::gdn){
  int h=group/g.d,j=group%g.d,key=s.packed_heads?h%g.kh:h/(g.vh/g.kh),qb=key*g.d,kb=qb+g.kh*g.d;
  float qn=std::sqrt(tree(g.d,[&](int k){float x=b.in(0).get(qb+k);return x*x;})+1e-6f);t.barrier();
  float kn=std::sqrt(tree(g.d,[&](int k){float x=b.in(0).get(kb+k);return x*x;})+1e-6f);t.barrier();
  float gate=b.in(1).get(h)+weight(1,h),sp=gate<20.f?std::log(1.f+std::exp(gate)):gate,decay=std::exp(weight(0,h)*sp);int base=(h*g.d+j)*g.d;
  float pred=tree(g.d,[&](int k){return (b.in(3).get(base+k)*decay)*(b.in(0).get(kb+k)/kn);});t.barrier();
  float delta=(b.in(0).get(2*g.kh*g.d+h*g.d+j)-pred)*ng::sigmoid(b.in(2).get(h));
  auto row=[&](int k){return b.in(3).get(base+k)*decay+delta*(b.in(0).get(kb+k)/kn);};
  float y=tree(g.d,[&](int k){return row(k)*((b.in(0).get(qb+k)/qn)/std::sqrt(float(g.d)));});t.barrier();
  t.each(1,[&](int){b.out(0).put(group,y);});t.each(g.d,[&](int k){b.out(1).put(base+k,row(k));});
 }else if(s.op==Op::gdn_norm_gate){
  int base=group*g.d;float inv=1.f/std::sqrt(tree(g.d,[&](int k){float x=b.in(0).get(base+k);return x*x;})/float(g.d)+1e-6f);t.barrier();
  t.each(g.d,[&](int k){b.out(0).put(base+k,((b.in(0).get(base+k)*inv)*weight(0,k))*ng::sigmoid(b.in(1).get(base+k)));});
 }else if(s.op==Op::qsa_prepare){
  int pos=*b.position();if(group<g.qh){int base=group*2*g.ad;rope([&](int k){return b.in(0).get(base+k);},[&](int k,float v){b.out(0).put(group*g.ad+k,v);b.out(1).put(group*g.ad+k,b.in(0).get(base+g.ad+k));},g.ad,0,pos);}
  else if(group<g.qh+g.kvh){int h=group-g.qh;rope([&](int k){return b.in(1).get(h*g.ad+k);},[&](int k,float v){b.out(2).put(h*g.ad+k,v);},g.ad,1,pos);}
  else {int h=group-g.qh-g.kvh;rope([&](int k){return b.in(2).get(h*g.id+k);},[&](int k,float v){b.out(3).put(h*g.id+k,v);},g.id,2,pos);}
 }else if(s.op==Op::qsa_append_pool){
  int pos=*b.position(),pools=(g.context+3)/4;
  if(group==pools){t.each(g.kvh*g.ad,[&](int k){b.out(0).put(pos*g.kvh*g.ad+k,b.in(0).get(k));b.out(1).put(pos*g.kvh*g.ad+k,b.in(1).get(k));});t.each(g.id,[&](int k){b.out(2).put(pos*g.id+k,b.in(2).get(k));});}
  else if(group==(pos/4)&&(pos+1)%4==0){auto pooled=[&](int k){float x=0;for(int j=0;j<4;++j){int r=group*4+j;x=x+(r<pos?b.out(2).get(r*g.id+k):b.in(2).get(k));}return bf(x/4.f);};rope(pooled,[&](int k,float v){b.out(3).put(group*g.id+k,v);},g.id,0,group*4);}
 }else if(s.op==Op::qsa_select){
  int pos=*b.position(),n=(pos+1)/4,base=2*((g.context+3)/4);
  for(int h=0;h<g.ih;++h)for(int block=0;block<n;++block){float score=ng::tree(t,g.id,[&](int k){return b.in(0).get(h*g.id+k)*b.in(1).get(block*g.id+k);},base);t.barrier();t.each(1,[&](int){t.x[block]=(h?t.x[block]:0.f)+std::max(0.f,score);});t.barrier();}
  t.each(n,[&](int k){t.x[k]=t.x[k]/std::sqrt(float(g.id));});t.barrier();int count=std::min(n,g.budget/4);
  t.each(g.budget+3,[&](int j){b.out(0).put(j,-1);});t.barrier();t.each(n,[&](int block){int rank=0;for(int k=0;k<n;++k)rank+=t.x[k]>t.x[block]||(t.x[k]==t.x[block]&&k<block);if(rank<count)for(int j=0;j<4;++j)b.out(0).put(rank*4+j,block*4+j);});
  t.each(pos+1-n*4,[&](int j){b.out(0).put(count*4+j,n*4+j);});
 }else if(s.op==Op::qsa_attention){
  int h=group,kh=h/(g.qh/g.kvh),n=0;while(n<int(b.in(4).n)&&b.in(4).get(n)>=0)++n;int base=g.budget+3;
  for(int j=0;j<n;++j){int id=int(b.in(4).get(j));float score=ng::tree(t,g.ad,[&](int k){return b.in(2).get((id*g.kvh+kh)*g.ad+k)*b.in(0).get(h*g.ad+k);},base)/std::sqrt(float(g.ad));t.barrier();t.each(1,[&](int){t.x[j]=score;});t.barrier();}
  float maximum=-INFINITY;for(int j=0;j<n;++j)maximum=std::max(maximum,t.x[j]);t.each(n,[&](int j){t.x[j]=std::exp(t.x[j]-maximum);t.x[base+j]=t.x[j];});t.barrier();float den=t.sum(n,base);t.barrier();t.each(n,[&](int j){t.x[j]=t.x[j]/den;});t.barrier();
  for(int k=0;k<g.ad;++k){float value=ng::tree(t,n,[&](int j){int id=int(b.in(4).get(j));return t.x[j]*b.in(3).get((id*g.kvh+kh)*g.ad+k);},base);t.barrier();t.each(1,[&](int){b.out(0).put(h*g.ad+k,bf(value)*ng::sigmoid(b.in(1).get(h*g.ad+k)));});t.barrier();}
 }
}
int tiny_groups(const Spec& s){switch(s.op){case Op::gdn:return s.g.vh*s.g.d;case Op::gdn_norm_gate:return s.g.vh;case Op::qsa_prepare:return s.g.qh+s.g.kvh+s.g.ih;case Op::qsa_append_pool:return (s.g.context+3)/4+1;case Op::qsa_attention:return s.g.qh;default:return 1;}}
// Remaining integration sites are direct data-parallel translations of Core.
// Reduction order is the same adjacent binary tree, including odd zero padding.
template<class Team> void simple(Bound b,int group,Team t) {
 auto s=b.s;auto bf=[](float x){return ng::Args::bf(x);};
 if(!*b.active())return;
 if(s.special==Special::begin){t.each(1,[&](int){if(*b.position()>=unsigned(s.g.context))*b.error()=1;});return;}
 if(*b.error())return;
 if(s.special==Special::commit){t.each(1,[&](int){++*b.position();});return;}
 if(s.special==Special::broadcast){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j%b.in(0).n));});return;}
 if(s.special==Special::check_status){
  float failed=ng::tree(t,int(b.in(0).n),[&](int j){return float(b.in(0).get(j)!=0);});t.barrier();
  t.each(1,[&](int){if(failed)*b.error()=1;});return;
 }
 if(s.special==Special::ple_hash){t.each(1,[&](int){
  auto history=static_cast<int64_t*>(b.in(1).p),meta=static_cast<int64_t*>(b.in(2).p),ids=static_cast<int64_t*>(b.out(0).p);
  int64_t token=static_cast<int32_t*>(b.in(0).p)[0],old0=history[0],old1=history[1];if(old1==s.g.eos)old0=s.g.eos;
  for(int n=2;n<=3;++n){uint64_t hash=uint64_t(token)*uint64_t(meta[0]);hash^=uint64_t(old1)*uint64_t(meta[1]);if(n==3)hash^=uint64_t(old0)*uint64_t(meta[2]);auto v=std::bit_cast<int64_t>(hash);
   for(int h=0;h<8;++h){int j=(n-2)*8+h;auto size=meta[3+j];if(size<=0){*b.error()=1;return;}ids[j]=(v%size+size)%size+meta[19+j];}}
  history[0]=old1;history[1]=token;
 });return;}
 if(s.op==Op::hc_combine){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j)+b.in(1).get(j%s.site.shape[1])*(2.f*ng::sigmoid(b.in(2).get(j/s.site.shape[1])/4.f)));});}
 else if(s.op==Op::expert_gather){
  t.each(s.g.top,[&](int j){int id=int(b.in(0).get(j));if(id<0||id>=s.g.experts){t.x[j]=1;return;}t.x[j]=0;
   for(int k=0;k<3;++k){b.out(0).put(j*3+k,k==0?id:k==1?0:s.g.mid);b.out(1).put(j*3+k,k==0?id:k==1?0:s.g.h);}});t.barrier();
  float bad=t.sum(s.g.top);t.barrier();t.each(1,[&](int){if(bad)*b.error()=1;});
  if(bad)return;t.each(int(b.out(2).n),[&](int j){b.out(2).put(j,b.in(1).get(j%b.in(1).n));});
 }else if(s.op==Op::route){
  int n=int(b.in(0).n),top=s.site.shape[1];float maximum=-INFINITY;bool finite=true;
  for(int j=0;j<n;++j){float v=b.in(0).get(j);finite=finite&&std::isfinite(v);maximum=std::max(maximum,v);}
  if(!finite){t.each(1,[&](int){*b.error()=1;});return;}
  t.each(n,[&](int j){t.x[j]=std::exp(b.in(0).get(j)-maximum);t.x[n+j]=t.x[j];});t.barrier();float den=t.sum(n);t.barrier();
  t.each(n,[&](int j){t.x[n+j]=t.x[n+j]/den;});t.barrier();
  t.each(n,[&](int j){int rank=0;float v=t.x[n+j];for(int k=0;k<n;++k)rank+=t.x[n+k]>v||(t.x[n+k]==v&&k<j);if(rank<top){b.out(0).put(rank,j);t.x[2*n+rank]=v;t.x[2*n+top+rank]=v;}});t.barrier();
  float selected=t.sum(top,2*n);t.barrier();t.each(top,[&](int j){b.out(1).put(j,t.x[2*n+top+j]/selected);});
 }else if(s.op==Op::ple_gate){
  int width=s.g.h;float sum=ng::tree(t,width,[&](int k){return bf(b.in(0).get(group*width+k)*b.in(1).get(group*width+k));});t.barrier();
  float z=bf(bf(sum)/std::sqrt(float(width))),root=bf(std::sqrt(std::max(std::abs(z),1e-6f))),sign=z>0?1.f:z<0?-1.f:0.f,gate=bf(ng::sigmoid(bf(sign*root)));
  t.each(width,[&](int k){b.out(0).put(group*width+k,gate*b.in(2).get(k));});
 }else if(s.op==Op::ple_add){t.each(int(b.out(0).n),[&](int j){b.out(0).put(j,b.in(0).get(j)+bf(b.in(1).get(j)+b.in(2).get(j)));});}
 else if(s.op==Op::argmax){
  t.each(128,[&](int lane){int best=lane;bool finite=true;for(int j=lane;j<int(b.in(0).n);j+=128){float v=b.in(0).get(j);finite=finite&&std::isfinite(v);if(v>b.in(0).get(best))best=j;}t.x[lane]=lane<int(b.in(0).n)?float(best):-1.f;t.x[128+lane]=float(finite);});t.barrier();
  t.each(1,[&](int){int best=0;bool finite=true;for(int lane=0;lane<128;++lane){int j=int(t.x[lane]);finite=finite&&bool(t.x[128+lane]);if(j>=0&&(b.in(0).get(j)>b.in(0).get(best)||(b.in(0).get(j)==b.in(0).get(best)&&j<best)))best=j;}b.out(0).put(0,best);if(!finite)*b.error()=1;});
 }
}
#ifdef OWN_RT_HOST_ONLY
struct NgHost final:HostOperation{ng::Shape shape;explicit NgHost(ng::Shape s):shape(s){}void run(std::span<void*const> p)const override{ng::Args a;std::copy(p.begin(),p.end(),a.p.begin());ng::cpu(shape,a);}};
struct Glue final:HostOperation {
 Spec s;int mode;Glue(Spec v,int m):s(v),mode(m){}
 void run(std::span<void*const> p)const override{
  Bound b{s,{}};std::copy(p.begin(),p.end(),b.p.begin());auto ctrl=static_cast<int32_t*>(p.back());
  if(mode==1){ctrl[0]=*b.position();ctrl[1]=*b.active();ctrl[2]=*b.error();}
  else if(mode==2){if(ctrl[2])*b.error()=1;}
  else if(mode==3){std::vector<float> scratch(std::max(8192,s.g.h));for(int g=0;g<tiny_groups(s);++g)tiny(b,g,ng::HostTeam{scratch.data()});}
  else {std::vector<float> scratch(std::max(4096,s.g.h));int groups=s.special==Special::normal&&s.op==Op::ple_gate?4:1;for(int g=0;g<groups;++g)simple(b,g,ng::HostTeam{scratch.data()});}
 }
};
#else
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=it.get_local_range(0))f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
struct Glue final:ownrt::SyclOperation {
 Spec s;int mode;Glue(Spec v,int m):s(v),mode(m){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  Bound b{s,{}};std::copy(p.begin(),p.end(),b.p.begin());auto ctrl=static_cast<int32_t*>(p.back());auto mode_=mode;
  if(mode==1||mode==2)return q.submit([&](sycl::handler& h){h.depends_on(deps);h.single_task([=]{if(mode_==1){ctrl[0]=*b.position();ctrl[1]=*b.active();ctrl[2]=*b.error();}else if(mode_==2){if(ctrl[2])*b.error()=1;}});});
  int groups=mode==3?tiny_groups(s):s.special==Special::normal&&s.op==Op::ple_gate?4:1,local=std::max(8192,s.g.h);
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> scratch(local,h);h.parallel_for(sycl::nd_range<1>(groups*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto t=Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()};if(mode_==3)tiny(b,it.get_group_linear_id(),t);else simple(b,it.get_group_linear_id(),t);});});
 }
};
#endif
}
Launch submit_parallel(ownrt::Device& d,const Spec& s,std::span<const ownrt::Allocation> bindings,ownrt::Allocation control,ownrt::Allocation score,ownrt::Allocation probability,std::span<const ownrt::Event> deps){
 if(bindings.size()!=size_t(s.ni+s.no+s.nw+4)||bindings.size()>31)throw std::invalid_argument("adapter binding count");
 ng::Shape shape{};shape.capacity=s.g.context;shape.budget=s.g.budget;
 std::array<ownrt::Allocation,16> a;a.fill(control);a[15]=control;
 auto in=[&](int dst,int j){a[dst]=bindings[j];};auto out=[&](int dst,int j){a[dst]=bindings[s.ni+j];};auto weight=[&](int dst,int j){a[dst]=bindings[s.ni+s.no+j];};
 bool use_ng=s.special==Special::normal;
 if(s.nw){bool gdn=s.special==Special::normal&&s.op==Op::gdn;bool f32=s.grids[gdn?1:0]==iq3::Type::F32;for(int j=0;j<s.nw;++j)if((s.grids[j]==iq3::Type::F32)!=f32&&!(gdn&&j==0))throw std::invalid_argument("mixed non-GEMV gain encodings");if(gdn&&s.grids[0]!=iq3::Type::F32)throw std::invalid_argument("stored GDN decay must be F32");if(f32)shape.flags|=8;}
 if(use_ng)switch(s.op){
 case Op::norm:shape.op=ng::norm;shape.width=s.site.shape[1];shape.heads=int(s.sizes[0])/shape.width;shape.flags|=s.site.parameter?1:0;in(0,0);weight(1,0);out(2,0);break;
 case Op::silu_div4:case Op::silu_product:shape.op=ng::activation;shape.width=int(s.sizes[0]);shape.extra=s.op==Op::silu_product;in(0,0);if(shape.extra)in(1,1);out(2,0);break;
 case Op::hc_mix:shape.op=ng::mix;shape.width=s.site.shape[1];in(0,0);in(1,1);out(2,0);break;
 case Op::conv:shape.op=ng::conv;shape.width=s.site.shape[0];shape.extra=s.site.parameter;in(0,0);in(1,1);weight(2,0);out(3,0);out(4,1);break;
 case Op::gdn:shape.op=ng::gdn;shape.flags|=2|(s.packed_heads?4:0);in(0,0);in(1,1);in(2,2);weight(3,0);weight(4,1);in(5,3);out(6,0);out(7,1);break;
 case Op::gdn_norm_gate:shape.op=ng::gated_norm;shape.heads=48;in(0,0);in(1,1);weight(2,0);out(3,0);break;
 case Op::moe_combine:shape.op=ng::moe_combine;shape.width=s.site.shape[1];shape.extra=s.site.shape[0];in(0,0);in(1,1);in(2,2);in(3,3);out(4,0);break;
 case Op::qsa_prepare:shape.op=ng::prepare;for(int j=0;j<3;++j){in(j,j);weight(3+j,j);}for(int j=0;j<4;++j)out(6+j,j);break;
 case Op::qsa_append_pool:shape.op=ng::pool;for(int j=0;j<3;++j)in(j,j);weight(3,0);for(int j=0;j<4;++j)out(4+j,j);break;
 case Op::qsa_select:shape.op=ng::select;in(0,0);in(1,1);out(2,0);break;
 case Op::qsa_attention:shape.op=ng::attention_score;for(int j=0;j<5;++j)in(j,j);out(5,0);a[6]=score;a[7]=probability;break;
 default:use_ng=false;
 }
 // Packet15's GDN/QSA geometry is fixed to the real model. Mini's synthetic
 // geometry uses dimensioned parallel equations, never the interpreter control.
 bool tiny=s.g.h!=2560;
 bool tiny_core=tiny&&s.special==Special::normal&&(s.op==Op::gdn||s.op==Op::gdn_norm_gate||s.op==Op::qsa_prepare||s.op==Op::qsa_append_pool||s.op==Op::qsa_select||s.op==Op::qsa_attention);
 std::vector<ownrt::Allocation> b(bindings.begin(),bindings.end());b.push_back(control);
 if(!use_ng||tiny_core){Glue k(s,tiny_core?3:0);auto e=d.compute(k,b,deps);return {e,e,1};}
 // Validate before submitting anything, so a bad shape cannot strand a partial chain.
 ng::validate(shape);auto required=ng::required_bytes(shape);for(int j=0;j<16;++j)if(d.arena.row(a[j]).bytes<required[j])throw std::invalid_argument("adapter allocation too short at slot "+std::to_string(j));
 Glue entry(s,1),exit(s,2);auto first=d.compute(entry,b,deps),last=first;uint32_t count=1;
 auto kernel=[&](ng::Shape sh){std::array<ownrt::Event,1> after{last};
#ifdef OWN_RT_HOST_ONLY
  NgHost k(sh);last=d.compute(k,a,after);
#else
  last=ng::submit(d,sh,a,after);
#endif
  ++count;};
 kernel(shape);if(shape.op==ng::attention_score){shape.op=ng::attention_softmax;kernel(shape);shape.op=ng::attention_value;kernel(shape);}
 std::array<ownrt::Event,1> after{last};last=d.compute(exit,b,after);++count;return {first,last,count};
}
}
