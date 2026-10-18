// Compile against the exact generated production grouping body, CPU metadata only.
#define main unused_plan_probe_entry
#include "build/fix6/after.cpp"
#undef main
int main(int argc,char**argv){
 require(argc==2,"dispatch path required");
 Weights w;w.directory=flash::directory_from_loader(iq3::read_plan(std::string(FIX6_PLAN)));
 packet26::dispatch.load(argv[1]);
 for(auto&[key,value]:packet26::dispatch.fusions)if(value=="p39.epilogue")value="packet18";
 for(auto key:{"small.hc","small.gdn.ab","small.ffn"})packet26::dispatch.fusions[key]="round2";
 Options a;auto original=split(plan(w,a),0,false,0);
 Probe good(w,a,original);require(good.small_groups.size()>40,"complete primitive tuples must fuse");
 auto first=std::find_if(original.launches.begin(),original.launches.end(),[](const auto&l){return l.label.ends_with(".router");});
 require(first!=original.launches.end(),"router required");
 auto prefix=first->label.substr(0,first->label.size()-6);auto label=prefix+"shexpup";
 unsigned checks=1;
 auto test=[&](const std::string&name,auto mutate,bool reject){
  auto p=original;mutate(p);bool refused=false;std::string error;
  try{Probe probe(w,a,std::move(p));if(!reject)require(probe.small_groups.size()+1==good.small_groups.size(),"only unavailable group skipped");}
  catch(const std::exception&e){refused=true;error=e.what();}
  require(refused==reject,"mutation verdict: "+name+" "+error);++checks;
  std::cout<<"{\"case\":\""<<name<<"\",\"refused\":"<<(refused?"true":"false")<<",\"error\":\""<<error<<"\"}\n";
 };
 auto member=[&](auto&p)->flash::Launch&{return *std::find_if(p.launches.begin(),p.launches.end(),[&](const auto&l){return l.label==label;});};
 test("missing",[&](auto&p){std::erase_if(p.launches,[&](const auto&l){return l.label==label;});},false);
 test("other-card",[&](auto&p){member(p).card=1;},true);
 test("different-input",[&](auto&p){member(p).inputs[0]="different";},true);
 test("non-gemv",[&](auto&p){member(p).op="norm";},true);
 test("duplicate",[&](auto&p){p.launches.push_back(member(p));},true);
 test("wrong-shape",[&](auto&p){member(p).shape[1]++;},true);
 test("input-overwritten",[&](auto&p){auto i=std::find_if(p.launches.begin(),p.launches.end(),[&](const auto&l){return l.label==prefix+"router";});auto x=*i;x.op="mutation";x.label="mutation";x.outputs={i->inputs[0]};p.launches.insert(i+1,x);},true);
 test("early-output-read",[&](auto&p){auto output=member(p).outputs[0];auto i=std::find_if(p.launches.begin(),p.launches.end(),[&](const auto&l){return l.label==prefix+"router";});auto x=*i;x.op="mutation";x.label="mutation";x.inputs={output};x.outputs={"unused"};p.launches.insert(i+1,x);},true);
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"complete_groups\":"<<good.small_groups.size()<<",\"device_executed\":false}\n";
}
