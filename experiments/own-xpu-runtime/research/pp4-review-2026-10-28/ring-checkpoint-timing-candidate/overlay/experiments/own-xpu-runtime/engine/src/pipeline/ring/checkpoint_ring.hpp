#pragma once
// Bounded two/three-slot target checkpoint transport, included after Engine, SnapshotFlat and
// pipeline/operator_state.hpp. Slots share one inventory and frozen census.
namespace mtp36 {class DraftRuntime;}
namespace pipeline::ring_next {
// Pure checked geometry; the Engine allocator independently retains its per-allocation cap.
inline size_t checkpoint_ring_reserve(size_t bytes,size_t rows,size_t depth,size_t owned){
 constexpr size_t slot_limit=256ull*1024*1024,row_limit=4096,device_limit=30ull*1024*1024*1024;
 require(bytes&&bytes<=slot_limit&&rows&&rows<=row_limit&&(depth==2||depth==3),"ring backup geometry bound");
 const size_t reserve=depth*(bytes+2*rows*sizeof(SnapshotFlat::Item));
 require(reserve<=depth*(slot_limit+2*row_limit*sizeof(SnapshotFlat::Item)),"ring derived total backup/table reserve");
 require(owned<=device_limit&&reserve<=device_limit-owned,"ring complete reserve exceeds per-card arena admission");
 return reserve;
}
template<class Owner> class CheckpointRingFor {
 Owner& e;bool verify;
 struct Item {Allocation id;size_t bytes,offset;std::string label;CheckpointQsa qsa{};bool sparse=false;};
 struct Independent {Allocation id;size_t bytes,saved_bytes;Memory memory;std::string label;};
 struct Extent {size_t item=0,source=0,backup=0,bytes=0;};
 std::vector<Item> items,excluded_private;std::vector<Independent> independent,independent_private;
 size_t bytes_=0,table_rows=0,allocation_count=0;
 struct Metadata {
  unsigned parity=0;int active=0,spare=1,extent=32,alternate=32;int64_t history0=0,history1=0;
  decltype(e.lookup_ids) lookup;decltype(e.selected) selected;decltype(e.loaded_layer) loaded;
  decltype(e.fp32_sources) sources;decltype(e.fp32_extents) extents;
 };
 struct Slot {
  Allocation image=0,capture_table=0,restore_table=0;std::vector<Allocation> capture_ids,restore_ids;std::map<Allocation,std::string> before_sha;std::vector<Extent> extents;
  int position=0;size_t rows=0,tiles=0;bool active=false;Metadata metadata;std::array<uint8_t,65536> output{};uint8_t* shared=nullptr;
 };
 std::vector<Slot> slots;
 uint64_t captures_=0,restores_=0,byte_checks_=0,releases_=0;
 // Optional host wall attribution only. Nested prepare/copy scopes belong to
 // capture/restore totals; they must never be added to those totals.
 bool wall_timing_=false;
 struct WallTotals {double capture_ms=0,capture_prepare_ms=0,capture_flat_copy_ms=0,
                           restore_ms=0,restore_prepare_ms=0,restore_flat_copy_ms=0;} wall_;
 struct WallScope {
  double* total;std::chrono::steady_clock::time_point start;
  explicit WallScope(double* value):total(value),start(value?std::chrono::steady_clock::now():std::chrono::steady_clock::time_point{}){}
  ~WallScope(){if(total)*total+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();}
 };
 double* timed(double& total){return wall_timing_?&total:nullptr;}
 void idle(){
  e.drain();require(!e.poisoned&&!e.integer(0,"error"),"ring snapshot sticky failure");
  require(!e.progress_pending&&!e.progress_callback&&!e.correction_exchange&&!e.reply_report.pending()&&!e.dev(0).before_compute&&!e.dev(0).after_compute,
          "ring snapshot exclusive drained owner");
  require(!e.prepare_async&&!e.head_export&&!e.head_publish&&!e.head_merge,"ring snapshot unsupported callback owner");
 }
 void inventory(){
  require(e.allocations.size()==allocation_count,"ring allocation census changed");
  for(const auto& item:items){const auto& r=e.dev(0).arena.row(item.id);require(r.live&&r.memory==Memory::device&&r.bytes==item.bytes&&r.label==item.label,"ring target allocation changed");}
  for(const auto& item:independent_private){const auto& r=e.dev(0).arena.row(item.id);require(r.live&&r.memory==item.memory&&r.bytes==item.bytes&&r.label==item.label,"ring provider-private allocation changed");}
  for(const auto& item:independent){const auto& r=e.dev(0).arena.row(item.id);require(r.live&&r.memory==item.memory&&r.bytes==item.bytes&&r.label==item.label,"ring independent draft allocation changed");}
 }
 void prepare(Slot& slot,bool reverse,int position){
  if(!reverse){slot.extents.clear();const int suffix=std::min(int(slots.size()),e.p.g.context-position);
   for(size_t i=0;i<items.size();++i){const auto& item=items[i];if(!item.sparse)slot.extents.push_back({i,0,item.offset,item.bytes});
    else for(int p=position;p<position+suffix;++p)if(!item.qsa.pooled||(p+1)%4==0)slot.extents.push_back({i,item.qsa.offset(p,e.p.g.context),item.offset+size_t(item.qsa.pooled?0:p-position)*item.qsa.row_bytes,item.qsa.row_bytes});
   }
  }
  ownrt::CopyEngine copy(e.dev(0));std::vector<ownrt::PreparedCompute> checked;std::vector<size_t> lengths;
  e.dev(0).begin_capture(checked);
  try{for(const auto& extent:slot.extents){const auto& item=items[extent.item];
    checkpoint_copy_extent(e,copy,reverse,slot.image,item.id,extent.source,extent.backup,extent.bytes);
    for(size_t offset=0;offset<extent.bytes;offset+=SnapshotBatch::limit)lengths.push_back(std::min(SnapshotBatch::limit,extent.bytes-offset));require(checked.size()==lengths.size(),"ring chunk count");
   }e.dev(0).end_capture();}catch(...){e.dev(0).end_capture();throw;}
  require(!checked.empty()&&checked.size()==lengths.size()&&checked.size()<=table_rows,"ring checked descriptor count "+std::to_string(checked.size())+"/"+std::to_string(lengths.size())+" capacity "+std::to_string(table_rows));
  auto& ids=reverse?slot.restore_ids:slot.capture_ids;const auto table=reverse?slot.restore_table:slot.capture_table;ids={table};
  std::vector<SnapshotFlat::Item> rows;size_t total=0;
  for(size_t i=0;i<checked.size();++i){const auto& command=checked[i];require(command.ids.size()==2&&command.pointers.size()==2,"ring checked copy ABI");
   total+=(lengths[i]+SnapshotFlat::tile-1)/SnapshotFlat::tile;
   rows.push_back({static_cast<uint8_t*>(command.pointers[0]),static_cast<const uint8_t*>(command.pointers[1]),lengths[i],total});
   ids.insert(ids.end(),command.ids.begin(),command.ids.end());
  }
  slot.rows=rows.size();slot.tiles=total;e.upload(0,table,0,rows.data(),rows.size()*sizeof(rows[0]));e.drain();
 }
 void copy(Slot& slot,bool reverse){inventory();SnapshotFlat op;op.count=slot.rows;op.tiles=slot.tiles;e.tail=e.dev(0).compute(op,reverse?slot.restore_ids:slot.capture_ids,{});e.drain();}
 void save_metadata(Slot& slot){auto& m=slot.metadata;m.parity=e.bank_parity;m.active=e.active_bank;m.spare=e.spare_bank;m.extent=e.context_extent;m.alternate=e.alternate_context_extent;
  m.history0=e.history0;m.history1=e.history1;m.lookup=e.lookup_ids;m.selected=e.selected;m.loaded=e.loaded_layer;m.sources=e.fp32_sources;m.extents=e.fp32_extents;}
 void restore_metadata(const Slot& slot){const auto& m=slot.metadata;
  if(e.bank_parity!=m.parity){require(e.a.pipeline_first(),"ring unexpected middle-stage bank parity");e.swap_state_banks();}
  require(e.bank_parity==m.parity&&e.active_bank==m.active&&e.spare_bank==m.spare,"ring saved physical bank identity");
  if(e.context_extent!=m.extent)e.admit_position(m.extent-1);
  if(e.a.pipeline_first()&&e.alternate_context_extent!=m.alternate){e.swap_state_banks();e.admit_position(m.alternate-1);e.swap_state_banks();}
  require(e.context_extent==m.extent&&e.alternate_context_extent==m.alternate,"ring saved attention metadata");
  e.history0=m.history0;e.history1=m.history1;e.lookup_ids=m.lookup;e.selected=m.selected;e.loaded_layer=m.loaded;e.fp32_sources=m.sources;e.fp32_extents=m.extents;
  for(auto id:e.fp32_sources)if(id)require(e.dev(0).arena.row(id).live,"ring restored cache references dead allocation");
 }
public:
 CheckpointRingFor(Owner& owner,bool full_byte_verification,const OperatorStatePartition& partition):CheckpointRingFor(owner,full_byte_verification,partition,static_cast<const mtp36::DraftRuntime*>(nullptr)){}
 template<class Draft> CheckpointRingFor(Owner& owner,bool full_byte_verification,const OperatorStatePartition& partition,const Draft* provider):e(owner),verify(full_byte_verification){
  if(const char* flag=std::getenv("OWNRT_RING_CHECKPOINT_WALL_TIMING")){
   require(std::string(flag)=="0"||std::string(flag)=="1","ring checkpoint wall timing flag");
   wall_timing_=e.a.pipeline_first()&&std::string(flag)=="1";
  }
  require(owner.a.pipeline_ring_depth==2||owner.a.pipeline_ring_depth==3,"ring configured snapshot capacity");slots.resize(size_t(owner.a.pipeline_ring_depth));
  idle();require(e.resident&&e.a.pipeline_enabled()&&(!e.a.prefill_rows||e.a.pipeline_ring_persistent_requests),"ring resident verified-prefill/scalar owner");
  require(!e.a.mtp||partition.enabled,"ring provider needs independent state partition");
  std::set<Allocation> private_ids(partition.draft_private.begin(),partition.draft_private.end());
  std::set<Allocation> draft(partition.draft_device.begin(),partition.draft_device.end()),target(partition.target_device.begin(),partition.target_device.end());
  require(!partition.enabled||(!draft.empty()&&draft.size()==partition.draft_device.size()&&target.size()==partition.target_device.size()),"ring explicit complete ownership");
  for(auto id:partition.draft_device){const auto& row=e.dev(0).arena.row(id);require(e.allocations.count(id)&&row.live&&row.memory==Memory::device&&row.category!=Category::weights&&!target.count(id),"ring draft device identity");size_t saved=row.bytes;if(provider){const auto saved_row=std::find_if(provider->recursive_rows.begin(),provider->recursive_rows.end(),[&](const auto& item){return item.id==id;});require(saved_row!=provider->recursive_rows.end()&&saved_row->memory==Memory::device,"ring recursive canonical reserve metadata");saved=saved_row->sparse?saved_row->qsa.row_bytes*size_t(saved_row->qsa.pooled?1:slots.size()):saved_row->bytes;}independent.push_back({id,row.bytes,saved,row.memory,row.label});}
  require(private_ids.size()==partition.draft_private.size()&&private_ids.size()<=1,"ring provider-private census");
  for(auto id:private_ids){const auto& row=e.dev(0).arena.row(id);require(partition.enabled&&e.allocations.count(id)&&!target.count(id)&&!draft.count(id)&&row.live&&row.memory==Memory::device&&row.category==Category::runtime_overhead&&row.label=="card0:draft:recursive-private-image","ring explicit provider-private image");independent_private.push_back({id,row.bytes,row.bytes,row.memory,row.label});}
  std::set<Allocation> pinned;
  for(auto id:partition.draft_pinned){const auto& row=e.dev(0).arena.row(id);require(pinned.insert(id).second&&!e.allocations.count(id)&&row.live&&row.memory==Memory::pinned,"ring draft pinned identity");independent.push_back({id,row.bytes,row.bytes,row.memory,row.label});}
  require(!partition.enabled||pinned.size()==2,"ring pinned provider inventory");
  for(const auto& [id,where]:e.allocations){const auto& row=e.dev(where.first).arena.row(id);require(where.first==0&&row.live&&row.memory==Memory::device,"ring owner census");if(row.category==Category::weights)continue;
   if(partition.enabled){require(target.count(id)+draft.count(id)+private_ids.count(id)==1,"ring overlapping/unassigned mutable allocation");if(draft.count(id)||private_ids.count(id))continue;}
   if(row.label=="card0:speculative-private-image"||row.label=="card0:speculative-copy-table"||row.label=="card0:speculative-static-copy-table"){require(row.category==Category::runtime_overhead,"ring legacy private identity");excluded_private.push_back({id,row.bytes,0,row.label});continue;}
   require(!row.label.starts_with("card0:wavefront-")&&!row.label.starts_with("card0:ring:"),"ring cannot coexist with another snapshot owner");
   if(row.label.starts_with("card0:prefill:"))continue; // row-local op15 scratch is never read by speculative decode.
   require(row.bytes>0,"ring target allocation extent");
   items.push_back({id,row.bytes,0,row.label});
  }
  std::set<Allocation> scope;for(const auto& item:items)scope.insert(item.id);const auto qsa=checkpoint_qsa(e.p,e.buffers[0],e.dev(0).arena,scope);
  for(auto& item:items){const auto sparse=qsa.find(item.id);item.sparse=sparse!=qsa.end();if(item.sparse)item.qsa=sparse->second;const size_t saved=item.sparse?item.qsa.row_bytes*size_t(item.qsa.pooled?1:slots.size()):item.bytes;
   require(saved&&saved<=256ull*1024*1024&&bytes_<=256ull*1024*1024-saved,"ring sparse aggregate per-slot backup bound");item.offset=bytes_;bytes_+=saved;table_rows+=item.sparse?size_t(item.qsa.pooled?1:slots.size())*((item.qsa.row_bytes+SnapshotBatch::limit-1)/SnapshotBatch::limit):(saved+SnapshotBatch::limit-1)/SnapshotBatch::limit;
  }
  require(bytes_&&table_rows&&table_rows<=4096,"ring target snapshot census");
  constexpr size_t device_limit=30ull*1024*1024*1024;
  size_t owned=0;for(const auto& [id,where]:e.allocations){
   require(where.first==0&&where.second<=device_limit&&owned<=device_limit-where.second,"ring device ownership sum bound");owned+=where.second;
  }
  if constexpr(requires{e.owned_bytes.at(0);})require(owned==e.owned_bytes.at(0),"ring device ownership accounting");
  (void)checkpoint_ring_reserve(bytes_,table_rows,slots.size(),owned);
  // Allocate EVERY slot before preparing/freezing. No snapshot ever includes
  // another slot's private image, descriptors or mutable host bookkeeping.
  for(size_t i=0;i<slots.size();++i){auto& s=slots[i];const auto label="ring:"+std::to_string(i);
   s.image=e.allocate(0,label+":image",bytes_,Category::runtime_overhead,Lifetime::process);
   s.capture_table=e.allocate(0,label+":capture",table_rows*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
   s.restore_table=e.allocate(0,label+":restore",table_rows*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
  }
  for(auto& s:slots){prepare(s,false,0);prepare(s,true,0);}allocation_count=e.allocations.size();inventory();
 }
 bool active(int index)const{require(index>=0&&size_t(index)<slots.size(),"ring slot index");return slots[size_t(index)].active;}
 int capture(uint8_t* shared){WallScope total(timed(wall_.capture_ms));idle();inventory();require(shared,"ring output mapping");int index=-1;for(int i=0;i<int(slots.size());++i)if(!slots[size_t(i)].active){index=i;break;}require(index>=0,"ring checkpoint full");
  auto& slot=slots[size_t(index)];slot.position=e.integer(0,"position");require(slot.position>=0&&slot.position<e.p.g.context,"ring capture position");save_metadata(slot);slot.shared=shared;std::memcpy(slot.output.data(),shared,slot.output.size());if(verify)for(const auto& item:items)slot.before_sha[item.id]=checkpoint_allocation_sha(e,item.id,item.bytes);{WallScope phase(timed(wall_.capture_prepare_ms));prepare(slot,false,slot.position);}
  {WallScope phase(timed(wall_.capture_flat_copy_ms));copy(slot,false);}slot.active=true;++captures_;return index;}
 void restore(int index){WallScope total(timed(wall_.restore_ms));idle();inventory();require(active(index),"ring restore inactive slot");auto& slot=slots[size_t(index)];restore_metadata(slot);
  {WallScope phase(timed(wall_.restore_prepare_ms));prepare(slot,true,slot.position);}
  {WallScope phase(timed(wall_.restore_flat_copy_ms));copy(slot,true);}require(slot.shared,"ring saved output mapping");std::memcpy(slot.shared,slot.output.data(),slot.output.size());
  if(verify){for(const auto& item:items)require(checkpoint_allocation_sha(e,item.id,item.bytes)==slot.before_sha.at(item.id),"ring full target allocation restore differs: "+item.label);
   require(std::equal(slot.output.begin(),slot.output.end(),slot.shared),"ring output restore differs");++byte_checks_;}
  require(!e.integer(0,"error"),"ring restore sticky error");++restores_;
 }
 void release(int index){idle();inventory();require(active(index),"ring double slot release");slots[size_t(index)].active=false;slots[size_t(index)].shared=nullptr;++releases_;}
 void reset_after_owner_zero(){idle();inventory();for(const auto& s:slots)require(!s.active,"ring reset pending slot");require(e.integer(0,"position")==0&&e.bank_parity==0,"ring cold reset position/banks");
  e.admit_position(0);if(e.a.pipeline_first()&&e.alternate_context_extent!=32){e.swap_state_banks();e.admit_position(0);e.swap_state_banks();}
  for(auto& s:slots){prepare(s,false,0);prepare(s,true,0);s.shared=nullptr;s.output.fill(0);s.metadata={};s.position=0;s.before_sha.clear();}inventory();captures_=restores_=byte_checks_=releases_=0;wall_={};
 }
 void write_layout(const fs::path& path,bool live=false){
  inventory();require(live||(independent.empty()&&independent_private.empty()),"target-only ring layout requires absent provider");
  std::ostringstream o;o<<"{\"schema\":"<<ownrt::quote(live?(slots.size()==3?"ownrt.ring-checkpoint-layout.live.sparse.v2":"ownrt.ring-checkpoint-layout.live.sparse.v1"):"ownrt.ring-checkpoint-layout.sparse.v1")<<",\"complete_target_owned_mutable_allocations\":false,\"target_mutable_allocation_coverage\":\"complete\",\"checkpoint_policy\":\"full-non-qsa+sparse-positional-qsa-rows\",\"restore_verification\":\"full-allocation-streaming-sha256\",\"provider_present\":"<<(independent.empty()?"false":"true")<<",\"ring_capacity\":"<<slots.size()<<",\"slot_reserve_bytes\":"<<bytes_<<",\"slot_bytes\":"<<bytes_<<",\"allocations\":[";
  auto item_json=[&](Allocation id,const std::string& label,size_t bytes){o<<"{\"id\":"<<id<<",\"label\":"<<ownrt::quote(label)<<",\"bytes\":"<<bytes<<"}";};
  for(size_t i=0;i<items.size();++i){if(i)o<<',';const auto& item=items[i];const size_t saved=item.sparse?item.qsa.row_bytes*size_t(item.qsa.pooled?1:slots.size()):item.bytes;o<<"{\"id\":"<<item.id<<",\"label\":"<<ownrt::quote(item.label)<<",\"bytes\":"<<item.bytes<<",\"saved_bytes\":"<<saved<<",\"checkpoint\":"<<ownrt::quote(item.sparse?"sparse-positional-suffix-rows":"full-allocation")<<"}";}o<<"],\"excluded_private_runtime_allocations\":[";
  for(size_t i=0;i<excluded_private.size();++i){if(i)o<<',';const auto& item=excluded_private[i];o<<"{\"id\":"<<item.id<<",\"label\":"<<ownrt::quote(item.label)<<",\"bytes\":"<<item.bytes<<",\"reason\":\"inactive-legacy-snapshot\"}";}o<<"],\"checkpoint_private_allocations\":[";
  bool comma=false;for(const auto& slot:slots)for(auto id:{slot.image,slot.capture_table,slot.restore_table}){if(comma)o<<',';const auto& row=e.dev(0).arena.row(id);item_json(id,row.label,row.bytes);comma=true;}o<<"]";
  if(live){auto emit=[&](const auto& rows){bool comma=false;for(const auto& item:rows){o<<(comma?",":"")<<"{\"id\":"<<item.id<<",\"label\":"<<ownrt::quote(item.label)<<",\"bytes\":"<<item.bytes<<",\"saved_bytes\":"<<item.saved_bytes<<",\"memory\":"<<ownrt::quote(item.memory==Memory::pinned?"pinned":"device")<<"}";comma=true;}};o<<",\"independent_draft_allocations\":[";emit(independent);o<<"],\"provider_private_allocations\":[";emit(independent_private);o<<"]";}
  o<<"}";save(path,o.str());
 }
 void borrow_boundary(size_t pending){idle();inventory();size_t active=0;for(const auto& slot:slots)active+=slot.active?1:0;require(pending<=slots.size()&&active==pending,"provider borrow target checkpoint count");}
 void boundary(){idle();inventory();for(const auto& slot:slots)require(!slot.active,"ring active slot at boundary");}
 std::string wall_timing_json()const{
  if(!wall_timing_)return "null";
  std::ostringstream out;out<<"{\"schema\":\"ownrt.ring-checkpoint-wall-timing.v1\",\"clock\":\"steady_clock\",\"units\":\"milliseconds\",\"diagnostic_only\":true,\"capture_calls\":"<<captures_<<",\"restore_calls\":"<<restores_
   <<",\"capture_total_ms\":"<<wall_.capture_ms<<",\"capture_prepare_ms\":"<<wall_.capture_prepare_ms<<",\"capture_flat_copy_ms\":"<<wall_.capture_flat_copy_ms
   <<",\"restore_total_ms\":"<<wall_.restore_ms<<",\"restore_prepare_ms\":"<<wall_.restore_prepare_ms<<",\"restore_flat_copy_ms\":"<<wall_.restore_flat_copy_ms
   <<",\"full_byte_verification\":"<<(verify?"true":"false")<<",\"scope\":\"Completed request-local host scopes; prepare and flat-copy are nested within their capture/restore total. Prepare includes descriptor upload and its existing drain; flat-copy includes inventory, submit and existing completion drain. Totals also include guards, metadata and optional full-byte verification. No GPU timestamps; do not sum overlapping scopes.\"}";return out.str();
 }
 uint64_t releases()const{return releases_;}
 size_t slot_bytes()const{return bytes_;}uint64_t captures()const{return captures_;}uint64_t restores()const{return restores_;}uint64_t byte_checks()const{return byte_checks_;}
};
}
