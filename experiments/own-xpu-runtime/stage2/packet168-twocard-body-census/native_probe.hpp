#pragma once
// Isolated body probe (five arm classes; attention class 1 always runs = residual). It cannot certify an overlapped native
// emission interval: suffix/mailbox/head traffic is outside this loop and is
// reported only inside the subtraction residual.
// No diagnostic token, confirmation or shared stream is published.
namespace p168 {
static int classify(const flash::Launch& l) {
 const auto& op=l.op;const auto& n=l.label;
 // Head and transfer have no diagnostic skip arm. They are residual work.
 if(n=="logits"||n=="argmax"||op=="handoff"||op=="handoff_result")return -1;
 if(op=="begin"||op=="commit"||op=="check_status")return 0;
 if(op.starts_with("qsa_"))return 1;
 if(op=="gdn"||op=="conv"||op=="gdn_norm_gate")return 2;
 // One physical launch owns route+shared activation; another owns shared
 // down+expert mixture/blend. Keep both in the fused router/shared class.
 if(op=="route"||op=="moe_combine"||n.find("router")!=std::string::npos||n.find("shexp")!=std::string::npos)return 3;
 if(op=="expert_gate_up"||op=="routed_gemv"||op=="expert_gather"||n.find("exps")!=std::string::npos)return 4;
 if(p60::stage(n)==0)return 7;
 if(op=="gemv"||p60::stage(n)>0)return 6;
 return 7;
}
static std::string signature(Engine& e) {
 std::ostringstream s;
 for(const auto& [name,b]:e.buffers[0])s<<name<<':'<<hash(e.readback(0,b.id,b.n*flash::scalar_bytes(b.type)))<<';';
 for(const auto& [name,id]:e.state_spares)s<<name<<':'<<hash(e.readback(0,id,e.dev(0).arena.row(id).bytes))<<';';
 // A private reserve is intentionally overwritten by the next bank capture.
 // The committed and spare banks above are the observable rollback image.
 s<<e.history0<<':'<<e.history1<<':'<<e.bank_parity<<':'<<e.context_extent;
 return s.str();
}
static void sensor(Engine& e,const std::string& phase) {
 pipeline_cancel_check();record_host_memory(e.a.output,("packet168-"+phase).c_str());
 require(!e.poisoned&&!e.integer(0,"error"),"packet168 sticky failure");
}
static std::string routes(Engine& e) {
 std::ostringstream s;
 for(const auto& l:e.p.launches)if(l.op=="route")for(const auto& name:l.outputs){
  const auto& b=e.buffers[0].at(name);
  s<<name<<':'<<hash(e.readback(0,b.id,b.n*flash::scalar_bytes(b.type)))<<';';
 }
 return s.str();
}
static void probe(Engine& e,pipeline::SpeculativeImage& image,
                  const pipeline::Request& request,uint8_t* shared) {
 require(e.a.census_probe&&(request.token==0||request.token==2||request.token==3||request.token==4||request.token==6||request.token==7),"packet168 five-class diagnostic arm only");
 require(request.fixture>=1&&request.fixture<=8,"packet168 bounded repeats1..8");
 // No same-shape transfer arm is implemented by this prototype. Refuse it,
 // rather than report an empty mask as a measured zero transfer cost.
 image.boundary();e.drain();
 // v3 fix for device-census-B-v2 (benchmark-analysis, 65+63 -> position 128):
 // the setup request's last half step admitted position P-1 only, so the
 // prepared qsa_select/qsa_attention launch extent is ((P-1+32)/32)*32. The
 // body pass runs at the device position P (commit incremented it). When P is
 // a multiple of 32 that extent equals P and the device guard
 // pos>position_limit(s)-s.tokens (kernels.hpp/round2.hpp) set the sticky
 // error in the CONTROL pass. Admit P exactly as a non-speculative half step
 // does, before the image and the signature, and mirror the guard on host.
 const int position=e.integer(0,"position");
 require(position>=0&&position<e.p.g.context,"packet168 probe position bound");
 e.admit_position(position);
 require(position<=e.context_extent-1,"packet168 probe position outside prepared launch extent");
 const auto before=signature(e);
 std::ofstream out(e.a.output/"packet168-probes.jsonl",std::ios::app);
 auto execute=[&](int arm){
   size_t skipped=0;auto start=std::chrono::steady_clock::now();
   for(auto& l:e.p.launches){
     // This remains an isolated body probe. Neither partition of the head
     // nor transfer is executed or assigned an invented skip measurement.
     if(classify(l)<0)continue;
     if(arm&&classify(l)==arm){++skipped;continue;}
     e.enqueue(l,e.logical);
   }
   e.drain();require(!e.integer(0,"error"),"packet168 arm raised sticky error");
   require(!arm||skipped>0,"packet168 empty class mask");
   return std::pair{Engine::ms(start),skipped};
 };
 for(int repeat=0;repeat<request.fixture;++repeat){
   sensor(e,"before-control-snapshot");image.begin(shared);
   auto control=execute(0);const auto repaired_expected=signature(e);const auto route_expected=routes(e);
   image.restore();e.drain();sensor(e,"after-control-restore");
   require(signature(e)==before,"packet168 control restore differs");
   image.begin(shared);sensor(e,"before-arm");auto arm=execute(request.token);
   const bool same_routes=routes(e)==route_expected;
   image.restore();e.drain();sensor(e,"after-arm-restore");
   require(signature(e)==before,"packet168 arm restore differs");
   image.begin(shared);sensor(e,"before-repair");execute(0);
   require(signature(e)==repaired_expected,"packet168 exact repair differs");
   image.restore();e.drain();sensor(e,"after-repair-restore");
   require(signature(e)==before,"packet168 repair restore differs");
   // A skipped upstream class legitimately changes router inputs. Expert count
   // and shapes are fixed (top-k); identity changes are recorded, never hidden.
   out<<"{\"schema\":\"packet168.body-probe.v2\",\"diagnostic_only\":true,\"reported_tokens\":0,\"rank\":"<<e.a.rank
      <<",\"arm\":"<<request.token<<",\"prompt_index\":"<<request.position<<",\"repeat\":"<<repeat<<",\"control_ms\":"<<control.first<<",\"arm_ms\":"<<arm.first
      <<",\"skipped_sites\":"<<arm.second<<",\"restore_exact\":true,\"repair_exact\":true,\"route_identity_preserved\":"<<(same_routes?"true":"false")
      <<",\"class_coverage_complete\":true,\"matched_native_emission_interval\":false}\n";
   require(bool(out),"packet168 stream write");
 }
 image.boundary();sensor(e,"final-boundary");
}
}
