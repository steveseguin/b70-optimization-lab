// Compile against the generated actual Engine TU. Public entry below never
// creates Device/Engine, touches tensor payloads, or invokes model execution.
#include "build/private/source/diet-native/native-src/entry-main.cpp"
int main(int argc,char**argv){try{
  require(argc==2,"use --synthetic or --headers");const std::string mode=argv[1];
  require(mode=="--synthetic"||mode=="--headers","preflight mode");
  Options a;a.gsq_packed=true;a.cards=1;a.rank=0;a.draft_rank=0;a.context=4096;a.memory="resident";
  a.mini=mode=="--synthetic";a.pipeline_mini=a.mini;
  a.plan=gsq::bound::placement_path;a.auth=gsq::bound::auth_path;a.model=gsq::bound::model_root;
  Weights w(a);auto p=gsq_build_plan(w,a);size_t gemv=0,routed=0,lookup=0,controls=0;
  for(const auto&l:p.launches){require(l.op!="expert_gate_up"&&!p39::tagged(l),"preflight unfused graph");
    if(l.op=="gemv"||l.op=="routed_gemv"){
      auto v=selected_variant(w,a,p,l);require(v==(!a.mini&&l.weights[0]=="output.weight"?6:0),"preflight variant policy");
      if(l.op=="gemv")++gemv;else ++routed;
    }else if(l.op=="lookup")++lookup;else controls+=l.weights.size();
  }
  require(gemv&&routed&&lookup&&controls,"preflight nonvacuous graph");
  if(!a.mini)require(w.directory.size()==1224&&p.g.h==2560&&p.g.vocab==248320,"preflight real geometry");
  for(unsigned type:{12,13,23,42}){
    auto fmt=gsq::layout(type);std::vector<uint8_t>b(fmt.bytes,0x55);b[0]=0;b[1]=0x38;
    for(size_t i=0;i<fmt.elements;++i)require(std::bit_cast<uint32_t>(iq3::decode(static_cast<iq3::Type>(type),b.data(),i))==std::bit_cast<uint32_t>(gsq::element_unchecked(type,b.data(),i)),"private decoder bridge");
  }
  std::cout<<"{\"passed\":true,\"mode\":"<<ownrt::quote(mode)<<",\"tensors\":"<<w.directory.size()<<",\"launches\":"<<p.launches.size()<<",\"gemv\":"<<gemv<<",\"routed\":"<<routed<<",\"lookup\":"<<lookup<<",\"control_occurrences\":"<<controls<<",\"device_constructed\":false,\"payload_read\":false,\"native_model_qualified\":false}\n";
  return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
