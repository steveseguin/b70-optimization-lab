// Included inside Engine. No weight upload/allocation or device-owner transition.
  bool bracket_weights_locked=false;
  std::string bracket_arena_descriptors(bool weights_only=false) const {
    std::ostringstream out;
    for(const auto& [id,owner]:allocations) {
      const auto& row=devices.at(owner.first)->arena.row(id);
      if(weights_only&&row.category!=Category::weights)continue;
      out<<id<<':'<<owner.first<<':'<<row.label<<':'<<row.bytes<<':'
         <<int(row.category)<<':'<<int(row.memory)<<':'<<int(row.lifetime)<<':'
         <<uintptr_t(row.pointer)<<':'<<row.live<<'\n';
    }
    return out.str();
  }
  std::string bracket_arena_hash(bool weights_only=false) const {
    const auto text=bracket_arena_descriptors(weights_only);
    return hash(std::vector<uint8_t>(text.begin(),text.end()));
  }
  void bracket_select(const fs::path& selection,const std::string& digest,bool validate_only=false) {
    guard();drain();verify_configuration();
    p49d::Selection next;next.load(selection.string(),digest);
    require(next.draft.size()==sealed_selection.draft.size(),"bracket draft schema differs");
    for(const auto& [key,value]:sealed_selection.draft) {
      require(next.draft.contains(key),"bracket missing draft choice");
      if(true)require(next.draft.at(key)==value,"bracket draft layout/selection differs: reload required: "+key);
    }
    require(next.choices.size()==sealed_selection.choices.size(),"bracket choice shape differs");
    for(const auto& [key,value]:sealed_selection.choices) {
      require(next.choices.contains(key),"bracket missing choice");
      // packet186: only a V3-layout load (rank0_layers present) may switch the V3 execution
      // (boundary) and the packet153 snapshot host mode; every other key is storage or closed.
      // packet188: a k3-storage load (rank0_layers 0-26) may also switch the two trims.
      const bool k3_storage=sealed_selection.choices.contains("rank0_layers")&&sealed_selection.choices.at("rank0_layers")=="0-26";
      // packet189: a k3-storage load may also switch the boundary export path (boundary_export copy <-> kernel).
      // packet194: a k3-storage load may also switch the gate/up kernel of the exp-halfcache layout (expert_gateup production <-> diet).
      const bool switchable=sealed_selection.choices.contains("rank0_layers")&&(key=="boundary"||key=="snapshot_host"||(k3_storage&&(key=="kernel_io"||key=="rank0_prepare"||key=="boundary_export"||key=="expert_gateup")));
      if(!switchable)
        require(next.choices.at(key)==value,"bracket storage/unsupported choice differs: reload required: "+key);
    }
    // Narrow, explicit domains; parser registration alone does not qualify a switch.
    auto domain=[](const auto& values,const char* key,std::initializer_list<const char*> allowed){
      for(auto value:allowed)if(values.at(key)==value)return;
      throw std::invalid_argument(std::string("bracket unsupported switch value: ")+key);
    };
    for(const auto* selection:{&sealed_selection,&next}) {
      domain(selection->choices,"other_fusion",{"fused"});
      domain(selection->choices,"route",{"route-fast"});
      domain(selection->choices,"recurrence",{"rows4-shared","rec-parallel","rec-both-plus"});
      domain(selection->choices,"hc_gate",{"wide"});
      domain(selection->choices,"probe",{"off"});
      domain(selection->choices,"snapshot_host",{"production","static"}); // packet153 receipts; packet186 bundles static with V3
      domain(selection->choices,"dense_scales",{"expanded"}); // packet183 metadata closed (-6.2%)
      if(selection->choices.contains("rank0_layers")){
        domain(selection->choices,"rank0_layers",{"0-25","0-26"});
        if(selection->choices.at("rank0_layers")=="0-26"){ // packet188: k3 storage; V3 (k2) and k3 views, trims switchable
          domain(selection->choices,"boundary",{"rank0","rank0-k3"});
          domain(selection->choices,"kernel_io",{"copy","kernel"});
          domain(selection->choices,"rank0_prepare",{"sync","async"});
          domain(selection->choices,"boundary_export",{"copy","kernel"}); // packet189
          if(selection->choices.contains("expert_gateup"))domain(selection->choices,"expert_gateup",{"production","diet"}); // packet194 (absent = production, the 19-key record selection)
        } else {
          domain(selection->choices,"boundary",{"none","rank0"});
          require(!selection->choices.contains("kernel_io")&&!selection->choices.contains("rank0_prepare")&&!selection->choices.contains("boundary_export")&&!selection->choices.contains("expert_gateup"),"packet188 trims require the k3 storage");
        }
        domain(selection->choices,"head",{"production"}); // V3: full target head on rank 1, no merge
      }
      domain(selection->draft,"qsa_attention",{"production","packet59"});
    }
    require(resident&&prepared_path,"bracket requires resident prepared path");
    if(validate_only)return;
    const auto before=bracket_arena_hash();
    if(miss_banks()){
      // Quiescent request boundary: return all three physical roles to their
      // load-time order through the existing six-pair rotation machinery.
      if(active_bank!=0){if(spare_bank!=0)rotate_spare_bank();swap_state_banks();}
      if(spare_bank!=1)rotate_spare_bank();
      require(active_bank==0&&spare_bank==1,"bracket canonical bank roles");
      bank_parity=0;bank_cache_ready=false;
      for(auto& cache:bank_cache)cache=BankCache{};
    }else if(bank_parity)swap_state_banks();
    sealed_selection=std::move(next);a.selection=selection;a.selection_sha256=digest;refresh_v3();
    prepared.clear();alternate_prepared.clear();issue_sites.clear();alternate_issue_sites.clear();matrices.clear();
    context_extent=alternate_context_extent=32;capacity_reprepares=0;
    prepare_plan();prepare_commands();
    if(miss_banks()){
      for(int i=0;i<6;++i){if(i%2==0)rotate_spare_bank();else swap_state_banks();if(i<5){prepare_plan();prepare_commands();}}
      require(active_bank==0&&spare_bank==1,"bracket six-pair recapture");
      bank_parity=0;bank_cache_ready=true;
    }else if(a.rank==0){swap_state_banks();prepare_plan();prepare_commands();swap_state_banks();}
    require(bank_parity==0&&before==bracket_arena_hash(),"bracket changed loaded arena descriptors");
    verify_configuration();
  }

  // ---- packet186 V3 / packet188 k3: verified-boundary rebalance ------------------------------
  // Storage flag (rank0_layers, fixed per load): rank 0 also holds layers 24-25 (0-25) or 24-26 (0-26).
  // Execution flag (boundary, switchable only at a quiescent bracket boundary): rank 0 runs 24-25 (rank0)
  // or 24-26 (rank0-k3, k3 storage only) for the verified token. Rank 0 never runs a stored moved layer
  // inside a half; a stored layer outside the active boundary set (layer 26 in a V3 view of the k3
  // storage) is idle on rank 0 and run by rank 1. Precomputed: the half loop pays one byte test per launch.
  bool v3_extended=false,v3_active=false;int v3_first=24,v3_end=26,v3_store_end=26;
  bool kio_active=false,prepare_async=false; // packet188 trims: kernel_io=kernel, rank0_prepare=async
  // packet189: boundary_export=copy (default; V3's copy-engine readback of the 20,480-byte export) or kernel
  // (packet188's folded KioCopy readback). Only meaningful with kernel_io=kernel; counters prove which path ran.
  bool export_copy=true;uint64_t export_copy_runs=0,export_kernel_runs=0;
  // packet194: expert_gateup=diet selects packet193's exact gate/up instruction diet (p193diet::GateUp) at every exp-halfcache
  // gate/up site when commands are prepared; production (default, absent in the 19-key record selection) is the record kernel.
  // Per-prepare counters: gate/up sites prepared with the diet kernel (exp-halfcache, IQ2_S layers) and gate/up sites on another
  // layout that keep their kernel (IQ3_S p28 layers at production shape; every miniature expert). At production shape a selected
  // diet with zero diet sites refuses (full_shape_entry.cpp): never silently inert.
  bool expert_diet=false;uint64_t expert_diet_sites=0,expert_diet_inert_sites=0;
  std::vector<uint8_t> v3_skip_half;std::vector<size_t> v3_sites,v3_store_sites;std::set<std::string> v3_private;
  void refresh_v3(){
    auto pick=[&](const char* key,const char* fallback){auto i=sealed_selection.choices.find(key);return i==sealed_selection.choices.end()?std::string(fallback):i->second;};
    const auto layers=pick("rank0_layers","0-23"),mode=pick("boundary","none"),io=pick("kernel_io","copy"),prep=pick("rank0_prepare","sync"),exp=pick("boundary_export","copy"),gateup=pick("expert_gateup","production");
    require(layers=="0-23"||layers=="0-25"||layers=="0-26","packet188 rank0_layers domain");
    require(mode=="none"||mode=="rank0"||mode=="rank0-k3","packet188 boundary domain");
    require(io=="copy"||io=="kernel","packet188 kernel_io domain");require(prep=="sync"||prep=="async","packet188 rank0_prepare domain");
    require(exp=="copy"||exp=="kernel","packet189 boundary_export domain");
    require(gateup=="production"||gateup=="diet","packet194 expert_gateup domain");
    require(layers=="0-26"||!sealed_selection.choices.contains("expert_gateup"),"packet194 expert_gateup is a k3-storage key");
    v3_extended=layers!="0-23";v3_active=mode!="none";
    require(!v3_active||v3_extended,"V3 boundary requires an extended rank-0 layout");
    require(mode!="rank0-k3"||layers=="0-26","packet188 k3 boundary requires rank0_layers 0-26");
    require(layers=="0-26"||(io=="copy"&&prep=="sync"&&exp=="copy"),"packet188 trims require the k3 storage (pinned kernel-io staging)");
    require(layers!="0-26"||v3_active,"packet188 k3 storage runs a boundary in every view");
    require(layers!="0-26"||sealed_selection.choices.contains("boundary_export"),"packet189 k3 storage selections name boundary_export explicitly");
    kio_active=io=="kernel";prepare_async=prep=="async";export_copy=exp=="copy";expert_diet=gateup=="diet";
    if(v3_extended)require(resident&&!a.legacy&&a.draft_rank==1&&a.target_split==0&&head_choice()=="production",
      "V3 layout requires the resident prepared path, the rank-1 draft, the 24/24 base split and the full target head on rank 1");
    const int mini=a.mini?1:0;
    v3_first=a.mini?2:24;
    v3_store_end=v3_first+(layers=="0-26"?3-mini:layers=="0-25"?2-mini:0);
    v3_end=v3_first+(mode=="rank0-k3"?3-mini:2-mini); // execution set [v3_first, v3_end); U views keep the V3 set
    v3_skip_half.assign(p.launches.size(),0);v3_sites.clear();v3_store_sites.clear();
    if(a.pipeline_enabled()){
      // The general pipeline owns explicit disjoint layer ranges. It does not
      // use the legacy two-rank duplicated island or its separate boundary op.
      require(!v3_extended&&!v3_active&&!kio_active&&!prepare_async&&export_copy&&!expert_diet,
              "general pipeline requires neutral legacy V3 boundary selection");
      return;
    }
    for(size_t i=0;i<p.launches.size();++i){const auto& l=p.launches[i];if(!l.label.starts_with("blk."))continue;
      const int layer=std::stoi(l.label.substr(4));const bool stored=layer>=v3_first&&layer<v3_store_end,moved=layer>=v3_first&&layer<v3_end;
      if(a.rank==0&&layer>=v3_first){require(v3_extended&&stored,"rank 0 holds a moved layer without the V3 layout");v3_skip_half[i]=1;v3_store_sites.push_back(i);if(moved)v3_sites.push_back(i);}
      if(a.rank==1&&moved&&v3_active)v3_skip_half[i]=1;
    }
    if(a.rank==0&&v3_extended)v3_check_plan();
    if(a.rank==0&&!v3_extended)require(v3_sites.empty()&&v3_store_sites.empty()&&v3_private.empty(),"production layout holds no moved layer");
  }
  // Load-time proof that the stored moved layers are a closed island on rank 0: they read only their own
  // buffers plus the residual stream and the shared controls, contain no position-dependent (QSA) operator,
  // and no other rank-0 launch touches their buffers. Their state can therefore only change when the
  // boundary command issues them (for a verified token only).
  void v3_check_plan(){
    require(!v3_sites.empty()&&!v3_store_sites.empty(),"V3 layout without moved layers on rank 0");
    std::set<int> stored,executed;std::set<std::string> ops;std::set<std::string> priv;
    const std::set<std::string> shared{"streams","active","error"};
    for(size_t i:v3_store_sites){const auto& l=p.launches[i];stored.insert(std::stoi(l.label.substr(4)));ops.insert(l.op);
      require(!l.op.starts_with("qsa")&&l.op!="lookup"&&l.op!="begin"&&l.op!="commit"&&l.op!="handoff"&&l.op!="handoff_result","V3 moved layer must be position-free GDN");
      for(const auto& x:l.outputs)if(x!="streams"&&x!="error")priv.insert(x);}
    for(size_t i:v3_sites)executed.insert(std::stoi(p.launches[i].label.substr(4)));
    std::set<int> expected_store,expected_exec;for(int k=v3_first;k<v3_store_end;++k)expected_store.insert(k);for(int k=v3_first;k<v3_end;++k)expected_exec.insert(k);
    require(stored==expected_store&&executed==expected_exec&&ops.count("gdn")&&ops.count("conv"),"V3 moved layers must be exactly the stored GDN layers (24-25 / 24-26; mini 2 / 2-3)");
    for(size_t i:v3_store_sites){const auto& l=p.launches[i];
      for(const auto& x:l.inputs)require(priv.count(x)||shared.count(x),"V3 moved layer reads a buffer outside its island: "+x);}
    for(size_t i=0;i<p.launches.size();++i){if(std::find(v3_store_sites.begin(),v3_store_sites.end(),i)!=v3_store_sites.end())continue;const auto& l=p.launches[i];
      for(const auto& x:l.inputs)require(!priv.count(x),"rank-0 half reads a V3 private buffer: "+x);
      for(const auto& x:l.outputs)require(!priv.count(x),"rank-0 half writes a V3 private buffer: "+x);}
    // Per-layer islands: an executed boundary never reads a stored-but-idle layer's buffers.
    std::set<std::string> exec_priv;for(size_t i:v3_sites)for(const auto& x:p.launches[i].outputs)if(x!="streams"&&x!="error")exec_priv.insert(x);
    for(size_t i:v3_sites)for(const auto& x:p.launches[i].inputs)require(exec_priv.count(x)||shared.count(x),"V3 boundary reads an idle stored layer's buffer: "+x);
    const auto& last=p.launches[v3_sites.back()];
    require(last.label=="blk."+std::to_string(v3_end-1)+".ffn.combine"&&std::find(last.outputs.begin(),last.outputs.end(),"streams")!=last.outputs.end(),"V3 boundary must end with the last moved layer's residual stream");
    require(v3_private.empty()||v3_private==priv,"V3 private set is a load-time constant");v3_private=std::move(priv);
  }

  // ---- packet188 kernel-io staging (pinned USM host, per rank, k3 storage loads only) ----------------
  std::vector<Allocation> kio;std::vector<uint8_t*> kio_host;size_t kio_bytes=0,kio_stage_bytes=0;
  uint64_t kio_sync_transfers=0,kio_async_copies=0,staged_halves=0;
  uint8_t* raw(int c,Allocation id){return static_cast<uint8_t*>(dev(c).arena.row(id).pointer);}
  void allocate_kio(){
    if(sealed_selection.choices.find("rank0_layers")==sealed_selection.choices.end()||sealed_selection.choices.at("rank0_layers")!="0-26")return;
    require(kio.empty(),"packet188 kernel-io staging allocated once");
    size_t stage=4096; // token + every rank-0 lookup output, 64-byte aligned
    for(const auto& l:p.launches)if(l.op=="lookup"){const auto& s=buffers[l.card].at(l.outputs[0]);stage+=(s.n*flash::scalar_bytes(s.type)+63)/64*64;}
    kio_stage_bytes=(stage+4095)/4096*4096;kio_bytes=p188::stage_offset+kio_stage_bytes;
    for(int c=0;c<a.cards;++c){kio.push_back(allocate(c,"kernel-io",kio_bytes,Category::pinned_slab,Lifetime::transfer,Memory::pinned));
      kio_host.push_back(raw(c,kio.back()));std::memset(kio_host.back(),0,kio_bytes);}
  }
  bool kio_sync(int c,Allocation id,size_t offset,size_t n){
    if(!kio_active||size_t(c)>=kio.size()||n==0||n>p188::sync_capacity)return false;
    const auto& r=dev(c).arena.row(id);return r.live&&r.memory==Memory::device&&offset+n<=r.bytes;
  }
  void kio_upload(int c,Allocation dst,size_t offset,const void* src,size_t n){
    drain();auto started=std::chrono::steady_clock::now();
    std::memcpy(kio_host[c]+p188::sync_offset,src,n);
    p188::KioCopy op;op.add(raw(c,dst)+offset,kio_host[c]+p188::sync_offset,n);Allocation ids[1]={dst};
    wait(c,dev(c).compute(op,std::span<const Allocation>(ids,1),{}));retire_events(c);
    transfer_ms+=ms(started);++kio_sync_transfers;
  }
  std::vector<uint8_t> kio_readback(int c,Allocation src,size_t n){
    drain();auto started=std::chrono::steady_clock::now();
    p188::KioCopy op;op.add(kio_host[c]+p188::sync_offset,raw(c,src),n);Allocation ids[1]={src};
    wait(c,dev(c).compute(op,std::span<const Allocation>(ids,1),{}));retire_events(c);
    std::vector<uint8_t> b(kio_host[c]+p188::sync_offset,kio_host[c]+p188::sync_offset+n);
    transfer_ms+=ms(started);++kio_sync_transfers;return b;
  }
  // Ordered, unwaited copy of (dst,dst_offset) <- (src,src_offset) items: one KioCopy kernel when kernel_io=kernel,
  // otherwise one CopyEngine copy per item (the transfer the rest of the engine already uses).
  struct IoItem{Allocation dst;size_t dst_offset;Allocation src;size_t src_offset;size_t bytes;};
  ownrt::Event io_copy(int c,const std::vector<IoItem>& items){
    require(!items.empty()&&items.size()<=p188::KioCopy::width,"packet188 io_copy width");
    for(const auto& x:items){const auto& d=dev(c).arena.row(x.dst);const auto& s=dev(c).arena.row(x.src);
      require(d.live&&s.live&&x.bytes>0&&x.dst_offset+x.bytes<=d.bytes&&x.src_offset+x.bytes<=s.bytes,"packet188 io_copy extent");}
    if(!kio_active){ownrt::CopyEngine copy(dev(c));ownrt::Event last=0;for(const auto& x:items)last=copy.copy(x.dst,x.dst_offset,x.src,x.src_offset,x.bytes,{});return last;}
    p188::KioCopy op;std::vector<Allocation> ids;
    for(const auto& x:items){op.add(raw(c,x.dst)+x.dst_offset,raw(c,x.src)+x.src_offset,x.bytes);
      for(auto id:{x.dst,x.src})if(dev(c).arena.row(id).memory==Memory::device&&std::find(ids.begin(),ids.end(),id)==ids.end())ids.push_back(id);}
    require(!ids.empty(),"packet188 io_copy needs a device endpoint");
    ++kio_async_copies;return dev(c).compute(op,std::span<const Allocation>(ids.data(),ids.size()),{});
  }
  ownrt::Event io_copy(int c,Allocation dst,size_t dst_offset,Allocation src,size_t src_offset,size_t bytes){
    return io_copy(c,std::vector<IoItem>{{dst,dst_offset,src,src_offset,bytes}});
  }
  // rank0_prepare=async (rank 0): the device position and token_history are captured into pinned slots by an
  // ordered copy issued before the half's first kernel; token + lookup outputs are staged in pinned memory and
  // loaded by ONE ordered copy. No host wait: the half's final drain completes them; finish_staged() then
  // checks the captured position and returns the captured history (the bytes the synchronous path read).
  void stage_half_inputs(int token){
    require(a.rank==0&&prepare_async&&!kio.empty(),"packet188 staged inputs ownership");
    std::vector<IoItem> pre{{kio[0],p188::position_slot,buffers[0].at("position").id,0,4}};
    if(buffers[0].count("token_history"))pre.push_back({kio[0],p188::token_history_slot,buffers[0].at("token_history").id,0,p188::history_bytes});
    std::memset(kio_host[0]+p188::position_slot,0xff,4);tail=io_copy(0,pre);
    std::vector<std::pair<std::string,std::vector<uint16_t>>> staged;prepare_token(token,&staged);
    std::vector<IoItem> load;size_t off=p188::stage_offset;
    std::memcpy(kio_host[0]+off,&token,4);load.push_back({buffers[0].at("token").id,0,kio[0],off,4});off+=64;
    for(const auto& [name,values]:staged){const auto& s=buffers[0].at(name);const size_t n=values.size()*2;
      require(n==s.n*flash::scalar_bytes(s.type),"control extent");require(off+n<=kio_bytes,"packet188 staged input capacity");
      std::memcpy(kio_host[0]+off,values.data(),n);load.push_back({s.id,0,kio[0],off,n});off+=(n+63)/64*64;}
    tail=io_copy(0,load);++staged_halves;
  }
  // Folded kernel readbacks (kernel_io=kernel): one ordered kernel stores several small device values into the
  // pinned sync staging, then one wait. Values are the bytes the separate synchronous readbacks returned.
  std::vector<uint8_t> kio_read_many(int c,const std::vector<std::pair<Allocation,size_t>>& sources){
    require(kio_active&&size_t(c)<kio.size()&&!sources.empty()&&sources.size()<=p188::KioCopy::width,"packet188 folded readback");
    drain();auto started=std::chrono::steady_clock::now();
    p188::KioCopy op;std::vector<Allocation> ids;size_t off=0;
    for(const auto& [id,n]:sources){const auto& r=dev(c).arena.row(id);require(r.live&&r.memory==Memory::device&&n<=r.bytes&&off+n<=p188::sync_capacity,"packet188 folded readback extent");
      op.add(kio_host[c]+p188::sync_offset+off,raw(c,id),n);if(std::find(ids.begin(),ids.end(),id)==ids.end())ids.push_back(id);off+=(n+63)/64*64;}
    wait(c,dev(c).compute(op,std::span<const Allocation>(ids.data(),ids.size()),{}));retire_events(c);
    std::vector<uint8_t> out;off=0;
    for(const auto& [id,n]:sources){out.insert(out.end(),kio_host[c]+p188::sync_offset+off,kio_host[c]+p188::sync_offset+off+n);off+=(n+63)/64*64;}
    transfer_ms+=ms(started);++kio_sync_transfers;return out;
  }
  std::pair<int,int> read_error_and_token(){
    auto b=kio_read_many(0,{{buffers[0].at("error").id,4},{buffers[0].at("next_token").id,4}});
    int error=0,token=-1;std::memcpy(&error,b.data(),4);std::memcpy(&token,b.data()+4,4);return {error,token};
  }
  std::vector<uint8_t> finish_staged(int expected_position,bool history){
    require(!tail,"packet188 staged inputs read before the half drained");
    int32_t position=-1;std::memcpy(&position,kio_host[0]+p188::position_slot,4);
    require(position==expected_position,"position sequence mismatch (staged)");
    if(!history)return {};
    return std::vector<uint8_t>(kio_host[0]+p188::token_history_slot,kio_host[0]+p188::token_history_slot+p188::history_bytes);
  }
