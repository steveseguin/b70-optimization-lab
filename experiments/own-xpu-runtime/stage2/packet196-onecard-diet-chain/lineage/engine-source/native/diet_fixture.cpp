// Packet58-onecard-diet-engine: engine-dispatch exactness of the one-card gate/up instruction diet on the host twins (CPU only).
// The REAL dispatch (p58ag::expert with the record line's halfcache layout, cached=true, indirect expert-cache slots, the
// halfcache table binding p[19]) and the in-load key expert_gateup = production | diet is driven through the engine's own
// host backend (packet18::LifetimeMock, as main.cpp's Host) on: (a) packet162b's REAL layer-0 and layer-24 gate/up rows
// (10 routed experts x 640 rows x two streams, re-laid out into the 820-B p49bgemv layout by the line's repack_row),
// (b) a synthetic 512-expert bank (packet192/193 raw-byte generator, finite halves) with the record's scenarios (invalid
// expert, inactive, error-preset, partial routes, NaN / Inf / subnormal inputs) and permuted slot tables (reverse,
// shuffled), (c) the non-finite-half bank (+-Inf, NaN patterns, +-0, subnormal halves). For every stratum the bytes of
// y, peer y, status, peer status, error, active and position after `diet` must equal the bytes after `production`, and
// the six-argument `production` must equal the five-argument record dispatch. Differing BF16 words that are NaN on both
// sides on a NaN-producing stratum are classified "payload order" (packet162/193 rule: recorded, never canonicalised);
// any other difference fails. Negative cases: `diet` on a non-halfcache layout (cached=false), on a direct (non-slot)
// binding and an unknown key value must refuse without writing.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p58ag_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p58ag_expert.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/lifetime_mock.hpp"
#include <openssl/evp.h>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <vector>
namespace {
using namespace ownrt;using namespace integrated;
void check(bool v,const std::string&s){if(!v)throw std::runtime_error(s);}
std::string sha256hex(const uint8_t*p,size_t n){unsigned char md[32];unsigned len=0;check(EVP_Digest(p,n,md,&len,EVP_sha256(),nullptr)==1&&len==32,"sha256");std::string s;for(unsigned i=0;i<32;++i){s+="0123456789abcdef"[md[i]>>4];s+="0123456789abcdef"[md[i]&15];}return s;}
// main.cpp's host backend: compute runs the host operation synchronously (the engine's OWN_RT_HOST_ONLY twin)
class Host final : public packet18::LifetimeMock {
public:
  ownrt::Event copy(void *a, const void *b, size_t n, std::span<const ownrt::Event> d) override {auto e = LifetimeMock::copy(a, b, n, d);finish(e);return e;}
  std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const> p) override {
    auto host=std::dynamic_pointer_cast<const integrated::HostOperation>(op);if(!host)throw std::logic_error("host operation type");
    return [this,host,pointers=std::vector<void*>(p.begin(),p.end())]{host->run(pointers);return marker({});};
  }
  ownrt::Event compute(const ownrt::Operation &o, std::span<void *const> p, std::span<const ownrt::Event> d) override {dynamic_cast<const integrated::HostOperation &>(o).run(p);return marker(d);}
};
struct Runner {
 Device d;std::vector<Allocation>owned;size_t serial=0;
 Runner():d(std::make_unique<Host>()){}
 Allocation alloc(size_t n){auto id=d.arena.allocate("p58de-fixture-"+std::to_string(serial++),n,Memory::device,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void* ptr(Allocation id){return d.arena.row(id).pointer;}
 void write(Allocation id,const void*p,size_t n){check(d.arena.row(id).bytes>=n,"write extent");std::memcpy(ptr(id),p,n);}
 Allocation upload(const void*p,size_t n){auto id=alloc(n);write(id,p,n);return id;}
 template<class T>Allocation vec(const std::vector<T>&v){return upload(v.data(),v.size()*sizeof(T));}
 Allocation word(uint32_t v){return upload(&v,4);}
 std::vector<uint8_t>read(Allocation id){size_t n=d.arena.row(id).bytes;auto p=static_cast<uint8_t*>(ptr(id));return std::vector<uint8_t>(p,p+n);}
 using Snap=std::vector<std::vector<uint8_t>>;
 Snap snapshot(const std::vector<Allocation>&ids){Snap out;for(auto id:ids)out.push_back(read(id));return out;}
 void restore(const std::vector<Allocation>&ids,const Snap&v){for(size_t j=0;j<ids.size();++j)write(ids[j],v[j].data(),v[j].size());}
 void finish(Event e){check(d.wait(e,std::chrono::milliseconds(300000)),"fixture submission timeout");}
 void clear(){d.retire_completed_events();for(auto id:owned)d.arena.release(id);owned.clear();}
};
constexpr unsigned K=2560,ROWS=640,COUNT=10,E=512;constexpr iq3::Type T=iq3::Type::IQ2_S;
constexpr size_t RB=p49bgemv::layout(T,K).row_bytes;static_assert(RB==820);
constexpr size_t EXPERT_BYTES=size_t(ROWS)*RB;                       // 524,800: the p58::resolve expert span
constexpr size_t REAL_ROWS=2*ROWS*COUNT,REAL_RAW=820;               // packet162b: 12,800 raw GGUF rows (82 B x 10 blocks)
struct Lcg{uint32_t s;uint32_t next(){s=s*1664525u+1013904223u;return s;}};
// synthetic bank: random raw 820-B GGUF IQ2_S rows, every block scale 0x2400 (packet192/193 generator), repacked by the line's tool
std::vector<uint8_t> synthetic_bank(uint32_t seed,unsigned experts){
 Lcg g{seed};std::vector<uint8_t> raw(REAL_RAW),bank(size_t(experts)*EXPERT_BYTES);
 for(size_t row=0;row<size_t(experts)*ROWS;++row){for(auto&v:raw)v=uint8_t(g.next()>>24);for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}p49bgemv::repack_row(T,K,raw.data(),bank.data()+row*RB);}
 return bank;
}
// non-finite-half bank (packet58-onecard-diet-micro seed 193): every block half from {finite, +-Inf, NaN patterns, +-0, subnormal, max}
uint16_t special_half(Lcg&g){static const uint16_t table[]={0x7c00,0xfc00,0x7e00,0xfe01,0x7c01,0xfdff,0x0000,0x8000,0x0001,0x8001,0x03ff,0x83ff,0x7bff,0xfbff,0x0400,0x8400};
 unsigned c=g.next()%16;if(c<8)return uint16_t(0x0400+g.next()%0x7800)|uint16_t((g.next()&1)<<15);return table[g.next()%16];}
std::vector<uint8_t> exc_bank(uint32_t seed,unsigned experts){
 Lcg g{seed};auto bank=synthetic_bank(seed,experts);const auto l=p49bgemv::layout(T,K);
 for(size_t row=0;row<size_t(experts)*ROWS;++row)for(unsigned b=0;b<K/256;++b){uint16_t h=special_half(g);std::memcpy(bank.data()+row*RB+l.halves+2*b,&h,2);}
 return bank;
}
std::pair<std::vector<uint8_t>,std::vector<uint8_t>> real_bank(const std::string& path){
 std::ifstream f(path,std::ios::binary|std::ios::ate);check(bool(f)&&f.tellg()==std::streamoff(REAL_ROWS*REAL_RAW),"real rows extent: "+path);
 std::vector<uint8_t> raw(REAL_ROWS*REAL_RAW);f.seekg(0);f.read(reinterpret_cast<char*>(raw.data()),raw.size());check(bool(f),"real rows truncated");
 std::vector<uint8_t> w(size_t(COUNT)*EXPERT_BYTES),peer(w.size());
 for(size_t row=0;row<REAL_ROWS;++row){const auto* s=raw.data()+row*REAL_RAW;
  for(unsigned b=0;b<10;++b)check((p49bgemv::load16(s+82*b)&0x7c00)!=0x7c00,"nonfinite real weight scale");
  auto& dest=row<ROWS*COUNT?w:peer;p49bgemv::repack_row(T,K,s,dest.data()+(row%(ROWS*COUNT))*RB);}
 return {w,peer};
}
std::vector<unsigned> permutation(unsigned n,int kind){std::vector<unsigned>p(n);for(unsigned i=0;i<n;++i)p[i]=kind==1?n-1-i:i;
 if(kind==2){Lcg g{0x58d0u};for(unsigned i=n-1;i>0;--i){unsigned j=g.next()%(i+1);std::swap(p[i],p[j]);}}return p;}
// p58::Pointer slot table over a bank: slot e -> expert block perm[e] (identity = the record line's resident-expert layout)
std::vector<p58::Pointer> slots(const uint8_t*bank,const std::vector<unsigned>&perm){std::vector<p58::Pointer>t(perm.size());for(size_t e=0;e<perm.size();++e){p58::Pointer q;q.address=uint64_t(bank+size_t(perm[e])*EXPERT_BYTES);q.generation=0x58d0ull+e;t[e]=q;}return t;}
std::vector<uint16_t> input(unsigned scenario,uint32_t seed){
 std::vector<uint16_t> x(K);Lcg g{seed};for(auto& v:x)v=iq3::bf16_bits(float(int(g.next()%255)-127)/128.f);
 if(scenario==5){static const uint16_t special[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2};for(size_t i=0;i<K;i+=17)x[i]=special[(i/17)%8];} // packet162b fixture f2
 if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}            // +-Inf
 if(scenario==7){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;} // subnormals and signed zeros
 return x;
}
bool nan16(uint16_t v){return (v&0x7f80u)==0x7f80u&&(v&0x7fu);}
struct Diff{size_t bytes=0,words=0,nan_words=0,other_bytes=0;};
Diff diff(const std::vector<uint8_t>& a,const std::vector<uint8_t>& b,bool bf16){Diff d;check(a.size()==b.size(),"compared extents");
 if(bf16){for(size_t i=0;i+1<a.size();i+=2){uint16_t x=uint16_t(a[i]|(a[i+1]<<8)),y=uint16_t(b[i]|(b[i+1]<<8));if(x!=y){++d.words;d.bytes+=(a[i]!=b[i])+(a[i+1]!=b[i+1]);if(nan16(x)&&nan16(y))++d.nan_words;else d.other_bytes+=(a[i]!=b[i])+(a[i+1]!=b[i+1]);}}}
 else for(size_t i=0;i<a.size();++i)if(a[i]!=b[i]){++d.bytes;++d.other_bytes;}
 return d;}
const char* SCENARIO[]={"normal","invalid-expert","inactive","error-preset","partial-routes","nan-inputs","inf-inputs","subnormal-inputs","slots-reverse","slots-shuffled"};
}
int main(int argc,char**argv){std::filesystem::path out;std::string real;
 try{
  for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--output"&&i+1<argc)out=argv[++i];else if(k=="--real-rows"&&i+1<argc)real=argv[++i];else throw std::invalid_argument("diet fixture arguments: --output DIR --real-rows DIR");}
  check(!out.empty()&&!real.empty(),"--output and --real-rows required");std::filesystem::create_directories(out);
  Runner r;std::ofstream cases(out/"cases.jsonl");unsigned strata=0,equal=0,payload_rows=0,refusals=0;size_t compared=0;
  // the engine's exact-half-decode-table (main.cpp initialize_cache): table[i] = iq3::half(i)
  std::vector<float> table(65536);for(unsigned i=0;i<65536;++i)table[i]=iq3::half(uint16_t(i));auto halfcache=r.vec(table);
  struct Bank{std::string name;std::vector<uint8_t> w,peer;unsigned experts;bool nan;};
  std::vector<Bank> banks;
  {auto [w0,p0]=real_bank(real+"/layer0.bin");banks.push_back({"real-layer0",std::move(w0),std::move(p0),COUNT,false});
   auto [w24,p24]=real_bank(real+"/layer24.bin");banks.push_back({"real-layer24",std::move(w24),std::move(p24),COUNT,false});
   banks.push_back({"synthetic",synthetic_bank(192u,E),synthetic_bank(193u,E),E,false});
   banks.push_back({"exceptional-halves",exc_bank(0x193u,COUNT),exc_bank(0x194u,COUNT),COUNT,true});}
  for(const auto& bank:banks){
   auto gate_id=r.vec(bank.w),up_id=r.vec(bank.peer);const auto* gate=static_cast<const uint8_t*>(r.ptr(gate_id));const auto* up=static_cast<const uint8_t*>(r.ptr(up_id));
   for(unsigned scenario=0;scenario<10;++scenario){
    if(bank.name!="synthetic"&&scenario>=8)continue; // slot permutations on the 512-expert bank only
    const bool nan_stratum=bank.nan||scenario==5||scenario==6;
    const int perm_kind=scenario==8?1:scenario==9?2:0;auto perm=permutation(bank.experts,perm_kind);
    auto gslots=slots(gate,perm),uslots=slots(up,perm);
    auto ac=r.word(scenario==2?0:1),er=r.word(scenario==3?7:0),pos=r.word(0);
    std::vector<iq3::Route> routes(COUNT);for(unsigned j=0;j<COUNT;++j)routes[j]={uint32_t(bank.experts==E?(j*37+5)%E:(j*3+1)%COUNT),0,ROWS};
    if(scenario==1)routes[2].expert_id=bank.experts; // invalid expert -> status/error
    if(scenario==4){routes[0].row_count=0;routes[1].row_count=ROWS-2;routes[1].row_begin=1;routes[2].row_begin=ROWS;routes[2].row_count=1;routes[7].row_begin=3;routes[7].row_count=ROWS-3;}
    Matrix a{};a.type=T;a.w=r.vec(gslots);a.x=r.vec(input(scenario,0x5eed+scenario));a.y=r.vec(std::vector<uint16_t>(ROWS*COUNT,0x7e31));a.rows=ROWS;a.columns=K;a.span=ROWS;a.count=COUNT;a.experts=bank.experts;a.routes=r.vec(routes);a.status=r.vec(std::vector<uint32_t>(COUNT,9));a.workspace=r.vec(std::vector<float>(ROWS*COUNT*8,-3));
    auto b=a;b.w=r.vec(uslots);b.y=r.vec(std::vector<uint16_t>(ROWS*COUNT,0x7e32));b.status=r.vec(std::vector<uint32_t>(COUNT,8));
    std::vector<Matrix> m{a,b};p39::Bindings controls;controls.active=ac;controls.error=er;controls.position=pos;controls.capacity=4096;controls.indirect=true;
    std::vector<Allocation> watch{a.y,b.y,a.status,b.status,er,ac,pos};const bool bf16[]={true,true,false,false,false,false,false};
    auto initial=r.snapshot(watch);
    r.finish(p58ag::expert(r.d,m,controls,halfcache,true).last);auto record=r.snapshot(watch);   // the five-argument record dispatch (key absent = production)
    r.restore(watch,initial);r.finish(p58ag::expert(r.d,m,controls,halfcache,true,"production").last);auto production=r.snapshot(watch);
    r.restore(watch,initial);r.finish(p58ag::expert(r.d,m,controls,halfcache,true,"diet").last);auto diet=r.snapshot(watch);
    check(record==production,"six-argument production differs from the five-argument record dispatch: "+bank.name+" "+SCENARIO[scenario]);
    check(production!=initial,"production wrote nothing: "+bank.name+" "+SCENARIO[scenario]);
    Diff total;for(size_t j=0;j<watch.size();++j){auto d=diff(production[j],diet[j],bf16[j]);total.bytes+=d.bytes;total.words+=d.words;total.nan_words+=d.nan_words;total.other_bytes+=d.other_bytes;compared+=production[j].size();}
    check(total.other_bytes==0,"diet value difference: "+bank.name+" "+SCENARIO[scenario]+" bytes "+std::to_string(total.other_bytes));
    check(total.bytes==0||nan_stratum,"diet payload-order difference outside a NaN stratum: "+bank.name+" "+SCENARIO[scenario]);
    const bool bytes_equal=total.bytes==0;equal+=bytes_equal;payload_rows+=!bytes_equal;++strata;
    check(production[2]==diet[2]&&production[3]==diet[3]&&production[4]==diet[4]&&production[5]==diet[5]&&production[6]==diet[6],"status/control words differ");
    uint32_t error_word=0;std::memcpy(&error_word,diet[4].data(),4);
    cases<<"{\"bank\":"<<quote(bank.name)<<",\"scenario\":"<<quote(SCENARIO[scenario])<<",\"experts\":"<<bank.experts<<",\"slots\":"<<quote(perm_kind==0?"identity":perm_kind==1?"reverse":"shuffled")<<",\"nan_stratum\":"<<(nan_stratum?"true":"false")<<",\"record_equals_production\":true,\"bytes_equal\":"<<(bytes_equal?"true":"false")<<",\"different_bytes\":"<<total.bytes<<",\"different_words\":"<<total.words<<",\"nan_vs_nan_words\":"<<total.nan_words<<",\"other_bytes\":"<<total.other_bytes<<",\"payload_order_only\":"<<((!bytes_equal&&total.other_bytes==0)?"true":"false")<<",\"compared_bytes\":"<<[&]{size_t n=0;for(auto& v:production)n+=v.size();return n;}()<<",\"y_sha256\":"<<quote(sha256hex(diet[0].data(),diet[0].size()))<<",\"py_sha256\":"<<quote(sha256hex(diet[1].data(),diet[1].size()))<<",\"error_word\":"<<error_word<<",\"status\":["<<[&]{std::string s;for(unsigned j=0;j<COUNT;++j){uint32_t v;std::memcpy(&v,diet[2].data()+4*j,4);s+=(j?",":"")+std::to_string(v);}return s;}()<<"]}\n";
    if(scenario==0&&bank.name=="synthetic"){ // negatives on the normal stratum: non-halfcache layout, direct binding and an unknown value refuse before any write
     auto before=r.snapshot(watch);bool refused=false;
     try{p58ag::expert(r.d,m,controls,halfcache,false,"diet");}catch(const std::invalid_argument&){refused=true;}
     check(refused&&r.snapshot(watch)==before,"diet on a non-halfcache layout must refuse without writing");++refusals;
     refused=false;try{p58ag::expert(r.d,m,controls,halfcache,true,"bogus");}catch(const std::invalid_argument&){refused=true;}
     check(refused&&r.snapshot(watch)==before,"unknown expert_gateup must refuse without writing");++refusals;
     auto direct=controls;direct.indirect=false;refused=false;try{p58ag::expert(r.d,m,direct,halfcache,true,"diet");}catch(const std::invalid_argument&){refused=true;}
     check(refused&&r.snapshot(watch)==before,"diet on a direct (non-slot) binding must refuse without writing");++refusals;
    }
    for(auto id:watch)(void)id;
    r.d.retire_completed_events();
   }
   r.clear();halfcache=r.vec(table);
  }
  cases.close();
  std::ofstream receipt(out/"result.json");
  receipt<<"{\"schema\":\"packet58dietengine.diet-dispatch-fixture.v1\",\"passed\":true,\"device_executed\":false,\"cpu_only\":true,\"strata\":"<<strata<<",\"byte_equal_strata\":"<<equal<<",\"payload_order_only_strata\":"<<payload_rows<<",\"refusals\":"<<refusals<<",\"compared_bytes\":"<<compared<<",\"dispatch\":\"p58ag::expert(cached=true halfcache layout, indirect slots, expert_gateup=production|diet) vs the five-argument record dispatch\",\"real_rows\":"<<quote(real)<<"}\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
