#pragma once
#include <cstdint>
#include <stdexcept>
namespace p130 {
// Per native request, not speculative position. A service is consumed once.
struct Interleave {
 uint32_t sequence=0,completed=0;int position=-1,fixture=-1,boundary=-1;
 void arm(uint32_t seq,int pos,int fix){
  if(!seq||fix<=0||seq<=sequence||(sequence&&completed!=sequence))
   throw std::logic_error("p130 outstanding/stale request");
  sequence=seq;position=pos;fixture=fix;boundary=-1;
 }
 bool pending()const{return sequence&&completed!=sequence;}
 bool done(uint32_t seq,int pos,int fix)const{
  if(seq!=sequence||pos!=position||fix!=fixture)throw std::logic_error("p130 request identity");
  return completed==seq;
 }
 void finish(uint32_t seq,int pos,int fix){
  if(done(seq,pos,fix))throw std::logic_error("p130 duplicate suffix");completed=seq;
 }
 template<class Fence,class Ready,class Service>
 void chunk(int layer,Fence fence,Ready ready,Service service){
  if(!pending())return;
  fence(); // no later target layer submitted before this fence completes
  boundary=layer;
  if(ready(sequence))service(sequence,position,fixture);
 }
};
}
