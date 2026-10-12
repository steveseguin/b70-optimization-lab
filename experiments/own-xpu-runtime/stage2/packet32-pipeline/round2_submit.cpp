#include "round2_submit.hpp"
#include "mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace round2 {
#ifndef OWN_RT_HOST_ONLY
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=32)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
// This is an adjacent reduction, NOT the implementation-defined SYCL sum.
inline float lane_tree(sycl::sub_group sg,float v){
 unsigned lane=sg.get_local_linear_id();
 for(unsigned stride=1;stride<32;stride*=2){float right=sycl::select_from_group(sg,v,sycl::id<1>((lane+stride)%32));if(lane%(2*stride)==0)v=v+right;}
 return sycl::select_from_group(sg,v,sycl::id<1>(0));
}
inline void gdn_device(ng::Shape s,ng::Args a,sycl::nd_item<1> it){
 auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),g=it.get_group_linear_id();
 Team t{it,nullptr};int blocked=lane==0?int(!a.i(18)[0]||t.error(a)):0;
 if(sycl::select_from_group(sg,blocked,sycl::id<1>(0)))return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(g==0&&lane==0)t.fail(a);return;}
 int h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
 for(int r=0;r<s.tokens;++r){int qb=r*10240+key*128,kb=qb+2048;float q[4],k[4],v[4],qs=0.f,ks=0.f;
  for(int z=0;z<4;++z){q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];}
  float qn=detmath::sqrt(lane_tree(sg,qs)+1e-6f),kn=detmath::sqrt(lane_tree(sg,ks)+1e-6f);
  float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate,av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
  float decay=detmath::exp(av*sp),pred=0.f;
  for(int z=0;z<4;++z){q[z]=(q[z]/qn)/detmath::sqrt(float(128));k[z]=k[z]/kn;v[z]=a.b(r?7:5,state+4*lane+z)*decay;pred=pred+v[z]*k[z];}
  pred=lane_tree(sg,pred);float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*ng::sigmoid(a.b(2,r*48+h)),y=0.f;
  for(int z=0;z<4;++z){v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];}
  y=lane_tree(sg,y);if(lane==0)a.put(6,(r*48+h)*128+j,y);
  for(int z=0;z<4;++z)a.put(7,state+4*lane+z,v[z]);
  // Next token reads the BF16-rounded state, including when input/output alias.
  sycl::group_barrier(sg,sycl::memory_scope::device);
 }
}
#endif
#ifdef OWN_RT_HOST_ONLY
template<ng::Op Code,int Stage> struct Kernel final:integrated::HostOperation {
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());if constexpr(Code==ng::gdn)gdn_host(s,a);else {std::vector<float> local(round2::local_floats(s));packet24::mock_items(round2::groups(s),[&](size_t g){group<Code,Stage>(s,a,int(g),static_cast<float*>(p[19]),ng::HostTeam{local.data()});});}}
};
#else
template<ng::Op Code,int Stage> struct Kernel final:ownrt::SyclOperation {
 ng::Shape s;explicit Kernel(ng::Shape v):s(v){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto shape=s;float* global=static_cast<float*>(p[19]);int count=round2::groups(s),local=round2::local_floats(s);
  if constexpr(Code==ng::gdn)return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(size_t(count)*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{gdn_device(shape,a,it);});});
  else return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> x(local,h);h.parallel_for(sycl::nd_range<1>(size_t(count)*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{group<Code,Stage>(shape,a,int(it.get_group_linear_id()),global,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});
 }
};
#endif
template<ng::Op Code> integrated::Launch issue(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){Kernel<Code,0> first(s);auto e=d.compute(first,a,deps);if constexpr(Code==ng::select){Kernel<Code,1> second(s);std::array<ownrt::Event,1> after{e};auto end=d.compute(second,a,after);return {e,end,2};}return {e,e,1};}
integrated::Launch submit(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,ownrt::Allocation scratch,std::span<const ownrt::Event> deps){
 ng::validate(s);if(a.size()!=19||!supported(s))throw std::invalid_argument("round2 non-GEMV binding/op");auto need=ng::required_bytes(s);for(int j=0;j<19;++j)if(d.arena.row(a[j]).bytes<need[j])throw std::invalid_argument("round2 non-GEMV short binding");if(d.arena.row(scratch).bytes<round2::scratch_floats(s)*4)throw std::invalid_argument("round2 non-GEMV scratch");
 std::vector<std::pair<int,bool>> used;
 switch(s.op){
 case ng::gdn:used={{0,false},{1,false},{2,false},{3,false},{4,false},{5,false},{6,true},{7,true}};break;
 case ng::select:used={{0,false},{1,false},{2,true}};break;
 case ng::attention_score:used={{0,false},{2,false},{4,false},{6,true}};break;
 case ng::attention_softmax:used={{4,false},{6,false},{7,true}};break;
 case ng::attention_value:used={{1,false},{3,false},{4,false},{5,true},{7,false}};break;
 }
 used.insert(used.end(),{{15,true},{17,false},{18,false}});
 for(size_t i=0;i<used.size();++i){auto [slot,write]=used[i];const auto& binding=d.arena.row(a[slot]);if(!binding.live||binding.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(binding.pointer)%4)throw std::invalid_argument("round2 binding memory/alignment");if(a[slot]==scratch)throw std::invalid_argument("round2 scratch aliases binding");for(size_t j=0;j<i;++j){auto [other,other_write]=used[j];bool state_alias=s.op==ng::gdn&&slot==7&&other==5;if(a[slot]==a[other]&&(write||other_write)&&!state_alias)throw std::invalid_argument("round2 conflicting binding aliases");}}
 const auto& scratch_row=d.arena.row(scratch);if(!scratch_row.live||scratch_row.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(scratch_row.pointer)%4)throw std::invalid_argument("round2 scratch memory/alignment");
 std::array<ownrt::Allocation,20> bound;std::copy(a.begin(),a.end(),bound.begin());bound[19]=scratch;
 switch(s.op){case ng::gdn:return issue<ng::gdn>(d,s,bound,deps);case ng::select:return issue<ng::select>(d,s,bound,deps);case ng::attention_score:return issue<ng::attention_score>(d,s,bound,deps);case ng::attention_softmax:return issue<ng::attention_softmax>(d,s,bound,deps);case ng::attention_value:return issue<ng::attention_value>(d,s,bound,deps);default:throw std::invalid_argument("round2 non-GEMV op");}
}

// By-value concrete binding set: no Spec/View/type switch reaches a row loop.
struct SimpleArgs {
 const void* input;int32_t* ids;float* probability;int32_t* gate;int32_t* down;
 float* scratch;uint32_t* error;const uint32_t* active;int n,top,mid,width;
 ng::Args control()const{ng::Args a{};a.p[15]=error;return a;}
};
template<flash::Scalar Input> inline float read(const SimpleArgs& a,int i){if constexpr(Input==flash::Scalar::bf16)return std::bit_cast<float>(uint32_t(static_cast<const uint16_t*>(a.input)[i])<<16);else return static_cast<const float*>(a.input)[i];}
template<integrated::Op Code,int Stage,flash::Scalar Input,int FixedN=0,int FixedTop=0,class T> void simple_group(SimpleArgs a,int group,T t){
 auto ctrl=a.control();t.each(1,[&](int){t.x[0]=float(!*a.active||t.error(ctrl));});t.barrier();if(t.x[0])return;t.barrier();
 int n=FixedN?FixedN:a.n,top=FixedTop?FixedTop:a.top;
 if constexpr(Code==integrated::Op::route){
  if constexpr(Stage==0){
   // One cooperative softmax. Original exponentials and denominator tree are
   // retained; all 512 rank candidates are dispatched in independent groups.
   t.each(1,[&](int){float m=-INFINITY;bool finite=true;for(int k=0;k<n;++k){float v=read<Input>(a,k);finite=finite&&std::isfinite(v);m=std::max(m,v);}t.x[n]=m;t.x[n+1]=finite?0.f:1.f;});t.barrier();
   if(t.x[n+1]){t.each(1,[&](int){t.fail(ctrl);});return;}float m=t.x[n];t.barrier();
   t.each(n,[&](int k){float v=detmath::exp(read<Input>(a,k)-m);t.x[k]=v;a.scratch[k]=v;});t.barrier();float den=t.sum(n);t.barrier();t.each(n,[&](int k){a.scratch[k]=a.scratch[k]/den;});
  }else if constexpr(Stage==1){t.each(32,[&](int lane){int j=group*32+lane;if(j>=n)return;float v=a.scratch[j];int rank=0;
   // Losing entries may stop once ten values outrank them. This is exactly
   // the old rank predicate, including probability-rounding ties and ID order.
   for(int k=0;k<n&&rank<top;++k)rank+=a.scratch[k]>v||(a.scratch[k]==v&&k<j);
   if(rank<top){a.ids[rank]=j;a.probability[rank]=v;if(a.gate)for(int k=0;k<3;++k){a.gate[rank*3+k]=k==0?j:k==1?0:a.mid;a.down[rank*3+k]=k==0?j:k==1?0:a.width;}}
  });}else {t.each(top,[&](int k){t.x[k]=a.probability[k];});t.barrier();float den=t.sum(top);t.barrier();t.each(top,[&](int k){a.probability[k]=a.probability[k]/den;});}
 }else if constexpr(Code==integrated::Op::argmax){
  int chunks=(n+1023)/1024;
  t.each(32,[&](int lane){int best=-1;bool bad=false;
   if constexpr(Stage==0){for(int j=group*1024+lane;j<std::min(n,(group+1)*1024);j+=32){float v=read<Input>(a,j);bad=bad||!std::isfinite(v);if(best<0||v>read<Input>(a,best)||(v==read<Input>(a,best)&&j<best))best=j;}}
   else for(int j=lane;j<chunks;j+=32){int k=int(a.scratch[j]);bad=bad||a.scratch[chunks+j]!=0;if(best<0||read<Input>(a,k)>read<Input>(a,best)||(read<Input>(a,k)==read<Input>(a,best)&&k<best))best=k;}
   t.x[lane]=float(best);t.x[32+lane]=bad?1.f:0.f;
  });t.barrier();
  t.each(1,[&](int){int best=-1;bool bad=false;for(int lane=0;lane<32;++lane){int k=int(t.x[lane]);bad=bad||t.x[32+lane]!=0;if(k>=0&&(best<0||read<Input>(a,k)>read<Input>(a,best)||(read<Input>(a,k)==read<Input>(a,best)&&k<best)))best=k;}
   if constexpr(Stage==0){a.scratch[group]=float(best);a.scratch[chunks+group]=bad?1.f:0.f;}
   else {if(bad){best=0;for(int lane=0;lane<128;++lane){int local=lane;for(int j=lane;j<n;j+=128)if(read<Input>(a,j)>read<Input>(a,local))local=j;if(lane<n&&(read<Input>(a,local)>read<Input>(a,best)||(read<Input>(a,local)==read<Input>(a,best)&&local<best)))best=local;}}a.ids[0]=best;if(bad)t.fail(ctrl);}
  });
 }
}
#ifdef OWN_RT_HOST_ONLY
template<integrated::Op Code,int Stage,flash::Scalar Input,int FixedN=0,int FixedTop=0> struct Simple final:integrated::HostOperation{
 integrated::Spec s;explicit Simple(integrated::Spec v):s(v){}
#else
template<integrated::Op Code,int Stage,flash::Scalar Input,int FixedN=0,int FixedTop=0> struct Simple final:ownrt::SyclOperation{
 integrated::Spec s;explicit Simple(integrated::Spec v):s(v){}
#endif
 SimpleArgs bind(std::span<void*const> p)const{int tail=s.ni+s.no+s.nw;return {p[0],static_cast<int32_t*>(p[s.ni]),Code==integrated::Op::route?static_cast<float*>(p[s.ni+1]):nullptr,Code==integrated::Op::route&&s.no>=4?static_cast<int32_t*>(p[s.ni+2]):nullptr,Code==integrated::Op::route&&s.no>=4?static_cast<int32_t*>(p[s.ni+3]):nullptr,static_cast<float*>(p[tail]),static_cast<uint32_t*>(p[tail+1]),static_cast<const uint32_t*>(p[tail+3]),int(s.sizes[0]),s.site.shape[1],s.g.mid,s.g.h};}
 int count()const{if constexpr(Code==integrated::Op::route)return Stage==1?(int(s.sizes[0])+31)/32:1;else return Stage==0?(int(s.sizes[0])+1023)/1024:1;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto a=bind(p);std::vector<float> x(std::max(64,a.n+2));packet24::mock_items(count(),[&](size_t g){simple_group<Code,Stage,Input,FixedN,FixedTop>(a,int(g),ng::HostTeam{x.data()});});}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto a=bind(p);int groups=count(),local=Code==integrated::Op::route?int(s.sizes[0])+2:64;return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> x(local,h);h.parallel_for(sycl::nd_range<1>(size_t(groups)*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{simple_group<Code,Stage,Input,FixedN,FixedTop>(a,int(it.get_group_linear_id()),Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});});});}
#endif
};
template<integrated::Op Code,flash::Scalar Input,int FixedN=0,int FixedTop=0> integrated::Launch issue_simple(ownrt::Device& d,const integrated::Spec& s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){
 integrated::Launch result{};auto issue=[&]<int Stage>(){Simple<Code,Stage,Input,FixedN,FixedTop> op(s);std::array<ownrt::Event,1> after{result.last};auto e=d.compute(op,a,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};issue.template operator()<0>();issue.template operator()<1>();if constexpr(Code==integrated::Op::route)issue.template operator()<2>();return result;
}
integrated::Launch submit_simple(ownrt::Device& d,const integrated::Spec& s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){
 int tail=s.ni+s.no+s.nw;bool route=s.op==integrated::Op::route;if(a.size()!=size_t(tail+5)||(s.ni!=1&&s.ni!=3)||s.nw||(!route&&s.op!=integrated::Op::argmax)||s.sizes[0]<1||s.sizes[0]>1000000||(s.types[s.ni]!=flash::Scalar::i32&&s.types[s.ni]!=flash::Scalar::u32))throw std::invalid_argument("round2 simple bindings/op/type");
 // Builder::node appends active/error to every real schedule input list.
 // Standalone fixtures may use the compact one-input ABI. The three-input ABI
 // is accepted only when the appended scalar controls alias the canonical
 // trailing controls; arbitrary extra inputs remain invalid.
 if(s.ni==3&&(s.types[1]!=flash::Scalar::u32||s.types[2]!=flash::Scalar::u32||s.sizes[1]!=1||s.sizes[2]!=1||a[1]!=a[tail+3]||a[2]!=a[tail+1]))throw std::invalid_argument("round2 simple scheduled controls");
 if(route&&(s.sizes[0]>512||s.site.shape[1]<1||s.site.shape[1]>int(s.sizes[0])||(s.no!=2&&s.no!=4)||s.types[s.ni+1]!=flash::Scalar::f32))throw std::invalid_argument("round2 route shape/type");
 if(route&&s.no==4&&((s.types[s.ni+2]!=flash::Scalar::i32&&s.types[s.ni+2]!=flash::Scalar::u32)||(s.types[s.ni+3]!=flash::Scalar::i32&&s.types[s.ni+3]!=flash::Scalar::u32)))throw std::invalid_argument("round2 route descriptor output type");
 if(route&&(s.sizes[s.ni]<size_t(s.site.shape[1])||s.sizes[s.ni+1]<size_t(s.site.shape[1])||(s.no==4&&(s.sizes[s.ni+2]<size_t(3*s.site.shape[1])||s.sizes[s.ni+3]<size_t(3*s.site.shape[1])))))throw std::invalid_argument("round2 route output shape");
 if(!route&&s.sizes[s.ni]<1)throw std::invalid_argument("round2 argmax output shape");
 if(!route&&(s.no<1||s.no>2))throw std::invalid_argument("round2 argmax outputs");
 for(int j=0;j<s.ni+s.no;++j){size_t bytes=s.sizes[j]*(s.types[j]==flash::Scalar::bf16?2:s.types[j]==flash::Scalar::i64?8:4);if(d.arena.row(a[j]).bytes<bytes)throw std::invalid_argument("round2 simple short allocation");}
 size_t scratch=route?s.sizes[0]:2*((s.sizes[0]+1023)/1024);if(d.arena.row(a[tail]).bytes<scratch*4)throw std::invalid_argument("round2 simple scratch");for(int j=1;j<=3;++j)if(d.arena.row(a[tail+j]).bytes<4)throw std::invalid_argument("round2 simple control extent");
 std::vector<std::pair<uint64_t,bool>> accesses{{a[0],false},{a[s.ni],true},{a[tail],true},{a[tail+1],true},{a[tail+2],false},{a[tail+3],false}};
 if(route){accesses.emplace_back(a[s.ni+1],true);if(s.no==4){accesses.emplace_back(a[s.ni+2],true);accesses.emplace_back(a[s.ni+3],true);}}
 for(auto [id,write]:accesses){const auto& row=d.arena.row(id);if(!row.live||row.memory!=ownrt::Memory::device||reinterpret_cast<uintptr_t>(row.pointer)%4)throw std::invalid_argument("round2 simple memory/alignment");}
 iq3::kopt3::validate_aliases(accesses);
 auto launch=[&]<flash::Scalar Input>(){if(route){if(s.sizes[0]==512&&s.site.shape[1]==10)return issue_simple<integrated::Op::route,Input,512,10>(d,s,a,deps);return issue_simple<integrated::Op::route,Input>(d,s,a,deps);}return issue_simple<integrated::Op::argmax,Input>(d,s,a,deps);};
 if(s.types[0]==flash::Scalar::bf16)return launch.template operator()<flash::Scalar::bf16>();if(s.types[0]==flash::Scalar::f32)return launch.template operator()<flash::Scalar::f32>();throw std::invalid_argument("round2 simple input type");
}
} // namespace round2
