// Included inside Engine: diagnostic calls use the same prepared commands.
using P141Snapshot=std::map<Allocation,std::vector<uint8_t>>;
P141Snapshot p141_snapshot(const std::set<Allocation>& ids) {
 P141Snapshot s;size_t total=0;
 for(auto id:ids){const auto&r=dev(0).arena.row(id);total+=r.bytes;
  require(total<=1500ull*1024*1024,"p141 snapshot exceeds 1500 MiB");s[id]=readback(0,id,r.bytes);}
 return s;
}
void p141_restore(const P141Snapshot&s){
 for(const auto&[id,b]:s)for(size_t off=0;off<b.size();off+=4194304)
  upload(0,id,off,b.data()+off,std::min(size_t(4194304),b.size()-off));
 drain();
}
std::map<Allocation,std::string> p141_hashes(const std::set<Allocation>&ids){
 std::map<Allocation,std::string> result;
 for(auto id:ids){const auto&r=dev(0).arena.row(id);result[id]=hash(readback(0,id,r.bytes));}
 return result;
}
void p141_probe(int token,int position) {
#ifndef OWN_RT_HOST_ONLY
 require(a.rank==0&&a.context==4096&&a.draft_rank==1&&prepared_path,"p141 rank/selection");
 require(integer(0,"position")==position&&position==133&&token==10015,"p141 capture position/token mismatch");
 require(!dev(0).before_compute&&!dev(0).after_compute,"p141 pending observer");
 const fs::path packet=P141_PACKET;
 std::ifstream routes_in(packet/"routes.bin",std::ios::binary);
 std::vector<uint8_t> routes((std::istreambuf_iterator<char>(routes_in)),{});
 require(routes.size()==24*120,"p141 routes extent");
 std::array<std::array<iq3::Route,10>,24> route_table{};
 std::memcpy(route_table.data(),routes.data(),routes.size());
 drain();admit_position(position);put(0,"token",&token,4);prepare_token(token);
 std::vector<size_t> body;
 // The prefix is the unchanged token preparation/embedding/stream broadcast.
 // It is outside the target-body numerator and runs exactly once.
 for(size_t i=0;i<p.launches.size();++i){const auto&l=p.launches[i];
  if(l.label.starts_with("blk."))body.push_back(i);
  else if(body.empty())enqueue(l,logical);
 }
 drain();require(!body.empty()&&issue_sites[body.front()].layer==0&&issue_sites[body.back()].layer==23,"p141 full rank0 half");
 std::set<Allocation> state;
 for(const auto&[id,owner]:allocations){const auto&r=dev(owner.first).arena.row(id);
  if(owner.first==0&&r.live&&r.memory==Memory::device&&r.category!=Category::weights)state.insert(id);
 }
 auto initial=p141_snapshot(state);
 const auto eviction=allocate(0,"p141-evict",256ull*1024*1024,Category::scratch,Lifetime::transaction);
 const auto sink=allocate(0,"p141-touch-sink",256*1024,Category::scratch,Lifetime::transaction);
 // Explicit initialization avoids uninitialized device reads.
 std::vector<uint8_t> zeros(4194304,0);
 for(size_t off=0;off<256ull*1024*1024;off+=zeros.size())upload(0,eviction,off,zeros.data(),zeros.size());
 auto touch=[&](Allocation id,size_t off,size_t bytes){
  require(bytes>0&&off+bytes<=dev(0).arena.row(id).bytes,"p141 touch range");
  require((bytes+4095)/4096*4<=dev(0).arena.row(sink).bytes,"p141 touch sink bound");
  P141Touch op;op.offset=off;op.bytes=bytes;std::array<Allocation,2> ids{id,sink};
  return dev(0).compute(op,ids,{});
 };
 auto weight_ranges=[&](size_t i){
  std::vector<std::tuple<Allocation,size_t,size_t>> ranges;
  std::set<Allocation> ids;
  for(const auto&cmd:issue_sites[i].commands)for(auto id:cmd.ids)
   if(dev(0).arena.row(id).category==Category::weights)ids.insert(id);
  int layer=issue_sites[i].layer;
  for(auto id:ids){const auto&r=dev(0).arena.row(id);
   if(r.label.find("_exps.weight")!=std::string::npos){require(r.bytes%512==0,"p141 expert extent");size_t stride=r.bytes/512;
    for(const auto&route:route_table.at(layer)){require(route.expert_id<512,"p141 expert id");ranges.emplace_back(id,size_t(route.expert_id)*stride,stride);}
   }else ranges.emplace_back(id,0,r.bytes);
  }return ranges;
 };
 // Resolve allocation metadata outside every timed half. The a/natural
 // issue loop only walks the original prepared commands and records handles.
 std::map<size_t,std::set<Allocation>> mutations;
 std::map<size_t,std::vector<std::tuple<Allocation,size_t,size_t>>> touch_plan;
 for(auto i:body){auto&site=issue_sites[i];
   auto&mutated=mutations[i];
   auto outputs=[&](const flash::Launch&l){for(const auto&n:l.outputs)mutated.insert(buffers[0].at(n).id);};
   outputs(p.launches[i]);
   if(auto group=small_groups.find(&p.launches[i]);group!=small_groups.end())for(auto*l:group->second.members)outputs(*l);
   // Capture in-place model state even for a fused/derived site.
   for(const auto&cmd:site.commands)for(auto id:cmd.ids){const auto&r=dev(0).arena.row(id);
    if(r.category==Category::kv||r.category==Category::recurrent)mutated.insert(id);
   }
  touch_plan[i]=weight_ranges(i);
 }
 std::ofstream meta(a.output/"p141-touch-plan.jsonl");
 for(auto i:body){size_t total=0;for(auto[id,off,n]:touch_plan[i])total+=n;
  meta<<"{\"site\":"<<i<<",\"kernel_count\":"<<issue_sites[i].commands.size()<<",\"pretouch_events\":"<<touch_plan[i].size()<<",\"pretouch_bytes\":"<<total<<"}\n";
 }meta.close();
 struct E {ownrt::Event event;size_t site;int repetition;bool touch;};
 std::ofstream out(a.output/"p141-events.jsonl");require(bool(out),"p141 timing output");
 std::map<Allocation,std::string> reference;
 std::array<std::string,4> order{"a","b","c","natural"};
 // Four cyclic orders, each arm in each position. b has two warmups and four
 // retained repeats of each original multi-pass site, in layer order.
 for(int block=0;block<4;++block)for(int slot=0;slot<4;++slot){
  guard();const auto arm=order[(block+slot)%4];p141_restore(initial);
  if(arm!="natural"){auto ev=touch(eviction,0,256ull*1024*1024);wait(0,ev);dev(0).retire_completed_events();}
  std::vector<E> events;events.reserve(8192);auto wall=std::chrono::steady_clock::now();
  for(auto i:body){guard();auto&site=issue_sites[i];if(site.commands.empty())continue;
   const auto&mutated=mutations.at(i);
   P141Snapshot before;std::map<Allocation,std::string> once;
   if(arm=="b")before=p141_snapshot(mutated);
   int repeats=arm=="b"?6:1;
   for(int repeat=0;repeat<repeats;++repeat){
    if(repeat)p141_restore(before);
    if(arm=="c")for(auto [id,off,bytes]:touch_plan.at(i))events.push_back({touch(id,off,bytes),i,repeat,true});
    dev(0).before_compute=[&](){guard();};
    dev(0).after_compute=[&](ownrt::Event event){tail=event;events.push_back({event,i,repeat,false});};
    try{enqueue(p.launches[i],logical);}catch(...){dev(0).before_compute={};dev(0).after_compute={};throw;}
    dev(0).before_compute={};dev(0).after_compute={};
    if(arm=="b"){
     if(tail)wait(0,tail);
     // Resolve timing before snapshot readback can retire events.
     for(const auto&ev:events){auto t=dev(0).timing(ev.event);require(t.start_ns&&t.end_ns>t.start_ns&&t.end_ns-t.start_ns<4000000000ull,"p141 invalid event");
      out<<"{\"block\":"<<block<<",\"arm\":\"b\",\"site\":"<<i<<",\"label\":"<<ownrt::quote(p.launches[i].label)<<",\"class\":"<<ownrt::quote(class_names.at(site.cls))<<",\"repeat\":"<<repeat<<",\"warmup\":"<<(repeat<2?"true":"false")<<",\"pretouch\":false,\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<"}\n";
     }events.clear();
     if(repeat==0)once=p141_hashes(mutated);
     if(repeat==5)require(once==p141_hashes(mutated),"p141 warm site output/state differs");
     drain();
    }
   }
  }
  if(tail)wait(0,tail);double wall_ms=ms(wall);
  uint64_t first=0,last=0,kernel_ns=0,touch_ns=0;
  for(const auto&ev:events){auto t=dev(0).timing(ev.event);require(t.start_ns&&t.end_ns>t.start_ns&&t.end_ns-t.start_ns<4000000000ull,"p141 invalid event");
   if(!first)first=t.start_ns;last=t.end_ns;(ev.touch?touch_ns:kernel_ns)+=t.end_ns-t.start_ns;
   out<<"{\"block\":"<<block<<",\"arm\":"<<ownrt::quote(arm)<<",\"site\":"<<ev.site<<",\"label\":"<<ownrt::quote(p.launches[ev.site].label)<<",\"class\":"<<ownrt::quote(class_names.at(issue_sites[ev.site].cls))<<",\"repeat\":0,\"warmup\":false,\"pretouch\":"<<(ev.touch?"true":"false")<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<"}\n";
  }
  out.flush();require(bool(out)&&size_t(out.tellp())<100000000,"p141 timing output budget");
  drain();require(integer(0,"error")==0,"p141 sticky device error");
  // All 24 actual route triples must agree with the independently retained
  // packet138 capture. No route is injected or selected by timing.
  for(auto i:body){const auto&l=p.launches[i];if(l.op=="routed_gemv"&&!l.weights.empty()&&l.weights[0].find("ffn_down_exps")!=std::string::npos){
   auto actual=readback(0,buffers[0].at(l.inputs.at(1)).id,120);size_t layer=std::stoi(l.label.substr(4));
   require(std::equal(actual.begin(),actual.end(),routes.begin()+layer*120),"p141 captured route mismatch layer "+std::to_string(layer));
  }}
  auto actual=p141_hashes(state);if(reference.empty())reference=actual;else require(actual==reference,"p141 complete half state differs");
  std::ofstream hashes(a.output/"p141-state-hashes.jsonl",std::ios::app);
  hashes<<"{\"block\":"<<block<<",\"arm\":"<<ownrt::quote(arm)<<",\"sha256_by_allocation\":{";bool comma=false;
  for(const auto&[id,digest]:actual){hashes<<(comma?",":"")<<ownrt::quote(std::to_string(id))<<":"<<ownrt::quote(digest);comma=true;}hashes<<"}}\n";

  std::ofstream rows(a.output/"p141-halves.jsonl",std::ios::app);
  rows<<"{\"block\":"<<block<<",\"slot\":"<<slot<<",\"arm\":"<<ownrt::quote(arm)<<",\"wall_ms\":"<<wall_ms<<",\"event_span_ns\":"<<(last-first)<<",\"kernel_ns\":"<<kernel_ns<<",\"pretouch_ns\":"<<touch_ns<<",\"routes_equal\":true,\"state_equal\":true}\n";
  if(arm=="natural"){
   // Independent cold control: normal engine enqueue and cancellation/tail
   // callbacks, with no event recording or per-site diagnostic bookkeeping.
   p141_restore(initial);auto ev=touch(eviction,0,256ull*1024*1024);wait(0,ev);dev(0).retire_completed_events();
   dev(0).before_compute=[&](){guard();};
   dev(0).after_compute=[&](ownrt::Event event){tail=event;};
   auto control_start=std::chrono::steady_clock::now();
   try{for(auto i:body){guard();enqueue(p.launches[i],logical);}if(tail)wait(0,tail);}
   catch(...){dev(0).before_compute={};dev(0).after_compute={};throw;}
   double control_ms=ms(control_start);dev(0).before_compute={};dev(0).after_compute={};drain();
   require(integer(0,"error")==0&&p141_hashes(state)==reference,"p141 control state differs");
   std::ofstream controls(a.output/"p141-controls.jsonl",std::ios::app);
   controls<<"{\"block\":"<<block<<",\"wall_ms\":"<<control_ms<<",\"state_equal\":true}\n";
  }
 }
 p141_restore(initial);release(0,sink);release(0,eviction);
 save(a.output/"p141-complete.json","{\"passed\":true,\"diagnostic_only\":true,\"blocks\":4,\"arms\":4,\"arithmetic\":\"iq3-p49-split32-v1\"}\n");
#else
 (void)token;(void)position;throw std::runtime_error("p141 diagnostic requires coordinator device window");
#endif
}
