// Copy-forward of packet98c's quiescent switch, narrowed to the one-card ABI.
// No weight allocation, layout conversion, cache eviction or model reload.
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
    for(const auto& [name,bank]:expert_banks) {
      const auto& row=devices.at(0)->arena.row(bank.host);
      out<<"pinned:"<<name<<':'<<bank.host<<':'<<row.bytes<<':'<<uintptr_t(row.pointer)<<':'<<row.live<<'\n';
    }
    return out.str();
  }
  std::string bracket_arena_hash(bool weights_only=false) const {
    const auto text=bracket_arena_descriptors(weights_only);
    return hash(std::vector<uint8_t>(text.begin(),text.end()));
  }
  static void bracket_domain(const p49d::Selection& next) {
    require(next.choices.size()==4&&next.choices.at("down")=="down-tile16"&&
            next.choices.at("hc")=="production","bracket storage/unsupported choice differs: reload required");
    require(next.choices.at("route")=="route-exp32-rank4"&&next.choices.at("recurrence")=="rows4-shared","frozen tile16 arithmetic required");
  }
  void bracket_select(const fs::path& selection,const std::string& digest,const std::string& hc="production") {
    require(hc=="production"||hc=="p60fusion","HC dimension");
    require(!maintenance.running,"HC switch during compute refused");
    guard();drain();cache_quiesce();verify_configuration();
    require(!poisoned&&!integer(0,"error"),"bracket cannot erase target failure");
    require(a.cards==1&&a.rank<0&&!a.mtp&&a.memory=="resident"&&!a.legacy&&bank_parity==0,
            "bracket requires plain single-card prepared path");
    p49d::Selection next;next.load(selection.string(),digest);
    bracket_domain(next);bracket_domain(sealed_selection);
    const auto before=bracket_arena_hash();
    a.hc=hc;
    sealed_selection=std::move(next);a.selection=selection;a.selection_sha256=digest;
    prepared.clear();alternate_prepared.clear();issue_sites.clear();alternate_issue_sites.clear();matrices.clear();
    p=::plan(w,a);index_plan();
    context_extent=alternate_context_extent=32;capacity_reprepares=0;
    prepare_plan();prepare_commands();
    require(bank_parity==0&&before==bracket_arena_hash(),"bracket changed loaded arena descriptors");
    verify_configuration();
  }
