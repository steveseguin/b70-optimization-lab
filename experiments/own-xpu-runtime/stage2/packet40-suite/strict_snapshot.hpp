#pragma once
// Exact speculative rollback. Only the private backup is cleared at a request
// boundary; no model allocation is canonicalized, hidden or reset before hashing.
namespace pipeline {
class SpeculativeImage {
 Engine& e;
 struct Source {std::string name;Allocation standalone=0;size_t bytes=0;bool bank=false,kv=false,pooled=false;};
 struct Extent {Allocation id;size_t offset,bytes,backup_offset;};
 std::vector<Source> sources;
 std::vector<Extent> saved;
 std::vector<std::pair<Allocation,size_t>> protected_active,protected_qsa;
 Allocation backup=0;size_t capacity=0;bool valid=false,dirty=false;
 std::array<uint8_t,65536> shared_before{};uint8_t* shared_slot=nullptr;
 unsigned parity=0;int64_t history0=0,history1=0;
 std::map<std::string,std::vector<uint8_t>> lookup;
 std::vector<std::vector<uint32_t>> selected;
 std::vector<int> loaded;
 std::vector<Allocation> fp32_sources;
 std::vector<size_t> fp32_extents;
 uint64_t captures=0,restores=0,saved_bytes=0;
 void zero_private() {
  if(!backup)return;
  std::vector<uint8_t> zeros(std::min(capacity,size_t(4*1024*1024)),0);
  for(size_t off=0;off<capacity;off+=zeros.size())e.upload(0,backup,off,zeros.data(),std::min(zeros.size(),capacity-off));
  dirty=false;
 }
 void copy(bool restore) {
  ownrt::CopyEngine engine(e.dev(0));
  for(const auto& x:saved)for(size_t off=0;off<x.bytes;off+=128ull*1024*1024){
   size_t count=std::min(x.bytes-off,size_t(128ull*1024*1024));
   e.tail=restore?engine.copy(x.id,x.offset+off,backup,x.backup_offset+off,count,{}):engine.copy(backup,x.backup_offset+off,x.id,x.offset+off,count,{});
  }
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
   capacity+=row.bytes;sources.push_back(std::move(row));
  }
  for(const auto& [name,id]:e.state_spares)represented.insert(id);
  for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
   if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab||represented.count(id)||id==e.one[0])continue;
   require(owner.first==0&&row.memory==Memory::device,"snapshot owner/memory");
   sources.push_back({{},id,row.bytes,false,false,false});capacity+=row.bytes;
  }
  require(capacity>0,"empty speculative snapshot");saved.reserve(sources.size());
  backup=e.allocate(0,"speculative-private-image",capacity,Category::runtime_overhead,Lifetime::process);
  zero_private();
 }
 void begin(uint8_t* shared) {
  require(e.a.rank==0&&backup&&!valid,"snapshot begin ownership");e.drain();
  require(!e.poisoned&&!e.integer(0,"error"),"snapshot cannot erase target failure");
  // Host layer streaming releases its weights at every completed half. Restoring
  // metadata never revives an allocation freed by a later layer transition.
  if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,"snapshot requires released streaming layer");
  require(shared!=nullptr,"snapshot shared slot");shared_slot=shared;std::memcpy(shared_before.data(),shared_slot,shared_before.size());
  parity=e.bank_parity;history0=e.history0;history1=e.history1;
  lookup=e.lookup_ids;selected=e.selected;loaded=e.loaded_layer;fp32_sources=e.fp32_sources;fp32_extents=e.fp32_extents;
  int position=e.integer(0,"position");require(position>=0&&position<e.p.g.context,"snapshot position");
  saved.clear();protected_active.clear();protected_qsa.clear();size_t offset=0;
  for(const auto& source:sources){
   Allocation id=source.standalone;size_t skip=0;
   if(!id){id=source.bank?e.state_spares.at(source.name):e.buffers[0].at(source.name).id;
    if(source.bank)protected_active.push_back({e.buffers[0].at(source.name).id,source.bytes});
    if(source.kv){size_t rows=source.pooled?size_t((e.p.g.context+3)/4):size_t(e.p.g.context);
     size_t valid_rows=source.pooled?size_t(position/4):size_t(position);
     require(source.bytes%rows==0,"snapshot QSA row geometry");skip=valid_rows*(source.bytes/rows);
     if(skip)protected_qsa.push_back({id,skip});
    }
   }
   // Active recurrent banks and already-committed QSA prefixes are not saved:
   // illegal mutation there must remain visible to the full-state gate.
   size_t bytes=source.bytes-skip;if(bytes)saved.push_back({id,skip,bytes,offset});offset+=bytes;
  }
  require(offset<=capacity,"snapshot extent overflow");valid=true;dirty=true;
  copy(false);++captures;saved_bytes+=offset;
 }
 void accept(){require(valid,"snapshot accept without speculation");e.drain();valid=false;}
 void restore(){
  require(valid,"snapshot restore without speculation");e.drain();
  require(!e.poisoned&&!e.integer(0,"error"),"snapshot cannot roll back sticky failure");
  require(e.bank_parity==parity,"snapshot restore bank selection");
  if(!e.resident)for(int layer:e.loaded_layer)require(layer==-1,"snapshot restore streaming layer retained");
  copy(true);e.drain();
  require(shared_slot!=nullptr,"restore shared slot lifetime");std::memcpy(shared_slot,shared_before.data(),shared_before.size());
  e.history0=history0;e.history1=history1;e.lookup_ids=std::move(lookup);e.selected=std::move(selected);
  e.loaded_layer=std::move(loaded);e.fp32_sources=std::move(fp32_sources);e.fp32_extents=std::move(fp32_extents);
  for(size_t card=0;card<e.fp32_sources.size();++card)if(e.fp32_sources[card])require(e.dev(int(card)).arena.row(e.fp32_sources[card]).live,"snapshot resurrected dead FP32 source");
  valid=false;++restores;
 }
 void boundary(){
  require(!valid,"snapshot boundary with unresolved speculation");e.drain();if(dirty)zero_private();
  lookup.clear();selected.clear();loaded.clear();fp32_sources.clear();fp32_extents.clear();saved.clear();
  protected_active.clear();protected_qsa.clear();history0=history1=0;parity=0;
  shared_before.fill(0);shared_slot=nullptr;
  require(lookup.empty()&&selected.empty()&&loaded.empty()&&fp32_sources.empty()&&fp32_extents.empty()&&saved.empty(),"private host snapshot retirement");
  if(backup)save(e.a.output/"speculative-snapshot.json","{\"passed\":true,\"capacity_bytes\":"+std::to_string(capacity)+",\"captures\":"+std::to_string(captures)+",\"restores\":"+std::to_string(restores)+",\"snapshot_payload_bytes\":"+std::to_string(saved_bytes)+",\"private_backup_zeroed\":true,\"committed_state_scrubbed\":false,\"private_host_backup_empty\":true,\"snapshot_valid\":false,\"counters_are_telemetry\":true,\"rank0_shared_slot_bytes\":65536,\"rank1_shared_regions_untouched\":true}");
 }
#ifdef OWN_RT_HOST_ONLY
 // CPU-only negative control: write a byte excluded from the rollback image.
 // A subsequent strict final-state comparison MUST detect the corruption.
 void corrupt_protected_for_gate(int which){
  require(valid&&(which==0||which==1),"negative control outside speculation");e.drain();
  const auto& list=which?protected_qsa:protected_active;require(!list.empty(),"negative control lacks protected extent");
  auto [id,bytes]=list.front();require(bytes,"empty protected extent");auto raw=e.readback(0,id,1);raw[0]^=1;e.upload(0,id,0,raw.data(),1);
 }
#endif
};
}
