#pragma once
// Diagnostic sidecar only. No graph/device allocation or command ABI.
#include <array>
#include <cstdint>
#include <utility>
#include <filesystem>
#include <fstream>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>
#include <iterator>
namespace l4raw {
constexpr int rows=244;
constexpr std::array<size_t,4> extents={40960,192,192,24576};
constexpr std::array<const char*,4> fields={"conv","alpha","beta","y"};
constexpr size_t row_bytes=65920,total_bytes=row_bytes*rows;
using Bytes=std::vector<uint8_t>;
using Digest=std::function<std::string(const Bytes&)>;
inline void check(bool ok,const char*why){if(!ok)throw std::runtime_error(std::string("L4 raw history: ")+why);}
class Recorder {
 std::filesystem::path dir;Digest digest;std::ofstream payload,index;
 int next=0,last_sequence=-1,sequence=0,token=0,fixture=0,parity=0;
 bool pending=false,captured=false,initial=false,sealed=false;
 static Bytes bytes(const std::filesystem::path&p){std::ifstream f(p,std::ios::binary);check(bool(f),"open sealed input");return Bytes(std::istreambuf_iterator<char>(f),{});}
 std::string sha(const Bytes&b){auto h=digest(b);check(h.size()==64&&std::all_of(h.begin(),h.end(),[](char c){return(c>='0'&&c<='9')||(c>='a'&&c<='f');}),"digest format");return h;}
public:
 explicit Recorder(std::filesystem::path path,Digest hash):dir(std::move(path)),digest(std::move(hash)){
  check(std::filesystem::create_directory(dir),"fresh exclusive output required");
  payload.open(dir/"history.bin",std::ios::binary);index.open(dir/"rows.jsonl");check(bool(payload)&&bool(index),"open outputs");
 }
 void begin(int position,int seq,int tok,int fix,bool speculative,int bank_parity){
  check(!sealed&&!pending&&position==next&&position>=0&&position<rows,"strict row position/lifetime");
  check(!speculative&&fix==(position==rows-1?1:0),"target-only original fixture schedule");
  check(seq>last_sequence&&tok>=0&&(bank_parity==0||bank_parity==1),"row identity");
  sequence=seq;token=tok;fixture=fix;parity=bank_parity;pending=true;captured=false;
 }
 void initial_zero(const Bytes&state,const Bytes&history){
  check(pending&&next==0&&!initial,"initial identity once before row0 convolution");
  check(state.size()==3145728&&history.size()==122880,"initial extents");
  check(std::all_of(state.begin(),state.end(),[](uint8_t x){return x==0;})&&std::all_of(history.begin(),history.end(),[](uint8_t x){return x==0;}),"cold positive-zero initial state/history required");
  std::ofstream f(dir/"initial.json");f<<"{\"schema\":\"ownrt.l4-raw-initial.v1\",\"before_position\":0,\"bank_parity\":"<<parity<<",\"positive_zero\":true,\"state_bytes\":"<<state.size()<<",\"state_sha256\":\""<<sha(state)<<"\",\"history_bytes\":"<<history.size()<<",\"history_sha256\":\""<<sha(history)<<"\"}\n";
  f.flush();check(bool(f),"initial metadata write");initial=true;
 }
 void capture(const std::array<Bytes,4>&values){
  check(pending&&!captured&&initial,"capture ordering");
  // Validate every extent BEFORE appending any row bytes.
  for(size_t i=0;i<4;++i)check(values[i].size()==extents[i],"field extent");
  index<<"{\"position\":"<<next<<",\"sequence\":"<<sequence<<",\"token\":"<<token<<",\"fixture\":"<<fixture<<",\"bank_parity_before_swap\":"<<parity<<",\"fields\":{";
  size_t offset=size_t(next)*row_bytes;
  for(size_t i=0;i<4;++i){payload.write(reinterpret_cast<const char*>(values[i].data()),values[i].size());index<<(i?",":"")<<"\""<<fields[i]<<"\":{\"offset\":"<<offset<<",\"bytes\":"<<values[i].size()<<",\"sha256\":\""<<sha(values[i])<<"\"}";offset+=values[i].size();}
  index<<"}}\n";payload.flush();index.flush();check(bool(payload)&&bool(index),"row write");captured=true;
 }
 void finish_row(){
  check(pending&&captured,"row must contain exactly one completed capture");
  last_sequence=sequence;pending=false;++next;
  if(next!=rows)return;
  payload.close();index.close();check(bool(payload)&&bool(index),"output close");
  auto data=bytes(dir/"history.bin"),idx=bytes(dir/"rows.jsonl"),init=bytes(dir/"initial.json");check(data.size()==total_bytes,"complete bounded payload");
  std::ofstream seal(dir/"seal.json");seal<<"{\"schema\":\"ownrt.l4-raw-history.v1\",\"rows\":"<<rows<<",\"row_bytes\":"<<row_bytes<<",\"payload_bytes\":"<<data.size()<<",\"payload_sha256\":\""<<sha(data)<<"\",\"index_sha256\":\""<<sha(idx)<<"\",\"initial_sha256\":\""<<sha(init)<<"\",\"scope\":\"captured rows only; require successful owner termination and full final source-state neutrality separately\"}\n";
  seal.flush();check(bool(seal),"seal write");sealed=true;
 }
 bool complete()const{return sealed;}
};
} // namespace l4raw
