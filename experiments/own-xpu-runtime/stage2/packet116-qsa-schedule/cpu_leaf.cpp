#include "p116_qsa_host.hpp"
#include <iostream>
#include <fstream>
#include <cstring>
#include <random>
void check(bool x,const char*m){if(!x)throw std::runtime_error(m);}
int main(int argc,char**argv){try{
 size_t checks=0,bytes=0;std::ofstream raw(argv[1],std::ios::binary);check(bool(raw),"output");
 auto equal=[&](const auto&a,const auto&b){check(a.size()==b.size(),"size");size_t n=a.size()*sizeof(a[0]);if(std::memcmp(a.data(),b.data(),n)){std::cerr<<"check="<<checks<<" bytes="<<n;for(size_t j=0;j<n;++j)if(reinterpret_cast<const unsigned char*>(a.data())[j]!=reinterpret_cast<const unsigned char*>(b.data())[j]){std::cerr<<" offset="<<j<<" expected="<<unsigned(reinterpret_cast<const unsigned char*>(a.data())[j])<<" actual="<<unsigned(reinterpret_cast<const unsigned char*>(b.data())[j]);break;}std::cerr<<"\n";throw std::runtime_error("raw mismatch");}uint64_t hash=1469598103934665603ull;for(size_t j=0;j<n;++j){hash^=reinterpret_cast<const unsigned char*>(a.data())[j];hash*=1099511628211ull;}raw.write(reinterpret_cast<const char*>(&hash),sizeof(hash));bytes+=n;++checks;};
 // Exhaustive signed-zero/payload tree probes. Same operands/order, different
 // evaluation schedule, two compiler families independently checked.
 for(unsigned trial=0;trial<1024;++trial){float x[128];uint32_t state=trial+1;
  for(int j=0;j<128;++j){state=1664525*state+1013904223;uint32_t bits=state; if(trial<768)bits=(state&0x807fffff)|((100+state%50)<<23);else if(trial<896)bits=(j%3?0x80000000:0);else bits=0x7f800000|(state&0x807fffff);x[j]=std::bit_cast<float>(bits);}
  std::vector<float> y(x,x+128);float expected=p47ref::adjacent(y),actual=p116::fixed_tree<0,128>([&](int j){return x[j];});equal(std::array{expected},std::array{actual});
 }
 for(int context:{1,2,3,31,32,33,63,64,65,128,4096})for(int rows:{1,2}){if(context<rows)continue;
  for(int pattern=0;pattern<7;++pattern){p47ref::Fixture first(context,rows,0x116+pattern,pattern%3),second=first;
   for(auto*f:{&first,&second}){auto a=f->args();
    if(pattern==3){a.put(0,0,std::bit_cast<float>(0x7fc10000u));a.put(2,0,std::bit_cast<float>(0x7fc20000u));a.put(3,0,std::bit_cast<float>(0x7fc30000u));}
    if(pattern==4){a.put(0,0,INFINITY);a.put(2,0,-INFINITY);a.put(3,0,INFINITY);a.put(1,0,-INFINITY);}
    if(pattern==5)a.i(18)[0]=0;if(pattern==6)a.i(15)[0]=7;
   }
   std::vector<float> before(rows*6144,-123.25f),after=before;p47ref::cpu_split(first.shape,first.args(),before.data());p116::attention_host(second.shape,second.args(),after.data());equal(before,after);
   for(int slot=0;slot<19;++slot)equal(first.data[slot],second.data[slot]);
  }
 }
 // Selection: entire input/state/scratch; tie boundaries, tails, NaN/Inf,
 // stopped/inactive controls and invalid position. Both execution orders.
 for(int context:{1,3,4,31,32,33,127,128,129,2048,2051,4096})for(int pattern=0;pattern<10;++pattern)for(int reverse=0;reverse<2;++reverse){
  ng::Shape s{};s.op=ng::select;s.capacity=context;s.budget=2048;auto need=ng::required_bytes(s);need[16]=4;
  std::array<std::vector<uint32_t>,19> a,b;for(int j=0;j<19;++j)a[j].resize((need[j]+3)/4,0x35353535);ng::Args aa,bb;for(int j=0;j<19;++j)aa.p[j]=a[j].data();
  uint32_t state=0x116;for(int slot:{0,1})for(size_t j=0;j<need[slot]/2;++j){state=1664525*state+1013904223;aa.put(slot,j,pattern==1?0.f:float(int(state%2047)-1023)/1024);}
  aa.i(15)[0]=0;aa.i(17)[0]=context-1;aa.i(18)[0]=1;
  if(pattern==2)aa.put(0,0,std::bit_cast<float>(0x7fc10000u));if(pattern==3)aa.put(1,0,INFINITY);if(pattern==4)aa.i(18)[0]=0;if(pattern==5)aa.i(15)[0]=7;if(pattern==6)aa.i(17)[0]=context;if(pattern==7)aa.i(17)[0]=-1;
  b=a;for(int j=0;j<19;++j)bb.p[j]=b[j].data();std::vector<float> x(round2::scratch_floats(s),-123.25f),y=x;
  auto prod=[&]{round2::cpu_stage<ng::select,0>(s,aa,x.data());if(pattern>=8&&!aa.i(15)[0]&&context>=4)x[0]=pattern==8?INFINITY:std::bit_cast<float>(0x7fc30000u);round2::cpu_stage<ng::select,1>(s,aa,x.data());};
  auto cand=[&]{p116::selection_host<0>(s,bb,y.data());if(pattern>=8&&!bb.i(15)[0]&&context>=4)y[0]=pattern==8?INFINITY:std::bit_cast<float>(0x7fc30000u);p116::selection_host<1>(s,bb,y.data());};
  if(reverse){cand();prod();}else{prod();cand();}for(int j=0;j<19;++j)equal(a[j],b[j]);equal(x,y);
 }
 raw.close();std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"bytes_compared\":"<<bytes<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
