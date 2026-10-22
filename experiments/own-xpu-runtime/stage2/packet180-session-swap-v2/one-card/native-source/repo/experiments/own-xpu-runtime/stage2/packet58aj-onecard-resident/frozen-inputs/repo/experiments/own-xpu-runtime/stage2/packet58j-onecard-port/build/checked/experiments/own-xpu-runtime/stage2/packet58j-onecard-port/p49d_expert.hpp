#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49d_expert.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Packet53b: physical scheduling changes only. Each of the 32 logical lanes
// retains its original k=256*t+8*lane chain and the adjacent reduction tree.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49b_expert_kernel.hpp"

namespace p49dvirtual {
using iq3::Type;
enum Variant : unsigned {virtual2_global=0,virtual4_global=1,virtual8_global=2,virtual16_global=3};
struct VariantSpec {const char* name;unsigned virtualization;bool persistent,local_table;};
inline constexpr std::array<VariantSpec,4> variants{{
 {"virtual2-global",2,false,false},{"virtual4-global",4,false,false},
 {"virtual8-global",8,false,false},{"virtual16-global",16,false,false}}};
inline constexpr unsigned persistent_groups=64, workgroup_size=256;
inline bool valid_variant(Type t,unsigned v){return (t==Type::IQ2_S||t==Type::IQ4_NL)&&v>=1&&v<4;}

// Full uncompressed 8 KiB table. Its layout deliberately matches production:
// two adjacent uint32 gathers per eight magnitudes. No compact-code arithmetic.
template<unsigned K>inline void decode_iq2(const uint8_t* row,unsigned k,float(&v)[8],const uint32_t* table=nullptr){
 constexpr auto l=p49bgemv::layout(Type::IQ2_S,K);
 unsigned block=k/256,i=k%256,q=i/8;
 unsigned pair=p49bgemv::load16(row+block*64+q*2);
 unsigned index=(pair&255)|(((row[l.high+block*8+q/4]>>(2*(q%4)))&3)<<8);
 unsigned signs=pair>>8;
 float d=iq3::half(p49bgemv::load16(row+l.halves+2*block));
 float scale=(d*(0.5f+float((row[l.scales+block*8+i/32]>>(4*((i/16)%2)))&15)))*0.25f;
 uint32_t a=table?table[2*index]:p42expert::iq2_words[2*index];
 uint32_t b=table?table[2*index+1]:p42expert::iq2_words[2*index+1];
 bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffff)>=0x7f800000||(std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000;
 #pragma unroll
 for(unsigned j=0;j<8;++j){unsigned magnitude=((j<4?a:b)>>(8*(j%4)))&255;
  if(exceptional)v[j]=(scale*float(magnitude))*float((signs>>j)&1?-1:1);
  else {int signed_magnitude=(signs>>j)&1?-int(magnitude):int(magnitude);v[j]=scale*float(signed_magnitude);}
 }
}
template<Type T,unsigned K,unsigned V>inline std::array<float,V> lane_chains(const uint8_t* w,const uint16_t* x,unsigned physical_lane,const uint32_t* table=nullptr){
 static_assert(V==1||V==2||V==4||V==8||V==16);static_assert((T==Type::IQ2_S&&K==2560)||(T==Type::IQ4_NL&&K==640));
 std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  #pragma unroll
  for(unsigned chain=0;chain<V;++chain){unsigned k=step*256+8*(physical_lane*V+chain);if(k>=K)continue;
   float values[8];if constexpr(T==Type::IQ2_S)decode_iq2<K>(w,k,values,table);else p49bgemv::decode8<T,K>(w,k,values);
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
   #pragma unroll
   for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[k+j];
#endif
    float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
   }
  }
 }
 return sums;
}
template<unsigned V>inline std::array<std::array<float,V>,2> gate_chains(const uint8_t* w,const uint8_t* peer,const uint16_t* x,unsigned physical_lane,const uint32_t* table=nullptr){
 static_assert(V==1||V==2||V==4||V==8||V==16);std::array<std::array<float,V>,2> sums{};
 for(unsigned step=0;step<10;++step){
  #pragma unroll
  for(unsigned chain=0;chain<V;++chain){unsigned k=step*256+8*(physical_lane*V+chain);float a[8],b[8];decode_iq2<2560>(w,k,a,table);decode_iq2<2560>(peer,k,b,table);
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
   #pragma unroll
   for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[k+j];
#endif
    float input=iq3::bits_float(uint32_t(bits)<<16);float pa=a[j]*input;sums[0][chain]=sums[0][chain]+pa;float pb=b[j]*input;sums[1][chain]=sums[1][chain]+pb;
   }
  }
 }
 return sums;
}
template<unsigned V>inline float local_tree(std::array<float,V> values){
 // V consecutive logical lanes: perform exactly the first log2(V) levels.
 for(unsigned width=1;width<V;width*=2)for(unsigned lane=0;lane<V;lane+=2*width)values[lane]=values[lane]+values[lane+width];
 return values[0];
}
template<Type T,unsigned K,unsigned V>inline float host_row(const uint8_t* w,const uint16_t* x,const uint32_t* table=nullptr){
 float physical[32/V];for(unsigned lane=0;lane<32/V;++lane)physical[lane]=local_tree<V>(lane_chains<T,K,V>(w,x,lane,table));
 for(unsigned width=1;width<32/V;width*=2)for(unsigned lane=0;lane<32/V;lane+=2*width)physical[lane]=physical[lane]+physical[lane+width];return physical[0];
}
inline unsigned group_count(unsigned total,unsigned variant){
 auto v=variants.at(variant);return v.persistent?persistent_groups:(total+8*v.virtualization-1)/(8*v.virtualization);
}
// Logical output-row assignment shared with CPU coverage checks. Each SG owns
// V adjacent output rows; successive iterations stride over the whole launch.
template<unsigned V>inline unsigned scheduled_row(unsigned group,unsigned subgroup,unsigned row_in_subgroup,unsigned iteration,unsigned groups){
 return ((group*8+subgroup)*V+row_in_subgroup)+iteration*groups*8*V;
}
template<Type T,unsigned K,unsigned SelectedArm>struct Kernel final:p49b::Base {
 static constexpr bool paired=T==Type::IQ2_S;
 unsigned rows=paired?640:2560,count=10,experts=512;bool indirect=false;
 static_assert(SelectedArm==(paired?2u:3u));
 p39::Bound bind(std::span<void*const>p)const {
  p39::Bound b{};b.indirect=indirect;b.rows=rows;b.count=count;b.experts=experts;b.rb=p49bgemv::layout(T,K).row_bytes;
  b.w=static_cast<const uint8_t*>(p[0]);b.peer=static_cast<const uint8_t*>(p[1]);b.x=static_cast<const uint16_t*>(p[2]);b.y=static_cast<uint16_t*>(p[3]);b.py=static_cast<uint16_t*>(p[4]);b.routes=static_cast<const iq3::Route*>(p[5]);b.status=static_cast<uint32_t*>(p[6]);b.peer_status=static_cast<uint32_t*>(p[7]);b.error=static_cast<uint32_t*>(p[16]);b.active=static_cast<const uint32_t*>(p[17]);return b;
 }
 template<unsigned Arm>void host_run(std::span<void*const>p)const {
  constexpr auto choice=variants[Arm];constexpr unsigned V=choice.virtualization;auto b=bind(p);unsigned total=rows*count,groups=group_count(total,Arm);
  std::array<uint32_t,2048> table{};if constexpr(choice.local_table)for(unsigned j=0;j<2048;++j)table[j]=p42expert::iq2_words[j];
  const uint32_t* lookup=choice.local_table?table.data():nullptr;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<8;++sub)for(unsigned iteration=0;;++iteration){
   unsigned base=scheduled_row<V>(group,sub,0,iteration,groups);if(base>=total)break;
   for(unsigned rr=0;rr<V&&base+rr<total;++rr){unsigned logical=base+rr,row=logical%rows,slot=logical/rows;auto r=b.routes[slot];bool ok=iq3::valid_route(r,experts,rows,rows),valid=ok&&row<r.row_count;
    if(!row){b.status[slot]=!ok;if constexpr(paired)b.peer_status[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
    float values[2][32/V]{};if(valid){size_t source=size_t(r.expert_id)*rows+r.row_begin+row;for(unsigned lane=0;lane<32/V;++lane){
     if constexpr(paired){auto sums=gate_chains<V>(p58::resolve(b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),p58::resolve(b.peer,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x,lane,lookup);values[0][lane]=local_tree<V>(sums[0]);values[1][lane]=local_tree<V>(sums[1]);}
     else values[0][lane]=local_tree<V>(lane_chains<T,K,V>(p58::resolve(b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x+slot*K,lane));
    }}
    for(unsigned stream=0;stream<(paired?2u:1u);++stream){for(unsigned width=1;width<32/V;width*=2)for(unsigned lane=0;lane<32/V;lane+=2*width)values[stream][lane]=values[stream][lane]+values[stream][lane+width];(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[stream][0]:iq3::bits_float(0x7fc00000));}
   }
   if constexpr(!choice.persistent)break;
  }
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  host_run<SelectedArm>(p);
 }
#else
 template<unsigned Arm>sycl::event submit_stream_arm(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const{
  static_assert(paired);constexpr unsigned V=variants[Arm].virtualization,P=32/V;auto b=bind(p);unsigned total=b.rows*b.count,groups=(total+4*V-1)/(4*V);
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*256,256)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,stream=sub%2,physical=lane%P;
   unsigned logical=(it.get_group_linear_id()*4+sub/2)*V+lane/P,row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
   iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;float value=0;
   if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;value=local_tree<V>(lane_chains<Type::IQ2_S,2560,V>(p58::resolve(stream?b.peer:b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x,physical));}
   for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
   if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}}
  }));});
 }
 template<unsigned Arm>sycl::event submit_arm(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const {
  if constexpr(paired&&variants[Arm].virtualization>=8)return submit_stream_arm<Arm>(q,p,deps);
  else {
  constexpr auto choice=variants[Arm];constexpr unsigned V=choice.virtualization,P=32/V;auto b=bind(p);unsigned total=b.rows*b.count,groups=group_count(total,Arm);
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*workgroup_size,workgroup_size)](sycl::handler& h){sycl::local_accessor<uint32_t,1> table(choice.local_table?2048:1,h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    if constexpr(choice.local_table){for(unsigned j=it.get_local_linear_id();j<2048;j+=workgroup_size)table[j]=p42expert::iq2_words[j];it.barrier(sycl::access::fence_space::local_space);}
    const uint32_t* lookup=choice.local_table?table.template get_multi_ptr<sycl::access::decorated::no>().get():nullptr;
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,row_in_subgroup=lane/P,physical_lane=lane%P,group=it.get_group_linear_id();
    // Loop predicate uses the first row of the subgroup, never a physical
    // lane's row. Padded rows still participate in all subgroup collectives.
    for(unsigned iteration=0;scheduled_row<V>(group,sub,0,iteration,groups)<total;++iteration){
     unsigned logical=scheduled_row<V>(group,sub,row_in_subgroup,iteration,groups),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
     iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
     float value[2]{};if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
      if constexpr(paired){auto sums=gate_chains<V>(p58::resolve(b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),p58::resolve(b.peer,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x,physical_lane,lookup);value[0]=local_tree<V>(sums[0]);value[1]=local_tree<V>(sums[1]);}
      else value[0]=local_tree<V>(lane_chains<T,K,V>(p58::resolve(b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x+slot*K,physical_lane));
     }
     for(unsigned stream=0;stream<(paired?2u:1u);++stream){for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value[stream],(lane+width)%32);if(physical_lane%(2*width)==0)value[stream]=value[stream]+rhs;}
      if(in_range&&!physical_lane)(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value[stream]:iq3::bits_float(0x7fc00000));
     }
     if(in_range&&!physical_lane&&!row){b.status[slot]=!ok;if constexpr(paired)b.peer_status[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
     if constexpr(!choice.persistent)break;
    }
   }));
  });
 }
 }
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  return submit_arm<SelectedArm>(q,p,deps);
 }
#endif
};
using GateKernel=Kernel<Type::IQ2_S,2560,2>;
using DownKernel=Kernel<Type::IQ4_NL,640,3>;
} // namespace p49dvirtual
