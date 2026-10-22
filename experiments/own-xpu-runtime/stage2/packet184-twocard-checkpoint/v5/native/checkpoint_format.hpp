#pragma once
// packet184 two-card (TP2) session checkpoint -- label "experimental-two-card", contract "v1.2+p184".
// FORMAT part: constants, strict JSON reader, manifest model, load/verify, sibling lock, the commit /
// inspect / delete tools and the pure --input classification. Self-contained (C++20 standard library
// + OpenSSL EVP): included by the engine entry TU (via checkpoint_tp2.hpp) AND compiled alone into the
// device-free tool binary (v5/native/checkpoint_tool.cpp, gnu host build, no SYCL) that the coordinator
// runs for commit, precheck inspect and delete. No kernel arithmetic anywhere.
//
// Layout of a checkpoint ROOT/ID (the manifest is the visibility point and the only source of truth):
//   manifest.json   two-card manifest; names BOTH rank blob sets with sha256; written last (rename)
//   fields.tsv      derived index rendered from the parsed manifest (byte-equal at every load)
//   tokens.bin      processed history, N little-endian int32
//   rank0/<blob>.bin, rank1/<blob>.bin   one file per saved buffer, nothing else
// Sibling lock ROOT/ID.lock (flock). The two-card coordinator holds it (exclusive for save, shared for
// restore) across both ranks; ranks and the commit tool only PROVE that someone holds it.
//
// Two-card atomicity ("both ranks or none"):
//   save    = stage (each rank writes its blob set + rankR/stage.json under the coordinator's
//             exclusive lock) -> commit (device-free tool: re-hashes BOTH rank sets, writes
//             manifest.json.tmp + fields.tsv, removes the stage receipts, renames manifest.json).
//             Without the rename nothing is visible; the coordinator removes a failed directory.
//   restore = verify on both ranks (manifest, identity, geometry, own blob set fully hashed and
//             held in memory, the other rank's set present with manifest sizes; any failure is a
//             refusal before any upload) -> apply on both ranks only after BOTH verified.
//
// MTP draft state (mtp36::DraftRuntime): SAVED, not rebuilt. Draft KV row j is computed from the
// target's layer-47 hidden stream at position j; no target buffer retains those streams (QSA keeps
// K/V projections, GDN keeps the recurrent summary), so rebuilding the draft cache needs a full
// target re-prefill. The rank-1 target 'streams' buffer at the boundary (hidden stream of the last
// processed position, the input of the next draft step) is saved for the same reason.
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <cerrno>
#include <cstring>
#include <cstdlib>
#include <functional>
#include <optional>
#include <stdexcept>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include <unistd.h>
#include <openssl/evp.h>
namespace pipeline { namespace ckpt184 {
namespace fs = std::filesystem;
static void require(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
static std::string sha256_hex(const std::vector<uint8_t>& b) {
  unsigned char digest[32];unsigned n=0;
  require(EVP_Digest(b.data(),b.size(),digest,&n,EVP_sha256(),nullptr)==1&&n==32,"sha256");
  std::string s;for(auto v:digest){s+="0123456789abcdef"[v>>4];s+="0123456789abcdef"[v&15];}return s;
}
static std::string quote(const std::string& v) {
  std::string o="\"";
  for(unsigned char c:v) {
    if(c=='"')o+="\\\"";else if(c=='\\')o+="\\\\";else if(c=='\n')o+="\\n";else if(c=='\t')o+="\\t";else if(c=='\r')o+="\\r";
    else if(c<0x20){char u[8];std::snprintf(u,sizeof u,"\\u%04x",unsigned(c));o+=u;}
    else o+=char(c);
  }
  return o+"\"";
}

static const char* const FORMAT="ownrt.session-checkpoint.v1";
static const char* const LABEL="experimental-two-card";
static const char* const CONTRACT="v1.2+p184";
static const char* const PACKET="packet184-twocard-checkpoint";
static const char* const PROFILE="tp2-bundle8-v5";
static const char* const TOKENIZER_IDENTITY_FORMAT="ownrt.tokenizer-identity.v1";
static const char* const DRAFT_POLICY="saved";
static const char* const DRAFT_REASON="draft KV row j is computed from the target layer-47 hidden stream at position j, which no target buffer retains; rebuilding needs a full target re-prefill";
static const std::vector<std::string> OPERATIONS{"same-generation-resume","append","restore-then-save"};

struct Refusal : std::runtime_error {
  std::string check, detail;
  Refusal(const std::string& op,const std::string& c,const std::string& d)
    : std::runtime_error("checkpoint "+op+" refused: "+c+": "+d),check(c),detail(d) {}
};
[[noreturn]] static void refuse(const std::string& op,const std::string& check,const std::string& detail) {throw Refusal(op,check,detail);}
static bool valid_id(const std::string& id) {
  if(id.empty()||id.size()>96)return false;
  auto alnum=[](char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9');};
  if(!alnum(id[0]))return false;
  for(char c:id)if(!alnum(c)&&c!='.'&&c!='_'&&c!='-')return false;
  return !(id.size()>=5&&id.compare(id.size()-5,5,".lock")==0);
}
static bool hex64(const std::string& s) {
  if(s.size()!=64)return false;
  for(char c:s)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
  return true;
}
static bool suffix(const std::string& s,const std::string& x){return s.size()>=x.size()&&s.compare(s.size()-x.size(),std::string::npos,x)==0;}

// ---------------------------------------------------------------- strict JSON reader (packet181)
struct CJson {
  enum Kind {Null,Bool,Number,String,Array,Object};
  Kind kind=Null; bool boolean=false; std::string text;
  std::vector<CJson> items; std::vector<std::string> keys;
  const CJson* find(const std::string& k) const {for(size_t j=0;j<keys.size();++j)if(keys[j]==k)return &items[j];return nullptr;}
};
struct CJsonParser {
  const std::string& s; size_t i=0; int depth=0;
  explicit CJsonParser(const std::string& t):s(t){}
  [[noreturn]] void fail(const std::string& why) const {throw std::runtime_error("json: "+why+" at byte "+std::to_string(i));}
  static bool digit(char c){return c>='0'&&c<='9';}
  void ws(){while(i<s.size()&&(s[i]==' '||s[i]=='\n'||s[i]=='\r'||s[i]=='\t'))++i;}
  bool eat(char c){ws();if(i<s.size()&&s[i]==c){++i;return true;}return false;}
  void expect(char c){if(!eat(c))fail(std::string("expected '")+c+"'");}
  static void utf8(std::string& o,unsigned cp) {
    if(cp<0x80)o+=char(cp);
    else if(cp<0x800){o+=char(0xC0|(cp>>6));o+=char(0x80|(cp&0x3F));}
    else {o+=char(0xE0|(cp>>12));o+=char(0x80|((cp>>6)&0x3F));o+=char(0x80|(cp&0x3F));}
  }
  std::string string() {
    ws();if(i>=s.size()||s[i]!='"')fail("expected string");++i;std::string o;
    while(true) {
      if(i>=s.size())fail("unterminated string");
      const unsigned char c=static_cast<unsigned char>(s[i++]);
      if(c=='"')return o;
      if(c<0x20)fail("raw control character in string");
      if(c!='\\'){o+=char(c);continue;}
      if(i>=s.size())fail("truncated escape");
      const char e=s[i++];
      switch(e) {
        case '"':o+='"';break; case '\\':o+='\\';break; case '/':o+='/';break;
        case 'b':o+='\b';break; case 'f':o+='\f';break; case 'n':o+='\n';break;
        case 'r':o+='\r';break; case 't':o+='\t';break;
        case 'u': {
          if(i+4>s.size())fail("short \\u escape");
          unsigned cp=0;
          for(int k=0;k<4;++k){const char h=s[i++];cp<<=4;
            if(h>='0'&&h<='9')cp|=unsigned(h-'0');else if(h>='a'&&h<='f')cp|=unsigned(h-'a'+10);
            else if(h>='A'&&h<='F')cp|=unsigned(h-'A'+10);else fail("bad \\u hex digit");}
          if(cp>=0xD800&&cp<=0xDFFF)fail("surrogate escape (never written by the checkpoint writer)");
          utf8(o,cp);break;
        }
        default:fail("unknown escape");
      }
    }
  }
  CJson value() {
    ws();if(i>=s.size())fail("unexpected end");
    if(++depth>64)fail("nesting deeper than 64");
    CJson v;const char c=s[i];
    if(c=='{') {
      ++i;v.kind=CJson::Object;ws();
      if(i<s.size()&&s[i]=='}')++i;
      else while(true) {
        std::string k=string();
        for(const auto& f:v.keys)if(f==k)fail("duplicate key "+k);
        expect(':');CJson item=value();v.keys.push_back(std::move(k));v.items.push_back(std::move(item));
        if(eat(','))continue;
        expect('}');break;
      }
    } else if(c=='[') {
      ++i;v.kind=CJson::Array;ws();
      if(i<s.size()&&s[i]==']')++i;
      else while(true){v.items.push_back(value());if(eat(','))continue;expect(']');break;}
    } else if(c=='"'){v.kind=CJson::String;v.text=string();}
    else if(s.compare(i,4,"true")==0){i+=4;v.kind=CJson::Bool;v.boolean=true;}
    else if(s.compare(i,5,"false")==0){i+=5;v.kind=CJson::Bool;}
    else if(s.compare(i,4,"null")==0){i+=4;}
    else {
      const size_t b=i;if(s[i]=='-')++i;
      if(i<s.size()&&s[i]=='0')++i;
      else {if(i>=s.size()||s[i]<'1'||s[i]>'9')fail("bad number");while(i<s.size()&&digit(s[i]))++i;}
      if(i<s.size()&&s[i]=='.'){++i;if(i>=s.size()||!digit(s[i]))fail("bad fraction");while(i<s.size()&&digit(s[i]))++i;}
      if(i<s.size()&&(s[i]=='e'||s[i]=='E')){++i;if(i<s.size()&&(s[i]=='+'||s[i]=='-'))++i;
        if(i>=s.size()||!digit(s[i]))fail("bad exponent");while(i<s.size()&&digit(s[i]))++i;}
      v.kind=CJson::Number;v.text=s.substr(b,i-b);
    }
    --depth;return v;
  }
};
static CJson parse_json(const std::string& text) {
  CJsonParser p(text);CJson v=p.value();p.ws();
  if(p.i!=text.size())p.fail("trailing bytes after the object");
  return v;
}
static const CJson& at(const CJson& o,const char* k) {
  if(o.kind!=CJson::Object)throw std::runtime_error(std::string("expected an object holding ")+k);
  const CJson* v=o.find(k);if(!v)throw std::runtime_error(std::string("field missing: ")+k);
  return *v;
}
static const std::string& str(const CJson& v,const std::string& what) {
  if(v.kind!=CJson::String)throw std::runtime_error("not a string: "+what);return v.text;
}
static int64_t integer(const CJson& v,const std::string& what) {
  if(v.kind!=CJson::Number)throw std::runtime_error("not a number: "+what);
  const auto& t=v.text;const size_t k=t[0]=='-'?1:0;
  if(t.size()<=k||t.size()>k+19)throw std::runtime_error("integer out of range: "+what);
  for(size_t j=k;j<t.size();++j)if(t[j]<'0'||t[j]>'9')throw std::runtime_error("not an integer: "+what);
  try{return std::stoll(t);}catch(const std::out_of_range&){throw std::runtime_error("integer out of int64 range: "+what);}
}
static bool boolean(const CJson& v,const std::string& what){if(v.kind!=CJson::Bool)throw std::runtime_error("not a boolean: "+what);return v.boolean;}
static void keys(const CJson& o,std::initializer_list<const char*> k,const std::string& what) {
  if(o.kind!=CJson::Object)throw std::runtime_error("not an object: "+what);
  if(o.keys.size()!=k.size())throw std::runtime_error("unexpected key set in "+what);
  size_t j=0;for(const char* key:k){if(o.keys[j++]!=key)throw std::runtime_error("field order/name in "+what+": expected "+key);}
}
static std::vector<int64_t> int_list(const CJson& v,const std::string& what) {
  if(v.kind!=CJson::Array)throw std::runtime_error("not an array: "+what);
  std::vector<int64_t> out;for(const auto& x:v.items)out.push_back(integer(x,what));return out;
}
static std::string join(const std::vector<int64_t>& v){std::ostringstream o;for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];return o.str();}

// ---------------------------------------------------------------- file helpers
static void write_file(const fs::path& path,const void* data,size_t n) {
  int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0644);
  require(fd>=0,"checkpoint create "+path.string()+": "+std::strerror(errno));
  auto p=static_cast<const uint8_t*>(data);size_t left=n;
  while(left){ssize_t w=::write(fd,p,left);if(w<=0){::close(fd);require(false,"checkpoint write "+path.string());}p+=w;left-=size_t(w);}
  if(::fsync(fd)!=0){::close(fd);require(false,"checkpoint fsync "+path.string());}
  require(::close(fd)==0,"checkpoint close "+path.string());
}
static void write_text(const fs::path& path,const std::string& s){write_file(path,s.data(),s.size());}
static void fsync_dir(const fs::path& d) {
  int fd=::open(d.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
  require(fd>=0,"checkpoint directory open "+d.string());
  const int rc=::fsync(fd);::close(fd);require(rc==0,"checkpoint directory fsync "+d.string());
}
static std::vector<uint8_t> read_file(const fs::path& path) {
  std::ifstream f(path,std::ios::binary);require(bool(f),"checkpoint read "+path.string());
  std::vector<uint8_t> b((std::istreambuf_iterator<char>(f)),{});require(!f.bad(),"checkpoint read "+path.string());
  return b;
}
static std::string read_text(const fs::path& path){auto b=read_file(path);return std::string(b.begin(),b.end());}
static std::string self_sha256(){return sha256_hex(read_file("/proc/self/exe"));}
static std::map<std::string,std::string> read_request(const fs::path& path,const std::string& op) {
  std::map<std::string,std::string> values;std::istringstream in{read_text(path)};std::string line;
  while(std::getline(in,line)) {
    if(line.empty())continue;const auto tab=line.find('\t');
    if(tab==std::string::npos||tab==0)refuse(op,"request","malformed request line in "+path.string());
    if(!values.emplace(line.substr(0,tab),line.substr(tab+1)).second)refuse(op,"request","duplicate request key "+line.substr(0,tab));
  }
  return values;
}
static const std::string& need(const std::map<std::string,std::string>& m,const std::string& k,const std::string& op) {
  auto it=m.find(k);if(it==m.end())refuse(op,"request","missing request key "+k);return it->second;
}
static int64_t need_int(const std::map<std::string,std::string>& m,const std::string& k,const std::string& op) {
  const auto& v=need(m,k,op);
  if(v.empty()||v.size()>18||!std::all_of(v.begin()+(v[0]=='-'?1:0),v.end(),[](char c){return c>='0'&&c<='9';}))refuse(op,"request","not an integer: "+k);
  return std::stoll(v);
}
static std::pair<fs::path,std::string> split_dir(const fs::path& target) {
  fs::path dir=target.lexically_normal();if(dir.filename().empty())dir=dir.parent_path();
  return {dir.has_parent_path()?dir.parent_path():fs::path("."),dir.filename().string()};
}

// ---------------------------------------------------------------- locks
// User-facing tools (inspect, delete) take the sibling lock themselves (packet181 protocol).
struct Lock {
  fs::path path;int fd=-1;
  Lock(const fs::path& root,const std::string& id,bool exclusive,const std::string& op) {
    path=root/(id+".lock");
    for(int attempt=0;attempt<3;++attempt) {
      fd=::open(path.c_str(),O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0644);
      if(fd<0)refuse(op,"lock io","cannot open "+path.string()+": "+std::strerror(errno));
      if(::flock(fd,(exclusive?LOCK_EX:LOCK_SH)|LOCK_NB)!=0) {
        const int err=errno;::close(fd);fd=-1;
        if(err==EWOULDBLOCK)refuse(op,"lock","checkpoint "+id+" is in use ("+
          std::string(exclusive?"another process holds its lock":"it is being saved or deleted")+"); no checkpoint operation waits");
        refuse(op,"lock io",std::string("flock: ")+std::strerror(err));
      }
      struct stat held{},live{};
      if(::fstat(fd,&held)==0&&::stat(path.c_str(),&live)==0&&held.st_dev==live.st_dev&&held.st_ino==live.st_ino)return;
      ::close(fd);fd=-1;
    }
    refuse(op,"lock io","lock file replaced by concurrent deletes");
  }
  Lock(const Lock&)=delete;Lock& operator=(const Lock&)=delete;
  void unlink_while_held(){::unlink(path.c_str());}
  ~Lock(){if(fd>=0)::close(fd);}
};
// Ranks and the commit tool run inside the coordinator's lock: they prove the lock is held by
// another open file description (an exclusive non-blocking attempt must fail with EWOULDBLOCK).
static void lock_held_proof(const fs::path& root,const std::string& id,const std::string& op) {
  const fs::path p=root/(id+".lock");
  int fd=::open(p.c_str(),O_RDWR|O_NOFOLLOW|O_CLOEXEC);
  if(fd<0)refuse(op,"lock","coordinator lock file missing: "+p.string());
  if(::flock(fd,LOCK_EX|LOCK_NB)==0){::flock(fd,LOCK_UN);::close(fd);refuse(op,"lock","the coordinator does not hold "+p.string());}
  const int err=errno;::close(fd);
  if(err!=EWOULDBLOCK)refuse(op,"lock io",std::string("flock: ")+std::strerror(err));
}

// ---------------------------------------------------------------- tokenizer/template identity (packet181)
struct TokenizerIdentity { std::string file_sha256,format,gguf_header_sha256,tokenizer_source_sha256,vocab_bin_sha256; };
static TokenizerIdentity tokenizer_identity(const fs::path& path,const std::string& op) {
  if(path.empty())refuse(op,"tokenizer identity","--tokenizer-identity FILE is required for every checkpoint operation");
  if(!fs::is_regular_file(path))refuse(op,"tokenizer identity","file missing: "+path.string());
  const auto bytes=read_file(path);
  if(bytes.empty()||bytes.size()>65536)refuse(op,"tokenizer identity","file size outside 1..65536 bytes");
  TokenizerIdentity t;t.file_sha256=sha256_hex(bytes);
  std::map<std::string,std::string> values;std::istringstream in{std::string(bytes.begin(),bytes.end())};std::string line;
  while(std::getline(in,line)) {
    if(line.empty()||line[0]=='#')continue;
    const auto tab=line.find('\t');
    if(tab==std::string::npos||tab==0||line.find('\t',tab+1)!=std::string::npos)refuse(op,"tokenizer identity","each line must be KEY<TAB>VALUE");
    if(!values.emplace(line.substr(0,tab),line.substr(tab+1)).second)refuse(op,"tokenizer identity","duplicate key "+line.substr(0,tab));
  }
  auto get=[&](const char* k)->std::string{auto it=values.find(k);if(it==values.end())refuse(op,"tokenizer identity",std::string("missing key ")+k);return it->second;};
  t.format=get("format");if(t.format!=TOKENIZER_IDENTITY_FORMAT)refuse(op,"tokenizer identity","format "+t.format);
  t.gguf_header_sha256=get("gguf_header_sha256");t.tokenizer_source_sha256=get("tokenizer_source_sha256");t.vocab_bin_sha256=get("vocab_bin_sha256");
  for(const auto* v:{&t.gguf_header_sha256,&t.tokenizer_source_sha256,&t.vocab_bin_sha256})
    if(!hex64(*v))refuse(op,"tokenizer identity","pinned hashes must be 64 lowercase hex characters");
  return t;
}

// ---------------------------------------------------------------- shared pure helpers
static bool kv_name(const std::string& n){return suffix(n,".qsa.keys")||suffix(n,".qsa.values")||suffix(n,".qsa.raw")||suffix(n,".qsa.pooled");}
static std::pair<int64_t,int64_t> history_of(const std::vector<int>& tokens,int64_t eos) {
  const size_t N=tokens.size();return {N>=2?int64_t(tokens[N-2]):eos,int64_t(tokens[N-1])};
}

// ---------------------------------------------------------------- manifest model
struct Blob { std::string name,source,sha256;uint64_t bytes=0;int64_t rows=-1; };
struct Skip { std::string label,source,rule; };
struct RankState {
  int rank=0;std::string directory;std::vector<int64_t> qsa_layers,gdn_layers;
  int64_t history0=0,history1=0,bank_parity=0,active_bank=0,spare_bank=0,launch_extent=0,alternate_launch_extent=0,draft_position=-1,draft_context_extent=0;
  bool miss_banks=false,draft_owner=false,draft_disabled=false;
  std::vector<Blob> blobs;std::vector<Skip> skipped;
};
struct Manifest {
  std::string text,sha256;
  std::string checkpoint_id,created,operation,parent_id,parent_sha;
  std::string identity_sha,draft_manifest_sha,binary_sha,selection_sha,arithmetic,engine_packet,engine_profile;
  std::vector<std::string> stat_rows_text;
  bool mini=false;
  int64_t ranks=2,draft_rank=1,target_split=0,layer_boundary=0;
  int64_t h=0,kvh=0,ad=0,ih=0,g_id=0,qh=0,kh=0,vh=0,d=0,context=0,vocab=0,eos=0;
  std::vector<int64_t> qsa_layers,gdn_layers;
  TokenizerIdentity tokenizer;
  int64_t prompt_length=0,length=0,position=0,next_token=0,history0=0,history1=0;std::string tokens_sha;
  int64_t draft_position=-1;bool draft_disabled=false;
  std::vector<RankState> rank_states;
  int64_t save_bytes=0;std::string stage_seconds_text[2],commit_seconds_text;
};
static RankState parse_rank_state(const CJson& r,const std::string& what) {
  keys(r,{"rank","directory","qsa_layers","gdn_layers","host_state","blobs","skipped"},what);
  RankState s;s.rank=int(integer(at(r,"rank"),what+".rank"));s.directory=str(at(r,"directory"),what+".directory");
  if(s.rank<0||s.rank>1||s.directory!="rank"+std::to_string(s.rank))throw std::runtime_error(what+" rank/directory");
  s.qsa_layers=int_list(at(r,"qsa_layers"),what+".qsa_layers");s.gdn_layers=int_list(at(r,"gdn_layers"),what+".gdn_layers");
  const auto& hs=at(r,"host_state");
  keys(hs,{"history0","history1","bank_parity","active_bank","spare_bank","miss_banks","launch_extent","alternate_launch_extent","draft_owner","draft_position","draft_disabled","draft_context_extent"},what+".host_state");
  s.history0=integer(at(hs,"history0"),"history0");s.history1=integer(at(hs,"history1"),"history1");s.bank_parity=integer(at(hs,"bank_parity"),"bank_parity");
  s.active_bank=integer(at(hs,"active_bank"),"active_bank");s.spare_bank=integer(at(hs,"spare_bank"),"spare_bank");s.miss_banks=boolean(at(hs,"miss_banks"),"miss_banks");
  s.launch_extent=integer(at(hs,"launch_extent"),"launch_extent");s.alternate_launch_extent=integer(at(hs,"alternate_launch_extent"),"alternate_launch_extent");
  s.draft_owner=boolean(at(hs,"draft_owner"),"draft_owner");s.draft_position=integer(at(hs,"draft_position"),"draft_position");
  s.draft_disabled=boolean(at(hs,"draft_disabled"),"draft_disabled");s.draft_context_extent=integer(at(hs,"draft_context_extent"),"draft_context_extent");
  const auto& blobs=at(r,"blobs");if(blobs.kind!=CJson::Array)throw std::runtime_error(what+".blobs");
  std::set<std::string> names;
  for(const auto& b:blobs.items) {
    keys(b,{"name","source","bytes","sha256","slice"},what+".blob");
    Blob x;x.name=str(at(b,"name"),"blob.name");x.source=str(at(b,"source"),"blob.source");
    const int64_t bytes=integer(at(b,"bytes"),"blob.bytes");x.sha256=str(at(b,"sha256"),"blob.sha256");
    if(!valid_id(x.name)||x.name=="stage")throw std::runtime_error("blob name "+x.name);
    if(!names.insert(x.name).second)throw std::runtime_error("duplicate blob "+x.name);
    if(bytes<0||bytes>(int64_t(1)<<40)||!hex64(x.sha256))throw std::runtime_error("blob "+x.name);
    static const std::set<std::string> sources{"plan","spare","reserve","draft"};
    if(!sources.count(x.source))throw std::runtime_error("blob source "+x.source);
    x.bytes=uint64_t(bytes);
    const auto& slice=at(b,"slice");
    if(slice.kind!=CJson::Null){const auto v=int_list(slice,"blob.slice");if(v.size()!=2||v[0]!=0||v[1]<0)throw std::runtime_error("blob slice "+x.name);x.rows=v[1];}
    s.blobs.push_back(x);
  }
  const auto& skipped=at(r,"skipped");if(skipped.kind!=CJson::Array)throw std::runtime_error(what+".skipped");
  std::set<std::string> labels;
  for(const auto& k:skipped.items) {
    keys(k,{"label","source","rule"},what+".skipped");
    Skip x{str(at(k,"label"),"skip.label"),str(at(k,"source"),"skip.source"),str(at(k,"rule"),"skip.rule")};
    if(x.label.empty()||x.rule.rfind("skip: ",0)!=0||!labels.insert(x.label).second)throw std::runtime_error("skipped entry "+x.label);
    s.skipped.push_back(x);
  }
  return s;
}
// One strict parse; every structural and semantic rule is checked here.
static void manifest_fill(Manifest& m) {
  const CJson root=parse_json(m.text);
  keys(root,{"format","label","contract","operations","checkpoint_id","created","lineage","model","engine","topology","geometry","dtypes",
             "tokenizer_identity","token_state","sampler","draft","ranks","measurements"},"manifest");
  if(str(at(root,"format"),"format")!=FORMAT)throw std::runtime_error("format");
  if(str(at(root,"contract"),"contract")!=CONTRACT)throw std::runtime_error("contract "+str(at(root,"contract"),"contract")+" (this engine reads v1.2+p184 two-card checkpoints only)");
  if(str(at(root,"label"),"label")!=LABEL)throw std::runtime_error("label does not pair with contract v1.2+p184 (expected experimental-two-card)");
  const auto& ops=at(root,"operations");
  if(ops.kind!=CJson::Array||ops.items.size()!=OPERATIONS.size())throw std::runtime_error("operations");
  for(size_t i=0;i<ops.items.size();++i)if(str(ops.items[i],"operations")!=OPERATIONS[i])throw std::runtime_error("operations");
  m.checkpoint_id=str(at(root,"checkpoint_id"),"checkpoint_id");if(!valid_id(m.checkpoint_id))throw std::runtime_error("checkpoint_id is not a valid id");
  m.created=str(at(root,"created"),"created");
  const auto& lineage=at(root,"lineage");keys(lineage,{"operation","parent"},"lineage");
  m.operation=str(at(lineage,"operation"),"lineage.operation");const auto& parent=at(lineage,"parent");
  if(m.operation=="save"){if(parent.kind!=CJson::Null)throw std::runtime_error("lineage: a plain save has no parent");}
  else if(m.operation=="restore-then-save") {
    keys(parent,{"checkpoint_id","manifest_sha256"},"lineage.parent");
    m.parent_id=str(at(parent,"checkpoint_id"),"lineage.parent.checkpoint_id");m.parent_sha=str(at(parent,"manifest_sha256"),"lineage.parent.manifest_sha256");
    if(!valid_id(m.parent_id)||!hex64(m.parent_sha))throw std::runtime_error("lineage.parent");
  } else throw std::runtime_error("lineage.operation "+m.operation);
  const auto& model=at(root,"model");keys(model,{"identity_tsv_sha256","shard_stat_rows","draft_manifest_sha256"},"model");
  m.identity_sha=str(at(model,"identity_tsv_sha256"),"model.identity_tsv_sha256");
  m.draft_manifest_sha=str(at(model,"draft_manifest_sha256"),"model.draft_manifest_sha256");
  if(!m.identity_sha.empty()&&!hex64(m.identity_sha))throw std::runtime_error("model.identity_tsv_sha256");
  if(!m.draft_manifest_sha.empty()&&!hex64(m.draft_manifest_sha))throw std::runtime_error("model.draft_manifest_sha256");
  const auto& rows=at(model,"shard_stat_rows");if(rows.kind!=CJson::Array)throw std::runtime_error("model.shard_stat_rows");
  for(const auto& r:rows.items){keys(r,{"name","size","dev","ino","mtime","ctime"},"shard_stat_row");
    std::ostringstream j;j<<"{\"name\":"<<quote(str(at(r,"name"),"name"))<<",\"size\":"<<integer(at(r,"size"),"size")<<",\"dev\":"<<integer(at(r,"dev"),"dev")
     <<",\"ino\":"<<integer(at(r,"ino"),"ino")<<",\"mtime\":"<<integer(at(r,"mtime"),"mtime")<<",\"ctime\":"<<integer(at(r,"ctime"),"ctime")<<"}";m.stat_rows_text.push_back(j.str());}
  if(m.identity_sha.empty()!=m.stat_rows_text.empty()||(!m.identity_sha.empty()&&m.stat_rows_text.size()!=3))throw std::runtime_error("model identity rows");
  const auto& engine=at(root,"engine");keys(engine,{"binary_sha256","packet","profile","selection_sha256","arithmetic","mini"},"engine");
  m.binary_sha=str(at(engine,"binary_sha256"),"engine.binary_sha256");if(!hex64(m.binary_sha))throw std::runtime_error("engine.binary_sha256");
  m.engine_packet=str(at(engine,"packet"),"engine.packet");m.engine_profile=str(at(engine,"profile"),"engine.profile");
  if(m.engine_packet!=PACKET||m.engine_profile!=PROFILE)throw std::runtime_error("engine packet/profile");
  m.selection_sha=str(at(engine,"selection_sha256"),"engine.selection_sha256");if(!m.selection_sha.empty()&&!hex64(m.selection_sha))throw std::runtime_error("engine.selection_sha256");
  m.arithmetic=str(at(engine,"arithmetic"),"engine.arithmetic");m.mini=boolean(at(engine,"mini"),"engine.mini");
  const auto& topo=at(root,"topology");keys(topo,{"ranks","draft_rank","target_split","layer_boundary"},"topology");
  m.ranks=integer(at(topo,"ranks"),"ranks");m.draft_rank=integer(at(topo,"draft_rank"),"draft_rank");
  m.target_split=integer(at(topo,"target_split"),"target_split");m.layer_boundary=integer(at(topo,"layer_boundary"),"layer_boundary");
  if(m.ranks!=2||m.draft_rank!=1)throw std::runtime_error("topology: two ranks with the MTP draft on rank 1 required");
  const auto& g=at(root,"geometry");
  keys(g,{"layers","qsa_layers","gdn_layers","h","kvh","ad","ih","id","qh","gdn","context","vocab","eos"},"geometry");
  m.qsa_layers=int_list(at(g,"qsa_layers"),"qsa_layers");m.gdn_layers=int_list(at(g,"gdn_layers"),"gdn_layers");
  m.h=integer(at(g,"h"),"h");m.kvh=integer(at(g,"kvh"),"kvh");m.ad=integer(at(g,"ad"),"ad");m.ih=integer(at(g,"ih"),"ih");
  m.g_id=integer(at(g,"id"),"id");m.qh=integer(at(g,"qh"),"qh");
  const auto& gdn=at(g,"gdn");keys(gdn,{"kh","vh","d"},"geometry.gdn");
  m.kh=integer(at(gdn,"kh"),"kh");m.vh=integer(at(gdn,"vh"),"vh");m.d=integer(at(gdn,"d"),"d");
  m.context=integer(at(g,"context"),"context");m.vocab=integer(at(g,"vocab"),"vocab");m.eos=integer(at(g,"eos"),"eos");
  if(integer(at(g,"layers"),"layers")!=int64_t(m.qsa_layers.size()+m.gdn_layers.size()))throw std::runtime_error("geometry.layers");
  if(m.context<1||m.vocab<1||m.eos<0||m.eos>=m.vocab)throw std::runtime_error("geometry bounds");
  const auto& dt=at(root,"dtypes");keys(dt,{"kv","gdn_state","ple","draft_kv"},"dtypes");
  for(const char* k:{"kv","gdn_state","ple","draft_kv"})if(str(at(dt,k),k)!="bf16")throw std::runtime_error(std::string("dtypes.")+k);
  const auto& ti=at(root,"tokenizer_identity");
  keys(ti,{"file_sha256","format","gguf_header_sha256","tokenizer_source_sha256","vocab_bin_sha256"},"tokenizer_identity");
  m.tokenizer.file_sha256=str(at(ti,"file_sha256"),"t.file_sha256");m.tokenizer.format=str(at(ti,"format"),"t.format");
  m.tokenizer.gguf_header_sha256=str(at(ti,"gguf_header_sha256"),"t.gguf");m.tokenizer.tokenizer_source_sha256=str(at(ti,"tokenizer_source_sha256"),"t.src");
  m.tokenizer.vocab_bin_sha256=str(at(ti,"vocab_bin_sha256"),"t.vocab");
  if(m.tokenizer.format!=TOKENIZER_IDENTITY_FORMAT)throw std::runtime_error("tokenizer_identity.format");
  for(const auto* v:{&m.tokenizer.file_sha256,&m.tokenizer.gguf_header_sha256,&m.tokenizer.tokenizer_source_sha256,&m.tokenizer.vocab_bin_sha256})
    if(!hex64(*v))throw std::runtime_error("tokenizer_identity hash");
  const auto& ts=at(root,"token_state");
  keys(ts,{"prompt_length","length","position","next_token","tokens_sha256","token_history"},"token_state");
  m.prompt_length=integer(at(ts,"prompt_length"),"prompt_length");m.length=integer(at(ts,"length"),"length");
  m.position=integer(at(ts,"position"),"position");m.next_token=integer(at(ts,"next_token"),"next_token");
  m.tokens_sha=str(at(ts,"tokens_sha256"),"tokens_sha256");
  const auto history=int_list(at(ts,"token_history"),"token_history");if(history.size()!=2)throw std::runtime_error("token_history must hold two tokens");
  m.history0=history[0];m.history1=history[1];
  if(m.position<1||m.position>=m.context)throw std::runtime_error("position outside context allocation");
  if(m.length!=m.position)throw std::runtime_error("length != position");
  if(m.prompt_length<1||m.prompt_length>m.position)throw std::runtime_error("prompt_length outside the processed prefix");
  if(m.next_token<0||m.next_token>=m.vocab)throw std::runtime_error("next_token outside vocabulary");
  if(!hex64(m.tokens_sha))throw std::runtime_error("tokens_sha256");
  const auto& sampler=at(root,"sampler");keys(sampler,{"mode","state"},"sampler");
  if(str(at(sampler,"mode"),"sampler.mode")!="greedy-argmax"||at(sampler,"state").kind!=CJson::Null)throw std::runtime_error("sampler");
  const auto& draft=at(root,"draft");keys(draft,{"policy","reason","rank","position","disabled","boundary_hidden_blob"},"draft");
  if(str(at(draft,"policy"),"draft.policy")!=DRAFT_POLICY||str(at(draft,"reason"),"draft.reason")!=DRAFT_REASON)throw std::runtime_error("draft policy");
  if(integer(at(draft,"rank"),"draft.rank")!=1||str(at(draft,"boundary_hidden_blob"),"draft.boundary_hidden_blob")!="rank1/streams")throw std::runtime_error("draft rank/boundary hidden blob");
  m.draft_position=integer(at(draft,"position"),"draft.position");m.draft_disabled=boolean(at(draft,"disabled"),"draft.disabled");
  if(m.draft_position<0||m.draft_position>m.position-1||(!m.draft_disabled&&m.draft_position!=m.position-1))throw std::runtime_error("draft position");
  const auto& ranks=at(root,"ranks");if(ranks.kind!=CJson::Array||ranks.items.size()!=2)throw std::runtime_error("ranks: exactly two rank states");
  for(size_t i=0;i<2;++i){auto s=parse_rank_state(ranks.items[i],"ranks["+std::to_string(i)+"]");if(s.rank!=int(i))throw std::runtime_error("rank order");m.rank_states.push_back(std::move(s));}
  // Cross-rank semantics: the rank layer sets partition the model; per-blob slices follow the token state.
  std::vector<int64_t> q,dn;for(const auto& s:m.rank_states){q.insert(q.end(),s.qsa_layers.begin(),s.qsa_layers.end());dn.insert(dn.end(),s.gdn_layers.begin(),s.gdn_layers.end());}
  std::sort(q.begin(),q.end());std::sort(dn.begin(),dn.end());
  if(q!=m.qsa_layers||dn!=m.gdn_layers)throw std::runtime_error("rank layer sets do not partition the geometry");
  {
    int64_t top0=0;for(auto x:m.rank_states[0].qsa_layers)top0=std::max(top0,x+1);for(auto x:m.rank_states[0].gdn_layers)top0=std::max(top0,x+1);
    for(auto x:m.rank_states[1].qsa_layers)if(x<top0)throw std::runtime_error("rank 1 layer below the rank boundary");
    for(auto x:m.rank_states[1].gdn_layers)if(x<top0)throw std::runtime_error("rank 1 layer below the rank boundary");
    if(m.layer_boundary!=top0)throw std::runtime_error("topology.layer_boundary differs from the rank 0 layer set");
  }
  int64_t total=0;
  for(const auto& s:m.rank_states) {
    if(s.rank==0&&(s.history0!=m.history0||s.history1!=m.history1))throw std::runtime_error("rank 0 host token history differs from token_state");
    if(s.draft_owner!=(s.rank==1))throw std::runtime_error("draft owner must be rank 1");
    if(s.rank==1&&(s.draft_position!=m.draft_position||s.draft_disabled!=m.draft_disabled))throw std::runtime_error("rank 1 draft host state differs from the manifest draft record");
    for(const auto& b:s.blobs) {
      total+=int64_t(b.bytes);
      const bool kv=kv_name(b.name.substr(b.source=="draft"?6:0));
      if(b.source=="draft"&&b.name.compare(0,6,"draft.")!=0)throw std::runtime_error("draft blob prefix "+b.name);
      if((b.source=="spare"&&b.name.compare(0,6,"spare.")!=0)||(b.source=="reserve"&&b.name.compare(0,8,"reserve.")!=0))throw std::runtime_error("bank blob prefix "+b.name);
      if(kv&&(b.source=="plan"||b.source=="draft")) {
        const int64_t rows=b.source=="draft"?m.draft_position:m.position;
        const int64_t want=suffix(b.name,".qsa.pooled")?rows/4:rows;
        if(b.rows!=want)throw std::runtime_error("blob slice rows "+b.name);
      } else if(b.rows!=-1)throw std::runtime_error("whole blob with a slice "+b.name);
    }
  }
  const auto& meas=at(root,"measurements");keys(meas,{"save_bytes","stage_seconds","commit_seconds"},"measurements");
  m.save_bytes=integer(at(meas,"save_bytes"),"save_bytes");if(m.save_bytes!=total)throw std::runtime_error("save_bytes != sum of both ranks' blob bytes");
  const auto& st=at(meas,"stage_seconds");if(st.kind!=CJson::Array||st.items.size()!=2)throw std::runtime_error("stage_seconds");
  for(size_t i=0;i<2;++i){if(st.items[i].kind!=CJson::Number)throw std::runtime_error("stage_seconds");m.stage_seconds_text[i]=st.items[i].text;}
  if(at(meas,"commit_seconds").kind!=CJson::Number)throw std::runtime_error("commit_seconds");m.commit_seconds_text=at(meas,"commit_seconds").text;
}
// fields.tsv: derived index rendered FROM the parsed manifest; never read as a source of values.
static std::string render_fields(const Manifest& m) {
  std::ostringstream f;
  auto row=[&](const char* k,const std::string& v){f<<k<<'\t'<<v<<'\n';};
  auto num=[&](const char* k,int64_t v){row(k,std::to_string(v));};
  row("format",FORMAT);row("label",LABEL);row("contract",CONTRACT);row("checkpoint_id",m.checkpoint_id);row("created",m.created);
  row("operation",m.operation);row("parent_checkpoint_id",m.parent_id);row("parent_manifest_sha256",m.parent_sha);
  num("position",m.position);num("prompt_length",m.prompt_length);num("length",m.length);num("next_token",m.next_token);
  row("tokens_sha256",m.tokens_sha);num("history0",m.history0);num("history1",m.history1);
  row("identity_tsv_sha256",m.identity_sha);row("draft_manifest_sha256",m.draft_manifest_sha);row("binary_sha256",m.binary_sha);
  row("selection_sha256",m.selection_sha);row("arithmetic",m.arithmetic);row("mini",m.mini?"true":"false");
  row("tokenizer_identity_sha256",m.tokenizer.file_sha256);
  num("ranks",m.ranks);num("draft_rank",m.draft_rank);num("target_split",m.target_split);num("layer_boundary",m.layer_boundary);
  num("h",m.h);num("kvh",m.kvh);num("ad",m.ad);num("ih",m.ih);num("id",m.g_id);num("kh",m.kh);num("vh",m.vh);num("d",m.d);num("qh",m.qh);
  num("context",m.context);num("vocab",m.vocab);num("eos",m.eos);row("qsa_layers",join(m.qsa_layers));row("gdn_layers",join(m.gdn_layers));
  row("draft_policy",DRAFT_POLICY);num("draft_position",m.draft_position);row("draft_disabled",m.draft_disabled?"true":"false");
  num("save_bytes",m.save_bytes);row("stage_seconds",m.stage_seconds_text[0]+","+m.stage_seconds_text[1]);row("commit_seconds",m.commit_seconds_text);
  row("manifest_sha256",m.sha256);
  for(const auto& s:m.rank_states) {
    f<<"rank\t"<<s.rank<<'\t'<<join(s.qsa_layers)<<'\t'<<join(s.gdn_layers)<<'\t'<<s.history0<<'\t'<<s.history1<<'\t'<<s.bank_parity<<'\t'<<s.active_bank<<'\t'<<s.spare_bank
     <<'\t'<<(s.miss_banks?1:0)<<'\t'<<s.launch_extent<<'\t'<<s.alternate_launch_extent<<'\t'<<(s.draft_owner?1:0)<<'\t'<<s.draft_position<<'\t'<<(s.draft_disabled?1:0)<<'\t'<<s.draft_context_extent<<'\n';
    for(const auto& b:s.blobs)f<<"blob\t"<<s.rank<<'\t'<<b.name<<'\t'<<b.source<<'\t'<<b.bytes<<'\t'<<b.sha256<<'\t'<<b.rows<<'\n';
    for(const auto& k:s.skipped)f<<"skip\t"<<s.rank<<'\t'<<k.label<<'\t'<<k.source<<'\t'<<k.rule<<'\n';
  }
  return f.str();
}
static std::set<std::string> rank_files(const RankState& s){std::set<std::string> out;for(const auto& b:s.blobs)out.insert(b.name+".bin");return out;}

// ---------------------------------------------------------------- load + verify
enum class Verify { metadata, tokens, full };
struct Load {
  Manifest m;std::vector<int> tokens;
  std::array<std::vector<std::pair<std::string,std::vector<uint8_t>>>,2> blobs;  // kept per rank on request
  uint64_t bytes_read=0,blobs_verified=0;
};
// verify_rank: -1 = hash both ranks (inspect, commit check); 0/1 = hash that rank fully and keep its
// bytes, check the other rank's files by size only (a rank restore; the peer hashes its own set).
static Load load(const fs::path& d,const std::string& expected_id,Verify mode,const std::string& op,int verify_rank,bool keep,
                 const std::function<void(int,const Blob&)>& progress=nullptr) {
  if(!fs::is_directory(fs::symlink_status(d)))refuse(op,"visibility","checkpoint directory missing: "+d.string());
  if(!fs::is_regular_file(fs::symlink_status(d/"manifest.json")))
    refuse(op,"visibility","manifest.json missing (partial, deleted or unverified checkpoint)");
  Load r;auto& m=r.m;
  const auto manifest_bytes=read_file(d/"manifest.json");m.text.assign(manifest_bytes.begin(),manifest_bytes.end());m.sha256=sha256_hex(manifest_bytes);
  try{manifest_fill(m);}catch(const Refusal&){throw;}catch(const std::exception& error){refuse(op,"manifest",error.what());}
  if(m.checkpoint_id!=expected_id)refuse(op,"manifest","checkpoint_id "+m.checkpoint_id+" does not name its directory "+expected_id);
  if(!fs::is_regular_file(fs::symlink_status(d/"fields.tsv")))refuse(op,"manifest cross-check","fields.tsv missing");
  const std::string tsv=read_text(d/"fields.tsv");
  {
    const std::string key="\nmanifest_sha256\t";const auto pos=tsv.find(key);
    if(pos==std::string::npos)refuse(op,"manifest cross-check","fields.tsv has no manifest_sha256 row");
    const auto end=tsv.find('\n',pos+key.size());
    if(tsv.substr(pos+key.size(),end-pos-key.size())!=m.sha256)refuse(op,"manifest sha256","manifest.json differs from the sha256 sealed at save");
  }
  const std::string rendered=render_fields(m);
  if(tsv!=rendered) {
    std::istringstream a{tsv},b{rendered};std::string la,lb;size_t line=0;
    while(true){++line;const bool ga=bool(std::getline(a,la)),gb=bool(std::getline(b,lb));if(!ga||!gb||la!=lb)break;}
    refuse(op,"manifest cross-check","fields.tsv line "+std::to_string(line)+" ("+la.substr(0,la.find('\t'))+") differs from the rendering of manifest.json; manifest.json is the only source of truth");
  }
  // Closed file sets: top level, then each rank directory (both ranks or none).
  std::set<std::string> top{"manifest.json","fields.tsv","tokens.bin","rank0","rank1"},seen;
  for(const auto& entry:fs::directory_iterator(d)) {
    const std::string n=entry.path().filename().string();
    if(!top.count(n))refuse(op,"file set","unexpected entry "+n+" (the directory holds only manifest.json, fields.tsv, tokens.bin, rank0/ and rank1/)");
    const bool dir=n=="rank0"||n=="rank1";
    if(dir?!fs::is_directory(entry.symlink_status()):!fs::is_regular_file(entry.symlink_status()))refuse(op,"file set","wrong entry type "+n);
    seen.insert(n);
  }
  for(const auto& n:top)if(!seen.count(n))refuse(op,"file set",n=="rank0"||n=="rank1"?"rank blob set missing: "+n:"missing file "+n);
  for(const auto& s:m.rank_states) {
    const auto expected=rank_files(s);std::set<std::string> have;
    for(const auto& entry:fs::directory_iterator(d/s.directory)) {
      const std::string n=entry.path().filename().string();
      if(!fs::is_regular_file(entry.symlink_status())||!expected.count(n))refuse(op,"file set","rank "+std::to_string(s.rank)+": unexpected entry "+n);
      have.insert(n);
    }
    for(const auto& n:expected)if(!have.count(n))refuse(op,"file set","rank "+std::to_string(s.rank)+" blob set mismatched: missing "+n);
  }
  if(mode==Verify::metadata)return r;
  const int64_t N=m.position;
  std::vector<uint8_t> token_bytes;
  try{token_bytes=read_file(d/"tokens.bin");}catch(const std::exception&){refuse(op,"blob read","tokens.bin");}
  if(token_bytes.size()!=size_t(N)*4)refuse(op,"token state","tokens.bin extent");
  if(sha256_hex(token_bytes)!=m.tokens_sha)refuse(op,"token state","tokens.bin sha256");
  r.bytes_read+=token_bytes.size();r.tokens.assign(size_t(N),0);
  for(int64_t i=0;i<N;++i){int32_t x;std::memcpy(&x,token_bytes.data()+4*i,4);
    if(x<0||x>=m.vocab)refuse(op,"token state","token outside vocabulary at index "+std::to_string(i));r.tokens[size_t(i)]=x;}
  const auto [h0,h1]=history_of(r.tokens,m.eos);
  if(m.history0!=h0||m.history1!=h1)refuse(op,"token state","manifest token_history disagrees with the last processed tokens in tokens.bin");
  if(mode==Verify::tokens)return r;
  std::array<std::map<std::string,std::vector<uint8_t>>,2> small;
  for(const auto& s:m.rank_states) {
    const bool hash_this=verify_rank<0||verify_rank==s.rank;
    for(const auto& b:s.blobs) {
      const fs::path p=d/s.directory/(b.name+".bin");
      if(!hash_this){std::error_code ec;const auto size=fs::file_size(p,ec);if(ec||size!=b.bytes)refuse(op,"blob bytes","rank "+std::to_string(s.rank)+" blob "+b.name+" (peer set)");continue;}
      std::vector<uint8_t> data;
      try{data=read_file(p);}catch(const std::exception&){refuse(op,"blob read","rank "+std::to_string(s.rank)+" "+b.name);}
      if(data.size()!=b.bytes)refuse(op,"blob bytes","rank "+std::to_string(s.rank)+" "+b.name);
      if(sha256_hex(data)!=b.sha256)refuse(op,"blob sha256","rank "+std::to_string(s.rank)+" "+b.name);
      r.bytes_read+=data.size();++r.blobs_verified;if(progress)progress(s.rank,b);
      if(data.size()<=16)small[size_t(s.rank)][b.name]=data;
      if(keep&&verify_rank==s.rank)r.blobs[size_t(s.rank)].emplace_back(b.name,std::move(data));
    }
  }
  // Semantic control-blob cross-checks for every hashed rank.
  auto i32=[&](int rank,const char* name,int64_t want,const char* what) {
    auto it=small[size_t(rank)].find(name);if(it==small[size_t(rank)].end())refuse(op,"completeness","rank "+std::to_string(rank)+" control blob missing: "+name);
    int32_t x=0;if(it->second.size()!=4)refuse(op,"token state",std::string(name)+" blob extent");std::memcpy(&x,it->second.data(),4);
    if(int64_t(x)!=want)refuse(op,"token state","rank "+std::to_string(rank)+": "+what);
  };
  for(int rank:{0,1}) {
    if(!(verify_rank<0||verify_rank==rank))continue;
    i32(rank,"position",N,"position blob disagrees with the manifest");
    i32(rank,"error",0,"sticky device error recorded in the checkpoint");
    i32(rank,"token",r.tokens[size_t(N-1)],"last stepped token blob disagrees with tokens.bin");
    if(rank==1){i32(rank,"next_token",m.next_token,"next_token blob disagrees with the manifest pending token");
      i32(rank,"draft.position",m.draft_position,"draft position blob disagrees with the manifest draft record");}
    if(rank==0) {
      auto it=small[0].find("token_history");if(it==small[0].end())refuse(op,"completeness","rank 0 control blob missing: token_history");
      int64_t x[2];if(it->second.size()!=16)refuse(op,"token state","token_history blob extent");std::memcpy(x,it->second.data(),16);
      if(x[0]!=h0||x[1]!=h1)refuse(op,"token state","token_history blob disagrees with tokens.bin");
    }
  }
  return r;
}

// ---------------------------------------------------------------- commit (device-free tool, save phase 2)
static std::string iso_now(){char iso[32];std::time_t now=std::time(nullptr);std::strftime(iso,sizeof iso,"%Y-%m-%dT%H:%M:%SZ",std::gmtime(&now));return iso;}
static std::string number_text(double v){std::ostringstream o;o.precision(17);o<<v;return o.str();}
static int commit_tool(const fs::path& target,const fs::path& tokenizer_path,int64_t prompt_length,const std::string& parent_id,const std::string& parent_sha) {
  const std::string op="save";const auto started=std::chrono::steady_clock::now();
  const auto [root,id]=split_dir(target);const fs::path d=root/id;
  bool ok=false;std::string check,detail,manifest_sha;uint64_t save_bytes=0;
  try {
    if(!valid_id(id))refuse(op,"id","invalid checkpoint id "+id);
    const auto tokenizer=tokenizer_identity(tokenizer_path,op);
    lock_held_proof(root,id,op);
    if(fs::exists(fs::symlink_status(d/"manifest.json")))refuse(op,"never overwrite","checkpoint "+id+" is already visible");
    if(parent_id.empty()!=parent_sha.empty()||(!parent_id.empty()&&(!valid_id(parent_id)||!hex64(parent_sha))))refuse(op,"lineage","parent id and manifest sha256 go together");
    std::array<CJson,2> stage;std::array<std::string,2> stage_text;
    for(int r:{0,1}){stage_text[size_t(r)]=read_text(d/("rank"+std::to_string(r))/"stage.json");
      try{stage[size_t(r)]=parse_json(stage_text[size_t(r)]);}catch(const std::exception& e){refuse(op,"stage","rank "+std::to_string(r)+" stage receipt: "+e.what());}}
    auto facts=[&](int r,const char* k)->const CJson&{return at(stage[size_t(r)],k);};
    for(const char* k:{"identity_tsv_sha256","binary_sha256","selection_sha256","arithmetic","tokens_sha256"})
      if(str(facts(0,k),k)!=str(facts(1,k),k))refuse(op,"two-card identity",std::string("ranks disagree on ")+k);
    for(const char* k:{"position","pending","draft_rank","target_split"})
      if(integer(facts(0,k),k)!=integer(facts(1,k),k))refuse(op,"two-card identity",std::string("ranks disagree on ")+k);
    if(boolean(facts(0,"mini"),"mini")!=boolean(facts(1,"mini"),"mini"))refuse(op,"two-card identity","ranks disagree on mini");
    if(integer(facts(0,"rank"),"rank")!=0||integer(facts(1,"rank"),"rank")!=1)refuse(op,"two-card identity","stage receipts are not rank 0 and rank 1");
    // The commit tool is the device-free tool binary: it records the engine binary both ranks
    // reported (they must agree); each rank re-checks it against /proc/self/exe at restore.
    const std::string binary=str(facts(0,"binary_sha256"),"binary_sha256");
    if(!hex64(binary))refuse(op,"engine identity","staged engine binary sha256");
    // Geometry objects must be byte-equal between ranks (same model, same binary).
    {std::ostringstream a,b;auto dump=[&](std::ostream& o,const CJson& g){for(size_t i=0;i<g.keys.size();++i)o<<g.keys[i]<<'='<<g.items[i].text<<';';};
     dump(a,facts(0,"geometry"));dump(b,facts(1,"geometry"));if(a.str()!=b.str())refuse(op,"two-card identity","ranks disagree on geometry");}
    const int64_t N=integer(facts(0,"position"),"position"),pending=integer(facts(0,"pending"),"pending");
    const auto& geom=facts(0,"geometry");const int64_t vocab=integer(at(geom,"vocab"),"vocab"),eos=integer(at(geom,"eos"),"eos");
    if(prompt_length<1||prompt_length>N)refuse(op,"token state","--prompt-length outside the processed prefix");
    const auto token_bytes=read_file(d/"tokens.bin");if(token_bytes.size()!=size_t(N)*4||sha256_hex(token_bytes)!=str(facts(0,"tokens_sha256"),"tokens_sha256"))refuse(op,"token state","tokens.bin changed after staging");
    std::vector<int> tokens(static_cast<size_t>(N),0);for(int64_t i=0;i<N;++i){int32_t x;std::memcpy(&x,token_bytes.data()+4*i,4);tokens[size_t(i)]=x;}
    const auto [h0,h1]=history_of(tokens,eos);
    // Re-hash both ranks' staged blobs against their stage receipts.
    std::array<std::string,2> rank_text;uint64_t total=0;
    for(int r:{0,1}) {
      const auto& rs=facts(r,"rank_state");RankState s;
      try{s=parse_rank_state(rs,"stage rank "+std::to_string(r));}catch(const std::exception& e){refuse(op,"stage","rank "+std::to_string(r)+": "+e.what());}
      if(s.rank!=r)refuse(op,"stage","rank "+std::to_string(r)+" stage rank state");
      std::set<std::string> want=rank_files(s);want.insert("stage.json");std::set<std::string> have;
      for(const auto& entry:fs::directory_iterator(d/s.directory)){const auto n=entry.path().filename().string();
        if(!want.count(n)||!fs::is_regular_file(entry.symlink_status()))refuse(op,"file set","rank "+std::to_string(r)+": unexpected staged entry "+n);have.insert(n);}
      if(have!=want)refuse(op,"file set","rank "+std::to_string(r)+" staged blob set incomplete");
      for(const auto& b:s.blobs){const auto data=read_file(d/s.directory/(b.name+".bin"));
        if(data.size()!=b.bytes||sha256_hex(data)!=b.sha256)refuse(op,"blob sha256","rank "+std::to_string(r)+" staged blob "+b.name+" changed before commit");total+=b.bytes;}
      // Re-serialize this rank's state exactly as staged (the stage receipt's own bytes).
      const auto& t=stage_text[size_t(r)];const auto k=t.find("\"rank_state\":");const auto e=t.find(",\"coverage\":");
      if(k==std::string::npos||e==std::string::npos||e<k)refuse(op,"stage","rank "+std::to_string(r)+" stage receipt layout");
      rank_text[size_t(r)]=t.substr(k+13,e-k-13);
    }
    const auto& rs1=at(facts(1,"rank_state"),"host_state");
    const int64_t draft_position=integer(at(rs1,"draft_position"),"draft_position");const bool draft_disabled=boolean(at(rs1,"draft_disabled"),"draft_disabled");
    std::vector<int64_t> qsa,gdn;
    for(int r:{0,1}){const auto& rs=facts(r,"rank_state");for(auto x:int_list(at(rs,"qsa_layers"),"q"))qsa.push_back(x);for(auto x:int_list(at(rs,"gdn_layers"),"g"))gdn.push_back(x);}
    std::sort(qsa.begin(),qsa.end());std::sort(gdn.begin(),gdn.end());
    int64_t boundary=0;   // first layer owned by rank 1 = one past rank 0's highest layer
    for(const char* k:{"qsa_layers","gdn_layers"})for(auto x:int_list(at(facts(0,"rank_state"),k),k))boundary=std::max(boundary,x+1);
    const double stage0=std::stod(at(stage[0],"stage_seconds").text),stage1=std::stod(at(stage[1],"stage_seconds").text);
    const double commit_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
    std::ostringstream m;
    m<<"{\"format\":"<<quote(FORMAT)<<",\"label\":"<<quote(LABEL)<<",\"contract\":"<<quote(CONTRACT)<<",\"operations\":[";
    for(size_t i=0;i<OPERATIONS.size();++i)m<<(i?",":"")<<quote(OPERATIONS[i]);
    m<<"],\"checkpoint_id\":"<<quote(id)<<",\"created\":"<<quote(iso_now())
     <<",\"lineage\":{\"operation\":"<<quote(parent_id.empty()?"save":"restore-then-save")<<",\"parent\":";
    if(parent_id.empty())m<<"null";else m<<"{\"checkpoint_id\":"<<quote(parent_id)<<",\"manifest_sha256\":"<<quote(parent_sha)<<"}";
    m<<"},\"model\":{\"identity_tsv_sha256\":"<<quote(str(facts(0,"identity_tsv_sha256"),"i"))<<",\"shard_stat_rows\":[";
    {const auto& rows=facts(0,"shard_stat_rows");for(size_t i=0;i<rows.items.size();++i){const auto& r=rows.items[i];
      m<<(i?",":"")<<"{\"name\":"<<quote(str(at(r,"name"),"name"))<<",\"size\":"<<at(r,"size").text<<",\"dev\":"<<at(r,"dev").text<<",\"ino\":"<<at(r,"ino").text
       <<",\"mtime\":"<<at(r,"mtime").text<<",\"ctime\":"<<at(r,"ctime").text<<"}";}}
    m<<"],\"draft_manifest_sha256\":"<<quote(str(facts(1,"draft_manifest_sha256"),"d"))<<"}"
     <<",\"engine\":{\"binary_sha256\":"<<quote(binary)<<",\"packet\":"<<quote(PACKET)<<",\"profile\":"<<quote(PROFILE)
     <<",\"selection_sha256\":"<<quote(str(facts(0,"selection_sha256"),"s"))<<",\"arithmetic\":"<<quote(str(facts(0,"arithmetic"),"a"))
     <<",\"mini\":"<<(boolean(facts(0,"mini"),"mini")?"true":"false")<<"}"
     <<",\"topology\":{\"ranks\":2,\"draft_rank\":"<<integer(facts(0,"draft_rank"),"dr")<<",\"target_split\":"<<integer(facts(0,"target_split"),"ts")<<",\"layer_boundary\":"<<boundary<<"}"
     <<",\"geometry\":{\"layers\":"<<(qsa.size()+gdn.size())<<",\"qsa_layers\":["<<join(qsa)<<"],\"gdn_layers\":["<<join(gdn)<<"]"
     <<",\"h\":"<<at(geom,"h").text<<",\"kvh\":"<<at(geom,"kvh").text<<",\"ad\":"<<at(geom,"ad").text<<",\"ih\":"<<at(geom,"ih").text<<",\"id\":"<<at(geom,"id").text
     <<",\"qh\":"<<at(geom,"qh").text<<",\"gdn\":{\"kh\":"<<at(geom,"kh").text<<",\"vh\":"<<at(geom,"vh").text<<",\"d\":"<<at(geom,"d").text<<"}"
     <<",\"context\":"<<at(geom,"context").text<<",\"vocab\":"<<vocab<<",\"eos\":"<<eos<<"}"
     <<",\"dtypes\":{\"kv\":\"bf16\",\"gdn_state\":\"bf16\",\"ple\":\"bf16\",\"draft_kv\":\"bf16\"}"
     <<",\"tokenizer_identity\":{\"file_sha256\":"<<quote(tokenizer.file_sha256)<<",\"format\":"<<quote(tokenizer.format)
     <<",\"gguf_header_sha256\":"<<quote(tokenizer.gguf_header_sha256)<<",\"tokenizer_source_sha256\":"<<quote(tokenizer.tokenizer_source_sha256)
     <<",\"vocab_bin_sha256\":"<<quote(tokenizer.vocab_bin_sha256)<<"}"
     <<",\"token_state\":{\"prompt_length\":"<<prompt_length<<",\"length\":"<<N<<",\"position\":"<<N<<",\"next_token\":"<<pending
     <<",\"tokens_sha256\":"<<quote(sha256_hex(token_bytes))<<",\"token_history\":["<<h0<<","<<h1<<"]}"
     <<",\"sampler\":{\"mode\":\"greedy-argmax\",\"state\":null}"
     <<",\"draft\":{\"policy\":"<<quote(DRAFT_POLICY)<<",\"reason\":"<<quote(DRAFT_REASON)<<",\"rank\":1,\"position\":"<<draft_position
     <<",\"disabled\":"<<(draft_disabled?"true":"false")<<",\"boundary_hidden_blob\":\"rank1/streams\"}"
     <<",\"ranks\":["<<rank_text[0]<<","<<rank_text[1]<<"]"
     <<",\"measurements\":{\"save_bytes\":"<<total<<",\"stage_seconds\":["<<number_text(stage0)<<","<<number_text(stage1)<<"],\"commit_seconds\":"<<number_text(commit_seconds)<<"}}\n";
    if(pending<0||pending>=vocab)refuse(op,"token state","pending token outside vocabulary");
    // Round trip through the same strict reader restore uses; fields.tsv is rendered from that parse.
    Manifest parsed;parsed.text=m.str();parsed.sha256=sha256_hex(std::vector<uint8_t>(parsed.text.begin(),parsed.text.end()));
    try{manifest_fill(parsed);}catch(const std::exception& error){refuse(op,"manifest round trip",error.what());}
    require(parsed.position==N&&parsed.next_token==pending&&parsed.history0==h0&&parsed.history1==h1&&parsed.checkpoint_id==id&&
            parsed.save_bytes==int64_t(total)&&parsed.binary_sha==binary,"checkpoint manifest round trip differs");
    write_text(d/"manifest.json.tmp",parsed.text);
    write_text(d/"fields.tsv",render_fields(parsed));
    for(int r:{0,1}){fs::remove(d/("rank"+std::to_string(r))/"stage.json");fsync_dir(d/("rank"+std::to_string(r)));}
    fs::rename(d/"manifest.json.tmp",d/"manifest.json");   // visibility point
    fsync_dir(d);fsync_dir(root);
    manifest_sha=parsed.sha256;save_bytes=total;ok=true;
  } catch(const Refusal& r){check=r.check;detail=r.detail;}
    catch(const std::exception& error){check="io";detail=error.what();}
  std::ostringstream o;o.precision(17);
  o<<"{\"schema\":\"ownrt.checkpoint-commit.v1\",\"ok\":"<<(ok?"true":"false")<<",\"checkpoint_dir\":"<<quote(d.string())<<",\"checkpoint_id\":"<<quote(id);
  if(ok)o<<",\"manifest_sha256\":"<<quote(manifest_sha)<<",\"save_bytes\":"<<save_bytes<<",\"commit_seconds\":"
         <<std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count()<<",\"error\":null}";
  else o<<",\"manifest_sha256\":null,\"error\":{\"check\":"<<quote(check)<<",\"detail\":"<<quote(detail)<<"}}";
  std::cout<<o.str()<<"\n"<<std::flush;return ok?0:1;
}

// ---------------------------------------------------------------- input classification (restore)
static bool stop_token(int64_t token,int64_t eos,bool mini){return token==eos||(!mini&&token==248046);}
// Operation by --input shape (packet181 semantics, two-card controller bounds):
//   length == prompt_length, equal to the recorded prompt           -> same-generation resume
//   length >= N+1, input[0:N] == tokens.bin, input[N] == pending t    -> append (delta = input[N+1:])
// The two-card controller steps positions [N, len(input)+max_new-1) after the restore; its prompt is
// the full history (saved N tokens, then the pending token, then the delta).
static std::pair<std::string,size_t> classify_input(const Manifest& m,const std::vector<int>& tokens,const std::vector<int>& input,
                                                    int64_t max_new,bool mini,const std::string& op) {
  const int64_t N=m.position;const size_t plen=size_t(m.prompt_length);
  auto first_mismatch=[&](size_t n)->int64_t{for(size_t i=0;i<n;++i)if(input[i]!=tokens[i])return int64_t(i);return -1;};
  if(max_new<1)refuse(op,"request","--max-new must be positive");
  if(input.size()==plen) {
    const int64_t mis=first_mismatch(plen);
    if(mis>=0)refuse(op,"prefix","same-generation resume: --input differs from the recorded original prompt at index "+std::to_string(mis));
    if(stop_token(m.next_token,m.eos,mini))refuse(op,"ended generation","same-generation resume: the saved generation already ended with stop token "+std::to_string(m.next_token)+
        "; continue with append (--input = saved history + that token + the new turn)");
    if(N+1+max_new>m.context)refuse(op,"context","same-generation resume of "+std::to_string(N)+" saved positions plus the pending token plus --max-new "+std::to_string(max_new)+
        " exceeds the context allocation "+std::to_string(m.context));
    return {"same-generation-resume",0};
  }
  if(input.size()>=size_t(N)+1) {
    const int64_t mis=first_mismatch(size_t(N));
    if(mis>=0)refuse(op,"prefix","append: --input differs from the saved processed history at index "+std::to_string(mis)+
        " (saved "+std::to_string(tokens[size_t(mis)])+", given "+std::to_string(input[size_t(mis)])+")");
    if(input[size_t(N)]!=int(m.next_token))refuse(op,"prefix","append: --input["+std::to_string(N)+"] must be the saved pending token "+std::to_string(m.next_token)+
        " (given "+std::to_string(input[size_t(N)])+")");
    if(int64_t(input.size())+max_new>m.context)refuse(op,"context","append: --input length plus --max-new exceeds the context allocation "+std::to_string(m.context));
    return {"append",input.size()-size_t(N)-1};
  }
  refuse(op,"prefix","--input length "+std::to_string(input.size())+" is neither the recorded prompt length "+std::to_string(plen)+
      " (same-generation resume) nor at least "+std::to_string(N+1)+" (saved history plus the pending token; append)");
}
// The controller prompt of a restored request: same-generation resume steps history+pending; an
// append's --input already is history+pending+delta.
static std::vector<int> controller_prompt(const std::vector<int>& tokens,const Manifest& m,const std::vector<int>& input,const std::string& operation) {
  if(operation=="append")return input;
  std::vector<int> out=tokens;out.push_back(int(m.next_token));return out;
}

// ---------------------------------------------------------------- device-free host tools
static int inspect_tool(const fs::path& target,bool metadata) {
  const std::string op="inspect",mode=metadata?"metadata":"full";
  const auto [root,id]=split_dir(target);const fs::path dir=root/id;
  std::cerr<<"{\"event\":\"inspect-start\",\"mode\":"<<quote(mode)<<",\"checkpoint_dir\":"<<quote(dir.string())<<"}"<<std::endl;
  bool ok=false;std::string check,detail;Load loaded;
  try {
    if(!valid_id(id))refuse(op,"visibility","directory name is not a checkpoint id");
    if(!fs::is_directory(fs::symlink_status(dir))||!fs::is_regular_file(fs::symlink_status(dir/"manifest.json")))
      refuse(op,"visibility","manifest.json missing (partial, deleted or unverified checkpoint)");
    Lock lock(root,id,false,op);
    loaded=load(dir,id,metadata?Verify::metadata:Verify::full,op,-1,false,[&](int rank,const Blob& b){
      std::cerr<<"{\"event\":\"blob-verified\",\"rank\":"<<rank<<",\"name\":"<<quote(b.name)<<",\"bytes\":"<<b.bytes<<"}\n";});
    ok=true;
  } catch(const Refusal& r){check=r.check;detail=r.detail;}
    catch(const std::exception& error){check="io";detail=error.what();}
  std::ostringstream o;
  o<<"{\"schema\":\"ownrt.checkpoint-inspect.v1\",\"ok\":"<<(ok?"true":"false")<<",\"mode\":"<<quote(mode)
   <<",\"device_required\":false,\"checkpoint_dir\":"<<quote(dir.string())<<",\"checkpoint_id\":"<<quote(id);
  if(ok) {
    std::string manifest=loaded.m.text;while(!manifest.empty()&&(manifest.back()=='\n'||manifest.back()==' '))manifest.pop_back();
    o<<",\"label\":"<<quote(LABEL)<<",\"contract\":"<<quote(CONTRACT)<<",\"manifest_sha256\":"<<quote(loaded.m.sha256)
     <<",\"verified\":{\"manifest_seal\":true,\"fields_tsv_cross_check\":true,\"file_set_closed\":true,\"both_rank_sets_present\":true,\"tokens\":"<<(metadata?"null":"true")
     <<",\"semantic_blob_checks\":"<<(metadata?"null":"true")<<",\"blobs_verified\":";
    if(metadata)o<<"null,\"blob_bytes_verified\":null";else o<<loaded.blobs_verified<<",\"blob_bytes_verified\":"<<loaded.bytes_read;
    o<<"},\"manifest\":"<<manifest<<",\"error\":null}";
  } else o<<",\"manifest\":null,\"error\":{\"check\":"<<quote(check)<<",\"detail\":"<<quote(detail)<<"}}";
  std::cout<<o.str()<<"\n"<<std::flush;
  std::cerr<<"{\"event\":\"inspect-end\",\"ok\":"<<(ok?"true":"false")<<"}"<<std::endl;
  return ok?0:1;
}
static int delete_tool(const fs::path& target) {
  const std::string op="delete";
  const auto [root,id]=split_dir(target);const fs::path dir=root/id;
  bool deleted=false;std::string reason,check,detail;size_t removed=0;
  try {
    // Validate the target as a complete two-card checkpoint WITHOUT creating or taking a lock.
    try {
      if(!valid_id(id))refuse(op,"target","directory name is not a checkpoint id");
      load(dir,id,Verify::metadata,op,-1,false);
    } catch(const Refusal&){reason="not_a_checkpoint";throw;}
    std::unique_ptr<Lock> lock;
    try{lock=std::make_unique<Lock>(root,id,true,op);}
    catch(const Refusal& r){reason=r.check=="lock"?"in_use":"io";throw;}
    reason="not_a_checkpoint";
    const auto loaded=load(dir,id,Verify::metadata,op,-1,false);
    reason="io";
    require(fs::remove(dir/"manifest.json"),"delete manifest.json");++removed;   // invisible first
    for(const char* n:{"fields.tsv","tokens.bin"}){require(fs::remove(dir/n),std::string("delete ")+n);++removed;}
    for(const auto& s:loaded.m.rank_states){for(const auto& n:rank_files(s)){require(fs::remove(dir/s.directory/n),"delete "+n);++removed;}
      require(fs::remove(dir/s.directory),"delete rank directory "+s.directory);}
    require(fs::remove(dir),"delete directory "+dir.string());
    fsync_dir(root);lock->unlink_while_held();
    deleted=true;reason.clear();
  } catch(const Refusal& r){check=r.check;detail=r.detail;if(reason.empty())reason="io";}
    catch(const std::exception& error){check="io";detail=error.what();if(reason.empty())reason="io";}
  std::ostringstream o;
  o<<"{\"schema\":\"ownrt.checkpoint-delete.v1\",\"ok\":"<<(deleted?"true":"false")<<",\"deleted\":"<<(deleted?"true":"false")
   <<",\"checkpoint_dir\":"<<quote(dir.string())<<",\"checkpoint_id\":"<<quote(id)<<",\"files_removed\":"<<removed<<",\"reason\":";
  if(deleted)o<<"null,\"error\":null}";
  else o<<quote(reason)<<",\"error\":{\"check\":"<<quote(check)<<",\"detail\":"<<quote(detail)<<"}}";
  std::cout<<o.str()<<"\n"<<std::flush;return deleted?0:1;
}
// argv form: --checkpoint-inspect DIR | --checkpoint-inspect-metadata DIR | --checkpoint-delete DIR |
//            --checkpoint-commit DIR --tokenizer-identity FILE --prompt-length P [--parent-id ID --parent-manifest-sha256 SHA]
// Returns -1 when argv is not a host-tool invocation.
static int host_tool(int argc,char** argv) {
  if(argc<3)return -1;const std::string verb=argv[1];
  if(verb!="--checkpoint-inspect"&&verb!="--checkpoint-inspect-metadata"&&verb!="--checkpoint-delete"&&verb!="--checkpoint-commit")return -1;
  const fs::path target=argv[2];
  if(verb=="--checkpoint-delete"){require(argc==3,"--checkpoint-delete DIR takes no other arguments");return delete_tool(target);}
  if(verb=="--checkpoint-inspect"||verb=="--checkpoint-inspect-metadata"){require(argc==3,"inspect takes DIR only");return inspect_tool(target,verb=="--checkpoint-inspect-metadata");}
  fs::path tokenizer;int64_t prompt_length=-1;std::string parent_id,parent_sha;
  for(int i=3;i<argc;++i) {
    const std::string k=argv[i];require(i+1<argc,"missing value for "+k);const std::string v=argv[++i];
    if(k=="--tokenizer-identity")tokenizer=v;else if(k=="--prompt-length")prompt_length=std::stoll(v);
    else if(k=="--parent-id")parent_id=v;else if(k=="--parent-manifest-sha256")parent_sha=v;
    else throw std::runtime_error("unknown --checkpoint-commit option "+k);
  }
  return commit_tool(target,tokenizer,prompt_length,parent_id,parent_sha);
}

}} // namespace pipeline::ckpt184
