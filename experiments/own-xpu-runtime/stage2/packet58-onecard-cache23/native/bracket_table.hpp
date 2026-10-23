struct BracketView {std::string label;fs::path selection;std::string digest,maintenance,capacity,hc;bool resident=false;};
static std::vector<BracketView> bracket_table(const Options& a) {
  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.cache_maintenance,a.cache_cap,a.hc,a.resident_lookups}};
  require(!a.suite_inputs.empty()&&!a.mtp&&a.cards==1&&a.rank<0&&a.memory=="resident"&&!a.legacy&&a.miss_path=="zero-copy",
          "capacity bracket requires resident single-card zero-copy suite");
  require(a.mini||((a.tokens==64||a.tokens==128)&&a.context==4096&&a.retain_steps.ranges.empty()),"fixed smoke/bracket dimensions");
  std::ifstream f(a.bracket_inputs);std::vector<BracketView> views;std::string line;
  while(std::getline(f,line)) {
    std::istringstream row(line);BracketView v;std::string extra;
    require(bool(row>>v.label>>v.selection>>v.digest>>v.maintenance>>v.capacity>>v.hc)&&!(row>>extra),"complete six-field bracket row");
    require(views.size()<5&&v.selection.is_absolute(),"bounded absolute bracket selection");
    p49d::Selection selection;selection.load(v.selection.string(),v.digest);Engine::bracket_domain(selection);
    require(v.digest==a.selection_sha256&&v.selection==a.selection,"immutable tile16 identity");
    require(v.maintenance==a.cache_maintenance,"maintenance fixed throughout capacity bracket");
    require(v.capacity=="max"||v.capacity=="max23","cache capacity dimension");
    require(v.hc=="spin-kio","kernel foreground io fixed throughout the capacity bracket");v.resident=true;
    require(!a.wait_policy_supplied||a.wait_policy=="spin","wait policy conflicts with bracket view");
    require(!a.foreground_io_supplied,"bracket selects foreground io per view");
    views.push_back(v);
  }
  require(f.eof()&&(views.size()==1||views.size()==5),"complete smoke or five-view bracket required");
  if(views.size()==1) {
    require((a.mini||a.tokens==64)&&views[0].label=="S0"&&views[0].capacity=="max23"&&views[0].hc=="spin-kio","fixed maximum smoke");
  } else {
    require(a.mini||a.tokens==128,"128-token bracket required");
    const char* labels[]={"A0","B0","A1","B1","A2"};
    for(size_t i=0;i<5;++i)require(views[i].label==labels[i]&&views[i].capacity==(i%2?"max23":"max")&&views[i].hc=="spin-kio","max/max23 capacity bracket order");
  }
  return views;
}
