// Full 48-head state comparisons; no backend, model or device is created.
#include "p113_recurrence.hpp"
#include "p82b_recurrence.hpp"
#include "failure.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
namespace {
void check(bool x,const std::string&s){if(!x)throw std::runtime_error(s);}
struct Data {
 std::vector<uint16_t> qkv,gate,beta,input,state,y;
 std::vector<float> decay,bias;
 int32_t active=1,error=0,pos=0;
 Data(unsigned tokens,unsigned scenario):qkv(tokens*10240),gate(tokens*48),beta(tokens*48),input(786432),state(786432,0x3d80),y(tokens*6144,0x7e31),decay(48),bias(48){
  uint32_t seed=0x82a975+scenario;
  auto fill=[&](auto&v){for(auto&x:v){seed=1664525*seed+1013904223;x=ng::Args::bits(float(int(seed%257)-128)/512.f);}};
  fill(qkv);fill(gate);fill(beta);fill(input);
  for(unsigned h=0;h<48;++h){decay[h]=-0.125f-float(h)/512;bias[h]=float(int(h%9)-4)/16;}
  if(scenario==1){active=0;pos=-1;}
  if(scenario==2)error=7;
  if(scenario==3)pos=-1;
  if(scenario==4)pos=4096;
  if(scenario==5)pos=4096-int(tokens);
  if(scenario==6){qkv[0]=0x7fc1;qkv[128]=0xffd5;input[0]=0x7fd3;gate[0]=0x7fc5;beta[1]=0xffd6;}
  if(scenario==7){qkv[0]=0x7f80;qkv[2048]=0xff80;gate[0]=0x7f80;gate[1]=0xff80;}
  if(scenario==8){qkv[0]=1;qkv[1]=0x8001;qkv[2]=0x8000;input[0]=1;input[1]=0x8001;}
  if(scenario==10){error=7;pos=-1;}
  if(scenario==11){active=0;error=7;pos=4096;}
  if(scenario==12){active=0;pos=0;}
  if(scenario==9){gate[0]=ng::Args::bits(20.f);gate[1]=ng::Args::bits(19.875f);gate[2]=ng::Args::bits(-100.f);beta[0]=ng::Args::bits(-100.f);beta[1]=ng::Args::bits(100.f);}
 }
 ng::Args args(bool alias){ng::Args a;a.p[0]=qkv.data();a.p[1]=gate.data();a.p[2]=beta.data();a.p[3]=decay.data();a.p[4]=bias.data();a.p[5]=alias?state.data():input.data();a.p[6]=y.data();a.p[7]=state.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;return a;}
 std::vector<uint8_t> bytes()const{std::vector<uint8_t>b;auto add=[&](const void*p,size_t n){auto v=static_cast<const uint8_t*>(p);b.insert(b.end(),v,v+n);};add(state.data(),state.size()*2);add(y.data(),y.size()*2);add(&error,4);add(&pos,4);add(&active,4);return b;}
};
void run(const std::string&,ng::Shape s,Data&d,bool alias){p113rec::host(s,d.args(alias));}

}
int main(int argc,char**argv){try{
 check(argc==3,"view output");std::string view=argv[1];std::filesystem::path out=argv[2];
 std::ofstream expected(out/"expected.bin"),actual(out/"candidate.bin"),cases(out/"cases.jsonl");
 unsigned guard_checks=0;
 for(int active:{-1,0,1})for(int error:{0,1,7})for(int pos:{-1,0,4093,4095,4096})for(int tokens:{1,4}){
  int expected_guard=(!active||error)?1:(pos<0||pos>4096-tokens)?2:0;
  check(p82brec::entry_decision(active,error,pos,4096,tokens)==expected_guard,"guard semantics");++guard_checks;
 }
 check(guard_checks==90,"guard coverage");
 unsigned checks=0,tokens_checked=0;size_t bytes_checked=0;
 auto compare=[&](const Data&a,const Data&b,const std::string&desc,unsigned tokens){auto x=a.bytes(),y=b.bytes();
  // Raw comparison comes first. Digest transcripts bound the exact compared bytes
  // without retaining hundreds of MB of synthetic state copies.
  if(x!=y){unsigned printed=0;for(size_t j=0;j<x.size()&&printed<12;++j)if(x[j]!=y[j]){std::cerr<<desc<<" byte="<<j<<" expected="<<unsigned(x[j])<<" actual="<<unsigned(y[j])<<"\n";++printed;}}check(x==y,desc);if(desc.find("-s6-")!=std::string::npos&&std::getenv("P82_EXCEPTION_DUMP")){std::ofstream raw(out/(desc+".raw"),std::ios::binary);raw.write(reinterpret_cast<const char*>(x.data()),x.size());}expected<<packet26::hash(x.data(),x.size())<<'\n';actual<<packet26::hash(y.data(),y.size())<<'\n';
  cases<<"{\"case\":\""<<desc<<"\",\"bytes\":"<<x.size()<<",\"tokens\":"<<tokens<<",\"passed\":true}\n";++checks;tokens_checked+=tokens;bytes_checked+=x.size();};
 for(unsigned scenario=0;scenario<13;++scenario)for(bool alias:{false,true})for(bool packed:{false,true}){
  // Compare every state/output byte after each of four consecutive single-token calls.
  Data a(1,scenario),b=a;ng::Shape s{};s.op=ng::gdn;s.tokens=1;s.capacity=4096;s.flags=2|8|(packed?4:0);
  if(alias){a.state=a.input;b.state=b.input;}
  for(unsigned t=0;t<4;++t){
   p82brec::host<true>(s,a.args(alias));run(view,s,b,alias);
   compare(a,b,"serial-s"+std::to_string(scenario)+"-a"+std::to_string(alias)+"-p"+std::to_string(packed)+"-t"+std::to_string(t),1);
   if(!alias){a.input=a.state;b.input=b.state;}
   // New input each token, including after inactive/error decisions; preserve guards.
   for(size_t i=4096;i<a.qkv.size();++i){a.qkv[i]=ng::Args::bits(float(int((i+t*31)%113)-56)/256);b.qkv[i]=a.qkv[i];}
   if(scenario!=3&&scenario!=4){++a.pos;++b.pos;}
  }

 }
 std::ofstream(out/"native.json")<<"{\"passed\":true,\"cases\":"<<checks<<",\"tokens_checked\":"<<tokens_checked<<",\"bytes_compared\":"<<bytes_checked<<",\"full_state_elements\":786432,\"raw_bytes_compared\":true,\"transcript\":\"sha256 after raw equality\"}\n";
 std::cout<<checks<<" full-state checks PASS\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
