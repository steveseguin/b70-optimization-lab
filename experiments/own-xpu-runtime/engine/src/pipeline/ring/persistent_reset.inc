// Included inside Dispatcher. Ring-only persistent boundary; no allocation or
// process replacement, arithmetic change, oracle change or recovery after error.
std::string allocation_identity(){
 std::ostringstream out;out<<e.dev(0).generation()<<'\n';
 auto item=[&](Allocation id,int card){const auto& row=e.dev(card).arena.row(id);require(row.live,"reset dead allocation");out<<id<<' '<<card<<' '<<row.bytes<<' '<<int(row.memory)<<' '<<int(row.category)<<' '<<uintptr_t(row.pointer)<<' '<<ownrt::quote(row.label)<<'\n';};
 for(const auto& [id,where]:e.allocations)item(id,where.first);
 if(provider)for(auto id:provider->live_pinned_inventory())item(id,0);
 const auto text=out.str();return hash(std::vector<uint8_t>(text.begin(),text.end()));
}
void reset_owner_state(){
 require(e.a.pipeline_ring_persistent_requests&&reset_spec.has_value(),"ring reset owner callback admission");
 require(prefill_replay.empty(),"ring reset retains unreplayed prefill chunk");
 prefill_replay.clear();
 Candidate empty;const auto& d=*reset_spec;
 pipeline::request_reset(e,empty,provider,{},accepted_output_rows,std::pair<fs::path,std::string>{d.destination,d.oracle});
 // Existing backing allocations stay live; logical cache contents become cold.
 std::fill(e.loaded_layer.begin(),e.loaded_layer.end(),-1);
 if(provider)provider->recursive_reset_after_owner_zero();
}
void write_request_stage_metadata(){
 require(e.a.pipeline_ring_persistent_requests,"ring persistent stage metadata owner");
 std::ostringstream o;o<<"{\"schema\":\"ownrt.pipeline-stage.v1\",\"stage_id\":"<<context.stage<<",\"stage_count\":"<<context.stages
  <<",\"begin\":"<<e.a.pipeline_boundaries[context.stage]<<",\"end\":"<<e.a.pipeline_boundaries[context.stage+1]
  <<",\"provider_stage\":"<<e.a.pipeline_provider_stage<<",\"provider_present\":"<<(provider?"true":"false")<<",\"first\":"<<(e.a.pipeline_first()?"true":"false")<<",\"final\":"<<(e.a.pipeline_final()?"true":"false")
  <<",\"activation_dtype\":\"F32\",\"stream_bytes\":"<<context.stream_bytes<<",\"boundaries\":[";
 for(size_t i=0;i<e.a.pipeline_boundaries.size();++i)o<<(i?",":"")<<e.a.pipeline_boundaries[i];
 o<<"],\"mode\":\"persistent-rolling\",\"speculation_enabled\":true,\"inactive_alternate_banks\":[";bool comma=false;
 for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name);comma=true;}
 o<<"],\"ring_capacity\":"<<context.depth<<",\"depth\":"<<context.depth<<",\"ring_epoch\":"<<context.epoch<<",\"ring_request_sha256\":"<<ownrt::quote(e.a.pipeline_ring_request_sha256)
  <<",\"provider_borrow_mode\":\"pending-target\",\"verification_policy\":"<<ownrt::quote(e.a.pipeline_ring_check_policy)<<",\"persistent_requests\":true}";
 if(context.depth==3){auto text=o.str();text.pop_back();text+=",\"ring_depth\":3}";save(e.a.output/"pipeline-stage.json",text);}else save(e.a.output/"pipeline-stage.json",o.str());
}
Reply persistent_reset(const Request& request){
 namespace wire=ownrt::ring_next::wire;namespace reset=ownrt::ring_next::reset;
 require(e.a.pipeline_ring_persistent_requests&&request.op==11&&!request.token&&!request.position&&!request.fixture&&!request.speculative&&request.reserved[0]==context.stage&&request.reserved[1]==int(e.a.pipeline_final()),"ring reset command admission");
 require(!reset_spec&&!e.poisoned&&!e.progress_pending&&!e.progress_callback&&!e.preparing_commands&&!e.draft_timing&&!e.correction_exchange&&!e.head_export&&!e.head_publish&&!e.head_merge&&!e.prepare_async&&!e.dev(0).before_compute&&!e.dev(0).after_compute,"ring reset queued owner refusal");
 bool dedicated_reset_complete=false;
 struct DedicatedPoison {Engine* owner;bool& complete;~DedicatedPoison(){if(owner&&!complete)owner->poisoned=true;}};
 DedicatedPoison poison{dedicated_suite?&e:nullptr,dedicated_reset_complete};
 const auto metadata=original_output/("reset-"+std::to_string(request.sequence)+".json");
 std::optional<ownrt::provider_only::suite::Prepared> prompt_transition;
 const auto d=[&]{
  if(dedicated_suite){
   require(e.a.oracle.empty(),"dedicated target reset has no oracle");
   prompt_transition.emplace(dedicated_suite->prepare(metadata,original_output,context,context.stage,request.sequence,true));
   return prompt_transition->descriptor;
  }
  return reset::load(metadata,original_output,context.epoch,e.a.pipeline_ring_request_sha256,context.stage,request.sequence,e.a.oracle.string());
 }();
 require(prefill_replay.empty(),"ring reset retains unreplayed prefill chunk");
 ring.boundary();checkpoints.boundary();require(provider_at_capture.empty(),"ring reset retains capture provenance");
 if(provider){provider->recursive_idle();require(!provider->recursive_active&&!provider_sequence->poisoned()&&provider->recursive_healthy()&&provider->live_position()==std::max(0,ring.committed()-1)&&provider_sequence->serial()==uint64_t(provider->live_position()),"ring reset canonical provider frontier");peer->request_boundary();if(seed_peer)seed_peer->request_boundary();}
 attest(); // seal the old request once, before its state or output path changes
 const auto inventory_before=allocation_identity();const int previous_position=ring.committed();const auto old_output=e.a.output;
 reset_spec=d;
 ring.reset(request.sequence,d.next_epoch,reset::digest(d.next_request),ownrt::ring_next::request_prefix(reset::digest(d.next_request),d.next_epoch));
 reset_spec.reset();
 context.epoch=d.next_epoch;context.request=reset::digest(d.next_request);e.a.pipeline_ring_request_sha256=d.next_request;
 if(provider){provider_sequence.emplace(context);peer->request_boundary();if(seed_peer)seed_peer->request_boundary();}
 require(e.a.output==d.destination&&allocation_identity()==inventory_before,"ring reset physical allocation identity");
 if(prompt_transition){
  require(bool(bulk_prompt)&&!dedicated_bulk_map.empty(),"dedicated target retained prompt/map");
  bulk_prompt=prompt_transition->release_after_owner_reset(context);
  // Every peer must already be quiescent. Invalidate only THIS owner's map:
  // transport header, all4 slots, raw forward/reverse rows and bulk records.
  std::fill(dedicated_bulk_map.begin(),dedicated_bulk_map.end(),uint8_t(0));
 }
 std::memset(shared,0,mapped_bytes);accepted_output_rows=0;provider_at_capture.clear();provider_borrows_by_depth.fill(0);provider_borrows_while_target_pending=0;
 survival_records=survival_rows=survival_advanced_records=draft_trace_rows=draft_trace_omitted=trace_rows=trace_omitted=0;
 auto reopen=[&](std::ofstream& stream,const char* name){stream.close();stream.clear();stream.open(e.a.output/name);require(bool(stream),"ring reset trace open");};
 reopen(trace,"ring.jsonl");if(provider){reopen(draft_trace,"ring-draft-batches.jsonl");reopen(survival_trace,"ring-provider-survival.jsonl");}
 for(const auto* name:{"launch-plan.json","ring-checkpoint-layout.json"}){require(fs::is_regular_file(original_output/name),"ring reset immutable sidecar missing");fs::copy_file(original_output/name,e.a.output/name,fs::copy_options::none);}
 write_request_stage_metadata();
 ring.boundary();checkpoints.boundary();require(!ring.physical()&&!ring.committed()&&!ring.pending()&&!e.integer(0,"error")&&!e.bank_parity&&!e.prefill_bank_parity_bias&&e.context_extent==32&&e.alternate_context_extent==32,"ring reset cold target boundary");
 require(!provider||(provider->live_position()==0&&provider->live_extent()==32&&!provider_sequence->serial()&&!provider->recursive_captures&&!provider->recursive_restores&&!provider->recursive_verified_restores&&!provider->recursive_active),"ring reset cold provider boundary");
 const auto inventory_after=allocation_identity();require(inventory_after==inventory_before,"ring reset final allocation identity");
 const auto metadata_sha=hash(std::vector<uint8_t>(d.raw.begin(),d.raw.end()));
 std::string provider_host_sha,provider_sequence_sha;
 if(provider){const auto host=provider->survival_host_json(provider->recursive_host_state()),sequence=provider_sequence->survival_identity();provider_host_sha=hash(std::vector<uint8_t>(host.begin(),host.end()));provider_sequence_sha=hash(std::vector<uint8_t>(sequence.begin(),sequence.end()));}
 // Reset maintenance, descriptor upload and control readbacks finish before the
 // next request's counters start. No device work follows this counter boundary.
 e.drain();e.submission_card=-1;e.current_cls=0;e.host_waits=0;e.parity_argument_checks=0;
 e.wait_ms=e.prepare_ms=e.enqueue_ms=e.enqueue_including_wait_ms=0;e.gemv_ms=e.nongemv_ms=e.transfer_ms=0;
 e.submitted=e.max_submission_ns=0;e.retirement_ms=e.profiling_ms=0;e.retirement_calls=e.capacity_reprepares=0;
 e.correction_exchange_calls=e.correction_send_bytes=e.correction_receive_bytes=0;e.family_ms.fill(0);
 std::fill(e.class_ms.begin(),e.class_ms.end(),0);std::fill(e.class_launches.begin(),e.class_launches.end(),0);std::fill(e.class_groups.begin(),e.class_groups.end(),0);
 ++reset_index;std::ostringstream out;out<<"{\"schema\":\"ownrt.ring-reset.v1\",\"passed\":true,\"stage_id\":"<<context.stage<<",\"global_sequence\":"<<request.sequence
  <<",\"previous_epoch\":"<<d.previous_epoch<<",\"next_epoch\":"<<d.next_epoch<<",\"previous_request_sha256\":"<<ownrt::quote(d.previous_request)<<",\"next_request_sha256\":"<<ownrt::quote(d.next_request)
  <<",\"destination\":"<<ownrt::quote(d.destination.string())<<",\"oracle\":"<<ownrt::quote(d.oracle)<<",\"metadata_sha256\":"<<ownrt::quote(metadata_sha)<<",\"reset_index\":"<<reset_index<<",\"previous_target_position\":"<<previous_position
  <<",\"target_position\":0,\"target_physical\":0,\"target_committed\":0,\"target_pending\":0,\"draft_position\":"<<(provider?"0":"null")<<",\"provider_serial\":"<<(provider?"0":"null")
  <<",\"context_extent\":32,\"alternate_extent\":32,\"draft_context_extent\":"<<(provider?"32":"null")<<",\"pending_ticket\":false,\"sticky_error\":0,\"allocation_ids_preserved\":true"
  <<",\"allocation_inventory_before_sha256\":"<<ownrt::quote(inventory_before)<<",\"allocation_inventory_after_sha256\":"<<ownrt::quote(inventory_after)<<",\"provider_cold_host_sha256\":"<<ownrt::quote(provider_host_sha)<<",\"provider_cold_sequence_sha256\":"<<ownrt::quote(provider_sequence_sha)
  <<",\"cold_state_byte_verified\":false,\"counters_reset\":true,\"trace_reset\":true,\"shared_publication_invalidated\":true,\"check_policy\":"<<ownrt::quote(e.a.pipeline_ring_check_policy)<<"}";
 if(prompt_transition){
  auto text=out.str();text.pop_back();
  text+=",\"dedicated_suite_sha256\":"+ownrt::quote(d.prompt.suite_sha)+
   ",\"dedicated_prompt_sha256\":"+ownrt::quote(d.prompt.prompt_sha)+
   ",\"dedicated_prompt_index\":"+std::to_string(d.prompt.index)+
   ",\"dedicated_bulk_map_invalidated_bytes\":"+std::to_string(dedicated_bulk_map.size())+"}";
  out.str(text);
 }
 save(e.a.output/"ring-reset.json",out.str());
 Reply reply{};reply.sequence=request.sequence;reply.rank=e.a.rank;reply.reserved[0]=context.stage;reply.reserved[1]=e.a.pipeline_final();dedicated_reset_complete=true;return reply;
}
