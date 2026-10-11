#include "gguf.hpp"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstring>
#include <fstream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
namespace iq3 {
namespace {
constexpr uint64_t limit=(uint64_t(1)<<63)-1,header_limit=32*1024*1024,count_limit=1000000;
void require(bool b,const char* s) {if(!b) throw std::runtime_error(s);}
uint64_t add(uint64_t a,uint64_t b) {require(a<=limit && b<=limit-a,"byte overflow");return a+b;}
uint64_t mul(uint64_t a,uint64_t b) {require(!b || a<=limit/b,"size overflow");return a*b;}
bool utf8(const std::string& s) {
  size_t i=0;
  while(i<s.size()) {
    auto c=uint8_t(s[i++]); if(c<128) continue;
    unsigned n; uint32_t code,min;
    if(c>=0xc2 && c<=0xdf) {n=1;code=c&31;min=0x80;}
    else if(c>=0xe0 && c<=0xef) {n=2;code=c&15;min=0x800;}
    else if(c>=0xf0 && c<=0xf4) {n=3;code=c&7;min=0x10000;}
    else return false;
    if(n>s.size()-i) return false;
    for(unsigned j=0;j<n;++j) {auto d=uint8_t(s[i++]);if((d&0xc0)!=0x80)return false;code=(code<<6)|(d&63);}
    if(code<min || code>0x10ffff || (code>=0xd800 && code<=0xdfff))return false;
  } return true;
}
}
struct File {
  int fd=-1; uint64_t bytes=0;
  explicit File(const std::filesystem::path& path) {
    fd=open(path.c_str(),O_RDONLY|O_CLOEXEC);if(fd<0)throw std::runtime_error("open read-only failed");
    struct stat st{};
    if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_size<0) {close(fd);throw std::runtime_error("regular file required");}
    bytes=st.st_size;
  }
  ~File() {if(fd>=0)close(fd);}
};
uint64_t Meta::integer() const {
  require(type==0 || type==1 || type==2 || type==3 || type==4 || type==5 || type==10 || type==11,"metadata integer type required");
  if(auto p=std::get_if<uint64_t>(&value))return *p;
  if(auto p=std::get_if<int64_t>(&value)) {require(*p>=0,"negative metadata integer");return *p;}
  throw std::runtime_error("metadata integer required");
}
namespace {
struct Reader {
  File& f;uint64_t pos=0,read_bytes=0;
  void read(void* dst,size_t n) {
    require(pos<=std::min(f.bytes,header_limit) && n<=std::min(f.bytes,header_limit)-pos,"truncated/oversized header");
    size_t done=0;
    while(done<n) {
      auto got=pread(f.fd,static_cast<char*>(dst)+done,n-done,off_t(pos+done));
      if(got<0 && errno==EINTR)continue;
      require(got>0,"short header read"); done+=size_t(got);read_bytes+=uint64_t(got);
    }pos+=n;
  }
  uint64_t number(unsigned n) {uint8_t b[8]{};read(b,n);uint64_t v=0;for(unsigned i=0;i<n;++i)v|=uint64_t(b[i])<<(8*i);return v;}
  std::string string() {auto n=number(8);require(n<=header_limit && n<=std::min(f.bytes,header_limit)-pos,"string bound");std::string s(n,'\0');read(s.data(),n);require(utf8(s),"invalid UTF-8");return s;}
  Meta value(uint32_t t,bool nested=false) {
    Meta m;m.type=t;
    if(t==8)m.value=string();
    else if(t==9) {
      require(!nested,"nested metadata array");auto subtype=number(4),count=number(8);
      require(subtype<=12 && subtype!=9 && count<=count_limit,"array bound/type");
      std::vector<Meta> v;v.reserve(count);for(uint64_t i=0;i<count;++i)v.push_back(value(subtype,true));m.value=std::move(v);
    } else {
      require(t<=12,"unsupported metadata type");
      constexpr unsigned widths[]={1,1,2,2,4,4,4,1,0,0,8,8,8};
      auto n=widths[t];auto bits=number(n);
      if(t==6)m.value=double(bits_float(uint32_t(bits)));
      else if(t==12)m.value=std::bit_cast<double>(bits);
      else if(t==1 || t==3 || t==5 || t==11) {
        if(n<8 && (bits&(uint64_t(1)<<(8*n-1))))bits|=(~uint64_t(0))<<(8*n);
        m.value=std::bit_cast<int64_t>(bits);
      } else {if(t==7)require(bits<2,"invalid bool");m.value=bits;}
    }return m;
  }
};
}
Shard::Shard(const std::filesystem::path& path):file(std::make_shared<File>(path)),basename(path.filename()) {
  file_bytes=file->bytes;Reader r{*file};char magic[4];r.read(magic,4);
  require(std::memcmp(magic,"GGUF",4)==0 && r.number(4)==3,"GGUF v3 LE required");
  auto nt=r.number(8),nm=r.number(8);require(nt<=count_limit && nm<=count_limit,"count bound");
  for(uint64_t i=0;i<nm;++i) {
    auto key=r.string();require(!key.empty() && !metadata.contains(key),"duplicate/empty metadata");
    auto type=r.number(4);metadata.emplace(std::move(key),r.value(type));
  }
  uint64_t alignment=32;
  if(metadata.contains("general.alignment")) {
    auto& m=metadata.at("general.alignment");require(m.type==4,"alignment type");alignment=m.integer();
  }
  require(alignment && alignment<=1048576 && !(alignment&(alignment-1)),"alignment bound");
  auto has=[&](const char* s){return metadata.contains(s);};
  if(has("split.no") || has("split.count") || has("split.tensors.count")) {
    require(has("split.no") && has("split.count") && has("split.tensors.count"),"incomplete split");
    auto count=metadata.at("split.count").integer();
    require(count>0 && count<=65535 && metadata.at("split.no").integer()<count && metadata.at("split.tensors.count").integer()>=nt,"split bounds");
  }
  for(uint64_t i=0;i<nt;++i) {
    Tensor t;t.name=r.string();require(!t.name.empty() && !tensors.contains(t.name),"duplicate/empty tensor");
    auto rank=r.number(4);require(rank>0 && rank<=4,"rank bound");uint64_t elements=1;
    for(uint64_t j=0;j<rank;++j) {auto d=r.number(8);require(d>0,"zero dimension");elements=mul(elements,d);t.dimensions.push_back(d);}
    t.type=Type(r.number(4));t.offset=r.number(8);auto l=layout(t.type);
    require(l.elements && t.dimensions[0]%l.elements==0 && t.offset%alignment==0,"unsupported type/row/alignment");
    t.bytes=mul(elements/l.elements,l.bytes);tensors.emplace(t.name,t);
  }
  header_bytes=r.pos;read_bytes=r.read_bytes;data_start=add(r.pos,alignment-1)/alignment*alignment;
  require(data_start<=file_bytes,"truncated alignment");
  std::vector<const Tensor*> ordered;for(auto& [name,t]:tensors)ordered.push_back(&t);
  std::sort(ordered.begin(),ordered.end(),[](auto a,auto b){return a->offset<b->offset;});uint64_t end=0;
  for(auto t:ordered) {require(t->offset>=end,"overlapping tensors");end=add(t->offset,t->bytes);require(add(data_start,end)<=file_bytes,"tensor out of file");}
}
void validate_splits(const std::vector<Shard>& shards) {
  require(!shards.empty(),"no shards");std::set<std::string> names;std::set<uint64_t> ordinals;uint64_t total=0;
  for(auto& s:shards)total=add(total,s.tensors.size());
  for(auto& s:shards) {
    if(shards.size()>1 || s.metadata.contains("split.count")) {
      auto& m=s.metadata;
      require(m.contains("split.count") && m.contains("split.no") && m.contains("split.tensors.count"),"missing split fields");
      require(m.at("split.count").integer()==shards.size() && m.at("split.tensors.count").integer()==total && ordinals.insert(m.at("split.no").integer()).second,"split coverage mismatch");
    }
    for(auto& [name,t]:s.tensors)require(names.insert(name).second,"cross-shard duplicate");
  }
}
Slice::Slice(std::shared_ptr<File> f,uint64_t off,size_t bytes):file_(std::move(f)),size_(bytes) {
  struct stat st{};require(!fstat(file_->fd,&st) && uint64_t(st.st_size)==file_->bytes,"backing file changed size");
  require(bytes && off<=file_->bytes && bytes<=file_->bytes-off,"slice outside file");
  auto page=sysconf(_SC_PAGESIZE);require(page>0,"page size unavailable");
  auto start=off/uint64_t(page)*uint64_t(page);delta_=off-start;length_=add(delta_,bytes);
  mapping_=mmap(nullptr,length_,PROT_READ,MAP_PRIVATE,file_->fd,off_t(start));
  if(mapping_==MAP_FAILED){mapping_=nullptr;throw std::runtime_error("mmap failed");}
}
Slice::~Slice(){if(mapping_)munmap(mapping_,length_);}
Slice::Slice(Slice&& s) noexcept:file_(std::move(s.file_)),mapping_(std::exchange(s.mapping_,nullptr)),length_(s.length_),delta_(s.delta_),size_(s.size_){}
Slice& Slice::operator=(Slice&& s) noexcept {if(this!=&s){if(mapping_)munmap(mapping_,length_);file_=std::move(s.file_);mapping_=std::exchange(s.mapping_,nullptr);length_=s.length_;delta_=s.delta_;size_=s.size_;}return *this;}
Slice Shard::slice(const Tensor& t,uint64_t relative,size_t bytes) const {
  const auto& owned=tensors.at(t.name);
  require(owned.offset==t.offset && owned.bytes==t.bytes && owned.type==t.type && owned.dimensions==t.dimensions,"foreign tensor descriptor");
  require(relative<=t.bytes && bytes<=t.bytes-relative,"slice outside tensor");
  return Slice(file,add(add(data_start,t.offset),relative),bytes);
}
std::vector<Planned> read_plan(const std::filesystem::path& path) {
  std::ifstream f(path);require(bool(f),"plan open failed");std::vector<Planned> out;std::string line;
  while(std::getline(f,line)) {
    if(line.empty() || line[0]=='#')continue;
    std::istringstream s(line);Planned p;unsigned type,rank;
    require(bool(s>>p.shard>>p.name>>p.component>>type>>p.offset>>p.bytes>>p.layer>>p.mask>>rank),"bad plan row");
    require(rank>0 && rank<=4 && p.mask>=0 && p.mask<=3,"bad plan rank/mask");
    p.type=Type(type);for(unsigned i=0;i<rank;++i){uint64_t n;require(bool(s>>n),"plan dimension");p.dimensions.push_back(n);}
    std::string extra;require(!(s>>extra),"trailing plan fields");out.push_back(std::move(p));
  }require(!out.empty(),"empty plan");return out;
}
namespace {
void placement_identity(const Planned& p) {
  std::string suffix=p.name;
  int layer=-1;
  if(suffix.starts_with("blk.")) {
    auto dot=suffix.find('.',4);require(dot!=std::string::npos,"layer name");
    auto number=suffix.substr(4,dot-4);
    require(!number.empty() && number.find_first_not_of("0123456789")==std::string::npos,"layer digits");
    layer=std::stoi(number);require(layer>=0 && layer<48 && number==std::to_string(layer),"layer range/canonical name");
    suffix=suffix.substr(dot+1);
  }
  static const std::map<std::string,std::string> components={
    {"attn_gate.weight","gdn"},{"attn_qkv.weight","gdn"},{"ssm_a","gdn"},
    {"ssm_alpha.weight","gdn"},{"ssm_beta.weight","gdn"},{"ssm_conv1d.weight","gdn"},{"ssm_dt.bias","gdn"},{"ssm_out.weight","gdn"},
    {"ffn_down_exps.weight","routed_experts"},{"ffn_gate_exps.weight","routed_experts"},{"ffn_up_exps.weight","routed_experts"},
    {"ffn_down_shexp.weight","shared_experts"},{"ffn_gate_shexp.weight","shared_experts"},{"ffn_up_shexp.weight","shared_experts"},
    {"ffn_gate_inp.weight","routers"},{"ffn_gate_inp_shexp.weight","routers"},
    {"hc_attn_down.weight","hyperconnections"},{"hc_attn_up.weight","hyperconnections"},{"hc_attn_inject.weight","hyperconnections"},
    {"hc_ffn_down.weight","hyperconnections"},{"hc_ffn_up.weight","hyperconnections"},{"hc_ffn_inject.weight","hyperconnections"},
    {"output_hc_down.weight","hyperconnections"},{"output_hc_up.weight","hyperconnections"},
    {"attn_k_norm.weight","norms"},{"attn_q_norm.weight","norms"},{"hc_attn_norm.weight","norms"},{"hc_ffn_norm.weight","norms"},
    {"indexer.k_norm.weight","norms"},{"indexer.q_norm.weight","norms"},{"ssm_norm.weight","norms"},{"output_hc_norm.weight","norms"},
    {"ple_conv1d.weight","ple_projection"},{"ple_key.weight","ple_projection"},{"ple_norm_conv.weight","ple_projection"},
    {"ple_norm_key.weight","ple_projection"},{"ple_norm_query.weight","ple_projection"},{"ple_value.weight","ple_projection"},
    {"attn_k.weight","qsa_attention"},{"attn_output.weight","qsa_attention"},{"attn_q.weight","qsa_attention"},{"attn_v.weight","qsa_attention"},
    {"indexer.k_proj.weight","qsa_indexer"},{"indexer.q_proj.weight","qsa_indexer"},
    {"output.weight","target_head"},{"per_layer_token_embd.weight","ple_lookup"},{"token_embd.weight","embedding"}
  };
  if(p.name=="per_layer_token_embd.weight")layer=1; // global lookup belongs to layer1
  require(components.contains(suffix) && components.at(suffix)==p.component && layer==p.layer,"component/layer name identity");
  bool global=suffix.starts_with("output") || suffix=="token_embd.weight" || suffix=="per_layer_token_embd.weight";
  require(global==!p.name.starts_with("blk."),"global/layer namespace");
  bool host=p.component=="embedding" || p.component=="ple_lookup";
  bool replica=p.component=="hyperconnections" && (suffix.ends_with("_down.weight") || suffix.ends_with("_up.weight"));
  int mask=host?0:replica?3:layer>=0 && layer<24?1:2;
  require(p.mask==mask,"placement mask differs from census rule");
}
}
Model::Model(const std::vector<std::filesystem::path>& paths,std::vector<Planned> p):plan(std::move(p)) {
  for(auto& path:paths)shards.emplace_back(path);validate_splits(shards);
  std::map<std::string,const Shard*> byfile;size_t n=0;
  for(auto& s:shards){require(byfile.emplace(s.basename,&s).second,"duplicate shard filename");n+=s.tensors.size();}
  require(n==plan.size(),"census tensor coverage");std::set<std::string> names;
  const std::set<std::string> components={"embedding","ple_lookup","gdn","hyperconnections","norms","ple_projection","qsa_attention","qsa_indexer","routed_experts","routers","shared_experts","target_head"};
  for(auto& row:plan) {
    placement_identity(row);
    require(names.insert(row.name).second && components.contains(row.component),"duplicate/unknown census component");
    require(row.layer>=-1 && row.layer<48,"layer outside target");
    bool host=row.component=="embedding" || row.component=="ple_lookup";
    require(host?(row.mask==0):(row.mask>0),"host lookup residency violation");
    if(!host && row.mask!=3)require(row.mask==(row.layer>=0 && row.layer<24?1:2),"layer ownership violation");
    if(row.mask==3)require(row.component=="hyperconnections" && row.type==Type::Q8_0,"unexpected replica");
    auto& t=byfile.at(row.shard)->tensors.at(row.name);
    require(t.type==row.type && t.dimensions==row.dimensions && t.offset==row.offset && t.bytes==row.bytes,"census descriptor mismatch");
  }
}
std::array<uint64_t,3> Model::census() const {
  std::array<uint64_t,3> totals{};for(auto& p:plan) {if(!p.mask)totals[2]=add(totals[2],p.bytes);for(int card=0;card<2;++card)if(p.mask&(1<<card))totals[card]=add(totals[card],p.bytes);}return totals;
}
Slice Model::slice(const std::string& name,uint64_t relative,size_t bytes) const {
  for(auto& s:shards)if(s.tensors.contains(name))return s.slice(s.tensors.at(name),relative,bytes);
  throw std::out_of_range("tensor name");
}
ownrt::Allocation Model::reserve(const std::string& name,unsigned card,ownrt::Device& device) const {
  require(card<2,"card bound");for(auto& p:plan)if(p.name==name) {
    require(p.mask&(1<<card),"tensor not owned by card");
    return device.arena.allocate(p.component+":"+name,p.bytes,ownrt::Memory::device,ownrt::Category::weights,ownrt::Lifetime::process);
  }
  throw std::out_of_range("tensor name");
}
}
