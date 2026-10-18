struct BracketView {std::string label;fs::path selection;std::string digest;};
static std::vector<BracketView> bracket_table(const Options& a) {
  if(a.bracket_inputs.empty())return {{"",a.selection,a.selection_sha256}};
  require(!a.suite_inputs.empty()&&!a.mtp&&a.cards==1&&a.rank<0&&a.memory=="resident"&&!a.legacy,
          "bracket requires resident single-card suite");
  require(a.mini||(a.tokens==128&&a.context==4096&&a.retain_steps.ranges.empty()),
          "bracket is fixed 128-token context4096 screen");
  std::ifstream f(a.bracket_inputs);std::vector<BracketView> views;BracketView v;
  while(f>>v.label>>v.selection>>v.digest) {
    require(views.size()<5&&v.selection.is_absolute(),"bounded absolute bracket selection");
    p49d::Selection selection;selection.load(v.selection.string(),v.digest);Engine::bracket_domain(selection);
    views.push_back(v);
  }
  require(f.eof()&&views.size()==5,"five complete bracket views required");
  const char* labels[]={"A0","B0","A1","B1","A2"};
  for(size_t i=0;i<5;++i)require(views[i].label==labels[i],"bracket A/B/A/B/A order");
  require(views[0].digest==a.selection_sha256&&views[0].selection==a.selection&&
          views[0].digest==views[2].digest&&views[0].digest==views[4].digest&&
          views[1].digest==views[3].digest&&views[0].digest!=views[1].digest,"bracket selection identity");
  p49d::Selection control;control.load(views[0].selection.string(),views[0].digest);
  require(control.choices.at("route")=="route-exp32-rank4"&&control.choices.at("recurrence")=="rows4-shared",
          "tile16-only control required");
  return views;
}
