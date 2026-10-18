// Bounded fixtures, no model, backend or GPU linkage.
#include "p67_hc.hpp"
#include "p67_recurrence.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
namespace {
void require(bool ok,const std::string&what){if(!ok)throw std::runtime_error(what);}
uint32_t rnd(uint32_t&s){s=s*1664525+1013904223;return s;}
std::vector<uint16_t> values(size_t n,uint32_t seed){std::vector<uint16_t>v(n);for(auto&x:v)x=iq3::bf16_bits(float(int(rnd(seed)%513)-256)/512.f);return v;}
struct Recorder {
 std::ofstream expected,actual,cases;unsigned count=0;uint64_t bytes=0,chains=0;
 explicit Recorder(const std::filesystem::path&p):expected(p/"expected.bin",std::ios::binary),actual(p/"candidate.bin",std::ios::binary),cases(p/"cases.jsonl"){}
 template<class T>void compare(const T*a,const T*b,size_t n,const std::string&desc){
  size_t nb=n*sizeof(T);expected.write(reinterpret_cast<const char*>(a),nb);actual.write(reinterpret_cast<const char*>(b),nb);bytes+=nb;
  if(std::memcmp(a,b,nb)){size_t at=0;auto x=reinterpret_cast<const uint8_t*>(a),y=reinterpret_cast<const uint8_t*>(b);while(at<nb&&x[at]==y[at])++at;throw std::runtime_error(desc+" mismatch byte="+std::to_string(at)+" expected="+std::to_string(x[at])+" actual="+std::to_string(y[at]));}
 }
 void done(const std::string&site,unsigned scenario,unsigned row){cases<<"{\"site\":\""<<site<<"\",\"scenario\":"<<scenario<<",\"serial_row\":"<<row<<",\"passed\":true}\n";++count;}
};
void hc(Recorder&r,unsigned side,unsigned scenario){
 size_t rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);std::vector<uint8_t>w(10240*rb,0);uint32_t seed=6700+scenario+side*100;
 for(unsigned row=0;row<10240;++row){auto p=w.data()+row*rb;for(unsigned k=0;k<320;++k)p[k]=rnd(seed)>>24;for(unsigned g=0;g<10;++g){float scale=float(1+rnd(seed)%16)/2048.f;std::memcpy(p+320+g*4,&scale,4);}}
 auto act=values(320,seed),norm=values(10240,seed+1);uint32_t active=scenario==1?0:1,error=scenario==2?7:0,position=scenario==3?4096:17;
 if(scenario==4)std::fill(act.begin(),act.end(),0);
 if(scenario==5){act[0]=0x7fc1;act[8]=0xffd5;norm[0]=0x7fc3;}
 if(scenario==6){act[0]=0x7f80;act[8]=0xff80;}
 if(scenario==7){act[0]=1;act[1]=0x8001;act[8]=0x8000;}
 if(scenario==8)for(unsigned k=0;k<320;++k)act[k]=iq3::bf16_bits(k%2?-64.f:64.f);
 std::vector<uint16_t>g0(10240,0x3c31),g1=g0,m0(2560,0x3c32),m1=m0;
 p60::Bound a{};a.gate_w=w.data();a.act=act.data();a.norm=norm.data();a.gate=g0.data();a.mix=m0.data();a.error=&error;a.active=&active;a.position=&position;a.capacity=4096;
 auto b=a;b.gate=g1.data();b.mix=m1.data();p60::host_gate_mix(a);p67hc::host(b);
 r.compare(g0.data(),g1.data(),g0.size(),"HC gate");r.compare(m0.data(),m1.data(),m0.size(),"HC mix");
 // Validate the precise FP32 leaves, before BF16 can hide a reassociation.
 for(unsigned row=0;row<32;++row)for(unsigned physical=0;physical<8;++physical){
  auto c=p49dvirtual::dense_chains<iq3::Type::Q8_0,320,4>(w.data()+row*rb,act.data(),0,320,physical);
  for(unsigned v=0;v<4;++v){float e=p49c::dense_lane<iq3::Type::Q8_0,320>(w.data()+row*rb,act.data(),0,320,physical*4+v);r.compare(&e,&c[v],1,"HC FP32 leaf");++r.chains;}
 }
 r.done(side?"hc.f.gate":"hc.a.gate",scenario,0);
}
struct RecData {
 std::vector<uint16_t>conv,a,b,state,y,nextstate,gainbf;
 bool distinct=false,bf=false;
 std::vector<float>decay,gain;int32_t error=0,position=17,active=1;
 RecData(unsigned scenario):conv(values(10240,scenario+700)),a(values(48,2)),b(values(48,3)),state(values(6144*128,scenario+71)),y(6144,0x3c31),decay(48,-0.125f),gain(48,0.03125f){
  if(scenario==1)active=0;if(scenario==2)error=7;if(scenario==3)position=4096;if(scenario==4)std::fill(conv.begin(),conv.end(),0);
  if(scenario==5){conv[0]=0x7fc1;conv[8]=0xffd5;state[100]=0x7fc3;}
  if(scenario==6){conv[0]=0x7f80;conv[8]=0xff80;}
  if(scenario==7){conv[0]=1;state[1]=0x8001;conv[8]=0x8000;}
  if(scenario==8)position=-1;
 }
 ng::Args args(){ng::Args p{};p.p.fill(&error);p.p[0]=conv.data();p.p[1]=a.data();p.p[2]=b.data();p.p[3]=decay.data();p.p[4]=bf?static_cast<void*>(gainbf.data()):static_cast<void*>(gain.data());p.p[5]=state.data();p.p[6]=y.data();p.p[7]=distinct?nextstate.data():state.data();p.p[15]=&error;p.p[17]=&position;p.p[18]=&active;return p;}
};
void recurrence(Recorder&r,unsigned layout,unsigned scenario,bool bf=false,bool distinct=false){
 ng::Shape s{};s.op=ng::gdn;s.capacity=4096;s.tokens=1;s.flags=2|(bf?0:8)|(layout?4:0);RecData a(scenario);
 a.bf=bf;a.distinct=distinct;a.gainbf.assign(48,iq3::bf16_bits(0.03125f));a.nextstate=a.state;if(scenario==9)a.position=4095;RecData b=a;
 std::vector<float>scratch(p67rec::scratch_bytes/4+16,-123.25f);
 for(unsigned row=0;row<2;++row){
  if(row&&scenario!=3&&scenario!=8){++a.position;++b.position;a.conv=values(10240,scenario+200);b.conv=a.conv;}
  p49drec::recurrence_host<4>(s,a.args());p67rec::host(s,b.args(),scratch.data());
  r.compare(a.state.data(),b.state.data(),a.state.size(),"recurrence state");r.compare(a.y.data(),b.y.data(),a.y.size(),"recurrence output");
  if(distinct){r.compare(a.nextstate.data(),b.nextstate.data(),a.nextstate.size(),"recurrence distinct bank");a.state=a.nextstate;b.state=b.nextstate;}
  r.compare(&a.error,&b.error,1,"recurrence sticky error");r.compare(&a.position,&b.position,1,"recurrence position");r.compare(&a.active,&b.active,1,"recurrence active");
  require(std::all_of(scratch.end()-16,scratch.end(),[](float f){return f==-123.25f;}),"head scratch guard");
  for(unsigned h=0;h<48;++h)require(scratch[h*260+258]==-123.25f&&scratch[h*260+259]==-123.25f,"head scratch padding");
  r.done(std::string(layout?"gdn.recurrence.packed":"gdn.recurrence.grouped")+(bf?".bf16":".f32")+(distinct?".distinct":".alias"),scenario,row);
 }
}
}
int main(int argc,char**argv){try{
 require(argc==2,"output path required");std::filesystem::path out=argv[1];std::filesystem::create_directories(out);Recorder r(out);
 for(unsigned scenario=0;scenario<9;++scenario){hc(r,0,scenario);hc(r,1,scenario);recurrence(r,0,scenario);recurrence(r,1,scenario);}
 recurrence(r,1,9,true,false);recurrence(r,1,0,false,true);recurrence(r,1,0,true,true);
 {RecData a(0);ng::Shape s{};s.tokens=2;std::vector<float>tmp(p67rec::scratch_bytes/4);bool refused=false;try{p67rec::host(s,a.args(),tmp.data());}catch(const std::invalid_argument&){refused=true;}require(refused,"multi-token call refused");}
 r.expected.close();r.actual.close();r.cases.close();require(r.count==60,"fixture coverage");
 std::ofstream(out/"native.json")<<"{\"schema\":\"packet67.cpu-byte-identity.v1\",\"passed\":true,\"device_executed\":false,\"cases\":"<<r.count<<",\"raw_fp32_chain_checks\":"<<r.chains<<",\"compared_bytes\":"<<r.bytes<<",\"serial_m2_state_carried\":true,\"nan_tolerance\":false}\n";
 std::cout<<r.count<<" cases PASS; "<<r.bytes<<" bytes compared\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
