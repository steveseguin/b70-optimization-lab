struct BracketView {std::string label;fs::path selection;std::string digest,maintenance,capacity,hc;bool resident=false;};
static std::vector<BracketView> bracket_table(const Options& a) {
  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.cache_maintenance,a.cache_cap,a.hc,a.resident_lookups}};
  require(!a.suite_inputs.empty()&&!a.mtp&&a.cards==1&&a.rank<0&&a.memory=="resident"&&!a.legacy&&a.miss_path=="zero-copy",
          "capacity bracket requires resident single-card zero-copy suite");
  require(a.mini||((a.tokens==32||a.tokens==64||a.tokens==128)&&a.context==4096&&a.retain_steps.ranges.empty()),"fixed smoke/bracket dimensions");
  std::ifstream f(a.bracket_inputs);std::vector<BracketView> views;std::string line;
  while(std::getline(f,line)) {
    std::istringstream row(line);BracketView v;std::string extra;
    require(bool(row>>v.label>>v.selection>>v.digest>>v.maintenance>>v.capacity>>v.hc)&&!(row>>extra),"complete six-field bracket row");
    require(views.size()<6&&v.selection.is_absolute(),"bounded absolute bracket selection");
    p49d::Selection selection;selection.load(v.selection.string(),v.digest);Engine::bracket_domain(selection);
    require(v.digest==a.selection_sha256&&v.selection==a.selection,"immutable tile16 identity");
    require(v.maintenance==a.cache_maintenance,"maintenance fixed throughout capacity bracket");
    require(v.capacity=="max","fixed maximum cache");
    require(v.hc=="control"||v.hc=="no-upload"||v.hc=="no-scatter"||v.hc=="drain-only"||v.hc=="wait-split","lookup dimension");v.resident=true;
    views.push_back(v);
  }
  require(f.eof()&&(views.size()==1||views.size()==6),"complete smoke or five-view bracket required");
  if(views.size()==1) {
    require((a.mini||a.tokens==64)&&views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="control","fixed maximum smoke");
  } else {
    require(a.mini||a.tokens==32,"32-token diagnostic screen required");
    const char* labels[]={"A0","U0","S0","D0","W0","A1"};
    const char* arms[]={"control","no-upload","no-scatter","drain-only","wait-split","control"};
    for(size_t i=0;i<6;++i)require(views[i].label==labels[i]&&views[i].hc==arms[i],"fixed diagnostic order");
  }
  return views;
}
