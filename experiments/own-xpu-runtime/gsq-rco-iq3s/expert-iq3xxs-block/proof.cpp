// Source checkpoint only. Future GNU proof; no native owner/device creation.
#define OWN_RT_HOST_ONLY
#include "block.hpp"
#include <iostream>
#include <cstring>
#include <vector>
#include <bit>
static void same(float a,float b,const char*what){if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b))throw std::runtime_error(what);}
int main(){try{
 size_t checks=0;uint8_t block[98]{};
 const uint16_t halves[]{0,0x8000,1,0x8001,0x03ff,0x0400,0x3c00,0xbc00,0x7bff,0x7c00,0xfc00,0x7e11,0xfe11,0x7c01,0xfc01};
 // Focus only changed hoist/decode binding; old generic decoder is independent.
 for(auto h:halves)for(unsigned scale=0;scale<16;++scale)for(unsigned code=0;code<128;++code){
  block[0]=uint8_t(h);block[1]=uint8_t(h>>8);
  for(unsigned i=0;i<64;++i)block[2+i]=uint8_t(code*17+i*13);
  for(unsigned g=0;g<8;++g){uint32_t word=(scale<<28)|code|(code<<7)|(code<<14)|(code<<21);std::memcpy(block+66+g*4,&word,4);}
  for(unsigned g=0;g<8;++g)for(unsigned lane=0;lane<32;++lane){same(iq3block::block_element(block,iq3::half(h),g,lane),gsq::element_unchecked(18,block,g*32+lane),"exact hoisted decoder bits");++checks;}
 }
 // Complete production640rows/top10/per-slot stride, with four populated
 // synthetic experts. Internal Host operation fixture, not public bank admission.
 constexpr size_t rows=640,k=2560,rb=980;std::vector<uint8_t>w(4*rows*rb);
 for(size_t i=0;i<w.size();++i)w[i]=uint8_t(i*37+11);
 for(size_t i=0;i<w.size();i+=98){w[i]=0x00;w[i+1]=0x24;}
 std::vector<uint16_t>x(10*k),a(10*rows),b(10*rows);for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%31)-15)/32.f);
 std::vector<iq3::Route>routes(10);std::vector<uint32_t>sa(10),sb(10);
 for(unsigned i=0;i<10;++i)routes[i]={i%4,0,640};
 routes[3]={2,4,636};routes[4]={1,0,0};routes[5]={512,0,640};routes[6]={0,640,1};routes[7]=routes[1];
 gsqn::Shape shape{rows,k,rb,10,512,true,true};
 gsqn::PackedOperation<18>control;control.s=shape;iq3block::BlockOperation candidate;candidate.s=shape;
 auto compare=[&](){std::array<void*,5>pa{w.data(),x.data(),a.data(),routes.data(),sa.data()},pb{w.data(),x.data(),b.data(),routes.data(),sb.data()};control.run(pa);candidate.run(pb);if(a!=b||sa!=sb)throw std::runtime_error("full output/status/tail bits");checks+=a.size()+sa.size();
  gsqn::Bound bound{shape,w.data(),x.data(),b.data(),routes.data(),sb.data()};for(unsigned slot:{0u,1u,2u,7u,9u})for(unsigned row:{0u,319u,639u})for(unsigned lane=0;lane<32;++lane){same(gsqn::lane_sum<18>(bound,routes[slot],row,slot,lane),iq3block::block_lane_sum(bound,routes[slot],row,slot,lane),"lane ordered sum bits");++checks;}};
 compare();x[0]^=0x40;w[2]^=1;compare();
 if(!iq3block::selected("blk.0.expsgate","blk.0.ffn_gate_exps.weight")||iq3block::selected("blk.0.expsgate","blk.0.ffn_up_exps.weight")||iq3block::selected("blk.1.expsgate","blk.1.ffn_gate_exps.weight"))throw std::runtime_error("exact selector");
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"scope\":\"CPU loop/decoder delta only; no Device or public facade execution\"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
