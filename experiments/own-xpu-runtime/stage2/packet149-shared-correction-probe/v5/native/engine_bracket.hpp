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
      if(key!="probe")
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
      domain(selection->choices,"probe",{"off","xchg"});
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
    sealed_selection=std::move(next);a.selection=selection;a.selection_sha256=digest;
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
