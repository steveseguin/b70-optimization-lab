// CPU-only production-byte gate. No backend, device, engine or GPU is created.
#include "p65_expert.hpp"
#include "p73_hc.hpp"
#include "p90_expert.hpp"
#include "p95_expert.hpp"
#include "p90_hc.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>

namespace {
unsigned selected=0;
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
 const size_t cached_stride=paired?p90::expert_stride(K):stride;
 std::vector<uint8_t> w(rows*10*stride),peer(w.size()),cw(rows*10*cached_stride),cp(cw.size()),raw(raw_stride);uint32_t seed=0x650049+rows+scenario;
 for(auto* bank:{&w,&peer})for(unsigned row=0;row<rows*10;++row){
  for(auto& v:raw)v=next(seed)>>24;
  auto f=iq3::layout(T);for(size_t block=0;block<raw.size();block+=f.bytes){uint16_t half=uint16_t(0x2000u+((next(seed)>>16)&0x17ff));raw[block]=half&255;raw[block+1]=half>>8;}
  p49bgemv::repack_row(T,K,raw.data(),bank->data()+row*stride);
  auto& converted=bank==&w?cw:cp;
  if constexpr(paired)p90::expert_repack(K,raw.data(),converted.data()+row*cached_stride);
  else std::memcpy(converted.data()+row*cached_stride,bank->data()+row*stride,stride);
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
 Output expected(rows,scenario);auto ep=pointers(expected);p65::Kernel<T,K,64,false,true> production;production.rows=rows;production.count=10;production.experts=10;production.run(ep);
 auto arm=[&]<unsigned Followup>(const char* name){
  Output actual(rows,scenario);auto ap=pointers(actual);std::conditional_t<Followup==1&&T==Type::IQ2_S,p95exp::Kernel<T,K,64,false,true>,p65::Kernel<T,K,64,false,true>> candidate;
  candidate.rows=rows;candidate.count=10;candidate.experts=10;candidate.run(ap);
  const std::string desc=std::string(name)+" type="+std::to_string(int(T))+" rows="+std::to_string(rows)+" scenario="+std::to_string(scenario);
  auto a=expected.bytes(),b=actual.bytes();rec.compare(a,b,desc);
  rec.cases<<"{\"candidate\":\""<<name<<"\",\"type\":"<<int(T)<<",\"columns\":"<<K<<",\"rows\":"<<rows<<",\"selected_experts\":10,\"bank_experts\":10,\"scenario\":"<<scenario<<",\"compared_bytes\":"<<a.size()<<",\"passed\":true}\n";++rec.count;
 };
 if(selected==1)arm.template operator()<1>("exp-grid-prefetch");else arm.template operator()<0>("wide64");
 // Raw FP32 chains and full adjacent trees, independently anchored to packet49.
 // This catches a BF16-rounded match that hides a reordered accumulation.
 for(unsigned row=0;row<std::min(rows*10,64u);++row)for(unsigned stream=0;stream<(paired?2u:1u);++stream){
  const auto* weight=(stream?peer:w).data()+row*stride;const auto* input=x.data()+(paired?0:(row%10)*K);
  float baseline[32],pipelined[32],wide[32];
  for(unsigned lane=0;lane<32;++lane)baseline[lane]=p49bgemv::lane<T,K>(weight,input,0,K,lane);
  for(unsigned physical=0;physical<32/V;++physical){auto c=[&]{if constexpr(paired)return p95exp::grid_chains<K,V>(weight,input,physical);else return p65::wide_chains<T,K,V>(weight,input,physical);}();for(unsigned chain=0;chain<V;++chain){unsigned lane=physical*V+chain;pipelined[lane]=c[chain];require(std::bit_cast<uint32_t>(baseline[lane])==std::bit_cast<uint32_t>(c[chain]),"raw FP32 chain equality");++rec.chain_checks;}}
  for(unsigned physical=0;physical<32/V;++physical){auto c=[&]{if constexpr(!paired)return p65::wide_chains<T,K,V>(weight,input,physical);else return p65::wide_chains<T,K,V>(weight,input,physical);}();for(unsigned chain=0;chain<V;++chain){unsigned lane=physical*V+chain;wide[lane]=c[chain];require(std::bit_cast<uint32_t>(baseline[lane])==std::bit_cast<uint32_t>(c[chain]),"wide raw FP32 chain equality");++rec.chain_checks;}}
  float a=iq3::tree32(baseline),b=iq3::tree32(pipelined),c=iq3::tree32(wide);require(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b),"raw FP32 tree equality");require(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(c),"wide raw FP32 tree equality");rec.tree_checks+=2;
 }
}
void run_hc(Recorder& rec,unsigned scenario){
 const size_t rb=iq3::expanded::row_bytes(Type::Q8_0,320);
 std::vector<uint8_t> weights(10240*rb);std::vector<uint16_t> x(320),norm(10240);
 uint32_t seed=0x730060+scenario;
 for(unsigned r=0;r<10240;++r){auto w=weights.data()+r*rb;
  for(unsigned k=0;k<320;++k)w[k]=uint8_t(next(seed)>>24);
  for(unsigned k=0;k<10;++k){float d=float(int(next(seed)%63)-31)/64.f;uint32_t bits=std::bit_cast<uint32_t>(d);std::memcpy(w+320+4*k,&bits,4);}
 }
 for(auto&v:x)v=iq3::bf16_bits(float(int(next(seed)%33)-16)/32.f);
 for(auto&v:norm)v=iq3::bf16_bits(float(int(next(seed)%33)-16)/16.f);
 if(scenario==4){x[0]=0x7fc1;x[8]=0xffd5;}
 if(scenario==5){x[0]=0x7f80;x[8]=0xff80;}
 if(scenario==6){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;}
 if(scenario==7){for(auto&v:x)v=0;}
 uint32_t active=scenario==1?0:1,error=scenario==2?7:0,position=scenario==3?4096:0;
 std::vector<uint16_t> expected(10240+2560,0x7e31),actual(expected);
 p60::Bound b{};b.act=x.data();b.norm=norm.data();b.gate_w=weights.data();b.active=&active;b.error=&error;b.position=&position;
 b.gate=expected.data();b.mix=expected.data()+10240;p60::host_gate_mix(b);
 auto cached=p90::hc_from_expanded(weights.data(),10240);
 b.gate=actual.data();b.mix=actual.data()+10240;if(selected==2){b.gate_w=cached.data();p90hc::host(b);}else p73hc::host(b);
 auto bytes=[](const auto& v){const auto*p=reinterpret_cast<const uint8_t*>(v.data());return std::vector<uint8_t>(p,p+v.size()*2);};
 rec.compare(bytes(expected),bytes(actual),"hc scenario="+std::to_string(scenario));
 rec.cases<<"{\"candidate\":\""<<(selected==2?"hc-weightcache":"hc-wide")<<"\",\"scenario\":"<<scenario<<",\"compared_bytes\":"<<expected.size()*2<<",\"passed\":true}\n";++rec.count;
 // Test complete logical FP32 chains before any BF16 boundary.
 for(unsigned r=0;r<32;r+=2)for(unsigned lane=0;lane<32;++lane){
  auto c=p90hc::chains(cached.data()+r*p90::hc_stride,x.data(),lane);
  for(unsigned row=0;row<2;++row){float v=p49c::dense_lane<Type::Q8_0,320>(weights.data()+(r+row)*rb,x.data(),0,320,lane);
   require(std::bit_cast<uint32_t>(v)==std::bit_cast<uint32_t>(c[row]),"HC raw FP32 chain identity");++rec.chain_checks;
  }
 }
}

void exhaustive(Recorder& rec){
 // Test the real loader conversion for every FP16 bit pattern; original
 // nonfinite-scale refusal is retained rather than normalized or tolerated.
 const auto l=p49bgemv::layout(Type::IQ2_S,256);
 std::vector<uint8_t> src(82,0),dst(p90::expert_stride(256)),old(l.row_bytes);
 unsigned finite=0,rejected=0;
 for(unsigned h=0;h<65536;++h){
  src[0]=h&255;src[1]=h>>8;
  if((h&0x7c00)==0x7c00){bool refusal=false;try{p90::expert_repack(256,src.data(),dst.data());}catch(const std::invalid_argument&){refusal=true;}require(refusal,"nonfinite half not rejected");++rejected;continue;}
  p90::expert_repack(256,src.data(),dst.data());p49bgemv::repack_row(Type::IQ2_S,256,src.data(),old.data());
  float d=iq3::half(uint16_t(h)),cached=iq3::bits_float(p49bgemv::load32(dst.data()+l.halves));
  require(std::bit_cast<uint32_t>(d)==std::bit_cast<uint32_t>(cached),"cached half bits");
  for(unsigned nibble=0;nibble<16;++nibble){p65::RawTile t;t.a=0xa5ff;t.high=3;t.scale=nibble; t.half=h;float a[8],b[8];p65::decode_tile<Type::IQ2_S>(t,0,a);p90exp::decode_tile<Type::IQ2_S>(t,0,b,cached);require(std::memcmp(a,b,sizeof(a))==0,"all half/nibble decode bits");p95exp::GridWord grid{p42expert::iq2_words[2046],p42expert::iq2_words[2047]};float c[8];p95exp::decode_grid(t,0,grid,c);require(std::memcmp(a,c,sizeof(a))==0,"E3 all half/nibble decode bits");}
  const auto* a=reinterpret_cast<const uint8_t*>(&d);const auto* b=reinterpret_cast<const uint8_t*>(&cached);rec.compare({a,a+4},{b,b+4},"half decode");++finite;
 }
 for(unsigned index=0;index<1024;++index)for(unsigned signs=0;signs<256;++signs){p65::RawTile t;t.a=(index&255)|(signs<<8);t.high=index>>8;t.scale=0x5a;t.half=0xbc00;float a[8],b[8];p95exp::GridWord grid{p42expert::iq2_words[2*index],p42expert::iq2_words[2*index+1]};p65::decode_tile<Type::IQ2_S>(t,0,a);p95exp::decode_grid(t,0,grid,b);require(std::memcmp(a,b,sizeof(a))==0,"E3 all grid/sign bits");}
 require(finite==63488&&rejected==2048,"all half patterns covered");++rec.count;
 // HC production raw Q8 loader -> expanded scales -> exact FP32 cache.
 // Every signed code, eight zero/subnormal/normal/extreme signed half scales.
 const uint16_t halves[]={0,0x8000,1,0x8001,0x3c00,0xbc00,0x7bff,0xfbff};
 std::vector<uint8_t> q8(340);
 for(auto half:halves)for(unsigned code=0;code<256;++code){
  for(unsigned block=0;block<10;++block){q8[block*34]=half&255;q8[block*34+1]=half>>8;for(unsigned j=0;j<32;++j)q8[block*34+2+j]=uint8_t(code+j);}
  auto expanded=iq3::expanded::expand(Type::Q8_0,q8.data(),q8.size(),320);auto cached=p90::hc_repack(q8.data(),q8.size());
  for(unsigned k=0;k<320;++k){float value=iq3::bits_float(p49bgemv::load32(expanded.data()+320+4*(k/32)))*float(iq3::signed8(expanded[k]));uint32_t bits=std::bit_cast<uint32_t>(value);require(bits==p49bgemv::load32(cached.data()+4*k),"HC loader decoded bytes");}
 }
 for(uint16_t half:{uint16_t(0x7c00),uint16_t(0xfc00),uint16_t(0x7c01),uint16_t(0x7e01),uint16_t(0xfe01)}){
  q8[0]=half&255;q8[1]=half>>8;bool refused=false;
  try{(void)p90::hc_repack(q8.data(),q8.size());}catch(const std::invalid_argument&e){refused=std::string(e.what())=="p90 nonfinite HC weight scale";}
  require(refused,"nonfinite HC weight refusal");
 }
 ++rec.count;
 rec.cases<<"{\"finite_half_patterns\":63488,\"rejected_nonfinite_half_patterns\":2048,\"scale_nibbles_per_half\":16,\"hc_signed_codes\":256,\"hc_scale_patterns\":8,\"passed\":true}\n";
}

}
int main(int argc,char** argv){try{
 require(argc==3,"usage: p90_cpu VIEW OUTPUT_DIR");std::string name=argv[1];require(name=="production"||name=="exp-grid-prefetch","view");selected=name=="production"?0:1;std::filesystem::path out=argv[2];std::filesystem::create_directories(out);Recorder r(out);
 run_shape<Type::IQ2_S,2560>(r,640,0);run_shape<Type::IQ4_NL,640>(r,2560,0);
 for(unsigned scenario=0;scenario<8;++scenario){run_shape<Type::IQ2_S,2560>(r,17,scenario);run_shape<Type::IQ4_NL,640>(r,17,scenario);}

 for(unsigned scenario=0;scenario<8;++scenario)run_hc(r,scenario);
 exhaustive(r);
 r.expected.close();r.actual.close();r.cases.close();require(bool(r.expected)&&bool(r.actual)&&bool(r.cases),"output flush");
 require(r.count==28,"case count");
 std::ofstream receipt(out/"native.json");receipt<<"{\"schema\":\"packet95.cpu-byte-identity.v1\",\"passed\":true,\"device_executed\":false,\"cases\":"<<r.count<<",\"raw_fp32_chain_checks\":"<<r.chain_checks<<",\"raw_fp32_tree_checks\":"<<r.tree_checks<<",\"nan_tolerance\":false}\n";
 std::cout<<r.count<<" cases, "<<r.chain_checks<<" raw chains, "<<r.tree_checks<<" raw trees PASS\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
