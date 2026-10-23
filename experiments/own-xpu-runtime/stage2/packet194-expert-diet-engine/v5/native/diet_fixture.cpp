// Packet194: engine-dispatch exactness of the exp-diet gate/up kernel on the host twins (CPU only, no device).
// The REAL dispatch (p49d::expert with the engine's selection strings "exp-halfcache+down-tile16" and the in-load key
// expert_gateup = production | diet) is driven through the production submission ABI (p49d_fixture.cpp's host backend)
// on: (a) packet162b's REAL layer-0 and layer-24 gate/up rows (10 routed experts x 640 rows x two streams, repacked
// with the record's exp-halfcache layout), (b) synthetic banks with the record's scenarios (invalid expert, partial
// routes, inactive, error-preset, NaN / Inf / subnormal inputs). For every stratum the bytes of y, peer y, status,
// peer status, error, active and position after `diet` must equal the bytes after `production`, and the six-argument
// `production` must equal the five-argument record dispatch. Differing BF16 words that are NaN on both sides on a
// NaN-producing stratum are classified "payload order" (packet162/193 rule: recorded, never canonicalised); any other
// difference fails. Negative cases: `diet` on a non-halfcache gate/up layout and an unknown key value must refuse.
#include "p49d_submit.hpp"
#include "p49b_expert_submit.hpp"
#include "p90_layout.hpp"
#include "adapter.hpp"
#include "failure.hpp"
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
struct Cpu final:Backend {
 std::string identity()const override{return "CPU packet194 diet dispatch fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void*p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void*a,const void*b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation&op,std::span<void*const>p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
struct Runner {
 Device d;CopyEngine copy;std::vector<Allocation>owned;size_t serial=0;
 Runner():d(std::make_unique<Cpu>()),copy(d){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=d.arena.allocate("p194-fixture-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){check(d.wait(e,std::chrono::milliseconds(300000)),"fixture submission timeout");}
 void write(Allocation id,const void*p,size_t n){auto h=alloc(n,Memory::pinned);std::memcpy(d.arena.row(h).pointer,p,n);finish(copy.copy(id,0,h,0,n,{}));d.arena.release(h);owned.pop_back();}
 Allocation upload(const void*p,size_t n){auto id=alloc(n);write(id,p,n);return id;}
 template<class T>Allocation vec(const std::vector<T>&v){return upload(v.data(),v.size()*sizeof(T));}
 Allocation word(uint32_t v){return upload(&v,4);}
 std::vector<uint8_t>read(Allocation id){size_t n=d.arena.row(id).bytes;auto h=alloc(n,Memory::pinned);finish(copy.copy(h,0,id,0,n,{}));auto p=static_cast<uint8_t*>(d.arena.row(h).pointer);std::vector<uint8_t>v(p,p+n);d.arena.release(h);owned.pop_back();return v;}
 using Snap=std::vector<std::vector<uint8_t>>;
 Snap snapshot(const std::vector<Allocation>&ids){Snap out;for(auto id:ids)out.push_back(read(id));return out;}
 void restore(const std::vector<Allocation>&ids,const Snap&v){for(size_t j=0;j<ids.size();++j)write(ids[j],v[j].data(),v[j].size());}
 void clear(){d.retire_completed_events();for(auto id:owned)d.arena.release(id);owned.clear();}
};
constexpr unsigned K=2560,ROWS=640,COUNT=10;constexpr iq3::Type T=iq3::Type::IQ2_S;
constexpr size_t REAL_ROWS=12800,REAL_RAW=820; // packet162b micro-inputs: 640 rows x 10 experts x {w, peer} raw IQ2_S rows
uint32_t next(uint32_t& seed){seed=seed*1664525u+1013904223u;return seed;}
std::vector<uint16_t> input(unsigned scenario,uint32_t seed){
 std::vector<uint16_t> x(K);for(auto& v:x)v=iq3::bf16_bits(float(int(next(seed)%255)-127)/128.f);
 if(scenario==5){x[0]=0x7fc1;x[8]=0xffd5;}            // NaN payloads
 if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}            // +-Inf
 if(scenario==7){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;} // subnormals and signed zeros
 return x;
}
// Synthetic bank in the record's exp-halfcache layout (p90::expert_repack of random raw IQ2_S rows with finite halves).
std::vector<uint8_t> synthetic_bank(uint32_t seed){
 const size_t raw_stride=p49bgemv::source_row_bytes(T,K),stride=p90::expert_stride(K);const auto f=iq3::layout(T);
 std::vector<uint8_t> raw(raw_stride),bank(size_t(ROWS)*COUNT*stride);
 for(unsigned row=0;row<ROWS*COUNT;++row){
  for(auto& v:raw)v=next(seed)>>24;
  for(size_t block=0;block<raw.size();block+=f.bytes){uint16_t half=uint16_t(0x2000u+((next(seed)>>16)&0x17ff));raw[block]=half&255;raw[block+1]=half>>8;}
  p90::expert_repack(K,raw.data(),bank.data()+row*stride);
 }
 return bank;
}
std::pair<std::vector<uint8_t>,std::vector<uint8_t>> real_bank(const std::string& path){
 std::ifstream f(path,std::ios::binary|std::ios::ate);check(bool(f)&&f.tellg()==std::streamoff(REAL_ROWS*REAL_RAW),"real rows extent: "+path);
 std::vector<uint8_t> raw(REAL_ROWS*REAL_RAW);f.seekg(0);f.read(reinterpret_cast<char*>(raw.data()),raw.size());check(bool(f),"real rows truncated");
 const size_t stride=p90::expert_stride(K);std::vector<uint8_t> w(size_t(ROWS)*COUNT*stride),peer(w.size());
 for(size_t row=0;row<REAL_ROWS;++row){const auto* s=raw.data()+row*REAL_RAW;
  for(unsigned b=0;b<10;++b)check((p49bgemv::load16(s+82*b)&0x7c00)!=0x7c00,"nonfinite real weight scale");
  auto& dest=row<ROWS*COUNT?w:peer;p90::expert_repack(K,s,dest.data()+(row%(ROWS*COUNT))*stride);}
 return {w,peer};
}
bool nan16(uint16_t v){return (v&0x7f80u)==0x7f80u&&(v&0x7fu);}
struct Diff{size_t bytes=0,words=0,nan_words=0,other_bytes=0;};
Diff diff(const std::vector<uint8_t>& a,const std::vector<uint8_t>& b,bool bf16){Diff d;check(a.size()==b.size(),"compared extents");
 if(bf16){for(size_t i=0;i+1<a.size();i+=2){uint16_t x=uint16_t(a[i]|(a[i+1]<<8)),y=uint16_t(b[i]|(b[i+1]<<8));if(x!=y){++d.words;d.bytes+=(a[i]!=b[i])+(a[i+1]!=b[i+1]);if(nan16(x)&&nan16(y))++d.nan_words;else d.other_bytes+=(a[i]!=b[i])+(a[i+1]!=b[i+1]);}}}
 else for(size_t i=0;i<a.size();++i)if(a[i]!=b[i]){++d.bytes;++d.other_bytes;}
 return d;}
}
int main(int argc,char**argv){std::filesystem::path out;std::string real;
 try{
  for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--output"&&i+1<argc)out=argv[++i];else if(k=="--real-rows"&&i+1<argc)real=argv[++i];else throw std::invalid_argument("diet fixture arguments: --output DIR --real-rows DIR");}
  check(!out.empty()&&!real.empty(),"--output and --real-rows required");std::filesystem::create_directories(out);
  Runner r;std::ofstream cases(out/"cases.jsonl");unsigned strata=0,equal=0,payload_rows=0,refusals=0;size_t compared=0;
  const std::string experts="exp-halfcache+down-tile16"; // the record selection's `experts` choice
  struct Bank{std::string name;std::vector<uint8_t> w,peer;unsigned experts;};
  std::vector<Bank> banks;
  {auto [w0,p0]=real_bank(real+"/layer0.bin");banks.push_back({"real-layer0",std::move(w0),std::move(p0),COUNT});
   auto [w24,p24]=real_bank(real+"/layer24.bin");banks.push_back({"real-layer24",std::move(w24),std::move(p24),COUNT});
   banks.push_back({"synthetic",synthetic_bank(0x194u),synthetic_bank(0x194bu),COUNT});}
  for(const auto& bank:banks)for(unsigned scenario=0;scenario<8;++scenario){
   if(bank.name!="synthetic"&&scenario!=0&&scenario!=4&&scenario!=5)continue; // real rows: normal, partial routes and NaN inputs
   const bool nan_stratum=scenario==5||scenario==6;
   auto ac=r.word(scenario==2?0:1),er=r.word(scenario==3?7:0),pos=r.word(0);
   std::vector<iq3::Route> routes(COUNT);for(unsigned j=0;j<COUNT;++j)routes[j]={uint32_t((j*3+1)%COUNT),0,ROWS};
   if(scenario==1)routes[2].expert_id=bank.experts; // invalid expert -> status/error
   if(scenario==4){routes[0].row_count=0;routes[1].row_count=ROWS-2;routes[1].row_begin=1;routes[2].row_begin=ROWS;routes[2].row_count=1;}
   Matrix a{};a.type=T;a.w=r.vec(bank.w);a.x=r.vec(input(scenario,0x5eed+scenario));a.y=r.vec(std::vector<uint16_t>(ROWS*COUNT,0x7e31));a.rows=ROWS;a.columns=K;a.span=ROWS;a.count=COUNT;a.experts=bank.experts;a.routes=r.vec(routes);a.status=r.vec(std::vector<uint32_t>(COUNT,9));a.workspace=r.vec(std::vector<float>(ROWS*COUNT*8,-3));
   auto b=a;b.w=r.vec(bank.peer);b.y=r.vec(std::vector<uint16_t>(ROWS*COUNT,0x7e32));b.status=r.vec(std::vector<uint32_t>(COUNT,8));
   std::vector<Matrix> m{a,b};p39::Bindings controls;controls.active=ac;controls.error=er;controls.position=pos;controls.capacity=4096;
   std::vector<Allocation> watch{a.y,b.y,a.status,b.status,er,ac,pos};const bool bf16[]={true,true,false,false,false,false,false};
   auto initial=r.snapshot(watch);
   r.finish(p49d::expert(r.d,m,p39::Kind::expert_checks,controls,experts).last);auto record=r.snapshot(watch);   // the five-argument record dispatch
   r.restore(watch,initial);r.finish(p49d::expert(r.d,m,p39::Kind::expert_checks,controls,experts,"production").last);auto production=r.snapshot(watch);
   r.restore(watch,initial);r.finish(p49d::expert(r.d,m,p39::Kind::expert_checks,controls,experts,"diet").last);auto diet=r.snapshot(watch);
   check(record==production,"six-argument production differs from the five-argument record dispatch: "+bank.name+" scenario "+std::to_string(scenario));
   Diff total;for(size_t j=0;j<watch.size();++j){auto d=diff(production[j],diet[j],bf16[j]);total.bytes+=d.bytes;total.words+=d.words;total.nan_words+=d.nan_words;total.other_bytes+=d.other_bytes;compared+=production[j].size();}
   check(total.other_bytes==0,"diet value difference: "+bank.name+" scenario "+std::to_string(scenario)+" bytes "+std::to_string(total.other_bytes));
   check(total.bytes==0||nan_stratum,"diet payload-order difference outside a NaN stratum: "+bank.name+" scenario "+std::to_string(scenario));
   const bool bytes_equal=total.bytes==0;equal+=bytes_equal;payload_rows+=!bytes_equal;++strata;
   // status words: the diet must report the same route verdicts; error/active/position untouched identically
   check(production[2]==diet[2]&&production[3]==diet[3]&&production[4]==diet[4]&&production[5]==diet[5]&&production[6]==diet[6],"status/control words differ");
   std::string digest=packet26::hash(diet[0].data(),diet[0].size());
   cases<<"{\"bank\":"<<quote(bank.name)<<",\"scenario\":"<<scenario<<",\"nan_stratum\":"<<(nan_stratum?"true":"false")<<",\"record_equals_production\":true,\"bytes_equal\":"<<(bytes_equal?"true":"false")<<",\"different_bytes\":"<<total.bytes<<",\"different_words\":"<<total.words<<",\"nan_vs_nan_words\":"<<total.nan_words<<",\"other_bytes\":"<<total.other_bytes<<",\"payload_order_only\":"<<((!bytes_equal&&total.other_bytes==0)?"true":"false")<<",\"compared_bytes\":"<<[&]{size_t n=0;for(auto& v:production)n+=v.size();return n;}()<<",\"y_sha256\":"<<quote(digest)<<",\"status\":["<<[&]{std::string s;for(unsigned j=0;j<COUNT;++j){uint32_t v;std::memcpy(&v,diet[2].data()+4*j,4);s+=(j?",":"")+std::to_string(v);}return s;}()<<"]}\n";
   if(scenario==0){ // negatives on the normal stratum: non-halfcache layout and unknown value refuse before any write
    auto before=r.snapshot(watch);bool refused=false;
    try{p49d::expert(r.d,m,p39::Kind::expert_checks,controls,"wide64","diet");}catch(const std::invalid_argument&){refused=true;}
    check(refused&&r.snapshot(watch)==before,"diet on a non-halfcache layout must refuse without writing");++refusals;
    refused=false;try{p49d::expert(r.d,m,p39::Kind::expert_checks,controls,experts,"bogus");}catch(const std::invalid_argument&){refused=true;}
    check(refused&&r.snapshot(watch)==before,"unknown expert_gateup must refuse without writing");++refusals;
   }
   r.clear();
  }
  cases.close();
  std::ofstream receipt(out/"result.json");
  receipt<<"{\"schema\":\"packet194.diet-dispatch-fixture.v1\",\"passed\":true,\"device_executed\":false,\"cpu_only\":true,\"strata\":"<<strata<<",\"byte_equal_strata\":"<<equal<<",\"payload_order_only_strata\":"<<payload_rows<<",\"refusals\":"<<refusals<<",\"compared_bytes\":"<<compared<<",\"dispatch\":\"p49d::expert(experts=exp-halfcache+down-tile16, expert_gateup=production|diet) vs the five-argument record dispatch\",\"real_rows\":"<<quote(real)<<"}\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
