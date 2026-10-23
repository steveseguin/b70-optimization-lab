// Packet192: issue-floor decomposition of the two record expert kernels. MEASUREMENT ONLY.
// Kernels under test (record k3x selection "exp-halfcache+down-tile16", packet189 v5 -> packet190):
//   gate/up: p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>  (640 rows x K2560 x 10 experts, two streams)
//   down:    p100::Kernel<2>                                             (2560 rows x K640 x 10 experts, tile16 layout)
// Strata per kernel: cold (packet100b's 384 real routes, 512 MiB device scrub before every launch),
// warm (one real route's ten experts repeated, no scrub; plus packet162b's real layer0/layer24 rows for
// gate/up), no-load (p192noload: every row aliased into one 16-row slab; NOT exact, outputs discarded).
// Device mode runs the real kernels; host mode runs their OWN_RT_HOST_ONLY twins to produce/verify the
// exactness fixtures and to dry-run the stratum loop on CPU. CPU rows are never device speed evidence.
#include "p90_expert.hpp"
#include "p100_down.hpp"
#include "p192_noload.hpp"
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
constexpr size_t OUT_G=2*RG*N*2+2*N*4+4,OUT_D=size_t(RD)*N*2+N*4+4;       // 25,684 / 51,244 B
constexpr size_t SCRUB_WORDS=size_t(128)*1024*1024;                        // 512 MiB (packet100 identity)
constexpr size_t REAL_ROWS=2*RG*N,REAL_RAW=820;                            // packet162b shape: 12,800 raw rows
constexpr unsigned ROUTE_COUNT=384,CHUNK=256,WARMUPS=5;
constexpr unsigned ALIAS_ROWS=p192noload::alias_rows;
}
using Routes=std::array<iq3::Route,cfg::N>;
using Experts=std::array<uint32_t,cfg::N>;
struct Lcg{uint32_t s;uint32_t next(){s=s*1664525u+1013904223u;return s;}};
// Packet100's generator (seed 100, same LCG order: inputs first, then 256-row chunks): the down bank is
// byte-identical to packet100b's micro bank, so its real down-tile16 cold datum is a cross-check.
struct DownGen{Lcg g{100};std::vector<uint16_t>hx;size_t next_row=0;
 DownGen(){hx.resize(size_t(cfg::KD)*cfg::N);for(auto&v:hx)v=iq3::bf16_bits(float(int(g.next()%63)-31)/32.f);}
 bool done()const{return next_row>=cfg::DOWN_ROWS;}
 std::vector<uint8_t> chunk(){std::vector<uint8_t>raw(cfg::CHUNK*cfg::RBD),packed(raw.size());for(auto&v:raw)v=g.next()>>24;
  for(unsigned row=0;row<cfg::CHUNK;++row){for(unsigned block=0;block<20;++block){uint16_t h=0x2400+g.next()%1024;std::memcpy(raw.data()+row*cfg::RBD+block*18,&h,2);}
   p49bgemv::repack_row(iq3::Type::IQ4_NL,cfg::KD,raw.data()+row*cfg::RBD,packed.data()+row*cfg::RBD);}
  next_row+=cfg::CHUNK;return p100::transpose(packed.data(),cfg::CHUNK);}
};
// Gate/up synthetic generator (seed 192): raw 820-B IQ2_S rows, every block scale 0x2400 (finite, as
// packet162's synthetic rows), E1 repack to 840-B rows. Gate bank first, then the up bank.
struct GateGen{Lcg g{192};size_t next_row=0;static constexpr size_t TOTAL=2*cfg::GATE_ROWS;
 bool done()const{return next_row>=TOTAL;}
 std::vector<uint8_t> chunk(){std::vector<uint8_t>raw(cfg::CHUNK*cfg::REAL_RAW),out(cfg::CHUNK*cfg::RBG);for(auto&v:raw)v=g.next()>>24;
  for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}
  for(unsigned row=0;row<cfg::CHUNK;++row)p90::expert_repack(cfg::KG,raw.data()+row*cfg::REAL_RAW,out.data()+row*cfg::RBG);
  next_row+=cfg::CHUNK;return out;}
};
static std::vector<uint16_t> gate_input(uint32_t seed){std::vector<uint16_t>x(cfg::KG);Lcg g{seed};for(auto&v:x)v=iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);return x;}
static std::vector<uint8_t> load_real(const std::string&path){ // packet162b layer{0,24}.bin: 12,800 raw rows -> 840-B E1 rows
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
struct Fixtures{std::string dir;bool out=false;std::vector<uint8_t> gate_cold,down_cold,gate_warm,down_warm,gate_real0,gate_real24;
 static std::vector<uint8_t> read(const std::string&p,size_t bytes){std::ifstream f(p,std::ios::binary|std::ios::ate);require(bool(f)&&f.tellg()==std::streamoff(bytes),"fixture extent: "+p);std::vector<uint8_t>v(bytes);f.seekg(0);f.read((char*)v.data(),bytes);require(bool(f),"fixture read");return v;}
 void load(bool real){gate_cold=read(dir+"/gateup-cold.bin",cfg::ROUTE_COUNT*cfg::OUT_G);down_cold=read(dir+"/down-cold.bin",cfg::ROUTE_COUNT*cfg::OUT_D);gate_warm=read(dir+"/gateup-warm.bin",cfg::OUT_G);down_warm=read(dir+"/down-warm.bin",cfg::OUT_D);
  if(real){gate_real0=read(dir+"/gateup-real-layer0.bin",cfg::OUT_G);gate_real24=read(dir+"/gateup-real-layer24.bin",cfg::OUT_G);}}
 void write()const{auto w=[&](const char*n,const std::vector<uint8_t>&v){std::ofstream f(dir+"/"+n,std::ios::binary);f.write((const char*)v.data(),v.size());require(bool(f),"fixture write");};
  w("gateup-cold.bin",gate_cold);w("down-cold.bin",down_cold);w("gateup-warm.bin",gate_warm);w("down-warm.bin",down_warm);if(!gate_real0.empty()){w("gateup-real-layer0.bin",gate_real0);w("gateup-real-layer24.bin",gate_real24);}}
};
static size_t diff_bytes(const uint8_t*a,const uint8_t*b,size_t n){size_t d=0;for(size_t i=0;i<n;++i)d+=a[i]!=b[i];return d;}
static void bytes_row(const char*kernel,const char*stratum,int route,size_t diff,size_t total,bool exact_claim){
 std::cout<<"{\"kind\":\"bytes\",\"kernel\":\""<<kernel<<"\",\"stratum\":\""<<stratum<<"\",\"route\":"<<route<<",\"different_bytes\":"<<diff<<",\"compared_bytes\":"<<total<<",\"bytes_equal\":"<<(diff?"false":"true")<<",\"exactness_claim\":"<<(exact_claim?"true":"false")<<"}\n";}
static void sample_row(const char*kernel,const char*stratum,int route,unsigned pass,unsigned rep,bool warmup,uint64_t start,uint64_t end,size_t scrub,bool cpu){
 std::cout<<"{\"kind\":\"sample\",\"kernel\":\""<<kernel<<"\",\"stratum\":\""<<stratum<<"\",\"route\":"<<route<<",\"pass\":"<<pass<<",\"repeat\":"<<rep<<",\"warmup\":"<<(warmup?"true":"false")<<",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<",\"event_ns\":"<<(end-start)<<",\"scrub_bytes\":"<<scrub<<",\"exact\":"<<(std::string(stratum)=="noload"?"false":"true")<<",\"cpu_only\":"<<(cpu?"true":"false")<<",\"diagnostic_only\":true}\n";}
struct Args{std::string routes,real,fixtures,fixtures_out,mode="device";unsigned cold=20,warm=200,passes=2;bool admitted=false;int rank=-1;};
static void usage(){std::cout<<"usage: --rank 0 --routes ROUTES.json [--real-rows DIR] [--fixtures DIR | --fixtures-out DIR] --mode device|host --cold-repeats 20 --warm-repeats 200 --passes 2 --coordinator-admitted-device-window\n";}
static unsigned number(const std::string&v){require(!v.empty()&&v.size()<=6&&std::all_of(v.begin(),v.end(),[](char c){return c>='0'&&c<='9';}),"numeric option");return unsigned(std::stoul(v));}
static Args parse(int argc,char**argv){Args a;
 for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--coordinator-admitted-device-window"){a.admitted=true;continue;}require(i+1<argc,"missing argument: "+k);std::string v=argv[++i];
  if(k=="--rank"){require(v=="0","rank must be zero");a.rank=0;}else if(k=="--routes")a.routes=v;else if(k=="--real-rows")a.real=v;else if(k=="--fixtures")a.fixtures=v;else if(k=="--fixtures-out")a.fixtures_out=v;
  else if(k=="--mode"){require(v=="device"||v=="host","mode");a.mode=v;}else if(k=="--cold-repeats")a.cold=number(v);else if(k=="--warm-repeats")a.warm=number(v);else if(k=="--passes")a.passes=number(v);else throw std::runtime_error("unknown option: "+k);}
 require(a.rank==0&&!a.routes.empty()&&a.cold>=1&&a.warm>=1&&a.passes>=1,"invalid micro argv");
#ifdef OWN_RT_HOST_ONLY
 require(a.mode=="host","host twin runs --mode host only");require(!a.fixtures.empty()||!a.fixtures_out.empty(),"host twin needs --fixtures or --fixtures-out");
#else
 require(a.mode=="device"&&a.admitted&&!a.fixtures.empty()&&a.fixtures_out.empty(),"device mode requires coordinator admission and --fixtures");
#endif
 return a;}
// ---- host twin (OWN_RT_HOST_ONLY) and the shared launch plumbing ----
struct Bind{std::array<void*,19>p{};};
static Bind bind_gateup(const void*w,const void*peer,const void*x,uint8_t*o,const void*routes,const uint32_t*active){Bind b;b.p[0]=(void*)w;b.p[1]=(void*)peer;b.p[2]=(void*)x;b.p[3]=o;b.p[4]=o+cfg::RG*cfg::N*2;b.p[5]=(void*)routes;b.p[6]=o+2*cfg::RG*cfg::N*2;b.p[7]=o+2*cfg::RG*cfg::N*2+cfg::N*4;b.p[16]=o+cfg::OUT_G-4;b.p[17]=(void*)active;return b;}
static Bind bind_down(const void*t,const void*x,uint8_t*o,const void*routes,const uint32_t*active){Bind b;b.p[0]=(void*)t;b.p[1]=(void*)t;b.p[2]=(void*)x;b.p[3]=o;b.p[4]=o;b.p[5]=(void*)routes;b.p[6]=o+size_t(cfg::RD)*cfg::N*2;b.p[7]=b.p[6];b.p[16]=o+cfg::OUT_D-4;b.p[17]=(void*)active;return b;}
#ifdef OWN_RT_HOST_ONLY
#include <omp.h>
static uint64_t now_ns(){return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
template<class K>static std::vector<uint8_t> host_gateup(const K&k,const uint8_t*w,const uint8_t*peer,const uint16_t*x,const Routes&r){std::vector<uint8_t>o(cfg::OUT_G,0xa5);uint32_t active=1;std::memset(o.data()+cfg::OUT_G-4,0,4);auto b=bind_gateup(w,peer,x,o.data(),r.data(),&active);k.run(b.p);return o;}
template<class K>static std::vector<uint8_t> host_down(const K&k,const uint8_t*t,const uint16_t*x,const Routes&r){std::vector<uint8_t>o(cfg::OUT_D,0xa5);uint32_t active=1;std::memset(o.data()+cfg::OUT_D-4,0,4);auto b=bind_down(t,x,o.data(),r.data(),&active);k.run(b.p);return o;}
static int host_main(const Args&a){
 std::ifstream rf(a.routes);std::stringstream ss;ss<<rf.rdbuf();auto experts=parse_routes(ss.str());
 std::cout<<"{\"kind\":\"start\",\"mode\":\"host\",\"routes\":"<<experts.size()<<",\"threads\":"<<omp_get_max_threads()<<",\"cpu_only\":true}\n"<<std::flush;
 std::vector<uint8_t>gate(cfg::GATE_BANK),up(cfg::GATE_BANK),down(cfg::DOWN_BANK);
 {GateGen g;size_t row=0;while(!g.done()){auto c=g.chunk();size_t off=row*cfg::RBG;if(off<cfg::GATE_BANK)std::memcpy(gate.data()+off,c.data(),c.size());else std::memcpy(up.data()+off-cfg::GATE_BANK,c.data(),c.size());row+=cfg::CHUNK;}}
 DownGen d;{size_t row=0;while(!d.done()){auto c=d.chunk();std::memcpy(down.data()+row*cfg::RBD,c.data(),c.size());row+=cfg::CHUNK;}}
 auto xg=gate_input(192),xr=gate_input(162);std::vector<uint8_t>real0,real24;bool real=!a.real.empty();if(real){real0=load_real(a.real+"/layer0.bin");real24=load_real(a.real+"/layer24.bin");}
 p90exp::Kernel<iq3::Type::IQ2_S,cfg::KG,64,false,true>G;p100::Kernel<2>D;p192noload::GateUp GA;p192noload::Down DA;
 Fixtures fx;fx.dir=a.fixtures_out.empty()?a.fixtures:a.fixtures_out;fx.out=!a.fixtures_out.empty();
 if(!fx.out)fx.load(real);else{fx.gate_cold.resize(cfg::ROUTE_COUNT*cfg::OUT_G);fx.down_cold.resize(cfg::ROUTE_COUNT*cfg::OUT_D);}
 // cold stratum on CPU: one launch per route (parallel across routes; rows emitted in order), bytes vs fixture
 std::vector<size_t>gdiff(cfg::ROUTE_COUNT),ddiff(cfg::ROUTE_COUNT);std::vector<uint64_t>gns(cfg::ROUTE_COUNT),dns(cfg::ROUTE_COUNT);
 #pragma omp parallel for schedule(dynamic)
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){auto rg=routes_of(experts[r],cfg::RG),rd=routes_of(experts[r],cfg::RD);
  uint64_t t0=now_ns();auto og=host_gateup(G,gate.data(),up.data(),xg.data(),rg);uint64_t t1=now_ns();auto od=host_down(D,down.data(),d.hx.data(),rd);uint64_t t2=now_ns();gns[r]=t1-t0;dns[r]=t2-t1;
  if(fx.out){std::memcpy(fx.gate_cold.data()+size_t(r)*cfg::OUT_G,og.data(),cfg::OUT_G);std::memcpy(fx.down_cold.data()+size_t(r)*cfg::OUT_D,od.data(),cfg::OUT_D);gdiff[r]=ddiff[r]=0;}
  else{gdiff[r]=diff_bytes(og.data(),fx.gate_cold.data()+size_t(r)*cfg::OUT_G,cfg::OUT_G);ddiff[r]=diff_bytes(od.data(),fx.down_cold.data()+size_t(r)*cfg::OUT_D,cfg::OUT_D);}}
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){bytes_row("gateup","cold",int(r),gdiff[r],cfg::OUT_G,true);bytes_row("down","cold",int(r),ddiff[r],cfg::OUT_D,true);}
 for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){sample_row("gateup","cold",int(r),0,0,false,0,gns[r],0,true);sample_row("down","cold",int(r),0,0,false,0,dns[r],0,true);}
 // warm (route 0 experts) and real shapes
 auto rg0=routes_of(experts[0],cfg::RG),rd0=routes_of(experts[0],cfg::RD);
 {auto og=host_gateup(G,gate.data(),up.data(),xg.data(),rg0);auto od=host_down(D,down.data(),d.hx.data(),rd0);
  if(fx.out){fx.gate_warm=og;fx.down_warm=od;}bytes_row("gateup","warm",-1,fx.out?0:diff_bytes(og.data(),fx.gate_warm.data(),cfg::OUT_G),cfg::OUT_G,true);bytes_row("down","warm",-1,fx.out?0:diff_bytes(od.data(),fx.down_warm.data(),cfg::OUT_D),cfg::OUT_D,true);}
 if(real){Routes rr;for(unsigned i=0;i<cfg::N;++i)rr[i]={i,0,cfg::RG};
  auto o0=host_gateup(G,real0.data(),real0.data()+cfg::RG*cfg::N*cfg::RBG,xr.data(),rr),o24=host_gateup(G,real24.data(),real24.data()+cfg::RG*cfg::N*cfg::RBG,xr.data(),rr);
  if(fx.out){fx.gate_real0=o0;fx.gate_real24=o24;}bytes_row("gateup","warm-real-layer0",-1,fx.out?0:diff_bytes(o0.data(),fx.gate_real0.data(),cfg::OUT_G),cfg::OUT_G,true);bytes_row("gateup","warm-real-layer24",-1,fx.out?0:diff_bytes(o24.data(),fx.gate_real24.data(),cfg::OUT_G),cfg::OUT_G,true);}
 // alias self-test: on 16-row routes of expert 0 the no-load variant must equal production ((e*rows+row)&15 == row, slab = bank rows 0..15)
 {Routes ag,ad;for(unsigned i=0;i<cfg::N;++i){ag[i]={0,0,cfg::ALIAS_ROWS};ad[i]={0,0,cfg::ALIAS_ROWS};} // the alias slab is bank rows 0..15 = expert 0's first tile
  auto pg=host_gateup(G,gate.data(),up.data(),xg.data(),ag),ng=host_gateup(GA,gate.data(),up.data(),xg.data(),ag);auto pd=host_down(D,down.data(),d.hx.data(),ad),nd=host_down(DA,down.data(),d.hx.data(),ad);
  std::cout<<"{\"kind\":\"alias_selftest\",\"kernel\":\"gateup\",\"different_bytes\":"<<diff_bytes(pg.data(),ng.data(),cfg::OUT_G)<<",\"bytes_equal\":"<<(pg==ng?"true":"false")<<",\"rows_per_route\":"<<cfg::ALIAS_ROWS<<"}\n";
  std::cout<<"{\"kind\":\"alias_selftest\",\"kernel\":\"down\",\"different_bytes\":"<<diff_bytes(pd.data(),nd.data(),cfg::OUT_D)<<",\"bytes_equal\":"<<(pd==nd?"true":"false")<<",\"rows_per_route\":"<<cfg::ALIAS_ROWS<<"}\n";
  // and on full routes the alias variant must DIFFER from production (it is not exact by construction)
  auto fg=host_gateup(GA,gate.data(),up.data(),xg.data(),rg0),fd=host_down(DA,down.data(),d.hx.data(),rd0);
  bytes_row("gateup","noload",-1,diff_bytes(fg.data(),fx.out?fx.gate_warm.data():fx.gate_warm.data(),cfg::OUT_G),cfg::OUT_G,false);bytes_row("down","noload",-1,diff_bytes(fd.data(),fx.down_warm.data(),cfg::OUT_D),cfg::OUT_D,false);}
 // warm / no-load dry run of the stratum loop (sequential, few repeats)
 for(unsigned pass=0;pass<a.passes;++pass){for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_gateup(G,gate.data(),up.data(),xg.data(),rg0);uint64_t t1=now_ns();sample_row("gateup","warm",-1,pass,rep,false,t0,t1,0,true);}
  for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_gateup(GA,gate.data(),up.data(),xg.data(),rg0);uint64_t t1=now_ns();sample_row("gateup","noload",-1,pass,rep,false,t0,t1,0,true);}
  for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_down(D,down.data(),d.hx.data(),rd0);uint64_t t1=now_ns();sample_row("down","warm",-1,pass,rep,false,t0,t1,0,true);}
  for(unsigned rep=0;rep<a.warm;++rep){uint64_t t0=now_ns();host_down(DA,down.data(),d.hx.data(),rd0);uint64_t t1=now_ns();sample_row("down","noload",-1,pass,rep,false,t0,t1,0,true);}}
 if(fx.out)fx.write();
 std::cout<<"{\"kind\":\"summary\",\"schema\":\"packet192.issue-floor.v1\",\"passed\":true,\"drained\":true,\"diagnostic_only\":true,\"mode\":\"host\",\"cpu_only\":true,\"route_count\":"<<cfg::ROUTE_COUNT<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"real_shapes\":"<<(real?"true":"false")<<",\"fixtures_written\":"<<(fx.out?"true":"false")<<"}\n"<<std::flush;
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
template<class Launch>static void timed(Dev&d,uint32_t*scrub,const char*kernel,const char*stratum,int route,unsigned pass,unsigned repeats,bool cold,Launch launch){
 unsigned warm=cold?0:cfg::WARMUPS;
 for(unsigned rep=0;rep<warm+repeats;++rep){guard();
  if(cold)d.q.parallel_for(sycl::range<1>(cfg::SCRUB_WORDS),[=](sycl::id<1>id){scrub[id]=uint32_t(id[0]);}).wait_and_throw();
  sycl::event e=launch();e.wait_and_throw();
  uint64_t s=e.get_profiling_info<sycl::info::event_profiling::command_start>(),t=e.get_profiling_info<sycl::info::event_profiling::command_end>();
  sample_row(kernel,stratum,route,pass,rep<warm?rep:rep-warm,rep<warm,s,t,cold?cfg::SCRUB_WORDS*4:0,false);}
 std::cout<<std::flush;
}
static int device_main(const Args&a){
 std::ifstream rf(a.routes);std::stringstream ss;ss<<rf.rdbuf();auto experts=parse_routes(ss.str());
 const char*probe=std::getenv("ENTRY_PREPARE_OUTPUT");
 if(probe){ // CPU preparation path: parse, bound, exercise both generators and the real-row repack on one chunk; no device API.
  GateGen g;auto gc=g.chunk();DownGen d;auto dc=d.chunk();require(gc.size()==cfg::CHUNK*cfg::RBG&&dc.size()==cfg::CHUNK*cfg::RBD,"generator chunk extents");
  size_t device_bytes=cfg::SCRUB_WORDS*4+std::max(2*cfg::GATE_BANK+2*cfg::REAL_ROWS*cfg::RBG+2*cfg::KG*2+cfg::OUT_G,cfg::DOWN_BANK+cfg::KD*cfg::N*2+cfg::OUT_D)+256;
  std::ofstream(std::string(probe)+"/prepare.json")<<"{\"passed\":true,\"device_executed\":false,\"routes\":"<<experts.size()<<",\"planned_device_peak_bytes\":"<<device_bytes<<",\"gate_bank_bytes\":"<<cfg::GATE_BANK<<",\"down_bank_bytes\":"<<cfg::DOWN_BANK<<",\"scrub_bytes\":"<<cfg::SCRUB_WORDS*4<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<"}\n";
  std::cout<<"PASS CPU preparation before first device call; routes="<<experts.size()<<" planned_device_peak_bytes="<<device_bytes<<"\n";return 0;}
 Fixtures fx;fx.dir=a.fixtures;fx.load(!a.real.empty());
 std::vector<uint8_t>real0,real24;bool real=!a.real.empty();if(real){real0=load_real(a.real+"/layer0.bin");real24=load_real(a.real+"/layer24.bin");}
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 Dev d;std::cout<<"{\"kind\":\"start\",\"mode\":\"device\",\"device\":\""<<d.q.get_device().get_info<sycl::info::device::name>()<<"\",\"routes\":"<<experts.size()<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"warmups\":"<<cfg::WARMUPS<<"}\n"<<std::flush;
 auto*scrub=(uint32_t*)d.alloc(cfg::SCRUB_WORDS*4);
 auto upload=[&](uint8_t*dst,auto&gen,size_t total){std::vector<uint8_t>stage;stage.reserve(16*cfg::CHUNK*cfg::RBG);size_t off=0;while(!gen.done()){guard();stage.clear();for(unsigned i=0;i<16&&!gen.done();++i){auto c=gen.chunk();stage.insert(stage.end(),c.begin(),c.end());}d.q.memcpy(dst+off,stage.data(),stage.size()).wait_and_throw();off+=stage.size();}require(off==total,"bank upload extent");};
 auto fetch=[&](const uint8_t*o,size_t n){std::vector<uint8_t>v(n);d.q.memcpy(v.data(),o,n).wait_and_throw();return v;};
 uint32_t one=1;
 // ---------------- phase 1: gate/up ----------------
 {auto*gate=(uint8_t*)d.alloc(2*cfg::GATE_BANK);auto*up=gate+cfg::GATE_BANK;{GateGen g;upload(gate,g,2*cfg::GATE_BANK);}
  auto xg=gate_input(192),xr=gate_input(162);auto*x=(uint16_t*)d.alloc(cfg::KG*2);auto*xdr=(uint16_t*)d.alloc(cfg::KG*2);d.q.memcpy(x,xg.data(),cfg::KG*2);d.q.memcpy(xdr,xr.data(),cfg::KG*2);
  auto*routes=(iq3::Route*)d.alloc(sizeof(Routes));auto*o=(uint8_t*)d.alloc(cfg::OUT_G);auto*active=(uint32_t*)d.alloc(4);d.q.memcpy(active,&one,4).wait_and_throw();
  uint8_t*r0=nullptr,*r24=nullptr;if(real){r0=(uint8_t*)d.alloc(real0.size());r24=(uint8_t*)d.alloc(real24.size());d.q.memcpy(r0,real0.data(),real0.size());d.q.memcpy(r24,real24.data(),real24.size()).wait_and_throw();}
  allocation_row(d,"gateup");
  p90exp::Kernel<iq3::Type::IQ2_S,cfg::KG,64,false,true>G;p192noload::GateUp GA;
  auto set_routes=[&](const Routes&r){d.q.memcpy(routes,r.data(),sizeof(Routes)).wait_and_throw();};
  auto clear=[&]{d.q.memset(o,0xa5,cfg::OUT_G);d.q.memset(o+cfg::OUT_G-4,0,4).wait_and_throw();};
  auto launch=[&](auto&k,const uint8_t*w,const uint8_t*peer,const uint16_t*xx){auto b=bind_gateup(w,peer,xx,o,routes,active);return k.submit(d.q,b.p,{});};
  for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){guard();set_routes(routes_of(experts[r],cfg::RG));clear();launch(G,gate,up,x).wait_and_throw();auto got=fetch(o,cfg::OUT_G);bytes_row("gateup","cold",int(r),diff_bytes(got.data(),fx.gate_cold.data()+size_t(r)*cfg::OUT_G,cfg::OUT_G),cfg::OUT_G,true);}
  auto rg0=routes_of(experts[0],cfg::RG);set_routes(rg0);clear();launch(G,gate,up,x).wait_and_throw();{auto got=fetch(o,cfg::OUT_G);bytes_row("gateup","warm",-1,diff_bytes(got.data(),fx.gate_warm.data(),cfg::OUT_G),cfg::OUT_G,true);}
  Routes rr;for(unsigned i=0;i<cfg::N;++i)rr[i]={i,0,cfg::RG};
  if(real){set_routes(rr);clear();launch(G,r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr).wait_and_throw();{auto got=fetch(o,cfg::OUT_G);bytes_row("gateup","warm-real-layer0",-1,diff_bytes(got.data(),fx.gate_real0.data(),cfg::OUT_G),cfg::OUT_G,true);}
   clear();launch(G,r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr).wait_and_throw();{auto got=fetch(o,cfg::OUT_G);bytes_row("gateup","warm-real-layer24",-1,diff_bytes(got.data(),fx.gate_real24.data(),cfg::OUT_G),cfg::OUT_G,true);}}
  {Routes ag;for(unsigned i=0;i<cfg::N;++i)ag[i]={0,0,cfg::ALIAS_ROWS};set_routes(ag);clear();launch(G,gate,up,x).wait_and_throw();auto pg=fetch(o,cfg::OUT_G);clear();launch(GA,gate,up,x).wait_and_throw();auto ng=fetch(o,cfg::OUT_G);
   std::cout<<"{\"kind\":\"alias_selftest\",\"kernel\":\"gateup\",\"different_bytes\":"<<diff_bytes(pg.data(),ng.data(),cfg::OUT_G)<<",\"bytes_equal\":"<<(pg==ng?"true":"false")<<",\"rows_per_route\":"<<cfg::ALIAS_ROWS<<"}\n";
   set_routes(rg0);clear();launch(GA,gate,up,x).wait_and_throw();auto fg=fetch(o,cfg::OUT_G);bytes_row("gateup","noload",-1,diff_bytes(fg.data(),fx.gate_warm.data(),cfg::OUT_G),cfg::OUT_G,false);}
  std::cout<<std::flush;
  for(unsigned pass=0;pass<a.passes;++pass){
   for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){set_routes(routes_of(experts[r],cfg::RG));timed(d,scrub,"gateup","cold",int(r),pass,a.cold,true,[&]{return launch(G,gate,up,x);});}
   set_routes(rg0);timed(d,scrub,"gateup","warm",-1,pass,a.warm,false,[&]{return launch(G,gate,up,x);});
   if(real){set_routes(rr);timed(d,scrub,"gateup","warm-real-layer0",-1,pass,a.warm,false,[&]{return launch(G,r0,r0+cfg::RG*cfg::N*cfg::RBG,xdr);});timed(d,scrub,"gateup","warm-real-layer24",-1,pass,a.warm,false,[&]{return launch(G,r24,r24+cfg::RG*cfg::N*cfg::RBG,xdr);});}
   set_routes(rg0);timed(d,scrub,"gateup","noload",-1,pass,a.warm,false,[&]{return launch(GA,gate,up,x);});}
  d.q.wait_and_throw();for(void*p:{(void*)gate,(void*)x,(void*)xdr,(void*)routes,(void*)o,(void*)active})d.release(p);if(real){d.release(r0);d.release(r24);}
 }
 // ---------------- phase 2: down (tile16) ----------------
 {auto*t=(uint8_t*)d.alloc(cfg::DOWN_BANK);DownGen g;upload(t,g,cfg::DOWN_BANK);
  auto*x=(uint16_t*)d.alloc(size_t(cfg::KD)*cfg::N*2);d.q.memcpy(x,g.hx.data(),g.hx.size()*2);
  auto*routes=(iq3::Route*)d.alloc(sizeof(Routes));auto*o=(uint8_t*)d.alloc(cfg::OUT_D);auto*active=(uint32_t*)d.alloc(4);d.q.memcpy(active,&one,4).wait_and_throw();
  allocation_row(d,"down");
  p100::Kernel<2>D;p192noload::Down DA;
  auto set_routes=[&](const Routes&r){d.q.memcpy(routes,r.data(),sizeof(Routes)).wait_and_throw();};
  auto clear=[&]{d.q.memset(o,0xa5,cfg::OUT_D);d.q.memset(o+cfg::OUT_D-4,0,4).wait_and_throw();};
  auto launch=[&](auto&k){auto b=bind_down(t,x,o,routes,active);return k.submit(d.q,b.p,{});};
  for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){guard();set_routes(routes_of(experts[r],cfg::RD));clear();launch(D).wait_and_throw();auto got=fetch(o,cfg::OUT_D);bytes_row("down","cold",int(r),diff_bytes(got.data(),fx.down_cold.data()+size_t(r)*cfg::OUT_D,cfg::OUT_D),cfg::OUT_D,true);}
  auto rd0=routes_of(experts[0],cfg::RD);set_routes(rd0);clear();launch(D).wait_and_throw();{auto got=fetch(o,cfg::OUT_D);bytes_row("down","warm",-1,diff_bytes(got.data(),fx.down_warm.data(),cfg::OUT_D),cfg::OUT_D,true);}
  {Routes ad;for(unsigned i=0;i<cfg::N;++i)ad[i]={0,0,cfg::ALIAS_ROWS};set_routes(ad);clear();launch(D).wait_and_throw();auto pd=fetch(o,cfg::OUT_D);clear();launch(DA).wait_and_throw();auto nd=fetch(o,cfg::OUT_D);
   std::cout<<"{\"kind\":\"alias_selftest\",\"kernel\":\"down\",\"different_bytes\":"<<diff_bytes(pd.data(),nd.data(),cfg::OUT_D)<<",\"bytes_equal\":"<<(pd==nd?"true":"false")<<",\"rows_per_route\":"<<cfg::ALIAS_ROWS<<"}\n";
   set_routes(rd0);clear();launch(DA).wait_and_throw();auto fd=fetch(o,cfg::OUT_D);bytes_row("down","noload",-1,diff_bytes(fd.data(),fx.down_warm.data(),cfg::OUT_D),cfg::OUT_D,false);}
  std::cout<<std::flush;
  for(unsigned pass=0;pass<a.passes;++pass){
   for(unsigned r=0;r<cfg::ROUTE_COUNT;++r){set_routes(routes_of(experts[r],cfg::RD));timed(d,scrub,"down","cold",int(r),pass,a.cold,true,[&]{return launch(D);});}
   set_routes(rd0);timed(d,scrub,"down","warm",-1,pass,a.warm,false,[&]{return launch(D);});
   timed(d,scrub,"down","noload",-1,pass,a.warm,false,[&]{return launch(DA);});}
  d.q.wait_and_throw();for(void*p:{(void*)t,(void*)x,(void*)routes,(void*)o,(void*)active})d.release(p);
 }
 d.q.wait_and_throw();guard();
 std::cout<<"{\"kind\":\"summary\",\"schema\":\"packet192.issue-floor.v1\",\"passed\":true,\"drained\":true,\"diagnostic_only\":true,\"mode\":\"device\",\"cpu_only\":false,\"route_count\":"<<cfg::ROUTE_COUNT<<",\"cold_repeats\":"<<a.cold<<",\"warm_repeats\":"<<a.warm<<",\"passes\":"<<a.passes<<",\"real_shapes\":"<<(real?"true":"false")<<",\"device_peak_bytes\":"<<d.peak<<"}\n"<<std::flush;
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
