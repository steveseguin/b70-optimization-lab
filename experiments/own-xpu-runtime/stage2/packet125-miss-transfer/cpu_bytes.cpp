#include "micro_common.hpp"
#include <fstream>
#include <iostream>
static void check(bool value){if(!value)throw std::runtime_error("CPU byte gate mismatch");}
// Use the exact native fixture generator and frozen host methods. These are
// arithmetic/indirection tests, never CPU timing or device-equality claims.
int main(){unsigned checks=0;uint64_t digest=1469598103934665603ull;
 auto absorb=[&](const std::vector<uint8_t>&v){for(auto x:v){digest^=x;digest*=1099511628211ull;}};
 for(bool exceptional:{false,true})for(unsigned scene=0;scene<4;++scene){
  unsigned rows=32,count=2,experts=512;size_t g=rows*(exceptional?1100:820),d=rows*360;
  auto type=exceptional?iq3::Type::IQ3_S:iq3::Type::IQ2_S;
  auto gate=fixture(type,rows*2,2560,125),up=fixture(type,rows*2,2560,126),down=fixture(iq3::Type::IQ4_NL,rows*2,640,127);
  auto tiled=p100::transpose(down.data(),rows*2);std::vector<uint8_t> restored(down.size());
  for(unsigned row=0;row<rows*2;++row)for(unsigned block=0;block<20;++block){std::memcpy(restored.data()+row*360+block*16,p100::code_address(tiled.data(),row,block),16);std::memcpy(restored.data()+row*360+320+block*2,p100::half_address(tiled.data(),row,block),2);}check(restored==down);++checks;
  std::vector<uint16_t>x(2560),y(rows*count),uy(rows*count),act(640*count),dy(rows*count);for(unsigned i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%63)-31)/32);
  if(scene==1)x[0]=0x8000;if(scene==2){x[0]=0x7fc1;x[1]=0x7f80;}if(scene==3){x[0]=1;x[1]=0x8001;}
  iq3::Route routes[2]={{19,0,rows},{441,0,rows}};uint32_t status[9]={0,0,0,0,0,0,0,1,0};
  std::array<p58::Pointer,512>gt{},ut{},dt{};std::array<void*,19>gb{},db{};
  gb[0]=gt.data();gb[1]=ut.data();gb[2]=x.data();gb[3]=y.data();gb[4]=uy.data();gb[5]=routes;gb[6]=status;gb[7]=status+2;
  db[0]=dt.data();db[1]=dt.data();db[2]=act.data();db[3]=dy.data();db[4]=dy.data();db[5]=routes;db[6]=status+4;
  for(auto*b:{&gb,&db}){(*b)[16]=status+6;(*b)[17]=status+7;(*b)[18]=status+8;}
  p49dvirtual::GateKernel gk;gk.indirect=true;gk.rows=rows;gk.count=count;
  p28::Kernel<iq3::Type::IQ3_S,2560,1,1,false,true>g3;g3.b.rb=1100;g3.b.rows=rows;g3.b.count=count;g3.b.experts=experts;g3.b.indirect=true;g3.b.has_routes=true;
  p49dvirtual::DownKernel dk;dk.indirect=true;dk.rows=rows;dk.count=count;p100::Kernel<2>tk;tk.indirect=true;tk.rows=rows;tk.count=count;
  std::vector<uint8_t>expected;
  for(unsigned mode=0;mode<3;++mode){std::vector<uint8_t>packed(count*(2*g+d));
   for(unsigned s=0;s<count;++s){auto id=routes[s].expert_id;auto*base=packed.data()+s*(2*g+d);std::memcpy(base,gate.data()+s*g,g);std::memcpy(base+g,up.data()+s*g,g);std::memcpy(base+2*g,(mode==1?tiled:down).data()+s*d,d);
    gt[id]={uintptr_t(mode==2?base:gate.data()+s*g),1};ut[id]={uintptr_t(mode==2?base+g:up.data()+s*g),1};dt[id]={uintptr_t(mode==2?base+2*g:(mode==1?tiled:down).data()+s*d),1};}
   std::fill(y.begin(),y.end(),0xa5a5);std::fill(uy.begin(),uy.end(),0xa5a5);std::fill(dy.begin(),dy.end(),0xa5a5);
   if(exceptional)g3.run(gb);else gk.run(gb);for(unsigned s=0;s<count;++s)for(unsigned r=0;r<640;++r)act[s*640+r]=p39::activation(y[s*rows+r%rows],uy[s*rows+r%rows]);
   if(mode==1)tk.run(db);else dk.run(db);
   std::vector<uint8_t>out;for(auto&v:{x,y,uy,act,dy}){auto*b=(uint8_t*)v.data();out.insert(out.end(),b,b+v.size()*2);}auto*b=(uint8_t*)status;out.insert(out.end(),b,b+sizeof(status));
   if(mode==0)expected=out;else{check(out==expected);++checks;}absorb(out);
  }
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"digest\":"<<digest<<"}\n";
}
