// Packet145: immutable copies in class consumer order, built once before captures.
// Allocation order is a hypothesis; allocator physical adjacency is not asserted.
  std::map<std::string,Allocation> class_original,class_ordered;
  size_t class_copy_bytes=0;
  static constexpr size_t class_copy_budget=600ull*1024*1024;
  std::string class_capability()const{return sealed_selection.choices.at("class_layout_bank");}
  bool class_site(const flash::Launch& l)const{
    const auto cls=packet26::Dispatch::class_name(l.label), bank=class_capability();
    if(bank=="router-order600")return l.op=="gemv"&&cls=="router";
    if(bank=="gdnz-order600")return l.op=="gemv"&&cls=="gdn.z";
    return false;
  }
  void initialize_class_layout(){
    require(a.memory=="resident"&&!a.mini,"class layout requires full resident model");
    std::set<std::string> seen;
    // Complete consumer tuples only; budget is fixed before device results.
    for(const auto& l:p.launches){
      if(!class_site(l))continue;
      size_t bytes=0;std::vector<std::string> names;
      std::vector<const flash::Launch*> consumers{&l};
      if(class_capability()=="router-order600"){
        auto group=small_groups.find(&l);
        require(group!=small_groups.end()&&group->second.members.size()==4,"router requires complete fused/shared tuple");
        consumers=group->second.members;
      }
      for(const auto* consumer:consumers)for(const auto& n:consumer->weights)if(!seen.count(n)&&weights.at(l.card).count(n)){
        names.push_back(n);bytes+=dev(l.card).arena.row(weights.at(l.card).at(n)).bytes;
      }
      if(bytes>class_copy_budget-class_copy_bytes)break;
      for(const auto& n:names){
        auto original=weights.at(l.card).at(n);const size_t count=dev(l.card).arena.row(original).bytes;
        auto replacement=allocate(l.card,"class-order:"+n,count,Category::weights,Lifetime::process);
        ownrt::CopyEngine copy(dev(l.card));for(size_t off=0;off<count;off+=32*1024*1024){guard();wait(l.card,copy.copy(replacement,off,original,off,std::min(count-off,size_t(32*1024*1024)),{}));retire_events(l.card);}
        class_original[n]=original;class_ordered[n]=replacement;seen.insert(n);class_copy_bytes+=count;
      }
    }
    require(!class_ordered.empty(),"class layout has no complete consumer tuple within budget");
    class_select(sealed_selection.choices.at("class_layout"));
    std::ostringstream proof;proof<<"{\"class_layout_bank\":"<<ownrt::quote(class_capability())<<",\"bytes\":"<<class_copy_bytes<<",\"budget\":"<<class_copy_budget<<",\"weights\":[";
    bool first=true;for(const auto& [n,id]:class_ordered){proof<<(first?"":",")<<ownrt::quote(n);first=false;}proof<<"]}";
    save(a.output/"class-layout.json",proof.str());
  }
  void class_select(const std::string& value){
    require(value=="production"||value==class_capability(),"class layout outside loaded bank");
    for(const auto& [n,id]:class_original)weights.at(0).at(n)=value=="production"?id:class_ordered.at(n);
  }
