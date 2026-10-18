#pragma once
// Exact speculative rollback. Only the private backup is cleared at a request
// boundary; no model allocation is canonicalized, hidden or reset before hashing.
namespace pipeline {
// Scatter/gather transport only: all component copies are admitted by the
// unchanged CopyEngine guard before this operation can be submitted. Sources
// and destinations remain owner-bound allocations. No model arithmetic changes.
#ifdef OWN_RT_HOST_ONLY
struct SnapshotBatch final:integrated::HostOperation {
#else
struct SnapshotBatch final:ownrt::SyclOperation {
#endif
 struct Item {uint8_t* dst=nullptr;const uint8_t* src=nullptr;size_t bytes=0;};
 static constexpr size_t width=32,limit=128ull*1024*1024;
 std::array<Item,width> items{};size_t count=0,maximum=0,total=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>)const override {
  for(size_t i=0;i<count;++i)std::memcpy(items[i].dst,items[i].src,items[i].bytes);
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const>,const std::vector<sycl::event>& deps)const override {
  auto values=items;auto rows=count;auto columns=(maximum+15)/16;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);
   h.parallel_for(sycl::range<2>(rows,columns),[=](sycl::id<2> id){
    const auto item=values[id[0]];size_t off=id[1]*16;
    for(size_t j=0;j<16&&off+j<item.bytes;++j)item.dst[off+j]=item.src[off+j];
   });
  });
 }
#endif
};
// Packet62 flat copy schedule: the host descriptor table is copied into owned
// device storage, then one workgroup copies each 4096-byte tile. Binary search
// selects the owning extent; small rows never inherit the largest row's grid.
// Every source/destination/extent first passes the original CopyEngine checks.
#ifdef OWN_RT_HOST_ONLY
struct SnapshotFlat final:integrated::HostOperation {
#else
struct SnapshotFlat final:ownrt::SyclOperation {
#endif
 struct Item {uint8_t* dst;const uint8_t* src;size_t bytes,end_tile;};
 static constexpr size_t tile=4096,lanes=256;
 size_t count=0,tiles=0;
 static void copy_lane(const Item* rows,size_t n,size_t tile_id,size_t lane) {
  size_t lo=0,hi=n;
  while(lo<hi){size_t mid=(lo+hi)/2;if(rows[mid].end_tile<=tile_id)lo=mid+1;else hi=mid;}
  auto row=rows[lo];size_t start=lo?rows[lo-1].end_tile:0;
  size_t off=(tile_id-start)*tile+lane*16;
  for(size_t j=0;j<16&&off+j<row.bytes;++j)row.dst[off+j]=row.src[off+j];
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto rows=static_cast<const Item*>(p[0]);
  for(size_t t=0;t<tiles;++t)for(size_t lane=0;lane<lanes;++lane)copy_lane(rows,count,t,lane);
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto rows=static_cast<const Item*>(p[0]);auto n=count,total=tiles;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(total*lanes,lanes),[=](sycl::nd_item<1> id){
    copy_lane(rows,n,id.get_group_linear_id(),id.get_local_linear_id());
   });
  });
 }
#endif
};
static_assert(sizeof(SnapshotFlat::Item)==32);
// SPEED2_WRITE_SET_BEGIN
// Union of all selectable parallel writers, derived from Launch geometry.
// Bounds describe bytes which MAY be written, including every cancelled prefix.
// Unknown operators/reference execution preserve the complete allocation.
struct SnapshotWriteSet {
 static size_t scratch(const flash::Plan& p,const flash::Launch& l,size_t allocation,bool parallel) {
  if(!parallel)return allocation;
  auto ceil=[](size_t n,size_t d){return (n+d-1)/d;};
  size_t n=0;
  if(!l.inputs.empty())for(const auto& b:p.buffers)if(b.card==l.card&&b.name==l.inputs[0]){
   n=1;for(int v:b.shape){require(v>0,"snapshot input geometry");n*=size_t(v);}break;
  }
  size_t bytes=0;const auto& op=l.op;
  if(op=="norm"||op=="hc_combine"){
   if(l.shape.size()<2||l.shape[1]<=0||!n||n%size_t(l.shape[1]))return allocation;
   bytes=(n/size_t(l.shape[1]))*ceil(size_t(l.shape[1]),32)*4;
  }else if(op=="route")bytes=(2*ceil(n,16)+2*n)*4;
  else if(op=="argmax")bytes=2*ceil(n,256)*4;
  else if(op=="expert_gather")bytes=size_t(p.g.top)*4;
  else if(op=="gdn")bytes=p.g.h==2560?4192*4:0;
  else if(op=="gdn_norm_gate")bytes=p.g.h==2560?48*4*4:0;
  else if(op=="qsa_prepare")bytes=p.g.h==2560?30*8*4:0;
  else if(op=="qsa_append_pool")bytes=p.g.h==2560?ceil(size_t(p.g.context),4)*4*4:0;
  else if(op=="qsa_select")bytes=p.g.h==2560?ceil(size_t(p.g.context),4)*4:0;
  else if(op=="qsa_attention")bytes=p.g.h==2560?16+24*258*ceil(size_t(std::min(p.g.context,p.g.budget+3)),32)*4:0;
  else {
   static const std::set<std::string> no_global_scratch={"begin","commit","broadcast","ple_hash","check_status","lookup","handoff","handoff_result","gemv","routed_gemv","expert_gate_up","silu_div4","silu_product","hc_mix","conv","moe_combine","ple_gate","ple_add"};
   if(!no_global_scratch.count(op))return allocation;
  }
  if((op=="route"||op=="argmax")&&!n)return allocation;
  require(bytes<=allocation,"snapshot scratch writer exceeds allocation");return bytes;
 }
 static size_t scratch(const flash::Plan& p,size_t allocation,bool parallel) {
  size_t bound=0;for(const auto& l:p.launches)bound=std::max(bound,scratch(p,l,allocation,parallel));return bound;
 }
 static bool single_row(const flash::Plan& p,const std::string& name,bool parallel) {
  if(!parallel)return false;bool writer=false;
  for(const auto& l:p.launches)if(std::find(l.outputs.begin(),l.outputs.end(),name)!=l.outputs.end()){
   if(l.op!="qsa_append_pool")return false;writer=true;
  }
  return writer;
 }
};
// SPEED2_WRITE_SET_END
// SPEED4_REDO_PROOF_BEGIN
// Only physical spare banks qualify. All plan inputs bind the active bank;
// outputs[1] binds the distinct spare bank (Engine::prepare_plan and banks()).
// GDN writes vh*d rows of d BF16 elements; conv writes width*3*dilation.
// A complete, non-speculative redo therefore replaces EVERY skipped byte.
struct RedoBankProof {
 size_t bytes=0;std::string writer;
 static RedoBankProof derive(const flash::Plan& p,const std::string& name) {
  const flash::Buffer* buffer=nullptr;const flash::Launch* writer=nullptr;
  for(const auto& b:p.buffers)if(b.name==name){if(buffer)return {};buffer=&b;}
  for(const auto& l:p.launches)if(std::find(l.outputs.begin(),l.outputs.end(),name)!=l.outputs.end()){
   if(writer)return {};writer=&l;
  }
  if(!buffer||!writer||buffer->type!=flash::Scalar::bf16||writer->outputs.size()!=2||writer->outputs[1]!=name)return {};
  size_t elements=0;
  if(writer->op=="gdn"){
   if(writer->inputs.size()<4||writer->inputs[3]!=name||p.g.vh<=0||p.g.d<=0||
      writer->shape!=std::vector<int>{p.g.kh,p.g.vh,p.g.d}||buffer->shape!=std::vector<int>{p.g.vh,p.g.d,p.g.d})return {};
   elements=size_t(p.g.vh)*p.g.d*p.g.d;
  }else if(writer->op=="conv"){
   int dilation=writer->parameter;
   if(writer->inputs.size()<2||writer->inputs[1]!=name||writer->shape.size()!=1||writer->shape[0]<=0||
      (dilation!=1&&dilation!=3)||buffer->shape!=std::vector<int>{writer->shape[0],3*dilation})return {};
   elements=size_t(writer->shape[0])*3*dilation;
  }else return {};
  return {elements*flash::scalar_bytes(buffer->type),writer->label};
 }
};
// SPEED4_REDO_PROOF_END
class SpeculativeImage {
 Engine& e;
 struct Source {std::string name;Allocation standalone=0;size_t bytes=0;bool bank=false,kv=false,pooled=false;size_t write_bytes=0;bool single_row=false,redo_overwrite=false;};
 struct Extent {Allocation id;size_t offset,bytes,backup_offset;bool redo_overwrite=false;};
 std::vector<Source> sources;
 std::vector<Extent> saved;
 std::vector<std::pair<Allocation,size_t>> protected_active,protected_qsa;
 Allocation table=0;size_t table_capacity=0;
 Allocation backup=0;size_t capacity=0;bool valid=false,dirty=false;
 bool rotated=false;uint64_t bank_capture_bytes_avoided=0;
 bool redo_pending=false;int redo_position=-1,redo_token=-1;
 std::array<uint8_t,65536> shared_before{};uint8_t* shared_slot=nullptr;
 unsigned parity=0;int64_t history0=0,history1=0;
 int launch_extent=32,alternate_launch_extent=32;
 std::map<std::string,std::vector<uint8_t>> lookup;
 std::vector<std::vector<uint32_t>> selected;
 std::vector<int> loaded;
 std::vector<Allocation> fp32_sources;
 std::vector<size_t> fp32_extents;
 uint64_t captures=0,restores=0,saved_bytes=0,capture_submissions=0,restore_submissions=0;
 uint64_t restored_bytes=0,redo_omitted_bytes=0,redo_restores=0,redo_fallbacks=0,completed_redos=0;
 void zero_private() {
  if(!backup)return;
  std::vector<uint8_t> zeros(std::min(capacity,size_t(4*1024*1024)),0);
  for(size_t off=0;off<capacity;off+=zeros.size())e.upload(0,backup,off,zeros.data(),std::min(zeros.size(),capacity-off));
  for(const auto& [name,id]:e.state_reserves){const auto bytes=e.dev(0).arena.row(id).bytes;
   for(size_t off=0;off<bytes;off+=zeros.size())e.upload(0,id,off,zeros.data(),std::min(zeros.size(),bytes-off));}
  if(table){std::vector<uint8_t> zero(table_capacity,0);e.upload(0,table,0,zero.data(),zero.size());}
  dirty=false;
 }
 void copy(bool restore,bool for_redo=false,bool deferred_only=false) {
  ownrt::CopyEngine engine(e.dev(0));
  std::vector<ownrt::PreparedCompute> checked;std::vector<size_t> lengths;
  std::set<Allocation> distinct;
  // Capture is validation/preparation only. The original copy method rejects
  // zero/oversize/dead/out-of-range extents; no alternate checker is introduced.
  e.dev(0).begin_capture(checked);
  try {
   for(const auto& x:saved){require(distinct.insert(x.id).second,"overlapping snapshot source allocation");
    if(restore&&for_redo&&x.redo_overwrite){redo_omitted_bytes+=x.bytes;continue;}
    if(deferred_only&&!x.redo_overwrite)continue;
    if(restore)restored_bytes+=x.bytes;
    for(size_t off=0;off<x.bytes;off+=SnapshotBatch::limit){
     size_t count=std::min(x.bytes-off,SnapshotBatch::limit);
     if(restore)engine.copy(x.id,x.offset+off,backup,x.backup_offset+off,count,{});
     else engine.copy(backup,x.backup_offset+off,x.id,x.offset+off,count,{});
     lengths.push_back(count);
    }
   }
   e.dev(0).end_capture();
  }catch(...){e.dev(0).end_capture();throw;}
  require(checked.size()==lengths.size(),"snapshot copy capture cardinality");
  if(e.miss_batch()&&!checked.empty()) {
   std::vector<SnapshotFlat::Item> rows;std::vector<Allocation> ids{table};size_t tiles=0;
   for(size_t i=0;i<checked.size();++i){const auto& item=checked[i];
    require(item.ids.size()==2&&item.pointers.size()==2,"flat snapshot descriptor");
    tiles+=(lengths[i]+SnapshotFlat::tile-1)/SnapshotFlat::tile;
    rows.push_back({static_cast<uint8_t*>(item.pointers[0]),static_cast<const uint8_t*>(item.pointers[1]),lengths[i],tiles});
    ids.insert(ids.end(),item.ids.begin(),item.ids.end());
   }
   require(rows.size()*sizeof(SnapshotFlat::Item)<=table_capacity,"flat snapshot table capacity");
   e.upload(0,table,0,rows.data(),rows.size()*sizeof(SnapshotFlat::Item));
   SnapshotFlat op;op.count=rows.size();op.tiles=tiles;e.tail=e.dev(0).compute(op,ids,{});e.attribution_copy(e.tail,restore?"rollback.restore.flat":"snapshot.capture.flat");
   (restore?restore_submissions:capture_submissions)+=2;return;
  }
  // Similar-sized pieces share one kernel, limiting padded work. Each batch
  // carries at most 128 MiB and 32 descriptors (below the 1024-byte capture cap).
  std::vector<size_t> order(lengths.size());for(size_t i=0;i<order.size();++i)order[i]=i;
  std::stable_sort(order.begin(),order.end(),[&](size_t a,size_t b){return lengths[a]<lengths[b];});
  size_t cursor=0,submissions=0;
  while(cursor<order.size()){
   SnapshotBatch batch;std::vector<Allocation> ids;
   size_t start=cursor;
   while(cursor<order.size()&&batch.count<SnapshotBatch::width){
    size_t i=order[cursor],bytes=lengths[i];if(bytes>SnapshotBatch::limit-batch.total)break;
    const auto& item=checked[i];require(item.ids.size()==2&&item.pointers.size()==2,"snapshot copy descriptor");
    batch.items[batch.count++]={static_cast<uint8_t*>(item.pointers[0]),static_cast<const uint8_t*>(item.pointers[1]),bytes};
    batch.maximum=std::max(batch.maximum,bytes);batch.total+=bytes;
    ids.insert(ids.end(),item.ids.begin(),item.ids.end());++cursor;
   }
   require(batch.count&&batch.total<=SnapshotBatch::limit,"snapshot batch bound");
   if(batch.count==1)e.tail=e.dev(0).issue(checked[order[start]]);
   else e.tail=e.dev(0).compute(batch,ids,{});
   e.attribution_copy(e.tail,batch.count==1?(restore?"rollback.transfer.restore.single":"snapshot.transfer.capture.single"):(restore?"rollback.restore.batch":"snapshot.capture.batch"));
   ++submissions;
  }
  (restore?restore_submissions:capture_submissions)+=submissions;
 }
public:
 explicit SpeculativeImage(Engine& owner):e(owner) {
  if(e.a.rank!=0)return;
  std::set<std::string> outputs{"token","position","token_history"},kv;
  std::set<Allocation> represented;
  for(const auto& site:e.p.launches){outputs.insert(site.outputs.begin(),site.outputs.end());if(site.op=="qsa_append_pool")kv.insert(site.outputs.begin(),site.outputs.end());}
  for(const auto& [name,slot]:e.buffers[0]) {
   represented.insert(slot.id);
   if(!outputs.count(name))continue;
   Source row{name,0,slot.n*flash::scalar_bytes(slot.type),e.state_spares.count(name)!=0,kv.count(name)!=0,ends(name,".pooled")};
   row.write_bytes=row.bytes;row.kv=row.kv&&SnapshotWriteSet::single_row(e.p,name,true);
   row.single_row=row.kv&&e.a.nongemv=="parallel";
   if(row.bank){auto proof=RedoBankProof::derive(e.p,name);row.redo_overwrite=proof.bytes==row.bytes&&proof.bytes>0;require(!e.miss_banks()||row.redo_overwrite,"third bank requires proved full destination overwrite");}
   if(!(e.miss_banks()&&row.bank))capacity+=row.bytes;sources.push_back(std::move(row));
  }
  for(const auto& [name,id]:e.state_spares)represented.insert(id);
  for(const auto& [name,id]:e.state_reserves)represented.insert(id);
  for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
   if(e.head_auxiliary.contains(id)){
    require(e.split_head()&&owner.first==0&&row.label.starts_with("card0:p105:")&&!represented.count(id),"p105 auxiliary cannot alias target state");
    continue; // only the post-half suffix service reads/writes these allocations
   }
   if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab||represented.count(id)||id==e.one[0])continue;
   require(owner.first==0&&row.memory==Memory::device,"snapshot owner/memory");
   Source source{{},id,row.bytes,false,false,false};source.write_bytes=id==e.scratch[0]?SnapshotWriteSet::scratch(e.p,row.bytes,e.a.nongemv=="parallel"):row.bytes;
   sources.push_back(source);capacity+=row.bytes;
  }
  require(capacity>0,"empty speculative snapshot");saved.reserve(sources.size());
  backup=e.allocate(0,"speculative-private-image",capacity,Category::runtime_overhead,Lifetime::process);
  if(e.miss_batch()){
   table_capacity=(sources.size()+capacity/SnapshotBatch::limit+1)*sizeof(SnapshotFlat::Item);
   table=e.allocate(0,"speculative-copy-table",table_capacity,Category::runtime_overhead,Lifetime::process);
  }
  zero_private();
 }
 void begin(uint8_t* shared) {
  require(e.a.rank==0&&backup&&!valid&&!redo_pending,"snapshot begin ownership");e.drain();
  require(!e.poisoned&&!e.integer(0,"error"),"snapshot cannot erase target failure");
  // Host layer streaming releases its weights at every completed half. Restoring
  // metadata never revives an allocation freed by a later layer transition.
  if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,"snapshot requires released streaming layer");
  require(shared!=nullptr,"snapshot shared slot");shared_slot=shared;std::memcpy(shared_before.data(),shared_slot,shared_before.size());
  parity=e.bank_parity;history0=e.history0;history1=e.history1;
  launch_extent=e.context_extent;alternate_launch_extent=e.alternate_context_extent;
  lookup=e.lookup_ids;selected=e.selected;loaded=e.loaded_layer;fp32_sources=e.fp32_sources;fp32_extents=e.fp32_extents;
  int position=e.integer(0,"position");require(position>=0&&position<e.p.g.context,"snapshot position");
  saved.clear();protected_active.clear();protected_qsa.clear();size_t offset=0;
  for(const auto& source:sources){
   Allocation id=source.standalone;size_t skip=0,bytes=source.write_bytes;
   if(!id){id=source.bank?e.state_spares.at(source.name):e.buffers[0].at(source.name).id;
    if(source.bank)protected_active.push_back({e.buffers[0].at(source.name).id,source.bytes});
    if(source.bank&&e.miss_banks()){bank_capture_bytes_avoided+=source.bytes;continue;}
    if(source.kv){size_t rows=source.pooled?size_t((e.p.g.context+3)/4):size_t(e.p.g.context);
     size_t valid_rows=source.pooled?size_t(position/4):size_t(position);
     require(source.bytes%rows==0,"snapshot QSA row geometry");skip=valid_rows*(source.bytes/rows);
     bytes=source.single_row?source.bytes/rows:source.bytes-skip;
     if(skip)protected_qsa.push_back({id,skip});
    }
   }
   // Active recurrent banks and already-committed QSA prefixes are not saved:
   // illegal mutation there must remain visible to the full-state gate.
   require(skip<=source.bytes&&bytes<=source.bytes-skip,"snapshot writer range");
   if(source.redo_overwrite){require(source.bank&&id==e.state_spares.at(source.name)&&id!=e.buffers[0].at(source.name).id&&skip==0&&bytes==source.bytes,"redo spare bank binding/coverage");}
   if(bytes)saved.push_back({id,skip,bytes,offset,source.redo_overwrite});offset+=bytes;
  }
  require(offset<=capacity,"snapshot extent overflow");valid=true;dirty=true;
  copy(false);if(e.miss_banks()){e.rotate_spare_bank();rotated=true;}++captures;saved_bytes+=offset;
 }
 void accept(){require(valid,"snapshot accept without speculation");e.drain();rotated=false;valid=false;}
 void restore(bool for_redo=false,int position=-1,int token=-1){
  require(valid,"snapshot restore without speculation");e.drain();
  require(!e.poisoned&&!e.integer(0,"error"),"snapshot cannot roll back sticky failure");
  require(e.bank_parity==parity,"snapshot restore bank selection");
  if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,"snapshot restore streaming layer retained");
  require(!redo_pending,"nested redo restore");
  if(rotated){e.rotate_spare_bank();rotated=false;}
  copy(true,for_redo);if(!e.miss_overlap())e.drain();
  require(shared_slot!=nullptr,"restore shared slot lifetime");std::memcpy(shared_slot,shared_before.data(),shared_before.size());
  // Restore both prepared-command banks as well as their launch metadata.
  // Rebuild only QSA sites through the same admission path. Do this before
  // restoring fp32 lookup metadata because swapping banks invalidates it.
  if(e.context_extent!=launch_extent)e.admit_position(launch_extent-1);
  if(e.alternate_context_extent!=alternate_launch_extent){
   e.swap_state_banks();e.admit_position(alternate_launch_extent-1);e.swap_state_banks();
  }
  require(e.bank_parity==parity&&e.context_extent==launch_extent&&e.alternate_context_extent==alternate_launch_extent,"snapshot launch extent restore");
  e.history0=history0;e.history1=history1;e.lookup_ids=std::move(lookup);e.selected=std::move(selected);
  e.loaded_layer=std::move(loaded);e.fp32_sources=std::move(fp32_sources);e.fp32_extents=std::move(fp32_extents);
  for(size_t card=0;card<e.fp32_sources.size();++card)if(e.fp32_sources[card])require(e.dev(int(card)).arena.row(e.fp32_sources[card]).live,"snapshot resurrected dead FP32 source");
  valid=false;++restores;
  if(for_redo){redo_pending=true;redo_position=position;redo_token=token;++redo_restores;}
 }
 bool before_command(bool confirmed_half,int position,int token){
  if(!redo_pending)return false;
  if(confirmed_half&&position==redo_position&&token==redo_token)return true;
  // A promised redo may be abandoned by cancel/end/reset/dump. Restore its
  // deferred banks before any other command can observe or reuse the state.
  e.drain();require(!e.poisoned&&!e.integer(0,"error"),"deferred restore cannot erase failure");
  copy(true,false,true);e.drain();redo_pending=false;redo_position=redo_token=-1;++redo_fallbacks;return false;
 }
 void finish_redo(){require(redo_pending&&!valid,"redo completion without pending restore");redo_pending=false;redo_position=redo_token=-1;++completed_redos;}
 void boundary(){
  before_command(false,-1,-1);
  require(!valid&&!redo_pending,"snapshot boundary with unresolved speculation");e.drain();if(dirty)zero_private();
  lookup.clear();selected.clear();loaded.clear();fp32_sources.clear();fp32_extents.clear();saved.clear();
  protected_active.clear();protected_qsa.clear();history0=history1=0;parity=0;launch_extent=alternate_launch_extent=32;
  shared_before.fill(0);shared_slot=nullptr;
  require(lookup.empty()&&selected.empty()&&loaded.empty()&&fp32_sources.empty()&&fp32_extents.empty()&&saved.empty(),"private host snapshot retirement");
  if(backup)save(e.a.output/"speculative-snapshot.json","{\"passed\":true,\"miss_selection\":"+ownrt::quote(e.miss_choice())+",\"bank_capture_bytes_avoided\":"+std::to_string(bank_capture_bytes_avoided)+",\"capacity_bytes\":"+std::to_string(capacity)+",\"captures\":"+std::to_string(captures)+",\"restores\":"+std::to_string(restores)+",\"snapshot_payload_bytes\":"+std::to_string(saved_bytes)+",\"capture_submissions\":"+std::to_string(capture_submissions)+",\"restore_submissions\":"+std::to_string(restore_submissions)+",\"restored_bytes\":"+std::to_string(restored_bytes)+",\"redo_omitted_bytes\":"+std::to_string(redo_omitted_bytes)+",\"redo_restores\":"+std::to_string(redo_restores)+",\"completed_redos\":"+std::to_string(completed_redos)+",\"redo_fallbacks\":"+std::to_string(redo_fallbacks)+",\"copy_extent_guard_unchanged\":true,\"private_backup_zeroed\":true,\"committed_state_scrubbed\":false,\"private_host_backup_empty\":true,\"snapshot_valid\":false,\"counters_are_telemetry\":true,\"rank0_shared_slot_bytes\":65536,\"rank1_shared_regions_untouched\":true}");
 }
#ifdef OWN_RT_HOST_ONLY
 // CPU-only negative control: write a byte excluded from the rollback image.
 // A subsequent strict final-state comparison MUST detect the corruption.
 void corrupt_protected_for_gate(int which){
  require(valid&&(which>=0&&which<=2),"negative control outside speculation");e.drain();
  if(which==2){
   // Deliberately omit a required, overwrite-only output. First-write-before-read
   // does not make its old bytes dispensable at terminal rollback.
   auto id=e.buffers[0].at("streams").id;
   auto it=std::find_if(saved.begin(),saved.end(),[&](const Extent& x){return x.id==id;});
   require(it!=saved.end(),"negative control lacks required streams extent");saved.erase(it);return;
  }
  const auto& list=which?protected_qsa:protected_active;require(!list.empty(),"negative control lacks protected extent");
  auto [id,bytes]=list.front();require(bytes,"empty protected extent");auto raw=e.readback(0,id,1);raw[0]^=1;e.upload(0,id,0,raw.data(),1);
 }
#endif
};
}
