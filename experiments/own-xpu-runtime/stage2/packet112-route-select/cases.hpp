#pragma once
#include "p112_route.hpp"
#include <fstream>
#include <bit>
#include <array>
#include <string>
#include <vector>
#include <cstring>
#include <stdexcept>
namespace p112test {
inline void require(bool ok,const std::string&s){if(!ok)throw std::runtime_error(s);}
struct State {
 std::array<int32_t,12>ids;std::array<float,12>weights;
 std::array<int32_t,32>up,down;std::array<float,1090>scratch;
 uint32_t error=0,active=1,position=0,rope=0;
 State(){ids.fill(-7);weights.fill(-6);up.fill(-5);down.fill(-4);scratch.fill(-7.25f);}
 route42::Args args(void*x,flash::Scalar type,unsigned no){
  route42::Args a{};a.input=x;a.input_type=type;a.n=512;a.top=10;a.mid=640;a.h=2560;a.no=no;
  a.output[0]=ids.data();a.output[1]=weights.data();a.output[2]=up.data();a.output[3]=down.data();
  a.output_type[0]=a.output_type[2]=a.output_type[3]=flash::Scalar::u32;a.output_type[1]=flash::Scalar::f32;
  a.scratch=scratch.data();a.error=&error;a.active=&active;return a;
 }
 integrated::Spec spec(flash::Scalar type,unsigned no)const{
  integrated::Spec s{};s.op=integrated::Op::route;s.special=integrated::Special::normal;
  s.ni=1;s.no=no;s.nw=0;s.g.mid=640;s.g.h=2560;s.site.shape[1]=10;
  s.types[0]=type;s.sizes[0]=512;
  for(unsigned j=0;j<no;++j){s.types[1+j]=j==1?flash::Scalar::f32:flash::Scalar::u32;s.sizes[1+j]=j<2?10:30;}
  return s;
 }
 std::vector<void*> bindings(void*x,unsigned no){std::vector<void*>v{x,ids.data(),weights.data()};if(no==4){v.push_back(up.data());v.push_back(down.data());}
  for(auto*p:{static_cast<void*>(scratch.data()),static_cast<void*>(&error),static_cast<void*>(&position),static_cast<void*>(&active),static_cast<void*>(&rope)})v.push_back(p);return v;}
};
template<class T>inline void equal(const T&a,const T&b,const std::string&s){require(!std::memcmp(&a,&b,sizeof(T)),s);}
inline void compare(const State&a,const State&b,unsigned scenario,bool partial_max=false){
 auto name="case="+std::to_string(scenario)+" ";equal(a.ids,b.ids,name+"ids and guards");equal(a.weights,b.weights,name+"weights and guards");
 equal(a.up,b.up,name+"up descriptors and guards");equal(a.down,b.down,name+"down descriptors and guards");
 equal(a.error,b.error,name+"error");equal(a.active,b.active,name+"active");equal(a.position,b.position,name+"position");equal(a.rope,b.rope,name+"rope");
 // On rejected nonfinite rows production's concurrent early failure makes
 // only scratch[0:32] partially written and unspecified. All other bytes,
 // every public output and every guard remain part of the byte gate.
 unsigned first=partial_max?32:0;
 require(!std::memcmp(a.scratch.data()+first,b.scratch.data()+first,(a.scratch.size()-first)*4),name+"scratch");
}
struct Case {
 std::array<float,512>x{};std::array<uint16_t,512>xb{};
 bool bf16=false,nonfinite=false;unsigned no=4;uint32_t active=1,error=0;
 void* input(){return bf16?static_cast<void*>(xb.data()):x.data();}
 flash::Scalar type()const{return bf16?flash::Scalar::bf16:flash::Scalar::f32;}
};
using Inputs=std::array<std::array<float,512>,16>;
inline Inputs read_inputs(const std::string&path){Inputs inputs{};std::ifstream f(path,std::ios::binary);require(bool(f),"harness inputs missing");f.read(reinterpret_cast<char*>(inputs.data()),sizeof inputs);require(bool(f)&&f.peek()==EOF,"harness input extent");return inputs;}
inline Case make_case(const Inputs&inputs,unsigned scenario){
 Case c;c.bf16=(scenario/16)%2;c.no=(scenario/32)%2?2:4;
 c.x=inputs[scenario%16];uint32_t seed=0x1120049u+scenario;
 auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
 if(scenario>=64 && scenario<1536)for(unsigned j=0;j<512;++j){float v=float(int(next()%65537)-32768)/257.f;
  switch(scenario%12){
   case 0:v=0.f;break;case 1:v=float(j%7);break;case 2:v=j<502?-100.f:100.f;break;
   case 3:v=j==511?80.f:-80.f;break;case 4:v=std::bit_cast<float>(0x3f800000u+j%23);break;
   case 5:v=j%2?-0.f:0.f;break;case 6:v=std::bit_cast<float>(1u+j);break;
   case 7:v=float(511-j);break;case 8:v=float(j);break;case 9:v=float(int(next()%5)-2);break;
   case 10:v=(j%2?1.f:-1.f)*std::numeric_limits<float>::max();break;default:break;
  }c.x[j]=v;
 }
 if(scenario>=1536){
  unsigned pos=scenario-1536;constexpr uint32_t nonfinite[]={0x7f800000,0xff800000,0x7fc12345,0xffc54321,0x7f812345,0xff812345};
  c.x[pos]=std::bit_cast<float>(nonfinite[pos%6]);c.nonfinite=true;
 }
 if(scenario==1534)c.active=0;if(scenario==1535)c.error=7;
 for(unsigned j=0;j<512;++j)c.xb[j]=iq3::bf16_bits(c.x[j]);
 return c;
}
}
