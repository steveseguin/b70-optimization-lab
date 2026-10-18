// CPU-only production-byte gate. No backend, device, engine or GPU is created.
#include "p65_expert.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>

namespace {
using iq3::Type;
void require(bool ok,const std::string& what){if(!ok)throw std::runtime_error(what);}
struct Output {
 std::vector<uint16_t> y,peer;
 std::vector<uint32_t> status,peer_status;
 uint32_t error=0,active=1;
 Output(unsigned rows,unsigned scenario):y(rows*10,0x7e31),peer(rows*10,0x7e32),status(10,9),peer_status(10,8),error(scenario==3?7:0),active(scenario==2?0:1){}
 std::vector<uint8_t> bytes()const{
  std::vector<uint8_t> b;auto add=[&](const auto* p,size_t n){auto q=reinterpret_cast<const uint8_t*>(p);b.insert(b.end(),q,q+n);};
  add(y.data(),y.size()*2);add(peer.data(),peer.size()*2);add(status.data(),status.size()*4);add(peer_status.data(),peer_status.size()*4);add(&error,4);add(&active,4);return b;
 }
};
struct Recorder {
 std::ofstream expected,actual,cases;unsigned count=0;uint64_t chain_checks=0,tree_checks=0;
 explicit Recorder(const std::filesystem::path& p):expected(p/"expected.bin",std::ios::binary),actual(p/"candidate.bin",std::ios::binary),cases(p/"cases.jsonl"){require(bool(expected)&&bool(actual)&&bool(cases),"output files");}
 void compare(const std::vector<uint8_t>& a,const std::vector<uint8_t>& b,const std::string& desc){
  expected.write(reinterpret_cast<const char*>(a.data()),a.size());actual.write(reinterpret_cast<const char*>(b.data()),b.size());
  if(a!=b){size_t at=0;while(at<std::min(a.size(),b.size())&&a[at]==b[at])++at;throw std::runtime_error(desc+" byte mismatch at "+std::to_string(at));}
 }
};
uint32_t next(uint32_t& seed){seed=seed*1664525u+1013904223u;return seed;}
template<Type T,unsigned K>void run_shape(Recorder& rec,unsigned rows,unsigned scenario){
 constexpr bool paired=T==Type::IQ2_S;constexpr unsigned V=paired?8:16;
 const auto layout=p49bgemv::layout(T,K);const size_t stride=layout.row_bytes,raw_stride=p49bgemv::source_row_bytes(T,K);
 std::vector<uint8_t> w(rows*10*stride),peer(w.size()),raw(raw_stride);uint32_t seed=0x650049+rows+scenario;
 for(auto* bank:{&w,&peer})for(unsigned row=0;row<rows*10;++row){
  for(auto& v:raw)v=next(seed)>>24;
  auto f=iq3::layout(T);for(size_t block=0;block<raw.size();block+=f.bytes){uint16_t half=uint16_t(0x2000u+((next(seed)>>16)&0x17ff));raw[block]=half&255;raw[block+1]=half>>8;}
  p49bgemv::repack_row(T,K,raw.data(),bank->data()+row*stride);
 }
 std::vector<uint16_t> x(K*(paired?1:10));for(auto& v:x)v=iq3::bf16_bits(float(int(next(seed)%33)-16)/32.f);
 // Deliberately compare payload bits; no NaN tolerance or normalization.
 if(scenario==5){x[0]=0x7fc1;x[8]=0xffd5;}
 if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}
 if(scenario==7){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;}
 std::vector<iq3::Route> routes(10);for(unsigned i=0;i<10;++i)routes[i]={uint32_t((i*3+1)%10),0,rows};
 if(scenario>=1&&scenario<=3)routes[2].expert_id=10;
 if(scenario==4){routes[0].row_count=0;routes[1].row_count=rows-2;routes[1].row_begin=1;routes[2].row_begin=rows;routes[2].row_count=1;}
 auto pointers=[&](Output& o){std::array<void*,19> p{};p[0]=w.data();p[1]=peer.data();p[2]=x.data();p[3]=o.y.data();p[4]=o.peer.data();p[5]=routes.data();p[6]=o.status.data();p[7]=o.peer_status.data();p[16]=&o.error;p[17]=&o.active;return p;};
 Output expected(rows,scenario);auto ep=pointers(expected);p49dvirtual::Kernel<T,K,paired?2:3> production;production.rows=rows;production.count=10;production.experts=10;production.run(ep);
 auto arm=[&]<unsigned WG,bool Prefetch,bool Wide=false>(const char* name){
  Output actual(rows,scenario);auto ap=pointers(actual);p65::Kernel<T,K,WG,Prefetch,Wide> candidate;candidate.rows=rows;candidate.count=10;candidate.experts=10;candidate.run(ap);
  const std::string desc=std::string(name)+" type="+std::to_string(int(T))+" rows="+std::to_string(rows)+" scenario="+std::to_string(scenario);
  auto a=expected.bytes(),b=actual.bytes();rec.compare(a,b,desc);
  rec.cases<<"{\"candidate\":\""<<name<<"\",\"type\":"<<int(T)<<",\"columns\":"<<K<<",\"rows\":"<<rows<<",\"selected_experts\":10,\"bank_experts\":10,\"scenario\":"<<scenario<<",\"compared_bytes\":"<<a.size()<<",\"passed\":true}\n";++rec.count;
 };
 arm.template operator()<64,false>("wg64");arm.template operator()<128,false>("wg128");arm.template operator()<64,true>("prefetch64");
 arm.template operator()<64,false,true>("wide64");
 // Raw FP32 chains and full adjacent trees, independently anchored to packet49.
 // This catches a BF16-rounded match that hides a reordered accumulation.
 for(unsigned row=0;row<std::min(rows*10,64u);++row)for(unsigned stream=0;stream<(paired?2u:1u);++stream){
  const auto* weight=(stream?peer:w).data()+row*stride;const auto* input=x.data()+(paired?0:(row%10)*K);
  float baseline[32],pipelined[32],wide[32];
  for(unsigned lane=0;lane<32;++lane)baseline[lane]=p49bgemv::lane<T,K>(weight,input,0,K,lane);
  for(unsigned physical=0;physical<32/V;++physical){auto c=p65::pipelined_chains<T,K,V>(weight,input,physical);for(unsigned chain=0;chain<V;++chain){unsigned lane=physical*V+chain;pipelined[lane]=c[chain];require(std::bit_cast<uint32_t>(baseline[lane])==std::bit_cast<uint32_t>(c[chain]),"raw FP32 chain equality");++rec.chain_checks;}}
  for(unsigned physical=0;physical<32/V;++physical){auto c=p65::wide_chains<T,K,V>(weight,input,physical);for(unsigned chain=0;chain<V;++chain){unsigned lane=physical*V+chain;wide[lane]=c[chain];require(std::bit_cast<uint32_t>(baseline[lane])==std::bit_cast<uint32_t>(c[chain]),"wide raw FP32 chain equality");++rec.chain_checks;}}
  float a=iq3::tree32(baseline),b=iq3::tree32(pipelined),c=iq3::tree32(wide);require(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b),"raw FP32 tree equality");require(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(c),"wide raw FP32 tree equality");rec.tree_checks+=2;
 }
}
}
int main(int argc,char** argv){try{
 require(argc==2,"usage: p65_cpu OUTPUT_DIR");std::filesystem::path out=argv[1];std::filesystem::create_directories(out);Recorder r(out);
 run_shape<Type::IQ2_S,2560>(r,640,0);run_shape<Type::IQ4_NL,640>(r,2560,0);
 for(unsigned scenario=0;scenario<8;++scenario){run_shape<Type::IQ2_S,2560>(r,17,scenario);run_shape<Type::IQ4_NL,640>(r,17,scenario);}
 r.expected.close();r.actual.close();r.cases.close();require(bool(r.expected)&&bool(r.actual)&&bool(r.cases),"output flush");
 require(r.count==72,"case count");
 std::ofstream receipt(out/"native.json");receipt<<"{\"schema\":\"packet65.cpu-byte-identity.v1\",\"passed\":true,\"device_executed\":false,\"cases\":"<<r.count<<",\"raw_fp32_chain_checks\":"<<r.chain_checks<<",\"raw_fp32_tree_checks\":"<<r.tree_checks<<",\"nan_tolerance\":false}\n";
 std::cout<<r.count<<" cases, "<<r.chain_checks<<" raw chains, "<<r.tree_checks<<" raw trees PASS\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
