#pragma once
#ifdef OWN_RT_HOST_ONLY
namespace p207 {
// Separate synthetic entry: same Matrix admission, capture and issue as Chunks.
// No Weights, model payload, Engine constructor or selected-device execution.
inline std::vector<uint8_t> proof_weights(unsigned rows,unsigned seed) {
  constexpr unsigned k=2560,raw_stride=2100;
  std::vector<uint8_t> raw(size_t(rows)*raw_stride);
  for(unsigned r=0;r<rows;++r)for(unsigned block=0;block<10;++block) {
    auto* b=raw.data()+size_t(r)*raw_stride+block*210;
    for(unsigned i=0;i<192;++i)b[i]=uint8_t((r*17+block*31+i*13+seed)^(i>>2));
    for(unsigned i=0;i<16;++i)b[192+i]=uint8_t(int((r+block+i+seed)%7)-3);
    b[208]=0;b[209]=0x24;
  }
  return iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),k);
}
inline int pair_proof(const fs::path& output) {
  require(!fs::exists(output) && !fs::is_symlink(output),"p207 fresh proof output required");
  fs::create_directories(output);
  std::ofstream report(output/"pair-proof.json");require(bool(report),"p207 pair proof receipt");
  bool passed=false;std::string error;std::vector<std::string> cases,receipts;
  try {
    for(unsigned rows:{10240u,6144u}) {
      ownrt::Device d(std::make_unique<Host>());bool closed=false;
      try {
        auto alloc=[&](const std::string& name,size_t n){auto id=d.arena.allocate("card0:p207:"+name,n,Memory::device,Category::scratch,Lifetime::transaction);std::memset(d.arena.row(id).pointer,0,n);return id;};
        auto bytes=[&](Allocation id){const auto& r=d.arena.row(id);auto* p=static_cast<uint8_t*>(r.pointer);return std::vector<uint8_t>(p,p+r.bytes);};
        auto store=[&](Allocation id,const auto& v){require(v.size()*sizeof(v[0])==d.arena.row(id).bytes,"p207 fixture payload extent");std::memcpy(d.arena.row(id).pointer,v.data(),d.arena.row(id).bytes);};
        auto weights=proof_weights(rows,rows==10240?7:19);
        Allocation w=alloc("weights",weights.size());store(w,weights);
        std::array<Matrix,2> matrices;
        std::array<std::vector<uint16_t>,2> inputs;
        for(unsigned row=0;row<2;++row) {
          Matrix m{};m.type=iq3::Type::Q6_K;m.rows=rows;m.columns=2560;m.span=rows;m.w=w;
          m.x=alloc("x"+std::to_string(row),5120);m.y=alloc("y"+std::to_string(row),size_t(rows)*2);m.workspace=alloc("scratch"+std::to_string(row),4);
          inputs[row].resize(2560);for(unsigned i=0;i<2560;++i)inputs[row][i]=iq3::bf16_bits(float(int((i*13+row*29)%101)-50)/128.f);
          store(m.x,inputs[row]);matrices[row]=m;
        }
        const auto originals=matrices;
        std::vector<ownrt::PreparedCompute> captured;d.begin_capture(captured);
        try{paired_projection(d,matrices[0],matrices[1],6);d.end_capture();}catch(...){d.end_capture();throw;}
        require(captured.size()==1 && captured[0].ids==std::vector<Allocation>{w,matrices[0].x,matrices[1].x,matrices[0].y,matrices[1].y,matrices[0].workspace,matrices[1].workspace},"p207 actual pair capture bindings");
        auto decoy=alloc("caller-mutated-output",size_t(rows)*2);std::memset(d.arena.row(decoy).pointer,0xa5,size_t(rows)*2);
        matrices[0].y=decoy;matrices[1].x=matrices[0].x; // owned capture must not follow caller changes
        auto issue=[&]{auto event=d.issue(captured.at(0));require(d.wait(event,std::chrono::seconds(5)) && d.complete(event) && !d.in_flight(),"p207 HOST pair completion");d.retire_completed_events();};
        issue();std::array<std::vector<uint8_t>,2> actual{bytes(originals[0].y),bytes(originals[1].y)};
        for(unsigned row=0;row<2;++row) {
          std::vector<uint16_t> expected(rows);
          for(unsigned r=0;r<rows;++r) {
            float lanes[32];for(unsigned lane=0;lane<32;++lane)lanes[lane]=p33::dense_lane<iq3::Type::Q6_K,2560>(weights.data()+size_t(r)*3380,inputs[row].data(),0,2560,lane);
            expected[r]=iq3::bf16_bits(iq3::tree32(lanes));
          }
          require(actual[row].size()==expected.size()*2 && !std::memcmp(actual[row].data(),expected.data(),actual[row].size()),"p207 independent p33 BF16 mismatch");
        }
        require(actual[0]!=actual[1],"p207 distinct rows vacuous");
        const auto untouched_decoy=bytes(decoy);require(std::all_of(untouched_decoy.begin(),untouched_decoy.end(),[](auto b){return b==0xa5;}),"p207 capture followed caller metadata");
        std::memset(d.arena.row(originals[0].x).pointer,0,5120);issue();
        require(bytes(originals[0].y)!=actual[0] && bytes(originals[1].y)==actual[1],"p207 changed row not independently consumed");
        store(originals[0].x,inputs[0]);std::memset(d.arena.row(w).pointer,0,weights.size());issue();
        require(bytes(originals[0].y)!=actual[0] && bytes(originals[1].y)!=actual[1],"p207 shared weight not consumed");
        store(w,weights);issue();require(bytes(originals[0].y)==actual[0] && bytes(originals[1].y)==actual[1],"p207 live payload restore mismatch");
        auto refuses=[&](Matrix a,Matrix b,unsigned variant){bool refused=false;try{paired_projection(d,a,b,variant);}catch(const std::exception&){refused=true;}require(refused && bytes(originals[0].y)==actual[0] && bytes(originals[1].y)==actual[1] && !d.in_flight(),"p207 invalid pair mutated output");};
        auto bad=originals[1];bad.y=originals[0].y;refuses(originals[0],bad,6);
        bad=originals[1];bad.workspace=originals[0].workspace;refuses(originals[0],bad,6);
        bad=originals[1];bad.x=alloc("short-input",2);refuses(originals[0],bad,6);
        refuses(originals[0],originals[1],7);
        bad=originals[1];bad.type=iq3::Type::Q8_0;refuses(originals[0],bad,6);
        auto wrong=originals;for(auto& m:wrong)m.type=iq3::Type::Q8_0;refuses(wrong[0],wrong[1],6);
        wrong=originals;for(auto& m:wrong)m.columns=1280;refuses(wrong[0],wrong[1],6);
        wrong=originals;for(auto& m:wrong)m.rows=32;refuses(wrong[0],wrong[1],6);
        std::ostringstream row;row<<"{\"rows\":"<<rows<<",\"columns\":2560,\"variant\":6,\"stride\":3380,\"captured_operations\":1,\"passed\":true,\"outputs\":[{\"bytes\":"<<actual[0].size()<<",\"sha256\":"<<ownrt::quote(hash(actual[0]))<<",\"p33_equal\":true},{\"bytes\":"<<actual[1].size()<<",\"sha256\":"<<ownrt::quote(hash(actual[1]))<<",\"p33_equal\":true}],\"changed_row_independent\":true,\"changed_weight_consumed\":true,\"caller_metadata_immutable\":true,\"alias_extent_layout_refusals_unchanged\":true}";cases.push_back(row.str());
        auto receipt=d.shutdown(std::chrono::seconds(5));closed=true;receipts.push_back(receipt.json());require(receipt.safe_to_exit && receipt.exit_code==0,"p207 owner close");
      }catch(...) {
        if(!closed){auto receipt=d.shutdown(std::chrono::seconds(5));receipts.push_back(receipt.json());if(!receipt.safe_to_exit)ownrt::hold_for_supervisor();}throw;
      }
    }
    passed=true;
  }catch(const std::exception& e){error=e.what();}
  report<<"{\"schema\":\"packet207.pair-proof.v1\",\"passed\":"<<(passed?"true":"false")<<",\"device_executed\":false,\"model_executed\":false,\"backend\":\"existing HOST_ONLY simulated event backend\",\"error\":"<<ownrt::quote(error)<<",\"cases\":[";
  for(size_t i=0;i<cases.size();++i)report<<(i?",":"")<<cases[i];report<<"],\"teardown\":[";
  for(size_t i=0;i<receipts.size();++i)report<<(i?",":"")<<receipts[i];report<<"]}\n";report.flush();require(bool(report),"p207 pair proof write");return passed?0:1;
}
} // namespace p207
#endif
