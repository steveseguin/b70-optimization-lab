#define OWN_RT_HOST_ONLY
#include "block.hpp"
#include <iostream>
#include <cstring>
#include <bit>
#include <vector>
using namespace ownrt;
static size_t checks=0,refusals=0;
static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);++checks;}
static void same(float a,float b,const char*s){need(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b),s);}
static void halfset(uint8_t*b,uint16_t h){b[0]=uint8_t(h);b[1]=uint8_t(h>>8);}
template<unsigned T>void decoder(){
 constexpr size_t bytes=T==12?144:T==13?176:136;std::array<uint8_t,bytes>b{};
 const uint16_t halves[]{0,0x8000,1,0x8001,0x03ff,0x0400,0x3c00,0xbc00,0x7bff,0x7c00,0xfc00,0x7e11,0xfe11,0x7c01,0xfc01};
 auto compare=[&](){const float d=iq3::half(iq3::u16(b.data()));float dm=0;if constexpr(T!=23)dm=iq3::half(iq3::u16(b.data()+2));for(unsigned g=0;g<8;++g)for(unsigned lane=0;lane<32;++lane)same(denseblock::block_element<T>(b.data(),d,dm,g,lane),gsq::element_unchecked(T,b.data(),32*g+lane),"hoisted exact decoder bits");};
 for(size_t i=0;i<bytes;++i)b[i]=uint8_t(85+i*37);
 // Independent d/dmin combinations: signed zero/subnormal/finite/inf/qNaN/sNaN.
 for(auto d:halves)for(auto dm:halves){halfset(b.data(),d);if constexpr(T!=23)halfset(b.data()+2,dm);else {b[2]=uint8_t(dm);b[3]=uint8_t(dm>>8);}compare();}
 // Every six-bit scale/minimum and every low/high code at every group/lane.
 for(unsigned v=0;v<64;++v){
  for(size_t i=0;i<bytes;++i)b[i]=uint8_t(i*17+v*31);
  halfset(b.data(),0x3000);if constexpr(T!=23){halfset(b.data()+2,0x2c00);auto*s=b.data()+4;for(unsigned i=0;i<4;++i){s[i]=uint8_t(v|((v>>4)<<6));s[i+4]=uint8_t((63-v)|(((63-v)>>4)<<6));s[i+8]=uint8_t((v&15)|(((63-v)&15)<<4));}}
  else {b[2]=b[3]=uint8_t(((v>>4)&3)*85);for(unsigned i=4;i<8;++i)b[i]=uint8_t((v&15)*17);}
  compare();
 }
 // Ordered lane chains/full adjacent tree, independently populated ten blocks.
 std::vector<uint8_t>w(bytes*10);std::array<uint16_t,2560>x{};for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%31)-15)/32);
 gsqn::Shape shape{1,2560,bytes*10,1,1,false,false};gsqn::Bound bound{shape,w.data(),x.data(),nullptr,nullptr,nullptr};iq3::Route route{0,0,1};
 for(size_t h=0;h<std::size(halves);++h){for(size_t block=0;block<10;++block){for(size_t i=0;i<bytes;++i)w[block*bytes+i]=uint8_t(block*71+i*19);halfset(w.data()+block*bytes,halves[h]);if constexpr(T!=23)halfset(w.data()+block*bytes+2,halves[(h+block+3)%std::size(halves)]);}
  float a[32],c[32];for(unsigned lane=0;lane<32;++lane){a[lane]=gsqn::lane_sum<T>(bound,route,0,0,lane);c[lane]=denseblock::block_lane_sum<T>(bound,route,0,0,lane);same(a[lane],c[lane],"lane FP32 exact exceptional chain");}same(iq3::tree32(a),iq3::tree32(c),"same adjacent tree bits");need(iq3::bf16_bits(iq3::tree32(a))==iq3::bf16_bits(iq3::tree32(c)),"same final BF16 bits");
 }
}
struct Fixture {
 Host*host=new Host;Device d{std::unique_ptr<Backend>(host)};integrated::Matrix m{};Allocation control,decoy,extra;unsigned serial=0;bool closed=false;
 const denseblock::Site&s;
 Allocation alloc(size_t n){auto id=d.arena.allocate("card0:dense-block-"+std::to_string(serial++),n,Memory::device,Category::scratch,Lifetime::transaction);std::memset(d.arena.row(id).pointer,0xa5,n);return id;}
 template<class T>T*ptr(Allocation id){return static_cast<T*>(d.arena.row(id).pointer);}
 std::vector<uint8_t>bytes(Allocation id){auto&r=d.arena.row(id);auto*p=static_cast<uint8_t*>(r.pointer);return {p,p+r.bytes};}
 Fixture(const denseblock::Site&site):s(site){m.type=static_cast<iq3::Type>(s.type);m.rows=s.rows;m.columns=2560;m.count=m.experts=1;m.span=m.rows;m.w=alloc(s.bytes);m.x=alloc(5120);m.y=alloc(s.rows*2);control=alloc(s.rows*2);decoy=alloc(s.rows*2);extra=alloc(4);auto*w=ptr<uint8_t>(m.w);for(size_t i=0;i<s.bytes;++i)w[i]=uint8_t(i*37+11);auto f=gsq::layout(s.type);for(size_t i=0;i<s.bytes;i+=f.bytes){halfset(w+i,0x3000);if(s.type!=23)halfset(w+i+2,0x2800);}for(size_t i=0;i<2560;++i)ptr<uint16_t>(m.x)[i]=iq3::bf16_bits(float(int(i%19)-9)/16);}
 void done(Event e){need(d.wait(e,std::chrono::milliseconds(100))&&d.complete(e)&&d.in_flight()==0,"Host marker completion");d.retire_completed_events();}
 void compare(){auto original=m;original.y=control;auto e=gsqn::submit(d,original,gsqn::InputMode::shared,gsqn::Storage::packed_direct);done(e.last);need(bytes(control)==bytes(m.y),"full selected-shaped original/candidate BF16 output");}
 std::string close(){auto r=d.shutdown(std::chrono::milliseconds(100));need(r.safe_to_exit&&r.exit_code==0&&r.in_flight==0&&r.live_bytes==0,"safe Host close");closed=true;return r.json();}
 ~Fixture(){if(!closed){auto r=d.shutdown(std::chrono::milliseconds(100));if(!r.safe_to_exit)std::abort();}}
};
int main(){try{
 decoder<12>();decoder<13>();decoder<23>();
 for(const auto&s:denseblock::sites){integrated::Matrix m{};m.type=static_cast<iq3::Type>(s.type);m.rows=s.rows;m.columns=2560;m.count=m.experts=1;m.span=m.rows;denseblock::policy(m,s.label,s.weight,gsqn::InputMode::shared);++checks;}
 std::vector<std::string>owners;
 for(unsigned t:{12u,13u,23u}){const denseblock::Site*site=nullptr;for(const auto&s:denseblock::sites)if(s.type==t&&(!site||s.rows<site->rows))site=&s;need(site!=nullptr,"selected type present");Fixture f(*site);auto before=f.bytes(f.m.y),decoy=f.bytes(f.decoy);std::vector<PreparedCompute>cmd;f.d.begin_capture(cmd);auto caller=f.m;denseblock::submit(f.d,caller,site->label,site->weight,gsqn::InputMode::shared);f.d.end_capture();caller.w=0;caller.y=f.decoy;need(cmd.size()==1&&f.bytes(f.m.y)==before&&f.d.in_flight()==0,"capture nonexecution");f.done(f.d.issue(cmd[0]));f.compare();need(f.bytes(f.decoy)==decoy,"capture retained bindings");auto first=f.bytes(f.m.y);for(size_t i=0;i<2560;++i)f.ptr<uint16_t>(f.m.x)[i]=iq3::bf16_bits(float(i%7+1)/8);f.done(f.d.issue(cmd[0]));f.compare();need(first!=f.bytes(f.m.y),"live input changed actual result");auto second=f.bytes(f.m.y);auto fmt=gsq::layout(t);for(size_t i=0;i<site->bytes;i+=fmt.bytes)halfset(f.ptr<uint8_t>(f.m.w)+i,0x3800);f.done(f.d.issue(cmd[0]));f.compare();need(second!=f.bytes(f.m.y),"live weights changed actual result");
  auto refuse=[&](auto action){bool caught=false;auto y=f.bytes(f.m.y);try{action();}catch(const std::exception&){caught=true;}need(caught&&y==f.bytes(f.m.y),"strict facade refusal before writes");++refusals;};
  auto call=[&](const integrated::Matrix&m){denseblock::submit(f.d,m,site->label,site->weight,gsqn::InputMode::shared);};auto bad=f.m;
  bad.type=iq3::Type::BF16;refuse([&]{call(bad);});bad=f.m;bad.columns=512;refuse([&]{call(bad);});bad=f.m;bad.rows--;refuse([&]{call(bad);});bad=f.m;bad.span=0;refuse([&]{call(bad);});bad=f.m;bad.count=2;refuse([&]{call(bad);});bad=f.m;bad.experts=2;refuse([&]{call(bad);});bad=f.m;bad.routes=f.extra;refuse([&]{call(bad);});bad=f.m;bad.status=f.extra;refuse([&]{call(bad);});bad=f.m;bad.fp32=f.extra;refuse([&]{call(bad);});bad=f.m;bad.y=bad.x;refuse([&]{call(bad);});bad=f.m;bad.w=f.extra;refuse([&]{call(bad);});
  refuse([&]{denseblock::submit(f.d,f.m,site->label,"wrong.weight",gsqn::InputMode::shared);});refuse([&]{denseblock::submit(f.d,f.m,site->label,site->weight,gsqn::InputMode::per_slot);});f.d.arena.release(f.extra);refuse([&]{f.d.issue(cmd[0]);});owners.push_back(f.close());
 }
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"refusals\":"<<refusals<<",\"site_count\":116,\"device_executed\":false,\"scope\":\"exact decoder/ordered lane/tree and actual Host captured facade; simulated markers\",\"owners\":[";for(size_t i=0;i<owners.size();++i)std::cout<<(i?",":"")<<owners[i];std::cout<<"]}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
