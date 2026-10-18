// Packet142: immutable copies in class consumer order, built once before captures.
// Allocation order is a hypothesis; allocator physical adjacency is not asserted.
  std::map<std::string,Allocation> class_original,class_ordered;
  size_t class_copy_bytes=0;
  std::string current_class_bank;
  std::map<std::string,size_t> class_bytes;
  std::map<std::string,std::vector<std::string>> class_names143;
  static constexpr size_t class_copy_budget=600ull*1024*1024;
  std::string class_capability()const{return current_class_bank;}
  bool class_site(const flash::Launch& l)const{
    const auto cls=packet26::Dispatch::class_name(l.label), bank=class_capability();
    if(bank=="expert-gate-up-order600")return l.op=="expert_gate_up";
    if(bank=="hc-gate-low-order600")return cls=="hc.a.gate"||cls=="hc.a.low"||cls=="hc.f.gate"||cls=="hc.f.low";
    if(bank=="attention-order600")return l.op=="gemv"&&(cls=="gdn.qkv"||cls=="gdn.z"||cls=="qsa.qgate"||cls=="qsa.k"||cls=="qsa.v"||cls=="attention");
    return false;
  }
  void initialize_class_layout(){
    require(a.memory=="resident","class layout requires full resident model");
    std::set<std::string> seen;
    for(const auto& dimension:{"attention_layout","expert_gate_up_layout","hc_layout"}) {
    const auto value=sealed_selection.choices.at(dimension);
    require(value=="production"||value=="order600","invalid class dimension");
    if(value=="production")continue;
    current_class_bank=std::string(dimension)=="attention_layout"?"attention-order600":std::string(dimension)=="expert_gate_up_layout"?"expert-gate-up-order600":"hc-gate-low-order600";
    class_copy_bytes=0;class_original.clear();
    // Complete consumer tuples only; budget is fixed before device results.
    for(const auto& l:p.launches){
      if(!class_site(l))continue;
      size_t bytes=0;std::vector<std::string> names;
      for(const auto& n:l.weights)if(!seen.count(n)&&weights.at(l.card).count(n)){
        names.push_back(n);bytes+=dev(l.card).arena.row(weights.at(l.card).at(n)).bytes;
      }
      if(bytes>class_copy_budget-class_copy_bytes)break;
      for(const auto& n:names){
        auto original=weights.at(l.card).at(n);const size_t count=dev(l.card).arena.row(original).bytes;
        auto replacement=allocate(l.card,"class-order:"+n,count,Category::weights,Lifetime::process);
        ownrt::CopyEngine copy(dev(l.card));for(size_t off=0;off<count;off+=32*1024*1024){guard();wait(l.card,copy.copy(replacement,off,original,off,std::min(count-off,size_t(32*1024*1024)),{}));retire_events(l.card);}
        class_original[n]=original;class_ordered[n]=replacement;class_names143[current_class_bank].push_back(n);seen.insert(n);class_copy_bytes+=count;
      }
    }
    require(!class_original.empty(),"class layout has no complete consumer tuple within budget");
    // No captures exist yet. Retire every copy before releasing the old bytes.
    drain();
    for(const auto& [n,id]:class_original)weights.at(0).at(n)=class_ordered.at(n);
    for(const auto& [n,id]:class_original)release(0,id);
    class_original.clear();
    class_bytes[current_class_bank]=class_copy_bytes;
    }
    for(const auto& [n,id]:class_ordered)weights.at(0).at(n)=id;
    std::ostringstream proof;proof<<"{\"schema\":\"packet143.relocation.v1\",\"originals_released_before_capture\":true,\"copies_drained_before_release\":true,\"budget_per_class\":"<<class_copy_budget<<",\"classes\":[";
    bool first=true;for(const auto& [bank,count]:class_bytes){proof<<(first?"":",")<<"{\"bank\":"<<ownrt::quote(bank)<<",\"bytes\":"<<count<<",\"weights\":[";first=false;bool comma=false;for(const auto& n:class_names143.at(bank)){proof<<(comma?",":"")<<ownrt::quote(n);comma=true;}proof<<"]}";}proof<<"]}";
    save(a.output/"class-layout.json",proof.str());
  }
