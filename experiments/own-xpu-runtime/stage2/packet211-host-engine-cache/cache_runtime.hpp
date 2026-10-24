#pragma once
#ifndef OWN_RT_HOST_ONLY
#error P211 cache runtime is synthetic HOST_ONLY only
#endif
#include "host_indirect.hpp"
namespace p211 {
struct BankSpec {std::string name;unsigned layer=0,projection=0;ownrt::Allocation original=0;size_t expert_bytes=0;};
class MiniCache {
public:
 struct Bank:BankSpec {ownrt::Allocation pinned=0,table=0;};
 using Allocate=std::function<ownrt::Allocation(const std::string&,size_t,ownrt::Category,ownrt::Lifetime,ownrt::Memory)>;
private:
 ownrt::Device& d;unsigned experts,top;static constexpr unsigned layers=4;static constexpr size_t capacity=4096;
 Allocate allocate;std::map<std::string,Bank> banks;std::vector<ownrt::Allocation> retained;std::unique_ptr<p58::Cache> cache;
 ownrt::Allocation arena=0,staging=0,route_log=0;size_t offset=0;uint64_t generation=0,epoch=0;
 bool active=false,updating=false,poisoned=false,closed=false;unsigned current_row=0,count=0;size_t start=0;
 std::array<std::array<bool,layers>,2> seen{};std::filesystem::path output;std::vector<ownrt::Event> copies,route_events;
 std::string frozen_table,frozen_payload;uint64_t fills_total=0,fill_bytes_total=0,publications_total=0;
 ownrt::Allocation alloc(const std::string&name,size_t n,ownrt::Category c,ownrt::Lifetime l,ownrt::Memory m=ownrt::Memory::device){auto id=allocate("p211:"+name,n,c,l,m);retained.push_back(id);return id;}
 void* ptr(ownrt::Allocation id)const{return d.arena.row(id).pointer;}
 void wait_copies(){for(auto event:copies)require(d.wait(event,std::chrono::seconds(1))&&d.complete(event),"p211 host copy incomplete");require(d.in_flight()==0,"p211 outstanding host work");copies.clear();}
 std::vector<uint8_t> bytes(ownrt::Allocation id)const{const auto&r=d.arena.row(id);const auto*p=static_cast<const uint8_t*>(r.pointer);return {p,p+r.bytes};}
 std::string table_hash()const{std::vector<uint8_t> b;for(const auto&[name,bank]:banks){auto x=bytes(bank.table);b.insert(b.end(),x.begin(),x.end());}return ::hash(b);}
 std::string payload_hash()const{auto* p=static_cast<const uint8_t*>(ptr(arena))+offset;return ::hash({p,p+capacity});}
 void publication(const std::vector<p58::Entry>&entries){
  require(!active&&!poisoned&&d.in_flight()==0,"p211 publication owner guard");
  auto* values=static_cast<p58::Pointer*>(ptr(staging));ownrt::CopyEngine copy(d);size_t index=0;
  for(const auto&[name,bank]:banks){for(unsigned id=0;id<experts;++id){const auto&e=entries.at(bank.layer*experts+id);values[index+id]={bank.projection==0?e.gate:bank.projection==1?e.up:e.down,e.generation};}
   copies.push_back(copy.copy(bank.table,0,staging,index*sizeof(p58::Pointer),experts*sizeof(p58::Pointer),{}));index+=experts;}
  wait_copies();++publications_total;
 }
public:
 MiniCache(ownrt::Device&device,Allocate allocator,const std::vector<BankSpec>&specs,unsigned e,unsigned t):d(device),experts(e),top(t),allocate(std::move(allocator)){
  require(experts==16&&top==10&&specs.size()==12,"p211 exact tiny cache geometry");
  arena=alloc("cache-arena",capacity+255,ownrt::Category::weights,ownrt::Lifetime::process);
  auto base=uint64_t(ptr(arena));offset=size_t(((base+255)&~uint64_t(255))-base);
  std::memset(ptr(arena),0,capacity+255);
  staging=alloc("table-staging",12*experts*sizeof(p58::Pointer),ownrt::Category::pinned_slab,ownrt::Lifetime::transfer,ownrt::Memory::pinned);
  route_log=alloc("row-layer-routes",2*layers*top*sizeof(iq3::Route),ownrt::Category::pinned_slab,ownrt::Lifetime::transfer,ownrt::Memory::pinned);
  std::vector<p58::Expert> descriptors(layers*experts);std::set<std::pair<unsigned,unsigned>> fields;ownrt::CopyEngine copy(d);
  for(const auto&s:specs){require(s.layer<layers&&s.projection<3&&s.expert_bytes&&fields.insert({s.layer,s.projection}).second,"p211 unique tiny bank");Bank b;static_cast<BankSpec&>(b)=s;
   require(d.arena.row(s.original).live&&d.arena.row(s.original).bytes==experts*s.expert_bytes,"p211 original bank extent");retained.push_back(s.original);
   b.pinned=alloc("pinned:"+s.name,experts*s.expert_bytes,ownrt::Category::weights,ownrt::Lifetime::process,ownrt::Memory::pinned);
   b.table=alloc("table:"+s.name,experts*sizeof(p58::Pointer),ownrt::Category::weights,ownrt::Lifetime::process);
   copies.push_back(copy.copy(b.pinned,0,s.original,0,experts*s.expert_bytes,{}));wait_copies();
   for(unsigned id=0;id<experts;++id){auto&x=descriptors[s.layer*experts+id];auto address=uint64_t(ptr(b.pinned))+id*s.expert_bytes;
    if(s.projection==0){x.host_gate=address;x.gate_bytes=s.expert_bytes;}else if(s.projection==1){x.host_up=address;x.up_bytes=s.expert_bytes;}else{x.host_down=address;x.down_bytes=s.expert_bytes;}}
   require(banks.emplace(s.name,b).second,"p211 repeated bank name");
  }
  cache=std::make_unique<p58::Cache>(descriptors,uint64_t(ptr(arena))+offset,capacity);publication(cache->table());generation=d.generation();
 }
 bool running()const{return active;}
 bool failed()const{return poisoned;}
 ownrt::Allocation table(const std::string&name)const{return banks.at(name).table;}
 Span pinned(const std::string&name)const{const auto&b=banks.at(name);return {uint64_t(ptr(b.pinned)),d.arena.row(b.pinned).bytes};}
 Span cache_span()const{return {uint64_t(ptr(arena))+offset,capacity};}
 void admit()const{
  require(!poisoned&&!closed&&d.generation()==generation,"p211 retained cache owner generation");
  for(auto id:retained)require(d.arena.row(id).live,"p211 released indirect owner");
  // This HOST-only fixture checks live published generations/addresses against
  // committed Cache metadata. resolve() itself supplies none of these checks.
  for(const auto&[name,b]:banks){auto* actual=static_cast<const p58::Pointer*>(ptr(b.table));for(unsigned id=0;id<experts;++id){const auto&e=cache->table().at(b.layer*experts+id);auto address=b.projection==0?e.gate:b.projection==1?e.up:e.down;require(actual[id].address==address&&actual[id].generation==e.generation,"p211 unpublished/stale pointer table");}}
 }
 std::string normalized()const{
  admit();std::vector<uint8_t> out;auto put=[&](uint64_t n){for(int i=0;i<8;++i)out.push_back(uint8_t(n>>(8*i)));};auto base=cache_span().begin;
  for(const auto&[name,b]:banks){auto* values=static_cast<const p58::Pointer*>(ptr(b.table));for(unsigned id=0;id<experts;++id){auto x=values[id];bool resident=cache->resident(b.layer*experts+id);put(b.layer);put(b.projection);put(id);put(resident);put(x.generation);put(resident?x.address-base:0);auto* p=reinterpret_cast<const uint8_t*>(x.address);out.insert(out.end(),p,p+b.expert_bytes);}}
  return ::hash(out);
 }
 void row(unsigned value){require(active&&value<count,"p211 cache row admission");current_row=value;}
 void begin(size_t position,unsigned rows,const std::filesystem::path&destination){
  admit();require(!active&&!updating&&d.in_flight()==0&&(rows==1||rows==2),"p211 frozen interval admission");start=position;count=rows;current_row=0;output=destination;seen={};
  std::memset(ptr(route_log),0xa5,2*layers*top*sizeof(iq3::Route));frozen_table=table_hash();frozen_payload=payload_hash();epoch=cache->begin_position();active=true;
 }
 ownrt::Event retain(unsigned layer,ownrt::Allocation source){
  admit();require(active&&layer<layers&&!seen[current_row][layer],"p211 exact once row/layer route");
  require(d.arena.row(source).live&&d.arena.row(source).bytes>=top*sizeof(iq3::Route),"p211 actual route extent");ownrt::CopyEngine copy(d);
  auto event=copy.copy(route_log,(current_row*layers+layer)*top*sizeof(iq3::Route),source,0,top*sizeof(iq3::Route),{});route_events.push_back(event);seen[current_row][layer]=true;return event;
 }
 // Engine owns these copy events as tail dependencies. Consume while IDs are
 // still registered, after its tail wait and before any event retirement.
 void consume_route_events(){for(auto event:route_events)require(d.wait(event,std::chrono::seconds(1))&&d.complete(event),"p211 retained route copy incomplete");route_events.clear();}
 void end(){
  try{
   admit();require(active&&route_events.empty(),"p211 finish before route completion transfer");wait_copies();
   for(unsigned r=0;r<count;++r)for(unsigned layer=0;layer<layers;++layer)require(seen[r][layer],"p211 lost row route");
   require(table_hash()==frozen_table&&payload_hash()==frozen_payload,"p211 cache mutated during readers");
   const auto* log=static_cast<const iq3::Route*>(ptr(route_log));std::vector<uint32_t> chronological;unsigned hits=0,misses=0;
   for(unsigned r=0;r<count;++r)for(unsigned layer=0;layer<layers;++layer)for(unsigned k=0;k<top;++k){auto route=log[(r*layers+layer)*top+k];require(route.expert_id<experts,"p211 retained route outside bank");auto id=layer*experts+route.expert_id;chronological.push_back(id);(cache->resident(id)?hits:misses)++;}
   cache->finish_position(epoch,true);active=false;auto plan=cache->prepare(chronological);updating=true;ownrt::CopyEngine copy(d);
   for(const auto&f:plan.fills){size_t off=offset+f.offset;for(unsigned projection=0;projection<3;++projection){const Bank*bank=nullptr;for(const auto&[name,b]:banks)if(b.layer==f.expert/experts&&b.projection==projection){bank=&b;break;}require(bank,"p211 fill bank");copies.push_back(copy.copy(arena,off,bank->pinned,(f.expert%experts)*bank->expert_bytes,bank->expert_bytes,{}));off+=bank->expert_bytes;}}
   wait_copies();publication(plan.table);cache->commit(plan.epoch,true,true);updating=false;fills_total+=plan.fills.size();fill_bytes_total+=plan.fill_bytes;
   std::vector<uint8_t> raw(reinterpret_cast<const uint8_t*>(log),reinterpret_cast<const uint8_t*>(log)+count*layers*top*sizeof(iq3::Route));
   std::ofstream trace(output/"cache-intervals.jsonl",std::ios::app);require(bool(trace),"p211 cache trace open");
   trace<<"{\"start\":"<<start<<",\"count\":"<<count<<",\"epoch\":"<<epoch<<",\"frozen_table_payload\":true,\"route_sha256\":"<<ownrt::quote(::hash(raw))<<",\"routes\":[";
   for(size_t i=0;i<chronological.size();++i)trace<<(i?",":"")<<chronological[i];trace<<"],\"route_triples\":[";for(unsigned i=0;i<count*layers*top;++i)trace<<(i?",":"")<<"["<<log[i].expert_id<<","<<log[i].row_begin<<","<<log[i].row_count<<"]";trace<<"],\"hits\":"<<hits<<",\"misses\":"<<misses<<",\"fills\":"<<plan.fills.size()<<",\"evictions\":"<<plan.evictions<<",\"fill_bytes\":"<<plan.fill_bytes<<",\"fills_total\":"<<fills_total<<",\"fill_bytes_total\":"<<fill_bytes_total<<",\"publications_total\":"<<publications_total<<",\"normalized_table_sha256\":"<<ownrt::quote(normalized())<<",\"resident_ids\":[";
   bool first=true;for(unsigned id=0;id<layers*experts;++id)if(cache->resident(id)){trace<<(first?"":",")<<id;first=false;}trace<<"]}\n";trace.flush();require(bool(trace),"p211 cache trace write");
  }catch(...){poisoned=true;throw;}
 }
 void poison(){poisoned=true;}
 void failure_receipt(const std::filesystem::path&destination)const{std::ofstream out(destination/"cache-failure.json");out<<"{\"cache_active\":"<<(active?"true":"false")<<",\"poisoned\":"<<(poisoned?"true":"false")<<",\"updating\":"<<(updating?"true":"false")<<",\"start\":"<<start<<",\"count\":"<<count<<",\"rollback_claimed\":false}\n";out.flush();require(bool(out),"p211 cache failure receipt");}
 void request_reset(const std::filesystem::path&destination,const std::string&before){admit();require(!active&&!updating&&normalized()==before,"p211 warm cache changed by request reset");std::ofstream out(destination/"cache-reset.json");out<<"{\"passed\":true,\"preserved\":true,\"normalized_table_sha256\":"<<ownrt::quote(before)<<",\"capacity\":"<<capacity<<",\"resident_bytes\":"<<cache->resident_bytes()<<"}\n";out.flush();require(bool(out),"p211 reset receipt");}
 void close(){if(closed)return;require(route_events.empty(),"p211 close before route completion transfer");wait_copies();if(active){cache->finish_position(epoch,true);active=false;}if(updating)cache->close_failed(true);else cache->close();closed=true;}
};
}
