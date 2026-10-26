#include "checkpoint_fixture.hpp"
struct ProviderOwner:FixtureOwner {
 bool preparing_commands=false,draft_timing=false;int current_cls=9,drains=0;
 void drain(){++drains;FixtureOwner::drain();if(progress_callback)progress_callback();}
 using FixtureOwner::FixtureOwner;
};
// Executes the ACTUAL member extension and checked Host copy transport. Only the
// arithmetic entry points below are synthetic; no model kernels/GPU are invoked.
class FixtureDraft {
 ProviderOwner& e;
 struct FixturePrepared {Spec spec;std::vector<Allocation> bindings;p49d::Submit submit=nullptr;};std::map<const flash::Launch*,FixturePrepared> prepared;
 struct Site {std::vector<ownrt::PreparedCompute> commands;bool gemv=false;int cls=0;bool head=false;};std::vector<Site> issue_sites;uint64_t shared_copy_count=0;
 struct Plan {struct Geometry{int context=64,vocab=97;}g;}p;
 std::set<Allocation> mutable_ids;std::map<std::string,Allocation> names;
 Allocation publication{},half_staging{};size_t allocated=0;int position=0,context_extent=32;
 bool disabled=false,async_pending=false,pending_head=false,captured=true;int pending_confirmed=0;
 ownrt::Event publication_event=0;std::chrono::steady_clock::time_point pending_start;
 int depth_probe=0,queued_probe=-1,queued_confirmed=-1;const void* reverse_hidden=nullptr;std::vector<uint8_t> probe_reverse_hidden;
 Allocation id(const std::string& name)const{return names.at(name);}
 void admit_position(int extent=0){context_extent=extent?extent:std::min(p.g.context,((position+32)/32)*32);}
 int compute(int token,int target_position,bool head,bool asynchronous=false,bool recursive=false){
  assert(!asynchronous&&target_position==position+1);admit_position();++position;
  for(auto allocation:mutable_ids){const auto& row=e.dev(0).arena.row(allocation);if(allocation==id("error"))continue;std::memset(row.pointer,token+position,row.bytes);}
  std::memcpy(e.dev(0).arena.row(id("position")).pointer,&position,4);
  std::memset(e.dev(0).arena.row(publication).pointer,token,8);std::memset(e.dev(0).arena.row(half_staging).pointer,position,4+e.stream_bytes());probe_reverse_hidden.assign(e.stream_bytes(),uint8_t(token));pending_head=head;pending_confirmed=token;e.current_cls=77;
  if(recursive&&corrupt_target)e.history0=999;
  return head?(token+position*7)%p.g.vocab:-1;
 }
 int live_step(int token,int target_position,bool head,const void* hidden,size_t bytes){assert(hidden&&bytes==e.stream_bytes());const int saved_class=e.current_cls;const int out=compute(token,target_position,head);e.current_cls=saved_class;canonical_bytes=read_canonical();canonical_host=recursive_host_state();return out;}
public:
 using DraftRuntime=FixtureDraft;
#include "pipeline/recursive_provider/draft_runtime_extension.inc"
#include "pipeline/recursive_provider/pending_survival.inc"
 bool corrupt_target=false;std::map<Allocation,std::vector<uint8_t>> canonical_bytes;RecursiveHost canonical_host;
 explicit FixtureDraft(ProviderOwner& owner):e(owner){
  for(int i=0;i<71;++i){std::string name=i==0?"error":i==1?"position":"scratch"+std::to_string(i);const std::array<size_t,9> edges{1,15,16,17,4095,4096,4097,8192,8193};const size_t bytes=i<2?4:edges[size_t(i-2)%edges.size()];auto allocation=e.allocate(0,"draft:"+name,bytes,Category::scratch,Lifetime::transaction);names[name]=allocation;mutable_ids.insert(allocation);allocated+=bytes;}
  publication=e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned);half_staging=e.allocate(0,"draft:half-staging",4+e.stream_bytes(),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
  prepare_recursive_depth2();
  prepared[nullptr].spec.extent=32;prepared[nullptr].bindings={id("position")};issue_sites.resize(1);issue_sites[0].commands.resize(1);auto& command=issue_sites[0].commands[0];command.ids={id("position")};command.pointers={e.dev(0).arena.row(id("position")).pointer};command.argument_bytes={1,2,3};command.operation_bytes={4,5};command.copy_counter=&shared_copy_count;
 }

 void mutation_checks(const ownrt::recursive_provider_next::Sequence& sequence){
  auto baseline=capture_survival(sequence);
  for(auto allocation:{id("scratch2"),publication,half_staging,recursive_image}){auto* data=static_cast<uint8_t*>(e.dev(0).arena.row(allocation).pointer);data[0]^=1;refusal([&]{verify_survival(baseline,sequence);});data[0]^=1;}
  auto mutation=[&](auto& value){const auto old=value;++value;refusal([&]{verify_survival(baseline,sequence);});value=old;};
  mutation(context_extent);probe_reverse_hidden[0]^=1;refusal([&]{verify_survival(baseline,sequence);});probe_reverse_hidden[0]^=1;
  mutation(pending_confirmed);mutation(recursive_host.extent);mutation(recursive_target.history0);mutation(recursive_rows[0].offset);mutation(recursive_rows.back().pinned_before[0]);mutation(recursive_captures);
  mutation(prepared.at(nullptr).spec.extent);mutation(prepared.at(nullptr).bindings[0]);mutation(issue_sites[0].commands[0].ids[0]);mutation(issue_sites[0].commands[0].operation_bytes[0]);
  ownrt::ring_next::wire::Context context{0,{},0,4,16,97};ownrt::recursive_provider_next::Sequence fresh(context);refusal([&]{verify_survival(baseline,fresh);});
  ++shared_copy_count;++e.drains;verify_survival(baseline,sequence); // shared evidence counters are explicitly excluded
 }
 void reset_fixture(){
  // The fixture performs the existing canonical owner-zero operation; the new
  // private/host reset below is the actual production member implementation.
  e.a.pipeline_ring_persistent_requests=true;
  refusal([&]{recursive_reset_after_owner_zero();}); // current position is not cold
  const auto frozen=recursive_rows;const auto image=recursive_image;
  for(auto id:mutable_ids)std::memset(e.dev(0).arena.row(id).pointer,0,e.dev(0).arena.row(id).bytes);
  for(auto id:{publication,half_staging,recursive_image})std::memset(e.dev(0).arena.row(id).pointer,0,e.dev(0).arena.row(id).bytes);
  position=0;context_extent=32;pending_head=false;pending_confirmed=0;pending_start={};probe_reverse_hidden.clear();reverse_hidden=nullptr;publication_event=0;queued_probe=queued_confirmed=-1;
  recursive_reset_after_owner_zero();assert(recursive_image==image&&recursive_host==RecursiveHost{}&&recursive_target==RecursiveTarget{}&&!recursive_class&&!recursive_captures&&!recursive_restores&&!recursive_verified_restores);
  assert(recursive_rows.size()==frozen.size());for(size_t i=0;i<recursive_rows.size();++i){const auto& row=recursive_rows[i];assert(row.id==frozen[i].id&&row.offset==frozen[i].offset&&row.bytes==frozen[i].bytes);assert(std::all_of(row.pinned_before.begin(),row.pinned_before.end(),[](auto b){return !b;}));}
  for(auto [id,bytes]:read_canonical())assert(std::all_of(bytes.begin(),bytes.end(),[](auto b){return !b;}));
 }
 std::vector<Allocation> canonical_devices()const{return {mutable_ids.begin(),mutable_ids.end()};}
 std::vector<Allocation> pins()const{return {publication,half_staging};}
 std::map<Allocation,std::vector<uint8_t>> read_canonical(){std::map<Allocation,std::vector<uint8_t>> out;for(auto id:mutable_ids)out[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);for(auto id:{publication,half_staging})out[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);return out;}
};
static void options_gate(){
 setenv("OMP_NUM_THREADS","2",1);
 const std::vector<std::string> base{"native","--output","/unused-ring-parser-output","--rank","0","--memory","resident","--gsq-packed","--activations","f32","--context","4096","--target-split","24","--retain-steps","none","--pipeline-stage","0","--pipeline-boundaries","0,12,24,36,48","--native-nice",std::to_string(getpriority(PRIO_PROCESS,0))};
 auto check=[&](std::vector<std::string> extra){auto args=base;args.insert(args.end(),extra.begin(),extra.end());std::vector<char*> pointers;for(auto& a:args)pointers.push_back(a.data());return parse(int(pointers.size()),pointers.data());};
 auto legacy=check({});assert(!legacy.pipeline_ring&&!legacy.pipeline_wavefront);
 const std::vector<std::string> ring{"--pipeline-ring","--pipeline-ring-request-sha256",std::string(64,'a'),"--pipeline-ring-verify-restore"};
 auto admitted=check(ring);assert(admitted.pipeline_ring&&admitted.pipeline_ring_verify&&admitted.pipeline_ring_request_sha256==std::string(64,'a'));
 for(const auto& extra:std::vector<std::vector<std::string>>{{"--pipeline-ring"},{"--pipeline-ring-verify-restore"},{"--pipeline-ring-request-sha256",std::string(64,'a')},{"--pipeline-ring","--pipeline-ring-request-sha256",std::string(64,'A')}})refusal([&]{check(extra);});
 for(const auto& extra:std::vector<std::vector<std::string>>{{"--pipeline-wavefront"},{"--pipeline-live-draft"},{"--pipeline-draft-partition"},{"--pipeline-persistent-requests"},{"--draft-mtp"},{"--retain-steps","1"},{"--pipeline-ring-trace-limit","100001"}}){auto args=ring;args.insert(args.end(),extra.begin(),extra.end());refusal([&]{check(args);});}
 auto live=ring;live.insert(live.end(),{"--pipeline-ring-live-draft","--draft-mtp","--pipeline-ring-final-shared","/not-created/final-shared","--pipeline-ring-recursive-verify-restore"});auto admitted_live=check(live);auto pending=live;pending.insert(pending.end(),{"--pipeline-ring-pending-provider","--pipeline-ring-verify-provider-survival"});auto admitted_pending=check(pending);assert(admitted_pending.pipeline_ring_pending_provider&&admitted_pending.pipeline_ring_verify_provider_survival);auto missing=pending;missing.pop_back();refusal([&]{check(missing);});auto unexpected=live;unexpected.push_back("--pipeline-ring-verify-provider-survival");refusal([&]{check(unexpected);});assert(admitted_live.pipeline_ring_live_draft&&admitted_live.pipeline_live_draft&&admitted_live.pipeline_draft_partition&&admitted_live.pipeline_ring_recursive_verify);
 auto middle=ring;middle.insert(middle.end(),{"--pipeline-ring-live-draft","--pipeline-stage","1","--rank","1"});auto admitted_middle=check(middle);assert(admitted_middle.pipeline_ring_live_draft&&!admitted_middle.mtp&&admitted_middle.pipeline_ring_final_shared.empty());
 auto wrong=middle;wrong.insert(wrong.end(),{"--pipeline-ring-recursive-verify-restore"});refusal([&]{check(wrong);});wrong=middle;wrong.insert(wrong.end(),{"--pipeline-ring-final-shared","/unexpected-peer"});refusal([&]{check(wrong);});wrong=ring;wrong.push_back("--pipeline-ring-live-draft");refusal([&]{check(wrong);});

 auto remote=pending;remote.insert(remote.end(),{"--pipeline-provider-stage","2","--pipeline-stage","2","--rank","1","--pipeline-ring-persistent-requests","--pipeline-ring-seed-shared","/not-created/seed-shared"});auto actual=check(remote);assert(actual.pipeline_provider()&&!actual.pipeline_first()&&actual.draft_rank==0);
 auto no_seed=remote;no_seed.resize(no_seed.size()-2);refusal([&]{check(no_seed);});
 auto final_provider=remote;final_provider.insert(final_provider.end(),{"--pipeline-provider-stage","3","--pipeline-stage","3"});refusal([&]{check(final_provider);});
 auto wrong_owner=remote;wrong_owner.insert(wrong_owner.end(),{"--pipeline-stage","1"});refusal([&]{check(wrong_owner);});

}
int main(int argc,char** argv){options_gate();assert(argc==2||argc==3);const bool flat=argc==3;assert(!flat||std::string(argv[2])=="--flat");fs::path root=argv[1];fs::create_directory(root);ProviderOwner owner(root/"owner");owner.a.pipeline_stage=owner.a.pipeline_provider_stage=std::getenv("FIXTURE_PROVIDER_STAGE")?std::stoi(std::getenv("FIXTURE_PROVIDER_STAGE")):0;owner.a.pipeline_ring_recursive_flat_copy=flat;owner.a.pipeline_live_draft=owner.a.pipeline_draft_partition=owner.a.mtp=true;
 for(auto name:{"error","position"})owner.buffers[0][name]={owner.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
 auto target=owner.allocate(0,"target-state",257,Category::recurrent,Lifetime::request);std::memset(owner.dev(0).arena.row(target).pointer,53,257);owner.put("position",2);
 std::set<Allocation> before;for(auto& [id,where]:owner.allocations)before.insert(id);FixtureDraft draft(owner);
 int callbacks=0;const int drains_before=owner.drains;owner.progress_callback=[&]{++callbacks;};refusal([&]{draft.recursive_idle();});assert(!callbacks&&owner.drains==drains_before);owner.progress_callback={};
 auto partition=pipeline::admit_operator_partition(owner,before,draft.canonical_devices(),draft.pins(),draft.live_private_recursive_inventory());assert(partition.draft_device.size()==71&&partition.draft_pinned.size()==2&&partition.draft_private.size()==1&&partition.target_device.size()==before.size());
 refusal([&]{pipeline::admit_operator_partition(owner,before,draft.canonical_devices(),draft.pins());});auto overlap=draft.canonical_devices();overlap.push_back(draft.recursive_image);refusal([&]{pipeline::admit_operator_partition(owner,before,overlap,draft.pins(),draft.live_private_recursive_inventory());});
 const auto peer_path=fs::absolute(root/"final-shared");pipeline::recursive_provider::Peer peer(peer_path);assert(!fs::exists(peer_path)); // lazy: construction cannot open a not-yet-created final owner
 std::vector<uint8_t> shared(pipeline::shared_bytes);const int fd=::open(peer_path.c_str(),O_RDWR|O_CREAT|O_EXCL,0600);assert(fd>=0&&::ftruncate(fd,pipeline::shared_bytes)==0);auto* map=static_cast<uint8_t*>(::mmap(nullptr,pipeline::shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(map!=MAP_FAILED);
 namespace wire=ownrt::ring_next::wire;wire::Context context{0,{},owner.a.pipeline_stage,4,16,97};ownrt::recursive_provider::FinalRecord record;record.stage=3;record.published_sequence=3;record.row.epoch=0;record.row.id=1;record.row.position=0;record.row.token=7;record.row.owner=3;record.row.final=1;record.row.publication_ticket=2;record.row.request=context.request;record.row.before=ownrt::ring_next::request_prefix(context.request,0);record.row.after=ownrt::ring_next::extend(record.row.before,0,7);record.row.payload_sha=wire::digest({});
 record.hidden.bytes=16;record.hidden.position=0;record.hidden.final_stage=3;record.hidden.stages=4;record.hidden.row_ticket=2;record.hidden.commit_sequence=3;record.hidden.input_token=7;
 std::vector<uint8_t> hidden(16,23);const auto sha=hash(hidden);std::copy(sha.begin(),sha.end(),record.hidden.hidden_sha256.begin());std::memcpy(map+ownrt::live_draft::hidden_offset,hidden.data(),hidden.size());ownrt::recursive_provider::publish(map,record);
 auto event=peer.capture(context,root/"peer.json");ownrt::ring_next::Row seed{0,2,1,7,1,11,1,false,context.request,record.row.after,{}};seed.after=ownrt::ring_next::extend(seed.before,1,11);
 wire::RowMeta meta;meta.epoch=seed.epoch;meta.id=seed.id;meta.parent=seed.parent;meta.position=seed.position;meta.token=seed.token;meta.fixture=seed.fixture;meta.request=seed.request;meta.before=seed.before;meta.after=seed.after;meta.payload_sha=wire::digest({});
 meta.owner=context.stage;meta.publication_ticket=context.stage?seed.ticket:0;pipeline::Request request{27,11,1,1,2,9,{context.stage,0}};
 auto admit=[&](const auto& frame,const auto& header){return pipeline::recursive_provider::admit_batch(request,context,seed,event,{reinterpret_cast<const uint8_t*>(&frame),sizeof frame},{reinterpret_cast<const uint8_t*>(&header),sizeof header},hidden,1);};
 if(context.stage){
  const auto seed_path=fs::absolute(root/"seed-shared");const int sfd=::open(seed_path.c_str(),O_RDWR|O_CREAT|O_EXCL,0600);assert(sfd>=0&&!::ftruncate(sfd,pipeline::shared_bytes));
  auto* smap=static_cast<uint8_t*>(::mmap(nullptr,pipeline::shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,sfd,0));assert(smap!=MAP_FAILED);
  pipeline::recursive_provider::Peer source(seed_path);refusal([&]{source.capture_seed(context,root/"seed-peer.json");});
  ownrt::recursive_provider::SeedRecord journal;journal.published_sequence=8;journal.physical=4;journal.committed=2;journal.row=meta;journal.row.owner=0;journal.row.publication_ticket=seed.ticket;
  ownrt::recursive_provider::publish_seed(smap,journal);const auto captured=source.capture_seed(context,root/"seed-peer.json");assert(ownrt::recursive_provider::seed_row(captured,context)==seed);
  // Immutable copied identity survives producer storage overwrite; a new read
  // must refuse a missing marker, stale epoch or forged ticket/frontier.
  std::memset(smap+ownrt::recursive_provider::seed_record_offset,0,sizeof journal);assert(ownrt::recursive_provider::seed_row(captured,context)==seed);refusal([&]{source.capture_seed(context,root/"seed-peer.json");});
  for(int mutation=0;mutation<4;++mutation){auto bad=journal;if(mutation==0)++bad.row.epoch;if(mutation==1)bad.row.publication_ticket=8;if(mutation==2)bad.committed=1;if(mutation==3)bad.row.owner=2;ownrt::recursive_provider::publish_seed(smap,bad);refusal([&]{source.capture_seed(context,root/"seed-peer.json");});}
  auto wrong_ticket=meta;++wrong_ticket.publication_ticket;refusal([&]{admit(wrong_ticket,record.hidden);});
  // Remote wire sequence is independent: it may precede stage0's ROW ticket.
  auto early=request;early.sequence=1;auto pair=pipeline::recursive_provider::admit_batch(early,context,seed,event,{reinterpret_cast<const uint8_t*>(&meta),sizeof meta},{reinterpret_cast<const uint8_t*>(&record.hidden),sizeof record.hidden},hidden,1);ownrt::recursive_provider_next::Sequence(context).admit(pair.input,pair.expected);
  ::munmap(smap,pipeline::shared_bytes);::close(sfd);
 }
 auto wrong=record.hidden;++wrong.commit_sequence;refusal([&]{admit(meta,wrong);});auto wrong_meta=meta;++wrong_meta.id;refusal([&]{admit(wrong_meta,record.hidden);});auto admitted=admit(meta,record.hidden);
 std::map<Allocation,std::vector<uint8_t>> target_before;for(auto id:before)target_before[id]=owner.readback(0,id,owner.dev(0).arena.row(id).bytes);
 pipeline::ring_next::CheckpointRingFor<ProviderOwner> target_ring(owner,true,partition);std::array<uint8_t,65536> target_shared{};
 const int first_slot=target_ring.capture(target_shared.data());owner.put("position",3);std::memset(owner.dev(0).arena.row(target).pointer,61,257);owner.history0=3;target_shared[0]=1;
 const int second_slot=target_ring.capture(target_shared.data());owner.put("position",4);std::memset(owner.dev(0).arena.row(target).pointer,62,257);owner.history0=4;target_shared[0]=2;target_ring.borrow_boundary(2);
 ownrt::recursive_provider_next::Sequence sequence(context);auto result=draft.live_recursive_depth2(sequence,admitted.input,admitted.expected,true);assert(result.available_depth==2&&result.restored_position==1&&draft.recursive_captures==1&&draft.recursive_restores==1&&draft.recursive_verified_restores==1&&!draft.recursive_active);
 auto survival=draft.capture_survival(sequence);target_ring.restore(first_slot);target_ring.release(first_slot);target_ring.release(second_slot);draft.verify_survival(survival,sequence);target_ring.borrow_boundary(0);assert(owner.integer(0,"position")==2&&owner.history0==0&&target_shared[0]==0);draft.mutation_checks(sequence);
 // Releasing the older image must not rewind physical target progress. A later
 // suffix restore preserves all newly advanced provider bytes and descriptors.
 const int older=target_ring.capture(target_shared.data());owner.put("position",3);owner.history0=3;target_shared[0]=3;const int newer=target_ring.capture(target_shared.data());owner.put("position",4);owner.history0=4;target_shared[0]=4;target_ring.release(older);target_ring.borrow_boundary(1);assert(owner.integer(0,"position")==4);
 // A newly accepted seed keeps its original tentative bit. Independently bind
 // its final parent event, then advance canonical provider while one target
 // image still predates it. This is the one-pending rollback regression.
 auto record2=record;record2.published_sequence=11;record2.row.id=seed.id;record2.row.parent=seed.parent;record2.row.position=1;record2.row.token=seed.token;record2.row.fixture=1;record2.row.before=seed.before;record2.row.after=seed.after;record2.row.publication_ticket=10;record2.hidden.position=1;record2.hidden.row_ticket=10;record2.hidden.commit_sequence=11;record2.hidden.input_token=seed.token;record2.hidden.head=1;record2.hidden.next_token=19;ownrt::recursive_provider::publish(map,record2);auto event2=peer.capture(context,root/"peer.json");
 auto seed2=seed;seed2.id=3;seed2.parent=seed.id;seed2.ticket=13;seed2.position=2;seed2.token=19;seed2.fixture=2;seed2.tentative=true;seed2.before=seed.after;seed2.after=ownrt::ring_next::extend(seed2.before,2,19);
 auto meta2=meta;meta2.flags=wire::tentative;meta2.id=seed2.id;meta2.parent=seed2.parent;meta2.position=2;meta2.token=19;meta2.fixture=2;meta2.before=seed2.before;meta2.after=seed2.after;meta2.publication_ticket=context.stage?seed2.ticket:0;pipeline::Request request2{27,19,2,1,2,15,{context.stage,0}};
 auto pair2=pipeline::recursive_provider::admit_batch(request2,context,seed2,event2,{reinterpret_cast<const uint8_t*>(&meta2),sizeof meta2},{reinterpret_cast<const uint8_t*>(&record2.hidden),sizeof record2.hidden},hidden,2);
 draft.live_recursive_depth2(sequence,pair2.input,pair2.expected,true);assert(sequence.serial()==2&&draft.recursive_host_state().position==2);auto one_pending=draft.capture_survival(sequence);target_ring.restore(newer);target_ring.release(newer);draft.verify_survival(one_pending,sequence);assert(owner.integer(0,"position")==3&&owner.history0==3&&target_shared[0]==3);owner.put("position",2);owner.history0=0;
 assert(draft.read_canonical()==draft.canonical_bytes&&draft.recursive_host_state()==draft.canonical_host);for(auto [id,bytes]:target_before)assert(owner.readback(0,id,bytes.size())==bytes);assert(owner.history0==0&&owner.current_cls==9);
 // A fresh request keeps allocations/bindings and clears saved recursive host,
 // pinned images and counters. New Sequence context rejects prior publications;
 // measured restore still restores canonical bytes and host exactly.
 draft.reset_fixture();auto next_context=context;next_context.epoch=1;next_context.request[0]=1;ownrt::recursive_provider_next::Sequence next_sequence(next_context);
 refusal([&]{draft.live_recursive_depth2(next_sequence,admitted.input,admitted.expected,false);});assert(!next_sequence.poisoned());
 auto next_input=admitted.input;next_input.sequence=21;next_input.seed.epoch=1;next_input.seed.request=next_context.request;next_input.seed.ticket=19;next_input.seed.before=ownrt::ring_next::extend(ownrt::ring_next::request_prefix(next_context.request,1),0,next_input.parent.input_token);next_input.seed.after=ownrt::ring_next::extend(next_input.seed.before,1,next_input.seed.token);auto next_expected=admitted.expected;next_expected.seed=next_input.seed;
 auto next_result=draft.live_recursive_depth2(next_sequence,next_input,next_expected,false);assert(next_result.available_depth==2&&next_sequence.serial()==1&&draft.recursive_captures==1&&draft.recursive_restores==1&&!draft.recursive_verified_restores&&draft.read_canonical()==draft.canonical_bytes&&draft.recursive_host_state()==draft.canonical_host);
 ownrt::recursive_provider::invalidate(map);refusal([&]{peer.capture(context,root/"peer.json");});ownrt::recursive_provider::publish(map,record);map[ownrt::live_draft::hidden_offset]^=1;refusal([&]{peer.capture(context,root/"peer.json");});
 {ProviderOwner failed(root/"failed-owner");failed.a.pipeline_stage=failed.a.pipeline_provider_stage=context.stage;failed.a.pipeline_ring_recursive_flat_copy=flat;failed.a.pipeline_live_draft=failed.a.pipeline_draft_partition=failed.a.mtp=true;for(auto name:{"error","position"})failed.buffers[0][name]={failed.allocate(0,name,4,Category::graph_static,Lifetime::graph)};failed.put("position",2);FixtureDraft broken(failed);broken.corrupt_target=true;ownrt::recursive_provider_next::Sequence seq(context);refusal([&]{broken.live_recursive_depth2(seq,admitted.input,admitted.expected,true);});assert(seq.poisoned()&&broken.recursive_captures==1&&!broken.recursive_restores&&failed.history0==999);failed.close();}
 std::cout<<"recursive_flat_copy="<<flat<<" boundary sizes1/15/16/17/4095/4096/4097/8192/8193,71 device rows\n";
 ::munmap(map,pipeline::shared_bytes);::close(fd);owner.close();std::cout<<"PASS actual recursive member snapshot/CopyEngine transport71device+2pinned, private census, exact op27 accepted-seed/independent-peer binding, lazy readonly peer, marker/SHA refusal, complete canonical restoration, pending depth2/depth1 target rollback survival, corruption refusals for device/pinned/private/host/Sequence/prepared bindings, and unchanged target bytes/host; synthetic arithmetic only\n";
}
