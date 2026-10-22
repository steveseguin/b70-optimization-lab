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
      const bool switchable=sealed_selection.choices.contains("rank0_layers")&&(key=="boundary"||key=="snapshot_host");
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
        domain(selection->choices,"rank0_layers",{"0-25"});
        domain(selection->choices,"boundary",{"none","rank0"});
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

  // ---- packet186 V3: verified-boundary rebalance -------------------------------------------
  // Storage flag (rank0_layers, fixed per load: rank 0 also holds layers 24-25) and execution
  // flag (boundary: rank 0 runs 24-25 for the verified token; switchable only at a quiescent
  // bracket boundary). Precomputed so the half loop pays one byte test per launch.
  bool v3_extended=false,v3_active=false;int v3_first=24,v3_end=26;
  std::vector<uint8_t> v3_skip_half;std::vector<size_t> v3_sites;std::set<std::string> v3_private;
  void refresh_v3(){
    auto pick=[&](const char* key,const char* fallback){auto i=sealed_selection.choices.find(key);return i==sealed_selection.choices.end()?std::string(fallback):i->second;};
    const auto layers=pick("rank0_layers","0-23"),mode=pick("boundary","none");
    require(layers=="0-23"||layers=="0-25","packet186 rank0_layers domain");require(mode=="none"||mode=="rank0","packet186 boundary domain");
    v3_extended=layers=="0-25";v3_active=mode=="rank0";
    require(!v3_active||v3_extended,"V3 boundary requires rank0_layers 0-25");
    if(v3_extended)require(resident&&!a.legacy&&a.draft_rank==1&&a.target_split==0&&head_choice()=="production",
      "V3 layout requires the resident prepared path, the rank-1 draft, the 24/24 base split and the full target head on rank 1");
    v3_first=a.mini?2:24;v3_end=a.mini?3:26;
    v3_skip_half.assign(p.launches.size(),0);v3_sites.clear();
    for(size_t i=0;i<p.launches.size();++i){const auto& l=p.launches[i];if(!l.label.starts_with("blk."))continue;
      const int layer=std::stoi(l.label.substr(4));const bool moved=layer>=v3_first&&layer<v3_end;
      if(a.rank==0&&moved){require(v3_extended,"rank 0 holds a moved layer without the V3 layout");v3_skip_half[i]=1;v3_sites.push_back(i);}
      if(a.rank==1&&moved&&v3_active)v3_skip_half[i]=1;
    }
    if(a.rank==0&&v3_extended)v3_check_plan();
    if(a.rank==0&&!v3_extended)require(v3_sites.empty()&&v3_private.empty(),"production layout holds no moved layer");
  }
  // Load-time proof that the moved layers are a closed island on rank 0: they read only their own
  // buffers plus the residual stream and the shared controls, contain no position-dependent
  // (QSA) operator, and no other rank-0 launch touches their buffers. Their state can therefore
  // only change when the boundary command issues them.
  void v3_check_plan(){
    require(!v3_sites.empty(),"V3 layout without moved layers on rank 0");
    std::set<int> layers;std::set<std::string> ops;std::set<std::string> priv;
    const std::set<std::string> shared{"streams","active","error"};
    for(size_t i:v3_sites){const auto& l=p.launches[i];layers.insert(std::stoi(l.label.substr(4)));ops.insert(l.op);
      require(!l.op.starts_with("qsa")&&l.op!="lookup"&&l.op!="begin"&&l.op!="commit"&&l.op!="handoff"&&l.op!="handoff_result","V3 moved layer must be position-free GDN");
      for(const auto& x:l.outputs)if(x!="streams"&&x!="error")priv.insert(x);}
    std::set<int> expected;for(int k=v3_first;k<v3_end;++k)expected.insert(k);
    require(layers==expected&&ops.count("gdn")&&ops.count("conv"),"V3 moved layers must be exactly the GDN layers 24-25 (mini: 2)");
    for(size_t i:v3_sites){const auto& l=p.launches[i];
      for(const auto& x:l.inputs)require(priv.count(x)||shared.count(x),"V3 moved layer reads a buffer outside its island: "+x);}
    for(size_t i=0;i<p.launches.size();++i){if(std::find(v3_sites.begin(),v3_sites.end(),i)!=v3_sites.end())continue;const auto& l=p.launches[i];
      for(const auto& x:l.inputs)require(!priv.count(x),"rank-0 half reads a V3 private buffer: "+x);
      for(const auto& x:l.outputs)require(!priv.count(x),"rank-0 half writes a V3 private buffer: "+x);}
    const auto& last=p.launches[v3_sites.back()];
    require(last.label=="blk."+std::to_string(v3_end-1)+".ffn.combine"&&std::find(last.outputs.begin(),last.outputs.end(),"streams")!=last.outputs.end(),"V3 boundary must end with the layer-25 residual stream");
    require(v3_private.empty()||v3_private==priv,"V3 private set is a load-time constant");v3_private=std::move(priv);
  }
