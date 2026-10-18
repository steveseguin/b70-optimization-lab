// CPU census fixture only: audit production captures for every physical pair.
static void binding131(Engine& e) {
 if(e.a.rank!=0)return;
 const int pairs=e.miss_banks()?6:2;
 std::set<std::pair<int,int>> seen;
 unsigned checked=0;
 for(int i=0;i<pairs;++i){
  if(e.miss_banks())require(seen.emplace(e.active_bank,e.spare_bank).second,"duplicate bank pair");
  for(int position:{0,33,4095,0}) {
   e.admit_position(position);
   for(const auto& l:e.p.launches)if(l.op=="gdn"||l.op=="conv") {
    const auto& p=e.prepared.at(&l);const auto& name=l.outputs.at(1);
    const auto active=e.buffers[0].at(name).id,dest=e.state_spares.at(name);
    const auto input=std::find(l.inputs.begin(),l.inputs.end(),name)-l.inputs.begin();
    require(p.bindings.at(input)==active&&p.bindings.at(p.spec.ni+1)==dest&&active!=dest,"logical bank binding");
    if(l.op=="gdn"){
     auto b=p49drec::recurrence_bindings(p.spec,p.bindings);
     require(b.ids[5]==active&&b.ids[7]==dest,"production recurrence source/destination");
    }
    bool reads=false,writes=false;
    for(const auto& command:e.issue_sites.at(&l-e.p.launches.data()).commands){
     require(command.ids.size()==command.pointers.size(),"capture pointer extent");
     for(size_t j=0;j<command.ids.size();++j){
      const auto id=command.ids[j];
      require(command.pointers[j]==e.dev(0).arena.row(id).pointer,"captured pointer identity");
      reads|=id==active;writes|=id==dest;
      if(e.miss_banks())require(id!=e.state_reserves.at(name),"private reserve entered command");
     }
    }
    require(reads&&writes,"captured command lost recurrent bank");++checked;
   }
  }
  if(e.miss_banks()){if(i%2==0)e.rotate_spare_bank();else e.swap_state_banks();}
  else e.swap_state_banks();
 }
 e.bank_parity=0;
 require(checked==unsigned(pairs*4*37),"production bank audit coverage");
 if(e.miss_banks())require(e.active_bank==0&&e.spare_bank==1,"bank audit did not return to initial pair");
 std::ofstream out(e.a.output/"binding131.json");out<<"{\"passed\":true,\"pairs\":"<<pairs<<",\"checks\":"<<checked<<"}";
}
