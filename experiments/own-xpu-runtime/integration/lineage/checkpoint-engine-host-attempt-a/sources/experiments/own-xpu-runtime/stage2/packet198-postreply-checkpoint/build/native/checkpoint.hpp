// packet181 session checkpoint/restore v3 -- label "experimental-postreply-front" (SESSION-SWAP-DESIGN.md v1.2 +
// packet181 README "Operation semantics"). Entry-TU-only native delta: included solely by main.cpp via
// a relative quote include; no kernel arithmetic. TP1 (one-card) only.
//
// packet181 over packet180 (v1.2+p180 -> v1.2+p181):
//   * manifests carry label "experimental-postreply-front" and a qualified_by object naming the device gates
//     the operations passed (packet179 same-generation resume, packet180 append and
//     restore-then-save, both 2026-10-22, one card) and the scope (one card only; TP2 checkpoints
//     not implemented; no ctxkeeper adapter yet);
//   * the reader also accepts packet180's v1.2+p180 manifests (label "experimental", no
//     qualified_by). Label and contract must pair; whether a checkpoint can be restored is decided
//     by the identity and semantic checks below (binary, geometry, model, tokenizer, token state,
//     blobs), never by the label;
//   * every result.json records how its prompt positions were stepped. This engine has exactly one
//     prompt mechanism, "incremental": one position per step through the prompt step (final
//     norm/logits/argmax skipped except on the last input position), used identically for a fresh
//     prompt and for appended tokens after a restore. There is no chunked/batched prefill here.
//
// Operations (exact CLI and JSON schemas in the packet README):
//   save                    --checkpoint-save ROOT --checkpoint-id ID --tokenizer-identity FILE
//   same-generation resume  --checkpoint-restore ROOT --checkpoint-id ID --input <original prompt>
//   append                  --checkpoint-restore ROOT --checkpoint-id ID --input <saved history + pending + delta>
//   restore-then-save       a restore form plus --checkpoint-save ROOT2 --checkpoint-save-id ID2
//   inspect                 --checkpoint-inspect DIR | --checkpoint-inspect-metadata DIR  (device-free)
//   delete                  --checkpoint-delete DIR                                       (device-free)
// manifest.json is the single source of truth. It is parsed once by the strict parser below;
// fields.tsv is a derived index rendered FROM the parsed manifest at save and must equal that
// rendering byte for byte at every load, so a TSV-only edit (for example history0) is refused
// before any device upload. The checkpoint directory's file set is closed: manifest.json,
// fields.tsv, tokens.bin and one <name>.bin per manifest blob, nothing else.
// Locking: one sibling lock file ROOT/ID.lock outside the checkpoint directory (flock; shared
// for restore/inspect, exclusive for save/delete; never blocks: a busy lock is a refusal). It is
// held across every read of a restore or inspect and across the whole save and delete; delete
// validates its target as a checkpoint before creating or taking any lock.
//
// Slicing/completeness rules are unchanged from packet179: QSA keys/values/raw rows [0:N) on the
// dim0 position axis, pooled rows [0:N/4) floor (engine precedent: strict_snapshot.hpp valid_rows
// and the pool-completion quad rule in kernels.hpp; partial-quad state is whole in raw/keys/
// values). GDN history/state, PLE history, token_history (device-mutated shift register,
// restored verbatim) and controls are whole. Skipped by name: qsa ids (scratch, recomputed per
// token by qsa_select), ple_metadata (static GGUF-derived, re-put by the request reset, covered
// by the model-identity check). Every plan buffer must match exactly one saved/named-skip/
// intermediate rule or the save refuses (completeness proof). e.logical is ordering-relative,
// reset to zero in both arms, and deliberately not persisted.
#include <fcntl.h>
#include <sys/file.h>
#include <cerrno>
#include <cstring>
#include <cstdlib>
#include <functional>
namespace pipeline {

static const char* const CHECKPOINT_FORMAT="ownrt.session-checkpoint.v1";
static const char* const CHECKPOINT_LABEL="experimental-postreply-front";
static const char* const CHECKPOINT_CONTRACT="v1.2+p198";
static const char* const CHECKPOINT_PACKET="packet198-postreply-checkpoint";
// packet180 manifests stay readable (inspect, delete, and restore when every identity check passes).
static const char* const CHECKPOINT_LEGACY_LABEL="experimental";
static const char* const CHECKPOINT_LEGACY_CONTRACT="v1.2+p180";
// Written verbatim into every v1.2+p181 manifest and required byte-structurally equal on read.
// New transport/binary is unqualified; these inherited field names do not assert a device gate.
static const char* const CHECKPOINT_QUALIFIED_BY="{\"scope\":\"experimental postreply checkpoint front; no device qualification\",\"device_gates\":[]}";
// The only prompt mechanism of this engine (see the header comment); recorded in result.json.
static const char* const CHECKPOINT_PREFILL_PATH="incremental";
static const char* const TOKENIZER_IDENTITY_FORMAT="ownrt.tokenizer-identity.v1";
static const std::vector<std::string> CHECKPOINT_OPERATIONS{"same-generation-resume","append","restore-then-save"};

// A refusal names the operation, the failed check and a detail. Every restore refusal is raised
// before the first device upload.
struct CheckpointRefusal : std::runtime_error {
  std::string check, detail;
  CheckpointRefusal(const std::string& op,const std::string& c,const std::string& d)
    : std::runtime_error("checkpoint "+op+" refused: "+c+": "+d),check(c),detail(d) {}
};
[[noreturn]] static void checkpoint_refuse(const std::string& op,const std::string& check,const std::string& detail) {
  throw CheckpointRefusal(op,check,detail);
}

static bool checkpoint_valid_id(const std::string& id) {
  if(id.empty()||id.size()>64)return false;
  auto alnum=[](char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9');};
  if(!alnum(id[0]))return false;
  for(char c:id)if(!alnum(c)&&c!='.'&&c!='_'&&c!='-')return false;
  return !(id.size()>=5&&id.compare(id.size()-5,5,".lock")==0);  // reserved for sibling locks
}
static bool checkpoint_hex64(const std::string& s) {
  if(s.size()!=64)return false;
  for(char c:s)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
  return true;
}

// ---------------------------------------------------------------- strict JSON (reader)
struct CJson {
  enum Kind {Null,Bool,Number,String,Array,Object};
  Kind kind=Null; bool boolean=false; std::string text;   // number literal or decoded string
  std::vector<CJson> items;                               // array elements, or object values
  std::vector<std::string> keys;                          // object keys, parallel to items
  const CJson* find(const std::string& k) const;
};
inline const CJson* CJson::find(const std::string& k) const {
  for(size_t j=0;j<keys.size();++j)if(keys[j]==k)return &items[j];
  return nullptr;
}
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
static CJson checkpoint_parse_json(const std::string& text) {
  CJsonParser p(text);CJson v=p.value();p.ws();
  if(p.i!=text.size())p.fail("trailing bytes after the manifest object");
  return v;
}
static const CJson& cj_at(const CJson& o,const std::string& k) {
  if(o.kind!=CJson::Object)throw std::runtime_error("expected an object holding "+k);
  const CJson* v=o.find(k);if(!v)throw std::runtime_error("field missing: "+k);
  return *v;
}
static const std::string& cj_str(const CJson& v,const std::string& what) {
  if(v.kind!=CJson::String)throw std::runtime_error("not a string: "+what);return v.text;
}
static int64_t cj_int(const CJson& v,const std::string& what) {
  if(v.kind!=CJson::Number)throw std::runtime_error("not a number: "+what);
  const auto& t=v.text;const size_t k=t[0]=='-'?1:0;
  if(t.size()<=k||t.size()>18)throw std::runtime_error("integer out of range: "+what);
  for(size_t j=k;j<t.size();++j)if(t[j]<'0'||t[j]>'9')throw std::runtime_error("not an integer: "+what);
  return std::stoll(t);
}
static void cj_keys(const CJson& o,std::initializer_list<const char*> keys,const std::string& what) {
  if(o.kind!=CJson::Object)throw std::runtime_error("not an object: "+what);
  if(o.keys.size()!=keys.size())throw std::runtime_error("unexpected key set in "+what);
  for(const char* k:keys)if(!o.find(k))throw std::runtime_error("field missing: "+what+"."+k);
}
// Structural equality (kind, literal text, key order, items); used for the qualified_by record.
static bool cj_equal(const CJson& a,const CJson& b) {
  if(a.kind!=b.kind||a.boolean!=b.boolean||a.text!=b.text||a.keys!=b.keys||a.items.size()!=b.items.size())return false;
  for(size_t i=0;i<a.items.size();++i)if(!cj_equal(a.items[i],b.items[i]))return false;
  return true;
}

// ---------------------------------------------------------------- shared helpers (packet179)
static bool checkpoint_suffix(const std::string& s,const std::string& suffix) {
  return s.size()>=suffix.size()&&s.compare(s.size()-suffix.size(),std::string::npos,suffix)==0;
}
static std::string checkpoint_rule(const std::string& name) {
  static const std::set<std::string> controls{"token","position","active","error","next_token","streams"};
  if(checkpoint_suffix(name,".qsa.keys")||checkpoint_suffix(name,".qsa.values")||
     checkpoint_suffix(name,".qsa.raw")||checkpoint_suffix(name,".qsa.pooled"))return "saved-sliced-kv";
  if(checkpoint_suffix(name,".gdn.history")||checkpoint_suffix(name,".gdn.state")||
     checkpoint_suffix(name,".ple.history")||name=="token_history"||controls.count(name))return "saved-whole";
  if(checkpoint_suffix(name,".qsa.ids"))return "skip: qsa ids scratch, recomputed per token by qsa_select";
  if(name=="ple_metadata")return "skip: static GGUF-derived, re-put by request reset; covered by model identity";
  for(const char* bad:{"history","state","keys","values","raw","pooled","metadata","token"})
    require(name.find(bad)==std::string::npos,"checkpoint completeness proof failed: unclassified persistent-looking buffer "+name);
  return "skip: plan intermediate fully rewritten every token step";
}
static size_t checkpoint_slice_bytes(const Engine& e,const std::string& name,size_t full,int64_t N) {
  const auto& g=e.p.g;
  if(checkpoint_suffix(name,".qsa.keys")||checkpoint_suffix(name,".qsa.values")) {
    const size_t row=2ull*g.kvh*g.ad;require(full==row*size_t(g.context),"checkpoint qsa kv extent");return size_t(N)*row;
  }
  if(checkpoint_suffix(name,".qsa.raw")) {
    const size_t row=2ull*g.id;require(full==row*size_t(g.context),"checkpoint qsa raw extent");return size_t(N)*row;
  }
  if(checkpoint_suffix(name,".qsa.pooled")) {
    const size_t row=2ull*g.id;require(full==row*size_t((g.context+3)/4),"checkpoint qsa pooled extent");return size_t(N/4)*row;
  }
  return full;
}
static void checkpoint_write(const fs::path& path,const void* data,size_t n) {
  int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0644);
  require(fd>=0,"checkpoint create "+path.string());
  auto p=static_cast<const uint8_t*>(data);size_t left=n;
  while(left){ssize_t w=::write(fd,p,left);if(w<=0){::close(fd);require(false,"checkpoint write "+path.string());}p+=w;left-=size_t(w);}
  if(::fsync(fd)!=0){::close(fd);require(false,"checkpoint fsync "+path.string());}
  require(::close(fd)==0,"checkpoint close "+path.string());
}
static void checkpoint_fsync_dir(const fs::path& d) {
  int fd=::open(d.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
  require(fd>=0,"checkpoint directory open "+d.string());
  const int rc=::fsync(fd);::close(fd);
  require(rc==0,"checkpoint directory fsync "+d.string());
}
static std::vector<uint8_t> checkpoint_read(const fs::path& path) {
  std::ifstream f(path,std::ios::binary);require(bool(f),"checkpoint read "+path.string());
  std::vector<uint8_t> b((std::istreambuf_iterator<char>(f)),{});
  require(!f.bad(),"checkpoint read "+path.string());
  return b;
}
static std::string checkpoint_self_sha256() {return hash(checkpoint_read("/proc/self/exe"));}
static std::vector<int> checkpoint_layers(const Engine& e,const std::string& suffix) {
  std::vector<int> out;
  for(const auto& [name,s]:e.buffers[0])
    if(checkpoint_suffix(name,suffix)) {
      require(name.compare(0,4,"blk.")==0,"checkpoint layer buffer name");
      out.push_back(std::stoi(name.substr(4)));
    }
  std::sort(out.begin(),out.end());return out;
}
static std::string checkpoint_join(const std::vector<int64_t>& v) {
  std::ostringstream o;for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];return o.str();
}
static std::string checkpoint_join(const std::vector<int>& v) {
  return checkpoint_join(std::vector<int64_t>(v.begin(),v.end()));
}
static std::pair<int64_t,int64_t> checkpoint_history(const std::vector<int>& tokens,int64_t eos) {
  // Engine::prepare_token's host mirror after stepping tokens[0..N): history1 is the last
  // stepped token, history0 the one before it (eos when only one token was stepped).
  const size_t N=tokens.size();
  return {N>=2?int64_t(tokens[N-2]):eos,int64_t(tokens[N-1])};
}

// ---------------------------------------------------------------- tokenizer/template identity
struct TokenizerIdentity { std::string file_sha256,format,gguf_header_sha256,tokenizer_source_sha256,vocab_bin_sha256; };
static TokenizerIdentity checkpoint_tokenizer_identity(const fs::path& path,const std::string& op) {
  if(path.empty())checkpoint_refuse(op,"tokenizer identity","--tokenizer-identity FILE is required for every checkpoint operation");
  if(!fs::is_regular_file(path))checkpoint_refuse(op,"tokenizer identity","file missing: "+path.string());
  const auto bytes=checkpoint_read(path);
  if(bytes.empty()||bytes.size()>65536)checkpoint_refuse(op,"tokenizer identity","file size outside 1..65536 bytes");
  TokenizerIdentity t;t.file_sha256=hash(bytes);
  std::map<std::string,std::string> values;
  std::istringstream in{std::string(bytes.begin(),bytes.end())};std::string line;
  while(std::getline(in,line)) {
    if(line.empty()||line[0]=='#')continue;
    const auto tab=line.find('\t');
    if(tab==std::string::npos||tab==0||line.find('\t',tab+1)!=std::string::npos)
      checkpoint_refuse(op,"tokenizer identity","each line must be KEY<TAB>VALUE");
    if(!values.emplace(line.substr(0,tab),line.substr(tab+1)).second)
      checkpoint_refuse(op,"tokenizer identity","duplicate key "+line.substr(0,tab));
  }
  auto need=[&](const char* k)->std::string{auto it=values.find(k);
    if(it==values.end())checkpoint_refuse(op,"tokenizer identity",std::string("missing key ")+k);return it->second;};
  t.format=need("format");
  if(t.format!=TOKENIZER_IDENTITY_FORMAT)checkpoint_refuse(op,"tokenizer identity","format "+t.format);
  t.gguf_header_sha256=need("gguf_header_sha256");t.tokenizer_source_sha256=need("tokenizer_source_sha256");t.vocab_bin_sha256=need("vocab_bin_sha256");
  for(const auto* v:{&t.gguf_header_sha256,&t.tokenizer_source_sha256,&t.vocab_bin_sha256})
    if(!checkpoint_hex64(*v))checkpoint_refuse(op,"tokenizer identity","pinned hashes must be 64 lowercase hex characters");
  return t;
}

// ---------------------------------------------------------------- manifest model
struct CheckpointBlob { std::string name; uint64_t bytes=0; std::string sha256; int64_t rows=-1; };
struct CheckpointManifest {
  std::string text,sha256;                        // exact manifest.json bytes and their sha256
  std::string format,label,contract,checkpoint_id,created,operation,parent_id,parent_sha;
  bool legacy=false;                              // packet180 v1.2+p180 manifest (label experimental)
  std::string qualified_scope,qualified_gates;    // v1.2+p181 qualified_by, rendered for fields.tsv
  std::string identity_sha,binary_sha,engine_packet,engine_profile;
  TokenizerIdentity tokenizer;
  int64_t layers=0,kvh=0,ad=0,ih=0,g_id=0,qh=0,kh=0,vh=0,d=0,context=0,vocab=0,eos=0;
  std::vector<int64_t> qsa_layers,gdn_layers;
  int64_t prompt_length=0,length=0,position=0,next_token=0,history0=0,history1=0;
  std::string tokens_sha,save_seconds_text;
  int64_t save_bytes=0;
  std::vector<CheckpointBlob> blobs;
  std::vector<std::pair<std::string,std::string>> skips;
};
static std::vector<int64_t> cj_int_list(const CJson& v,const std::string& what) {
  if(v.kind!=CJson::Array)throw std::runtime_error("not an array: "+what);
  std::vector<int64_t> out;for(const auto& x:v.items)out.push_back(cj_int(x,what));return out;
}
// Parse manifest.json once into the authoritative model; every structural rule is checked here.
static void checkpoint_manifest_fill(CheckpointManifest& m) {
  const CJson root=checkpoint_parse_json(m.text);
  // packet181: two manifest contracts are read. v1.2+p181 (this engine) carries label
  // "experimental-postreply-front" and exactly this engine's qualified_by record; v1.2+p180 (packet180)
  // carries label "experimental" and no qualified_by. A label that does not pair with its
  // contract, or any other contract, is refused as a malformed manifest.
  if(root.kind!=CJson::Object)throw std::runtime_error("not an object: manifest");
  m.contract=cj_str(cj_at(root,"contract"),"contract");
  m.legacy=m.contract==CHECKPOINT_LEGACY_CONTRACT;
  if(m.contract!=CHECKPOINT_CONTRACT&&!m.legacy)
    throw std::runtime_error("contract "+m.contract+" (this engine reads experimental v1.2+p198 and legacy v1.2+p180 metadata; exact binary identity still required)");
  if(m.legacy)
    cj_keys(root,{"format","label","contract","operations","checkpoint_id","created","lineage","model","engine","geometry",
                  "dtypes","tokenizer_identity","token_state","sampler","blobs","skipped_buffers","measurements"},"manifest");
  else
    cj_keys(root,{"format","label","contract","qualified_by","operations","checkpoint_id","created","lineage","model","engine","geometry",
                  "dtypes","tokenizer_identity","token_state","sampler","blobs","skipped_buffers","measurements"},"manifest");
  m.format=cj_str(cj_at(root,"format"),"format");m.label=cj_str(cj_at(root,"label"),"label");
  if(m.format!=CHECKPOINT_FORMAT)throw std::runtime_error("format "+m.format);
  const std::string want_label=m.legacy?CHECKPOINT_LEGACY_LABEL:CHECKPOINT_LABEL;
  if(m.label!=want_label)throw std::runtime_error("label "+m.label+" does not pair with contract "+m.contract+" (expected "+want_label+")");
  if(!m.legacy) {
    const auto& q=cj_at(root,"qualified_by");
    if(!cj_equal(q,checkpoint_parse_json(CHECKPOINT_QUALIFIED_BY)))
      throw std::runtime_error("qualified_by differs from this engine's qualification record");
    m.qualified_scope=cj_str(cj_at(q,"scope"),"qualified_by.scope");
    std::ostringstream gates;
    for(size_t i=0;i<cj_at(q,"device_gates").items.size();++i) {
      const auto& g=cj_at(q,"device_gates").items[i];
      gates<<(i?";":"")<<cj_str(cj_at(g,"packet"),"packet")<<'@'<<cj_str(cj_at(g,"date"),"date")<<':';
      const auto& ops=cj_at(g,"operations").items;
      for(size_t j=0;j<ops.size();++j)gates<<(j?",":"")<<cj_str(ops[j],"operation");
    }
    m.qualified_gates=gates.str();
  }
  const auto& ops=cj_at(root,"operations");
  if(ops.kind!=CJson::Array||ops.items.size()!=CHECKPOINT_OPERATIONS.size())throw std::runtime_error("operations");
  for(size_t i=0;i<ops.items.size();++i)if(cj_str(ops.items[i],"operations")!=CHECKPOINT_OPERATIONS[i])throw std::runtime_error("operations");
  m.checkpoint_id=cj_str(cj_at(root,"checkpoint_id"),"checkpoint_id");
  if(!checkpoint_valid_id(m.checkpoint_id))throw std::runtime_error("checkpoint_id is not a valid id");
  m.created=cj_str(cj_at(root,"created"),"created");
  const auto& lineage=cj_at(root,"lineage");cj_keys(lineage,{"operation","parent"},"lineage");
  m.operation=cj_str(cj_at(lineage,"operation"),"lineage.operation");
  const auto& parent=cj_at(lineage,"parent");
  if(m.operation=="save"){if(parent.kind!=CJson::Null)throw std::runtime_error("lineage: a plain save has no parent");}
  else if(m.operation=="restore-then-save") {
    cj_keys(parent,{"checkpoint_id","manifest_sha256"},"lineage.parent");
    m.parent_id=cj_str(cj_at(parent,"checkpoint_id"),"lineage.parent.checkpoint_id");
    m.parent_sha=cj_str(cj_at(parent,"manifest_sha256"),"lineage.parent.manifest_sha256");
    if(!checkpoint_valid_id(m.parent_id)||!checkpoint_hex64(m.parent_sha))throw std::runtime_error("lineage.parent");
  } else throw std::runtime_error("lineage.operation "+m.operation);
  const auto& model=cj_at(root,"model");cj_keys(model,{"identity_tsv_sha256","shard_stat_rows"},"model");
  m.identity_sha=cj_str(cj_at(model,"identity_tsv_sha256"),"model.identity_tsv_sha256");
  if(!m.identity_sha.empty()&&!checkpoint_hex64(m.identity_sha))throw std::runtime_error("model.identity_tsv_sha256");
  if(cj_at(model,"shard_stat_rows").kind!=CJson::Array)throw std::runtime_error("model.shard_stat_rows");
  const auto& engine=cj_at(root,"engine");cj_keys(engine,{"binary_sha256","packet","profile"},"engine");
  m.binary_sha=cj_str(cj_at(engine,"binary_sha256"),"engine.binary_sha256");
  if(!checkpoint_hex64(m.binary_sha))throw std::runtime_error("engine.binary_sha256");
  m.engine_packet=cj_str(cj_at(engine,"packet"),"engine.packet");m.engine_profile=cj_str(cj_at(engine,"profile"),"engine.profile");
  const auto& g=cj_at(root,"geometry");
  cj_keys(g,{"layers","qsa_layers","gdn_layers","kvh","ad","ih","id","qh","gdn","context","vocab","eos"},"geometry");
  m.layers=cj_int(cj_at(g,"layers"),"layers");m.qsa_layers=cj_int_list(cj_at(g,"qsa_layers"),"qsa_layers");
  m.gdn_layers=cj_int_list(cj_at(g,"gdn_layers"),"gdn_layers");
  m.kvh=cj_int(cj_at(g,"kvh"),"kvh");m.ad=cj_int(cj_at(g,"ad"),"ad");m.ih=cj_int(cj_at(g,"ih"),"ih");
  m.g_id=cj_int(cj_at(g,"id"),"id");m.qh=cj_int(cj_at(g,"qh"),"qh");
  const auto& gdn=cj_at(g,"gdn");cj_keys(gdn,{"kh","vh","d"},"geometry.gdn");
  m.kh=cj_int(cj_at(gdn,"kh"),"kh");m.vh=cj_int(cj_at(gdn,"vh"),"vh");m.d=cj_int(cj_at(gdn,"d"),"d");
  m.context=cj_int(cj_at(g,"context"),"context");m.vocab=cj_int(cj_at(g,"vocab"),"vocab");m.eos=cj_int(cj_at(g,"eos"),"eos");
  if(m.layers!=int64_t(m.qsa_layers.size()+m.gdn_layers.size()))throw std::runtime_error("geometry.layers");
  if(m.context<1||m.vocab<1||m.eos<0||m.eos>=m.vocab)throw std::runtime_error("geometry bounds");
  const auto& dt=cj_at(root,"dtypes");cj_keys(dt,{"kv","gdn_state","ple"},"dtypes");
  for(const char* k:{"kv","gdn_state","ple"})if(cj_str(cj_at(dt,k),k)!="bf16")throw std::runtime_error(std::string("dtypes.")+k);
  const auto& ti=cj_at(root,"tokenizer_identity");
  cj_keys(ti,{"file_sha256","format","gguf_header_sha256","tokenizer_source_sha256","vocab_bin_sha256"},"tokenizer_identity");
  m.tokenizer.file_sha256=cj_str(cj_at(ti,"file_sha256"),"tokenizer_identity.file_sha256");
  m.tokenizer.format=cj_str(cj_at(ti,"format"),"tokenizer_identity.format");
  m.tokenizer.gguf_header_sha256=cj_str(cj_at(ti,"gguf_header_sha256"),"tokenizer_identity.gguf_header_sha256");
  m.tokenizer.tokenizer_source_sha256=cj_str(cj_at(ti,"tokenizer_source_sha256"),"tokenizer_identity.tokenizer_source_sha256");
  m.tokenizer.vocab_bin_sha256=cj_str(cj_at(ti,"vocab_bin_sha256"),"tokenizer_identity.vocab_bin_sha256");
  if(m.tokenizer.format!=TOKENIZER_IDENTITY_FORMAT)throw std::runtime_error("tokenizer_identity.format");
  for(const auto* v:{&m.tokenizer.file_sha256,&m.tokenizer.gguf_header_sha256,&m.tokenizer.tokenizer_source_sha256,&m.tokenizer.vocab_bin_sha256})
    if(!checkpoint_hex64(*v))throw std::runtime_error("tokenizer_identity hash");
  const auto& ts=cj_at(root,"token_state");
  cj_keys(ts,{"prompt_length","length","position","next_token","tokens_sha256","token_history"},"token_state");
  m.prompt_length=cj_int(cj_at(ts,"prompt_length"),"prompt_length");m.length=cj_int(cj_at(ts,"length"),"length");
  m.position=cj_int(cj_at(ts,"position"),"position");m.next_token=cj_int(cj_at(ts,"next_token"),"next_token");
  m.tokens_sha=cj_str(cj_at(ts,"tokens_sha256"),"tokens_sha256");
  const auto history=cj_int_list(cj_at(ts,"token_history"),"token_history");
  if(history.size()!=2)throw std::runtime_error("token_history must hold two tokens");
  m.history0=history[0];m.history1=history[1];
  if(m.position<1||m.position>=m.context)throw std::runtime_error("position outside context allocation");
  if(m.length!=m.position)throw std::runtime_error("length != position");
  if(m.prompt_length<1||m.prompt_length>m.position)throw std::runtime_error("prompt_length outside the processed prefix");
  if(m.next_token<0||m.next_token>=m.vocab)throw std::runtime_error("next_token outside vocabulary");
  if(!checkpoint_hex64(m.tokens_sha))throw std::runtime_error("tokens_sha256");
  const auto& sampler=cj_at(root,"sampler");cj_keys(sampler,{"mode","state"},"sampler");
  if(cj_str(cj_at(sampler,"mode"),"sampler.mode")!="greedy-argmax"||cj_at(sampler,"state").kind!=CJson::Null)throw std::runtime_error("sampler");
  const auto& blobs=cj_at(root,"blobs");if(blobs.kind!=CJson::Array)throw std::runtime_error("blobs");
  std::set<std::string> names;int64_t total=0;
  for(const auto& b:blobs.items) {
    cj_keys(b,{"name","bytes","sha256","slice"},"blob");
    CheckpointBlob x;x.name=cj_str(cj_at(b,"name"),"blob.name");
    const int64_t bytes=cj_int(cj_at(b,"bytes"),"blob.bytes");x.sha256=cj_str(cj_at(b,"sha256"),"blob.sha256");
    if(!checkpoint_valid_id(x.name)||x.name=="tokens"||x.name=="fields"||x.name=="manifest")throw std::runtime_error("blob name "+x.name);
    if(!names.insert(x.name).second)throw std::runtime_error("duplicate blob "+x.name);
    if(bytes<0||bytes>(int64_t(1)<<40)||!checkpoint_hex64(x.sha256))throw std::runtime_error("blob "+x.name);
    x.bytes=uint64_t(bytes);total+=bytes;
    const auto& slice=cj_at(b,"slice");
    if(slice.kind!=CJson::Null) {
      const auto s=cj_int_list(slice,"blob.slice");
      if(s.size()!=2||s[0]!=0||s[1]<0)throw std::runtime_error("blob slice "+x.name);
      x.rows=s[1];
      const int64_t want=checkpoint_suffix(x.name,".qsa.pooled")?m.position/4:m.position;
      if(checkpoint_rule(x.name)!="saved-sliced-kv"||x.rows!=want)throw std::runtime_error("blob slice rows "+x.name);
    } else if(checkpoint_rule(x.name)!="saved-whole")throw std::runtime_error("whole blob with a sliced rule "+x.name);
    m.blobs.push_back(x);
  }
  const auto& skips=cj_at(root,"skipped_buffers");if(skips.kind!=CJson::Array)throw std::runtime_error("skipped_buffers");
  for(const auto& s:skips.items) {
    cj_keys(s,{"name","rule"},"skipped buffer");
    const auto& n=cj_str(cj_at(s,"name"),"skip.name");
    if(!names.insert(n).second)throw std::runtime_error("buffer listed twice "+n);
    m.skips.emplace_back(n,cj_str(cj_at(s,"rule"),"skip.rule"));
  }
  const auto& meas=cj_at(root,"measurements");cj_keys(meas,{"save_seconds","save_bytes"},"measurements");
  const auto& seconds=cj_at(meas,"save_seconds");
  if(seconds.kind!=CJson::Number)throw std::runtime_error("save_seconds");
  m.save_seconds_text=seconds.text;m.save_bytes=cj_int(cj_at(meas,"save_bytes"),"save_bytes");
  if(m.save_bytes!=total)throw std::runtime_error("save_bytes != sum of blob bytes");
}
// fields.tsv: a derived, grep-friendly index. It is rendered from the PARSED manifest and must
// equal that rendering exactly; it is never read as a source of values.
static std::string checkpoint_render_fields(const CheckpointManifest& m) {
  std::ostringstream f;
  auto row=[&](const char* k,const std::string& v){f<<k<<'\t'<<v<<'\n';};
  auto num=[&](const char* k,int64_t v){row(k,std::to_string(v));};
  row("format",m.format);row("label",m.label);row("contract",m.contract);
  if(!m.legacy){row("qualified_scope",m.qualified_scope);row("qualified_by",m.qualified_gates);}  // v1.2+p180 rendering unchanged
  row("checkpoint_id",m.checkpoint_id);
  row("created",m.created);row("operation",m.operation);row("parent_checkpoint_id",m.parent_id);
  row("parent_manifest_sha256",m.parent_sha);
  num("position",m.position);num("prompt_length",m.prompt_length);num("length",m.length);num("next_token",m.next_token);
  row("tokens_sha256",m.tokens_sha);num("history0",m.history0);num("history1",m.history1);
  row("identity_tsv_sha256",m.identity_sha);row("binary_sha256",m.binary_sha);
  row("tokenizer_identity_sha256",m.tokenizer.file_sha256);
  num("kvh",m.kvh);num("ad",m.ad);num("ih",m.ih);num("id",m.g_id);num("kh",m.kh);num("vh",m.vh);num("d",m.d);num("qh",m.qh);
  num("context",m.context);num("vocab",m.vocab);num("eos",m.eos);num("layers",m.layers);
  row("qsa_layers",checkpoint_join(m.qsa_layers));row("gdn_layers",checkpoint_join(m.gdn_layers));
  row("save_seconds",m.save_seconds_text);num("save_bytes",m.save_bytes);row("manifest_sha256",m.sha256);
  for(const auto& b:m.blobs)f<<"blob\t"<<b.name<<'\t'<<b.bytes<<'\t'<<b.sha256<<'\t'<<b.rows<<'\n';
  for(const auto& [n,r]:m.skips)f<<"skip\t"<<n<<'\t'<<r<<'\n';
  return f.str();
}
static std::set<std::string> checkpoint_expected_files(const CheckpointManifest& m) {
  std::set<std::string> s{"manifest.json","fields.tsv","tokens.bin"};
  for(const auto& b:m.blobs)s.insert(b.name+".bin");
  return s;
}

// ---------------------------------------------------------------- shared sibling lock
struct CheckpointLock {
  fs::path path;int fd=-1;
  CheckpointLock(const fs::path& root,const std::string& id,bool exclusive,const std::string& op) {
    path=root/(id+".lock");
    for(int attempt=0;attempt<3;++attempt) {
      fd=::open(path.c_str(),O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0644);
      if(fd<0)checkpoint_refuse(op,"lock io","cannot open "+path.string()+": "+std::strerror(errno));
      if(::flock(fd,(exclusive?LOCK_EX:LOCK_SH)|LOCK_NB)!=0) {
        const int err=errno;::close(fd);fd=-1;
        if(err==EWOULDBLOCK)checkpoint_refuse(op,"lock","checkpoint "+id+" is in use ("+
          std::string(exclusive?"another process holds its lock":"it is being saved or deleted")+"); no checkpoint operation waits");
        checkpoint_refuse(op,"lock io",std::string("flock: ")+std::strerror(err));
      }
      struct stat held{},live{};
      if(::fstat(fd,&held)==0&&::stat(path.c_str(),&live)==0&&held.st_dev==live.st_dev&&held.st_ino==live.st_ino)return;
      ::close(fd);fd=-1;  // a concurrent delete unlinked this lock file after we opened it
    }
    checkpoint_refuse(op,"lock io","lock file replaced by concurrent deletes");
  }
  CheckpointLock(const CheckpointLock&)=delete;CheckpointLock& operator=(const CheckpointLock&)=delete;
  void unlink_while_held(){::unlink(path.c_str());}
  ~CheckpointLock(){if(fd>=0)::close(fd);}
};

// ---------------------------------------------------------------- load + verify
enum class CheckpointVerify { metadata, tokens, full };
struct CheckpointLoad {
  CheckpointManifest m;std::vector<int> tokens;
  std::vector<std::pair<std::string,std::vector<uint8_t>>> blobs;uint64_t bytes_read=0,blobs_verified=0;
};
static CheckpointLoad checkpoint_load(const fs::path& d,const std::string& expected_id,CheckpointVerify mode,const std::string& op,
                                      bool keep_blobs,const std::function<void(const CheckpointBlob&)>& progress=nullptr) {
  if(!fs::is_directory(fs::symlink_status(d)))checkpoint_refuse(op,"visibility","checkpoint directory missing: "+d.string());
  if(!fs::is_regular_file(fs::symlink_status(d/"manifest.json")))
    checkpoint_refuse(op,"visibility","manifest.json missing (partial, deleted or unverified checkpoint)");
  CheckpointLoad r;auto& m=r.m;
  const auto manifest_bytes=checkpoint_read(d/"manifest.json");
  m.text.assign(manifest_bytes.begin(),manifest_bytes.end());m.sha256=hash(manifest_bytes);
  try{checkpoint_manifest_fill(m);}
  catch(const CheckpointRefusal&){throw;}
  catch(const std::exception& error){checkpoint_refuse(op,"manifest",error.what());}
  if(m.checkpoint_id!=expected_id)checkpoint_refuse(op,"manifest","checkpoint_id "+m.checkpoint_id+" does not name its directory "+expected_id);
  if(!fs::is_regular_file(fs::symlink_status(d/"fields.tsv")))checkpoint_refuse(op,"manifest cross-check","fields.tsv missing");
  const auto tsv_bytes=checkpoint_read(d/"fields.tsv");const std::string tsv(tsv_bytes.begin(),tsv_bytes.end());
  {
    const std::string key="\nmanifest_sha256\t";const auto at=tsv.find(key);
    if(at==std::string::npos)checkpoint_refuse(op,"manifest cross-check","fields.tsv has no manifest_sha256 row");
    const auto end=tsv.find('\n',at+key.size());
    if(tsv.substr(at+key.size(),end-at-key.size())!=m.sha256)
      checkpoint_refuse(op,"manifest sha256","manifest.json differs from the sha256 sealed at save");
  }
  const std::string rendered=checkpoint_render_fields(m);
  if(tsv!=rendered) {
    std::istringstream a{tsv},b{rendered};std::string la,lb;size_t line=0;
    while(true){++line;const bool ga=bool(std::getline(a,la)),gb=bool(std::getline(b,lb));if(!ga||!gb||la!=lb)break;}
    const std::string key=la.substr(0,la.find('\t'));
    checkpoint_refuse(op,"manifest cross-check","fields.tsv line "+std::to_string(line)+" ("+key+
      ") differs from the rendering of manifest.json; manifest.json is the only source of truth");
  }
  const auto expected=checkpoint_expected_files(m);std::set<std::string> seen;
  for(const auto& entry:fs::directory_iterator(d)) {
    const std::string n=entry.path().filename().string();
    if(!fs::is_regular_file(entry.symlink_status()))checkpoint_refuse(op,"file set","non-regular entry "+n);
    if(!expected.count(n))checkpoint_refuse(op,"file set","unexpected file "+n+" (the directory holds only manifest.json, fields.tsv, tokens.bin and manifest blobs)");
    seen.insert(n);
  }
  for(const auto& n:expected)if(!seen.count(n))checkpoint_refuse(op,"file set","missing file "+n);
  if(mode==CheckpointVerify::metadata)return r;
  const int64_t N=m.position;
  std::vector<uint8_t> token_bytes;
  try{token_bytes=checkpoint_read(d/"tokens.bin");}catch(const std::exception&){checkpoint_refuse(op,"blob read","tokens.bin");}
  if(token_bytes.size()!=size_t(N)*4)checkpoint_refuse(op,"token state","tokens.bin extent");
  if(hash(token_bytes)!=m.tokens_sha)checkpoint_refuse(op,"token state","tokens.bin sha256");
  r.bytes_read+=token_bytes.size();
  r.tokens.assign(size_t(N),0);
  for(int64_t i=0;i<N;++i){int32_t x;std::memcpy(&x,token_bytes.data()+4*i,4);
    if(x<0||x>=m.vocab)checkpoint_refuse(op,"token state","token outside vocabulary at index "+std::to_string(i));r.tokens[size_t(i)]=x;}
  const auto [h0,h1]=checkpoint_history(r.tokens,m.eos);
  if(m.history0!=h0||m.history1!=h1)
    checkpoint_refuse(op,"token state","manifest token_history disagrees with the last processed tokens in tokens.bin");
  if(mode==CheckpointVerify::tokens)return r;
  std::map<std::string,std::vector<uint8_t>> small;
  for(const auto& b:m.blobs) {
    std::vector<uint8_t> data;
    try{data=checkpoint_read(d/(b.name+".bin"));}catch(const std::exception&){checkpoint_refuse(op,"blob read",b.name);}
    if(data.size()!=b.bytes)checkpoint_refuse(op,"blob bytes",b.name);
    if(hash(data)!=b.sha256)checkpoint_refuse(op,"blob sha256",b.name);
    r.bytes_read+=data.size();++r.blobs_verified;
    if(progress)progress(b);
    if(data.size()<=16)small[b.name]=data;
    if(keep_blobs)r.blobs.emplace_back(b.name,std::move(data));
  }
  // Semantic blob cross-checks: the device control blobs agree with the manifest and tokens.bin.
  auto int32_blob=[&](const char* name,int64_t want,const char* what) {
    auto it=small.find(name);if(it==small.end())return;
    int32_t x=0;if(it->second.size()!=4)checkpoint_refuse(op,"token state",std::string(name)+" blob extent");
    std::memcpy(&x,it->second.data(),4);
    if(int64_t(x)!=want)checkpoint_refuse(op,"token state",what);
  };
  for(const char* name:{"position","next_token","token","error","token_history"})
    if(!small.count(name))checkpoint_refuse(op,"completeness",std::string("control blob missing: ")+name);
  int32_blob("position",N,"position blob disagrees with manifest");
  int32_blob("next_token",m.next_token,"next_token blob disagrees with the manifest pending token");
  int32_blob("token",r.tokens[size_t(N-1)],"last stepped token blob disagrees with tokens.bin");
  int32_blob("error",0,"sticky device error recorded in the checkpoint");
  if(auto it=small.find("token_history");it!=small.end()) {
    int64_t x[2];if(it->second.size()!=16)checkpoint_refuse(op,"token state","token_history blob extent");
    std::memcpy(x,it->second.data(),16);
    if(x[0]!=h0||x[1]!=h1)checkpoint_refuse(op,"token state","token_history blob disagrees with tokens.bin");
  }
  return r;
}

// ---------------------------------------------------------------- operation classification
static void checkpoint_check_tokenizer(const TokenizerIdentity& t,const CheckpointManifest& m,const std::string& op) {
  if(t.file_sha256!=m.tokenizer.file_sha256||t.gguf_header_sha256!=m.tokenizer.gguf_header_sha256||
     t.tokenizer_source_sha256!=m.tokenizer.tokenizer_source_sha256||t.vocab_bin_sha256!=m.tokenizer.vocab_bin_sha256)
    checkpoint_refuse(op,"tokenizer identity","--tokenizer-identity "+t.file_sha256+" differs from the identity recorded at save "+m.tokenizer.file_sha256);
}
static bool checkpoint_stop_token(int64_t token,int64_t eos,bool mini) {return token==eos||(!mini&&token==248046);}
// Operation by --input shape (README "Operation semantics"), shared by the early precheck and by
// restore; returns {operation, appended length} or refuses (always before any upload):
//   length == prompt_length, equal to the recorded prompt          -> same-generation resume
//   length >= N+1, input[0:N] == tokens.bin, input[N] == pending t   -> append (delta = input[N+1:])
// Same-generation resume is refused when the saved generation already ended (pending stop token:
// stepping it would produce tokens the uninterrupted run never produces) and when N + --max-new
// does not fit the context allocation (one more position is needed when the run also saves).
static std::pair<std::string,size_t> checkpoint_classify(const CheckpointManifest& m,const std::vector<int>& tokens,const std::vector<int>& input,
                                                         int64_t max_new,bool saving,bool mini,const std::string& op) {
  const int64_t N=m.position;const size_t plen=size_t(m.prompt_length);
  auto first_mismatch=[&](size_t n)->int64_t{for(size_t i=0;i<n;++i)if(input[i]!=tokens[i])return int64_t(i);return -1;};
  if(input.size()==plen) {
    const int64_t at=first_mismatch(plen);
    if(at>=0)checkpoint_refuse(op,"prefix","same-generation resume: --input differs from the recorded original prompt at index "+std::to_string(at));
    if(checkpoint_stop_token(m.next_token,m.eos,mini))
      checkpoint_refuse(op,"ended generation","same-generation resume: the saved generation already ended with stop token "+std::to_string(m.next_token)+
        "; continue with append (--input = saved history + that token + the new turn)");
    if(N+max_new>m.context-(saving?1:0))
      checkpoint_refuse(op,"context","same-generation resume of "+std::to_string(N)+" saved positions plus --max-new "+std::to_string(max_new)+
        " exceeds the context allocation "+std::to_string(m.context)+(saving?" (a save needs one free position)":""));
    return {"same-generation-resume",0};
  }
  if(input.size()>=size_t(N)+1) {
    const int64_t at=first_mismatch(size_t(N));
    if(at>=0)checkpoint_refuse(op,"prefix","append: --input differs from the saved processed history at index "+std::to_string(at)+
      " (saved "+std::to_string(tokens[size_t(at)])+", given "+std::to_string(input[size_t(at)])+")");
    if(input[size_t(N)]!=int(m.next_token))checkpoint_refuse(op,"prefix","append: --input["+std::to_string(N)+"] must be the saved pending token "+
      std::to_string(m.next_token)+" (given "+std::to_string(input[size_t(N)])+")");
    if(int64_t(input.size())+max_new>m.context)
      checkpoint_refuse(op,"context","append: --input length plus --max-new exceeds the context allocation "+std::to_string(m.context));
    return {"append",input.size()-size_t(N)-1};
  }
  checkpoint_refuse(op,"prefix","--input length "+std::to_string(input.size())+" is neither the recorded prompt length "+
      std::to_string(plen)+" (same-generation resume) nor at least "+std::to_string(N+1)+" (saved history plus the pending token; append)");
}
// Early refusals before any model load (main, right after argument parsing): the manifest, tokens.bin,
// tokenizer identity and --input classification checks that restore repeats, authoritatively, under
// its lock after the model is loaded. A malformed --input is left to the normal input check.
static void checkpoint_precheck(const fs::path& root,const std::string& id,const fs::path& input_path,int64_t max_new,bool saving,
                                const fs::path& tokenizer_path,bool mini) {
  const std::string op="restore";const fs::path d=root/id;
  const auto tokenizer=checkpoint_tokenizer_identity(tokenizer_path,op);
  if(!fs::is_directory(fs::symlink_status(d))||!fs::is_regular_file(fs::symlink_status(d/"manifest.json")))
    checkpoint_refuse(op,"visibility","manifest.json missing (partial, deleted or unverified checkpoint)");
  CheckpointLock lock(root,id,false,op);
  const auto loaded=checkpoint_load(d,id,CheckpointVerify::tokens,op,false);
  checkpoint_check_tokenizer(tokenizer,loaded.m,op);
  std::vector<int> input;
  if(input_path.empty()){if(!mini)return;input={2,5,3,7,1};}
  else {std::ifstream f(input_path);int x;while(f>>x)input.push_back(x);if(!f.eof()||input.empty())return;}
  checkpoint_classify(loaded.m,loaded.tokens,input,max_new,saving,mini,op);
}

// ---------------------------------------------------------------- save
struct CheckpointParent { std::string checkpoint_id,manifest_sha256;bool present=false; };
struct SavedCheckpoint { int64_t position=0;int next_token=-1;uint64_t bytes=0;double seconds=0;std::string checkpoint_id,manifest_sha256,parent_id;bool present=false; };

static SavedCheckpoint checkpoint_save(Engine& e,const fs::path& root,const std::string& id,const std::vector<int>& prompt,
                                       const std::vector<int>& processed,int next_token,const fs::path& tokenizer_path,
                                       const CheckpointParent& parent) {
  const std::string op="save";
  const auto started=std::chrono::steady_clock::now();
  if(!checkpoint_valid_id(id))checkpoint_refuse(op,"id","invalid checkpoint id");
  const auto tokenizer=checkpoint_tokenizer_identity(tokenizer_path,op);  // before anything is written
  const int64_t N=int64_t(processed.size());
  const auto& g=e.p.g;
  if(N<1||N>=g.context)checkpoint_refuse(op,"token state","processed history outside the context allocation");
  if(prompt.empty()||prompt.size()>processed.size()||!std::equal(prompt.begin(),prompt.end(),processed.begin()))
    checkpoint_refuse(op,"token state","--input is not a prefix of the processed history");
  if(next_token<0||next_token>=g.vocab)checkpoint_refuse(op,"token state","pending token outside vocabulary");
  // Fail-closed self-checks against live device state and the host token-history mirror.
  require(uint32_t(N)==uint32_t(e.integer(0,"position")),"checkpoint save position mismatch");
  require(!e.integer(0,"error"),"checkpoint save with sticky device error refused");
  const auto [h0,h1]=checkpoint_history(processed,g.eos);
  require(e.history0==h0&&e.history1==h1,"checkpoint save: host token-history mirror disagrees with the processed tokens");
  fs::create_directories(root);
  CheckpointLock lock(root,id,true,op);
  const fs::path d=root/id;
  if(fs::exists(fs::symlink_status(d)))checkpoint_refuse(op,"never overwrite","checkpoint "+id+" already exists in "+root.string());
  require(fs::create_directory(d),"checkpoint create "+d.string());
  SavedCheckpoint saved;
  try {
  std::vector<uint8_t> token_bytes(size_t(N)*4);
  for(int64_t i=0;i<N;++i){uint32_t v=uint32_t(processed[size_t(i)]);std::memcpy(token_bytes.data()+4*i,&v,4);}
  checkpoint_write(d/"tokens.bin",token_bytes.data(),token_bytes.size());
  const std::string tokens_sha=hash(token_bytes);
  const auto qsa_layers=checkpoint_layers(e,".qsa.keys"),gdn_layers=checkpoint_layers(e,".gdn.state");
  std::vector<std::string> blob_rows,skip_rows;uint64_t total_bytes=0;
  for(const auto& [name,s]:e.buffers[0]) {
    const std::string rule=checkpoint_rule(name);
    if(rule!="saved-sliced-kv"&&rule!="saved-whole") {
      skip_rows.push_back("{\"name\":"+ownrt::quote(name)+",\"rule\":"+ownrt::quote(rule)+"}");
      continue;
    }
    require(checkpoint_valid_id(name)&&name!="tokens"&&name!="fields"&&name!="manifest","checkpoint blob name "+name);
    const size_t full=s.n*flash::scalar_bytes(s.type);
    const size_t bytes=rule=="saved-sliced-kv"?checkpoint_slice_bytes(e,name,full,N):full;
    auto data=e.readback(0,s.id,bytes);
    checkpoint_write(d/(name+".bin"),data.data(),data.size());
    total_bytes+=bytes;
    const int64_t rows=rule=="saved-sliced-kv"?(checkpoint_suffix(name,".qsa.pooled")?N/4:N):-1;
    std::ostringstream row;row<<"{\"name\":"<<ownrt::quote(name)<<",\"bytes\":"<<bytes<<",\"sha256\":"<<ownrt::quote(hash(data))<<",";
    if(rows>=0)row<<"\"slice\":[0,"<<rows<<"]}";else row<<"\"slice\":null}";
    blob_rows.push_back(row.str());
  }
  std::string identity_sha;std::vector<std::string> stat_rows;
  if(!e.a.auth.empty()) {
    auto bytes=checkpoint_read(e.a.auth);identity_sha=hash(bytes);
    std::istringstream lines{std::string(bytes.begin(),bytes.end())};std::string line;
    while(std::getline(lines,line)) {
      if(line.empty())continue;
      std::istringstream r(line);std::string name;uint64_t b,dv,ino,mt,ct;
      require(bool(r>>name>>b>>dv>>ino>>mt>>ct),"identity row parse");
      std::ostringstream j;j<<"{\"name\":"<<ownrt::quote(name)<<",\"size\":"<<b<<",\"dev\":"<<dv<<",\"ino\":"<<ino<<",\"mtime\":"<<mt<<",\"ctime\":"<<ct<<"}";
      stat_rows.push_back(j.str());
    }
    require(stat_rows.size()==3,"three admitted shards required");
  }
  const std::string binary_sha=checkpoint_self_sha256();
  char iso[32];std::time_t now=std::time(nullptr);
  std::strftime(iso,sizeof iso,"%Y-%m-%dT%H:%M:%SZ",std::gmtime(&now));
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  std::ostringstream m;m.precision(17);
  m<<"{\"format\":"<<ownrt::quote(CHECKPOINT_FORMAT)<<",\"label\":"<<ownrt::quote(CHECKPOINT_LABEL)
   <<",\"contract\":"<<ownrt::quote(CHECKPOINT_CONTRACT)<<",\"qualified_by\":"<<CHECKPOINT_QUALIFIED_BY<<",\"operations\":[";
  for(size_t i=0;i<CHECKPOINT_OPERATIONS.size();++i)m<<(i?",":"")<<ownrt::quote(CHECKPOINT_OPERATIONS[i]);
  m<<"],\"checkpoint_id\":"<<ownrt::quote(id)<<",\"created\":"<<ownrt::quote(iso)
   <<",\"lineage\":{\"operation\":"<<ownrt::quote(parent.present?"restore-then-save":"save")<<",\"parent\":";
  if(parent.present)m<<"{\"checkpoint_id\":"<<ownrt::quote(parent.checkpoint_id)<<",\"manifest_sha256\":"<<ownrt::quote(parent.manifest_sha256)<<"}";
  else m<<"null";
  m<<"},\"model\":{\"identity_tsv_sha256\":"<<ownrt::quote(identity_sha)<<",\"shard_stat_rows\":[";
  for(size_t i=0;i<stat_rows.size();++i)m<<(i?",":"")<<stat_rows[i];
  m<<"]},\"engine\":{\"binary_sha256\":"<<ownrt::quote(binary_sha)<<",\"packet\":"<<ownrt::quote(CHECKPOINT_PACKET)<<",\"profile\":\"tp1-full512\"}"
   <<",\"geometry\":{\"layers\":"<<(qsa_layers.size()+gdn_layers.size())<<",\"qsa_layers\":["<<checkpoint_join(qsa_layers)
   <<"],\"gdn_layers\":["<<checkpoint_join(gdn_layers)<<"],\"kvh\":"<<g.kvh<<",\"ad\":"<<g.ad<<",\"ih\":"<<g.ih<<",\"id\":"<<g.id<<",\"qh\":"<<g.qh
   <<",\"gdn\":{\"kh\":"<<g.kh<<",\"vh\":"<<g.vh<<",\"d\":"<<g.d<<"},\"context\":"<<g.context<<",\"vocab\":"<<g.vocab<<",\"eos\":"<<g.eos<<"}"
   <<",\"dtypes\":{\"kv\":\"bf16\",\"gdn_state\":\"bf16\",\"ple\":\"bf16\"}"
   <<",\"tokenizer_identity\":{\"file_sha256\":"<<ownrt::quote(tokenizer.file_sha256)<<",\"format\":"<<ownrt::quote(tokenizer.format)
   <<",\"gguf_header_sha256\":"<<ownrt::quote(tokenizer.gguf_header_sha256)<<",\"tokenizer_source_sha256\":"<<ownrt::quote(tokenizer.tokenizer_source_sha256)
   <<",\"vocab_bin_sha256\":"<<ownrt::quote(tokenizer.vocab_bin_sha256)<<"}"
   <<",\"token_state\":{\"prompt_length\":"<<prompt.size()<<",\"length\":"<<N<<",\"position\":"<<N<<",\"next_token\":"<<next_token
   <<",\"tokens_sha256\":"<<ownrt::quote(tokens_sha)<<",\"token_history\":["<<h0<<","<<h1<<"]}"
   <<",\"sampler\":{\"mode\":\"greedy-argmax\",\"state\":null}"
   <<",\"blobs\":[";
  for(size_t i=0;i<blob_rows.size();++i)m<<(i?",":"")<<blob_rows[i];
  m<<"],\"skipped_buffers\":[";
  for(size_t i=0;i<skip_rows.size();++i)m<<(i?",":"")<<skip_rows[i];
  m<<"],\"measurements\":{\"save_seconds\":"<<seconds<<",\"save_bytes\":"<<total_bytes<<"}}\n";
  // Round trip: the written manifest is re-parsed by the same strict reader that restore uses,
  // and fields.tsv is rendered from that parse, never from the writer's variables.
  CheckpointManifest parsed;parsed.text=m.str();parsed.sha256=hash(std::vector<uint8_t>(parsed.text.begin(),parsed.text.end()));
  try{checkpoint_manifest_fill(parsed);}catch(const std::exception& error){checkpoint_refuse(op,"manifest round trip",error.what());}
  require(parsed.position==N&&parsed.next_token==next_token&&parsed.history0==h0&&parsed.history1==h1&&
          parsed.checkpoint_id==id&&parsed.save_bytes==int64_t(total_bytes),"checkpoint manifest round trip differs");
  checkpoint_write(d/"manifest.json.tmp",parsed.text.data(),parsed.text.size());
  const std::string fields=checkpoint_render_fields(parsed);
  checkpoint_write(d/"fields.tsv",fields.data(),fields.size());
  // The manifest rename is the visibility point: a partial or unverified checkpoint is never
  // visible to restore, inspect or delete (all require manifest.json and a closed file set).
  fs::rename(d/"manifest.json.tmp",d/"manifest.json");
  checkpoint_fsync_dir(d);checkpoint_fsync_dir(root);
  saved.position=N;saved.next_token=next_token;saved.bytes=total_bytes;saved.seconds=seconds;
  saved.checkpoint_id=id;saved.manifest_sha256=parsed.sha256;saved.parent_id=parent.present?parent.checkpoint_id:"";saved.present=true;
  } catch(...) {
    // A failed save leaves no partial directory behind, so its id stays usable. The manifest
    // rename is the visibility point: a visible checkpoint is complete and is kept.
    std::error_code ec;if(!fs::exists(d/"manifest.json",ec))fs::remove_all(d,ec);
    throw;
  }
  return saved;
}

// ---------------------------------------------------------------- restore (same-generation resume or append)
struct RestoredCheckpoint {
  std::vector<int> tokens;int next_token=-1;int64_t history0=0,history1=0,position=0,prompt_length=0;
  std::string operation,checkpoint_id,manifest_sha256;size_t input_length=0,appended_length=0;uint64_t bytes_read=0;double restore_seconds=0;
  bool pending_is_stop=false;
};
static RestoredCheckpoint checkpoint_restore(Engine& e,const fs::path& root,const std::string& id,
                                             const std::vector<int>& input,const fs::path& tokenizer_path,int64_t max_new,bool saving) {
  const std::string op="restore";
  const auto started=std::chrono::steady_clock::now();
  const fs::path d=root/id;
  // No lock file is created for a checkpoint that does not exist.
  if(!fs::is_directory(fs::symlink_status(d))||!fs::is_regular_file(fs::symlink_status(d/"manifest.json")))
    checkpoint_refuse(op,"visibility","manifest.json missing (partial, deleted or unverified checkpoint)");
  CheckpointLock lock(root,id,false,op);   // shared; held across every read below and the upload
  auto loaded=checkpoint_load(d,id,CheckpointVerify::full,op,true);
  const auto& m=loaded.m;const auto& tokens=loaded.tokens;
  if(checkpoint_self_sha256()!=m.binary_sha)checkpoint_refuse(op,"engine identity","binary_sha256 differs from /proc/self/exe");
  const auto& g=e.p.g;
  auto want=[&](const char* key,int64_t have,int64_t value){if(have!=value)checkpoint_refuse(op,"geometry",std::string(key)+" checkpoint="+std::to_string(have)+" engine="+std::to_string(value));};
  want("kvh",m.kvh,g.kvh);want("ad",m.ad,g.ad);want("ih",m.ih,g.ih);want("id",m.g_id,g.id);want("kh",m.kh,g.kh);want("vh",m.vh,g.vh);
  want("d",m.d,g.d);want("qh",m.qh,g.qh);want("context",m.context,g.context);want("vocab",m.vocab,g.vocab);want("eos",m.eos,g.eos);
  const auto qsa_layers=checkpoint_layers(e,".qsa.keys"),gdn_layers=checkpoint_layers(e,".gdn.state");
  if(checkpoint_join(qsa_layers)!=checkpoint_join(m.qsa_layers))checkpoint_refuse(op,"geometry","qsa layer set differs");
  if(checkpoint_join(gdn_layers)!=checkpoint_join(m.gdn_layers))checkpoint_refuse(op,"geometry","gdn layer set differs");
  const int64_t N=m.position;
  if(e.a.auth.empty()){if(!m.identity_sha.empty())checkpoint_refuse(op,"model identity","full-model checkpoint on a mini engine");}
  else if(hash(checkpoint_read(e.a.auth))!=m.identity_sha)checkpoint_refuse(op,"model identity","identity.tsv sha256/stat pins differ");
  checkpoint_check_tokenizer(checkpoint_tokenizer_identity(tokenizer_path,op),m,op);
  RestoredCheckpoint out;out.input_length=input.size();
  std::tie(out.operation,out.appended_length)=checkpoint_classify(m,tokens,input,max_new,saving,e.a.mini,op);
  out.pending_is_stop=checkpoint_stop_token(m.next_token,m.eos,e.a.mini);
  // Completeness proof re-derived against live plan buffers before any upload.
  std::set<std::string> saved;size_t skipped_live=0;
  for(const auto& [name,s]:e.buffers[0]) {
    const std::string rule=checkpoint_rule(name);
    if(rule=="saved-sliced-kv"||rule=="saved-whole") {
      const size_t full=s.n*flash::scalar_bytes(s.type);
      const size_t bytes=rule=="saved-sliced-kv"?checkpoint_slice_bytes(e,name,full,N):full;
      auto it=std::find_if(m.blobs.begin(),m.blobs.end(),[&](const CheckpointBlob& b){return b.name==name;});
      if(it==m.blobs.end())checkpoint_refuse(op,"completeness","missing blob "+name);
      if(it->bytes!=bytes)checkpoint_refuse(op,"geometry","blob slice extent "+name);
      saved.insert(name);
    } else {
      auto it=std::find_if(m.skips.begin(),m.skips.end(),[&](const std::pair<std::string,std::string>& s){return s.first==name&&s.second==rule;});
      if(it==m.skips.end())checkpoint_refuse(op,"completeness","skip classification changed for "+name);
      ++skipped_live;
    }
  }
  if(saved.size()!=m.blobs.size())checkpoint_refuse(op,"completeness","blob count differs from live saved set");
  if(skipped_live!=m.skips.size())checkpoint_refuse(op,"completeness","skipped-buffer count differs from the live plan");
  for(const auto& [name,data]:loaded.blobs) {
    auto it=e.buffers[0].find(name);
    if(it==e.buffers[0].end())checkpoint_refuse(op,"geometry","engine buffer missing "+name);
    if(data.size()>it->second.n*flash::scalar_bytes(it->second.type))checkpoint_refuse(op,"geometry","blob exceeds allocation "+name);
  }
#ifdef OWN_RT_HOST_ONLY
  // CPU probe hook only (absent from the device build): hold the shared lock after every read so
  // the host probe can run a concurrent delete deterministically.
  if(const char* hold=std::getenv("OWNRT_CHECKPOINT_TEST_HOLD_MS")) {
    std::cerr<<"{\"event\":\"checkpoint-test-hold\",\"lock\":\"shared\",\"checkpoint_id\":"<<ownrt::quote(id)<<"}"<<std::endl;
    std::this_thread::sleep_for(std::chrono::milliseconds(std::stoi(hold)));
  }
#endif
  // Every refusal above precedes this line. Runs after p58_reset_request: every request
  // allocation is zeroed with its ID preserved, so sliced blobs land on zeroed tails byte-exactly
  // (neither arm ever wrote those rows); ple_metadata was re-put by the same reset.
  std::cerr<<"{\"event\":\"checkpoint-upload-begin\",\"checkpoint_id\":"<<ownrt::quote(id)<<",\"operation\":"<<ownrt::quote(out.operation)<<"}"<<std::endl;
  for(const auto& [name,data]:loaded.blobs) {
    auto it=e.buffers[0].find(name);
    e.upload(0,it->second.id,0,data.data(),data.size());
  }
  e.history0=m.history0;e.history1=m.history1;
  e.admit_position(int(N));
  out.tokens=tokens;out.next_token=int(m.next_token);out.history0=m.history0;out.history1=m.history1;out.position=N;
  out.prompt_length=m.prompt_length;out.checkpoint_id=id;out.manifest_sha256=m.sha256;out.bytes_read=loaded.bytes_read;
  out.restore_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  return out;
}

// ---------------------------------------------------------------- result.json "checkpoint" object
// packet181: "prefill" records, for every request, the prompt positions this process stepped and
// the mechanism: fresh run [0, len(input)), append [N, len(input)), same-generation resume none
// (path null). ms is the request's prefill_ms (the append prefill for an append). The restore
// object adds append_prefill_tokens and append_prefill_path beside packet180's append_prefill_ms.
static std::string checkpoint_result_json(const RestoredCheckpoint* r,double restore_ms,double append_prefill_ms,const SavedCheckpoint* s,
                                          double prefill_ms,size_t prefill_first,size_t prefill_tokens) {
  std::ostringstream o;o.precision(17);
  std::vector<std::string> ops;if(r)ops.push_back(r->operation);if(s)ops.push_back("save");
  o<<"{\"contract\":"<<ownrt::quote(CHECKPOINT_CONTRACT)<<",\"label\":"<<ownrt::quote(CHECKPOINT_LABEL)<<",\"operations\":[";
  for(size_t i=0;i<ops.size();++i)o<<(i?",":"")<<ownrt::quote(ops[i]);
  o<<"],\"prefill\":{\"path\":";
  if(prefill_tokens)o<<ownrt::quote(CHECKPOINT_PREFILL_PATH);else o<<"null";
  o<<",\"first_position\":"<<prefill_first<<",\"tokens\":"<<prefill_tokens<<",\"ms\":"<<prefill_ms<<"}";
  o<<",\"restore\":";
  if(r) {
    const bool append=r->operation=="append";
    o<<"{\"checkpoint_id\":"<<ownrt::quote(r->checkpoint_id)<<",\"manifest_sha256\":"<<ownrt::quote(r->manifest_sha256)
     <<",\"operation\":"<<ownrt::quote(r->operation)<<",\"saved_prefix_length\":"<<r->position<<",\"saved_history_length\":"<<r->position+1
     <<",\"saved_prompt_length\":"<<r->prompt_length<<",\"input_length\":"<<r->input_length<<",\"appended_length\":"<<r->appended_length
     <<",\"pending_token\":"<<r->next_token<<",\"pending_is_stop\":"<<(r->pending_is_stop?"true":"false")<<",\"pending_token_handling\":"
     <<ownrt::quote(append?"input[saved_prefix_length] is the saved pending token; it is stepped first as an ordinary prompt token at position saved_prefix_length, then the appended delta; the last input token's argmax is the first generated token"
                          :"stepped as the first decode step at position saved_prefix_length; the output continues the interrupted generation")
     <<",\"restore_ms\":"<<restore_ms<<",\"append_prefill_ms\":";
    if(append)o<<append_prefill_ms;else o<<"null";
    o<<",\"append_prefill_tokens\":"<<(append?r->input_length-size_t(r->position):size_t(0))<<",\"append_prefill_path\":";
    if(append)o<<ownrt::quote(CHECKPOINT_PREFILL_PATH);else o<<"null";
    o<<",\"restored_bytes\":"<<r->bytes_read<<"}";
  } else o<<"null";
  o<<",\"save\":";
  if(s) {
    o<<"{\"checkpoint_id\":"<<ownrt::quote(s->checkpoint_id)<<",\"manifest_sha256\":"<<ownrt::quote(s->manifest_sha256)
     <<",\"position\":"<<s->position<<",\"pending_token\":"<<s->next_token<<",\"bytes\":"<<s->bytes<<",\"seconds\":"<<s->seconds
     <<",\"parent_checkpoint_id\":";
    if(s->parent_id.empty())o<<"null";else o<<ownrt::quote(s->parent_id);
    o<<"}";
  } else o<<"null";
  o<<"}";
  return o.str();
}

// ---------------------------------------------------------------- device-free host tools
static std::pair<fs::path,std::string> checkpoint_target(const fs::path& target) {
  fs::path dir=target.lexically_normal();
  if(dir.filename().empty())dir=dir.parent_path();
  const fs::path root=dir.has_parent_path()?dir.parent_path():fs::path(".");
  return {root,dir.filename().string()};
}
static int checkpoint_inspect_tool(const fs::path& target,bool metadata) {
  const std::string op="inspect",mode=metadata?"metadata":"full";
  const auto [root,id]=checkpoint_target(target);const fs::path dir=root/id;
  std::cerr<<"{\"event\":\"inspect-start\",\"mode\":"<<ownrt::quote(mode)<<",\"checkpoint_dir\":"<<ownrt::quote(dir.string())<<"}"<<std::endl;
  bool ok=false;std::string check,detail;CheckpointLoad loaded;
  try {
    if(!checkpoint_valid_id(id))checkpoint_refuse(op,"visibility","directory name is not a checkpoint id");
    if(!fs::is_directory(fs::symlink_status(dir))||!fs::is_regular_file(fs::symlink_status(dir/"manifest.json")))
      checkpoint_refuse(op,"visibility","manifest.json missing (partial, deleted or unverified checkpoint)");
    CheckpointLock lock(root,id,false,op);
    loaded=checkpoint_load(dir,id,metadata?CheckpointVerify::metadata:CheckpointVerify::full,op,false,[&](const CheckpointBlob& b){
      std::cerr<<"{\"event\":\"blob-verified\",\"name\":"<<ownrt::quote(b.name)<<",\"bytes\":"<<b.bytes<<"}\n";});
    ok=true;
  } catch(const CheckpointRefusal& r){check=r.check;detail=r.detail;}
    catch(const std::exception& error){check="io";detail=error.what();}
  std::ostringstream o;
  o<<"{\"schema\":\"ownrt.checkpoint-inspect.v1\",\"ok\":"<<(ok?"true":"false")<<",\"mode\":"<<ownrt::quote(mode)
   <<",\"device_required\":false,\"checkpoint_dir\":"<<ownrt::quote(dir.string())<<",\"checkpoint_id\":"<<ownrt::quote(id);
  if(ok) {
    std::string manifest=loaded.m.text;while(!manifest.empty()&&(manifest.back()=='\n'||manifest.back()==' '))manifest.pop_back();
    o<<",\"label\":"<<ownrt::quote(loaded.m.label)<<",\"contract\":"<<ownrt::quote(loaded.m.contract)
     <<",\"manifest_sha256\":"<<ownrt::quote(loaded.m.sha256)
     <<",\"verified\":{\"manifest_seal\":true,\"fields_tsv_cross_check\":true,\"file_set_closed\":true,\"tokens\":"<<(metadata?"null":"true")
     <<",\"semantic_blob_checks\":"<<(metadata?"null":"true")<<",\"blobs_verified\":";
    if(metadata)o<<"null,\"blob_bytes_verified\":null";else o<<loaded.blobs_verified<<",\"blob_bytes_verified\":"<<loaded.bytes_read;
    o<<"},\"manifest\":"<<manifest<<",\"error\":null}";
  } else o<<",\"manifest\":null,\"error\":{\"check\":"<<ownrt::quote(check)<<",\"detail\":"<<ownrt::quote(detail)<<"}}";
  std::cout<<o.str()<<"\n"<<std::flush;
  std::cerr<<"{\"event\":\"inspect-end\",\"ok\":"<<(ok?"true":"false")<<"}"<<std::endl;
  return ok?0:1;
}
static int checkpoint_delete_tool(const fs::path& target) {
  const std::string op="delete";
  const auto [root,id]=checkpoint_target(target);const fs::path dir=root/id;
  bool deleted=false;std::string reason,check,detail;size_t removed=0;
  try {
    // 1. Validate the target as a complete checkpoint WITHOUT creating or taking a lock, so an
    //    arbitrary directory never gains a sibling lock file.
    try {
      if(!checkpoint_valid_id(id))checkpoint_refuse(op,"target","directory name is not a checkpoint id");
      checkpoint_load(dir,id,CheckpointVerify::metadata,op,false);
    } catch(const CheckpointRefusal&){reason="not_a_checkpoint";throw;}
    // 2. Exclusive, non-blocking: any restore/inspect/save holding the lock makes this in_use.
    std::unique_ptr<CheckpointLock> lock;
    try{lock=std::make_unique<CheckpointLock>(root,id,true,op);}
    catch(const CheckpointRefusal& r){reason=r.check=="lock"?"in_use":"io";throw;}
    // 3. Re-validate under the lock, remove exactly the manifest's file set, then the directory,
    //    then unlink the lock file while still holding it.
    reason="not_a_checkpoint";
    const auto loaded=checkpoint_load(dir,id,CheckpointVerify::metadata,op,false);
    reason="io";
    require(fs::remove(dir/"manifest.json"),"delete manifest.json");++removed;   // invisible first
    for(const auto& n:checkpoint_expected_files(loaded.m))if(n!="manifest.json"){require(fs::remove(dir/n),"delete "+n);++removed;}
    require(fs::remove(dir),"delete directory "+dir.string());
    checkpoint_fsync_dir(root);
    lock->unlink_while_held();
    deleted=true;reason.clear();
  } catch(const CheckpointRefusal& r){check=r.check;detail=r.detail;if(reason.empty())reason="io";}
    catch(const std::exception& error){check="io";detail=error.what();if(reason.empty())reason="io";}
  std::ostringstream o;
  o<<"{\"schema\":\"ownrt.checkpoint-delete.v1\",\"ok\":"<<(deleted?"true":"false")<<",\"deleted\":"<<(deleted?"true":"false")
   <<",\"checkpoint_dir\":"<<ownrt::quote(dir.string())<<",\"checkpoint_id\":"<<ownrt::quote(id)<<",\"files_removed\":"<<removed
   <<",\"reason\":";
  if(deleted)o<<"null,\"error\":null}";
  else o<<ownrt::quote(reason)<<",\"error\":{\"check\":"<<ownrt::quote(check)<<",\"detail\":"<<ownrt::quote(detail)<<"}}";
  std::cout<<o.str()<<"\n"<<std::flush;
  return deleted?0:1;
}
static int checkpoint_host_tool(const std::string& op,const fs::path& target) {
  if(op=="checkpoint-delete")return checkpoint_delete_tool(target);
  if(op=="checkpoint-inspect")return checkpoint_inspect_tool(target,false);
  if(op=="checkpoint-inspect-metadata")return checkpoint_inspect_tool(target,true);
  throw std::runtime_error("unknown checkpoint host tool "+op);
}

} // namespace pipeline
