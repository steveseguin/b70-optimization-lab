#pragma once
#include "wire.hpp"
#include "checkpoint_ring.hpp"
#include "engine_backend.hpp"
#include "reset_descriptor.hpp"
#include "pipeline/recursive_provider/admission.hpp"
#include "pipeline/recursive_provider/capture_ready.hpp"
// Opt-in ring24..26 and separately admitted provider27 handler. Include after existing native
// Request/Reply,half_step,publish,reverse_ready. Existing handlers20..23 untouched.
namespace pipeline::ring_next {
class Dispatcher {
 Engine& e;uint8_t* shared;size_t mapped_bytes;bool verify;
 ownrt::ring_next::wire::Context context;
 fs::path original_output;std::optional<ownrt::ring_next::reset::Descriptor> reset_spec;uint64_t reset_index=0;int accepted_output_rows=0;
 CheckpointRingFor<Engine> checkpoints;
 EngineBackend backend;
 mtp36::DraftRuntime* provider=nullptr;std::unique_ptr<pipeline::recursive_provider::Peer> peer,seed_peer;std::optional<ownrt::recursive_provider_next::Sequence> provider_sequence;std::ofstream draft_trace;uint64_t draft_trace_rows=0,draft_trace_omitted=0,provider_borrows_while_target_pending=0;
 struct ProviderCapture {int position=0;uint64_t serial=0;};std::map<uint64_t,ProviderCapture> provider_at_capture;
 std::array<uint64_t,4> provider_borrows_by_depth{};std::ofstream survival_trace;uint64_t survival_records=0,survival_rows=0,survival_advanced_records=0;
 ownrt::ring_next::StageRing<EngineBackend> ring;std::ofstream trace;uint64_t trace_rows=0,trace_omitted=0;
 std::span<uint8_t> area(size_t offset,size_t bytes){require(offset<=mapped_bytes&&bytes<=mapped_bytes-offset,"ring shared metadata bound");return {shared+offset,bytes};}
 void final_hidden(const ownrt::ring_next::Row& row,int commit_sequence,int next_token,Reply& reply){
  if(!e.a.pipeline_live_draft)return;
  require(e.a.pipeline_final()&&reverse_ready(shared).position_plus_one==uint32_t(row.position+1),"ring final raw hidden ownership");
  ownrt::live_draft::Handoff h;h.bytes=int32_t(e.stream_bytes());h.position=row.position;h.final_stage=e.a.pipeline_stage;h.stages=int32_t(e.a.pipeline_boundaries.size()-1);
  h.row_ticket=row.ticket;h.commit_sequence=commit_sequence;h.input_token=row.token;h.head=row.fixture>0;h.next_token=h.head?next_token:-1;
  const auto raw=area(ownrt::live_draft::hidden_offset,h.bytes);const auto bytes=std::vector<uint8_t>(raw.begin(),raw.end());const auto sha=hash(bytes);require(sha.size()==h.hidden_sha256.size(),"ring hidden SHA length");std::memcpy(h.hidden_sha256.data(),sha.data(),sha.size());
  ownrt::live_draft::validate(h,context.stream_bytes,context.stages,context.vocab);std::memcpy(area(ownrt::live_draft::header_offset,sizeof h).data(),&h,sizeof h);reply.bytes=h.bytes;reply.token=h.next_token;
 }
public:
 Dispatcher(Engine& owner,SpeculativeImage& legacy,const OperatorStatePartition& partition,uint8_t* mapping,size_t mapping_bytes,bool full_byte_verify,uint64_t epoch,ownrt::ring_next::Digest request,mtp36::DraftRuntime* draft=nullptr)
  :e(owner),shared(mapping),mapped_bytes(mapping_bytes),verify(full_byte_verify),
   context{epoch,request,owner.a.pipeline_stage,int(owner.a.pipeline_boundaries.size()-1),int(owner.stream_bytes()),owner.p.g.vocab,owner.a.pipeline_ring_depth},
   original_output(owner.a.output),checkpoints(owner,full_byte_verify,partition),backend(owner,legacy,checkpoints,mapping,[this]{reset_owner_state();}),provider(draft),
   ring(backend,owner.a.pipeline_final(),partition.enabled,owner.p.g.context,owner.p.g.vocab,epoch,request,ownrt::ring_next::request_prefix(request,epoch),0,owner.a.pipeline_ring_depth){
  require(shared&&mapped_bytes==shared_bytes&&owner.a.pipeline_enabled(),"ring dispatcher mapping/mode");ownrt::ring_next::wire::context(context);legacy.boundary();
  require(owner.a.pipeline_ring&&!owner.a.pipeline_wavefront,"ring exclusive owner");
  require(bool(provider)==bool(owner.a.pipeline_ring_live_draft&&owner.a.pipeline_provider())&&partition.enabled==bool(provider),"ring exact provider/partition ownership");
  if(provider){require(provider->recursive_image&&provider->live_private_recursive_inventory()==partition.draft_private,"ring recursive private image census");peer=std::make_unique<pipeline::recursive_provider::Peer>(owner.a.pipeline_ring_final_shared);if(owner.a.pipeline_provider_stage)seed_peer=std::make_unique<pipeline::recursive_provider::Peer>(owner.a.pipeline_ring_seed_shared);provider_sequence.emplace(context);draft_trace.open(e.a.output/"ring-draft-batches.jsonl");require(bool(draft_trace),"ring recursive trace open");if(owner.a.pipeline_ring_pending_provider){survival_trace.open(e.a.output/"ring-provider-survival.jsonl");require(bool(survival_trace),"provider survival trace open");}}
  checkpoints.write_layout(e.a.output/"ring-checkpoint-layout.json",owner.a.pipeline_ring_live_draft);
  trace.open(e.a.output/"ring.jsonl");require(bool(trace),"ring trace open");
 }
 bool handles_command(int op)const{return (e.a.pipeline_ring_persistent_requests&&op==11)||handles(op)||(e.a.pipeline_ring_live_draft&&provider&&op==ownrt::ring_next::wire::batch_op);}
 static bool handles(int op){return op==24||op==25||op==26;}
 Reply execute(const Request& r){
  namespace wire=ownrt::ring_next::wire;if(r.op==11)return persistent_reset(r);if(r.op==wire::batch_op)return draft_batch(r);require(handles(r.op),"ring dispatcher only owns admitted commands");
  const auto started=std::chrono::steady_clock::now();const double gpu_before=e.gemv_ms+e.nongemv_ms;
  wire::Command command{r.op,r.token,r.position,r.fixture,r.speculative,r.sequence,r.reserved[0],r.reserved[1]};
  const auto meta=wire::read<wire::RowMeta>(area(wire::row_offset,sizeof(wire::RowMeta)));
  std::vector<uint64_t> discarded;
  Reply reply{};reply.sequence=r.sequence;reply.rank=e.a.rank;reply.reserved[0]=context.stage;reply.reserved[1]=context.stage==context.stages-1;
  if(r.op==wire::row_op){
   const auto bytes=e.a.pipeline_first()?std::span<uint8_t>{}:area(slot_bytes,context.stream_bytes);std::vector<uint8_t> owned(bytes.begin(),bytes.end());
   const auto row=wire::row(meta,command,context,owned);require(!e.a.pipeline_ring_live_draft||e.a.pipeline_ring_pending_provider||!row.tentative,"quiescent ring-live refuses tentative target rows");if(e.a.pipeline_ring_live_draft&&e.a.pipeline_final())ownrt::recursive_provider::invalidate(shared);backend.stage_input(std::move(owned));const ProviderCapture captured{provider?provider->live_position():0,provider_sequence?provider_sequence->serial():0};const auto& completed=ring.execute(row);
   if(provider&&e.a.pipeline_ring_pending_provider&&row.tentative)require(provider_at_capture.emplace(row.id,captured).second,"duplicate target snapshot provider identity");
   reply.token=completed.token;reply.bytes=int32_t(completed.stream.size());
   require(completed.stream.empty()||completed.stream.size()==size_t(context.stream_bytes),"ring complete native stream result");
   if(!completed.stream.empty())std::memcpy(area(0,completed.stream.size()).data(),completed.stream.data(),completed.stream.size());
   const auto publication=wire::publication(meta,r.sequence,completed.stream);wire::write(area(wire::row_offset,sizeof publication),publication);
  }else{
   const auto row=wire::resolution(meta,command,context);const auto prior_checks=checkpoints.byte_checks();
   const int next_token=ring.oldest_result(row).token;
   std::optional<mtp36::DraftRuntime::SurvivalSnapshot> survival;std::vector<ownrt::ring_next::Row> survival_pending;
   if(r.op==wire::abort_op&&provider&&e.a.pipeline_ring_pending_provider&&e.a.pipeline_ring_verify_provider_survival){survival_pending=ring.completed_tentative_rows();require(!survival_pending.empty()&&survival_pending.front()==row,"provider survival exact oldest target");for(const auto& pending:survival_pending)require(provider_at_capture.count(pending.id),"missing provider identity at target snapshot");survival=provider->capture_survival(*provider_sequence);}
   const auto resolved=r.op==wire::accept_op?ring.accept(r.sequence,row,r.token):ring.abort_suffix(r.sequence,row);
   if(survival){auto after=provider->verify_survival(*survival,*provider_sequence);write_survival(r,row,resolved,*survival,after,survival_pending);}
   if(provider&&e.a.pipeline_ring_pending_provider){if(r.op==wire::accept_op)provider_at_capture.erase(row.id);else for(auto id:resolved.discarded)provider_at_capture.erase(id);}
   discarded=resolved.discarded;if(r.op==wire::accept_op&&row.fixture>0)++accepted_output_rows;
   if(r.op==wire::accept_op&&e.a.pipeline_first()&&e.a.pipeline_provider_stage){
    ownrt::recursive_provider::SeedRecord accepted;accepted.published_sequence=r.sequence;accepted.physical=ring.physical();accepted.committed=ring.committed();accepted.row=meta;accepted.row.publication_ticket=row.ticket;
    require(ownrt::recursive_provider::seed_row(accepted,context)==row,"stage0 accepted seed publication identity");ownrt::recursive_provider::publish_seed(shared,accepted);
   }
   const auto acknowledgment=wire::acknowledgment(context,r.sequence,row,resolved,checkpoints.byte_checks()>prior_checks);
   wire::write(area(wire::ack_offset,sizeof acknowledgment),acknowledgment);
   if(r.op==wire::accept_op&&e.a.pipeline_final()){
    if(e.a.pipeline_ring_live_draft){Reply ignored{};final_hidden(row,r.sequence,next_token,ignored);ownrt::recursive_provider::FinalRecord record;record.stage=context.stage;record.published_sequence=r.sequence;record.row=meta;record.row.publication_ticket=row.ticket;std::memcpy(&record.hidden,area(ownrt::live_draft::header_offset,sizeof(record.hidden)).data(),sizeof(record.hidden));ownrt::recursive_provider::validate_final_record(record,context,area(ownrt::live_draft::hidden_offset,context.stream_bytes));ownrt::recursive_provider::publish(shared,record);}
    else final_hidden(row,r.sequence,next_token,reply);
   }
  }
  if(trace_rows<size_t(e.a.pipeline_ring_trace_limit)){
   trace<<"{\"op\":"<<r.op<<",\"sequence\":"<<r.sequence<<",\"row_id\":"<<meta.id<<",\"parent_id\":"<<meta.parent<<",\"position\":"<<meta.position<<",\"token\":"<<meta.token<<",\"fixture\":"<<meta.fixture<<",\"tentative\":"<<((meta.flags&wire::tentative)?"true":"false")<<",\"physical\":"<<ring.physical()<<",\"committed\":"<<ring.committed()<<",\"pending\":"<<ring.pending()<<",\"discarded\":[";
   for(size_t i=0;i<discarded.size();++i)trace<<(i?",":"")<<discarded[i];trace<<"]}\n";trace.flush();require(bool(trace),"ring trace write");++trace_rows;
  }else ++trace_omitted;
  reply.busy_ms=Engine::ms(started);reply.gpu_ms=e.gemv_ms+e.nongemv_ms-gpu_before;
  return reply;
 }
#include "pipeline/recursive_provider/survival_writer.inc"
#include "pipeline/ring/persistent_reset.inc"
 Reply draft_batch(const Request& request){
  namespace wire=ownrt::ring_next::wire;
  require(e.a.pipeline_ring_live_draft&&provider&&peer&&provider_sequence&&request.op==wire::batch_op,"ring recursive command owner");
  const auto started=std::chrono::steady_clock::now();const double gpu=e.gemv_ms+e.nongemv_ms;
  provider->recursive_idle();const auto pending=ring.pending();
  if(e.a.pipeline_ring_pending_provider){require(pending<=size_t(context.depth)&&ring.physical()==ring.committed()+int(pending),"pending provider target cursors");require(ring.completed_tentative_rows().size()==pending,"pending provider completed target inventory");checkpoints.borrow_boundary(pending);}
  else {require(!pending,"quiescent ring-live requires no pending target");ring.boundary();checkpoints.boundary();}
  std::optional<ownrt::recursive_provider::SeedRecord> accepted;
  if(seed_peer)accepted=seed_peer->capture_seed(context,e.a.output/"ring-seed-peer.json");
  const auto seed=accepted?ownrt::recursive_provider::seed_row(*accepted,context):ring.last_accepted();
  require(seed.position>0&&(ring.committed()==seed.position+1||(accepted&&ring.committed()==seed.position)),"ring recursive accepted seed frontier");
  const auto event=peer->capture(context,e.a.output/"ring-final-peer.json");
  auto admitted=pipeline::recursive_provider::admit_batch(request,context,seed,event,area(wire::row_offset,sizeof(wire::RowMeta)),area(ownrt::live_draft::header_offset,sizeof(ownrt::live_draft::Handoff)),area(slot_bytes,context.stream_bytes),provider_sequence->serial()+1);
  const auto& input=admitted.input;const auto& pair=admitted.expected;
  const auto batch=ring.draft(request.sequence,[&](){
   if(e.a.pipeline_ring_parent_capture_ack){
    // Validate the complete sequence before releasing the independent final
    // owner. Admission owns all remaining header/hidden bytes by value.
    provider_sequence->admit(input,pair);
    auto captured=ownrt::recursive_provider::captured(context,seed,event.record,request.sequence,pair.provider_serial);
    Reply ready{};ready.status=ownrt::recursive_provider::capture_ready_status;ready.token=-1;ready.bytes=sizeof captured;ready.sequence=request.sequence;ready.rank=e.a.rank;ready.reserved[0]=context.stage;ready.busy_ms=Engine::ms(started);
    transfer(e.a.channel,&ready,sizeof ready,true,e.a.seconds);
    transfer(e.a.channel,&captured,sizeof captured,true,e.a.seconds);
   }
   return provider->live_recursive_depth2(*provider_sequence,input,pair,e.a.pipeline_ring_recursive_verify);
  });
  ++provider_borrows_by_depth[pending];provider_borrows_while_target_pending+=pending?1:0;
  const auto& result=provider_sequence->last_result();
  if(context.depth==2)wire::write(area(wire::proposal_offset,sizeof batch),batch);
  else {wire::ProposalMetaV2 extended;extended.base=batch;extended.guess2=result.guesses.size()<3?-1:result.guesses[2];wire::write(area(wire::proposal_offset,sizeof extended),extended);}
  if(draft_trace_rows<size_t(e.a.pipeline_ring_trace_limit)){
   draft_trace<<"{\"sequence\":"<<request.sequence<<",\"provider_serial\":"<<batch.provider_serial<<",\"target_pending_depth\":"<<pending<<",\"seed_row\":"<<batch.seed_row<<",\"parent_row\":"<<batch.parent_row<<",\"seed_position\":"<<batch.seed_position<<",\"confirmed_token\":"<<seed.token<<",\"fixture\":"<<seed.fixture<<",\"parent_final_ticket\":"<<input.parent.row_ticket<<",\"parent_final_commit\":"<<input.parent.commit_sequence<<",\"hidden_sha256\":"<<ownrt::quote(hash(input.hidden))<<",\"seed_accept_sequence\":"<<(accepted?accepted->published_sequence:0)<<",\"seed_journal_sha256\":"<<ownrt::quote(accepted?hash(std::vector<uint8_t>(reinterpret_cast<const uint8_t*>(&*accepted),reinterpret_cast<const uint8_t*>(&*accepted)+sizeof(*accepted))):std::string{})<<",\"guesses\":[";
   for(size_t i=0;i<result.guesses.size();++i)draft_trace<<(i?",":"")<<result.guesses[i];draft_trace<<"],\"restored_position\":"<<batch.restored_position<<",\"snapshot_bytes\":"<<result.snapshot_bytes<<",\"mutable_bytes_verified\":"<<(result.byte_verified?"true":"false")<<",\"canonical_ms\":"<<result.canonical_ms<<",\"capture_ms\":"<<result.capture_ms<<",\"recursive_ms\":"<<result.recursive_ms<<",\"restore_ms\":"<<result.restore_ms<<"}\n";draft_trace.flush();require(bool(draft_trace),"ring recursive trace write");++draft_trace_rows;
  }else ++draft_trace_omitted;
  Reply reply{};reply.sequence=request.sequence;reply.rank=e.a.rank;reply.reserved[0]=context.stage;reply.reserved[1]=0;reply.token=batch.guess0;reply.bytes=context.depth==3?sizeof(wire::ProposalMetaV2):sizeof batch;reply.busy_ms=Engine::ms(started);reply.gpu_ms=e.gemv_ms+e.nongemv_ms-gpu;return reply;
 }
 // RESET is admitted only by the separate persistent capability. Provider27
 // retains explicit quiescent or completed-tentative admission.
 void attest(const fs::path& destination={},int dump_marker=-1){
  ring.boundary();checkpoints.boundary();const int position=e.integer(0,"position");
  require(position==ring.committed()&&uint64_t(position)==ring.commits,"ring canonical position/commit conservation");
  require(e.bank_parity==(e.a.pipeline_first()?unsigned(position%2):0u),"ring canonical bank parity");
  require(ring.rows==ring.commits+ring.discarded_rows&&ring.tentative_rows==ring.accepted_tentative_rows+ring.discarded_rows,"ring row conservation");
  require(checkpoints.captures()==ring.tentative_rows&&checkpoints.releases()==checkpoints.captures()&&checkpoints.restores()==ring.abort_count,"ring snapshot conservation");
  require((!ring.abort_count&&!ring.discarded_rows)||(ring.abort_count<=ring.discarded_rows&&ring.discarded_rows<=uint64_t(context.depth)*ring.abort_count),"ring suffix count conservation");
  auto file_hash=[&](const fs::path& path,size_t limit){
   const int fd=::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK);require(fd>=0,"ring evidence open");
   struct Close {int fd;~Close(){::close(fd);}} close{fd};struct stat before{},after{},named{};
   require(!::fstat(fd,&before)&&S_ISREG(before.st_mode)&&before.st_size>0&&uint64_t(before.st_size)<=limit,"ring bounded regular evidence");
   std::vector<uint8_t> bytes(size_t(before.st_size));size_t done=0;
   while(done<bytes.size()){auto n=::pread(fd,bytes.data()+done,bytes.size()-done,off_t(done));if(n<0&&errno==EINTR)continue;require(n>0,"ring bounded evidence read");done+=size_t(n);}
   require(!::fstat(fd,&after)&&!::lstat(path.c_str(),&named)&&S_ISREG(named.st_mode)&&before.st_dev==after.st_dev&&before.st_ino==after.st_ino&&before.st_size==after.st_size&&before.st_mtim.tv_sec==after.st_mtim.tv_sec&&before.st_mtim.tv_nsec==after.st_mtim.tv_nsec&&before.st_ctim.tv_sec==after.st_ctim.tv_sec&&before.st_ctim.tv_nsec==after.st_ctim.tv_nsec&&before.st_dev==named.st_dev&&before.st_ino==named.st_ino,"ring evidence identity changed");return hash(bytes);
  };
  if(e.a.pipeline_ring_live_draft&&!e.a.pipeline_ring_pending_provider){require(!ring.tentative_rows&&!ring.abort_count&&!ring.discarded_rows&&!checkpoints.captures(),"initial ring-live must contain only verified target rows");require(!provider_borrows_while_target_pending,"initial ring-live cannot borrow pending target");}
  if(provider){provider->recursive_idle();require(provider->recursive_healthy()&&!provider->recursive_active&&provider->live_position()==std::max(0,position-1)&&provider_sequence->serial()==uint64_t(provider->live_position()),"ring canonical provider quiescence/position");require(provider->recursive_captures==provider->recursive_restores&&provider->recursive_verified_restores<=provider->recursive_restores,"ring recursive checkpoint conservation");}
  const auto layout=file_hash(e.a.output/"ring-checkpoint-layout.json",1024*1024);
  std::string seal;if(dump_marker>=0)seal=file_hash(e.a.output/("state-"+std::to_string(dump_marker))/"state-seal.txt",4096);
  std::ostringstream o;o<<"{\"schema\":"<<ownrt::quote(e.a.pipeline_ring_persistent_requests?(context.depth==3?"ownrt.ring-state.persistent.v2":"ownrt.ring-state.persistent.v1"):e.a.pipeline_ring_pending_provider?"ownrt.ring-state.pending-provider.v1":(e.a.pipeline_ring_live_draft?"ownrt.ring-state.live.v1":"ownrt.ring-state.v1"))<<",\"mode\":"<<ownrt::quote(e.a.pipeline_ring_persistent_requests?"persistent-rolling":e.a.pipeline_ring_pending_provider?"verified-ring-pending-provider":(e.a.pipeline_ring_live_draft?"verified-ring-live":"verified-ring"))<<",\"stage_id\":"<<context.stage<<",\"ring_request_sha256\":"<<ownrt::quote(e.a.pipeline_ring_request_sha256)<<",\"ring_epoch\":"<<context.epoch<<",\"ring_capacity\":"<<context.depth<<",\"depth\":"<<context.depth<<",\"dump_marker\":"<<dump_marker<<",\"state_seal_sha256\":"<<ownrt::quote(seal)<<",\"checkpoint_layout_sha256\":"<<ownrt::quote(layout)
   <<",\"actual_position\":"<<position<<",\"committed_position\":"<<ring.committed()<<",\"pending_tickets\":0,\"active_slots\":0,\"sticky_error\":0,\"rows\":"<<ring.rows<<",\"tentative_rows\":"<<ring.tentative_rows<<",\"commits\":"<<ring.commits<<",\"accepted_tentative_rows\":"<<ring.accepted_tentative_rows<<",\"abort_count\":"<<ring.abort_count<<",\"discarded_rows\":"<<ring.discarded_rows<<",\"snapshot_captures\":"<<checkpoints.captures()<<",\"snapshot_releases\":"<<checkpoints.releases()<<",\"byteverified_restore_count\":"<<checkpoints.byte_checks()<<",\"saved_bytes\":"<<checkpoints.captures()*checkpoints.slot_bytes()<<",\"target_mutable_checkpoint_bytes\":"<<checkpoints.slot_bytes()
   <<",\"restore_verification_enabled\":"<<(verify?"true":"false")<<",\"all_aborts_byte_verified\":"<<((!e.a.pipeline_ring_persistent_requests||verify)&&checkpoints.byte_checks()==ring.abort_count?"true":"false")<<",\"max_pending\":"<<ring.max_pending<<",\"trace_records\":"<<trace_rows<<",\"trace_omitted\":"<<trace_omitted<<",\"bank_parity\":"<<e.bank_parity<<",\"inactive_alternate_banks\":[";
  bool comma=false;for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name);comma=true;}o<<"],\"canonical_bank_mapping\":{";comma=false;
  for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name)<<":{\"active_allocation\":"<<e.buffers[0].at(name).id<<",\"inactive_allocation\":"<<id<<"}";comma=true;}o<<"}";
  if(e.a.pipeline_ring_live_draft){std::string draft_seal;if(provider&&dump_marker>=0)draft_seal=file_hash(e.a.output/("state-"+std::to_string(dump_marker)+".draft")/"state-seal.txt",4096);
   o<<",\"provider_borrow_mode\":"<<ownrt::quote(e.a.pipeline_ring_pending_provider?"pending-target":"quiescent-target")<<",\"provider_stage\":"<<e.a.pipeline_provider_stage<<",\"provider_present\":"<<(provider?"true":"false")<<",\"provider_borrows_while_target_pending\":"<<provider_borrows_while_target_pending<<",\"canonical_draft_state_seal_sha256\":"<<ownrt::quote(draft_seal)<<",\"provider_position\":";
   if(provider)o<<provider->live_position();else o<<"null";
   o<<",\"provider_serial\":"<<(provider_sequence?provider_sequence->serial():0)<<",\"provider_commands\":"<<(provider_sequence?provider_sequence->serial():0)<<",\"provider_recursive_active\":false,\"provider_snapshot_captures\":"<<(provider?provider->recursive_captures:0)<<",\"provider_snapshot_restores\":"<<(provider?provider->recursive_restores:0)<<",\"provider_byteverified_restore_count\":"<<(provider?provider->recursive_verified_restores:0)<<",\"provider_restore_verification_enabled\":"<<(e.a.pipeline_ring_recursive_verify?"true":"false")<<",\"provider_all_restores_byte_verified\":"<<((!e.a.pipeline_ring_persistent_requests||bool(provider&&e.a.pipeline_ring_recursive_verify))&&(!provider||provider->recursive_restores==provider->recursive_verified_restores)?"true":"false")<<",\"provider_private_bytes\":"<<(provider?provider->recursive_bytes:0)<<",\"provider_canonical_allocation_count\":"<<(provider?provider->live_mutable_inventory().size()+provider->live_pinned_inventory().size():0)<<",\"provider_trace_records\":"<<draft_trace_rows<<",\"provider_trace_omitted\":"<<draft_trace_omitted;
  }
  if(e.a.pipeline_ring_pending_provider){
   require(provider_at_capture.empty(),"pending provider capture provenance remains at boundary");
   require(!provider||(provider_borrows_by_depth[0]+provider_borrows_by_depth[1]+provider_borrows_by_depth[2]+provider_borrows_by_depth[3]==provider_sequence->serial()&&provider_borrows_while_target_pending==provider_borrows_by_depth[1]+provider_borrows_by_depth[2]+provider_borrows_by_depth[3]&&(e.a.pipeline_ring_verify_provider_survival?(survival_records==ring.abort_count&&survival_rows==ring.discarded_rows):(!survival_records&&!survival_rows&&!survival_advanced_records))),"pending provider borrow/survival accounting");
   std::string survival_sha;if(provider){survival_trace.flush();require(bool(survival_trace),"survival trace seal flush");if(survival_records)survival_sha=file_hash(e.a.output/"ring-provider-survival.jsonl",16ull*1024*1024);else survival_sha=ownrt::provider_survival::sha(std::string{});}
   o<<",\"provider_pending_borrows\":{\"1\":"<<provider_borrows_by_depth[1]<<",\"2\":"<<provider_borrows_by_depth[2];if(context.depth==3)o<<",\"3\":"<<provider_borrows_by_depth[3];o<<"},\"provider_quiescent_borrows\":"<<provider_borrows_by_depth[0]<<",\"provider_survival_verification_enabled\":"<<(e.a.pipeline_ring_verify_provider_survival?"true":"false")<<",\"provider_survival_records\":"<<survival_records<<",\"provider_survival_discarded_rows\":"<<survival_rows<<",\"provider_survival_advanced_records\":"<<survival_advanced_records<<",\"provider_survival_receipt_sha256\":"<<ownrt::quote(survival_sha)<<",\"provider_survival_bytes_verified\":"<<survival_records<<",\"provider_survival_host_verified\":"<<survival_records<<",\"provider_survival_sequence_verified\":"<<survival_records<<",\"provider_survival_private_verified\":"<<survival_records<<",\"provider_survival_bindings_verified\":"<<survival_records;
  }
  if(e.a.pipeline_ring_persistent_requests){
   o<<",\"verification_policy\":"<<ownrt::quote(e.a.pipeline_ring_check_policy)<<",\"reset_index\":"<<reset_index
    <<",\"target_restore_byte_checks_enabled\":"<<(verify?"true":"false")<<",\"provider_recursive_byte_checks_enabled\":"<<(provider&&e.a.pipeline_ring_recursive_verify?"true":"false")<<",\"provider_abort_survival_checks_enabled\":"<<(provider&&e.a.pipeline_ring_verify_provider_survival?"true":"false")
    <<",\"target_snapshot_restores\":"<<checkpoints.restores()<<",\"target_host_restore_checks\":"<<checkpoints.restores()<<",\"provider_host_restore_checks\":"<<(provider?provider->recursive_restores:0)<<",\"provider_canonical_commands_checked\":"<<(provider_sequence?provider_sequence->serial():0);
  }
  o<<"}";
  const auto path=destination.empty()?e.a.output/"ring-quiescence.json":destination;
  const auto text=o.str();struct stat prior{};const int found=::lstat(path.c_str(),&prior);
  if(!found){require(dump_marker>=0&&S_ISREG(prior.st_mode),"ring attestation destination already exists or is not regular");const std::vector<uint8_t> expected(text.begin(),text.end());require(file_hash(path,1024*1024)==hash(expected),"ring sealed attestation changed");}
  else {require(errno==ENOENT,"ring attestation destination lookup");const int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);require(fd>=0,"ring fresh attestation create");struct Close{int fd;~Close(){::close(fd);}} close{fd};size_t done=0;while(done<text.size()){auto n=::write(fd,text.data()+done,text.size()-done);if(n<0&&errno==EINTR)continue;require(n>0,"ring attestation write");done+=size_t(n);}}
 }
 void reply_published(int op){if(op==ownrt::ring_next::wire::row_op&&e.a.rank==1)e.reply_report.published();}
 void boundary(){ring.boundary();}
};
}
