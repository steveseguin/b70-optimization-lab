struct BracketView {std::string label;fs::path selection;std::string digest,maintenance,capacity,hc;};
static std::vector<BracketView> bracket_table(const Options& a) {
  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.cache_maintenance,a.cache_cap,a.hc}};
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
    require(v.capacity=="max","fixed maximum cache");
    require(v.hc=="production"||v.hc=="p60fusion","HC dimension");
    views.push_back(v);
  }
  require(f.eof()&&(views.size()==2||views.size()==5),"complete smoke or five-view bracket required");
  if(views.size()==2) {
    require((a.mini||a.tokens==64)&&views[0].label=="S0"&&views[1].label=="S1"&&views[0].capacity=="max"&&views[0].hc=="p60fusion","fixed maximum smoke");
  } else {
    require(a.mini||a.tokens==128,"128-token bracket required");
    const char* labels[]={"A0","B0","A1","B1","A2"};
    for(size_t i=0;i<5;++i)require(views[i].label==labels[i]&&views[i].hc=="p60fusion","production/p60fusion bracket order");
  }
  return views;
}
