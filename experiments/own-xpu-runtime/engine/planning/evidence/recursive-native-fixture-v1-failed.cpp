#include "checkpoint_fixture.hpp"
struct ProviderOwner:FixtureOwner {
 bool preparing_commands=false,draft_timing=false;int current_cls=9;
 using FixtureOwner::FixtureOwner;
};
// Executes the ACTUAL member extension and checked Host copy transport. Only the
// arithmetic entry points below are synthetic; no model kernels/GPU are invoked.
class FixtureDraft {
 ProviderOwner& e;
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
#include "pipeline/recursive_provider/draft_runtime_extension.inc"
 bool corrupt_target=false;std::map<Allocation,std::vector<uint8_t>> canonical_bytes;RecursiveHost canonical_host;
 explicit FixtureDraft(ProviderOwner& owner):e(owner){
  for(int i=0;i<71;++i){std::string name=i==0?"error":i==1?"position":"scratch"+std::to_string(i);const size_t bytes=i<2?4:size_t(17+i);auto allocation=e.allocate(0,"draft:"+name,bytes,Category::scratch,Lifetime::transaction);names[name]=allocation;mutable_ids.insert(allocation);allocated+=bytes;}
  publication=e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned);half_staging=e.allocate(0,"draft:half-staging",4+e.stream_bytes(),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
  prepare_recursive_depth2();
 }
 std::vector<Allocation> canonical_devices()const{return {mutable_ids.begin(),mutable_ids.end()};}
 std::vector<Allocation> pins()const{return {publication,half_staging};}
 std::map<Allocation,std::vector<uint8_t>> read_canonical(){std::map<Allocation,std::vector<uint8_t>> out;for(auto id:mutable_ids)out[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);for(auto id:{publication,half_staging})out[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);return out;}
};
int main(int argc,char** argv){assert(argc==2);fs::path root=argv[1];fs::create_directory(root);ProviderOwner owner(root/"owner");owner.a.pipeline_live_draft=owner.a.pipeline_draft_partition=owner.a.mtp=true;
 for(auto name:{"error","position"})owner.buffers[0][name]={owner.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
 auto target=owner.allocate(0,"target-state",257,Category::recurrent,Lifetime::request);std::memset(owner.dev(0).arena.row(target).pointer,53,257);owner.put("position",2);
 std::set<Allocation> before;for(auto& [id,where]:owner.allocations)before.insert(id);FixtureDraft draft(owner);
 auto partition=pipeline::admit_operator_partition(owner,before,draft.canonical_devices(),draft.pins(),draft.live_private_recursive_inventory());assert(partition.draft_device.size()==71&&partition.draft_pinned.size()==2&&partition.draft_private.size()==1&&partition.target_device.size()==before.size());
 refusal([&]{pipeline::admit_operator_partition(owner,before,draft.canonical_devices(),draft.pins());});auto overlap=draft.canonical_devices();overlap.push_back(draft.recursive_image);refusal([&]{pipeline::admit_operator_partition(owner,before,overlap,draft.pins(),draft.live_private_recursive_inventory());});
 const auto peer_path=fs::absolute(root/"final-shared");pipeline::recursive_provider::Peer peer(peer_path);assert(!fs::exists(peer_path)); // lazy: construction cannot open a not-yet-created final owner
 std::vector<uint8_t> shared(pipeline::shared_bytes);const int fd=::open(peer_path.c_str(),O_RDWR|O_CREAT|O_EXCL,0600);assert(fd>=0&&::ftruncate(fd,pipeline::shared_bytes)==0);auto* map=static_cast<uint8_t*>(::mmap(nullptr,pipeline::shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(map!=MAP_FAILED);
 namespace wire=ownrt::ring_next::wire;wire::Context context{0,{},0,4,16,97};ownrt::recursive_provider::FinalRecord record;record.stage=3;record.published_sequence=3;record.row.epoch=0;record.row.id=1;record.row.position=0;record.row.token=7;record.row.owner=3;record.row.final=1;record.row.publication_ticket=2;record.row.request=context.request;record.row.before=ownrt::ring_next::request_prefix(context.request,0);record.row.after=ownrt::ring_next::extend(record.row.before,0,7);record.row.payload_sha=wire::digest({});
 record.hidden.bytes=16;record.hidden.position=0;record.hidden.final_stage=3;record.hidden.stages=4;record.hidden.row_ticket=2;record.hidden.commit_sequence=3;record.hidden.input_token=7;
 std::vector<uint8_t> hidden(16,23);const auto sha=hash(hidden);std::copy(sha.begin(),sha.end(),record.hidden.hidden_sha256.begin());std::memcpy(map+ownrt::live_draft::hidden_offset,hidden.data(),hidden.size());ownrt::recursive_provider::publish(map,record);
 auto event=peer.capture(context,root/"peer.json");ownrt::ring_next::Row seed{0,2,1,7,1,11,1,false,context.request,record.row.after,{}};seed.after=ownrt::ring_next::extend(seed.before,1,11);
 wire::RowMeta meta;meta.epoch=seed.epoch;meta.id=seed.id;meta.parent=seed.parent;meta.position=seed.position;meta.token=seed.token;meta.fixture=seed.fixture;meta.request=seed.request;meta.before=seed.before;meta.after=seed.after;meta.payload_sha=wire::digest({});
 Request request{27,11,1,1,2,9,{0,0}};
 auto admit=[&](const auto& frame,const auto& header){return pipeline::recursive_provider::admit_batch(request,context,seed,event,{reinterpret_cast<const uint8_t*>(&frame),sizeof frame},{reinterpret_cast<const uint8_t*>(&header),sizeof header},hidden,1);};
 auto wrong=record.hidden;++wrong.commit_sequence;refusal([&]{admit(meta,wrong);});auto wrong_meta=meta;++wrong_meta.id;refusal([&]{admit(wrong_meta,record.hidden);});auto admitted=admit(meta,record.hidden);
 std::map<Allocation,std::vector<uint8_t>> target_before;for(auto id:before)target_before[id]=owner.readback(0,id,owner.dev(0).arena.row(id).bytes);
 ownrt::recursive_provider_next::Sequence sequence(context);auto result=draft.live_recursive_depth2(sequence,admitted.input,admitted.expected,true);assert(result.available_depth==2&&result.restored_position==1&&draft.recursive_captures==1&&draft.recursive_restores==1&&draft.recursive_verified_restores==1&&!draft.recursive_active);
 assert(draft.read_canonical()==draft.canonical_bytes&&draft.recursive_host_state()==draft.canonical_host);for(auto [id,bytes]:target_before)assert(owner.readback(0,id,bytes.size())==bytes);assert(owner.history0==0&&owner.current_cls==9);
 ownrt::recursive_provider::invalidate(map);refusal([&]{peer.capture(context,root/"peer.json");});ownrt::recursive_provider::publish(map,record);map[ownrt::live_draft::hidden_offset]^=1;refusal([&]{peer.capture(context,root/"peer.json");});
 ::munmap(map,pipeline::shared_bytes);::close(fd);owner.close();std::cout<<"PASS actual recursive member snapshot/CopyEngine transport71device+2pinned, private census, exact op27 accepted-seed/independent-peer binding, lazy readonly peer, marker/SHA refusal, complete canonical restoration and unchanged target bytes/host; synthetic arithmetic only\n";
}
