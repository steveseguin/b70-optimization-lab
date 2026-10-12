#pragma once
// Included after packet29 main.cpp. Production planning and all submissions stay
// upstream. Tiny planning uses its exact fusion source block (fusion-source.json).
namespace fixture34 {
inline std::string canonical(const std::string& n) {
 if(!n.starts_with("blk."))return n;
 auto dot=n.find('.',4);require(dot!=std::string::npos,"canonical layer name");
 int layer=std::stoi(n.substr(4,dot-4));
 return "blk."+std::to_string(24+layer%4)+n.substr(dot);
}
inline flash::Plan fuse_tiny(flash::Plan p,const Options& a) {
  std::vector<flash::Launch> fused;
  for (size_t i=0;i<p.launches.size();++i) {
    auto l=p.launches[i];
    if(l.op=="routed_gemv" && l.weights[0].find("ffn_gate_exps")!=std::string::npos) {
      require(i+2<p.launches.size(),"gate/up schedule");
      const auto& up=p.launches[i+2];
      require(up.op=="routed_gemv" && up.inputs==l.inputs && up.shape==l.shape &&
              up.weights[0].find("ffn_up_exps")!=std::string::npos,"gate/up dependency");
      l.op="expert_gate_up";
      l.weights.push_back(up.weights[0]);
      l.outputs.insert(l.outputs.end(),up.outputs.begin(),up.outputs.end());
      fused.push_back(l);fused.push_back(p.launches[i+1]);i+=2;
    } else fused.push_back(l);
  }
  p.launches=std::move(fused);
  // Optional arithmetic-preserving specialised fusions. The default schedule is
  // byte-for-byte packet18. The route consumer uses the single source row.
  std::vector<flash::Launch> specialised;
  std::map<std::string,std::string> routed_source;
  for(size_t i=0;i<p.launches.size();++i) {
    auto l=p.launches[i];
    if(a.nongemv=="parallel" && l.op=="route" && i+1<p.launches.size() && p.launches[i+1].op=="expert_gather" &&
       packet26::dispatch.fusion_for("route+gather")) {
      const auto& gather=p.launches[++i];
      l.outputs.push_back(gather.outputs[0]);l.outputs.push_back(gather.outputs[1]);
      routed_source[gather.outputs[2]]=gather.inputs[1];
    }
    if(l.op=="expert_gate_up" && routed_source.count(l.inputs[0]))l.inputs[0]=routed_source.at(l.inputs[0]);
    if(a.nongemv=="parallel" && l.op=="hc_combine" && i+1<p.launches.size()) {
      const auto& next=p.launches[i+1];
      auto fusion_class=l.label;if(fusion_class.starts_with("blk."))fusion_class=fusion_class.substr(fusion_class.find('.',4)+1);
      if(packet26::dispatch.fusion_for(fusion_class+"+norm") && next.op=="norm" && next.card==l.card && next.inputs==l.outputs) {
        l.outputs.insert(l.outputs.end(),next.outputs.begin(),next.outputs.end());
        l.weights=next.weights;l.parameter=next.parameter;++i;
      }
    }
    specialised.push_back(std::move(l));
  }
  p.launches=std::move(specialised);
  return p;
}
inline flash::Plan make_plan(Weights& w,Options& a,bool tiny) {
 require(w.mini&&!w.model,"fixture requires no model owner");
 flash::Plan p;
 a.cards=2;a.mini=tiny;a.first=false;a.nongemv="parallel";
 if(tiny) {
  auto g=Geometry::tiny();g.context=a.context;
  std::vector<bool> full(48);for(int i=0;i<48;++i)full[i]=(i%4==3);
  p=flash::Builder(g).build(full);
  w.synthesize(p);
  p=fuse_tiny(std::move(p),a);
 }else{
  std::ifstream f(fs::path(__FILE__).parent_path()/"directory.tsv");
  require(bool(f),"synthetic metadata snapshot missing");
  w.directory=flash::read_directory(f);
  p=::plan(w,a);
 }
 std::erase_if(p.launches,[](const flash::Launch& l){
  if(l.label=="begin.1"||l.label=="commit.final")return false;
  if(!l.label.starts_with("blk."))return true;
  int layer=std::stoi(l.label.substr(4));return layer<24||layer>=48;
 });
 // Preserve layer47 combine+final.norm exactly as packet29 submits it.
 // This boundary normalization adds an output, not a separate kernel launch.
 for(auto& l:p.launches){l.card=0;l.source_card=-1;}
 std::set<std::string> used{"error","position","active","streams"};
 for(const auto& l:p.launches){used.insert(l.inputs.begin(),l.inputs.end());used.insert(l.outputs.begin(),l.outputs.end());}
 std::erase_if(p.buffers,[&](const auto& b){return !used.count(b.name);});
 for(auto& b:p.buffers)b.card=0;
 int layers=0,gdn=0,qsa=0;
 for(const auto& l:p.launches){
  if(l.label.ends_with(".hc.a.gate"))++layers;
  if(l.op=="gdn")++gdn;if(l.op=="qsa_prepare")++qsa;
  for(const auto& n:l.weights) {
   const auto& t=w.directory.at(n);const auto& c=w.directory.at(canonical(n));
   require(t.grid==c.grid&&t.shape==c.shape&&t.bytes==c.bytes,"four-set weight alias mismatch: "+n);
  }
 }
 require(gdn==18&&qsa==6,"half requires18 GDN and6 QSA layers");
 require(!p.launches.empty()&&p.launches.front().op=="begin"&&p.launches.back().op=="commit","half boundary");
 return p;
}
inline uint64_t seed_for(const std::string& n) {
 uint64_t v=0x34d0cafe20261011ull;
 for(unsigned char c:canonical(n)){v^=c;v*=1099511628211ull;}return v;
}
inline uint64_t mix(uint64_t x) {
 x^=x>>30;x*=0xbf58476d1ce4e5b9ull;x^=x>>27;x*=0x94d049bb133111ebull;return x^(x>>31);
}
inline std::vector<uint8_t> generated(const flash::Tensor& t,size_t off,size_t n) {
 flash::validate_descriptor(t);
 require(n&&n<=4u*1024*1024&&off<=t.bytes&&n<=t.bytes-off,"generator bounded extent");
 auto type=flash::grid_type(t.grid);auto fmt=iq3::layout(type);
 std::vector<uint8_t> out(n);uint64_t seed=seed_for(t.name);
 if(type==iq3::Type::F32||type==iq3::Type::BF16){
  const size_t width=type==iq3::Type::F32?4:2;
  require(off%width==0&&n%width==0,"scalar generator alignment");
  for(size_t j=0;j<n;j+=width){
   uint64_t h=mix(seed+(off+j)/width);
   float x=float(int(h%33)-16)/8192.f;
   if(t.name.find("norm")!=std::string::npos)x+=1.f;
   if(ends(t.name,"ssm_a"))x=-.5f-std::abs(x);
   if(width==4)std::memcpy(out.data()+j,&x,4);
   else{uint16_t b=iq3::bf16_bits(x);std::memcpy(out.data()+j,&b,2);}
  }
 }else{
  // Thirty-two distinct valid blocks repeat throughout each tensor. All bit
  // patterns in integer fields are valid; half scales are finite small values.
  std::array<std::array<uint8_t,256>,32> blocks{};
  require(fmt.bytes<=256,"quant block bound");
  for(size_t k=0;k<blocks.size();++k){
   for(size_t j=0;j<fmt.bytes;++j)blocks[k][j]=uint8_t(mix(seed+k*257+j));
   size_t scale=type==iq3::Type::Q6_K?208:0;
   uint16_t half=type==iq3::Type::Q6_K?uint16_t(0x0010+(k%4)):uint16_t(0x0400+(k%4)*32);
   blocks[k][scale]=uint8_t(half);blocks[k][scale+1]=uint8_t(half>>8);
  }
  for(size_t j=0;j<n;){
   size_t absolute=off+j,within=absolute%fmt.bytes;
   size_t take=std::min(n-j,size_t(fmt.bytes)-within);
   std::memcpy(out.data()+j,blocks[(absolute/fmt.bytes)%32].data()+within,take);j+=take;
  }
 }
 return out;
}
inline size_t weight_bytes(const Weights& w,const flash::Plan& p) {
 std::set<std::string> unique;size_t bytes=0;
 for(const auto& l:p.launches)for(const auto& n:l.weights)if(unique.insert(canonical(n)).second)bytes+=w.directory.at(n).bytes;
 return bytes;
}

inline size_t generator_gate(const Weights& w,const flash::Plan& p) {
 size_t checks=0;std::set<std::string> visited;
 for(const auto& l:p.launches)for(const auto& n:l.weights){
  const auto& t=w.directory.at(n);const auto& c=w.directory.at(canonical(n));
  auto fmt=iq3::layout(flash::grid_type(t.grid));
  size_t bytes=std::min(t.bytes,size_t(fmt.bytes)*32);
  auto a=generated(t,0,bytes),b=generated(c,0,bytes);
  require(a==b,"canonical generated bytes disagree");++checks;
  if(visited.insert(c.name).second){
   for(size_t k=0;k<(bytes/fmt.bytes)*fmt.elements;++k)
    require(std::isfinite(iq3::element(flash::grid_type(t.grid),a.data(),k)),"nonfinite generated weight");
   ++checks;
   if(bytes>size_t(fmt.bytes)){
    auto second=generated(t,fmt.bytes,bytes-fmt.bytes);
    require(std::equal(second.begin(),second.end(),a.begin()+fmt.bytes),"chunk-independent generator");++checks;
   }
  }
 }
 // The four rotated expert banks must be different bytes even though their
 // admitted format and dimensions coincide. This catches an ignored seed.
 std::set<std::vector<uint8_t>> distinct;
 for(int layer=24;layer<28;++layer){
  const auto& t=w.directory.at("blk."+std::to_string(layer)+".ffn_gate_exps.weight");
  auto fmt=iq3::layout(flash::grid_type(t.grid));
  distinct.insert(generated(t,0,std::min(t.bytes,size_t(fmt.bytes)*32)));
 }
 require(distinct.size()==4,"four weight sets have identical bytes");++checks;
 return checks;
}
} // namespace fixture34
