#pragma once
// Unpromoted transport, included after Engine, SnapshotFlat and
// pipeline/operator_state.hpp. Two slots share one inventory and frozen census.
namespace pipeline::ring_next {
template<class Owner> class CheckpointRingFor {
 Owner& e;bool verify;
 struct Item {Allocation id;size_t bytes,offset;std::string label;};
 struct Independent {Allocation id;size_t bytes;Memory memory;std::string label;};
 std::vector<Item> items;std::vector<Independent> independent;
 size_t bytes_=0,table_rows=0,tiles=0,allocation_count=0;
 struct Metadata {
  unsigned parity=0;int active=0,spare=1,extent=32,alternate=32;int64_t history0=0,history1=0;
  decltype(e.lookup_ids) lookup;decltype(e.selected) selected;decltype(e.loaded_layer) loaded;
  decltype(e.fp32_sources) sources;decltype(e.fp32_extents) extents;
 };
 struct Slot {
  Allocation image=0,capture_table=0,restore_table=0;std::vector<Allocation> capture_ids,restore_ids;
  bool active=false;Metadata metadata;std::array<uint8_t,65536> output{};uint8_t* shared=nullptr;
 };
 std::array<Slot,2> slots;
 uint64_t captures_=0,restores_=0,byte_checks_=0;
 void idle(){
  e.drain();require(!e.poisoned&&!e.integer(0,"error"),"ring snapshot sticky failure");
  require(!e.progress_pending&&!e.progress_callback&&!e.correction_exchange&&!e.reply_report.pending()&&!e.dev(0).before_compute&&!e.dev(0).after_compute,
          "ring snapshot exclusive drained owner");
  require(!e.prepare_async&&!e.head_export&&!e.head_publish&&!e.head_merge,"ring snapshot unsupported callback owner");
 }
 void inventory(){
  require(e.allocations.size()==allocation_count,"ring allocation census changed");
  for(const auto& item:items){const auto& r=e.dev(0).arena.row(item.id);require(r.live&&r.memory==Memory::device&&r.bytes==item.bytes&&r.label==item.label,"ring target allocation changed");}
  for(const auto& item:independent){const auto& r=e.dev(0).arena.row(item.id);require(r.live&&r.memory==item.memory&&r.bytes==item.bytes&&r.label==item.label,"ring independent draft allocation changed");}
 }
 void prepare(Slot& slot,bool reverse){
  ownrt::CopyEngine copy(e.dev(0));std::vector<ownrt::PreparedCompute> checked;std::vector<size_t> lengths;
  e.dev(0).begin_capture(checked);
  try{for(const auto& item:items)for(size_t offset=0;offset<item.bytes;offset+=SnapshotBatch::limit){const size_t n=std::min(item.bytes-offset,SnapshotBatch::limit);
    if(reverse)copy.copy(item.id,offset,slot.image,item.offset+offset,n,{});
    else copy.copy(slot.image,item.offset+offset,item.id,offset,n,{});
    lengths.push_back(n);
   }e.dev(0).end_capture();}catch(...){e.dev(0).end_capture();throw;}
  require(!checked.empty()&&checked.size()==lengths.size()&&checked.size()==table_rows,"ring checked descriptor count");
  auto& ids=reverse?slot.restore_ids:slot.capture_ids;const auto table=reverse?slot.restore_table:slot.capture_table;ids={table};
  std::vector<SnapshotFlat::Item> rows;size_t total=0;
  for(size_t i=0;i<checked.size();++i){const auto& command=checked[i];require(command.ids.size()==2&&command.pointers.size()==2,"ring checked copy ABI");
   total+=(lengths[i]+SnapshotFlat::tile-1)/SnapshotFlat::tile;
   rows.push_back({static_cast<uint8_t*>(command.pointers[0]),static_cast<const uint8_t*>(command.pointers[1]),lengths[i],total});
   ids.insert(ids.end(),command.ids.begin(),command.ids.end());
  }
  if(tiles)require(tiles==total,"ring slot copy geometry mismatch");else tiles=total;
  e.upload(0,table,0,rows.data(),rows.size()*sizeof(rows[0]));e.drain();
 }
 void copy(Slot& slot,bool reverse){inventory();SnapshotFlat op;op.count=table_rows;op.tiles=tiles;e.tail=e.dev(0).compute(op,reverse?slot.restore_ids:slot.capture_ids,{});e.drain();}
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
 CheckpointRingFor(Owner& owner,bool full_byte_verification,const OperatorStatePartition& partition):e(owner),verify(full_byte_verification){
  idle();require(e.resident&&e.a.pipeline_enabled()&&!e.a.prefill_rows,"ring resident scalar owner");
  require(!e.a.mtp||partition.enabled,"ring provider needs independent state partition");
  std::set<Allocation> draft(partition.draft_device.begin(),partition.draft_device.end()),target(partition.target_device.begin(),partition.target_device.end());
  require(!partition.enabled||(!draft.empty()&&draft.size()==partition.draft_device.size()&&target.size()==partition.target_device.size()),"ring explicit complete ownership");
  for(auto id:partition.draft_device){const auto& row=e.dev(0).arena.row(id);require(e.allocations.count(id)&&row.live&&row.memory==Memory::device&&row.category!=Category::weights&&!target.count(id),"ring draft device identity");independent.push_back({id,row.bytes,row.memory,row.label});}
  std::set<Allocation> pinned;
  for(auto id:partition.draft_pinned){const auto& row=e.dev(0).arena.row(id);require(pinned.insert(id).second&&!e.allocations.count(id)&&row.live&&row.memory==Memory::pinned,"ring draft pinned identity");independent.push_back({id,row.bytes,row.memory,row.label});}
  require(!partition.enabled||pinned.size()==2,"ring pinned provider inventory");
  for(const auto& [id,where]:e.allocations){const auto& row=e.dev(where.first).arena.row(id);require(where.first==0&&row.live&&row.memory==Memory::device,"ring owner census");if(row.category==Category::weights)continue;
   if(partition.enabled){require(target.count(id)!=draft.count(id),"ring overlapping/unassigned mutable allocation");if(draft.count(id))continue;}
   if(row.label=="card0:speculative-private-image"||row.label=="card0:speculative-copy-table"||row.label=="card0:speculative-static-copy-table"){require(row.category==Category::runtime_overhead,"ring legacy private identity");continue;}
   require(!row.label.starts_with("card0:wavefront-")&&!row.label.starts_with("card0:ring:"),"ring cannot coexist with another snapshot owner");
   require(row.bytes>0&&row.bytes<=256ull*1024*1024&&bytes_<=256ull*1024*1024-row.bytes,"ring aggregate two-slot backup bound");
   items.push_back({id,row.bytes,bytes_,row.label});bytes_+=row.bytes;table_rows+=(row.bytes+SnapshotBatch::limit-1)/SnapshotBatch::limit;
  }
  require(bytes_&&table_rows&&table_rows<=4096,"ring target snapshot census");
  require(2*bytes_+4*table_rows*sizeof(SnapshotFlat::Item)<=512ull*1024*1024,"ring total backup/table reserve");
  // Allocate EVERY slot before preparing/freezing. No snapshot ever includes
  // another slot's private image, descriptors or mutable host bookkeeping.
  for(size_t i=0;i<slots.size();++i){auto& s=slots[i];const auto label="ring:"+std::to_string(i);
   s.image=e.allocate(0,label+":image",bytes_,Category::runtime_overhead,Lifetime::process);
   s.capture_table=e.allocate(0,label+":capture",table_rows*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
   s.restore_table=e.allocate(0,label+":restore",table_rows*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
  }
  for(auto& s:slots){prepare(s,false);prepare(s,true);}allocation_count=e.allocations.size();inventory();
 }
 bool active(int index)const{require(index>=0&&index<2,"ring slot index");return slots[size_t(index)].active;}
 int capture(uint8_t* shared){idle();inventory();require(shared,"ring output mapping");int index=-1;for(int i=0;i<2;++i)if(!slots[size_t(i)].active){index=i;break;}require(index>=0,"ring checkpoint full");
  auto& slot=slots[size_t(index)];save_metadata(slot);slot.shared=shared;std::memcpy(slot.output.data(),shared,slot.output.size());copy(slot,false);slot.active=true;++captures_;return index;}
 void restore(int index){idle();inventory();require(active(index),"ring restore inactive slot");auto& slot=slots[size_t(index)];restore_metadata(slot);copy(slot,true);require(slot.shared,"ring saved output mapping");std::memcpy(slot.shared,slot.output.data(),slot.output.size());
  if(verify){const auto expected=e.readback(0,slot.image,bytes_);for(const auto& item:items){const auto actual=e.readback(0,item.id,item.bytes);require(std::equal(actual.begin(),actual.end(),expected.begin()+item.offset),"ring full target restore bytes differ");}
   require(std::equal(slot.output.begin(),slot.output.end(),slot.shared),"ring output restore differs");++byte_checks_;}
  require(!e.integer(0,"error"),"ring restore sticky error");++restores_;
 }
 void release(int index){idle();inventory();require(active(index),"ring double slot release");slots[size_t(index)].active=false;slots[size_t(index)].shared=nullptr;}
 void reset_after_owner_zero(){idle();inventory();for(const auto& s:slots)require(!s.active,"ring reset pending slot");require(e.integer(0,"position")==0&&e.bank_parity==0,"ring cold reset position/banks");
  e.admit_position(0);if(e.a.pipeline_first()&&e.alternate_context_extent!=32){e.swap_state_banks();e.admit_position(0);e.swap_state_banks();}
  for(auto& s:slots){prepare(s,false);prepare(s,true);s.shared=nullptr;s.output.fill(0);s.metadata={};}inventory();captures_=restores_=byte_checks_=0;
 }
 size_t slot_bytes()const{return bytes_;}uint64_t captures()const{return captures_;}uint64_t restores()const{return restores_;}uint64_t byte_checks()const{return byte_checks_;}
};
}
