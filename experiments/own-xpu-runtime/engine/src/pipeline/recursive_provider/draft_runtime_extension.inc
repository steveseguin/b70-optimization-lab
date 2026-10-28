// Included inside mtp36::DraftRuntime; batch.hpp is included outside the class.
// Calls existing live_step/compute; it contains no model arithmetic executor.
struct RecursiveRow {
 Allocation id{};size_t bytes=0,offset=0;Memory memory=Memory::device;std::string label;
 pipeline::CheckpointQsa qsa{};bool sparse=false;std::vector<uint8_t> pinned_before;
 bool operator==(const RecursiveRow&)const=default;
};
struct RecursiveExtent {size_t row=0,source=0,backup=0,bytes=0;bool operator==(const RecursiveExtent&)const=default;};
struct RecursiveHost {
 int position=0,extent=0,pending_confirmed=0,queued_probe=0,queued_confirmed=0,depth=0;
 bool disabled=false,async_pending=false,pending_head=false,reverse_present=false,captured=false;
 ownrt::Event publication_event=0;std::chrono::steady_clock::time_point pending_start;
 std::vector<uint8_t> reverse_bytes;
 bool operator==(const RecursiveHost&)const=default;
};
struct RecursiveTarget {
 decltype(e.fp32_sources) sources;decltype(e.fp32_extents) extents;
 decltype(e.lookup_ids) lookup;decltype(e.selected) selected;decltype(e.loaded_layer) loaded;
 int64_t history0=0,history1=0;unsigned parity=0;int active=0,spare=0,extent=0,alternate=0;
 bool operator==(const RecursiveTarget&)const=default;
};
uint64_t recursive_captures=0,recursive_restores=0,recursive_verified_restores=0;
Allocation recursive_image{};size_t recursive_bytes=0;bool recursive_active=false;
std::vector<RecursiveRow> recursive_rows;std::vector<RecursiveExtent> recursive_extents;std::map<Allocation,std::string> recursive_before_sha;RecursiveHost recursive_host;RecursiveTarget recursive_target;int recursive_class=0;
RecursiveHost recursive_host_state()const{
 return {position,context_extent,pending_confirmed,queued_probe,queued_confirmed,depth_probe,disabled,async_pending,pending_head,reverse_hidden!=nullptr,captured,publication_event,pending_start,probe_reverse_hidden};
}
RecursiveTarget recursive_target_state()const{
 return {e.fp32_sources,e.fp32_extents,e.lookup_ids,e.selected,e.loaded_layer,e.history0,e.history1,e.bank_parity,e.active_bank,e.spare_bank,e.context_extent,e.alternate_context_extent};
}
void recursive_idle(){
 auto admitted=[&](){return !disabled&&!e.poisoned&&!async_pending&&!publication_event&&!e.progress_pending&&!e.progress_callback&&!e.preparing_commands&&!e.draft_timing&&!reverse_hidden&&!depth_probe&&queued_probe==-1&&queued_confirmed==-1&&!e.dev(0).before_compute&&!e.dev(0).after_compute&&!e.correction_exchange&&!e.head_export&&!e.head_publish&&!e.head_merge&&!e.reply_report.pending();};
 // drain() can invoke Engine progress callbacks. Refuse borrowers BEFORE it.
 ownrt::recursive_provider_next::quiesce(admitted,[&](){e.drain();});
}
bool recursive_healthy(){
 if(disabled||e.poisoned)return false;const auto raw=e.readback(0,id("error"),4);int error=0;std::memcpy(&error,raw.data(),4);return !error&&!e.integer(0,"error");
}
void recursive_inventory(){
 require(recursive_image&&recursive_rows.size()==mutable_ids.size()+2,"recursive exact canonical inventory count");
 std::set<Allocation> observed;for(const auto& item:recursive_rows){const auto& row=e.dev(0).arena.row(item.id);
  require(observed.insert(item.id).second&&row.live&&row.label==item.label&&row.memory==item.memory&&row.bytes==item.bytes,"recursive allocation identity changed");
  if(item.memory==Memory::device)require(mutable_ids.count(item.id)&&e.allocations.count(item.id),"recursive canonical device membership");
  else require(item.memory==Memory::pinned&&!e.allocations.count(item.id)&&(item.id==publication||item.id==half_staging),"recursive explicit pinned membership");
 }
 require(observed.count(publication)&&observed.count(half_staging),"recursive pinned inventory incomplete");
 const auto& backup=e.dev(0).arena.row(recursive_image);require(backup.live&&backup.memory==Memory::device&&backup.category==Category::runtime_overhead&&backup.bytes==recursive_bytes&&backup.label=="card0:draft:recursive-private-image"&&e.allocations.count(recursive_image)&&!mutable_ids.count(recursive_image),"recursive private image identity");
}
void prepare_recursive_depth2(){
 recursive_idle();require(e.a.pipeline_live_draft&&e.a.pipeline_draft_partition&&e.a.pipeline_provider()&&e.a.mtp&&!recursive_image&&!recursive_active,"recursive initialization owner");
 const auto qsa=pipeline::checkpoint_qsa(p,buffers,e.dev(0).arena,mutable_ids);const int suffix=e.a.pipeline_ring_depth;require(suffix==2||suffix==3,"recursive suffix geometry");
 for(auto allocation:mutable_ids){const auto& row=e.dev(0).arena.row(allocation);require(row.live&&row.memory==Memory::device&&row.category!=Category::weights&&row.bytes>0,"recursive canonical allocation");
  const auto sparse=qsa.find(allocation);const size_t saved=sparse==qsa.end()?row.bytes:sparse->second.row_bytes*size_t(sparse->second.pooled?1:suffix);
  require(saved&&recursive_bytes<=32ull*1024*1024-saved,"recursive sparse canonical reserve bound");
  recursive_rows.push_back({allocation,row.bytes,recursive_bytes,row.memory,row.label,sparse==qsa.end()?pipeline::CheckpointQsa{}:sparse->second,sparse!=qsa.end(),{}});recursive_bytes+=saved;
 }
 for(auto allocation:{publication,half_staging}){const auto& row=e.dev(0).arena.row(allocation);require(row.live&&row.memory==Memory::pinned&&row.bytes==(allocation==publication?8:4+e.stream_bytes())&&row.category==(allocation==publication?Category::output_ring:Category::pinned_slab),"recursive exact pinned extent/category");recursive_rows.push_back({allocation,row.bytes,0,row.memory,row.label,{},false,std::vector<uint8_t>(row.bytes)});}
 require(recursive_bytes>0,"recursive empty canonical snapshot");
 recursive_image=e.allocate(0,"draft:recursive-private-image",recursive_bytes,Category::runtime_overhead,Lifetime::process);allocated+=recursive_bytes;recursive_inventory();
}
// A NEW explicit ownership class is required at integration: these are provider
// rollback storage, NOT canonical draft buffers and NOT target-owned storage.
std::vector<Allocation> live_private_recursive_inventory()const{return recursive_image?std::vector<Allocation>{recursive_image}:std::vector<Allocation>{};}
void recursive_flat_copy(bool restore){
 recursive_inventory();ownrt::CopyEngine copy(e.dev(0));
 std::vector<ownrt::PreparedCompute> checked;std::vector<size_t> lengths;
 e.dev(0).begin_capture(checked);
 try{
  for(const auto& extent:recursive_extents){const auto& item=recursive_rows[extent.row];
   require(item.memory==Memory::device&&extent.bytes&&extent.source<=item.bytes&&extent.bytes<=item.bytes-extent.source&&extent.backup<=recursive_bytes&&extent.bytes<=recursive_bytes-extent.backup,"recursive sparse disjoint extent");
   pipeline::checkpoint_copy_extent(e,copy,restore,recursive_image,item.id,extent.source,extent.backup,extent.bytes);
   for(size_t offset=0;offset<extent.bytes;offset+=pipeline::SnapshotBatch::limit)lengths.push_back(std::min(pipeline::SnapshotBatch::limit,extent.bytes-offset));
   require(checked.size()==lengths.size(),"recursive flat chunk count");
  }
  e.dev(0).end_capture();
 }catch(...){e.dev(0).end_capture();throw;}
 require(!checked.empty()&&checked.size()==lengths.size()&&checked.size()<=4096,"recursive checked flat descriptor count");
 for(size_t first=0;first<checked.size();first+=pipeline::SnapshotInlineFlat::width){
  pipeline::SnapshotInlineFlat operation;std::vector<Allocation> bindings;
  const size_t end=std::min(checked.size(),first+pipeline::SnapshotInlineFlat::width);
  for(size_t i=first;i<end;++i){const auto& command=checked[i];
   require(command.ids.size()==2&&command.pointers.size()==2,"recursive checked copy ABI");
   operation.tiles+=(lengths[i]+pipeline::SnapshotFlat::tile-1)/pipeline::SnapshotFlat::tile;
   operation.items[operation.count++]={static_cast<uint8_t*>(command.pointers[0]),static_cast<const uint8_t*>(command.pointers[1]),lengths[i],operation.tiles};
   bindings.insert(bindings.end(),command.ids.begin(),command.ids.end());
  }
  e.tail=e.dev(0).compute(operation,bindings,{});
 }
 for(auto& item:recursive_rows)if(item.memory==Memory::pinned){const auto& row=e.dev(0).arena.row(item.id);
  if(restore)std::memcpy(row.pointer,item.pinned_before.data(),item.bytes);
  else std::memcpy(item.pinned_before.data(),row.pointer,item.bytes);
 }
 e.drain();
}
void recursive_copy(bool restore){
 if(e.a.pipeline_ring_recursive_flat_copy){recursive_flat_copy(restore);return;}
 recursive_inventory();ownrt::CopyEngine copy(e.dev(0));
 for(const auto& extent:recursive_extents){const auto& item=recursive_rows[extent.row];pipeline::checkpoint_copy_extent(e,copy,restore,recursive_image,item.id,extent.source,extent.backup,extent.bytes);}
 for(auto& item:recursive_rows)if(item.memory==Memory::pinned){const auto& row=e.dev(0).arena.row(item.id);if(restore)std::memcpy(row.pointer,item.pinned_before.data(),item.bytes);else std::memcpy(item.pinned_before.data(),row.pointer,item.bytes);}
 e.drain();
}
void recursive_capture(bool verify=false){
 recursive_idle();require(!recursive_active&&recursive_healthy()&&recursive_extents.empty(),"recursive capture admission");
 require(position>=0&&position<p.g.context,"recursive capture position");const int suffix=std::min(e.a.pipeline_ring_depth,p.g.context-position);require(suffix>0,"recursive capture suffix");
 for(size_t i=0;i<recursive_rows.size();++i){const auto& item=recursive_rows[i];if(item.memory!=Memory::device)continue;
  if(!item.sparse)recursive_extents.push_back({i,0,item.offset,item.bytes});
  else for(int row=position;row<position+suffix;++row)if(!item.qsa.pooled||(row+1)%4==0)recursive_extents.push_back({i,item.qsa.offset(row,this->p.g.context),item.offset+size_t(item.qsa.pooled?0:row-position)*item.qsa.row_bytes,item.qsa.row_bytes});
 }
 recursive_host=recursive_host_state();recursive_target=recursive_target_state();recursive_class=e.current_cls;
 if(verify)for(const auto& item:recursive_rows)if(item.memory==Memory::device)recursive_before_sha[item.id]=pipeline::checkpoint_allocation_sha(e,item.id,item.bytes);
 recursive_copy(false);recursive_active=true;++recursive_captures;
}
void recursive_restore(bool verify){
 recursive_idle();require(recursive_active&&recursive_healthy(),"recursive failure cannot be rolled back");
 require(recursive_target_state()==recursive_target,"recursive branch mutated target metadata");
 recursive_copy(true);position=recursive_host.position;disabled=recursive_host.disabled;async_pending=recursive_host.async_pending;pending_head=recursive_host.pending_head;pending_confirmed=recursive_host.pending_confirmed;
 publication_event=recursive_host.publication_event;pending_start=recursive_host.pending_start;queued_probe=recursive_host.queued_probe;queued_confirmed=recursive_host.queued_confirmed;
 require(!recursive_host.reverse_present&&depth_probe==recursive_host.depth&&captured==recursive_host.captured,"recursive immutable/queued metadata changed");reverse_hidden=nullptr;probe_reverse_hidden=recursive_host.reverse_bytes;
 if(position<p.g.context)admit_position(recursive_host.extent);else require(context_extent==recursive_host.extent,"recursive capacity extent mismatch");e.current_cls=recursive_class;
 require(recursive_host_state()==recursive_host&&recursive_target_state()==recursive_target,"recursive complete host restoration mismatch");
 if(verify){for(const auto& item:recursive_rows){const auto& row=e.dev(0).arena.row(item.id);if(item.memory==Memory::pinned)require(!std::memcmp(row.pointer,item.pinned_before.data(),item.bytes),"recursive pinned restore mismatch");else require(pipeline::checkpoint_allocation_sha(e,item.id,item.bytes)==recursive_before_sha.at(item.id),"recursive full allocation restore mismatch: "+item.label);}}
 recursive_idle();require(recursive_healthy(),"recursive post-restore error");recursive_active=false;recursive_extents.clear();recursive_before_sha.clear();++recursive_restores;if(verify)++recursive_verified_restores;
}
struct RecursiveAdapter {
 DraftRuntime& d;bool verify;void idle(){d.recursive_idle();}bool healthy(){return d.recursive_healthy();}
 int position()const{return d.position;}int context()const{return d.p.g.context;}int vocab()const{return d.p.g.vocab;}
 int canonical(int confirmed,int position,bool head,const std::vector<uint8_t>& hidden){return d.live_step(confirmed,position,head,hidden.data(),hidden.size());}
 void capture(){d.recursive_capture(verify);}size_t snapshot_bytes()const{return d.recursive_bytes;}
 int recursive(int first){return d.compute(first,d.position+1,true,false,true);}
 void restore(bool verify){d.recursive_restore(verify);}
};
ownrt::ring_next::wire::ProposalMeta live_recursive_depth2(ownrt::recursive_provider_next::Sequence& sequence,const ownrt::recursive_provider_next::Input& input,const ownrt::recursive_provider_next::ExpectedPair& expected,bool verify){
 require(recursive_image&&!recursive_active,"recursive provider not initialized/idle");RecursiveAdapter adapter{*this,verify};return sequence.run(adapter,input,expected,verify);
}

// Owner-zero reset has already cleared canonical device buffers and both pinned
// buffers. Private physical storage is zeroed by the same checked owner pass.
// Retain every allocation/prepared binding; clear only request-owned saved data.
void recursive_reset_after_owner_zero(){
 recursive_idle();require(e.a.pipeline_ring_persistent_requests&&!recursive_active&&position==0&&context_extent==32&&recursive_healthy(),"recursive cold reset admission");recursive_inventory();
 recursive_host={};recursive_target={};recursive_class=0;recursive_extents.clear();recursive_before_sha.clear();
 for(auto& row:recursive_rows)std::fill(row.pinned_before.begin(),row.pinned_before.end(),0);
 recursive_captures=recursive_restores=recursive_verified_restores=0;
 require(!pending_head&&!pending_confirmed&&!reverse_hidden&&probe_reverse_hidden.empty()&&queued_probe==-1&&queued_confirmed==-1&&!publication_event,"recursive cold host state");
}
