// Included inside Engine. Diagnostic copies only; no target arithmetic changes.
// One fixed slot per target output step and local layer, overwritten on redo.
static constexpr size_t route_capture_bytes=64*24*10*12;
std::vector<Allocation> route_capture_buffers;
std::array<int,64> route_capture_positions{},route_capture_tokens{};
std::array<bool,64> route_capture_valid{};
uint32_t route_capture_mask=0;
void capture_down(const flash::Launch& l,int fixture) {
  if(fixture<=0||fixture>64||l.op!="routed_gemv"||
     l.weights.empty()||l.weights[0].find("ffn_down_exps")==std::string::npos)return;
  require(a.cards==1&&a.rank>=0&&a.rank<2,"capture requires TP2 rank");
  int layer=std::stoi(l.weights[0].substr(4));
  require(layer>=a.rank*24&&layer<(a.rank+1)*24,"capture layer ownership");
  auto source=buffers[0].at(l.inputs.at(1));
  require(source.n*flash::scalar_bytes(source.type)==120,"capture route extent");
  size_t local=layer%24;
  require(!(route_capture_mask&(1u<<local)),"duplicate target down in half");
  ownrt::CopyEngine copy(dev(0));
  tail=copy.copy(route_capture_buffers.at(0),(size_t(fixture-1)*24+local)*120,
                 source.id,0,120,{});
  route_capture_mask|=1u<<local;
}
void capture_accept(int fixture,int position,int token,bool cancelled) {
  if(fixture<=0||fixture>64)return;
  require(!cancelled&&route_capture_mask==0xffffff,"incomplete accepted route capture");
  require(!route_capture_valid.at(fixture-1),"duplicate accepted target step");
  route_capture_valid[fixture-1]=true;
  route_capture_positions[fixture-1]=position;
  route_capture_tokens[fixture-1]=token;
}
void capture_flush() {
  require(std::all_of(route_capture_valid.begin(),route_capture_valid.end(),
                     [](bool v){return v;}),"capture requires 64 accepted steps");
  // Called by command 13 after the complete request, never by HALF/enqueue.
  auto raw=readback(0,route_capture_buffers.at(0),route_capture_bytes);
  auto path=a.output/"routes.bin";
  require(!fs::exists(path),"capture output already exists");
  std::ofstream binary(path,std::ios::binary);
  binary.write(reinterpret_cast<const char*>(raw.data()),raw.size());
  binary.close();require(bool(binary),"capture write failed");
  std::ostringstream meta;
  meta<<"{\"schema\":\"packet100b.rank-routes.v1\",\"diagnostic_only\":true,"
      <<"\"rank\":"<<a.rank<<",\"bytes\":"<<raw.size()<<",\"sha256\":"<<ownrt::quote(hash(raw))
      <<",\"steps\":[";
  for(int i=0;i<64;++i)meta<<(i?",":"")<<"{\"fixture\":"<<i+1
      <<",\"position\":"<<route_capture_positions[i]<<",\"input_token\":"<<route_capture_tokens[i]<<"}";
  meta<<"]}";save(a.output/"routes.json",meta.str());
}
