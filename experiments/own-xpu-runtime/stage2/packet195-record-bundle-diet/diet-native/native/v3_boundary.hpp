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
// Packet188 k3: the storage rank0_layers=0-26 also holds GDN layer 26 on rank 0; boundary=rank0-k3 runs
// 24-26 (rank 1 starts at QSA layer 27), boundary=rank0 runs 24-25 with layer 26 idle on rank 0 and run by
// rank 1. Every rule above holds for the whole stored set (engine_bracket.hpp v3_check_plan). With
// kernel_io=kernel the error check and the export are ONE kernel readback (kio_read_many).
// Packet189 k3x: the execution key boundary_export=copy|kernel (default copy) selects the export path of the
// 20,480-byte layer-end stream: copy = the copy-engine readback V3 (packet186/187) used, kernel = packet188's
// folded KioCopy readback. Only the transfer path differs; the exported bytes are identical (v3_state.cpp proof).
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/v5/native/v3_controller.hpp"
namespace pipeline {
namespace v3 {
// Extra layers rank 0 stores beyond 0-23: 0 (production), 2 (V3: 24-25), 3 (packet188 k3 storage: 24-26).
inline int rank0_extended(const Options& a){
 if(a.selection.empty())return 0;
 p49d::Selection s;s.load(a.selection.string(),a.selection_sha256);
 auto i=s.choices.find("rank0_layers");if(i==s.choices.end())return 0;
 return i->second=="0-25"?2:i->second=="0-26"?3:0;
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
 size_t bytes=4*e.p.g.h*2;require(bytes<=slot_bytes,"V3 export extent");
 // packet189 boundary_export: `kernel` (packet188's k3trims path) folds error + exported stream into ONE KioCopy
 // readback (one work-item per byte into pinned host memory, measured 28.9 ns/byte = 0.59 ms for 20,480 B);
 // `copy` (default, V3's record path, packet186/187) reads the 20,480-byte stream back on the copy engine
 // (2.6 ns/byte = 0.053 ms) and memcpys it to the shared slot, even when kernel_io=kernel. Under `copy` with
 // kernel_io=kernel the 4-byte error check stays a kernel read (e.integer -> readback -> kio); the bytes are the same.
 std::vector<uint8_t> folded; // packet188 kernel_io=kernel + boundary_export=kernel: error + exported stream in ONE kernel readback
 const bool export_kernel=e.kio_active&&!e.export_copy; // packet188's kio path (folded; kio_readback when fixtures are retained)
 if(export_kernel&&captured_count==0)p150::measure("handoff_export",r.position,false,[&]{folded=e.kio_read_many(0,{{e.buffers[0].at("error").id,4},{e.buffers[0].at("streams").id,bytes}});});
 {int error=0;if(!folded.empty())std::memcpy(&error,folded.data(),4);else error=e.integer(0,"error");
  require(!error,"sticky rank error in the V3 boundary (never rolled back)");}
 if(captured_count){auto raw=e.readback(0,e.snapshots[0],48*4*e.p.g.h*2);const size_t n=4*e.p.g.h*2;
  for(size_t i=0;i<captured_count;++i){int layer=captured[i];fixtures.layers[layer]={raw.begin()+layer*n,raw.begin()+(layer+1)*n};}
  std::vector<uint8_t> zero(48*4*e.p.g.h*2,0);e.upload(0,e.snapshots[0],0,zero.data(),zero.size());}
 publish(e,fixtures); // non-speculative: the boundary only ever runs on an accepted, verified token
 if(!folded.empty())std::memcpy(shared,folded.data()+4,bytes); // folded = error (4 B) followed by the exported stream (bytes)
 else p150::measure("handoff_export",r.position,false,[&]{auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes,/*copy_engine=*/!export_kernel);std::memcpy(shared,raw.data(),bytes);});
 ++(export_kernel?e.export_kernel_runs:e.export_copy_runs);
 v.ready=false;++v.runs;
 p150::record("boundary_total",r.position,false,begin);
 return {0,-1,0,int32_t(bytes),r.sequence,e.a.rank,{0,int32_t(e.v3_sites.size())},Engine::ms(begin),e.gemv_ms+e.nongemv_ms-gpu,0,0};
}
} // namespace pipeline

