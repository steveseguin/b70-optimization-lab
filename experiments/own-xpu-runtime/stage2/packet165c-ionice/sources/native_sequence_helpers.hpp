// CPU sequence sensors. Synthetic rows are never performance measurements.
struct AllocationIdentity {
 Allocation id; int card; void* pointer; size_t bytes; ownrt::Category category;
};
static std::vector<AllocationIdentity> identities(Engine& e) {
 std::vector<AllocationIdentity> result;
 for(auto [id,owner]:e.allocations){const auto& r=e.dev(owner.first).arena.row(id);
  result.push_back({id,owner.first,r.pointer,r.bytes,r.category});}
 return result;
}
static void identity_check(Engine& e,const std::vector<AllocationIdentity>& before) {
 require(e.allocations.size()==before.size(),"allocation census changed across reset");
 for(auto s:before){const auto& r=e.dev(s.card).arena.row(s.id);
  require(r.live&&r.pointer==s.pointer&&r.bytes==s.bytes&&r.category==s.category,"allocation identity changed");}
}
static std::set<Allocation> canonical(Engine& e) {
 std::set<Allocation> ids;
 for(int c=0;c<e.a.cards;++c){ids.insert(e.one[c]);
  for(auto key:{"active","token_history","ple_metadata","error"})if(e.buffers[c].count(key))ids.insert(e.buffers[c].at(key).id);}
 return ids;
}
static size_t poison_samples(Engine& e) {
 auto skip=canonical(e);size_t samples=0;
 for(auto [id,owner]:e.allocations){auto& r=e.dev(owner.first).arena.row(id);
  if(!r.live||r.category==Category::weights||r.category==Category::pinned_slab||skip.count(id))continue;
  std::memset(r.pointer,0xa5,std::min(r.bytes,size_t(64)));++samples;}
 e.history0=42;e.history1=43;e.lookup_ids["cpu-sequence-poison"]={1,2,3};
 for(auto& v:e.selected)v={1};
 return samples;
}
static size_t reset_samples(Engine& e) {
 auto skip=canonical(e);size_t samples=0;
 for(auto [id,owner]:e.allocations){auto& r=e.dev(owner.first).arena.row(id);
  if(!r.live||r.category==Category::weights||r.category==Category::pinned_slab||skip.count(id))continue;
  auto b=static_cast<const uint8_t*>(r.pointer);
  for(size_t i=0;i<std::min(r.bytes,size_t(64));++i)require(b[i]==0,"mutable sample survived reset: "+r.label);
  ++samples;}
 require(e.history0==e.p.g.eos&&e.history1==e.p.g.eos&&e.lookup_ids.empty(),"history/lookup reset");
 for(auto& v:e.selected)require(v.empty(),"selected reset");
 for(int c=0;c<e.a.cards;++c)require(e.integer(c,"active")==1&&e.integer(c,"error")==0,"canonical controls");
 return samples;
}
static void sensor(std::ofstream& stream,const std::string& id,const char* name) {
 require(stream.is_open()&&bool(stream),std::string("sensor closed after reset: ")+name);
 stream<<"{\"cpu_sequence_sensor\":true,\"request_id\":"<<ownrt::quote(id)<<",\"sensor\":"<<ownrt::quote(name)<<"}\n";
 stream.flush();require(bool(stream),"sensor failed after reset");
}
static void sensors(Engine& e,const std::string& id) {
 sensor(e.timings,id,"timings");sensor(e.prefill_timings,id,"prefill-timings");
 sensor(e.site_timings,id,"sites");sensor(e.progress,id,"progress");
}
static std::vector<std::string> sequence_ids() {
 const char* path=std::getenv("SEQUENCE_INPUTS");require(path,"sequence inputs missing");
 std::ifstream input(path);std::vector<std::string> ids;std::string id;
 while(input>>id)ids.push_back(id);
 require(ids.size()==13&&((ids[0]=="incident-retrospective"&&ids[1]=="prefill512")||(ids[0]=="prefill512"&&ids[1]=="incident-retrospective")),"real request order");
 require(std::set<std::string>(ids.begin(),ids.end()).size()==13,"duplicate request");
 ids.push_back("after-suite");return ids;
}
static void remove_synthetic_dumps(const fs::path& directory) {
 // These files contain only CPU fixture zeros/sentinels, never model evidence.
 std::vector<fs::path> files;
 for(auto& entry:fs::recursive_directory_iterator(directory))if(entry.is_regular_file()&&
  (entry.path().extension()==".bin"||entry.path().extension()==".bf16"))files.push_back(entry.path());
 for(auto& f:files)fs::remove(f);
}
