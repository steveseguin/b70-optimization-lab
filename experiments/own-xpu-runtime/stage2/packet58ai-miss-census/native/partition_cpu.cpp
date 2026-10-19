// Synthetic data only. Exact whole-output/status comparison of 0 vs 1+2.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/dc797adc79f2-p100_down.hpp"
#include <iostream>
#include <cstring>
using iq3::Type;
void check(bool x){if(!x)throw std::runtime_error("partition byte mismatch");}
uint32_t rng(uint32_t& x){return x=x*1664525u+1013904223u;}
template<bool Gate>void test(unsigned rows,unsigned placement,bool bad){
 constexpr unsigned K=Gate?2560:640,N=10,E=10;
 constexpr auto T=Gate?Type::IQ2_S:Type::IQ4_NL;
 const auto rb=p49bgemv::layout(T,K).row_bytes;
 const auto raw_rb=p49bgemv::source_row_bytes(T,K);
 const size_t bytes=E*rows*rb;
 std::vector<uint8_t>w(bytes),peer(bytes),raw(raw_rb);uint32_t seed=571;
 for(unsigned e=0;e<E*rows;++e){
   for(auto& x:raw)x=rng(seed)>>24;
   // Valid finite scales in the original packed row format.
   for(unsigned block=0;block<K/(Gate?256:32);++block){size_t off=block*(Gate?82:18);raw[off]=0;raw[off+1]=0x30;}
   p49bgemv::repack_row(T,K,raw.data(),w.data()+e*rb);
 }
 peer=w;
 if constexpr(!Gate){w=p100::transpose(w.data(),E*rows);peer=w;}
 std::vector<uint8_t>cache(2*bytes);std::memcpy(cache.data(),w.data(),bytes);std::memcpy(cache.data()+bytes,peer.data(),bytes);
 p58af::cache_begin=uintptr_t(cache.data());p58af::cache_end=p58af::cache_begin+cache.size();
 std::vector<p58::Pointer>wt(E),pt(E);
 for(unsigned e=0;e<E;++e){bool hit=placement==2||(placement==1&&e%2==0);wt[e]={uintptr_t(hit?cache.data()+e*rows*rb:w.data()+e*rows*rb),1};pt[e]={uintptr_t(hit?cache.data()+bytes+e*rows*rb:peer.data()+e*rows*rb),1};}
 std::vector<iq3::Route>routes(N);for(unsigned i=0;i<N;++i)routes[i]={i,0,rows};
 if(bad)routes[2].expert_id=E;
 std::vector<uint16_t>x(K*N);for(auto&v:x)v=iq3::bf16_bits(float(int(rng(seed)%33)-16)/32.f);
 std::vector<uint16_t>y(rows*N,0x7e31),py(y),z(y),pz(y);
 std::vector<uint32_t>status(N,9),ps(status),zs(status),pzs(status);
 uint32_t error=0,ze=0,active=1,pos=0;
 std::array<void*,19>b{};b[0]=wt.data();b[1]=pt.data();b[2]=x.data();b[3]=y.data();b[4]=py.data();b[5]=routes.data();b[6]=status.data();b[7]=ps.data();b[16]=&error;b[17]=&active;b[18]=&pos;
 using Kernel=std::conditional_t<Gate,p49dvirtual::Kernel<Type::IQ2_S,2560,2>,p100::Kernel<2>>;
 Kernel k;k.indirect=true;k.rows=rows;k.count=N;k.experts=E;p58af::partition=0;k.run(b);
 b[3]=z.data();b[4]=pz.data();b[6]=zs.data();b[7]=pzs.data();b[16]=&ze;
 p58af::partition=1;k.run(b);p58af::partition=2;k.run(b);p58af::partition=0;
 check(y==z&&py==pz&&status==zs&&ps==pzs&&error==ze);
 std::cout<<(Gate?"gate":"down")<<' '<<rows<<' '<<placement<<' '<<bad<<" PASS\n";
}
int main(){
 for(unsigned placement=0;placement<3;++placement)for(bool bad:{false,true}){
   test<true>(16,placement,bad);test<true>(640,placement,bad);
   test<false>(32,placement,bad);test<false>(2560,placement,bad);
 }
}
