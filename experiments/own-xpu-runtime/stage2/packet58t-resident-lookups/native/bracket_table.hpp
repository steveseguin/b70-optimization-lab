struct BracketView {std::string label;fs::path selection;std::string digest;int resident=0;};
static std::vector<BracketView> bracket_table(const Options& a) {
  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256,a.resident_lookups?1:0}};
  require(!a.suite_inputs.empty()&&!a.mtp&&a.cards==1&&a.rank<0&&a.memory=="resident"&&!a.legacy,"bracket requires resident single-card suite");
  require(a.mini||(a.tokens==128&&a.context==4096&&a.retain_steps.ranges.empty()),"fixed 128-token context4096 screen");
  std::ifstream f(a.bracket_inputs);std::vector<BracketView> views;BracketView v;
  while(f>>v.label>>v.selection>>v.digest>>v.resident) {
    require(views.size()<3&&v.selection.is_absolute(),"bounded absolute bracket selection");
    p49d::Selection selection;selection.load(v.selection.string(),v.digest);Engine::bracket_domain(selection);
    require(selection.choices.at("route")=="route-exp32-rank4"&&selection.choices.at("recurrence")=="rows4-shared","tile16-only bracket required");
    views.push_back(v);
  }
  require(f.eof()&&views.size()==3,"three complete views required");
  const char* labels[]={"A0","B0","A1"};
  for(size_t i=0;i<3;++i)require(views[i].label==labels[i]&&views[i].resident==int(i==1)&&views[i].digest==a.selection_sha256&&views[i].selection==a.selection,"bracket storage/order/selection identity");
  return views;
}
