// Packet183 S1 byte gate (CPU only; host build, -DOWN_RT_HOST_ONLY).
//
// 1. Lane level, compiled into this TU by each compiler: every lane of every
//    split part of every synthetic row, p183 metadata lanes vs the production
//    lanes (p33::dense_lane, p49c::dense_lane, p49dvirtual::dense_chains), bit
//    for bit, plus odd (non-256) begins for the p33 fallback.
// 2. Submission level, through the linked production objects: p33::submit
//    ("p33.dense.segment") vs p183::segment, p49c::dense_submit
//    (attention_combine) vs p183::attention, p49d::small vs p183::small on the
//    same buffers (restored between runs), eight input/control scenarios, every
//    watched buffer compared byte for byte; refused shapes stay refused.
// 3. Census: synthetic weights pass; infinite/NaN d and a flipped stored word
//    are counted; a non-256 K is refused.
// Weights are GGUF Q6_K blocks with random codes/sub-scales and d drawn from a
// set that covers normal, subnormal, signed-zero, unit and max fp16 values,
// expanded by the production loader (iq3::expanded::expand).
#include "s1_submit.hpp"
#include "p33_submit.hpp"
#include "p49c_submit.hpp"
#include "p49d_submit.hpp"
#include "small_gemv.hpp"
#include "failure.hpp"
#include <array>
#include <bit>
#include <chrono>
#include <fstream>
#include <cstring>
#include <iostream>
#include <sstream>
#include <vector>
namespace {
using namespace ownrt;
using namespace integrated;
void check(bool ok,const std::string& what){if(!ok)throw std::runtime_error(what);}
struct Cpu final:Backend {
 std::string identity()const override{return "CPU packet183 S1 byte fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void* p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void* dst,const void* src,size_t n,std::span<const Event>)override{std::memcpy(dst,src,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void*const> p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}
 bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;size_t serial=0;
 Runner():device(std::make_unique<Cpu>()),copy(device){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("p183-s1-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){check(device.wait(e,std::chrono::seconds(600)),"p183 fixture deadline");}
 Allocation upload(const void* src,size_t bytes){auto host=alloc(bytes,Memory::pinned),out=alloc(bytes);std::memcpy(device.arena.row(host).pointer,src,bytes);finish(copy.copy(out,0,host,0,bytes,{}));return out;}
 std::vector<uint8_t> read(Allocation id,size_t n){auto h=alloc(n,Memory::pinned);finish(copy.copy(h,0,id,0,n,{}));auto p=static_cast<const uint8_t*>(device.arena.row(h).pointer);return {p,p+n};}
 void restore(Allocation id,const std::vector<uint8_t>& v){auto h=alloc(v.size(),Memory::pinned);std::memcpy(device.arena.row(h).pointer,v.data(),v.size());finish(copy.copy(id,0,h,0,v.size(),{}));}
 void clear(){device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();}
};
struct Rng {uint32_t s;uint32_t next(){s=s*1664525u+1013904223u;return s;} uint8_t byte(){return uint8_t(next()>>24);}};
const uint16_t special_d[]={0x0000,0x8000,0x0001,0x8001,0x03ff,0x83ff,0x0400,0x7bff,0xfbff,0x3c00,0xbc00,0x1234,0x2e66};
// GGUF Q6_K block: ql[128] qh[64] scales[16] (int8) d (fp16).
std::vector<uint8_t> q6_rows(unsigned rows,unsigned K,uint32_t seed,bool forced_extremes){
 Rng r{seed};const unsigned blocks=K/256;std::vector<uint8_t> packed(size_t(rows)*blocks*210);
 for(size_t b=0;b<size_t(rows)*blocks;++b){uint8_t* q=packed.data()+b*210;for(unsigned i=0;i<208;++i)q[i]=r.byte();
  if(forced_extremes&&b%7==0){q[192]=0x80;q[193]=0x7f;q[194]=0x00;q[195]=0xff;q[196]=0x01;}
  uint16_t d;const uint32_t pick=r.next()%4;
  if(pick==0)d=special_d[(r.next()>>8)%(sizeof(special_d)/2)];
  else {uint32_t e=1+(r.next()>>8)%30,m=(r.next()>>8)&1023,s=(r.next()>>9)&1;d=uint16_t((s<<15)|(e<<10)|m);}
  q[208]=uint8_t(d);q[209]=uint8_t(d>>8);}
 return iq3::expanded::expand(iq3::Type::Q6_K,packed.data(),packed.size(),K);
}
std::vector<uint16_t> input(unsigned K,unsigned scenario,unsigned token){
 std::vector<uint16_t> x(K);for(unsigned j=0;j<K;++j)x[j]=iq3::bf16_bits(float(int((j*13+token*7)%257)-128)/64.f);
 if(scenario==3)for(auto& v:x)v=0;
 if(scenario==4)for(unsigned j=0;j<K;j+=3)x[j]=iq3::bf16_bits(-float(j%97)*0.75f);
 if(scenario==5)x[0]=0x7fc1;if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}if(scenario==7){x[0]=1;x[1]=0x8001;}
 return x;
}
uint64_t lane_checks=0,submission_checks=0;
template<unsigned K> void lanes(const std::vector<uint8_t>& w,unsigned rows,uint32_t seed){
 const size_t rb=iq3::expanded::row_bytes(iq3::Type::Q6_K,K);
 for(unsigned scenario:{0u,4u,5u,7u})for(unsigned row=0;row<rows;++row){auto x=input(K,scenario,row+seed);const uint8_t* r=w.data()+row*rb;
  for(unsigned split:{1u,4u})for(unsigned part=0;part<split;++part){auto b=iq3::kopt2::bounds(K,part,split);
   for(unsigned lane=0;lane<32;++lane){
    float a=p33::dense_lane<iq3::Type::Q6_K,K>(r,x.data(),b.first,b.second,lane),m=p183::p33_lane<K>(r,x.data(),b.first,b.second,lane);
    check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(m),"p33 lane K="+std::to_string(K)+" row="+std::to_string(row)+" lane="+std::to_string(lane));
    float c=p49c::dense_lane<iq3::Type::Q6_K,K>(r,x.data(),b.first,b.second,lane),n=p183::p49c_lane<K>(r,x.data(),b.first,b.second,lane);
    check(std::bit_cast<uint32_t>(c)==std::bit_cast<uint32_t>(n),"p49c lane K="+std::to_string(K)+" row="+std::to_string(row));
    lane_checks+=2;}
   if constexpr(K==2560)for(unsigned physical=0;physical<8;++physical){
    auto s=p49dvirtual::dense_chains<iq3::Type::Q6_K,K,4>(r,x.data(),b.first,b.second,physical),t=p183::small_chains<K,4>(r,x.data(),b.first,b.second,physical);
    for(unsigned v=0;v<4;++v)check(std::bit_cast<uint32_t>(s[v])==std::bit_cast<uint32_t>(t[v]),"small chain row="+std::to_string(row));lane_checks+=4;}
  }
  if(scenario==0)for(unsigned begin:{8u,264u,520u})for(unsigned lane=0;lane<32;++lane){ // odd begins: packet28 fallback
   float a=p33::dense_lane<iq3::Type::Q6_K,K>(r,x.data(),begin,K,lane),m=p183::p33_lane<K>(r,x.data(),begin,K,lane);
   check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(m),"p33 odd-begin lane");++lane_checks;}
 }
}
uint64_t mutation_checks=0;
// Mutation proof that the gate is not blind: words-zeroed weights must change
// the production result and leave S1's unchanged; perturbed metadata sub-scales
// must change S1's result and leave production's unchanged.
std::vector<uint8_t> zero_words(std::vector<uint8_t> w,unsigned rows,unsigned K){const size_t rb=iq3::expanded::row_bytes(iq3::Type::Q6_K,K);for(unsigned r=0;r<rows;++r)std::memset(w.data()+r*rb+K,0,4*(K/16));return w;}
std::vector<uint8_t> bump_meta(std::vector<uint8_t> w,unsigned rows,unsigned K){const size_t rb=iq3::expanded::row_bytes(iq3::Type::Q6_K,K);for(unsigned r=0;r<rows;++r)for(unsigned b=0;b<K/256;++b){uint8_t* m=w.data()+r*rb+K+4*(K/16)+18*b;if(iq3::u16(m)==0||iq3::u16(m)==0x8000){m[0]=0x00;m[1]=0x3c;}for(unsigned g=0;g<16;++g)m[2+g]=uint8_t(m[2+g]==127?126:m[2+g]+1);}return w;}
std::ostringstream cases;
template<unsigned K> void segment_case(Runner& run,unsigned rows,uint32_t seed){
 auto w=q6_rows(rows,K,seed,true);auto census=p183::census_q6(w.data(),rows,K);check(!census.nonfinite&&!census.mismatch&&census.groups==uint64_t(rows)*K/16,"segment census");
 lanes<K>(w,std::min(rows,K==2560?64u:16u),seed);
 for(unsigned variant:{6u,7u})for(unsigned scenario=0;scenario<8;++scenario){
  auto x=input(K,scenario,seed);std::vector<uint16_t> y(rows,0x7e31);std::vector<float> scratch(size_t(rows)*8,-7.25f);
  Matrix m{};m.type=iq3::Type::Q6_K;m.w=run.upload(w.data(),w.size());m.x=run.upload(x.data(),x.size()*2);m.y=run.upload(y.data(),y.size()*2);
  m.rows=rows;m.columns=K;m.span=rows;m.count=m.experts=1;m.workspace=run.upload(scratch.data(),scratch.size()*4);
  const std::array watched{m.y,m.workspace};std::vector<std::vector<uint8_t>> initial,expected;
  for(auto id:watched)initial.push_back(run.read(id,run.device.arena.row(id).bytes));
  auto base=p33::submit(run.device,{m},"p33.dense.segment",false,variant);run.finish(base.last);
  for(auto id:watched)expected.push_back(run.read(id,run.device.arena.row(id).bytes));
  for(size_t j=0;j<watched.size();++j)run.restore(watched[j],initial[j]);
  auto s1=p183::segment(run.device,{m},false,variant);run.finish(s1.last);check(s1.passes==base.passes,"segment pass count");
  for(size_t j=0;j<watched.size();++j)check(run.read(watched[j],expected[j].size())==expected[j],"segment bytes K="+std::to_string(K)+" v="+std::to_string(variant)+" scenario="+std::to_string(scenario)+" buffer="+std::to_string(j));
  if(scenario==0){
   for(unsigned kind=0;kind<2;++kind){auto mw=kind?bump_meta(w,rows,K):zero_words(w,rows,K);auto mm=m;mm.w=run.upload(mw.data(),mw.size());
    for(size_t j=0;j<watched.size();++j)run.restore(watched[j],initial[j]);run.finish(p33::submit(run.device,{mm},"p33.dense.segment",false,variant).last);const bool prod_same=run.read(m.y,expected[0].size())==expected[0];
    for(size_t j=0;j<watched.size();++j)run.restore(watched[j],initial[j]);run.finish(p183::segment(run.device,{mm},false,variant).last);const bool s1_same=run.read(m.y,expected[0].size())==expected[0];
    check(kind?(prod_same&&!s1_same):(!prod_same&&s1_same),"segment mutation proof kind="+std::to_string(kind));++mutation_checks;}
  }
  auto bad=m;bad.columns=K+256;bool refused=false;try{p183::segment(run.device,{bad},false,variant);}catch(const std::invalid_argument&){refused=true;}check(refused,"segment bad shape refusal");
  refused=false;try{p183::segment(run.device,{m},false,2);}catch(const std::invalid_argument&){refused=true;}check(refused,"segment non-expanded variant refusal");
  cases<<"{\"family\":\"p33.dense.segment\",\"K\":"<<K<<",\"rows\":"<<rows<<",\"variant\":"<<variant<<",\"scenario\":"<<scenario<<",\"passed\":true}\n";
  ++submission_checks;run.clear();
 }
}
void attention_case(Runner& run){
 constexpr unsigned K=6144,Rows=2560;auto w=q6_rows(Rows,K,0x183a,true);
 auto census=p183::census_q6(w.data(),Rows,K);check(!census.nonfinite&&!census.mismatch,"attention census");
 for(unsigned batch:{1u,2u})for(unsigned scenario=0;scenario<8;++scenario)for(unsigned token=0;token<batch;++token){
  auto x=input(K,scenario,token);
  uint32_t active=scenario==1?0:1,error=scenario==2?7:0,position=scenario==3?4096:scenario==4?0xffffffff:token;
  std::vector<uint16_t>y(Rows,0x7e31),out(Rows,0x7e33),streams(Rows*4,0x3d80);std::array<uint16_t,4>inject{0x3f00,0xbe80,0x3e00,0xbf00};std::vector<float>scratch(Rows*8,-7.25f);
  Matrix m{};m.type=iq3::Type::Q6_K;m.w=run.upload(w.data(),w.size());m.x=run.upload(x.data(),x.size()*2);m.y=run.upload(y.data(),y.size()*2);m.rows=Rows;m.columns=K;m.span=Rows;m.count=m.experts=1;m.workspace=run.upload(scratch.data(),scratch.size()*4);
  p39::Bindings b;b.error=run.upload(&error,4);b.active=run.upload(&active,4);b.position=run.upload(&position,4);b.capacity=4096;b.out=run.upload(out.data(),out.size()*2);b.streams=run.upload(streams.data(),streams.size()*2);b.inject=run.upload(inject.data(),8);
  const std::array watched{m.y,b.out,b.streams,m.workspace,b.error,b.active,b.position};std::vector<std::vector<uint8_t>> initial,expected;
  for(auto id:watched)initial.push_back(run.read(id,run.device.arena.row(id).bytes));
  auto base=p49c::dense_submit(run.device,m,p39::Kind::attention_combine,b);run.finish(base.last);
  for(auto id:watched)expected.push_back(run.read(id,run.device.arena.row(id).bytes));
  for(size_t j=0;j<watched.size();++j)run.restore(watched[j],initial[j]);
  auto s1=p183::attention(run.device,m,b);run.finish(s1.last);check(s1.passes==base.passes,"attention pass count");
  for(size_t j=0;j<watched.size();++j)check(run.read(watched[j],expected[j].size())==expected[j],"attention bytes scenario="+std::to_string(scenario)+" buffer="+std::to_string(j));
  if(scenario==0&&token==0){
   for(unsigned kind=0;kind<2;++kind){auto mw=kind?bump_meta(w,Rows,K):zero_words(w,Rows,K);auto mm=m;mm.w=run.upload(mw.data(),mw.size());
    for(size_t j=0;j<watched.size();++j)run.restore(watched[j],initial[j]);run.finish(p49c::dense_submit(run.device,mm,p39::Kind::attention_combine,b).last);const bool prod_same=run.read(m.y,expected[0].size())==expected[0];
    for(size_t j=0;j<watched.size();++j)run.restore(watched[j],initial[j]);run.finish(p183::attention(run.device,mm,b).last);const bool s1_same=run.read(m.y,expected[0].size())==expected[0];
    check(kind?(prod_same&&!s1_same):(!prod_same&&s1_same),"attention mutation proof kind="+std::to_string(kind));++mutation_checks;}
  }
  auto bad=m;bad.columns=2560;bool refused=false;try{p183::attention(run.device,bad,b);}catch(const std::invalid_argument&){refused=true;}check(refused,"attention bad shape refusal");
  cases<<"{\"family\":\"p49c.attention_combine\",\"K\":6144,\"rows\":2560,\"batch_rows\":"<<batch<<",\"row\":"<<token<<",\"scenario\":"<<scenario<<",\"passed\":true}\n";
  ++submission_checks;run.clear();
 }
}
void small_case(Runner& run){
 const auto shapes=packet27::small::shapes("small.ffn.q6");check(shapes.size()==4,"small shapes");
 for(unsigned scenario=0;scenario<8;++scenario){
  std::vector<Matrix> ms(4);std::vector<unsigned> variants(4);std::vector<std::vector<uint8_t>> weights(4);std::vector<Allocation> ys;
  auto x=input(2560,scenario,scenario);Rng r{0x5a11u+scenario};Allocation xid=run.upload(x.data(),x.size()*2);
  for(unsigned i=0;i<4;++i){const auto& e=shapes[i];variants[i]=e.variant;
   if(e.type==iq3::Type::Q6_K){weights[i]=q6_rows(e.rows,e.columns,0x5a00u+scenario*4+i,true);auto c=p183::census_q6(weights[i].data(),e.rows,e.columns);check(!c.nonfinite&&!c.mismatch,"small census");}
   else {check(e.type==iq3::Type::F32,"small F32 member");weights[i].resize(size_t(e.rows)*integrated::arithmetic::row_bytes(e.type,e.columns,e.variant));for(size_t k=0;k<weights[i].size();k+=4){float f=float(int(r.next()%2001)-1000)/4096.f;std::memcpy(weights[i].data()+k,&f,4);}}
   std::vector<uint16_t> y(e.rows,0x7e31);
   Matrix& m=ms[i];m.type=e.type;m.w=run.upload(weights[i].data(),weights[i].size());m.x=xid;m.y=run.upload(y.data(),y.size()*2);m.rows=e.rows;m.columns=e.columns;m.span=e.rows;m.count=m.experts=1;ys.push_back(m.y);}
  std::vector<std::vector<uint8_t>> initial,expected;for(auto id:ys)initial.push_back(run.read(id,run.device.arena.row(id).bytes));
  auto base=p49d::small(run.device,"small.ffn.q6",ms,variants);run.finish(base.last);
  for(auto id:ys)expected.push_back(run.read(id,run.device.arena.row(id).bytes));
  for(size_t j=0;j<ys.size();++j)run.restore(ys[j],initial[j]);
  auto s1=p183::small(run.device,"small.ffn.q6",ms,variants);run.finish(s1.last);
  for(size_t j=0;j<ys.size();++j)check(run.read(ys[j],expected[j].size())==expected[j],"small bytes scenario="+std::to_string(scenario)+" member="+std::to_string(j));
  if(scenario==0){
   for(unsigned kind=0;kind<2;++kind){auto mm=ms;for(unsigned i:{1u,2u}){auto mw=kind?bump_meta(weights[i],ms[i].rows,2560):zero_words(weights[i],ms[i].rows,2560);mm[i].w=run.upload(mw.data(),mw.size());}
    for(size_t j=0;j<ys.size();++j)run.restore(ys[j],initial[j]);run.finish(p49d::small(run.device,"small.ffn.q6",mm,variants).last);bool prod_same=true,s1_same=true;for(unsigned j:{1u,2u})prod_same=prod_same&&run.read(ys[j],expected[j].size())==expected[j];
    for(size_t j=0;j<ys.size();++j)run.restore(ys[j],initial[j]);run.finish(p183::small(run.device,"small.ffn.q6",mm,variants).last);for(unsigned j:{1u,2u})s1_same=s1_same&&run.read(ys[j],expected[j].size())==expected[j];
    check(kind?(prod_same&&!s1_same):(!prod_same&&s1_same),"small mutation proof kind="+std::to_string(kind));++mutation_checks;}
  }
  bool refused=false;try{p183::small(run.device,"small.ffn.q8",ms,variants);}catch(const std::invalid_argument&){refused=true;}check(refused,"small wrong tuple refusal");
  cases<<"{\"family\":\"p49d.small.ffn.q6\",\"scenario\":"<<scenario<<",\"passed\":true}\n";
  ++submission_checks;run.clear();
 }
}
std::string census_negatives(){
 constexpr unsigned K=2560;std::ostringstream o;
 auto w=q6_rows(4,K,0xcafe,false);auto good=p183::census_q6(w.data(),4,K);check(!good.nonfinite&&!good.mismatch,"census clean");
 std::vector<uint8_t> packed(4*10*210);Rng r{0xbeef};for(auto& v:packed)v=r.byte();for(size_t b=0;b<40;++b){packed[b*210+208]=0x00;packed[b*210+209]=0x3c;}
 packed[3*210+208]=0x00;packed[3*210+209]=0x7c; // +inf d
 packed[17*210+208]=0x00;packed[17*210+209]=0x7e; // NaN d
 auto e=iq3::expanded::expand(iq3::Type::Q6_K,packed.data(),packed.size(),K);auto bad=p183::census_q6(e.data(),4,K);
 check(bad.nonfinite==2,"census counts both non-finite d");
 auto flip=w;flip[K+4*5]^=1;auto mis=p183::census_q6(flip.data(),4,K);check(mis.mismatch==1&&!mis.nonfinite,"census counts a flipped stored word");
 bool refused=false;try{p183::census_q6(w.data(),1,2560+32);}catch(const std::invalid_argument&){refused=true;}check(refused,"census refuses non-256 K");
 o<<"{\"clean_groups\":"<<good.groups<<",\"nonfinite_detected\":"<<bad.nonfinite<<",\"nonfinite_word_mismatches\":"<<bad.mismatch<<",\"flipped_word_mismatches\":"<<mis.mismatch<<",\"bad_geometry_refused\":true}";
 return o.str();
}
} // namespace
int main(int argc,char** argv){
 try{
  check(argc==2,"usage: s1-bytes OUTPUT_CASES");
  Runner run;
  segment_case<2560>(run,640,0x2560);
  segment_case<6144>(run,256,0x6144);
  segment_case<10240>(run,96,0x10240);
  attention_case(run);
  small_case(run);
  const auto negatives=census_negatives();
  std::ofstream(argv[1])<<cases.str();
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"lane_checks\":"<<lane_checks<<",\"submission_checks\":"<<submission_checks<<",\"mutation_checks\":"<<mutation_checks<<",\"census_negatives\":"<<negatives<<"}"<<std::endl;
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
}
