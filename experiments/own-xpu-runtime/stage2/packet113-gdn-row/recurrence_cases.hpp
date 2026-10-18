#pragma once
#include "p113_recurrence.hpp"
#include <vector>
#include <cstring>
namespace p113test {
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
  if(scenario==13){qkv[0]=0x7f81;qkv[2049]=0xffa3;input[17]=0x7fa5;gate[3]=0x7f89;beta[4]=0xff91;}
  if(scenario==14){for(unsigned h=0;h<48;++h){input[h*16384+3]=0xffd9;input[h*16384+4]=0x7fc7;qkv[(h%16)*128+65]=0x7fc3;}}
  if(scenario==15){qkv[0]=0x7f7f;qkv[2048]=0xff7f;input[0]=0x7f7f;beta[0]=0x8000;}
  if(scenario==9){gate[0]=ng::Args::bits(20.f);gate[1]=ng::Args::bits(19.875f);gate[2]=ng::Args::bits(-100.f);beta[0]=ng::Args::bits(-100.f);beta[1]=ng::Args::bits(100.f);}
 }
 ng::Args args(bool alias){ng::Args a;a.p[0]=qkv.data();a.p[1]=gate.data();a.p[2]=beta.data();a.p[3]=decay.data();a.p[4]=bias.data();a.p[5]=alias?state.data():input.data();a.p[6]=y.data();a.p[7]=state.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;return a;}
 std::vector<uint8_t> bytes()const{std::vector<uint8_t>b;auto add=[&](const void*p,size_t n){auto v=static_cast<const uint8_t*>(p);b.insert(b.end(),v,v+n);};add(state.data(),state.size()*2);add(y.data(),y.size()*2);add(&error,4);add(&pos,4);add(&active,4);return b;}
};
template<class Run,class Compare> unsigned cases(Run run,Compare compare){
 unsigned checks=0;
 for(unsigned tokens:{1,2,4})for(unsigned scenario=0;scenario<16;++scenario)
 for(bool alias:{false,true})for(bool packed:{false,true}){
  Data a(tokens,scenario),b=a;ng::Shape s{};s.op=ng::gdn;s.tokens=tokens;s.capacity=4096;s.flags=2|8|(packed?4:0);
  if(alias){a.state=a.input;b.state=b.input;}
  for(unsigned t=0;t<4;++t){
   if(checks%2){run(true,s,b,alias);run(false,s,a,alias);}else{run(false,s,a,alias);run(true,s,b,alias);}
   compare(a,b,"m"+std::to_string(tokens)+"-s"+std::to_string(scenario)+"-a"+std::to_string(alias)+"-p"+std::to_string(packed)+"-t"+std::to_string(t),tokens);
   ++checks;
   if(!alias){a.input=a.state;b.input=b.state;}
   for(size_t i=4096;i<a.qkv.size();++i){a.qkv[i]=ng::Args::bits(float(int((i+t*31)%113)-56)/256);b.qkv[i]=a.qkv[i];}
   if(scenario!=3&&scenario!=4){a.pos+=tokens;b.pos+=tokens;}
  }
 }
 return checks;
}
}
