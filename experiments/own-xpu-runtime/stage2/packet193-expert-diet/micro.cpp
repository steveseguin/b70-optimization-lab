// Packet193: exact instruction-diet micro of the two record expert kernels (derived from packet192's harness).
// Production (pinned, never edited): gate/up p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>, down p100::Kernel<2>,
// and the routed-activation twin p193diet::ActProduction (the record's separate silu_product launch).
// Candidates (p193_diet.hpp): exp-diet (GateUp), exp-act-epilogue (GateUpAct), down-diet (Down).
// Device mode: for every candidate, byte identity (candidate vs production on the device, and both vs the host-twin
// fixtures) on all 384 real routes, the warm route, packet162b's real rows, the NaN/invalid-route fixtures and the
// exceptional-scale bank BEFORE any timing; then cold (384 routes + 512 MiB scrub) and warm strata with production
// and candidate interleaved in both orders (pass 0 = A/B, pass 1 = B/A). Host mode (OWN_RT_HOST_ONLY twins): the same
// comparisons on CPU, the fixture files, and the random-stress proof (--stress N rows per kernel). CPU rows are never speed evidence.
#include "p90_expert.hpp"
#include "p100_down.hpp"
#include "p193_diet.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n++;}}
static volatile std::sig_atomic_t stopped=0;static void stop(int){stopped=1;}
static void require(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
namespace cfg {
constexpr unsigned KG=2560,RG=640,KD=640,RD=2560,N=10,E=512;
constexpr size_t RBG=p90::expert_stride(KG),RBD=p100::row_bytes;
static_assert(RBG==840&&RBD==360);
constexpr size_t GATE_ROWS=size_t(E)*RG,DOWN_ROWS=size_t(E)*RD;          // 327,680 / 1,310,720 rows
constexpr size_t GATE_BANK=GATE_ROWS*RBG,DOWN_BANK=DOWN_ROWS*RBD;         // 275,251,200 / 471,859,200 B
constexpr size_t OUT_G=2*RG*N*2+2*N*4+4,OUT_D=size_t(RD)*N*2+N*4+4;       // 25,684 / 51,244 B (y|py|status|peer_status|error)
constexpr size_t ACT=size_t(RG)*N*2,OUT_GA=OUT_G+ACT;                      // + 12,800 B activation = 38,484 B
constexpr size_t SCRUB_WORDS=size_t(128)*1024*1024;                        // 512 MiB (packet100 identity)
constexpr size_t REAL_ROWS=2*RG*N,REAL_RAW=820;                            // packet162b shape: 12,800 raw rows
constexpr size_t EXC_ROWS=2*RG*N,EXC_BANK=EXC_ROWS*RBG;                    // exceptional-scale bank: 10 experts x 2 streams (10,752,000 B)
constexpr size_t DEXC_ROWS=size_t(RD)*N,DEXC_BANK=DEXC_ROWS*RBD;           // down exceptional bank: 10 experts tile16 (9,216,000 B)
constexpr unsigned ROUTE_COUNT=384,CHUNK=256,WARMUPS=5,FIXTURES=3;
}
using Routes=std::array<iq3::Route,cfg::N>;
using Experts=std::array<uint32_t,cfg::N>;
struct Lcg{uint32_t s;uint32_t next(){s=s*1664525u+1013904223u;return s;}};
// Packet100's generator (seed 100): byte-identical to packet100b's / packet192's down bank.
struct DownGen{Lcg g{100};std::vector<uint16_t>hx;size_t next_row=0;
 DownGen(){hx.resize(size_t(cfg::KD)*cfg::N);for(auto&v:hx)v=iq3::bf16_bits(float(int(g.next()%63)-31)/32.f);}
 bool done()const{return next_row>=cfg::DOWN_ROWS;}
 std::vector<uint8_t> chunk(){std::vector<uint8_t>raw(cfg::CHUNK*cfg::RBD),packed(raw.size());for(auto&v:raw)v=g.next()>>24;
  for(unsigned row=0;row<cfg::CHUNK;++row){for(unsigned block=0;block<20;++block){uint16_t h=0x2400+g.next()%1024;std::memcpy(raw.data()+row*cfg::RBD+block*18,&h,2);}
   p49bgemv::repack_row(iq3::Type::IQ4_NL,cfg::KD,raw.data()+row*cfg::RBD,packed.data()+row*cfg::RBD);}
  next_row+=cfg::CHUNK;return p100::transpose(packed.data(),cfg::CHUNK);}
};
// Gate/up synthetic generator (seed 192, packet192's): raw 820-B IQ2_S rows, every block scale 0x2400, E1 repack.
struct GateGen{Lcg g{192};size_t next_row=0;static constexpr size_t TOTAL=2*cfg::GATE_ROWS;
 bool done()const{return next_row>=TOTAL;}
 std::vector<uint8_t> chunk(){std::vector<uint8_t>raw(cfg::CHUNK*cfg::REAL_RAW),out(cfg::CHUNK*cfg::RBG);for(auto&v:raw)v=g.next()>>24;
  for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}
  for(unsigned row=0;row<cfg::CHUNK;++row)p90::expert_repack(cfg::KG,raw.data()+row*cfg::REAL_RAW,out.data()+row*cfg::RBG);
  next_row+=cfg::CHUNK;return out;}
};
// Exceptional-scale banks (seed 193): random codes/high/sub-scales; the E1 FP32 scale of every block drawn from
// {half-derived finite, huge finite, +-Inf, NaN payloads, +-0, FP32 subnormal} so the hoisted `exceptional` branch,
// signed zeros and Inf/NaN payload propagation are all exercised. Down: random IQ4 codes with half scales from
// {finite, +-Inf (0x7c00/0xfc00), NaN (0x7e00/0xfe01), zero, half subnormal (0x0001/0x8001)}.
static uint32_t special_scale(Lcg&g){static const uint32_t table[]={0x7f800000u,0xff800000u,0x7fc00000u,0x7f800001u,0xffc12345u,0x00000000u,0x80000000u,0x00000001u,0x80400000u,0x7f7fffffu,0xff7fffffu,0x7e000000u};
 unsigned c=g.next()%16;if(c<8){uint32_t h=0x0400+g.next()%0x7800;return std::bit_cast<uint32_t>(iq3::half(h|((g.next()&1)<<15)));}return table[g.next()%12];}
static std::vector<uint8_t> gate_exc_bank(){Lcg g{193};std::vector<uint8_t>raw(cfg::EXC_ROWS*cfg::REAL_RAW),out(cfg::EXC_BANK);for(auto&v:raw)v=g.next()>>24;
 for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}
 const auto l=p49bgemv::layout(iq3::Type::IQ2_S,cfg::KG);
 for(size_t row=0;row<cfg::EXC_ROWS;++row){p90::expert_repack(cfg::KG,raw.data()+row*cfg::REAL_RAW,out.data()+row*cfg::RBG);
  for(unsigned b=0;b<cfg::KG/256;++b){uint32_t s=special_scale(g);std::memcpy(out.data()+row*cfg::RBG+l.halves+4*b,&s,4);}}
 return out;}
static uint16_t special_half(Lcg&g){static const uint16_t table[]={0x7c00,0xfc00,0x7e00,0xfe01,0x0000,0x8000,0x0001,0x8001,0x03ff,0x7bff,0xfbff,0x0400};
 unsigned c=g.next()%16;if(c<8)return uint16_t(0x0400+g.next()%0x7800)|uint16_t((g.next()&1)<<15);return table[g.next()%12];}
static std::vector<uint8_t> down_exc_bank(){Lcg g{1193};std::vector<uint8_t>out;out.reserve(cfg::DEXC_BANK);
 for(size_t done=0;done<cfg::DEXC_ROWS;done+=cfg::CHUNK){std::vector<uint8_t>packed(cfg::CHUNK*cfg::RBD);for(auto&v:packed)v=g.next()>>24;
  for(unsigned row=0;row<cfg::CHUNK;++row)for(unsigned block=0;block<20;++block){uint16_t h=special_half(g);std::memcpy(packed.data()+row*cfg::RBD+320+block*2,&h,2);}
  auto t=p100::transpose(packed.data(),cfg::CHUNK);out.insert(out.end(),t.begin(),t.end());}
 require(out.size()==cfg::DEXC_BANK,"down exceptional bank extent");return out;}
static std::vector<uint16_t> gate_input(uint32_t seed){std::vector<uint16_t>x(cfg::KG);Lcg g{seed};for(auto&v:x)v=iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);return x;}
// packet162b's fixture inputs: seed 162+fixture; fixture 2 plants specials (+-0, subnormals, +-Inf, NaN payloads) at i%17==0.
static std::vector<uint16_t> fixture_input(unsigned fixture,size_t n){std::vector<uint16_t>x(n);uint32_t s=162+fixture;static const uint16_t special[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2};
 for(size_t i=0;i<n;++i){s=s*1664525+1013904223;x[i]=fixture==2&&i%17==0?special[(i/17)%8]:iq3::bf16_bits(float(int(s%255)-127)/128.f);}return x;}
static Routes fixture_routes(bool invalid,unsigned rows){Routes a;for(unsigned i=0;i<cfg::N;++i)a[i]={i,0,rows};if(invalid){a[3]={512,0,rows};a[7]={7,3,rows-3};}return a;}
static std::vector<uint8_t> load_real(const std::string&path){
 std::ifstream f(path,std::ios::binary|std::ios::ate);require(bool(f)&&f.tellg()==std::streamoff(cfg::REAL_ROWS*cfg::REAL_RAW),"real rows extent: "+path);
 std::vector<uint8_t>raw(cfg::REAL_ROWS*cfg::REAL_RAW);f.seekg(0);f.read((char*)raw.data(),raw.size());require(bool(f),"real rows truncated");
 std::vector<uint8_t>out(cfg::REAL_ROWS*cfg::RBG);
 for(size_t row=0;row<cfg::REAL_ROWS;++row){const auto*s=raw.data()+row*cfg::REAL_RAW;for(unsigned b=0;b<10;++b)require((p49bgemv::load16(s+82*b)&0x7c00)!=0x7c00,"nonfinite real weight scale");p90::expert_repack(cfg::KG,s,out.data()+row*cfg::RBG);}
 return out;
}
static std::vector<Experts> parse_routes(const std::string&text){
 size_t pos=text.find("\"routes\"");require(pos!=std::string::npos,"routes key");pos=text.find('[',pos);size_t end=text.find("]]",pos);require(pos!=std::string::npos&&end!=std::string::npos,"routes array");
 std::vector<Experts>out;Experts cur{};unsigned n=0;
 for(size_t i=pos+1;i<=end;++i){char c=text[i];
  if(c=='[')n=0;else if(c==']'){if(n==cfg::N){out.push_back(cur);n=0;}else require(n==0,"route arity");}
  else if(c>='0'&&c<='9'){uint32_t v=0;while(i<=end&&text[i]>='0'&&text[i]<='9'){v=v*10+unsigned(text[i]-'0');++i;}--i;require(n<cfg::N,"route arity");cur[n++]=v;}
  else require(c==','||c==' '||c=='\n'||c=='\r'||c=='\t',"routes json");}
 require(out.size()==cfg::ROUTE_COUNT,"384 real routes required");
 for(auto&r:out)for(auto e:r)require(e<cfg::E,"expert id bound");
 return out;
}
static Routes routes_of(const Experts&e,unsigned rows){Routes r;for(unsigned i=0;i<cfg::N;++i)r[i]={e[i],0,rows};return r;}
// Fixture set: every production output the device must reproduce. Gate/up strata carry OUT_GA bytes (gate/up + act twin).
struct Fixtures{std::string dir;bool out=false;
 std::vector<uint8_t> gate_cold,gate_warm,gate_real0,gate_real24,gate_fx,gate_exc,down_cold,down_warm,down_fx,down_exc;
 static std::vector<uint8_t> read(const std::string&p,size_t bytes){std::ifstream f(p,std::ios::binary|std::ios::ate);require(bool(f)&&f.tellg()==std::streamoff(bytes),"fixture extent: "+p);std::vector<uint8_t>v(bytes);f.seekg(0);f.read((char*)v.data(),bytes);require(bool(f),"fixture read");return v;}
 void load(bool real){gate_cold=read(dir+"/gateup-cold.bin",cfg::ROUTE_COUNT*cfg::OUT_GA);gate_warm=read(dir+"/gateup-warm.bin",cfg::OUT_GA);gate_fx=read(dir+"/gateup-fx.bin",6*cfg::OUT_GA);gate_exc=read(dir+"/gateup-exc.bin",cfg::OUT_GA);
  down_cold=read(dir+"/down-cold.bin",cfg::ROUTE_COUNT*cfg::OUT_D);down_warm=read(dir+"/down-warm.bin",cfg::OUT_D);down_fx=read(dir+"/down-fx.bin",6*cfg::OUT_D);down_exc=read(dir+"/down-exc.bin",cfg::OUT_D);
  if(real){gate_real0=read(dir+"/gateup-real-layer0.bin",cfg::OUT_GA);gate_real24=read(dir+"/gateup-real-layer24.bin",cfg::OUT_GA);}}
 void write()const{auto w=[&](const char*n,const std::vector<uint8_t>&v){std::ofstream f(dir+"/"+n,std::ios::binary);f.write((const char*)v.data(),v.size());require(bool(f),"fixture write");};
  w("gateup-cold.bin",gate_cold);w("gateup-warm.bin",gate_warm);w("gateup-fx.bin",gate_fx);w("gateup-exc.bin",gate_exc);w("down-cold.bin",down_cold);w("down-warm.bin",down_warm);w("down-fx.bin",down_fx);w("down-exc.bin",down_exc);
  if(!gate_real0.empty()){w("gateup-real-layer0.bin",gate_real0);w("gateup-real-layer24.bin",gate_real24);}}
};
static size_t diff_bytes(const uint8_t*a,const uint8_t*b,size_t n){size_t d=0;for(size_t i=0;i<n;++i)d+=a[i]!=b[i];return d;}
// Classify a difference: BF16 words of the y/py/out regions that differ with BOTH sides NaN are payload-order
// differences (the compiler's operand order of an IEEE add/mul on two NaNs); anything else is a value difference.
struct Diff{size_t bytes=0,words=0,nan_vs_nan=0,other_bytes=0;bool payload_order_only()const{return bytes&&words==nan_vs_nan&&!other_bytes;}};
static Diff classify(const uint8_t*a,const uint8_t*b,size_t n,std::initializer_list<std::pair<size_t,size_t>> bf16_regions){Diff d;d.bytes=diff_bytes(a,b,n);
 std::vector<bool> covered(n,false);
 for(auto [lo,hi]:bf16_regions){for(size_t i=lo;i+1<hi&&i+1<n;i+=2){uint16_t x,y;std::memcpy(&x,a+i,2);std::memcpy(&y,b+i,2);covered[i]=covered[i+1]=true;if(x!=y){++d.words;d.nan_vs_nan+=((x&0x7fff)>0x7f80)&&((y&0x7fff)>0x7f80);}}}
 for(size_t i=0;i<n;++i)if(!covered[i]&&a[i]!=b[i])++d.other_bytes;return d;}
static Diff classify_gate(const uint8_t*a,const uint8_t*b,size_t n){return n>cfg::OUT_G?classify(a,b,n,{{0,cfg::OUT_G-2*cfg::N*4-4},{cfg::OUT_G,cfg::OUT_GA}}):classify(a,b,n,{{0,cfg::OUT_G-2*cfg::N*4-4}});}
static Diff classify_down(const uint8_t*a,const uint8_t*b,size_t n){return classify(a,b,n,{{0,size_t(cfg::RD)*cfg::N*2}});}
// exactness_claim is false for exactly one row class: exp-act-epilogue on the non-finite-scale bank ("exceptional"), where every
// gate/up output is NaN and the activation of two NaNs with distinct payloads depends on the compiler's operand order of the
// multiply (a payload-order diagnostic, never a value difference; the loader admits only finite weight scales, p48 repack rule).
static bool claim(const char*candidate,const std::string&stratum){return !(std::string(candidate)=="exp-act-epilogue"&&stratum=="exceptional");}
static void bytes_row(const char*candidate,const char*kernel,const std::string&stratum,int route,const char*against,Diff d,size_t total,bool cpu){
 std::cout<<"{\"kind\":\"bytes\",\"candidate\":\""<<candidate<<"\",\"kernel\":\""<<kernel<<"\",\"stratum\":\""<<stratum<<"\",\"route\":"<<route<<",\"against\":\""<<against<<"\",\"different_bytes\":"<<d.bytes<<",\"compared_bytes\":"<<total<<",\"bytes_equal\":"<<(d.bytes?"false":"true")<<",\"different_words\":"<<d.words<<",\"nan_vs_nan_words\":"<<d.nan_vs_nan<<",\"other_bytes\":"<<d.other_bytes<<",\"payload_order_only\":"<<(d.payload_order_only()?"true":"false")<<",\"exactness_claim\":"<<(claim(candidate,stratum)?"true":"false")<<",\"cpu_only\":"<<(cpu?"true":"false")<<"}\n";}
static void sample_row(const char*candidate,const char*arm,const char*kernel,const char*stratum,int route,unsigned pass,const char*order,unsigned rep,bool warmup,uint64_t start,uint64_t end,uint64_t gateup_ns,uint64_t act_ns,int64_t gap_ns,size_t scrub,bool cpu){
 std::cout<<"{\"kind\":\"sample\",\"candidate\":\""<<candidate<<"\",\"arm\":\""<<arm<<"\",\"kernel\":\""<<kernel<<"\",\"stratum\":\""<<stratum<<"\",\"route\":"<<route<<",\"pass\":"<<pass<<",\"order\":\""<<order<<"\",\"repeat\":"<<rep<<",\"warmup\":"<<(warmup?"true":"false")<<",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<",\"event_ns\":"<<(end-start)<<",\"gateup_ns\":"<<gateup_ns<<",\"act_ns\":"<<act_ns<<",\"gap_ns\":"<<gap_ns<<",\"scrub_bytes\":"<<scrub<<",\"exact\":true,\"cpu_only\":"<<(cpu?"true":"false")<<",\"diagnostic_only\":true}\n";}
struct Args{std::string routes,real,fixtures,fixtures_out,mode="device";unsigned cold=20,warm=200,passes=2,stress=0;bool admitted=false;int rank=-1;};
static void usage(){std::cout<<"usage: --rank 0 --routes ROUTES.json [--real-rows DIR] [--fixtures DIR | --fixtures-out DIR] --mode device|host --cold-repeats 20 --warm-repeats 200 --passes 2 [--stress ROWS] --coordinator-admitted-device-window\n";}
static unsigned number(const std::string&v){require(!v.empty()&&v.size()<=6&&std::all_of(v.begin(),v.end(),[](char c){return c>='0'&&c<='9';}),"numeric option");return unsigned(std::stoul(v));}
static Args parse(int argc,char**argv){Args a;
 for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--coordinator-admitted-device-window"){a.admitted=true;continue;}require(i+1<argc,"missing argument: "+k);std::string v=argv[++i];
  if(k=="--rank"){require(v=="0","rank must be zero");a.rank=0;}else if(k=="--routes")a.routes=v;else if(k=="--real-rows")a.real=v;else if(k=="--fixtures")a.fixtures=v;else if(k=="--fixtures-out")a.fixtures_out=v;
  else if(k=="--mode"){require(v=="device"||v=="host","mode");a.mode=v;}else if(k=="--cold-repeats")a.cold=number(v);else if(k=="--warm-repeats")a.warm=number(v);else if(k=="--passes")a.passes=number(v);else if(k=="--stress")a.stress=number(v);else throw std::runtime_error("unknown option: "+k);}
 require(a.rank==0&&!a.routes.empty()&&a.cold>=1&&a.warm>=1&&a.passes==2,"invalid micro argv (two passes: A/B then B/A)");
#ifdef OWN_RT_HOST_ONLY
 require(a.mode=="host","host twin runs --mode host only");require(!a.fixtures.empty()||!a.fixtures_out.empty(),"host twin needs --fixtures or --fixtures-out");
#else
 require(a.mode=="device"&&a.admitted&&!a.fixtures.empty()&&a.fixtures_out.empty()&&a.stress==0,"device mode requires coordinator admission and --fixtures");
#endif
 return a;}
// ---- bindings (micro convention: p[8]=activation out) ----
struct Bind{std::array<void*,19>p{};};
static Bind bind_gateup(const void*w,const void*peer,const void*x,uint8_t*o,const void*routes,const uint32_t*active){Bind b;b.p[0]=(void*)w;b.p[1]=(void*)peer;b.p[2]=(void*)x;b.p[3]=o;b.p[4]=o+cfg::RG*cfg::N*2;b.p[5]=(void*)routes;b.p[6]=o+2*cfg::RG*cfg::N*2;b.p[7]=o+2*cfg::RG*cfg::N*2+cfg::N*4;b.p[8]=o+cfg::OUT_G;b.p[16]=o+cfg::OUT_G-4;b.p[17]=(void*)active;return b;}
static Bind bind_down(const void*t,const void*x,uint8_t*o,const void*routes,const uint32_t*active){Bind b;b.p[0]=(void*)t;b.p[1]=(void*)t;b.p[2]=(void*)x;b.p[3]=o;b.p[4]=o;b.p[5]=(void*)routes;b.p[6]=o+size_t(cfg::RD)*cfg::N*2;b.p[7]=b.p[6];b.p[16]=o+cfg::OUT_D-4;b.p[17]=(void*)active;return b;}
static const char*GATE_CANDIDATES[]={"exp-diet","exp-act-epilogue"};static const char*DOWN_CANDIDATE="down-diet";
#ifdef OWN_RT_HOST_ONLY
#include <omp.h>
static uint64_t now_ns(){return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
using GateProd=p90exp::Kernel<iq3::Type::IQ2_S,cfg::KG,64,false,true>;
// production gate/up + the act twin into one OUT_GA buffer (error cleared, out prefilled 0xa5 as the device harness does)
static std::vector<uint8_t> host_gate_prod(const uint8_t*w,const uint8_t*peer,const uint16_t*x,const Routes&r,uint32_t active=1,uint32_t error0=0){std::vector<uint8_t>o(cfg::OUT_GA,0xa5);std::memcpy(o.data()+cfg::OUT_G-4,&error0,4);auto b=bind_gateup(w,peer,x,o.data(),r.data(),&active);GateProd G;G.run(b.p);p193diet::ActProduction A;A.run(b.p);return o;}
template<class K>static std::vector<uint8_t> host_gate_cand(const K&k,const uint8_t*w,const uint8_t*peer,const uint16_t*x,const Routes&r,uint32_t active=1,uint32_t error0=0){std::vector<uint8_t>o(cfg::OUT_GA,0xa5);std::memcpy(o.data()+cfg::OUT_G-4,&error0,4);auto b=bind_gateup(w,peer,x,o.data(),r.data(),&active);k.run(b.p);return o;}
template<class K>static std::vector<uint8_t> host_down(const K&k,const uint8_t*t,const uint16_t*x,const Routes&r,uint32_t active=1,uint32_t error0=0){std::vector<uint8_t>o(cfg::OUT_D,0xa5);std::memcpy(o.data()+cfg::OUT_D-4,&error0,4);auto b=bind_down(t,x,o.data(),r.data(),&active);k.run(b.p);return o;}
// Random-stress: chain-level FP32 bit identity of the diet chains against production on random rows. Two profiles:
// "mixed" (non-finite scales in ~1/4 of the blocks, 3 % special inputs: +-0, subnormals, +-Inf, NaN payloads) where a
// mismatch is classified NaN-vs-NaN (payload order: both sums NaN) or value; and "finite" (half-derived scales,
// finite inputs: the engine's admissible domain) where any mismatch is a value difference.
struct StressCount{size_t blocks=0,exceptional=0,chains=0,nan_payload=0,value=0;};
static void stress_row(const char*kernel,const char*candidate,const char*profile,unsigned rows,const StressCount&c){
 std::cout<<"{\"kind\":\"stress\",\"kernel\":\""<<kernel<<"\",\"candidate\":\""<<candidate<<"\",\"profile\":\""<<profile<<"\",\"rows\":"<<rows<<",\"blocks\":"<<c.blocks<<",\"exceptional_blocks\":"<<c.exceptional<<",\"chains_compared\":"<<c.chains<<",\"fp32_mismatches\":"<<(c.nan_payload+c.value)<<",\"nan_vs_nan_mismatches\":"<<c.nan_payload<<",\"value_mismatches\":"<<c.value<<",\"passed\":"<<(c.value?"false":"true")<<",\"cpu_only\":true,\"exactness_claim\":true}\n";}
static void stress(unsigned rows){
 const auto l=p49bgemv::layout(iq3::Type::IQ2_S,cfg::KG);static const uint16_t sp[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2,0x0080,0x7f7f};
 auto nan=[](float f){return (std::bit_cast<uint32_t>(f)&0x7fffffffu)>0x7f800000u;};
 for(int profile=0;profile<2;++profile){const bool finite=profile==1;Lcg g{finite?0x1193u:0x193u};StressCount gc,dc;
  std::vector<uint8_t>row(cfg::RBG);std::vector<uint16_t>x(cfg::KG);
  for(unsigned r=0;r<rows;++r){for(auto&v:row)v=uint8_t(g.next()>>24);
   for(unsigned b=0;b<cfg::KG/256;++b){uint32_t s;if(finite){uint32_t h=0x0400+g.next()%0x7800;s=std::bit_cast<uint32_t>(iq3::half(h|((g.next()&1)<<15)));}else s=special_scale(g);std::memcpy(row.data()+l.halves+4*b,&s,4);gc.exceptional+=(s&0x7fffffff)>=0x7f800000;}
   for(auto&v:x){unsigned c=g.next()%64;v=(!finite&&c<2)?sp[g.next()%10]:iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);}
   gc.blocks+=cfg::KG/256;
   for(unsigned lane=0;lane<4;++lane){auto p=p90exp::wide_chains<iq3::Type::IQ2_S,cfg::KG,8>(row.data(),x.data(),lane),c=p193diet::diet_chains<cfg::KG,8>(row.data(),x.data(),lane);
    for(unsigned i=0;i<8;++i){++gc.chains;if(std::bit_cast<uint32_t>(p[i])!=std::bit_cast<uint32_t>(c[i])){if(nan(p[i])&&nan(c[i]))++gc.nan_payload;else ++gc.value;}}}
  }
  std::vector<uint8_t>tile(cfg::RBD*16);std::vector<uint16_t>xd(cfg::KD);
  for(unsigned r=0;r<rows;r+=16){std::vector<uint8_t>packed(cfg::RBD*16);for(auto&v:packed)v=uint8_t(g.next()>>24);
   for(unsigned rr=0;rr<16;++rr)for(unsigned block=0;block<20;++block){uint16_t h=finite?uint16_t((0x0400+g.next()%0x7800)|((g.next()&1)<<15)):special_half(g);std::memcpy(packed.data()+rr*cfg::RBD+320+block*2,&h,2);dc.exceptional+=(h&0x7c00)==0x7c00;}
   tile=p100::transpose(packed.data(),16);
   for(auto&v:xd){unsigned c=g.next()%64;v=(!finite&&c<2)?sp[g.next()%10]:iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);}
   dc.blocks+=16*20;
   for(unsigned rr=0;rr<16;++rr)for(unsigned lane=0;lane<2;++lane){auto p=p100::tile_chains(tile.data(),rr,xd.data(),lane),c=p193diet::diet_tile_chains<false>(tile.data(),rr,xd.data(),lane);
    for(unsigned i=0;i<16;++i){++dc.chains;if(std::bit_cast<uint32_t>(p[i])!=std::bit_cast<uint32_t>(c[i])){if(nan(p[i])&&nan(c[i]))++dc.nan_payload;else ++dc.value;}}}
  }
  stress_row("gateup","exp-diet",finite?"finite":"mixed",rows,gc);stress_row("down","down-diet",finite?"finite":"mixed",rows,dc);
 }
}
static int host_main(const Args&a){
 std::ifstream rf(a.routes);std::stringstream ss;ss<<rf.rdbuf();auto experts=parse_routes(ss.str());
 std::cout<<"{\"kind\":\"start\",\"mode\":\"host\",\"routes\":"<<experts.size()<<",\"threads\":"<<omp_get_max_threads()<<",\"candidates\":[\"exp-diet\",\"exp-act-epilogue\",\"down-diet\"],\"cpu_only\":true}\n"<<std::flush;
 std::vector<uint8_t>gate(cfg::GATE_BANK),up(cfg::GATE_BANK),down(cfg::DOWN_BANK);
 {GateGen g;size_t row=0;while(!g.done()){auto c=g.chunk();size_t off=row*cfg::RBG;if(off<cfg::GATE_BANK)std::memcpy(gate.data()+off,c.data(),c.size());else std::memcpy(up.data()+off-cfg::GATE_BANK,c.data(),c.size());row+=cfg::CHUNK;}}
 DownGen d;{size_t row=0;while(!d.done()){auto c=d.chunk();std::memcpy(down.data()+row*cfg::RBD,c.data(),c.size());row+=cfg::CHUNK;}}
 auto gexc=gate_exc_bank();auto dexc=down_exc_bank();
 auto xg=gate_input(192),xr=gate_input(162);std::vector<uint8_t>real0,real24;bool real=!a.real.empty();if(real){real0=load_real(a.real+"/layer0.bin");real24=load_real(a.real+"/layer24.bin");}
 p193diet::GateUp GD;p193diet::GateUpAct GE;p100::Kernel<2>D;p193diet::Down DD;
 Fixtures fx;fx.dir=a.fixtures_out.empty()?a.fixtures:a.fixtures_out;fx.out=!a.fixtures_out.empty();
 if(!fx.out)fx.load(real);else{fx.gate_cold.resize(cfg::ROUTE_COUNT*cfg::OUT_GA);fx.down_cold.resize(cfg::ROUTE_COUNT*cfg::OUT_D);fx.gate_fx.resize(6*cfg::OUT_GA);fx.down_fx.resize(6*cfg::OUT_D);}
 auto gate_compare=[&](const std::string&stratum,int route,const std::vector<uint8_t>&prod,const std::vector<uint8_t>&cd,const std::vector<uint8_t>&ce,const uint8_t*fixture){
  bytes_row("production","gateup",stratum,route,"fixture",fx.out?Diff{}:classify_gate(prod.data(),fixture,cfg::OUT_GA),cfg::OUT_GA,true);
  bytes_row("exp-diet","gateup",stratum,route,"production",classify_gate(cd.data(),prod.data(),cfg::OUT_G),cfg::OUT_G,true);
  bytes_row("exp-diet","gateup",stratum,route,"fixture",fx.out?classify_gate(cd.data(),prod.data(),cfg::OUT_G):classify_gate(cd.data(),fixture,cfg::OUT_G),cfg::OUT_G,true);
  bytes_row("exp-act-epilogue","gateup",stratum,route,"production",classify_gate(ce.data(),prod.data(),cfg::OUT_GA),cfg::OUT_GA,true);
  bytes_row("exp-act-epilogue","gateup",stratum,route,"fixture",fx.out?classify_gate(ce.data(),prod.data(),cfg::OUT_GA):classify_gate(ce.data(),fixture,cfg::OUT_GA),cfg::OUT_GA,true);};
 auto down_compare=[&](const std::string&stratum,int route,const std::vector<uint8_t>&prod,const std::vector<uint8_t>&cd,const uint8_t*fixture){
  bytes_row("production","down",stratum,route,"fixture",fx.out?Diff{}:classify_down(prod.data(),fixture,cfg::OUT_D),cfg::OUT_D,true);
  bytes_row("down-diet","down",stratum,route,"production",classify_down(cd.data(),prod.data(),cfg::OUT_D),cfg::OUT_D,true);
  bytes_row("down-diet","down",stratum,route,"fixture",fx.out?classify_down(cd.data(),prod.data(),cfg::OUT_D):classify_down(cd.data(),fixture,cfg::OUT_D),cfg::OUT_D,true);};
 // cold stratum on CPU: one launch per route per arm (parallel across routes; rows emitted in order)
 struct Cold{std::vector<uint8_t>gp,gd,ge,dp,dd;uint64_t gns=0,dns=0;};std::vector<Cold>cold(cfg::ROUTE_COUNT);
 #pragma omp parallel for schedule(dynamic)
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){auto rg=routes_of(experts[r],cfg::RG),rd=routes_of(experts[r],cfg::RD);auto&c=cold[r];
  uint64_t t0=now_ns();c.gp=host_gate_prod(gate.data(),up.data(),xg.data(),rg);uint64_t t1=now_ns();c.gd=host_gate_cand(GD,gate.data(),up.data(),xg.data(),rg);c.ge=host_gate_cand(GE,gate.data(),up.data(),xg.data(),rg);
  uint64_t t2=now_ns();c.dp=host_down(D,down.data(),d.hx.data(),rd);uint64_t t3=now_ns();c.dd=host_down(DD,down.data(),d.hx.data(),rd);c.gns=t1-t0;c.dns=t3-t2;
  if(fx.out){std::memcpy(fx.gate_cold.data()+size_t(r)*cfg::OUT_GA,c.gp.data(),cfg::OUT_GA);std::memcpy(fx.down_cold.data()+size_t(r)*cfg::OUT_D,c.dp.data(),cfg::OUT_D);}}
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){auto&c=cold[r];gate_compare("cold",int(r),c.gp,c.gd,c.ge,fx.gate_cold.data()+size_t(r)*cfg::OUT_GA);down_compare("cold",int(r),c.dp,c.dd,fx.down_cold.data()+size_t(r)*cfg::OUT_D);}
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){sample_row("production","production","gateup","cold",int(r),0,"AB",0,false,0,cold[r].gns,cold[r].gns,0,0,0,true);sample_row("production","production","down","cold",int(r),0,"AB",0,false,0,cold[r].dns,0,0,0,0,true);}
 // warm (route 0 experts), real shapes, NaN/invalid fixtures, exceptional banks
 auto rg0=routes_of(experts[0],cfg::RG),rd0=routes_of(experts[0],cfg::RD);
 {auto gp=host_gate_prod(gate.data(),up.data(),xg.data(),rg0),gd=host_gate_cand(GD,gate.data(),up.data(),xg.data(),rg0),ge=host_gate_cand(GE,gate.data(),up.data(),xg.data(),rg0);if(fx.out)fx.gate_warm=gp;gate_compare("warm",-1,gp,gd,ge,fx.gate_warm.data());
  auto dp=host_down(D,down.data(),d.hx.data(),rd0),dd=host_down(DD,down.data(),d.hx.data(),rd0);if(fx.out)fx.down_warm=dp;down_compare("warm",-1,dp,dd,fx.down_warm.data());}
 if(real){Routes rr=fixture_routes(false,cfg::RG);
  for(int which=0;which<2;++which){const auto&bank=which?real24:real0;const uint8_t*w=bank.data(),*peer=bank.data()+cfg::RG*cfg::N*cfg::RBG;
   auto gp=host_gate_prod(w,peer,xr.data(),rr),gd=host_gate_cand(GD,w,peer,xr.data(),rr),ge=host_gate_cand(GE,w,peer,xr.data(),rr);
   if(fx.out)(which?fx.gate_real24:fx.gate_real0)=gp;gate_compare(which?"warm-real-layer24":"warm-real-layer0",-1,gp,gd,ge,(which?fx.gate_real24:fx.gate_real0).data());}}
 for(unsigned f=0;f<cfg::FIXTURES;++f)for(unsigned bad=0;bad<2;++bad){unsigned slot=f*2+bad;std::string name="fixture-f"+std::to_string(f)+(bad?"-invalid":"-valid");
  auto xf=fixture_input(f,cfg::KG);auto rr=fixture_routes(bad,cfg::RG);
  auto gp=host_gate_prod(gate.data(),up.data(),xf.data(),rr),gd=host_gate_cand(GD,gate.data(),up.data(),xf.data(),rr),ge=host_gate_cand(GE,gate.data(),up.data(),xf.data(),rr);
  if(fx.out)std::memcpy(fx.gate_fx.data()+slot*cfg::OUT_GA,gp.data(),cfg::OUT_GA);gate_compare(name,-1,gp,gd,ge,fx.gate_fx.data()+slot*cfg::OUT_GA);
  auto xd=fixture_input(f,size_t(cfg::KD)*cfg::N);auto rd=fixture_routes(bad,cfg::RD);
  auto dp=host_down(D,down.data(),xd.data(),rd),dd=host_down(DD,down.data(),xd.data(),rd);
  if(fx.out)std::memcpy(fx.down_fx.data()+slot*cfg::OUT_D,dp.data(),cfg::OUT_D);down_compare(name,-1,dp,dd,fx.down_fx.data()+slot*cfg::OUT_D);}
 {auto xf=fixture_input(2,cfg::KG);auto rr=fixture_routes(false,cfg::RG);const uint8_t*w=gexc.data(),*peer=gexc.data()+cfg::RG*cfg::N*cfg::RBG;
  auto gp=host_gate_prod(w,peer,xf.data(),rr),gd=host_gate_cand(GD,w,peer,xf.data(),rr),ge=host_gate_cand(GE,w,peer,xf.data(),rr);if(fx.out)fx.gate_exc=gp;gate_compare("exceptional",-1,gp,gd,ge,fx.gate_exc.data());
  auto xd=fixture_input(2,size_t(cfg::KD)*cfg::N);auto rd=fixture_routes(false,cfg::RD);
  auto dp=host_down(D,dexc.data(),xd.data(),rd),dd=host_down(DD,dexc.data(),xd.data(),rd);if(fx.out)fx.down_exc=dp;down_compare("exceptional",-1,dp,dd,fx.down_exc.data());}
 // inactive / pre-set error gating of the activation epilogue (the separate launch must not write `out`)
 {auto rr=fixture_routes(false,cfg::RG);for(int mode=0;mode<2;++mode){uint32_t active=mode?1u:0u,error0=mode?1u:0u;
  auto gp=host_gate_prod(gate.data(),up.data(),xg.data(),rr,active,error0),ge=host_gate_cand(GE,gate.data(),up.data(),xg.data(),rr,active,error0);
  bytes_row("exp-act-epilogue","gateup",mode?"error-preset":"inactive",-1,"production",classify_gate(ge.data(),gp.data(),cfg::OUT_GA),cfg::OUT_GA,true);}}
 if(a.stress)stress(a.stress);
 // warm dry run of the timing loop (sequential, few repeats; CPU time only)
 for(unsigned pass=0;pass<a.passes;++pass){const char*order=pass?"BA":"AB";
  for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_gate_prod(gate.data(),up.data(),xg.data(),rg0);uint64_t t1=now_ns();host_gate_cand(GD,gate.data(),up.data(),xg.data(),rg0);uint64_t t2=now_ns();
   sample_row("exp-diet","production","gateup","warm",-1,pass,order,rep,false,t0,t1,t1-t0,0,0,0,true);sample_row("exp-diet","candidate","gateup","warm",-1,pass,order,rep,false,t1,t2,t2-t1,0,0,0,true);}
  for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_down(D,down.data(),d.hx.data(),rd0);uint64_t t1=now_ns();host_down(DD,down.data(),d.hx.data(),rd0);uint64_t t2=now_ns();
   sample_row("down-diet","production","down","warm",-1,pass,order,rep,false,t0,t1,0,0,0,0,true);sample_row("down-diet","candidate","down","warm",-1,pass,order,rep,false,t1,t2,0,0,0,0,true);}}
 if(fx.out)fx.write();
 std::cout<<"{\"kind\":\"summary\",\"schema\":\"packet193.diet.v1\",\"passed\":true,\"drained\":true,\"diagnostic_only\":true,\"mode\":\"host\",\"cpu_only\":true,\"route_count\":"<<cfg::ROUTE_COUNT<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"real_shapes\":"<<(real?"true":"false")<<",\"fixtures_written\":"<<(fx.out?"true":"false")<<",\"stress_rows\":"<<a.stress<<",\"candidates\":[\"exp-diet\",\"exp-act-epilogue\",\"down-diet\"]}\n"<<std::flush;
 return 0;
}
#else
// ---- device mode ----
struct Dev{sycl::queue q;size_t live=0,peak=0;std::vector<std::pair<void*,size_t>>held;
 Dev():q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}}){}
 void*alloc(size_t n){void*p=sycl::malloc_device(n,q);if(!p)throw std::bad_alloc();held.push_back({p,n});live+=n;peak=std::max(peak,live);return p;}
 void release(void*p){for(auto it=held.begin();it!=held.end();++it)if(it->first==p){q.wait_and_throw();sycl::free(p,q);live-=it->second;held.erase(it);return;}throw std::logic_error("release");}
 ~Dev(){try{q.wait_and_throw();}catch(...){}for(auto&h:held)sycl::free(h.first,q);}
};
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
static void allocation_row(const Dev&d,const char*phase){std::cout<<"{\"kind\":\"allocation\",\"phase\":\""<<phase<<"\",\"device_live_bytes\":"<<d.live<<",\"device_peak_bytes\":"<<d.peak<<"}\n"<<std::flush;}
struct Ev{uint64_t s,t;};
static Ev prof(sycl::event e){e.wait_and_throw();return {e.get_profiling_info<sycl::info::event_profiling::command_start>(),e.get_profiling_info<sycl::info::event_profiling::command_end>()};}
// One timed arm: production = gate/up (+ act twin for the epilogue candidate) or candidate; returns the sample fields.
struct Timed{uint64_t start,end,gateup,act;int64_t gap;};
template<class LaunchA,class LaunchB>static void interleaved(Dev&d,uint32_t*scrub,const char*candidate,const char*kernel,const char*stratum,int route,unsigned pass,unsigned repeats,bool cold,LaunchA production,LaunchB cand){
 const char*order=pass?"BA":"AB";unsigned warm=cold?0:cfg::WARMUPS;
 for(unsigned rep=0;rep<warm+repeats;++rep){guard();
  for(unsigned which=0;which<2;++which){bool prod=(which==0)==(pass==0);
   if(cold)d.q.parallel_for(sycl::range<1>(cfg::SCRUB_WORDS),[=](sycl::id<1>id){scrub[id]=uint32_t(id[0]);}).wait_and_throw();
   Timed t=prod?production():cand();
   sample_row(candidate,prod?"production":"candidate",kernel,stratum,route,pass,order,rep<warm?rep:rep-warm,rep<warm,t.start,t.end,t.gateup,t.act,t.gap,cold?cfg::SCRUB_WORDS*4:0,false);}}
 std::cout<<std::flush;
}
static int device_main(const Args&a){
 std::ifstream rf(a.routes);std::stringstream ss;ss<<rf.rdbuf();auto experts=parse_routes(ss.str());
 const char*probe=std::getenv("ENTRY_PREPARE_OUTPUT");
 if(probe){ // CPU preparation path: parse, bound, exercise every generator on one chunk; no device API.
  GateGen g;auto gc=g.chunk();DownGen d;auto dc=d.chunk();require(gc.size()==cfg::CHUNK*cfg::RBG&&dc.size()==cfg::CHUNK*cfg::RBD,"generator chunk extents");
  {Lcg s{193};unsigned exc=0;for(unsigned i=0;i<256;++i)exc+=(special_scale(s)&0x7fffffff)>=0x7f800000;require(exc>0,"exceptional scales present");}
  size_t device_bytes=cfg::SCRUB_WORDS*4+std::max(2*cfg::GATE_BANK+2*cfg::REAL_ROWS*cfg::RBG+cfg::EXC_BANK+(2+cfg::FIXTURES)*cfg::KG*2+cfg::OUT_GA,cfg::DOWN_BANK+cfg::DEXC_BANK+(1+cfg::FIXTURES)*cfg::KD*cfg::N*2+cfg::OUT_D)+256;
  std::ofstream(std::string(probe)+"/prepare.json")<<"{\"passed\":true,\"device_executed\":false,\"routes\":"<<experts.size()<<",\"planned_device_peak_bytes\":"<<device_bytes<<",\"gate_bank_bytes\":"<<cfg::GATE_BANK<<",\"down_bank_bytes\":"<<cfg::DOWN_BANK<<",\"exceptional_bank_bytes\":"<<cfg::EXC_BANK<<",\"down_exceptional_bank_bytes\":"<<cfg::DEXC_BANK<<",\"scrub_bytes\":"<<cfg::SCRUB_WORDS*4<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"candidates\":3}\n";
  std::cout<<"PASS CPU preparation before first device call; routes="<<experts.size()<<" planned_device_peak_bytes="<<device_bytes<<"\n";return 0;}
 Fixtures fx;fx.dir=a.fixtures;fx.load(!a.real.empty());
 std::vector<uint8_t>real0,real24;bool real=!a.real.empty();if(real){real0=load_real(a.real+"/layer0.bin");real24=load_real(a.real+"/layer24.bin");}
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 Dev d;std::cout<<"{\"kind\":\"start\",\"mode\":\"device\",\"device\":\""<<d.q.get_device().get_info<sycl::info::device::name>()<<"\",\"routes\":"<<experts.size()<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"warmups\":"<<cfg::WARMUPS<<",\"candidates\":[\"exp-diet\",\"exp-act-epilogue\",\"down-diet\"]}\n"<<std::flush;
 auto*scrub=(uint32_t*)d.alloc(cfg::SCRUB_WORDS*4);
 auto upload=[&](uint8_t*dst,auto&gen,size_t total){std::vector<uint8_t>stage;stage.reserve(16*cfg::CHUNK*cfg::RBG);size_t off=0;while(!gen.done()){guard();stage.clear();for(unsigned i=0;i<16&&!gen.done();++i){auto c=gen.chunk();stage.insert(stage.end(),c.begin(),c.end());}d.q.memcpy(dst+off,stage.data(),stage.size()).wait_and_throw();off+=stage.size();}require(off==total,"bank upload extent");};
 auto fetch=[&](const uint8_t*o,size_t n){std::vector<uint8_t>v(n);d.q.memcpy(v.data(),o,n).wait_and_throw();return v;};
 uint32_t one=1,zero=0;
 // ---------------- phase 1: gate/up ----------------
 {auto*gate=(uint8_t*)d.alloc(2*cfg::GATE_BANK);auto*up=gate+cfg::GATE_BANK;{GateGen g;upload(gate,g,2*cfg::GATE_BANK);}
  auto xg=gate_input(192),xr=gate_input(162);auto*x=(uint16_t*)d.alloc(cfg::KG*2);auto*xdr=(uint16_t*)d.alloc(cfg::KG*2);d.q.memcpy(x,xg.data(),cfg::KG*2);d.q.memcpy(xdr,xr.data(),cfg::KG*2);
  uint16_t*xf[cfg::FIXTURES];for(unsigned f=0;f<cfg::FIXTURES;++f){auto h=fixture_input(f,cfg::KG);xf[f]=(uint16_t*)d.alloc(cfg::KG*2);d.q.memcpy(xf[f],h.data(),cfg::KG*2).wait_and_throw();}
  auto*exc=(uint8_t*)d.alloc(cfg::EXC_BANK);{auto h=gate_exc_bank();d.q.memcpy(exc,h.data(),h.size()).wait_and_throw();}
  auto*routes=(iq3::Route*)d.alloc(sizeof(Routes));auto*o=(uint8_t*)d.alloc(cfg::OUT_GA);auto*active=(uint32_t*)d.alloc(4);d.q.memcpy(active,&one,4).wait_and_throw();
  uint8_t*r0=nullptr,*r24=nullptr;if(real){r0=(uint8_t*)d.alloc(real0.size());r24=(uint8_t*)d.alloc(real24.size());d.q.memcpy(r0,real0.data(),real0.size());d.q.memcpy(r24,real24.data(),real24.size()).wait_and_throw();}
  allocation_row(d,"gateup");
  p90exp::Kernel<iq3::Type::IQ2_S,cfg::KG,64,false,true>G;p193diet::ActProduction A;p193diet::GateUp GD;p193diet::GateUpAct GE;
  auto set_routes=[&](const Routes&r){d.q.memcpy(routes,r.data(),sizeof(Routes)).wait_and_throw();};
  auto clear=[&](uint32_t error0=0){d.q.memset(o,0xa5,cfg::OUT_GA);d.q.memcpy(o+cfg::OUT_G-4,&error0,4).wait_and_throw();};
  auto launch=[&](auto&k,const uint8_t*w,const uint8_t*peer,const uint16_t*xx){auto b=bind_gateup(w,peer,xx,o,routes,active);return k.submit(d.q,b.p,{});};
  // production pair = gate/up then the act twin (in-order queue); the device output is the OUT_GA image
  auto run_prod=[&](const uint8_t*w,const uint8_t*peer,const uint16_t*xx){launch(G,w,peer,xx);launch(A,w,peer,xx).wait_and_throw();return fetch(o,cfg::OUT_GA);};
  auto exact=[&](const std::string&stratum,int route,const uint8_t*w,const uint8_t*peer,const uint16_t*xx,const uint8_t*fixture,uint32_t error0=0){
   clear(error0);auto prod=run_prod(w,peer,xx);bytes_row("production","gateup",stratum,route,"fixture",classify_gate(prod.data(),fixture,cfg::OUT_GA),cfg::OUT_GA,false);
   clear(error0);launch(GD,w,peer,xx).wait_and_throw();auto cd=fetch(o,cfg::OUT_G);bytes_row("exp-diet","gateup",stratum,route,"production",classify_gate(cd.data(),prod.data(),cfg::OUT_G),cfg::OUT_G,false);bytes_row("exp-diet","gateup",stratum,route,"fixture",classify_gate(cd.data(),fixture,cfg::OUT_G),cfg::OUT_G,false);
   clear(error0);launch(GE,w,peer,xx).wait_and_throw();auto ce=fetch(o,cfg::OUT_GA);bytes_row("exp-act-epilogue","gateup",stratum,route,"production",classify_gate(ce.data(),prod.data(),cfg::OUT_GA),cfg::OUT_GA,false);bytes_row("exp-act-epilogue","gateup",stratum,route,"fixture",classify_gate(ce.data(),fixture,cfg::OUT_GA),cfg::OUT_GA,false);};
  for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){guard();set_routes(routes_of(experts[r],cfg::RG));exact("cold",int(r),gate,up,x,fx.gate_cold.data()+size_t(r)*cfg::OUT_GA);}
  auto rg0=routes_of(experts[0],cfg::RG);set_routes(rg0);exact("warm",-1,gate,up,x,fx.gate_warm.data());
  Routes rr=fixture_routes(false,cfg::RG);
  if(real){set_routes(rr);exact("warm-real-layer0",-1,r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr,fx.gate_real0.data());exact("warm-real-layer24",-1,r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr,fx.gate_real24.data());}
  for(unsigned f=0;f<cfg::FIXTURES;++f)for(unsigned bad=0;bad<2;++bad){set_routes(fixture_routes(bad,cfg::RG));exact("fixture-f"+std::to_string(f)+(bad?"-invalid":"-valid"),-1,gate,up,xf[f],fx.gate_fx.data()+(f*2+bad)*cfg::OUT_GA);}
  set_routes(rr);exact("exceptional",-1,exc,exc+cfg::RG*cfg::N*cfg::RBG,xf[2],fx.gate_exc.data());
  {set_routes(rr);d.q.memcpy(active,&zero,4).wait_and_throw();clear();auto prod=run_prod(gate,up,x);clear();launch(GE,gate,up,x).wait_and_throw();auto ce=fetch(o,cfg::OUT_GA);bytes_row("exp-act-epilogue","gateup","inactive",-1,"production",classify_gate(ce.data(),prod.data(),cfg::OUT_GA),cfg::OUT_GA,false);
   d.q.memcpy(active,&one,4).wait_and_throw();clear(1);prod=run_prod(gate,up,x);clear(1);launch(GE,gate,up,x).wait_and_throw();ce=fetch(o,cfg::OUT_GA);bytes_row("exp-act-epilogue","gateup","error-preset",-1,"production",classify_gate(ce.data(),prod.data(),cfg::OUT_GA),cfg::OUT_GA,false);}
  std::cout<<std::flush;clear();
  // timing: production vs each candidate, interleaved, both orders
  auto prod_pair=[&](const uint8_t*w,const uint8_t*peer,const uint16_t*xx){auto e1=launch(G,w,peer,xx);auto e2=launch(A,w,peer,xx);Ev g=prof(e1),t=prof(e2);return Timed{g.s,g.t+(t.t-t.s),g.t-g.s,t.t-t.s,int64_t(t.s)-int64_t(g.t)};};
  auto prod_only=[&](const uint8_t*w,const uint8_t*peer,const uint16_t*xx){Ev g=prof(launch(G,w,peer,xx));return Timed{g.s,g.t,g.t-g.s,0,0};};
  auto cand_run=[&](auto&k,const uint8_t*w,const uint8_t*peer,const uint16_t*xx){Ev g=prof(launch(k,w,peer,xx));return Timed{g.s,g.t,g.t-g.s,0,0};};
  for(unsigned pass=0;pass<a.passes;++pass){
   for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){set_routes(routes_of(experts[r],cfg::RG));
    interleaved(d,scrub,"exp-diet","gateup","cold",int(r),pass,a.cold,true,[&]{return prod_only(gate,up,x);},[&]{return cand_run(GD,gate,up,x);});
    interleaved(d,scrub,"exp-act-epilogue","gateup","cold",int(r),pass,a.cold,true,[&]{return prod_pair(gate,up,x);},[&]{return cand_run(GE,gate,up,x);});}
   set_routes(rg0);interleaved(d,scrub,"exp-diet","gateup","warm",-1,pass,a.warm,false,[&]{return prod_only(gate,up,x);},[&]{return cand_run(GD,gate,up,x);});
   interleaved(d,scrub,"exp-act-epilogue","gateup","warm",-1,pass,a.warm,false,[&]{return prod_pair(gate,up,x);},[&]{return cand_run(GE,gate,up,x);});
   if(real){set_routes(rr);
    interleaved(d,scrub,"exp-diet","gateup","warm-real-layer0",-1,pass,a.warm,false,[&]{return prod_only(r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr);},[&]{return cand_run(GD,r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr);});
    interleaved(d,scrub,"exp-diet","gateup","warm-real-layer24",-1,pass,a.warm,false,[&]{return prod_only(r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr);},[&]{return cand_run(GD,r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr);});
    interleaved(d,scrub,"exp-act-epilogue","gateup","warm-real-layer0",-1,pass,a.warm,false,[&]{return prod_pair(r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr);},[&]{return cand_run(GE,r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr);});
    interleaved(d,scrub,"exp-act-epilogue","gateup","warm-real-layer24",-1,pass,a.warm,false,[&]{return prod_pair(r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr);},[&]{return cand_run(GE,r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr);});}}
  d.q.wait_and_throw();for(void*p:{(void*)gate,(void*)x,(void*)xdr,(void*)exc,(void*)routes,(void*)o,(void*)active})d.release(p);for(unsigned f=0;f<cfg::FIXTURES;++f)d.release(xf[f]);if(real){d.release(r0);d.release(r24);}
 }
 // ---------------- phase 2: down (tile16) ----------------
 {auto*t=(uint8_t*)d.alloc(cfg::DOWN_BANK);DownGen g;upload(t,g,cfg::DOWN_BANK);
  auto*x=(uint16_t*)d.alloc(size_t(cfg::KD)*cfg::N*2);d.q.memcpy(x,g.hx.data(),g.hx.size()*2);
  uint16_t*xf[cfg::FIXTURES];for(unsigned f=0;f<cfg::FIXTURES;++f){auto h=fixture_input(f,size_t(cfg::KD)*cfg::N);xf[f]=(uint16_t*)d.alloc(h.size()*2);d.q.memcpy(xf[f],h.data(),h.size()*2).wait_and_throw();}
  auto*exc=(uint8_t*)d.alloc(cfg::DEXC_BANK);{auto h=down_exc_bank();d.q.memcpy(exc,h.data(),h.size()).wait_and_throw();}
  auto*routes=(iq3::Route*)d.alloc(sizeof(Routes));auto*o=(uint8_t*)d.alloc(cfg::OUT_D);auto*active=(uint32_t*)d.alloc(4);d.q.memcpy(active,&one,4).wait_and_throw();
  allocation_row(d,"down");
  p100::Kernel<2>D;p193diet::Down DD;
  auto set_routes=[&](const Routes&r){d.q.memcpy(routes,r.data(),sizeof(Routes)).wait_and_throw();};
  auto clear=[&]{d.q.memset(o,0xa5,cfg::OUT_D);d.q.memset(o+cfg::OUT_D-4,0,4).wait_and_throw();};
  auto launch=[&](auto&k,const uint8_t*bank,const uint16_t*xx){auto b=bind_down(bank,xx,o,routes,active);return k.submit(d.q,b.p,{});};
  auto exact=[&](const std::string&stratum,int route,const uint8_t*bank,const uint16_t*xx,const uint8_t*fixture){
   clear();launch(D,bank,xx).wait_and_throw();auto prod=fetch(o,cfg::OUT_D);bytes_row("production","down",stratum,route,"fixture",classify_down(prod.data(),fixture,cfg::OUT_D),cfg::OUT_D,false);
   clear();launch(DD,bank,xx).wait_and_throw();auto cd=fetch(o,cfg::OUT_D);bytes_row("down-diet","down",stratum,route,"production",classify_down(cd.data(),prod.data(),cfg::OUT_D),cfg::OUT_D,false);bytes_row("down-diet","down",stratum,route,"fixture",classify_down(cd.data(),fixture,cfg::OUT_D),cfg::OUT_D,false);};
  for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){guard();set_routes(routes_of(experts[r],cfg::RD));exact("cold",int(r),t,x,fx.down_cold.data()+size_t(r)*cfg::OUT_D);}
  auto rd0=routes_of(experts[0],cfg::RD);set_routes(rd0);exact("warm",-1,t,x,fx.down_warm.data());
  for(unsigned f=0;f<cfg::FIXTURES;++f)for(unsigned bad=0;bad<2;++bad){set_routes(fixture_routes(bad,cfg::RD));exact("fixture-f"+std::to_string(f)+(bad?"-invalid":"-valid"),-1,t,xf[f],fx.down_fx.data()+(f*2+bad)*cfg::OUT_D);}
  set_routes(fixture_routes(false,cfg::RD));exact("exceptional",-1,exc,xf[2],fx.down_exc.data());
  std::cout<<std::flush;clear();
  auto prod_run=[&]{Ev g=prof(launch(D,t,x));return Timed{g.s,g.t,0,0,0};};auto cand_run=[&]{Ev g=prof(launch(DD,t,x));return Timed{g.s,g.t,0,0,0};};
  for(unsigned pass=0;pass<a.passes;++pass){
   for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){set_routes(routes_of(experts[r],cfg::RD));interleaved(d,scrub,"down-diet","down","cold",int(r),pass,a.cold,true,prod_run,cand_run);}
   set_routes(rd0);interleaved(d,scrub,"down-diet","down","warm",-1,pass,a.warm,false,prod_run,cand_run);}
  d.q.wait_and_throw();for(void*p:{(void*)t,(void*)x,(void*)exc,(void*)routes,(void*)o,(void*)active})d.release(p);for(unsigned f=0;f<cfg::FIXTURES;++f)d.release(xf[f]);
 }
 d.q.wait_and_throw();guard();
 std::cout<<"{\"kind\":\"summary\",\"schema\":\"packet193.diet.v1\",\"passed\":true,\"drained\":true,\"diagnostic_only\":true,\"mode\":\"device\",\"cpu_only\":false,\"route_count\":"<<cfg::ROUTE_COUNT<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"real_shapes\":"<<(real?"true":"false")<<",\"stress_rows\":0,\"candidates\":[\"exp-diet\",\"exp-act-epilogue\",\"down-diet\"],\"device_peak_bytes\":"<<d.peak<<"}\n"<<std::flush;
 return 0;
}
#endif
int main(int argc,char**argv){try{
 if(argc==2&&std::string(argv[1])=="--help"){usage();return 0;}
 Args a=parse(argc,argv);
#ifdef OWN_RT_HOST_ONLY
 return host_main(a);
#else
 return device_main(a);
#endif
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
