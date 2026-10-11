// Included inside packet18, after the unchanged v1 lowering and kernels.
namespace {
// Tree of a complete power-of-two-aligned subtree. The final partial subtree
// executes the original +0 tail at each occupied level, never padded fake leaves.
template<int Width,class F> float subtree(int n,int begin,F get){
 float v[Width];int count=std::min(Width,n-begin);
 for(int i=0;i<count;++i)v[i]=get(begin+i);
 for(int stride=1;stride<Width&&stride<n;stride*=2)
  for(int i=0;i<count;i+=2*stride)v[i]=v[i]+(i+stride<count?v[i+stride]:0.f);
 return v[0];
}
struct V2Guard {
 int error(ng::Args a)const{
#ifdef OWN_RT_HOST_ONLY
 return a.i(15)[0];
#else
 return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();
#endif
 }
 void fail(ng::Args a)const{
#ifdef OWN_RT_HOST_ONLY
 a.i(15)[0]=1;
#else
 sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);
#endif
 }
};
#ifdef OWN_RT_HOST_ONLY
struct NgV2 final:HostOperation {
 ng::Shape shape;int phase,work;
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto scratch=static_cast<float*>(p[19]);packet24::mock_items(work,[&](size_t i){ng2::body(shape,a,phase,i,scratch,V2Guard{});});}
};
#else
struct NgV2 final:ownrt::SyclOperation {
 ng::Shape shape;int phase,work;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
 ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto ap=packet23::parameters(a);auto scratch=static_cast<float*>(p[19]);auto s=shape;int ph=phase,n=work;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>((n+63)/64*64),[=](sycl::id<1> id){int i=id[0];if(i<n)ng2::body(s,*ap,ph,i,scratch,V2Guard{});});});
 }
};
#endif
bool simple_v2(const Spec& s){return s.special==Special::broadcast||(s.special==Special::normal&&(s.op==Op::route||s.op==Op::hc_combine||s.op==Op::expert_gather||s.op==Op::argmax));}
int simple_phases(const Spec& s){return s.op==Op::route?5:(s.op==Op::argmax||s.op==Op::expert_gather)?2:1;}
int simple_work(const Spec& s,int phase){
 if(s.op==Op::route){int n=s.sizes[0];return phase==0||phase==1?(n+15)/16:phase==2||phase==3?n:1;}
 if(s.op==Op::argmax)return phase==0?(s.sizes[0]+255)/256:1;
 if(s.op==Op::expert_gather&&phase==1)return 1;
 if(s.op==Op::expert_gather)return std::max(s.g.top,int(s.sizes[s.ni+2]));
 return s.sizes[s.ni];
}
void simple_body(Bound b,int phase,int index,bool raw_rank){
 if(!*b.active()||b.failed())return;
 auto s=b.s;float* tmp=static_cast<float*>(b.p[b.tail()]);
 if(s.op==Op::route){
  int n=b.in(0).n,top=s.site.shape[1],chunks=(n+15)/16;
  // tmp: maxima[chunks], subtree sums[chunks], exponentials[n], probabilities[n].
  float* sums=tmp+chunks;float* ex=sums+chunks;float* prob=ex+n;
  if(phase==0){float maximum=-INFINITY;for(int j=index*16;j<std::min(n,(index+1)*16);++j){float x=b.in(0).get(j);if(!std::isfinite(x)){b.fail();return;}maximum=std::max(maximum,x);}tmp[index]=maximum;}
  else if(phase==1){float maximum=-INFINITY;for(int j=0;j<chunks;++j)maximum=std::max(maximum,tmp[j]);
   sums[index]=subtree<16>(n,index*16,[&](int j){float v=detmath::exp(b.in(0).get(j)-maximum);ex[j]=v;return v;});
  }else if(phase==2){float den=subtree<256>(chunks,0,[&](int j){return sums[j];});prob[index]=ex[index]/den;}
  else if(phase==3){float v=prob[index];int rank=0;for(int j=0;j<n;++j)rank+=prob[j]>v||(prob[j]==v&&j<index);
   if(rank<top){b.out(0).put(rank,index);b.out(1).put(rank,v);if(raw_rank)for(int k=0;k<3;++k){b.out(2).put(rank*3+k,k==0?index:k==1?0:s.g.mid);b.out(3).put(rank*3+k,k==0?index:k==1?0:s.g.h);}}
  }else if(!raw_rank){float sum=subtree<32>(top,0,[&](int j){return b.out(1).get(j);});for(int j=0;j<top;++j)b.out(1).put(j,b.out(1).get(j)/sum);}
 }else if(s.op==Op::argmax){
  int n=b.in(0).n,chunks=(n+255)/256;
  if(phase==0){int best=index*256;bool finite=true;for(int j=best;j<std::min(n,(index+1)*256);++j){float v=b.in(0).get(j);finite=finite&&std::isfinite(v);if(v>b.in(0).get(best))best=j;}tmp[index]=float(best);tmp[chunks+index]=finite?0:1;}
  else{int best=0;bool bad=false;for(int j=0;j<chunks;++j){bad=bad||tmp[chunks+j]!=0;int id=int(tmp[j]);if(b.in(0).get(id)>b.in(0).get(best))best=id;}
   if(bad){best=0;for(int lane=0;lane<128;++lane){int local=lane;for(int j=lane;j<n;j+=128)if(b.in(0).get(j)>b.in(0).get(local))local=j;if(lane<n&&(b.in(0).get(local)>b.in(0).get(best)||(b.in(0).get(local)==b.in(0).get(best)&&local<best)))best=local;}}
   b.out(0).put(0,best);if(bad)b.fail();}
 }else if(s.special==Special::broadcast)b.out(0).put(index,b.in(0).get(index%b.in(0).n));
 else if(s.op==Op::hc_combine)b.out(0).put(index,b.in(0).get(index)+b.in(1).get(index%s.site.shape[1])*(2.f*ng::sigmoid(b.in(2).get(index/s.site.shape[1])/4.f)));
 else if(s.op==Op::expert_gather){
  if(phase==1){for(int j=0;j<s.g.top;++j)if(tmp[j])b.fail();return;}
  if(index<s.g.top){float v=b.in(0).get(index);bool valid=std::isfinite(v)&&v>=0&&v<float(s.g.experts)&&std::floor(v)==v;int id=valid?int(v):0;tmp[index]=valid?0:1;for(int k=0;k<3;++k){b.out(0).put(index*3+k,k==0?id:k==1?0:s.g.mid);b.out(1).put(index*3+k,k==0?id:k==1?0:s.g.h);}}
  // Unfused compatibility path only. Fused Rank has no repeated-row binding.
  if(index<int(b.out(2).n))b.out(2).put(index,b.in(1).get(index%b.in(1).n));
 }
}
#ifdef OWN_RT_HOST_ONLY
struct SimpleV2 final:HostOperation {
 Spec spec;int phase,work;bool rank=false;
 void run(std::span<void*const> p)const override{Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());packet24::mock_items(work,[&](size_t i){simple_body(b,phase,i,rank);});}
};
#else
struct SimpleV2 final:ownrt::SyclOperation {
 Spec spec;int phase,work;bool rank=false;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{Bound b{spec,{}};std::copy(p.begin(),p.end(),b.p.begin());auto bp=packet23::parameters(b);int ph=phase,n=work;bool raw=rank;
 return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>((n+63)/64*64),[=](sycl::id<1> id){int i=id[0];if(i<n)simple_body(*bp,ph,i,raw);});});}
};
#endif
Launch simple_submit(ownrt::Device& d,const Spec& s,std::span<const ownrt::Allocation> bindings,bool rank,std::span<const ownrt::Event> deps={}){
 if(bindings.size()!=size_t(s.ni+s.no+s.nw+5)||bindings.size()>31)throw std::invalid_argument("adapter binding count");
 if(s.op==Op::route&&(s.sizes[0]>4096||s.site.shape[1]>32||s.site.shape[1]<1||size_t(s.site.shape[1])>s.sizes[0]))throw std::invalid_argument("v2 route geometry");
 size_t scratch_values=s.op==Op::route?2*((s.sizes[0]+15)/16)+2*s.sizes[0]:s.op==Op::argmax?2*((s.sizes[0]+255)/256):s.op==Op::expert_gather?size_t(s.g.top):0;
 if(d.arena.row(bindings[s.ni+s.no+s.nw]).bytes<scratch_values*sizeof(float))throw std::invalid_argument("simple v2 scratch extent");
 Launch result{};for(int phase=0;phase<(rank?4:simple_phases(s));++phase){SimpleV2 op;op.spec=s;op.phase=phase;op.rank=rank;op.work=simple_work(s,phase);std::array<ownrt::Event,1> after{result.last};auto e=d.compute(op,bindings,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;}return result;
}
}
Launch submit_parallel(ownrt::Device& d,const Spec& s,std::span<const ownrt::Allocation> bindings,ownrt::Allocation control,ownrt::Allocation score,ownrt::Allocation probability,std::span<const ownrt::Event> deps){
 if(bindings.size()!=size_t(s.ni+s.no+s.nw+5)||bindings.size()>31)throw std::invalid_argument("adapter binding count");
 if(packet24::kernel_version==1)return submit_parallel_v1(d,s,bindings,control,score,probability,deps);
 if(simple_v2(s))return simple_submit(d,s,bindings,false,deps);
 auto l=lower(d,s,bindings,control,score,probability);
 if(l.mode!=4||!ng2::supported(l.shape))return submit_parallel_v1(d,s,bindings,control,score,probability,deps);
 auto scratch=bindings[s.ni+s.no+s.nw];l.bindings.push_back(scratch);Launch result{};
 auto launch=[&](ng::Shape sh){if(size_t(ng2::scratch_floats(sh))*4>d.arena.row(scratch).bytes)throw std::invalid_argument("v2 scratch extent");for(int phase=0;phase<ng2::stages(sh);++phase){NgV2 op;op.shape=sh;op.phase=phase;op.work=ng2::work_items(sh,phase);if(!op.work)continue;std::array<ownrt::Event,1> after{result.last};auto e=d.compute(op,l.bindings,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;}};
 launch(l.shape);if(l.shape.op==ng::attention_score){l.shape.op=ng::attention_softmax;launch(l.shape);l.shape.op=ng::attention_value;launch(l.shape);}return result;
}
Launch submit_chain(ownrt::Device& d,const std::vector<Spec>& specs,const std::vector<std::vector<ownrt::Allocation>>& bindings,ownrt::Allocation control,ownrt::Allocation score,ownrt::Allocation probability){
 if(packet24::kernel_version==1)return submit_chain_v1(d,specs,bindings,control,score,probability);
 if(specs.empty()||specs.size()>8||specs.size()!=bindings.size())throw std::invalid_argument("fusion chain extent");
 Launch result{};for(size_t i=0;i<specs.size();++i){std::array<ownrt::Event,1> after{result.last};auto e=submit_parallel(d,specs[i],bindings[i],control,score,probability,result.last?std::span<const ownrt::Event>(after):std::span<const ownrt::Event>{});if(!result.first)result.first=e.first;result.last=e.last;result.passes+=e.passes;}return result;
}
Launch submit_rank(ownrt::Device& d,const Spec& s,const std::vector<ownrt::Allocation>& bindings){if(packet24::kernel_version==1)return submit_rank_v1(d,s,bindings);return simple_submit(d,s,bindings,true);}
