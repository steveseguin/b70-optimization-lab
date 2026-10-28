// CPU-only synthetic GGUF fixture. Uses actual loader + exact extracted Weights
// methods. Does not load any model asset or contact a device. UNCOMPILED.
#include "stage2/packet2/loader/gguf.hpp"
#include "gsq-rco-iq3s/integration/build/private/additive/device_formats.hpp"
#include <bit>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <sys/stat.h>
#include <vector>
namespace fs=std::filesystem;
void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
namespace ownrt {std::string quote(const std::string& s){return "\""+s+"\"";}}
struct Entry {std::string name,component;size_t bytes;};
struct LookupFixture {
 bool mini=false;std::unique_ptr<iq3::Model> model;
 std::map<std::string,Entry> directory;
 std::map<std::string,std::vector<uint8_t>> synthetic;
 uint64_t read_bytes=0;size_t max_read=0;std::string residency;
 std::map<std::string,std::unique_ptr<iq3::Slice>> lookup_mappings;
 std::map<std::string,std::pair<std::unique_ptr<uint8_t[]>,size_t>> lookup_copies;
 #include "weights_methods.inc"
};
void number(std::vector<uint8_t>& b,uint64_t x,unsigned bytes){for(unsigned i=0;i<bytes;++i)b.push_back(uint8_t(x>>(8*i)));}
void string(std::vector<uint8_t>& b,const std::string& x){number(b,x.size(),8);b.insert(b.end(),x.begin(),x.end());}
iq3::ShardIdentity identity(const fs::path& p){struct stat s{};require(!stat(p.c_str(),&s),"fixture stat");return {p.filename(),uint64_t(s.st_size),uint64_t(s.st_dev),uint64_t(s.st_ino),uint64_t(s.st_mtim.tv_sec)*1000000000ULL+s.st_mtim.tv_nsec,uint64_t(s.st_ctim.tv_sec)*1000000000ULL+s.st_ctim.tv_nsec};}
struct Files {std::vector<fs::path> paths;std::vector<iq3::Planned> plan;iq3::Admission admission;std::vector<size_t> data_offsets;};
Files files(const fs::path& dir){
 require(fs::create_directory(dir),"fresh fixture folder");Files result;
 for(int i=0;i<2;++i){
  const std::string name=i?"per_layer_token_embd.weight":"token_embd.weight";
  const unsigned type=i?20:23,columns=i?160:256,rows=96,rb=i?90:136;
  std::vector<uint8_t> b{'G','G','U','F'};number(b,3,4);number(b,1,8);number(b,3,8);
  for(auto [key,value]:std::vector<std::pair<std::string,uint64_t>>{{"split.no",uint64_t(i)},{"split.count",2},{"split.tensors.count",2}}){string(b,key);number(b,10,4);number(b,value,8);}
  string(b,name);number(b,2,4);number(b,columns,8);number(b,rows,8);number(b,type,4);number(b,0,8);
  b.resize((b.size()+31)/32*32);result.data_offsets.push_back(b.size());require(b.size()%4096!=0,"non-page aligned fixture");
  std::vector<uint8_t> payload(size_t(rows)*rb,0xab);
  const unsigned block=i?18:136;for(size_t n=0;n<payload.size();n+=block){payload[n]=0;payload[n+1]=0x3c;if(!i){payload[n+2]=payload[n+3]=0;for(unsigned k=4;k<8;++k)payload[n+k]=0x88;}}
  b.insert(b.end(),payload.begin(),payload.end());auto path=dir/(i?"part2.gguf":"part1.gguf");std::ofstream f(path,std::ios::binary);f.write(reinterpret_cast<const char*>(b.data()),b.size());f.close();require(bool(f),"fixture write");
  result.paths.push_back(path);result.plan.push_back({path.filename(),name,i?"ple_lookup":"embedding",iq3::Type(type),{columns,rows},0,payload.size(),i?1:-1,0});
  result.admission.shards.push_back(identity(path));
 }
 result.admission.expected=result.plan;return result;
}
LookupFixture fixture(const Files& f){LookupFixture w;w.model=std::make_unique<iq3::Model>(f.paths,f.plan,f.admission);for(const auto& p:f.plan)w.directory.emplace(p.name,Entry{p.name,p.component,size_t(p.bytes)});return w;}
template<class F>void refuses(F f){bool refused=false;try{f();}catch(const std::exception&){refused=true;}require(refused,"expected explicit refusal");}
void mutate(const fs::path& p,size_t off){std::fstream f(p,std::ios::in|std::ios::out|std::ios::binary);f.seekp(off);char b=1;f.write(&b,1);f.close();require(bool(f),"mutation fixture");}
int main(int argc,char**argv){try{
 require(argc==2,"fresh-output-folder argument");const fs::path root=argv[1];require(fs::create_directory(root),"exclusive fixture root");
 auto f=files(root/"equivalence");auto copied=fixture(f),mapped=fixture(f);copied.copy_lookups();mapped.map_lookups();
 require(mapped.lookup_copies.empty()&&mapped.lookup_mappings.size()==2,"views only; no anonymous table owner");
 size_t decoded=0;for(const auto& t:f.plan){
  const auto columns=t.dimensions[0],rows=t.dimensions[1],rb=t.bytes/rows;
  for(size_t row=0;row<rows;++row){mapped.verify_lookup_views();const auto a=copied.read(t.name,row*rb,rb),b=mapped.read(t.name,row*rb,rb);require(a==b,"exact row bytes across page offsets");for(size_t k=0;k<columns;++k){const auto x=gsq::element(unsigned(t.type),a,columns,k),y=gsq::element(unsigned(t.type),b,columns,k);require(std::bit_cast<uint32_t>(x)==std::bit_cast<uint32_t>(y),"exact F32 decode");++decoded;}mapped.verify_lookup_views();}
  refuses([&]{mapped.read(t.name,t.bytes,1);});refuses([&]{mapped.read(t.name,t.bytes-1,2);});refuses([&]{mapped.model->slice(t.name,t.bytes,1);});
  auto foreign=mapped.model->shards[&t-&f.plan[0]].tensors.at(t.name);++foreign.bytes;refuses([&]{mapped.model->shards[&t-&f.plan[0]].slice(foreign,0,1);});
 }
 // Slice ownership keeps the authenticated File alive after Model destruction.
 mapped.model.reset();mapped.verify_lookup_views();require(mapped.read(f.plan[0].name,0,136)==copied.read(f.plan[0].name,0,136),"held File lifetime");
 auto moved=std::move(mapped.lookup_mappings.at(f.plan[0].name));moved->verify_backing();
 auto moved_again=std::move(*moved);moved_again.verify_backing();refuses([&]{moved->verify_backing();});
 // Before-command mutation and after-arithmetic/before-result mutation both
 // refuse before any newly mutated/truncated view is dereferenced.
 auto before=files(root/"before");auto vb=fixture(before);vb.map_lookups();mutate(before.paths[0],before.data_offsets[0]);refuses([&]{vb.verify_lookup_views();});
 auto after=files(root/"after");auto va=fixture(after);va.map_lookups();va.verify_lookup_views();auto value=va.read(after.plan[0].name,0,136);mutate(after.paths[0],after.data_offsets[0]);refuses([&]{va.verify_lookup_views();});
 auto trunc=files(root/"truncate");auto vt=fixture(trunc);vt.map_lookups();fs::resize_file(trunc.paths[1],trunc.data_offsets[1]);refuses([&]{vt.verify_lookup_views();});
 // Foreign inode admission and unauthenticated view owner are refused.
 auto other=files(root/"other");refuses([&]{iq3::Shard shard(other.paths[0],&f.admission.shards[0]);});
 iq3::Shard unbound(other.paths[0]);auto uns=unbound.slice(unbound.tensors.at(other.plan[0].name),0,136);refuses([&]{uns.verify_backing();});
 std::cout<<"{\"passed\":true,\"synthetic_f32_values\":"<<decoded<<",\"model_payload_reads\":false,\"device_calls\":0,\"scope\":\"actual native loader plus exact extracted candidate Weights methods; no full Engine bootstrap proof\"}\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
