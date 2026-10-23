// Packet58-onecard-diet-micro: exact instruction-diet micro of the ONE-card record gate/up kernel (packet193's harness
// shape). Production (pinned, never edited): p58ag_exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true,0,Cached=true>
// on 820-B p49bgemv rows, halfcache table binding p[19], p58::resolve over p58::Pointer slots (b.indirect=true on the
// record line). Candidate (p58ag_diet.hpp): p58-diet (p58ag_diet::GateUp).
// Device mode: byte identity (candidate vs production on the device, and both vs the host-twin fixtures) on all 384
// real routes (indirect slots, as the record line runs), the warm route (indirect and direct), packet162b's real rows
// re-laid out into the 820-B layout, the NaN/invalid-route fixtures, the non-finite-half bank and permuted slot tables
// BEFORE any timing; then cold (384 routes + 512 MiB scrub) and warm strata with production and candidate interleaved
// in both orders (pass 0 = A/B, pass 1 = B/A), then a fresh production-only control pass (cold + warm). NaN-only
// strata (fixture f2, exceptional) are compared by is-NaN per word (exactness_claim=false, nan_claim=true): a word
// may differ only if NaN on both sides and no status/error byte may differ. Host mode (OWN_RT_HOST_ONLY twins): the
// same comparisons on CPU, the fixture files and the random-block stress proof (--stress N rows). CPU rows are never
// speed evidence.
#include "p58ag_expert.hpp"
#include "p58ag_diet.hpp"
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
constexpr unsigned KG=2560,RG=640,N=10,E=512;
constexpr size_t RB=p49bgemv::layout(iq3::Type::IQ2_S,KG).row_bytes;      // 820 (one-card p49bgemv layout)
static_assert(RB==820);
constexpr size_t EXPERT_BYTES=size_t(RG)*RB;                                // 524,800 (p58::resolve expert span)
constexpr size_t GATE_ROWS=size_t(E)*RG,GATE_BANK=GATE_ROWS*RB;             // 327,680 rows / 268,697,600 B per stream
constexpr size_t OUT_G=2*RG*N*2+2*N*4+4;                                    // 25,684 B (y|py|status|peer_status|error)
constexpr size_t SCRUB_WORDS=size_t(128)*1024*1024;                         // 512 MiB (packet100 identity)
constexpr size_t REAL_ROWS=2*RG*N,REAL_RAW=820;                             // packet162b shape: 12,800 raw GGUF rows (82 B x 10 blocks)
constexpr size_t EXC_ROWS=2*RG*N,EXC_BANK=EXC_ROWS*RB;                      // non-finite-half bank: 10 experts x 2 streams (10,496,000 B)
constexpr size_t TABLE=65536;                                               // halfcache entries (p[19]), 262,144 B
constexpr unsigned ROUTE_COUNT=384,CHUNK=256,WARMUPS=5,FIXTURES=3,SLOT_ROUTES=8,SLOT_TABLES=2;
}
using Routes=std::array<iq3::Route,cfg::N>;
using Experts=std::array<uint32_t,cfg::N>;
struct Lcg{uint32_t s;uint32_t next(){s=s*1664525u+1013904223u;return s;}};
// Gate/up synthetic generator (seed 192, packet192/193's raw bytes): raw 820-B GGUF IQ2_S rows, every block scale 0x2400,
// re-laid out through the one-card line's own layout tool p49bgemv::repack_row (820-B p49 layout).
struct GateGen{Lcg g{192};size_t next_row=0;static constexpr size_t TOTAL=2*cfg::GATE_ROWS;
 bool done()const{return next_row>=TOTAL;}
 std::vector<uint8_t> chunk(){std::vector<uint8_t>raw(cfg::CHUNK*cfg::REAL_RAW),out(cfg::CHUNK*cfg::RB);for(auto&v:raw)v=g.next()>>24;
  for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}
  for(unsigned row=0;row<cfg::CHUNK;++row)p49bgemv::repack_row(iq3::Type::IQ2_S,cfg::KG,raw.data()+row*cfg::REAL_RAW,out.data()+row*cfg::RB);
  next_row+=cfg::CHUNK;return out;}
};
// Non-finite-half bank (seed 193): random codes/high/sub-scales (finite scales for the repack admission), then every block
// half overwritten from {finite half, +-Inf, NaN payloads (quiet and signalling patterns), +-0, half subnormals, max finite}
// so the hoisted `exceptional` test, signed zeros and Inf/NaN propagation through the TABLE decode are all exercised.
static uint16_t special_half(Lcg&g){static const uint16_t table[]={0x7c00,0xfc00,0x7e00,0xfe01,0x7c01,0xfdff,0x0000,0x8000,0x0001,0x8001,0x03ff,0x83ff,0x7bff,0xfbff,0x0400,0x8400};
 unsigned c=g.next()%16;if(c<8)return uint16_t(0x0400+g.next()%0x7800)|uint16_t((g.next()&1)<<15);return table[g.next()%16];}
static std::vector<uint8_t> gate_exc_bank(){Lcg g{193};std::vector<uint8_t>raw(cfg::EXC_ROWS*cfg::REAL_RAW),out(cfg::EXC_BANK);for(auto&v:raw)v=g.next()>>24;
 for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}
 const auto l=p49bgemv::layout(iq3::Type::IQ2_S,cfg::KG);
 for(size_t row=0;row<cfg::EXC_ROWS;++row){p49bgemv::repack_row(iq3::Type::IQ2_S,cfg::KG,raw.data()+row*cfg::REAL_RAW,out.data()+row*cfg::RB);
  for(unsigned b=0;b<cfg::KG/256;++b){uint16_t h=special_half(g);std::memcpy(out.data()+row*cfg::RB+l.halves+2*b,&h,2);}}
 return out;}
static std::vector<uint16_t> gate_input(uint32_t seed){std::vector<uint16_t>x(cfg::KG);Lcg g{seed};for(auto&v:x)v=iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);return x;}
// packet162b's fixture inputs: seed 162+fixture; fixture 2 plants specials (+-0, subnormals, +-Inf, NaN payloads) at i%17==0.
static std::vector<uint16_t> fixture_input(unsigned fixture,size_t n){std::vector<uint16_t>x(n);uint32_t s=162+fixture;static const uint16_t special[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2};
 for(size_t i=0;i<n;++i){s=s*1664525+1013904223;x[i]=fixture==2&&i%17==0?special[(i/17)%8]:iq3::bf16_bits(float(int(s%255)-127)/128.f);}return x;}
static Routes fixture_routes(bool invalid,unsigned rows){Routes a;for(unsigned i=0;i<cfg::N;++i)a[i]={i,0,rows};if(invalid){a[3]={512,0,rows};a[7]={7,3,rows-3};}return a;}
// The engine's exact-half-decode-table: table[i] = iq3::half(i) for every 16-bit pattern (main.cpp initialize_cache).
static std::vector<float> half_table(){std::vector<float>t(cfg::TABLE);for(unsigned i=0;i<cfg::TABLE;++i)t[i]=iq3::half(uint16_t(i));return t;}
static std::vector<uint8_t> load_real(const std::string&path){
 std::ifstream f(path,std::ios::binary|std::ios::ate);require(bool(f)&&f.tellg()==std::streamoff(cfg::REAL_ROWS*cfg::REAL_RAW),"real rows extent: "+path);
 std::vector<uint8_t>raw(cfg::REAL_ROWS*cfg::REAL_RAW);f.seekg(0);f.read((char*)raw.data(),raw.size());require(bool(f),"real rows truncated");
 std::vector<uint8_t>out(cfg::REAL_ROWS*cfg::RB);
 for(size_t row=0;row<cfg::REAL_ROWS;++row){const auto*s=raw.data()+row*cfg::REAL_RAW;for(unsigned b=0;b<10;++b)require((p49bgemv::load16(s+82*b)&0x7c00)!=0x7c00,"nonfinite real weight scale");p49bgemv::repack_row(iq3::Type::IQ2_S,cfg::KG,s,out.data()+row*cfg::RB);}
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
// Slot tables (p58::Pointer per expert): slot e -> block perm[e] of the bank. Identity = the record line's cache layout
// relation for a resident expert; reverse and a seeded shuffle exercise non-identity slot resolution. Running routes R
// over table perm equals running routes perm(R) directly (the kernels are route-agnostic): that cross-check is claimed.
static std::vector<unsigned> permutation(unsigned n,int kind){std::vector<unsigned>p(n);for(unsigned i=0;i<n;++i)p[i]=kind==1?n-1-i:i;
 if(kind==2){Lcg g{0x58d0u};for(unsigned i=n-1;i>0;--i){unsigned j=g.next()%(i+1);std::swap(p[i],p[j]);}}return p;}
static std::vector<p58::Pointer> slot_table(const uint8_t*bank,const std::vector<unsigned>&perm){std::vector<p58::Pointer>t(perm.size());for(size_t e=0;e<perm.size();++e){p58::Pointer q;q.address=uint64_t(bank+size_t(perm[e])*cfg::EXPERT_BYTES);q.generation=0x58d0ull+e;t[e]=q;}return t;}
static const char*SLOT_NAMES[]={"identity","reverse","shuffled"};
// Fixture set: every production output the device must reproduce.
struct Fixtures{std::string dir;bool out=false;
 std::vector<uint8_t> cold,warm,warm_direct,real0,real24,fx,exc,slots;
 static std::vector<uint8_t> read(const std::string&p,size_t bytes){std::ifstream f(p,std::ios::binary|std::ios::ate);require(bool(f)&&f.tellg()==std::streamoff(bytes),"fixture extent: "+p);std::vector<uint8_t>v(bytes);f.seekg(0);f.read((char*)v.data(),bytes);require(bool(f),"fixture read");return v;}
 void load(bool real){cold=read(dir+"/gateup-cold.bin",cfg::ROUTE_COUNT*cfg::OUT_G);warm=read(dir+"/gateup-warm.bin",cfg::OUT_G);warm_direct=read(dir+"/gateup-warm-direct.bin",cfg::OUT_G);fx=read(dir+"/gateup-fx.bin",6*cfg::OUT_G);exc=read(dir+"/gateup-exc.bin",cfg::OUT_G);
  slots=read(dir+"/gateup-slots.bin",cfg::SLOT_TABLES*cfg::SLOT_ROUTES*cfg::OUT_G);
  if(real){real0=read(dir+"/gateup-real-layer0.bin",cfg::OUT_G);real24=read(dir+"/gateup-real-layer24.bin",cfg::OUT_G);}}
 void write()const{auto w=[&](const char*n,const std::vector<uint8_t>&v){std::ofstream f(dir+"/"+n,std::ios::binary);f.write((const char*)v.data(),v.size());require(bool(f),"fixture write");};
  w("gateup-cold.bin",cold);w("gateup-warm.bin",warm);w("gateup-warm-direct.bin",warm_direct);w("gateup-fx.bin",fx);w("gateup-exc.bin",exc);w("gateup-slots.bin",slots);
  if(!real0.empty()){w("gateup-real-layer0.bin",real0);w("gateup-real-layer24.bin",real24);}}
};
static size_t diff_bytes(const uint8_t*a,const uint8_t*b,size_t n){size_t d=0;for(size_t i=0;i<n;++i)d+=a[i]!=b[i];return d;}
// Classify a difference: BF16 words of the y/py regions that differ with BOTH sides NaN are payload-order differences
// (the compiler's/hardware's operand order of an IEEE add/mul on two NaNs); anything else is a value difference.
struct Diff{size_t bytes=0,words=0,nan_vs_nan=0,other_bytes=0;bool payload_order_only()const{return bytes&&words==nan_vs_nan&&!other_bytes;}};
static Diff classify(const uint8_t*a,const uint8_t*b,size_t n){Diff d;d.bytes=diff_bytes(a,b,n);const size_t words_end=2*cfg::RG*cfg::N*2;
 for(size_t i=0;i+1<words_end;i+=2){uint16_t x,y;std::memcpy(&x,a+i,2);std::memcpy(&y,b+i,2);if(x!=y){++d.words;d.nan_vs_nan+=((x&0x7fff)>0x7f80)&&((y&0x7fff)>0x7f80);}}
 for(size_t i=words_end;i<n;++i)if(a[i]!=b[i])++d.other_bytes;return d;}
// NaN-only diagnostic strata: packet162b's NaN-input fixture f2 and the non-finite-half bank. There every output word is
// NaN by construction (or a finite word that must still be byte-equal), so they are compared by is-NaN per word:
// exactness_claim=false, nan_claim=true; the gate for them is `other_bytes==0 && words==nan_vs_nan` (packet193's lesson:
// the device's NaN payload order differs from the host twins'; a payload-order-only difference is never a kill).
static bool nan_stratum(const std::string&s){return s.rfind("fixture-f2",0)==0||s=="exceptional";}
static void bytes_row(const char*candidate,const std::string&stratum,int route,const char*against,Diff d,size_t total,bool cpu){
 const bool nan=nan_stratum(stratum);const bool nan_ok=d.other_bytes==0&&d.words==d.nan_vs_nan;
 std::cout<<"{\"kind\":\"bytes\",\"candidate\":\""<<candidate<<"\",\"kernel\":\"gateup\",\"stratum\":\""<<stratum<<"\",\"route\":"<<route<<",\"against\":\""<<against<<"\",\"different_bytes\":"<<d.bytes<<",\"compared_bytes\":"<<total<<",\"bytes_equal\":"<<(d.bytes?"false":"true")<<",\"different_words\":"<<d.words<<",\"nan_vs_nan_words\":"<<d.nan_vs_nan<<",\"other_bytes\":"<<d.other_bytes<<",\"payload_order_only\":"<<(d.payload_order_only()?"true":"false")<<",\"exactness_claim\":"<<(nan?"false":"true")<<",\"nan_claim\":"<<(nan?"true":"false")<<",\"nan_equal\":"<<(nan_ok?"true":"false")<<",\"cpu_only\":"<<(cpu?"true":"false")<<"}\n";}
static void sample_row(const char*candidate,const char*arm,const char*stratum,int route,unsigned pass,const char*order,unsigned rep,bool warmup,uint64_t start,uint64_t end,size_t scrub,bool cpu){
 std::cout<<"{\"kind\":\"sample\",\"candidate\":\""<<candidate<<"\",\"arm\":\""<<arm<<"\",\"kernel\":\"gateup\",\"stratum\":\""<<stratum<<"\",\"route\":"<<route<<",\"pass\":"<<pass<<",\"order\":\""<<order<<"\",\"repeat\":"<<rep<<",\"warmup\":"<<(warmup?"true":"false")<<",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<",\"event_ns\":"<<(end-start)<<",\"scrub_bytes\":"<<scrub<<",\"exact\":true,\"cpu_only\":"<<(cpu?"true":"false")<<",\"diagnostic_only\":true}\n";}
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
// ---- bindings: the production dispatch's 20 slots (p58ag_submit.cpp ids{...}): 0 w, 1 peer, 2 x, 3 y, 4 py, 5 routes,
// 6 status, 7 peer_status, 16 error, 17 active, 18 position, 19 halfcache; the rest unused by expert_checks ----
struct Bind{std::array<void*,20>p{};};
static Bind bind_gateup(const void*w,const void*peer,const void*x,uint8_t*o,const void*routes,const uint32_t*active,const uint32_t*position,const float*table){Bind b;b.p[0]=(void*)w;b.p[1]=(void*)peer;b.p[2]=(void*)x;b.p[3]=o;b.p[4]=o+cfg::RG*cfg::N*2;b.p[5]=(void*)routes;b.p[6]=o+2*cfg::RG*cfg::N*2;b.p[7]=o+2*cfg::RG*cfg::N*2+cfg::N*4;b.p[16]=o+cfg::OUT_G-4;b.p[17]=(void*)active;b.p[18]=(void*)position;b.p[19]=(void*)table;return b;}
using Prod=p58ag_exp::Kernel<iq3::Type::IQ2_S,cfg::KG,64,false,true,0,true>;using Cand=p58ag_diet::GateUp;
template<class K>static K kernel(bool indirect,unsigned experts){K k;k.indirect=indirect;k.experts=experts;return k;}
// The production dispatch's boundary validation (p39::validate, unchanged) applied to every binding the micro launches.
template<class K>static void validate(const K&k,const Bind&b){auto bound=k.bind(b.p);bound.position=static_cast<const uint32_t*>(b.p[18]);bound.capacity=128;p39::validate<iq3::Type::IQ2_S,cfg::KG,p39::Kind::expert_checks,1>(bound);require(bound.halfcache==b.p[19]&&bound.rb==cfg::RB,"halfcache binding / row stride");}
static const char*CANDIDATE="p58-diet";
#ifdef OWN_RT_HOST_ONLY
#include <omp.h>
static uint64_t now_ns(){return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
template<class K>static std::vector<uint8_t> host_run(const K&k,const void*w,const void*peer,const uint16_t*x,const Routes&r,const float*table,uint32_t active=1,uint32_t error0=0){
 std::vector<uint8_t>o(cfg::OUT_G,0xa5);std::memcpy(o.data()+cfg::OUT_G-4,&error0,4);uint32_t position=0;auto b=bind_gateup(w,peer,x,o.data(),r.data(),&active,&position,table);validate(k,b);k.run(b.p);return o;}
// Random-block stress: chain-level FP32 bit identity of the diet chains against production on random 820-B rows, with
// the table decode (production identity) and with the computed decode (halfcache=nullptr; both kernels' fallback), plus
// the table-vs-computed identity of production itself (each classified NaN-vs-NaN payload order or value). Profiles: "mixed" (non-finite halves in ~1/2 of the blocks, 3 %
// special inputs) where a mismatch is classified NaN-vs-NaN (payload order) or value; "finite" (finite halves incl.
// subnormal and max, finite inputs: the engine's admissible domain) where any mismatch is a value difference.
struct StressCount{size_t blocks=0,exceptional=0,chains=0,nan_payload=0,value=0,table_nan_payload=0,table_value=0,nocache_nan_payload=0,nocache_value=0;};
static void stress_row(const char*profile,unsigned rows,const StressCount&c){
 std::cout<<"{\"kind\":\"stress\",\"kernel\":\"gateup\",\"candidate\":\""<<CANDIDATE<<"\",\"profile\":\""<<profile<<"\",\"rows\":"<<rows<<",\"blocks\":"<<c.blocks<<",\"exceptional_blocks\":"<<c.exceptional<<",\"chains_compared\":"<<c.chains<<",\"fp32_mismatches\":"<<(c.nan_payload+c.value)<<",\"nan_vs_nan_mismatches\":"<<c.nan_payload<<",\"value_mismatches\":"<<c.value<<",\"nocache_fp32_mismatches\":"<<(c.nocache_nan_payload+c.nocache_value)<<",\"nocache_value_mismatches\":"<<c.nocache_value<<",\"table_vs_half_mismatches\":"<<(c.table_nan_payload+c.table_value)<<",\"table_vs_half_nan_vs_nan\":"<<c.table_nan_payload<<",\"table_vs_half_value_mismatches\":"<<c.table_value<<",\"passed\":"<<((c.value||c.nocache_value||c.table_value)?"false":"true")<<",\"cpu_only\":true,\"exactness_claim\":true}\n";}
static void stress(unsigned rows,const float*table){
 const auto l=p49bgemv::layout(iq3::Type::IQ2_S,cfg::KG);static const uint16_t sp[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2,0x0080,0x7f7f};
 auto nan=[](float f){return (std::bit_cast<uint32_t>(f)&0x7fffffffu)>0x7f800000u;};
 for(int profile=0;profile<2;++profile){const bool finite=profile==1;Lcg g{finite?0x1158u:0x158u};StressCount c;
  std::vector<uint8_t>row(cfg::RB);std::vector<uint16_t>x(cfg::KG);
  for(unsigned r=0;r<rows;++r){for(auto&v:row)v=uint8_t(g.next()>>24);
   for(unsigned b=0;b<cfg::KG/256;++b){uint16_t h;if(finite){unsigned k=g.next()%32;h=k<2?uint16_t(0x0001+g.next()%0x3ff):k<4?uint16_t(0x7bff):uint16_t(0x0400+g.next()%0x7800);h|=uint16_t((g.next()&1)<<15);}else h=special_half(g);
    std::memcpy(row.data()+l.halves+2*b,&h,2);c.exceptional+=(h&0x7c00)==0x7c00;}
   for(auto&v:x){unsigned k=g.next()%64;v=(!finite&&k<2)?sp[g.next()%10]:iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);}
   c.blocks+=cfg::KG/256;
   for(unsigned lane=0;lane<4;++lane){auto p=p58ag_exp::wide_chains<iq3::Type::IQ2_S,cfg::KG,8>(row.data(),x.data(),lane,table),d=p58ag_diet::diet_chains<cfg::KG,8>(row.data(),x.data(),lane,table);
    auto pn=p58ag_exp::wide_chains<iq3::Type::IQ2_S,cfg::KG,8>(row.data(),x.data(),lane,nullptr),dn=p58ag_diet::diet_chains<cfg::KG,8>(row.data(),x.data(),lane,nullptr);
    for(unsigned i=0;i<8;++i){++c.chains;
     if(std::bit_cast<uint32_t>(p[i])!=std::bit_cast<uint32_t>(d[i])){if(nan(p[i])&&nan(d[i]))++c.nan_payload;else ++c.value;}
     if(std::bit_cast<uint32_t>(pn[i])!=std::bit_cast<uint32_t>(dn[i])){if(nan(pn[i])&&nan(dn[i]))++c.nocache_nan_payload;else ++c.nocache_value;}
     if(std::bit_cast<uint32_t>(p[i])!=std::bit_cast<uint32_t>(pn[i])){if(nan(p[i])&&nan(pn[i]))++c.table_nan_payload;else ++c.table_value;}}}
  }
  stress_row(finite?"finite":"mixed",rows,c);
 }
}
static int host_main(const Args&a){
 std::ifstream rf(a.routes);std::stringstream ss;ss<<rf.rdbuf();auto experts=parse_routes(ss.str());
 std::cout<<"{\"kind\":\"start\",\"mode\":\"host\",\"routes\":"<<experts.size()<<",\"threads\":"<<omp_get_max_threads()<<",\"candidates\":[\""<<CANDIDATE<<"\"],\"cpu_only\":true}\n"<<std::flush;
 auto table=half_table();for(unsigned i=0;i<cfg::TABLE;++i)require(std::bit_cast<uint32_t>(table[i])==std::bit_cast<uint32_t>(iq3::half(uint16_t(i))),"table identity");
 std::vector<uint8_t>gate(cfg::GATE_BANK),up(cfg::GATE_BANK);
 {GateGen g;size_t row=0;while(!g.done()){auto c=g.chunk();size_t off=row*cfg::RB;if(off<cfg::GATE_BANK)std::memcpy(gate.data()+off,c.data(),c.size());else std::memcpy(up.data()+off-cfg::GATE_BANK,c.data(),c.size());row+=cfg::CHUNK;}}
 auto gexc=gate_exc_bank();auto xg=gate_input(192),xr=gate_input(162);std::vector<uint8_t>real0,real24;bool real=!a.real.empty();if(real){real0=load_real(a.real+"/layer0.bin");real24=load_real(a.real+"/layer24.bin");}
 std::vector<std::vector<p58::Pointer>> gslots,uslots;for(int kind=0;kind<3;++kind){auto perm=permutation(cfg::E,kind);gslots.push_back(slot_table(gate.data(),perm));uslots.push_back(slot_table(up.data(),perm));}
 auto rslots=[&](const std::vector<uint8_t>&bank){auto perm=permutation(cfg::N,0);return std::pair{slot_table(bank.data(),perm),slot_table(bank.data()+cfg::RG*cfg::N*cfg::RB,perm)};};
 Prod PI=kernel<Prod>(true,cfg::E),PD=kernel<Prod>(false,cfg::E),P10=kernel<Prod>(true,cfg::N);Cand CI=kernel<Cand>(true,cfg::E),CD=kernel<Cand>(false,cfg::E),C10=kernel<Cand>(true,cfg::N);
 Fixtures fx;fx.dir=a.fixtures_out.empty()?a.fixtures:a.fixtures_out;fx.out=!a.fixtures_out.empty();
 if(!fx.out)fx.load(real);else{fx.cold.resize(cfg::ROUTE_COUNT*cfg::OUT_G);fx.fx.resize(6*cfg::OUT_G);fx.slots.resize(cfg::SLOT_TABLES*cfg::SLOT_ROUTES*cfg::OUT_G);}
 auto compare=[&](const std::string&stratum,int route,const std::vector<uint8_t>&prod,const std::vector<uint8_t>&cd,const uint8_t*fixture){
  bytes_row("production",stratum,route,"fixture",fx.out?Diff{}:classify(prod.data(),fixture,cfg::OUT_G),cfg::OUT_G,true);
  bytes_row(CANDIDATE,stratum,route,"production",classify(cd.data(),prod.data(),cfg::OUT_G),cfg::OUT_G,true);
  bytes_row(CANDIDATE,stratum,route,"fixture",fx.out?classify(cd.data(),prod.data(),cfg::OUT_G):classify(cd.data(),fixture,cfg::OUT_G),cfg::OUT_G,true);};
 // cold stratum on CPU: one launch per route per arm, indirect identity slots (the record line's path); parallel across routes
 struct Cold{std::vector<uint8_t>gp,gd;uint64_t gns=0;};std::vector<Cold>cold(cfg::ROUTE_COUNT);
 #pragma omp parallel for schedule(dynamic)
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){auto rg=routes_of(experts[r],cfg::RG);auto&c=cold[r];
  uint64_t t0=now_ns();c.gp=host_run(PI,gslots[0].data(),uslots[0].data(),xg.data(),rg,table.data());uint64_t t1=now_ns();c.gd=host_run(CI,gslots[0].data(),uslots[0].data(),xg.data(),rg,table.data());c.gns=t1-t0;
  if(fx.out)std::memcpy(fx.cold.data()+size_t(r)*cfg::OUT_G,c.gp.data(),cfg::OUT_G);}
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r)compare("cold",int(r),cold[r].gp,cold[r].gd,fx.cold.data()+size_t(r)*cfg::OUT_G);
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r)sample_row("production","production","cold",int(r),0,"AB",0,false,0,cold[r].gns,0,true);
 // warm (route 0 experts): indirect and direct; the direct result must equal the indirect one (claimed harness/kernel cross-check)
 auto rg0=routes_of(experts[0],cfg::RG);
 {auto gp=host_run(PI,gslots[0].data(),uslots[0].data(),xg.data(),rg0,table.data()),gd=host_run(CI,gslots[0].data(),uslots[0].data(),xg.data(),rg0,table.data());if(fx.out)fx.warm=gp;compare("warm",-1,gp,gd,fx.warm.data());
  auto dp=host_run(PD,gate.data(),up.data(),xg.data(),rg0,table.data()),dd=host_run(CD,gate.data(),up.data(),xg.data(),rg0,table.data());if(fx.out)fx.warm_direct=dp;compare("warm-direct",-1,dp,dd,fx.warm_direct.data());
  bytes_row("production","warm-direct",-1,"indirect",classify(dp.data(),gp.data(),cfg::OUT_G),cfg::OUT_G,true);}
 // permuted slot tables on the first SLOT_ROUTES routes: indirect(perm, R) vs direct(perm(R)) and candidate vs production
 for(unsigned t=1;t<=cfg::SLOT_TABLES;++t){auto perm=permutation(cfg::E,int(t));std::string name=std::string("slots-")+SLOT_NAMES[t];
  for(unsigned r=0;r<cfg::SLOT_ROUTES;++r){auto rr=routes_of(experts[r],cfg::RG);Experts mapped;for(unsigned i=0;i<cfg::N;++i)mapped[i]=perm[experts[r][i]];auto rm=routes_of(mapped,cfg::RG);
   auto gp=host_run(PI,gslots[t].data(),uslots[t].data(),xg.data(),rr,table.data()),gd=host_run(CI,gslots[t].data(),uslots[t].data(),xg.data(),rr,table.data()),dp=host_run(PD,gate.data(),up.data(),xg.data(),rm,table.data());
   size_t slot=((t-1)*cfg::SLOT_ROUTES+r)*cfg::OUT_G;if(fx.out)std::memcpy(fx.slots.data()+slot,gp.data(),cfg::OUT_G);compare(name,int(r),gp,gd,fx.slots.data()+slot);
   bytes_row("production",name,int(r),"direct-permuted",classify(gp.data(),dp.data(),cfg::OUT_G),cfg::OUT_G,true);}}
 Routes rr=fixture_routes(false,cfg::RG);
 if(real){for(int which=0;which<2;++which){const auto&bank=which?real24:real0;auto [sw,sp]=rslots(bank);
   auto gp=host_run(P10,sw.data(),sp.data(),xr.data(),rr,table.data()),gd=host_run(C10,sw.data(),sp.data(),xr.data(),rr,table.data());
   if(fx.out)(which?fx.real24:fx.real0)=gp;compare(which?"warm-real-layer24":"warm-real-layer0",-1,gp,gd,(which?fx.real24:fx.real0).data());}}
 for(unsigned f=0;f<cfg::FIXTURES;++f)for(unsigned bad=0;bad<2;++bad){unsigned slot=f*2+bad;std::string name="fixture-f"+std::to_string(f)+(bad?"-invalid":"-valid");
  auto xf=fixture_input(f,cfg::KG);auto rf=fixture_routes(bad,cfg::RG);
  auto gp=host_run(PI,gslots[0].data(),uslots[0].data(),xf.data(),rf,table.data()),gd=host_run(CI,gslots[0].data(),uslots[0].data(),xf.data(),rf,table.data());
  if(fx.out)std::memcpy(fx.fx.data()+slot*cfg::OUT_G,gp.data(),cfg::OUT_G);compare(name,-1,gp,gd,fx.fx.data()+slot*cfg::OUT_G);}
 {auto xf=fixture_input(2,cfg::KG);auto [sw,sp]=rslots(gexc);
  auto gp=host_run(P10,sw.data(),sp.data(),xf.data(),rr,table.data()),gd=host_run(C10,sw.data(),sp.data(),xf.data(),rr,table.data());if(fx.out)fx.exc=gp;compare("exceptional",-1,gp,gd,fx.exc.data());}
 if(a.stress)stress(a.stress,table.data());
 // warm dry run of the timing loop (sequential, few repeats; CPU time only, never speed evidence)
 for(unsigned pass=0;pass<a.passes;++pass){const char*order=pass?"BA":"AB";
  for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_run(PI,gslots[0].data(),uslots[0].data(),xg.data(),rg0,table.data());uint64_t t1=now_ns();host_run(CI,gslots[0].data(),uslots[0].data(),xg.data(),rg0,table.data());uint64_t t2=now_ns();
   sample_row(CANDIDATE,"production","warm",-1,pass,order,rep,false,t0,t1,0,true);sample_row(CANDIDATE,"candidate","warm",-1,pass,order,rep,false,t1,t2,0,true);}}
 if(fx.out)fx.write();
 std::cout<<"{\"kind\":\"summary\",\"schema\":\"packet58dm.diet.v1\",\"passed\":true,\"drained\":true,\"diagnostic_only\":true,\"mode\":\"host\",\"cpu_only\":true,\"route_count\":"<<cfg::ROUTE_COUNT<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"real_shapes\":"<<(real?"true":"false")<<",\"fixtures_written\":"<<(fx.out?"true":"false")<<",\"stress_rows\":"<<a.stress<<",\"candidates\":[\""<<CANDIDATE<<"\"]}\n"<<std::flush;
 return 0;
}
#else
// ---- device mode ----
struct Dev{sycl::queue q;size_t live=0,peak=0;std::vector<std::pair<void*,size_t>>held;
 Dev():q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}}){}
 void*alloc(size_t n){void*p=sycl::malloc_device(n,q);if(!p)throw std::bad_alloc();held.push_back({p,n});live+=n;peak=std::max(peak,live);return p;}
 ~Dev(){try{q.wait_and_throw();}catch(...){}for(auto&h:held)sycl::free(h.first,q);}
};
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
static void allocation_row(const Dev&d,const char*phase){std::cout<<"{\"kind\":\"allocation\",\"phase\":\""<<phase<<"\",\"device_live_bytes\":"<<d.live<<",\"device_peak_bytes\":"<<d.peak<<"}\n"<<std::flush;}
struct Ev{uint64_t s,t;};
static Ev prof(sycl::event e){e.wait_and_throw();return {e.get_profiling_info<sycl::info::event_profiling::command_start>(),e.get_profiling_info<sycl::info::event_profiling::command_end>()};}
template<class LaunchA,class LaunchB>static void interleaved(Dev&d,uint32_t*scrub,const char*candidate,const char*stratum,int route,unsigned pass,unsigned repeats,bool cold,LaunchA production,LaunchB cand,bool control=false){
 const char*order=control?"P":(pass?"BA":"AB");unsigned warm=cold?0:cfg::WARMUPS;
 for(unsigned rep=0;rep<warm+repeats;++rep){guard();
  for(unsigned which=0;which<(control?1u:2u);++which){bool prod=control||((which==0)==(pass==0));
   if(cold)d.q.parallel_for(sycl::range<1>(cfg::SCRUB_WORDS),[=](sycl::id<1>id){scrub[id]=uint32_t(id[0]);}).wait_and_throw();
   Ev t=prod?production():cand();
   sample_row(candidate,prod?"production":"candidate",stratum,route,pass,order,rep<warm?rep:rep-warm,rep<warm,t.s,t.t,cold?cfg::SCRUB_WORDS*4:0,false);}}
 std::cout<<std::flush;
}
static int device_main(const Args&a){
 std::ifstream rf(a.routes);std::stringstream ss;ss<<rf.rdbuf();auto experts=parse_routes(ss.str());
 const char*probe=std::getenv("ENTRY_PREPARE_OUTPUT");
 if(probe){ // CPU preparation path: parse, bound, exercise every generator on one chunk; no device API.
  GateGen g;auto gc=g.chunk();require(gc.size()==cfg::CHUNK*cfg::RB,"generator chunk extent");
  {Lcg s{193};unsigned exc=0;for(unsigned i=0;i<256;++i)exc+=(special_half(s)&0x7c00)==0x7c00;require(exc>0,"exceptional halves present");}
  auto t=half_table();require(std::bit_cast<uint32_t>(t[0x3c00])==0x3f800000u&&std::bit_cast<uint32_t>(t[0x7c00])==0x7f800000u,"table decode");
  size_t device_bytes=cfg::SCRUB_WORDS*4+2*cfg::GATE_BANK+2*cfg::REAL_ROWS*cfg::RB+cfg::EXC_BANK+cfg::TABLE*4+3*cfg::E*sizeof(p58::Pointer)+3*2*cfg::N*sizeof(p58::Pointer)+(2+cfg::FIXTURES)*cfg::KG*2+cfg::OUT_G+sizeof(Routes)+8;
  std::ofstream(std::string(probe)+"/prepare.json")<<"{\"passed\":true,\"device_executed\":false,\"routes\":"<<experts.size()<<",\"planned_device_peak_bytes\":"<<device_bytes<<",\"gate_bank_bytes\":"<<cfg::GATE_BANK<<",\"exceptional_bank_bytes\":"<<cfg::EXC_BANK<<",\"halfcache_bytes\":"<<cfg::TABLE*4<<",\"scrub_bytes\":"<<cfg::SCRUB_WORDS*4<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"candidates\":1}\n";
  std::cout<<"PASS CPU preparation before first device call; routes="<<experts.size()<<" planned_device_peak_bytes="<<device_bytes<<"\n";return 0;}
 Fixtures fx;fx.dir=a.fixtures;fx.load(!a.real.empty());
 std::vector<uint8_t>real0,real24;bool real=!a.real.empty();if(real){real0=load_real(a.real+"/layer0.bin");real24=load_real(a.real+"/layer24.bin");}
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 Dev d;std::cout<<"{\"kind\":\"start\",\"mode\":\"device\",\"device\":\""<<d.q.get_device().get_info<sycl::info::device::name>()<<"\",\"routes\":"<<experts.size()<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"warmups\":"<<cfg::WARMUPS<<",\"candidates\":[\""<<CANDIDATE<<"\"]}\n"<<std::flush;
 auto*scrub=(uint32_t*)d.alloc(cfg::SCRUB_WORDS*4);
 auto upload=[&](uint8_t*dst,auto&gen,size_t total){std::vector<uint8_t>stage;stage.reserve(16*cfg::CHUNK*cfg::RB);size_t off=0;while(!gen.done()){guard();stage.clear();for(unsigned i=0;i<16&&!gen.done();++i){auto c=gen.chunk();stage.insert(stage.end(),c.begin(),c.end());}d.q.memcpy(dst+off,stage.data(),stage.size()).wait_and_throw();off+=stage.size();}require(off==total,"bank upload extent");};
 auto fetch=[&](const uint8_t*o,size_t n){std::vector<uint8_t>v(n);d.q.memcpy(v.data(),o,n).wait_and_throw();return v;};
 auto put=[&](const void*h,size_t n){auto*p=(uint8_t*)d.alloc(n);d.q.memcpy(p,h,n).wait_and_throw();return p;};
 uint32_t one=1,zero=0;
 auto*gate=(uint8_t*)d.alloc(2*cfg::GATE_BANK);auto*up=gate+cfg::GATE_BANK;{GateGen g;upload(gate,g,2*cfg::GATE_BANK);}
 auto ht=half_table();auto*table=(const float*)put(ht.data(),ht.size()*4);
 std::vector<const p58::Pointer*>gslots,uslots;for(int kind=0;kind<3;++kind){auto perm=permutation(cfg::E,kind);auto g=slot_table(gate,perm),u=slot_table(up,perm);gslots.push_back((const p58::Pointer*)put(g.data(),g.size()*16));uslots.push_back((const p58::Pointer*)put(u.data(),u.size()*16));}
 auto xg=gate_input(192),xr=gate_input(162);auto*x=(const uint16_t*)put(xg.data(),cfg::KG*2);auto*xdr=(const uint16_t*)put(xr.data(),cfg::KG*2);
 const uint16_t*xf[cfg::FIXTURES];for(unsigned f=0;f<cfg::FIXTURES;++f){auto h=fixture_input(f,cfg::KG);xf[f]=(const uint16_t*)put(h.data(),cfg::KG*2);}
 auto*exc=(uint8_t*)d.alloc(cfg::EXC_BANK);{auto h=gate_exc_bank();d.q.memcpy(exc,h.data(),h.size()).wait_and_throw();}
 uint8_t*r0=nullptr,*r24=nullptr;if(real){r0=put(real0.data(),real0.size());r24=put(real24.data(),real24.size());}
 auto rslots=[&](const uint8_t*bank){auto perm=permutation(cfg::N,0);auto w=slot_table(bank,perm),p=slot_table(bank+cfg::RG*cfg::N*cfg::RB,perm);return std::pair{(const p58::Pointer*)put(w.data(),w.size()*16),(const p58::Pointer*)put(p.data(),p.size()*16)};};
 auto [es_w,es_p]=rslots(exc);std::pair<const p58::Pointer*,const p58::Pointer*> r0s{},r24s{};if(real){r0s=rslots(r0);r24s=rslots(r24);}
 auto*routes=(iq3::Route*)d.alloc(sizeof(Routes));auto*o=(uint8_t*)d.alloc(cfg::OUT_G);auto*active=(uint32_t*)put(&one,4);auto*position=(uint32_t*)put(&zero,4);
 allocation_row(d,"gateup");
 Prod PI=kernel<Prod>(true,cfg::E),PD=kernel<Prod>(false,cfg::E),P10=kernel<Prod>(true,cfg::N);Cand CI=kernel<Cand>(true,cfg::E),CD=kernel<Cand>(false,cfg::E),C10=kernel<Cand>(true,cfg::N);
 auto set_routes=[&](const Routes&r){d.q.memcpy(routes,r.data(),sizeof(Routes)).wait_and_throw();};
 auto clear=[&](uint32_t error0=0){d.q.memset(o,0xa5,cfg::OUT_G);d.q.memcpy(o+cfg::OUT_G-4,&error0,4).wait_and_throw();};
 auto launch=[&](auto&k,const void*w,const void*peer,const uint16_t*xx){auto b=bind_gateup(w,peer,xx,o,routes,active,position,table);validate(k,b);return k.submit(d.q,b.p,{});};
 auto run=[&](auto&k,const void*w,const void*peer,const uint16_t*xx){clear();launch(k,w,peer,xx).wait_and_throw();return fetch(o,cfg::OUT_G);};
 auto exact=[&](auto&P,auto&C,const std::string&stratum,int route,const void*w,const void*peer,const uint16_t*xx,const uint8_t*fixture){
  auto prod=run(P,w,peer,xx);bytes_row("production",stratum,route,"fixture",classify(prod.data(),fixture,cfg::OUT_G),cfg::OUT_G,false);
  auto cd=run(C,w,peer,xx);bytes_row(CANDIDATE,stratum,route,"production",classify(cd.data(),prod.data(),cfg::OUT_G),cfg::OUT_G,false);bytes_row(CANDIDATE,stratum,route,"fixture",classify(cd.data(),fixture,cfg::OUT_G),cfg::OUT_G,false);return prod;};
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){guard();set_routes(routes_of(experts[r],cfg::RG));exact(PI,CI,"cold",int(r),gslots[0],uslots[0],x,fx.cold.data()+size_t(r)*cfg::OUT_G);}
 auto rg0=routes_of(experts[0],cfg::RG);set_routes(rg0);auto warm_ind=exact(PI,CI,"warm",-1,gslots[0],uslots[0],x,fx.warm.data());
 {auto dp=exact(PD,CD,"warm-direct",-1,gate,up,x,fx.warm_direct.data());bytes_row("production","warm-direct",-1,"indirect",classify(dp.data(),warm_ind.data(),cfg::OUT_G),cfg::OUT_G,false);}
 for(unsigned t=1;t<=cfg::SLOT_TABLES;++t){auto perm=permutation(cfg::E,int(t));std::string name=std::string("slots-")+SLOT_NAMES[t];
  for(unsigned r=0;r<cfg::SLOT_ROUTES;++r){guard();Experts mapped;for(unsigned i=0;i<cfg::N;++i)mapped[i]=perm[experts[r][i]];
   set_routes(routes_of(experts[r],cfg::RG));auto gp=exact(PI,CI,name,int(r),gslots[t],uslots[t],x,fx.slots.data()+((t-1)*cfg::SLOT_ROUTES+r)*cfg::OUT_G);
   set_routes(routes_of(mapped,cfg::RG));auto dp=run(PD,gate,up,x);bytes_row("production",name,int(r),"direct-permuted",classify(gp.data(),dp.data(),cfg::OUT_G),cfg::OUT_G,false);}}
 Routes rr=fixture_routes(false,cfg::RG);
 if(real){set_routes(rr);exact(P10,C10,"warm-real-layer0",-1,r0s.first,r0s.second,xdr,fx.real0.data());exact(P10,C10,"warm-real-layer24",-1,r24s.first,r24s.second,xdr,fx.real24.data());}
 for(unsigned f=0;f<cfg::FIXTURES;++f)for(unsigned bad=0;bad<2;++bad){set_routes(fixture_routes(bad,cfg::RG));exact(PI,CI,"fixture-f"+std::to_string(f)+(bad?"-invalid":"-valid"),-1,gslots[0],uslots[0],xf[f],fx.fx.data()+(f*2+bad)*cfg::OUT_G);}
 set_routes(rr);exact(P10,C10,"exceptional",-1,es_w,es_p,xf[2],fx.exc.data());
 std::cout<<std::flush;clear();
 // timing: production vs candidate, interleaved, both orders (indirect slots = the record line's path), then the control pass
 auto prod_ind=[&]{return prof(launch(PI,gslots[0],uslots[0],x));};auto cand_ind=[&]{return prof(launch(CI,gslots[0],uslots[0],x));};
 auto prod_dir=[&]{return prof(launch(PD,gate,up,x));};auto cand_dir=[&]{return prof(launch(CD,gate,up,x));};
 for(unsigned pass=0;pass<a.passes;++pass){
  for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){set_routes(routes_of(experts[r],cfg::RG));interleaved(d,scrub,CANDIDATE,"cold",int(r),pass,a.cold,true,prod_ind,cand_ind);}
  set_routes(rg0);interleaved(d,scrub,CANDIDATE,"warm",-1,pass,a.warm,false,prod_ind,cand_ind);
  interleaved(d,scrub,CANDIDATE,"warm-direct",-1,pass,a.warm,false,prod_dir,cand_dir);
  if(real){set_routes(rr);
   interleaved(d,scrub,CANDIDATE,"warm-real-layer0",-1,pass,a.warm,false,[&]{return prof(launch(P10,r0s.first,r0s.second,xdr));},[&]{return prof(launch(C10,r0s.first,r0s.second,xdr));});
   interleaved(d,scrub,CANDIDATE,"warm-real-layer24",-1,pass,a.warm,false,[&]{return prof(launch(P10,r24s.first,r24s.second,xdr));},[&]{return prof(launch(C10,r24s.first,r24s.second,xdr));});}}
 // fresh production-only control (kill rule: interleaved production medians must agree with this within 10 %)
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){set_routes(routes_of(experts[r],cfg::RG));interleaved(d,scrub,"control","cold",int(r),0,a.cold,true,prod_ind,cand_ind,true);}
 set_routes(rg0);interleaved(d,scrub,"control","warm",-1,0,a.warm,false,prod_ind,cand_ind,true);
 d.q.wait_and_throw();guard();
 std::cout<<"{\"kind\":\"summary\",\"schema\":\"packet58dm.diet.v1\",\"passed\":true,\"drained\":true,\"diagnostic_only\":true,\"mode\":\"device\",\"cpu_only\":false,\"route_count\":"<<cfg::ROUTE_COUNT<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"real_shapes\":"<<(real?"true":"false")<<",\"stress_rows\":0,\"candidates\":[\""<<CANDIDATE<<"\"],\"device_peak_bytes\":"<<d.peak<<"}\n"<<std::flush;
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
