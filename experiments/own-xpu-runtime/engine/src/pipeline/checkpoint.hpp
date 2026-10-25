#pragma once
// Included after Engine and the existing checked SnapshotFlat transport.
// This first wavefront proof copies complete mutable physical allocations. It
// intentionally does not inherit the one-rank redo-overwrite/bank omission rules.
namespace pipeline {
template<class Owner> class StageCheckpointFor {
 Owner& e;
 struct Item {Allocation id;size_t bytes,offset;std::string label;};
 std::vector<Item> items;
 struct HostItem {Allocation id;size_t bytes;std::string label;std::vector<uint8_t> before;};
 std::vector<HostItem> host_items;
 Allocation backup=0,capture_table=0,restore_table=0;
 std::vector<Allocation> capture_ids,restore_ids;
 size_t capacity=0,pinned_bytes=0,table_rows=0,tiles=0,allocation_count=0;
 bool active_=false,verify_;uint64_t captures_=0,commits_=0,aborts_=0,byte_checks_=0;
 unsigned parity=0;int active_bank=0,spare_bank=1,extent=32,alternate_extent=32;
 int64_t history0=0,history1=0;
 decltype(e.lookup_ids) lookup;
 decltype(e.selected) selected;
 decltype(e.loaded_layer) loaded;
 decltype(e.fp32_sources) fp32_sources;
 decltype(e.fp32_extents) fp32_extents;
 std::array<uint8_t,65536> output_before{};uint8_t* output=nullptr;
 void quiescent(){
  e.drain();require(!e.poisoned&&!e.integer(0,"error"),"wavefront checkpoint cannot erase sticky failure");
  require(!e.progress_pending&&!e.progress_callback&&!e.correction_exchange&&!e.reply_report.pending()&&!e.dev(0).before_compute&&!e.dev(0).after_compute,
          "wavefront checkpoint requires exclusive quiescent target owner");
  require(!e.prepare_async&&!e.head_export&&!e.head_publish&&!e.head_merge,"wavefront unsupported callback ownership");
 }
 void inventory()const{
  require(e.allocations.size()==allocation_count,"wavefront allocation set changed after load");
  for(const auto& item:items){const auto& row=e.dev(0).arena.row(item.id);
   require(row.live&&row.memory==Memory::device&&row.bytes==item.bytes&&row.label==item.label,"wavefront mutable allocation identity changed");}
  for(const auto& item:host_items){const auto& row=e.dev(0).arena.row(item.id);
   require(row.live&&row.memory==Memory::pinned&&row.bytes==item.bytes&&row.label==item.label,"wavefront pinned draft identity changed");}
 }
 void prepare(bool reverse){
  ownrt::CopyEngine copy(e.dev(0));std::vector<ownrt::PreparedCompute> checked;std::vector<size_t> lengths;
  e.dev(0).begin_capture(checked);
  try{for(const auto& item:items)for(size_t off=0;off<item.bytes;off+=SnapshotBatch::limit){const auto n=std::min(item.bytes-off,SnapshotBatch::limit);
    if(reverse)copy.copy(item.id,off,backup,item.offset+off,n,{});
    else copy.copy(backup,item.offset+off,item.id,off,n,{});
    lengths.push_back(n);
   }e.dev(0).end_capture();}catch(...){e.dev(0).end_capture();throw;}
  require(!checked.empty()&&checked.size()==lengths.size(),"wavefront checked snapshot descriptors");
  std::vector<SnapshotFlat::Item> rows;auto& ids=reverse?restore_ids:capture_ids;
  const Allocation table=reverse?restore_table:capture_table;ids={table};size_t end=0;
  for(size_t i=0;i<checked.size();++i){const auto& cmd=checked[i];require(cmd.ids.size()==2&&cmd.pointers.size()==2,"wavefront checked copy ABI");
   end+=(lengths[i]+SnapshotFlat::tile-1)/SnapshotFlat::tile;
   rows.push_back({static_cast<uint8_t*>(cmd.pointers[0]),static_cast<const uint8_t*>(cmd.pointers[1]),lengths[i],end});ids.insert(ids.end(),cmd.ids.begin(),cmd.ids.end());
  }
  require(rows.size()==table_rows,"wavefront fixed copy table cardinality");
  if(reverse)require(end==tiles,"wavefront reverse copy geometry");else tiles=end;
  e.upload(0,table,0,rows.data(),rows.size()*sizeof(rows[0]));e.drain();
 }
 void copy(bool reverse){
  inventory();SnapshotFlat op;op.count=table_rows;op.tiles=tiles;
  e.tail=e.dev(0).compute(op,reverse?restore_ids:capture_ids,{});e.drain();
 }
 void metadata_restore(){
  if(e.bank_parity!=parity){require(e.a.pipeline_first(),"wavefront nonfirst bank change");e.swap_state_banks();}
  require(e.bank_parity==parity&&e.active_bank==active_bank&&e.spare_bank==spare_bank,"wavefront bank identity restore");
  if(e.context_extent!=extent)e.admit_position(extent-1);
  if(e.a.pipeline_first()&&e.alternate_context_extent!=alternate_extent){e.swap_state_banks();e.admit_position(alternate_extent-1);e.swap_state_banks();}
  require(e.context_extent==extent&&e.alternate_context_extent==alternate_extent,"wavefront attention/prepared extent restore");
  e.history0=history0;e.history1=history1;e.lookup_ids=lookup;e.selected=selected;e.loaded_layer=loaded;
  e.fp32_sources=fp32_sources;e.fp32_extents=fp32_extents;
  for(size_t c=0;c<e.fp32_sources.size();++c)if(e.fp32_sources[c])require(e.dev(int(c)).arena.row(e.fp32_sources[c]).live,"wavefront dead cached source");
 }
public:
 explicit StageCheckpointFor(Owner& engine,bool verify,const std::vector<Allocation>& pinned={}):e(engine),verify_(verify){
  require(e.a.pipeline_enabled()&&e.a.pipeline_wavefront&&e.resident&&(!e.a.mtp||e.a.pipeline_live_draft)&&!e.a.prefill_rows,"wavefront checkpoint mode");quiescent();
  for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);if(!row.live||row.category==Category::weights)continue;
   // Legacy rank-zero snapshot storage is allocated for the preserved controller
   // but never used by WAVE_ROW. Only these exact private labels are excluded.
   if(row.label=="card0:speculative-private-image"||row.label=="card0:speculative-copy-table"||row.label=="card0:speculative-static-copy-table"){
    require(row.category==Category::runtime_overhead,"wavefront legacy-private category");continue;
   }
   require(owner.first==0&&row.memory==Memory::device&&row.bytes>0,"wavefront allocation owner/extent");
   require(row.bytes<=512ull*1024*1024&&capacity<=512ull*1024*1024-row.bytes,"wavefront complete checkpoint exceeds 512 MiB admission");
   items.push_back({id,row.bytes,capacity,row.label});capacity+=row.bytes;table_rows+=(row.bytes+SnapshotBatch::limit-1)/SnapshotBatch::limit;
  }
  // Engine::allocations deliberately tracks device memory only. Pinned draft
  // transports must come from the provider's explicit inventory, never that map.
  require(pinned.size()==size_t(e.a.pipeline_live_draft&&e.a.mtp?2:0),"wavefront exact pinned provider inventory");
  std::set<Allocation> pinned_ids;std::set<std::string> pinned_labels;
  for(auto id:pinned){
   require(e.a.pipeline_first()&&pinned_ids.insert(id).second&&!e.allocations.count(id),"wavefront duplicate/device pinned inventory");
   const auto& row=e.dev(0).arena.row(id);
   require(row.live&&row.memory==Memory::pinned&&pinned_labels.insert(row.label).second&&
     ((row.label=="card0:draft:publication"&&row.bytes==8&&row.category==Category::output_ring)||
      (row.label=="card0:draft:half-staging"&&row.bytes==4+e.stream_bytes()&&row.category==Category::pinned_slab)),"wavefront pinned draft allocation admission");
   host_items.push_back({id,row.bytes,row.label,std::vector<uint8_t>(row.bytes)});pinned_bytes+=row.bytes;
  }
  require(capacity>0&&table_rows>0&&table_rows<=4096,"wavefront checkpoint census");require(capacity+pinned_bytes<=512ull*1024*1024,"wavefront total checkpoint extent");
  backup=e.allocate(0,"wavefront-private-image",capacity,Category::runtime_overhead,Lifetime::process);
  capture_table=e.allocate(0,"wavefront-capture-table",table_rows*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
  restore_table=e.allocate(0,"wavefront-restore-table",table_rows*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
  prepare(false);prepare(true);allocation_count=e.allocations.size();
  std::ostringstream receipt;receipt<<"{\"schema\":\"ownrt.wavefront-checkpoint-layout.v1\",\"complete_mutable_physical_allocations\":true,\"bytes\":"<<capacity+pinned_bytes<<",\"device_bytes\":"<<capacity<<",\"pinned_bytes\":"<<pinned_bytes<<",\"allocations\":[";
  for(size_t i=0;i<items.size();++i){const auto& item=items[i];receipt<<(i?",":"")<<"{\"id\":"<<item.id<<",\"label\":"<<ownrt::quote(item.label)<<",\"bytes\":"<<item.bytes<<"}";}receipt<<"],\"pinned_allocations\":[";
  for(size_t i=0;i<host_items.size();++i){const auto& item=host_items[i];receipt<<(i?",":"")<<"{\"id\":"<<item.id<<",\"label\":"<<ownrt::quote(item.label)<<",\"bytes\":"<<item.bytes<<"}";}
  receipt<<"]}";save(e.a.output/"wavefront-checkpoint-layout.json",receipt.str());
 }
 bool active()const{return active_;}
 uint64_t aborts()const{return aborts_;}
 uint64_t byte_checks()const{return byte_checks_;}
 size_t bytes()const{return capacity+pinned_bytes;}
 void begin(uint8_t* shared){
  require(!active_,"wavefront checkpoint already active");quiescent();inventory();require(shared,"wavefront output slot");
  parity=e.bank_parity;active_bank=e.active_bank;spare_bank=e.spare_bank;extent=e.context_extent;alternate_extent=e.alternate_context_extent;
  history0=e.history0;history1=e.history1;lookup=e.lookup_ids;selected=e.selected;loaded=e.loaded_layer;fp32_sources=e.fp32_sources;fp32_extents=e.fp32_extents;
  for(auto& item:host_items)std::memcpy(item.before.data(),e.dev(0).arena.row(item.id).pointer,item.bytes);
  output=shared;std::memcpy(output_before.data(),output,output_before.size());copy(false);active_=true;++captures_;
 }
 void commit(){require(active_,"wavefront checkpoint commit without row");quiescent();inventory();active_=false;++commits_;}
 void abort(){
  require(active_,"wavefront checkpoint abort without row");quiescent();inventory();metadata_restore();copy(true);
  for(const auto& item:host_items)std::memcpy(e.dev(0).arena.row(item.id).pointer,item.before.data(),item.bytes);
  require(output,"wavefront output lifetime");std::memcpy(output,output_before.data(),output_before.size());
  // readback may allocate transient host transport, never a model allocation.
  if(verify_){const auto expected=e.readback(0,backup,capacity);
   for(const auto& item:items){const auto actual=e.readback(0,item.id,item.bytes);require(std::equal(actual.begin(),actual.end(),expected.begin()+item.offset),"wavefront abort full mutable bytes differ: "+item.label);}
   for(const auto& item:host_items)require(!std::memcmp(e.dev(0).arena.row(item.id).pointer,item.before.data(),item.bytes),"wavefront abort pinned draft bytes differ");
   require(std::equal(output_before.begin(),output_before.end(),output),"wavefront abort output slot differs");++byte_checks_;
  }
  require(e.history0==history0&&e.history1==history1&&e.lookup_ids==lookup&&e.selected==selected&&e.loaded_layer==loaded&&e.fp32_sources==fp32_sources&&e.fp32_extents==fp32_extents,"wavefront abort host metadata differs");
  active_=false;++aborts_;
 }
 void attest(const ownrt::wavefront::Ledger& ledger,const fs::path& destination={},int dump_marker=-1){
  ledger.boundary();require(!active_,"wavefront boundary has active checkpoint");quiescent();inventory();
  const int position=e.integer(0,"position");require(position==ledger.position(),"wavefront quiescent position differs from ledger");
  require(e.bank_parity==(e.a.pipeline_first()?unsigned(position%2):0u),"wavefront committed canonical bank parity");
  require(ledger.tentative_rows==captures_&&ledger.aborts==aborts_&&captures_==commits_+aborts_,"wavefront checkpoint ledger accounting");
  std::string seal_sha;
  if(dump_marker>=0){const auto seal=e.a.output/("state-"+std::to_string(dump_marker))/"state-seal.txt";
   require(fs::file_size(seal)<=4096,"wavefront state seal extent");std::ifstream f(seal,std::ios::binary);require(bool(f),"wavefront state seal missing");
   std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)),{});require(!bytes.empty()&&!f.bad()&&bytes.size()==fs::file_size(seal),"wavefront state seal read");seal_sha=hash(bytes);
  }
  std::ostringstream o;o<<"{\"schema\":\"ownrt.wavefront-state.v1\",\"mode\":\"verified-wavefront\",\"stage_id\":"<<e.a.pipeline_stage
   <<",\"dump_marker\":"<<dump_marker<<",\"state_seal_sha256\":"<<ownrt::quote(seal_sha)<<",\"pending_ticket\":false,\"actual_position\":"<<position<<",\"abort_count\":"<<aborts_<<",\"byteverified_restore_count\":"<<byte_checks_<<",\"saved_bytes\":"<<uint64_t(capacity+pinned_bytes)*captures_
   <<",\"committed_position\":"<<ledger.position()<<",\"pending_tickets\":0,\"checkpoint_active\":false,\"rows\":"<<ledger.rows<<",\"tentative_rows\":"<<ledger.tentative_rows
   <<",\"commits\":"<<ledger.commits<<",\"aborts\":"<<ledger.aborts<<",\"snapshot_captures\":"<<captures_<<",\"snapshot_commits\":"<<commits_<<",\"snapshot_aborts\":"<<aborts_
   <<",\"restore_verification_enabled\":"<<(verify_?"true":"false")<<",\"abort_byte_checks\":"<<byte_checks_<<",\"all_aborts_byte_verified\":"<<(aborts_==byte_checks_?"true":"false")
   <<",\"bank_parity\":"<<e.bank_parity<<",\"sticky_error\":0,\"full_mutable_checkpoint_bytes\":"<<capacity+pinned_bytes<<",\"inactive_alternate_banks\":[";
  bool comma=false;for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name);comma=true;}o<<"],\"canonical_bank_mapping\":{";comma=false;
  for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name)<<":{\"active_allocation\":"<<e.buffers[0].at(name).id<<",\"inactive_allocation\":"<<id<<"}";comma=true;}o<<"}}";
  const auto path=destination.empty()?e.a.output/"wavefront-quiescence.json":destination;
  if(dump_marker>=0&&fs::exists(path)){std::ifstream prior(path);std::string text((std::istreambuf_iterator<char>(prior)),{});require(text==o.str(),"wavefront sealed attestation changed");}
  else save(path,o.str());
 }
};
using StageCheckpoint=StageCheckpointFor<Engine>;
} // namespace pipeline
