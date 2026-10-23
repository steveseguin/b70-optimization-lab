#include "../packet205-host-row-capture/host_backend.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/cache_table.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/publish.hpp"
#include <openssl/sha.h>
#include <array>
#include <map>
#include <iostream>
#include <sstream>
using namespace ownrt;
namespace {
constexpr unsigned L=48,E=4,T=2,B=32,N=L*3;
static_assert(sizeof(iq3::Route)==12);
struct Pointer {uint64_t address,generation;};static_assert(sizeof(Pointer)==16);
void need(bool v,const char*msg){if(!v)throw std::runtime_error(msg);}
template<class F>bool refuses(F f){try{f();return false;}catch(const std::exception&){return true;}}
std::string sha(const std::vector<uint8_t>&v){unsigned char h[32];SHA256(v.data(),v.size(),h);std::string s;for(auto b:h){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
// Deliberately a synthetic byte consumer, not production expert arithmetic.
// The same prepared operation reads live table contents from fixed allocations.
struct Consumer final:integrated::HostOperation {
 void run(std::span<void*const> p)const override {
  auto routes=static_cast<const iq3::Route*>(p[3]);auto out=static_cast<uint8_t*>(p[4]);
  for(unsigned k=0;k<T;++k){need(routes[k].expert_id<E,"synthetic route extent");
   for(unsigned projection=0;projection<3;++projection){auto table=static_cast<const Pointer*>(p[projection]);auto entry=table[routes[k].expert_id];need(entry.address&&entry.generation,"published pointer");
    std::memcpy(out+(k*3+projection)*B,reinterpret_cast<const void*>(entry.address),B);
   }
  }
 }
};
struct Fixture {
 Host* host;Device d;std::unique_ptr<p58::Cache> cache;bool closed=false,halted=false,reading=false,updating=false;uint64_t epoch=0;size_t cache_offset=0;uint64_t captured_generation=0;
 std::array<Allocation,N> banks{},tables{},mutable_tables{},decoys{};
 std::array<std::array<Allocation,L>,2> inputs{},outputs{};
 std::array<std::array<std::vector<PreparedCompute>,L>,2> sites;
 Allocation arena,staging,publication,route_work,route_log;std::vector<PreparedCompute> published;std::vector<Event> events;std::vector<Allocation> retained;
 std::array<std::array<std::array<iq3::Route,T>,L>,2> routes{};
 unsigned interval=0,hits=0,misses=0;uint64_t count=0;std::vector<uint32_t> last_replay;std::vector<std::string> order;
 explicit Fixture():host(new Host),d(std::unique_ptr<Backend>(host)) {
  // MockDevice has no promised alignment. Own an extent with 255 padding bytes
  // and use its aligned interior for the real Cache's 256-byte slot ABI.
  arena=alloc("cache",8*256+255);auto raw=uint64_t(d.arena.row(arena).pointer);cache_offset=size_t((raw+255)&~uint64_t(255))-raw;
  staging=alloc("table-staging",N*E*sizeof(Pointer),Memory::pinned);
  publication=alloc("publication-device",N*E*sizeof(Pointer));route_work=alloc("route-workspace",T*sizeof(iq3::Route));route_log=alloc("retained-row-layer-routes",2*L*T*sizeof(iq3::Route),Memory::pinned);
  std::vector<p58::Expert> experts(L*E);
  for(unsigned layer=0;layer<L;++layer)for(unsigned projection=0;projection<3;++projection){unsigned i=layer*3+projection;
   banks[i]=alloc("pinned-bank",E*B,Memory::pinned);tables[i]=alloc("pointer-table",E*sizeof(Pointer));mutable_tables[i]=tables[i];decoys[i]=alloc("decoy-table",E*sizeof(Pointer));std::memset(ptr(decoys[i]),0x5a,E*sizeof(Pointer));
   for(unsigned expert=0;expert<E;++expert){auto* bytes=static_cast<uint8_t*>(ptr(banks[i]))+expert*B;
    for(unsigned j=0;j<B;++j)bytes[j]=uint8_t((layer*37+expert*59+projection*83+j*11)^(j*layer+expert));
    auto& e=experts[layer*E+expert];uint64_t address=uint64_t(bytes);
    if(projection==0){e.host_gate=address;e.gate_bytes=B;}else if(projection==1){e.host_up=address;e.up_bytes=B;}else{e.host_down=address;e.down_bytes=B;}
   }
  }
  for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer){inputs[row][layer]=alloc("immutable-row-route",T*sizeof(iq3::Route));outputs[row][layer]=alloc("row-layer-output",T*3*B);}
  cache=std::make_unique<p58::Cache>(experts,uint64_t(ptr(arena))+cache_offset,8*256);
  publish(cache->table(),false);capture();set_routes(0);
 }
 ~Fixture(){if(!closed){auto r=d.shutdown(std::chrono::milliseconds(100));if(!r.safe_to_exit)std::abort();}}
 Allocation alloc(const char*name,size_t n,Memory m=Memory::device){auto id=d.arena.allocate("card0:p210:"+std::to_string(++count)+":"+name,n,m,m==Memory::pinned?Category::pinned_slab:Category::scratch,Lifetime::transaction);std::memset(d.arena.row(id).pointer,0,n);retained.push_back(id);return id;}
 void* ptr(Allocation id){return d.arena.row(id).pointer;}
 std::vector<uint8_t> bytes(Allocation id){auto&r=d.arena.row(id);auto*p=static_cast<uint8_t*>(r.pointer);return {p,p+r.bytes};}
 void complete(){for(auto e:events)need(d.wait(e,std::chrono::milliseconds(100))&&d.complete(e),"host markers incomplete");need(d.in_flight()==0,"host work pending");d.retire_completed_events();events.clear();}
 void capture(){
  for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer){auto& c=sites[row][layer];d.begin_capture(c);try{
   CopyEngine copy(d);copy.copy(route_work,0,inputs[row][layer],0,T*sizeof(iq3::Route),{});
   Consumer op;std::array<Allocation,6> ids{mutable_tables[layer*3],mutable_tables[layer*3+1],mutable_tables[layer*3+2],route_work,outputs[row][layer],arena};d.compute(op,ids,{});
   copy.copy(route_log,(row*L+layer)*T*sizeof(iq3::Route),route_work,0,T*sizeof(iq3::Route),{});d.end_capture();
  }catch(...){d.end_capture();throw;}need(c.size()==3,"capture route-copy/consumer/route-retention");}
  std::array<uint64_t*,N> destinations{};for(unsigned i=0;i<N;++i)destinations[i]=static_cast<uint64_t*>(ptr(tables[i]));
  p58v::Publish op(destinations,E*2,ptr(staging));std::vector<Allocation> ids{publication};ids.insert(ids.end(),tables.begin(),tables.end());
  d.begin_capture(published);try{d.compute(op,ids,{});d.end_capture();}catch(...){d.end_capture();throw;}
  need(published.size()==1&&published[0].ids.size()==145,"real 144-table publication capture");
  // These caller-side values were the actual inputs to capture, then changed.
  for(unsigned i=0;i<N;++i){mutable_tables[i]=decoys[i];destinations[i]=static_cast<uint64_t*>(ptr(decoys[i]));}op.tables=destinations;std::fill(ids.begin(),ids.end(),publication);
  captured_generation=d.generation();
 }
 void retained_admit(){need(d.generation()==captured_generation,"retained indirect storage generation changed");for(auto id:retained)need(d.arena.row(id).live,"indirect payload/table owner released");}
 void set_routes(unsigned round){need(!reading&&!updating&&!halted,"route update during ownership");interval=round;
  for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer)for(unsigned k=0;k<T;++k){auto&r=routes[row][layer][k];r={};r.expert_id=(layer+round+row+k)%E;r.row_begin=row*T+k;r.row_count=1;}
  // First next-chunk row reuses some prior final-row experts, ensuring cache hits.
  for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer)std::memcpy(ptr(inputs[row][layer]),routes[row][layer].data(),T*sizeof(iq3::Route));
  std::memset(ptr(route_log),0xa5,2*L*T*sizeof(iq3::Route));
 }
 void begin(){need(!halted&&!reading&&!updating,"chunk intake halted");retained_admit();epoch=cache->begin_position();reading=true;order.push_back("begin-frozen-interval");}
 void site(unsigned row,unsigned layer){need(reading&&!halted&&!updating,"late consumer outside frozen interval");try{retained_admit();
  for(auto r:routes[row][layer]){if(cache->resident(layer*E+r.expert_id))++hits;else ++misses;}
  for(auto& c:sites[row][layer])events.push_back(d.issue(c));
 }catch(...){halted=true;throw;}}
 std::vector<uint8_t> outputs_bytes(){std::vector<uint8_t> v;for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer){auto b=bytes(outputs[row][layer]);v.insert(v.end(),b.begin(),b.end());}return v;}
 std::vector<uint8_t> expected(){std::vector<uint8_t> v;for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer)for(auto route:routes[row][layer])for(unsigned projection=0;projection<3;++projection){for(unsigned j=0;j<B;++j)v.push_back(uint8_t((layer*37+route.expert_id*59+projection*83+j*11)^(j*layer+route.expert_id)));}return v;}
 std::vector<uint8_t> all_tables(){std::vector<uint8_t> v;for(auto id:tables){auto b=bytes(id);v.insert(v.end(),b.begin(),b.end());}return v;}
 std::vector<uint32_t> replay(bool wrong_order=false){std::vector<uint32_t> out;auto* log=static_cast<const iq3::Route*>(ptr(route_log));
  auto add=[&](unsigned row,unsigned layer){for(unsigned k=0;k<T;++k){const auto& r=log[(row*L+layer)*T+k];need(r.expert_id<E,"retained route outside bank");need(!std::memcmp(&r,&routes[row][layer][k],sizeof(r)),"retained row route mismatch");out.push_back(layer*E+r.expert_id);}};
  if(wrong_order)for(unsigned layer=0;layer<L;++layer)for(unsigned row=0;row<2;++row)add(row,layer);
  else for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer)add(row,layer);return out;
 }
 void end_read(){need(reading&&!halted,"end reading admission");try{complete();cache->finish_position(epoch,true);reading=false;order.push_back("all-consumers-complete");}catch(...){halted=true;throw;}}
 void stage(const std::vector<p58::Entry>& table){auto* out=static_cast<Pointer*>(ptr(staging));for(unsigned layer=0;layer<L;++layer)for(unsigned projection=0;projection<3;++projection)for(unsigned id=0;id<E;++id){auto&e=table[layer*E+id];out[(layer*3+projection)*E+id]={projection==0?e.gate:projection==1?e.up:e.down,e.generation};}}
 void publish(const std::vector<p58::Entry>& table,bool scatter,bool inject_partial=false){need(!reading&&!halted,"publication while readers/failed");need(d.in_flight()==0,"publication staging still owned by pending work");stage(table);CopyEngine copy(d);
  if(scatter){need(!inject_partial,"scatter has no injected DMA failure");retained_admit();events.push_back(d.issue(published.at(0)));}
  else for(unsigned i=0;i<N;++i){size_t n=E*sizeof(Pointer);bool changed=std::memcmp(ptr(tables[i]),static_cast<uint8_t*>(ptr(staging))+i*n,n)!=0;events.push_back(copy.copy(tables[i],0,staging,i*n,n,{}));if(inject_partial&&changed){complete();copy.copy(tables[i],0,staging,i*n,n+1,{});}}
  complete();
 }
 void update(bool scatter,bool wrong_order=false,bool fail_fill=false,bool fail_publish=false){need(!halted&&!reading&&!updating,"update while readers/failed");try{
  last_replay=replay(wrong_order);auto plan=cache->prepare(last_replay);updating=true;CopyEngine copy(d);unsigned copies=0;
  for(auto& f:plan.fills){size_t offset=cache_offset+f.offset;unsigned layer=f.expert/E,id=f.expert%E;
   for(unsigned projection=0;projection<3;++projection){size_t n=B;if(fail_fill&&copies==1)n=E*B+1;events.push_back(copy.copy(arena,offset,banks[layer*3+projection],id*B,n,{}));offset+=B;++copies;}
  }
  complete();order.push_back("fills-complete");publish(plan.table,scatter,fail_publish);order.push_back("tables-published");cache->commit(plan.epoch,true,true);updating=false;order.push_back("cache-commit");
 }catch(...){halted=true;throw;}}
 std::vector<uint32_t> resident_ids(){std::vector<uint32_t> ids;for(unsigned i=0;i<L*E;++i)if(cache->resident(i))ids.push_back(i);return ids;}
 std::vector<uint8_t> normalized(){std::vector<uint8_t> out;auto emit=[&](uint64_t n){for(unsigned i=0;i<8;++i)out.push_back(uint8_t(n>>(i*8)));};auto base=uint64_t(ptr(arena))+cache_offset;
  for(unsigned id=0;id<L*E;++id){auto&e=cache->table()[id];emit(id);emit(cache->resident(id));emit(e.generation);
   for(auto address:{e.gate,e.up,e.down}){emit(address>=base&&address<base+8*256?address-base:UINT64_MAX);auto* p=reinterpret_cast<const uint8_t*>(address);out.insert(out.end(),p,p+B);}}
  return out;
 }
 bool decoys_untouched(){for(auto id:decoys)for(auto b:bytes(id))if(b!=0x5a)return false;return true;}
 Receipt close(){complete();if(reading){cache->finish_position(epoch,true);reading=false;}if(updating){cache->close_failed(true);updating=false;}else cache->close();auto r=d.shutdown(std::chrono::milliseconds(100));need(r.safe_to_exit,"retained CPU owner");closed=true;return r;}
};
}
int main(){try{
 std::map<std::string,bool> checks;std::map<std::string,std::string> hashes,receipts,errors;std::vector<std::string> intervals;
 auto run_rows=[](Fixture&f,bool layer_major){if(layer_major){for(unsigned layer=0;layer<L;++layer)for(unsigned row=0;row<2;++row)f.site(row,layer);}else{for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<L;++layer)f.site(row,layer);}};
 auto list=[](const std::vector<uint32_t>&v){std::ostringstream out;out<<'[';for(size_t i=0;i<v.size();++i)out<<(i?",":"")<<v[i];out<<']';return out.str();};
 {
  Fixture serial,chunk;
  checks["publication_capture_has_145_owned_device_ids"]=chunk.published[0].ids.size()==145&&chunk.published[0].ids[0]==chunk.publication;
  checks["captured_table_ids_ignore_caller_rebinding"]=chunk.sites[0][0][1].ids[0]==chunk.tables[0]&&chunk.mutable_tables[0]==chunk.decoys[0];
  bool outputs_exact=true,normalized_exact=true,freeze=true,decoys=true,late=true,publication_livestaging=true;unsigned total_hits=0,total_misses=0;
  checks["publish_during_read_refused"]=true;checks["cache_prepare_during_read_refused"]=true;
  for(unsigned round=0;round<3;++round){serial.set_routes(round);chunk.set_routes(round);auto before_tables=chunk.all_tables(),before_slots=chunk.bytes(chunk.arena);auto old_normal=chunk.normalized();
   serial.begin();chunk.begin();
   checks["publish_during_read_refused"]&=refuses([&]{chunk.publish(chunk.cache->table(),true);})&&chunk.all_tables()==before_tables;
   checks["cache_prepare_during_read_refused"]&=refuses([&]{chunk.cache->prepare({0});});
   auto hits=chunk.hits,misses=chunk.misses;run_rows(serial,false);run_rows(chunk,true);
   freeze&=chunk.all_tables()==before_tables&&chunk.bytes(chunk.arena)==before_slots;
   outputs_exact&=serial.outputs_bytes()==serial.expected()&&chunk.outputs_bytes()==chunk.expected()&&serial.outputs_bytes()==chunk.outputs_bytes();
   serial.end_read();chunk.end_read();late&=refuses([&]{chunk.site(0,0);});
   auto routes=chunk.replay();auto expected_routes=serial.replay();need(routes==expected_routes,"retained chronological routes changed across schedules");
   serial.update(false);chunk.update(true);
   normalized_exact&=serial.normalized()==chunk.normalized();decoys&=chunk.decoys_untouched();publication_livestaging&=chunk.all_tables()==chunk.bytes(chunk.staging)&&chunk.normalized()!=old_normal;
   total_hits+=chunk.hits-hits;total_misses+=chunk.misses-misses;
   std::ostringstream row;row<<"{\"round\":"<<round<<",\"output_bytes\":"<<chunk.outputs_bytes().size()<<",\"output_sha256\":\""<<sha(chunk.outputs_bytes())<<"\",\"expected_sha256\":\""<<sha(chunk.expected())<<"\",\"normalized_table_sha256\":\""<<sha(chunk.normalized())<<"\",\"route_log_sha256\":\""<<sha(chunk.bytes(chunk.route_log))<<"\",\"hits\":"<<chunk.hits-hits<<",\"misses\":"<<chunk.misses-misses<<",\"routes\":"<<list(routes)<<",\"resident_ids\":"<<list(chunk.resident_ids())<<"}";intervals.push_back(row.str());
  }
  checks["frozen_table_and_victim_bytes_both_rows"]=freeze;checks["independent_payload_formula_and_schedules_exact"]=outputs_exact;checks["normalized_identity_payload_generation_exact"]=normalized_exact;
  checks["both_cache_hits_and_pinned_misses_consumed"]=total_hits>0&&total_misses>0;
  checks["late_old_table_consumer_refused"]=late;checks["caller_destination_decoys_untouched"]=decoys;checks["live_staging_updates_fixed_table_handles"]=publication_livestaging;
  receipts["serial"]=serial.close().json();receipts["chunk"]=chunk.close().json();
 }
 {
  Fixture good,wrong;good.begin();wrong.begin();run_rows(good,true);run_rows(wrong,true);good.end_read();wrong.end_read();good.update(true);wrong.update(true,true);
  checks["wrong_layer_major_replay_changes_residency"]=good.resident_ids()!=wrong.resident_ids();
  hashes["correct_replay_normalized"]=sha(good.normalized());hashes["wrong_replay_normalized"]=sha(wrong.normalized());
  checks["wrong_replay_changes_normalized_table"]=hashes["correct_replay_normalized"]!=hashes["wrong_replay_normalized"];
  receipts["correct_replay"]=good.close().json();receipts["wrong_replay"]=wrong.close().json();
 }
 {
  Fixture f;f.begin();run_rows(f,true);f.end_read();f.update(true);f.set_routes(1);f.begin();
  auto* table=static_cast<Pointer*>(f.ptr(f.tables[0]));auto selected=f.routes[0][0][0].expert_id;table[selected]=table[(selected+2)%E];
  f.site(0,0);f.complete();auto expected=f.expected();std::vector<uint8_t> target(expected.begin(),expected.begin()+T*3*B);
  hashes["changed_table_output"]=sha(f.bytes(f.outputs[0][0]));hashes["expected_table_output"]=sha(target);
  checks["captured_consumer_reads_live_table_bytes"]=f.bytes(f.outputs[0][0])!=target;
  receipts["live_table_mutation"]=f.close().json();
 }
 {
  Fixture f;auto before=f.outputs_bytes();f.d.arena.release(f.banks[0]);
  checks["released_indirect_pinned_payload_refuses_capture"]=refuses([&]{f.begin();})&&f.outputs_bytes()==before;
  receipts["stale_indirect"]=f.close().json();
 }
 {
  Fixture f;f.host->auto_marker=false;f.events.push_back(f.d.issue(f.published[0]));
  checks["pending_publication_retains_hidden_pinned_staging"]=f.d.in_flight()>0&&refuses([&]{f.d.arena.release(f.staging);});
  auto old_staging=f.bytes(f.staging);auto changed=f.cache->table();++changed[0].generation;
  checks["pending_publication_refuses_staging_overwrite"]=refuses([&]{f.publish(changed,true);})&&f.bytes(f.staging)==old_staging;
  f.host->finish_all();f.host->auto_marker=true;f.complete();receipts["pending_staging"]=f.close().json();
 }
 {
  Fixture f;f.begin();f.host->auto_marker=false;f.events.push_back(f.d.issue(f.sites[0][0][1]));auto old=f.all_tables();
  checks["incomplete_consumer_prevents_finish_and_publication"]=refuses([&]{f.end_read();})&&f.halted&&refuses([&]{f.publish(f.cache->table(),true);})&&f.all_tables()==old;
  checks["incomplete_consumer_retains_payloads"]=refuses([&]{f.d.arena.release(f.banks[0]);});
  f.host->finish_all();f.host->auto_marker=true;receipts["incomplete_consumer"]=f.close().json();
 }
 {
  Fixture f;f.begin();run_rows(f,true);f.end_read();f.update(true);f.set_routes(1);f.begin();run_rows(f,true);f.end_read();auto old_slots=f.bytes(f.arena),old_table=f.all_tables();
  try{f.update(true,false,true);}catch(const std::exception&e){errors["partial_fill"]=e.what();}
  checks["partial_fill_fault_injected"]=errors["partial_fill"]=="copy extent/lifetime";f.complete();
  checks["partial_fill_overwrites_populated_victim"]=f.bytes(f.arena)!=old_slots&&f.all_tables()==old_table;
  checks["partial_fill_poison_no_rollback_or_next_chunk"]=f.halted&&f.updating&&refuses([&]{f.begin();})&&refuses([&]{f.site(0,0);})&&refuses([&]{f.publish(f.cache->table(),true);});
  hashes["before_partial_fill_slots"]=sha(old_slots);hashes["before_partial_fill_tables"]=sha(old_table);hashes["after_partial_fill_tables"]=sha(f.all_tables());
  hashes["partial_fill_slots"]=sha(f.bytes(f.arena));receipts["partial_fill"]=f.close().json();
 }
 {
  Fixture f;f.begin();run_rows(f,true);f.end_read();f.update(true);f.set_routes(1);f.begin();run_rows(f,true);f.end_read();auto before=f.all_tables();
  try{f.update(false,false,false,true);}catch(const std::exception&e){errors["partial_publication"]=e.what();}
  checks["partial_publication_fault_injected"]=errors["partial_publication"]=="copy extent/lifetime";f.complete();
  checks["partial_publication_changes_some_not_all_tables"]=f.all_tables()!=before&&f.all_tables()!=f.bytes(f.staging);
  checks["partial_publication_poison_no_rollback_or_next_chunk"]=f.halted&&f.updating&&refuses([&]{f.begin();})&&refuses([&]{f.site(0,0);})&&refuses([&]{f.publish(f.cache->table(),true);});
  hashes["before_partial_publication_tables"]=sha(before);hashes["intended_publication_tables"]=sha(f.bytes(f.staging));hashes["partial_publication_tables"]=sha(f.all_tables());receipts["partial_publication"]=f.close().json();
 }
 bool passed=true;for(auto&[name,value]:checks)passed&=value;
 std::cout<<"{\"schema\":\"packet210.host-cache-proof.v1\",\"passed\":"<<(passed?"true":"false")<<",\"device_executed\":false,\"model_executed\":false,\"completion_scope\":\"real CPU bytes; existing Host/LifetimeMock simulated markers\",\"arithmetic_scope\":\"synthetic pointer-table byte consumer, not production expert arithmetic\",\"policy\":\"single frozen two-row interval then chronological single-touch prepare/fill/publish/commit\",\"geometry\":{\"layers\":48,\"experts\":4,\"projections\":3,\"payload_bytes\":32,\"top\":2,\"cache_bytes\":2048,\"route_bytes\":12,\"route_row_begin\":\"row*2+slot\",\"route_row_count\":1},\"checks\":{";bool first=true;
 for(auto&[name,value]:checks){std::cout<<(first?"":",")<<'"'<<name<<"\":"<<(value?"true":"false");first=false;}std::cout<<"},\"intervals\":[";
 for(size_t i=0;i<intervals.size();++i)std::cout<<(i?",":"")<<intervals[i];std::cout<<"],\"byte_sha256\":{";first=true;
 for(auto&[name,value]:hashes){std::cout<<(first?"":",")<<'"'<<name<<"\":\""<<value<<'"';first=false;}std::cout<<"},\"first_errors\":{";first=true;for(auto&[name,value]:errors){std::cout<<(first?"":",")<<ownrt::quote(name)<<":"<<ownrt::quote(value);first=false;}std::cout<<"},\"owner_receipts\":{";first=true;
 for(auto&[name,value]:receipts){std::cout<<(first?"":",")<<'"'<<name<<"\":"<<value;first=false;}std::cout<<"}}\n";return passed?0:1;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
