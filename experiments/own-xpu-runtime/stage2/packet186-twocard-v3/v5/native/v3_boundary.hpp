// Packet186 V3: verified-boundary rebalance (included by rank.hpp after native_controller.hpp).
//
// Placement (storage, fixed per load; selection key rank0_layers=0-25): rank 0 also holds the GDN
// layers 24-25; rank 1 keeps 24-47 and the full 248,320-row target head (head=production).
// Execution (selection key boundary=rank0, switchable at a quiescent bracket boundary):
//   * a rank-0 half runs embedding + layers 0-23 exactly as bundle 8 and no longer exports;
//   * after every rank-0 accept that a rank-1 half will consume, the controller sends ONE boundary
//     command: rank 0 issues layers 24-25 for that accepted position/token, drains, exports the
//     layer-25 residual stream to the shared slot; rank 1 starts at layer 26;
//   * the draft is unchanged (rank 1, MTP).
// State of layers 24-25 on rank 0 (why it never sees a guessed token):
//   1. not banked (banks() skips them) and not in the speculative image (v3_private): no
//      speculative command ever issues them, so rollback has nothing of theirs to restore;
//   2. the boundary refuses unless the previous rank-0 command was the ACCEPT of a completed half
//      for exactly this (position, token) and no candidate is pending (a speculative half is only
//      accepted on a hit; a miss is rolled back, corrected with the verified token, then accepted);
//   3. for every decode position (fixture >= 2) the token must also equal rank 1's own published
//      verification for that position (the same check a redo uses);
//   4. no rank-0 half may start while an accepted position still waits for its boundary, so the
//      layer-23 stream the boundary consumes is the accepted one;
//   5. request reset / bracket boundary clear the pending flag; reset zeroes all state bytes.
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/v5/native/v3_controller.hpp"
namespace pipeline {
namespace v3 {
inline bool rank0_extended(const Options& a){
 if(a.selection.empty())return false;
 p49d::Selection s;s.load(a.selection.string(),a.selection_sha256);
 auto i=s.choices.find("rank0_layers");return i!=s.choices.end()&&i->second=="0-25";
}
}
struct V3Boundary {
 bool ready=false;int position=-1,token=-1,fixture=0;
 int half_position=-1,half_token=-1;uint64_t runs=0;
 void reset(){ready=false;position=token=half_position=half_token=-1;fixture=0;}
};
static void v3_before_half(Engine& e,V3Boundary& v,const Request& r){
 if(e.a.rank!=0||!e.v3_active)return;
 require(!v.ready,"V3: a rank-0 half cannot start before the previous accepted position's boundary");
 v.half_position=r.position;v.half_token=r.token;
}
static void v3_accepted(Engine& e,V3Boundary& v,const Candidate& c){
 if(e.a.rank!=0||!e.v3_active)return;
 require(!v.ready&&c.pending&&!c.cancelled&&c.position==v.half_position&&v.half_token>=0,"V3: accept does not match the last completed half");
 v.ready=true;v.position=c.position;v.token=v.half_token;v.fixture=c.fixture;
}
static Reply v3_boundary_step(Engine& e,V3Boundary& v,const Request& r,uint8_t* shared,const Candidate& c){
 const auto begin=std::chrono::steady_clock::now();
 require(e.a.rank==0&&e.v3_active&&!e.v3_sites.empty(),"V3 boundary ownership");
 require(!c.pending,"V3 boundary with an unresolved candidate");
 require(v.ready&&r.position==v.position&&r.token==v.token&&r.fixture==v.fixture,"V3 boundary requires the accepted half's (position, token)");
 if(r.fixture>=2){auto& confirmed=verification(shared);
  require(__atomic_load_n(&confirmed.position_plus_one,__ATOMIC_ACQUIRE)==uint32_t(r.position)&&confirmed.token==r.token,"V3 boundary token differs from rank 1's verification");}
 e.verify_configuration();e.guard();
 const double gpu=e.gemv_ms+e.nongemv_ms;
 Candidate fixtures;fixtures.fixture=r.fixture;std::array<int,4> captured{};size_t captured_count=0;
 const auto body=std::chrono::steady_clock::now();
 for(size_t index:e.v3_sites){
  const auto& l=e.p.launches[index];
  e.enqueue(l,e.logical);
  if(e.issue_sites.at(index).layer_end){
   const int layer=e.issue_sites[index].layer;
   if(e.a.retain_steps.contains(r.fixture)){ownrt::CopyEngine copy(e.dev(0));e.tail=copy.copy(e.snapshots[0],size_t(layer)*4*e.p.g.h*2,e.buffers[0].at("streams").id,0,4*e.p.g.h*2,{});captured.at(captured_count++)=layer;}
  }
 }
 e.drain();p150::record("boundary_body",r.position,false,body);
 require(!e.integer(0,"error"),"sticky rank error in the V3 boundary (never rolled back)");
 if(captured_count){auto raw=e.readback(0,e.snapshots[0],48*4*e.p.g.h*2);const size_t n=4*e.p.g.h*2;
  for(size_t i=0;i<captured_count;++i){int layer=captured[i];fixtures.layers[layer]={raw.begin()+layer*n,raw.begin()+(layer+1)*n};}
  std::vector<uint8_t> zero(48*4*e.p.g.h*2,0);e.upload(0,e.snapshots[0],0,zero.data(),zero.size());}
 publish(e,fixtures); // non-speculative: the boundary only ever runs on an accepted, verified token
 size_t bytes=4*e.p.g.h*2;require(bytes<=slot_bytes,"V3 export extent");
 p150::measure("handoff_export",r.position,false,[&]{auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);});
 v.ready=false;++v.runs;
 p150::record("boundary_total",r.position,false,begin);
 return {0,-1,0,int32_t(bytes),r.sequence,e.a.rank,{0,int32_t(e.v3_sites.size())},Engine::ms(begin),e.gemv_ms+e.nongemv_ms-gpu,0,0};
}
} // namespace pipeline

