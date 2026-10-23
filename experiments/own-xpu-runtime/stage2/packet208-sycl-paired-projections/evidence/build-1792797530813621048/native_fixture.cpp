#include "paired_sycl.hpp"
#include <openssl/evp.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
#include <sstream>
namespace p208 {
using ownrt::Allocation;using ownrt::Memory;using ownrt::Category;using ownrt::Lifetime;
namespace fs=std::filesystem;
inline std::string hash(const std::vector<uint8_t>& bytes) {
  unsigned char digest[32];unsigned n=0;require(EVP_Digest(bytes.data(),bytes.size(),digest,&n,EVP_sha256(),nullptr)==1 && n==32,"p208 SHA256");
  std::string s;for(auto b:digest){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;
}
inline std::vector<uint8_t> synthetic_weights(unsigned rows,unsigned seed) {
  std::vector<uint8_t> raw(size_t(rows)*2100);
  for(unsigned row=0;row<rows;++row)for(unsigned block=0;block<10;++block) {
    auto* b=raw.data()+size_t(row)*2100+block*210;
    for(unsigned i=0;i<192;++i)b[i]=uint8_t((row*17+block*31+i*13+seed)^(i>>2));
    for(unsigned i=0;i<16;++i)b[192+i]=uint8_t(int((row+block+i+seed)%7)-3);
    b[208]=0;b[209]=0x24;
  }
  return iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),2560);
}
struct Fixture {
  ownrt::Device& d;void(*guard)();Allocation slab;
  Fixture(ownrt::Device& device,void(*check)()):d(device),guard(check) {
    slab=d.arena.allocate("card0:p208:transfer",1024*1024,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
  }
  Allocation alloc(const std::string& name,size_t n) {guard();return d.arena.allocate("card0:p208:"+name,n,Memory::device,Category::scratch,Lifetime::transaction);}
  void complete(ownrt::Event event) {
    require(d.wait(event,std::chrono::seconds(30)) && d.complete(event) && d.in_flight()==0,"p208 incomplete native owner");
    d.retire_completed_events();guard();
  }
  void upload(Allocation id,const std::vector<uint8_t>& input) {
    require(input.size()==d.arena.row(id).bytes,"p208 upload extent");ownrt::CopyEngine copy(d);
    for(size_t offset=0;offset<input.size();offset+=1024*1024) {
      guard();size_t n=std::min(size_t(1024*1024),input.size()-offset);
      std::memcpy(d.arena.row(slab).pointer,input.data()+offset,n);complete(copy.copy(id,offset,slab,0,n,{}));
    }
  }
  std::vector<uint8_t> read(Allocation id) {
    std::vector<uint8_t> output(d.arena.row(id).bytes);ownrt::CopyEngine copy(d);
    for(size_t offset=0;offset<output.size();offset+=1024*1024) {
      guard();size_t n=std::min(size_t(1024*1024),output.size()-offset);complete(copy.copy(slab,0,id,offset,n,{}));
      std::memcpy(output.data()+offset,static_cast<uint8_t*>(d.arena.row(slab).pointer),n);
    }return output;
  }
  std::string run(unsigned rows) {
    auto weights=synthetic_weights(rows,rows==10240?7:19);Allocation w=alloc("weights",weights.size());upload(w,weights);
    std::array<integrated::Matrix,2> pair,serial;std::array<std::vector<uint16_t>,2> inputs;
    for(unsigned r=0;r<2;++r) {
      integrated::Matrix m{};m.type=iq3::Type::Q6_K;m.rows=rows;m.columns=2560;m.span=rows;m.w=w;
      m.x=alloc("row-input",5120);m.y=alloc("pair-output",size_t(rows)*2);m.workspace=alloc("pair-unused-workspace",4);
      pair[r]=m;m.y=alloc("serial-output",size_t(rows)*2);m.workspace=alloc("serial-validation-workspace",size_t(rows)*32);serial[r]=m;
      inputs[r].resize(2560);for(unsigned i=0;i<2560;++i)inputs[r][i]=iq3::bf16_bits(float(int((i*13+r*29)%101)-50)/128.f);
      const auto* p=reinterpret_cast<const uint8_t*>(inputs[r].data());upload(m.x,{p,p+5120});
    }
    std::vector<ownrt::PreparedCompute> pairs,refs;
    d.begin_capture(pairs);try{paired_projection(d,pair[0],pair[1],6);d.end_capture();}catch(...){d.end_capture();throw;}
    d.begin_capture(refs);try{for(const auto& m:serial)p33::submit(d,{m},"p33.dense.segment",false,6);d.end_capture();}catch(...){d.end_capture();throw;}
    require(pairs.size()==1 && pairs[0].ids==std::vector<Allocation>{w,pair[0].x,pair[1].x,pair[0].y,pair[1].y,pair[0].workspace,pair[1].workspace} && refs.size()==2,"p208 captured native ABI");
    auto captured=pair;pair[0].y=serial[0].y;pair[1].x=pair[0].x; // caller metadata cannot redirect prepared closure
    for(auto& command:refs){guard();complete(d.issue(command));}
    guard();complete(d.issue(pairs[0]));std::array<std::vector<uint8_t>,2> actual{read(captured[0].y),read(captured[1].y)};
    for(unsigned r=0;r<2;++r) {
      auto reference=read(serial[r].y);require(reference==actual[r],"p208 native serial/pair mismatch");
      std::vector<uint16_t> cpu(rows);
      for(unsigned row=0;row<rows;++row) {
        if(row%128==0)guard();float lanes[32];for(unsigned lane=0;lane<32;++lane)lanes[lane]=p33::dense_lane<iq3::Type::Q6_K,2560>(weights.data()+size_t(row)*3380,inputs[r].data(),0,2560,lane);
        cpu[row]=iq3::bf16_bits(iq3::tree32(lanes));
      }
      require(!std::memcmp(cpu.data(),actual[r].data(),actual[r].size()),"p208 CPU oracle/native mismatch");
    }
    require(actual[0]!=actual[1],"p208 row fixture vacuous");
    upload(captured[0].x,std::vector<uint8_t>(5120));guard();complete(d.issue(pairs[0]));
    require(read(captured[0].y)!=actual[0] && read(captured[1].y)==actual[1],"p208 live input/capture isolation");
    const auto* restored=reinterpret_cast<const uint8_t*>(inputs[0].data());upload(captured[0].x,{restored,restored+5120});
    upload(w,std::vector<uint8_t>(weights.size()));guard();complete(d.issue(pairs[0]));
    require(read(captured[0].y)!=actual[0] && read(captured[1].y)!=actual[1],"p208 shared weight consumption");
    std::ostringstream out;out<<"{\"rows\":"<<rows<<",\"columns\":2560,\"stride\":3380,\"variant\":6,\"passed\":true,\"pair_commands\":1,\"serial_commands\":2,\"weights_sha256\":"<<ownrt::quote(hash(weights))<<",\"output_sha256\":["<<ownrt::quote(hash(actual[0]))<<','<<ownrt::quote(hash(actual[1]))<<"],\"native_serial_cpu_exact\":true,\"live_input_weight_controls\":true}";return out.str();
  }
};
} // namespace p208

// This symbol is emitted and linked for offline review. No CLI calls it. Future
// execution requires a separately reviewed external coordinator and admission.
extern "C" __attribute__((used,noinline)) int p208_future_qualification(const char* destination,void(*guard)()) {
  using namespace p208;
  require(destination && guard,"p208 requires external admission guard");guard();
  fs::path output(destination);require(!fs::exists(output) && !fs::is_symlink(output),"p208 fresh output only");
  fs::create_directories(output);std::ofstream out(output/"result.json");require(bool(out),"p208 result open");
  std::unique_ptr<ownrt::Device> d;bool passed=false,safe=true;std::string error,receipt;std::vector<std::string> cases;
  try {
    guard();d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true));
    Fixture f(*d,guard);for(unsigned rows:{10240u,6144u})cases.push_back(f.run(rows));
    guard();auto r=d->shutdown(std::chrono::seconds(30));receipt=r.json();safe=r.safe_to_exit;require(safe && r.exit_code==0,"p208 owner teardown failed");passed=true;
  }catch(const std::exception& ex) {
    error=ex.what();if(d && receipt.empty()){try{auto r=d->shutdown(std::chrono::seconds(30));receipt=r.json();safe=r.safe_to_exit;}catch(const std::exception&){safe=false;}}
  }
  out<<"{\"schema\":\"packet208.future-native-proof.v1\",\"passed\":"<<(passed?"true":"false")<<",\"error\":"<<ownrt::quote(error)<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"cases\":[";
  for(size_t i=0;i<cases.size();++i)out<<(i?",":"")<<cases[i];out<<"],\"teardown\":"<<(receipt.empty()?"null":receipt)<<"}\n";out.flush();
  if(!safe)ownrt::hold_for_supervisor();return passed && bool(out)?0:1;
}
int main(int,char**) {
  std::cerr<<"P208 compile-only artifact: no device execution CLI; independent admission required.\n";
  return 64;
}
