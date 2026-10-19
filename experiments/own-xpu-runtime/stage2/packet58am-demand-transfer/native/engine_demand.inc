  p58am::Pool demand_pool;
  Allocation demand_storage=0;
  uint64_t previous_snapshot=0;
  std::array<uint64_t,5> demand_bypass{}; // invalid, no neighbor, maintenance, pool, pointer uncertainty
  struct DemandLayer {
    Allocation descriptor=0,stage=0,host=0,host_stage=0;
    std::array<Allocation,3> hosts{},tables{};
    std::array<size_t,3> bank_bytes{};
    bool layout_supported=false;
    std::vector<ownrt::PreparedCompute> describe,gate_resident,gate_missing,down_resident,down_missing;
    uint64_t gate_ticket=0,down_ticket=0;
    bool trace=false;unsigned resident_slots=0,staged_entries=0;
    uint64_t router=0,producer=0,readback=0,gr=0,gm=0,dr=0,dm=0;
    std::array<uint64_t,30> copies{};unsigned copies_size=0;
  };
  std::array<DemandLayer,48> demand_layers{};
  p58am::Backend& demand_backend(){auto*b=dynamic_cast<p58am::Backend*>(p58v::backend(dev(0)));require(b,"owned demand backend unavailable");return *b;}
  void* demand_pointer(Allocation id,size_t off=0,size_t n=1){const auto&r=dev(0).arena.row(id);require(r.live&&off<=r.bytes&&n<=r.bytes-off,"demand live extent");return static_cast<char*>(r.pointer)+off;}
  void demand_initialize(){
    demand_storage=allocate(0,"demand-packed-32x2",p58am::pool_bytes,Category::weights,Lifetime::process);
    for(unsigned layer=0;layer<48;++layer){auto& x=demand_layers[layer];auto suffix=std::to_string(layer);
      x.descriptor=allocate(0,"demand-descriptor-"+suffix,sizeof(p58am::Map),Category::weights,Lifetime::process);
      x.stage=allocate(0,"demand-slot-map-"+suffix,sizeof(p58am::Map),Category::weights,Lifetime::process);
      x.host=allocate(0,"demand-host-descriptor-"+suffix,sizeof(p58am::Map),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
      x.host_stage=allocate(0,"demand-host-slot-map-"+suffix,sizeof(p58am::Map),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
      for(auto&[name,bank]:expert_banks)if(bank.layer==int(layer)){x.hosts.at(bank.projection)=bank.host;x.tables.at(bank.projection)=bank.table;x.bank_bytes.at(bank.projection)=bank.expert_bytes;}
      for(auto id:x.hosts)require(id,"demand layer bank missing");
      // This mixed checkpoint includes an IQ3_XXS gate/up layer. Its packed
      // rows are not IQ2_S: neither reinterpret them nor stage truncated bytes.
      x.layout_supported=x.bank_bytes==std::array<size_t,3>{p58am::gate_bytes,p58am::up_bytes,p58am::down_bytes};
    }
  }
  void demand_capture(std::vector<ownrt::PreparedCompute>& commands,const std::function<void()>& action){
    commands.clear();dev(0).begin_capture(commands);try{action();dev(0).end_capture();}catch(...){dev(0).end_capture();throw;}
  }
  void demand_prepare(){
    if(!demand_storage)return;
    for(const auto& l:p.launches){if(l.op!="expert_gate_up"&&l.op!="routed_gemv")continue;
      auto layer=std::stoi(l.label.substr(4));auto& x=demand_layers.at(layer);const bool down=l.op=="routed_gemv";
      auto& members=matrices.at(&l);p39::Bindings b;b.indirect=true;b.error=buffers[0].at("error").id;b.active=buffers[0].at("active").id;b.position=buffers[0].at("position").id;b.capacity=p.g.context;
      if(!down)demand_capture(x.describe,[&]{p58am::descriptor(dev(0),members[0].routes,x.tables,x.descriptor,uint64_t(demand_pointer(cache_arena)),a.cache_bytes,x.bank_bytes);});
      if(!x.layout_supported){(down?x.down_resident:x.gate_resident).clear();(down?x.down_missing:x.gate_missing).clear();continue;}
      demand_capture(down?x.down_resident:x.gate_resident,[&]{p58am::partition(dev(0),members,b,halfcache,x.descriptor,x.stage,1,down);});
      demand_capture(down?x.down_missing:x.gate_missing,[&]{p58am::partition(dev(0),members,b,halfcache,x.descriptor,x.stage,2,down);});
    }
    size_t metadata=sizeof(demand_layers)+sizeof(demand_pool)+sizeof(demand_bypass)+96*sizeof(p58am::Map)+512*128;
    size_t commands=0;
    for(auto& x:demand_layers)for(auto* v:{&x.describe,&x.gate_resident,&x.gate_missing,&x.down_resident,&x.down_missing}){
      require(v->size()==((&x.describe==v||x.layout_supported)?1u:0u),"layout-qualified captured demand operation per hook");commands+=v->size();metadata+=v->capacity()*sizeof(ownrt::PreparedCompute);
      for(auto& c:*v)metadata+=c.ids.capacity()*sizeof(Allocation)+c.pointers.capacity()*sizeof(void*)+c.argument_bytes.capacity()+c.operation_bytes.capacity()+1024;
    }
    require(metadata+1048576<=2097152,"demand host metadata/event cap including runtime allowance");
    save(a.output/"demand-prepared-census.json","{\"layers\":48,\"commands\":"+std::to_string(commands)+",\"application_metadata_bound_bytes\":"+std::to_string(metadata)+",\"native_event_runtime_allowance_bytes\":1048576,\"host_metadata_cap_bytes\":2097152,\"device_maps_bytes\":"+std::to_string(96*sizeof(p58am::Map))+",\"packed_staging_bytes\":126156800,\"event_capacity\":512}\n");
  }
  ownrt::Event demand_issue_commands(const std::vector<ownrt::PreparedCompute>& commands){ownrt::Event last=0;for(auto& cmd:commands){last=dev(0).issue(cmd);finish(0,{last,last,1},true);}return last;}
  void demand_wait(uint64_t ticket){auto end=std::chrono::steady_clock::now()+std::chrono::seconds(a.wait_seconds);while(!demand_backend().demand_complete(ticket)){guard();require(std::chrono::steady_clock::now()<end,"demand cooperative descriptor wait");std::this_thread::sleep_for(std::chrono::milliseconds(1));}}
  bool demand_issue(size_t index){
    const auto& l=p.launches[index];if(l.op!="expert_gate_up"&&l.op!="routed_gemv")return false;
    const unsigned layer=std::stoi(l.label.substr(4));auto&x=demand_layers.at(layer);auto& b=demand_backend();
    if(l.op=="routed_gemv"){
      if(a.demand=="off"||!x.layout_supported){x.dr=demand_issue_commands(issue_sites.at(index).commands);return true;}
      x.dr=demand_issue_commands(x.down_resident);if(x.down_ticket)b.demand_barrier(x.down_ticket);x.dm=demand_issue_commands(x.down_missing);return true;
    }
    x.trace=a.demand_diagnostics&&!allocation_probe;x.copies_size=0;x.staged_entries=0;x.resident_slots=0;x.gm=x.dm=x.dr=0;x.gate_ticket=x.down_ticket=0;
    auto producer=x.producer=demand_issue_commands(x.describe);
    auto descriptor=x.readback=b.demand_copy(demand_pointer(x.host),demand_pointer(x.descriptor),sizeof(p58am::Map),producer);
    x.gr=demand_issue_commands(a.demand=="off"||!x.layout_supported?issue_sites.at(index).commands:x.gate_resident); // Host waits only AFTER resident launch.
    demand_wait(descriptor);
    auto* desc=static_cast<p58am::Map*>(demand_pointer(x.host));auto* stages=static_cast<p58am::Map*>(demand_pointer(x.host_stage));*stages={};
    bool neighbor=false;for(auto&s:desc->slots){neighbor|=s.valid&&s.resident;x.resident_slots+=s.valid&&s.resident;}
    if(a.demand=="off"||!x.layout_supported)return true;
    std::array<int,10> entry;entry.fill(-1);
    for(unsigned slot=0;slot<10;++slot){auto&s=desc->slots[slot];if(!s.valid){++demand_bypass[0];continue;}if(s.resident)continue;auto expert=layer*512+s.expert;bool pending=false;
      if(maintenance.plan)for(auto&f:maintenance.plan->fills)pending|=f.expert==expert;
      // Only exact immutable pinned-bank addresses are eligible misses. An
      // uncertain/malformed published pointer remains on the original path.
      if(!allocation_probe&&(s.gate!=uint64_t(demand_pointer(x.hosts[0],size_t(s.expert)*p58am::gate_bytes,p58am::gate_bytes))||s.up!=uint64_t(demand_pointer(x.hosts[1],size_t(s.expert)*p58am::up_bytes,p58am::up_bytes))||s.down!=uint64_t(demand_pointer(x.hosts[2],size_t(s.expert)*p58am::down_bytes,p58am::down_bytes)))){++demand_bypass[4];continue;}
      entry[slot]=demand_pool.acquire(expert,maintenance_position,neighbor,pending);if(entry[slot]<0){++demand_bypass[!neighbor?1:pending?2:3];continue;}++x.staged_entries;
      size_t off=size_t(entry[slot])*p58am::expert_bytes;auto&stage=stages->slots[slot];stage.expert=s.expert;stage.generation=s.generation;stage.valid=1;
      stage.gate=uint64_t(demand_pointer(demand_storage,off,p58am::expert_bytes));stage.up=stage.gate+p58am::gate_bytes;stage.down=stage.up+p58am::up_bytes;
      x.copies[x.copies_size++]=b.demand_copy(demand_pointer(demand_storage,off,p58am::gate_bytes),demand_pointer(x.hosts[0],size_t(s.expert)*p58am::gate_bytes,p58am::gate_bytes),p58am::gate_bytes,0);
      x.copies[x.copies_size++]=b.demand_copy(demand_pointer(demand_storage,off+p58am::gate_bytes,p58am::up_bytes),demand_pointer(x.hosts[1],size_t(s.expert)*p58am::up_bytes,p58am::up_bytes),p58am::up_bytes,0);
    }
    x.gate_ticket=b.demand_copy(demand_pointer(x.stage),stages,sizeof(*stages),0);x.down_ticket=0;
    for(unsigned slot=0;slot<10;++slot)if(entry[slot]>=0){size_t off=size_t(entry[slot])*p58am::expert_bytes+p58am::gate_bytes+p58am::up_bytes;
      x.down_ticket=b.demand_copy(demand_pointer(demand_storage,off,p58am::down_bytes),demand_pointer(x.hosts[2],size_t(desc->slots[slot].expert)*p58am::down_bytes,p58am::down_bytes),p58am::down_bytes,0);x.copies[x.copies_size++]=x.down_ticket;demand_pool.copied(entry[slot],x.down_ticket);
    }
    b.demand_barrier(x.gate_ticket);x.gm=demand_issue_commands(x.gate_missing);return true;
  }
  void demand_collect(){
    if(!a.demand_diagnostics||allocation_probe||!demand_storage)return;
    std::ofstream out(a.output/"demand-events.jsonl",std::ios::app);
    for(unsigned layer=0;layer<48;++layer){auto&x=demand_layers[layer];if(!x.trace)continue;
      out<<"{\"schema\":\"packet58am.demand.v1\",\"identity\":"<<ownrt::quote(a.demand_identity)<<",\"position\":"<<maintenance_position<<",\"layer\":"<<layer<<",\"layout_supported\":"<<(x.layout_supported?"true":"false")<<",\"mode\":"<<ownrt::quote(a.demand)<<",\"slot_ids\":[0,1,2,3,4,5,6,7,8,9],\"resident_slots\":"<<x.resident_slots<<",\"staged_entries\":"<<x.staged_entries<<",\"staged_bytes\":"<<x.staged_entries*p58am::expert_bytes<<",\"copy_engine\":\"copy-only-BCS\",\"descriptor_producer\":"<<x.producer<<",\"descriptor_readback\":"<<x.readback<<",\"missing_consumer\":"<<x.gm<<",\"clock_domain\":\"same-device-sycl-profiling\",\"events\":[";
      bool comma=false;auto emit=[&](const char*kind,uint64_t id,bool copy){if(!id)return;std::array<uint64_t,2> stamp;if(copy)stamp=demand_backend().demand_timing(id);else{auto t=dev(0).timing(id);stamp={t.start_ns,t.end_ns};}out<<(comma?",":"")<<"{\"kind\":"<<ownrt::quote(kind)<<",\"id\":"<<id<<",\"start_ns\":"<<stamp[0]<<",\"end_ns\":"<<stamp[1]<<"}";comma=true;};
      emit("router",x.router,false);emit("descriptor",x.producer,false);emit("descriptor-D2H",x.readback,true);emit((a.demand=="off"||!x.layout_supported)?"original-mixed-gate":"resident-gate",x.gr,false);emit("missing-gate",x.gm,false);emit((a.demand=="off"||!x.layout_supported)?"original-mixed-down":"resident-down",x.dr,false);emit("missing-down",x.dm,false);if(a.demand!="off")emit("stage-map-H2D",x.gate_ticket,true);
      for(unsigned i=0;i<x.copies_size;++i)emit("packed-H2D",x.copies[i],true);
      out<<"],\"all_consumers_completed\":true,\"snapshot_disposition\":\"retained-until-policy\"}\n";x.trace=false;
    }
    require(bool(out),"demand event stream write");
  }
  void demand_consumed(){if(!demand_storage)return;demand_pool.consumed(maintenance_position);demand_backend().demand_retire();
    size_t retained=0,leased=0;for(auto&e:demand_pool.rows){retained+=e.state==p58am::State::retained;leased+=e.state==p58am::State::leased;}
    save(a.output/"demand-counters.json","{\"schema\":\"packet58am.counters.v1\",\"staged_H2D_bytes\":"+std::to_string(demand_pool.staged_bytes)+",\"fill_D2D_bytes\":"+std::to_string(demand_pool.d2d_bytes)+",\"staged_unused_bytes\":"+std::to_string(demand_pool.unused_bytes)+",\"repeated_demand_bytes\":"+std::to_string(demand_pool.repeated_bytes)+",\"high_water_entries\":"+std::to_string(demand_pool.high_water)+",\"retained_entries\":"+std::to_string(retained)+",\"leased_entries\":"+std::to_string(leased)+"}\n");
    save(a.output/"demand-bypass.json","{\"invalid_route\":"+std::to_string(demand_bypass[0])+",\"no_resident_neighbor\":"+std::to_string(demand_bypass[1])+",\"maintenance_selected\":"+std::to_string(demand_bypass[2])+",\"pool_full\":"+std::to_string(demand_bypass[3])+",\"pointer_uncertain\":"+std::to_string(demand_bypass[4])+"}\n");
  }
  void demand_select_fills(){if(!maintenance.plan)return;for(auto& f:maintenance.plan->fills)demand_pool.select(f.expert,previous_snapshot,maintenance.plan->epoch);demand_pool.discard(previous_snapshot);}
