// Actual Engine/Dispatcher/legacy owner-zero/checked ring descriptor reset on
// the Host backend. The minimal plan contains no arithmetic or model weights.
#include "checkpoint_fixture.hpp"
static void options_gate(){
 setenv("OMP_NUM_THREADS","2",1);
 const std::vector<std::string> base{"native","--output","/unused-ring-reset-parser","--rank","0","--memory","resident","--gsq-packed","--activations","f32","--context","4096","--target-split","24","--retain-steps","none","--pipeline-stage","0","--pipeline-boundaries","0,12,24,36,48","--native-nice",std::to_string(getpriority(PRIO_PROCESS,0)),"--pipeline-ring","--pipeline-ring-request-sha256",std::string(64,'a'),"--pipeline-ring-live-draft","--draft-mtp","--pipeline-ring-final-shared","/unused-peer","--pipeline-ring-pending-provider"};
 auto check=[&](std::vector<std::string> extra){auto args=base;args.insert(args.end(),extra.begin(),extra.end());std::vector<char*> pointers;for(auto& a:args)pointers.push_back(a.data());return parse(int(pointers.size()),pointers.data());};
 std::vector<std::string> full{"--pipeline-ring-verify-restore","--pipeline-ring-recursive-verify-restore","--pipeline-ring-verify-provider-survival"};assert(!check(full).pipeline_ring_persistent_requests);
 auto qualified=full;qualified.push_back("--pipeline-ring-persistent-requests");auto q=check(qualified);assert(q.pipeline_ring_check_policy=="qualification");auto short_context=qualified;short_context.insert(short_context.end(),{"--context","16"});refusal([&]{check(short_context);});
 auto measured=check({"--pipeline-ring-persistent-requests","--pipeline-ring-check-policy","measured"});assert(!measured.pipeline_ring_verify&&!measured.pipeline_ring_recursive_verify&&!measured.pipeline_ring_verify_provider_survival);
 auto batched=qualified;batched.insert(batched.end(),{"--prefill-rows","2","--prefill-shared","/unused-prefill"});assert(check(batched).prefill_rows==2);
 auto legacy_prefill=full;legacy_prefill.insert(legacy_prefill.end(),{"--prefill-rows","2","--prefill-shared","/unused-prefill"});refusal([&]{check(legacy_prefill);});
 for(const auto& bad:std::vector<std::vector<std::string>>{{},{"--pipeline-ring-check-policy","measured"},{"--pipeline-ring-persistent-requests"},{"--pipeline-ring-persistent-requests","--pipeline-ring-check-policy","other"},{"--pipeline-ring-persistent-requests","--pipeline-ring-check-policy","measured","--pipeline-ring-verify-restore"},{"--pipeline-ring-persistent-requests","--pipeline-ring-check-policy","measured","--pipeline-persistent-requests"}})refusal([&]{check(bad);});
}
static std::string descriptor(const fs::path& destination,int stage,int sequence,int epoch){return "{\"schema\":\"ownrt.ring-reset-request.v1\",\"stage_id\":"+std::to_string(stage)+",\"global_sequence\":"+std::to_string(sequence)+",\"previous_epoch\":"+std::to_string(epoch)+",\"next_epoch\":"+std::to_string(epoch+1)+",\"previous_request_sha256\":\""+std::string(64,char('a'+epoch))+"\",\"next_request_sha256\":\""+std::string(64,char('b'+epoch))+"\",\"destination\":"+ownrt::quote(destination.string())+",\"oracle\":\"\"}";}
static void bundle_geometry(){
 constexpr std::array<uint64_t,4> stages{3853756052ull,3783064464ull,3783064464ull,3780215860ull};constexpr uint64_t draft=638509378ull;
 const uint64_t total=std::accumulate(stages.begin(),stages.end(),uint64_t(draft));assert(total>4ull*1024*1024*1024&&total>8ull*1024*1024*1024&&total<=gsq_bundle::byte_cap);
 assert(stages.back()+draft>4ull*1024*1024*1024&&stages.back()+draft<8ull*1024*1024*1024&&gsq_bundle::byte_cap==16ull*1024*1024*1024&&gsq_bundle::row_cap==4096&&gsq_bundle::metadata_cap==1024*1024);
}
int main(int argc,char** argv){options_gate();bundle_geometry();assert(argc==2);fs::path root=fs::absolute(argv[1]);assert(fs::create_directory(root));
 for(bool checked:{true,false}){
  Options args;args.mini=true;args.cards=1;args.card=0;args.rank=1;args.memory="resident";args.context=64;args.retain_steps.ranges.clear();args.reset_dump=false;args.finish_dump=false;args.draft_rank=0;args.pipeline_stage=1;args.pipeline_boundaries={0,1,2};args.pipeline_ring=args.pipeline_ring_live_draft=args.pipeline_live_draft=args.pipeline_draft_partition=args.pipeline_ring_pending_provider=args.pipeline_ring_persistent_requests=true;args.pipeline_ring_check_policy=checked?"qualification":"measured";args.pipeline_ring_verify=checked;args.pipeline_ring_request_sha256=std::string(64,'a');args.output=root/(checked?"checked":"measured");fs::create_directory(args.output);
  Weights weights(args);flash::Plan plan;plan.g=Geometry::tiny();plan.g.context=64;
  for(auto name:{"position","error","token","active","next_token"})plan.buffers.push_back({name,{1},flash::Scalar::i32,0});plan.buffers.push_back({"streams",{plan.g.h*4},flash::Scalar::bf16,0});plan.buffers.push_back({"reset-test-scratch",{257},flash::Scalar::f32,0});
  Engine e(weights,args,plan);e.initialize();
  // Empty-plan Host construction selects the legacy 256MiB operator reserve,
  // exceeding the admitted aggregate ring bound. This test executes no model
  // operator: replace only that unused reserve BEFORE freezing the census.
  e.release(0,e.scratch[0]);e.scratch[0]=e.allocate(0,"reset-fixture-operator-scratch",4096,Category::scratch,Lifetime::transaction);
  pipeline::SpeculativeImage legacy(e);pipeline::OperatorStatePartition partition;std::vector<uint8_t> shared(pipeline::shared_bytes,0xab);
  {
   pipeline::ring_next::Dispatcher dispatcher(e,legacy,partition,shared.data(),shared.size(),checked,0,ownrt::ring_next::reset::digest(args.pipeline_ring_request_sha256));dispatcher.write_request_stage_metadata();save(args.output/"launch-plan.json","{}");
   const auto count=e.allocations.size();auto scratch=e.buffers[0].at("reset-test-scratch").id;
   for(int epoch=0;epoch<2;++epoch){const int sequence=epoch+1;auto destination=args.output/"requests"/std::to_string(epoch);const auto metadata=args.output/("reset-"+std::to_string(sequence)+".json");save(metadata,descriptor(destination,1,sequence,epoch));
    std::vector<uint8_t> dirt(1028,77);e.upload(0,scratch,0,dirt.data(),dirt.size());e.context_extent=64;e.lookup_ids["stale"]={1,2,3};e.fp32_sources[0]=scratch;e.fp32_extents[0]=1028;e.loaded_layer[0]=7;e.selected[0]={4};
    pipeline::Request request{11,0,0,0,0,sequence,{1,1}};auto bad=request;bad.token=1;refusal([&]{dispatcher.execute(bad);});assert(e.a.output!=destination);
    const auto reply=dispatcher.execute(request);assert(reply.sequence==sequence&&!reply.bytes&&!reply.token&&reply.rank==1&&reply.reserved[0]==1&&reply.reserved[1]==1);assert(e.allocations.size()==count&&e.a.output==destination&&e.context_extent==32&&e.alternate_context_extent==32&&!e.integer(0,"position")&&!e.integer(0,"error"));
    auto zero=e.readback(0,scratch,1028);assert(std::all_of(zero.begin(),zero.end(),[](auto b){return !b;}));assert(e.lookup_ids.empty()&&!e.fp32_sources[0]&&!e.fp32_extents[0]&&e.loaded_layer[0]==-1&&e.selected[0].empty());assert(std::all_of(shared.begin(),shared.end(),[](auto b){return !b;}));assert(fs::is_regular_file(destination/"ring-reset.json"));refusal([&]{dispatcher.execute(request);});
   }
   dispatcher.attest();
  }
  e.drain();e.shutdown();
 }
 std::cout<<"PASS actual native Dispatcher two cold resets, fixed qualification/measured parser, real Host owner zero, table reconstruction, stable allocation inventory, cache/stream coldness, monotonic epochs/sequences and stale refusals; no model arithmetic/GPU\n";
}
