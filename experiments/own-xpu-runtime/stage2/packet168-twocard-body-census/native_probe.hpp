#pragma once
// Isolated diagnostic prototype. It deliberately cannot certify an overlapped
// native emission interval: suffix/mailbox traffic is outside this loop.
// No diagnostic token, confirmation or shared stream is published.
namespace p168 {
static int classify(const flash::Launch& l) {
 const auto& op=l.op;const auto& n=l.label;
 if(n=="logits"||n=="argmax")return 9;
 if(op=="begin"||op=="commit"||op=="check_status")return 0;
 if(op.starts_with("qsa_"))return 1;
 if(op=="gdn"||op=="conv"||op=="gdn_norm_gate")return 2;
 if(op=="route"||n.find("router")!=std::string::npos)return 3;
 if(op=="expert_gate_up"||op=="routed_gemv"||op=="expert_gather"||n.find("exps")!=std::string::npos)return 4;
 if(n.find("shexp")!=std::string::npos)return 5;
 if(op=="gemv"||n.find(".hc.")!=std::string::npos)return 6;
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
static void probe(Engine& e,pipeline::SpeculativeImage& image,
                  const pipeline::Request& request,uint8_t* shared) {
 require(e.a.census_probe&&request.token>=0&&request.token<=9,"packet168 diagnostic arm");
 require(request.fixture>=1&&request.fixture<=8,"packet168 bounded repeats1..8");
 // No same-shape transfer arm is implemented by this prototype. Refuse it,
 // rather than report an empty mask as a measured zero transfer cost.
 require(request.token!=8,"packet168 cross-card transfer is not implemented");
 image.boundary();e.drain();const auto before=signature(e);
 std::ofstream out(e.a.output/"packet168-probes.jsonl",std::ios::app);
 auto execute=[&](int arm){
   size_t skipped=0;auto start=std::chrono::steady_clock::now();
   for(auto& l:e.p.launches){
     // Sticky checks and commit are always retained. The class map is a
     // prototype; fused command coverage must still qualify independently.
     if(arm&&classify(l)==arm){++skipped;continue;}
     e.enqueue(l,e.logical);
   }
   e.drain();require(!e.integer(0,"error"),"packet168 arm raised sticky error");
   return std::pair{Engine::ms(start),skipped};
 };
 for(int repeat=0;repeat<request.fixture;++repeat){
   sensor(e,"before-control-snapshot");image.begin(shared);
   auto control=execute(0);const auto repaired_expected=signature(e);
   image.restore();e.drain();sensor(e,"after-control-restore");
   require(signature(e)==before,"packet168 control restore differs");
   image.begin(shared);sensor(e,"before-arm");auto arm=execute(request.token);
   image.restore();e.drain();sensor(e,"after-arm-restore");
   require(signature(e)==before,"packet168 arm restore differs");
   image.begin(shared);sensor(e,"before-repair");execute(0);
   require(signature(e)==repaired_expected,"packet168 exact repair differs");
   image.restore();e.drain();sensor(e,"after-repair-restore");
   require(signature(e)==before,"packet168 repair restore differs");
   out<<"{\"schema\":\"packet168.isolated-prototype.v1\",\"diagnostic_only\":true,\"reported_tokens\":0,\"rank\":"<<e.a.rank
      <<",\"arm\":"<<request.token<<",\"repeat\":"<<repeat<<",\"control_ms\":"<<control.first<<",\"arm_ms\":"<<arm.first
      <<",\"skipped_sites\":"<<arm.second<<",\"restore_exact\":true,\"repair_exact\":true,\"class_coverage_complete\":false,\"matched_native_emission_interval\":false}\n";
   require(bool(out),"packet168 stream write");
 }
 image.boundary();sensor(e,"final-boundary");
}
}
