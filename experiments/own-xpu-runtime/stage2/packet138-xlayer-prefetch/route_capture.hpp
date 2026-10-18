// Included inside Engine. Diagnostic copies on the existing ordered queue only.
// Four HC streams are retained without averaging or changing model arithmetic.
static constexpr size_t capture_steps=48, capture_layers=24;
static constexpr size_t capture_route_bytes=120, capture_hidden_bytes=5120;
static constexpr size_t capture_residual_bytes=20480, capture_logits_bytes=1024;
static constexpr size_t capture_stride=120+5120+20480+1024;
static constexpr size_t route_capture_bytes=capture_steps*capture_layers*capture_stride;
std::vector<Allocation> route_capture_buffers;
std::array<int,capture_steps> route_capture_positions{},route_capture_tokens{};
std::array<bool,capture_steps> route_capture_valid{};
uint32_t route_capture_mask=0,capture_router_mask=0,capture_residual_mask=0;
void capture_begin(){route_capture_mask=0;capture_router_mask=0;capture_residual_mask=0;}
void capture_copy(const std::string& name,size_t offset,size_t bytes){
  auto source=buffers[0].at(name);
  require(source.n*flash::scalar_bytes(source.type)==bytes,"capture source extent: "+name);
  ownrt::CopyEngine copy(dev(0));
  tail=copy.copy(route_capture_buffers.at(0),offset,source.id,0,bytes,{});
}
void capture_down(const flash::Launch& l,int fixture) {
  if(fixture<=0||fixture>int(capture_steps)||!l.label.starts_with("blk."))return;
  require(a.cards==1&&a.rank>=0&&a.rank<2,"capture requires TP2 rank");
  int layer=std::stoi(l.label.substr(4));
  require(layer>=a.rank*24&&layer<(a.rank+1)*24,"capture layer ownership");
  size_t local=layer%24,offset=(size_t(fixture-1)*24+local)*capture_stride;
  uint32_t bit=1u<<local;
  auto suffix=[&](const std::string&s){return l.label.size()>=s.size()&&l.label.compare(l.label.size()-s.size(),s.size(),s)==0;};
  if(suffix(".router")){
    require(l.op=="gemv"&&!(capture_router_mask&bit),"duplicate/wrong router site");
    capture_copy(l.inputs.at(0),offset+120,5120);
    capture_copy(l.outputs.at(0),offset+120+5120+20480,1024);
    capture_router_mask|=bit;
  }else if(l.op=="routed_gemv"&&!l.weights.empty()&&l.weights[0].find("ffn_down_exps")!=std::string::npos){
    require(!(route_capture_mask&bit),"duplicate target down in half");
    capture_copy(l.inputs.at(1),offset,120);route_capture_mask|=bit;
  }else if(suffix(".ffn.combine")){
    require(l.op=="hc_combine"&&!(capture_residual_mask&bit),"duplicate/wrong residual site");
    capture_copy("streams",offset+120+5120,20480);capture_residual_mask|=bit;
  }
}
void capture_accept(int fixture,int position,int token,bool cancelled) {
  if(fixture<=0||fixture>int(capture_steps))return;
  require(!cancelled&&route_capture_mask==0xffffff&&capture_router_mask==0xffffff&&capture_residual_mask==0xffffff,
          "incomplete accepted capture");
  require(!route_capture_valid.at(fixture-1),"duplicate accepted target step");
  route_capture_valid[fixture-1]=true;
  route_capture_positions[fixture-1]=position;route_capture_tokens[fixture-1]=token;
}
void capture_flush() {
  require(std::all_of(route_capture_valid.begin(),route_capture_valid.end(),[](bool v){return v;}),"capture requires 48 accepted steps");
  auto path=a.output/"capture.bin";require(!fs::exists(path),"capture output already exists");
  auto raw=readback(0,route_capture_buffers.at(0),route_capture_bytes);
  std::ofstream binary(path,std::ios::binary);binary.write(reinterpret_cast<const char*>(raw.data()),raw.size());
  binary.close();require(bool(binary),"capture write failed");
  std::ostringstream meta;
  meta<<"{\"schema\":\"packet138.rank-capture.v1\",\"diagnostic_only\":true,\"rank\":"<<a.rank
      <<",\"bytes\":"<<raw.size()<<",\"stride\":"<<capture_stride<<",\"sha256\":"<<ownrt::quote(hash(raw))<<",\"steps\":[";
  for(int i=0;i<int(capture_steps);++i)meta<<(i?",":"")<<"{\"fixture\":"<<i+1<<",\"position\":"<<route_capture_positions[i]<<",\"input_token\":"<<route_capture_tokens[i]<<"}";
  meta<<"]}";save(a.output/"capture.json",meta.str());
}
