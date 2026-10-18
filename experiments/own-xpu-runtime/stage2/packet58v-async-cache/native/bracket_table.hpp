struct BracketView {std::string label;fs::path selection;std::string digest,maintenance;};
static std::vector<BracketView> bracket_table(const Options& a) {
  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.cache_maintenance}};
  require(!a.suite_inputs.empty()&&!a.mtp&&a.cards==1&&a.rank<0&&a.memory=="resident"&&!a.legacy&&a.miss_path=="zero-copy",
          "maintenance bracket requires resident single-card zero-copy suite");
  require(a.mini||((a.tokens==64||a.tokens==128)&&a.context==4096&&a.retain_steps.ranges.empty()),"fixed smoke/bracket dimensions");
  std::ifstream f(a.bracket_inputs);std::vector<BracketView> views;BracketView v;
  while(f>>v.label>>v.selection>>v.digest>>v.maintenance) {
    require(views.size()<5&&v.selection.is_absolute(),"bounded absolute bracket selection");
    p49d::Selection selection;selection.load(v.selection.string(),v.digest);Engine::bracket_domain(selection);
    require(v.digest==a.selection_sha256&&v.selection==a.selection,"immutable tile16 identity");
    require(v.maintenance=="serial"||v.maintenance=="overlap","maintenance dimension");
    views.push_back(v);
  }
  require(f.eof()&&(views.size()==1||views.size()==5),"complete smoke or five-view bracket required");
  if(views.size()==1) {
    require((a.mini||a.tokens==64)&&views[0].label=="S0"&&views[0].maintenance=="overlap","fixed overlap smoke");
  } else {
    require(a.mini||a.tokens==128,"128-token bracket required");
    const char* labels[]={"A0","B0","A1","B1","A2"};
    for(size_t i=0;i<5;++i)require(views[i].label==labels[i]&&views[i].maintenance==(i%2?"overlap":"serial"),"serial/overlap bracket order");
  }
  return views;
}
