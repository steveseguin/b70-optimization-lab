"""Apply the packet179 entry-TU native delta and harness edits (one-time, fail-closed).

Native delta: patch one-card/native-source/**/build/native/main.cpp (the authoritative
compiled source, NOT the lineage generated provenance copy) and write its new sibling
checkpoint.hpp with a relative quote include. Kernel arithmetic untouched: every kernel
object is relinked byte-identical from packet165 by build_checkpoint.py. Harness edits:
worker/measurement/screen/entry checkpoint kind, native-help-flags, budget growth.
"""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
OLD=P.parent/'packet165-warm-prefill'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')

NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
MAIN=P/'one-card'/NAT/'main.cpp'

CHECKPOINT_HPP=r'''// packet179 session checkpoint/restore -- EXPERIMENTAL (SESSION-SWAP-DESIGN.md v1.1).
// Entry-TU-only native delta: included solely by main.cpp via a relative quote include;
// no kernel arithmetic. TP1 (one-card) only; every compatibility check fails closed and
// names the failed check. Slicing: QSA keys/values/raw rows [0:N) on the dim0 position
// axis, pooled rows [0:N/4) floor (engine precedent: strict_snapshot.hpp valid_rows and
// the pool-completion quad rule in kernels.hpp; partial-quad state is whole in raw/keys/
// values). GDN history/state, PLE history, token_history (device-mutated shift register,
// restored verbatim, never reconstructed) and controls are whole. Skipped by name: qsa ids
// (scratch, recomputed per token by qsa_select), ple_metadata (static GGUF-derived, re-put
// by the request reset, covered by the model-identity check). Every plan buffer must match
// exactly one saved/named-skip/intermediate rule or the save refuses (completeness proof).
// Controls note: only position, token_history and history0/history1 are live at a token
// boundary; token/streams/next_token are dead (rewritten by broadcast/per-step put/argmax)
// and are saved whole anyway for design conformance. e.logical is ordering-relative, reset
// to zero in both arms, and deliberately not persisted.
#include <fcntl.h>
namespace pipeline {

struct SavedCheckpoint { int64_t position; int next_token; uint64_t bytes; double seconds; };
struct RestoredCheckpoint { std::vector<int> tokens; int next_token; int64_t history0, history1; int64_t position; double restore_seconds; };

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
  int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL,0644);
  require(fd>=0,"checkpoint create "+path.string());
  auto p=static_cast<const uint8_t*>(data);size_t left=n;
  while(left){ssize_t w=::write(fd,p,left);require(w>0,"checkpoint write "+path.string());p+=w;left-=size_t(w);}
  require(::fsync(fd)==0,"checkpoint fsync "+path.string());
  require(::close(fd)==0,"checkpoint close "+path.string());
}
static std::vector<uint8_t> checkpoint_read(const fs::path& path) {
  std::ifstream f(path,std::ios::binary);require(bool(f),"checkpoint read "+path.string());
  return std::vector<uint8_t>((std::istreambuf_iterator<char>(f)),{});
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
static std::string checkpoint_join(const std::vector<int>& v) {
  std::ostringstream o;for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];return o.str();
}

struct CheckpointFields {
  std::map<std::string,std::string> values;
  std::vector<std::array<std::string,4>> blobs;   // name, bytes, sha256, rows(-1 = whole)
  std::vector<std::pair<std::string,std::string>> skips;
};
static CheckpointFields checkpoint_fields(const fs::path& d) {
  CheckpointFields r;
  const auto fields_bytes=checkpoint_read(d/"fields.tsv");
  std::istringstream in{std::string(fields_bytes.begin(),fields_bytes.end())};
  std::string line;
  while(std::getline(in,line)) {
    if(line.empty())continue;
    std::vector<std::string> f;size_t at=0;
    while(true){auto tab=line.find('\t',at);f.push_back(line.substr(at,tab==std::string::npos?tab:tab-at));if(tab==std::string::npos)break;at=tab+1;}
    if(f[0]=="blob"){require(f.size()==5,"checkpoint fields blob row");r.blobs.push_back({f[1],f[2],f[3],f[4]});}
    else if(f[0]=="skip"){require(f.size()==3,"checkpoint fields skip row");r.skips.push_back({f[1],f[2]});}
    else {require(f.size()==2,"checkpoint fields value row");require(r.values.emplace(f[0],f[1]).second,"checkpoint fields duplicate "+f[0]);}
  }
  return r;
}

static SavedCheckpoint checkpoint_save(Engine& e,const fs::path& dir,const std::string& id,
                                       const std::vector<int>& prompt,const std::vector<int>& generated) {
  const auto started=std::chrono::steady_clock::now();
  require(!generated.empty(),"checkpoint save requires at least one generated token");
  std::vector<int> tokens=prompt;
  // The final generated token was computed by argmax but never stepped; the processed
  // prefix is prompt + generated minus that pending token.
  tokens.insert(tokens.end(),generated.begin(),generated.end()-1);
  const int64_t N=int64_t(tokens.size());
  const int next_token=generated.back();
  // Fail-closed self-checks against live device state.
  require(uint32_t(N)==uint32_t(e.integer(0,"position")),"checkpoint save position mismatch");
  require(!e.integer(0,"error"),"checkpoint save with sticky device error refused");
  require(N<e.p.g.context,"checkpoint position outside context");
  const fs::path d=dir/id;
  require(!fs::exists(d),"checkpoint id already exists");
  fs::create_directories(d);
  std::vector<uint8_t> token_bytes(size_t(N)*4);
  for(int64_t i=0;i<N;++i){uint32_t v=uint32_t(tokens[size_t(i)]);std::memcpy(token_bytes.data()+4*i,&v,4);}
  checkpoint_write(d/"tokens.bin",token_bytes.data(),token_bytes.size());
  const std::string tokens_sha=hash(token_bytes);
  const auto qsa_layers=checkpoint_layers(e,".qsa.keys"),gdn_layers=checkpoint_layers(e,".gdn.state");
  std::vector<std::string> blob_rows,blob_fields,skip_fields,skip_rows;
  uint64_t total_bytes=0;
  for(const auto& [name,s]:e.buffers[0]) {
    const std::string rule=checkpoint_rule(name);
    if(rule!="saved-sliced-kv"&&rule!="saved-whole") {
      skip_fields.push_back("skip\t"+name+"\t"+rule);
      skip_rows.push_back("{\"name\":"+ownrt::quote(name)+",\"rule\":"+ownrt::quote(rule)+"}");
      continue;
    }
    const size_t full=s.n*flash::scalar_bytes(s.type);
    const size_t bytes=rule=="saved-sliced-kv"?checkpoint_slice_bytes(e,name,full,N):full;
    auto data=e.readback(0,s.id,bytes);
    checkpoint_write(d/(name+".bin"),data.data(),data.size());
    total_bytes+=bytes;
    const int64_t rows=rule=="saved-sliced-kv"?(checkpoint_suffix(name,".qsa.pooled")?N/4:N):-1;
    blob_fields.push_back("blob\t"+name+"\t"+std::to_string(bytes)+"\t"+hash(data)+"\t"+std::to_string(rows));
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
  const auto& g=e.p.g;
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  std::ostringstream m;m.precision(17);
  m<<"{\"format\":\"ownrt.session-checkpoint.v1\",\"label\":\"experimental\",\"checkpoint_id\":"<<ownrt::quote(id)
   <<",\"created\":"<<ownrt::quote(iso)
   <<",\"model\":{\"identity_tsv_sha256\":"<<ownrt::quote(identity_sha)<<",\"shard_stat_rows\":[";
  for(size_t i=0;i<stat_rows.size();++i)m<<(i?",":"")<<stat_rows[i];
  m<<"]},\"engine\":{\"binary_sha256\":"<<ownrt::quote(binary_sha)<<",\"packet\":\"packet179-session-swap\",\"profile\":\"tp1-full512\"}"
   <<",\"geometry\":{\"layers\":"<<(qsa_layers.size()+gdn_layers.size())<<",\"qsa_layers\":["<<checkpoint_join(qsa_layers)
   <<"],\"gdn_layers\":["<<checkpoint_join(gdn_layers)<<"],\"kvh\":"<<g.kvh<<",\"ad\":"<<g.ad<<",\"ih\":"<<g.ih<<",\"id\":"<<g.id
   <<",\"gdn\":{\"kh\":"<<g.kh<<",\"vh\":"<<g.vh<<",\"d\":"<<g.d<<"},\"context\":"<<g.context<<",\"vocab\":"<<g.vocab<<",\"eos\":"<<g.eos<<"}"
   <<",\"dtypes\":{\"kv\":\"bf16\",\"gdn_state\":\"bf16\",\"ple\":\"bf16\"}"
   <<",\"token_state\":{\"prompt_length\":"<<prompt.size()<<",\"length\":"<<N<<",\"position\":"<<N<<",\"next_token\":"<<next_token
   <<",\"tokens_sha256\":"<<ownrt::quote(tokens_sha)<<",\"token_history\":["<<e.history0<<","<<e.history1<<"]}"
   <<",\"sampler\":{\"mode\":\"greedy-argmax\",\"state\":null}"
   <<",\"blobs\":[";
  for(size_t i=0;i<blob_rows.size();++i)m<<(i?",":"")<<blob_rows[i];
  m<<"],\"skipped_buffers\":[";
  for(size_t i=0;i<skip_rows.size();++i)m<<(i?",":"")<<skip_rows[i];
  m<<"],\"measurements\":{\"save_seconds\":"<<seconds<<",\"save_bytes\":"<<total_bytes<<"}}\n";
  checkpoint_write(d/"manifest.json.tmp",m.str().data(),m.str().size());
  std::ostringstream f;
  f<<"format\townrt.session-checkpoint.v1\n"<<"label\texperimental\n"<<"checkpoint_id\t"<<id<<"\n"<<"created\t"<<iso<<"\n"
   <<"position\t"<<N<<"\n"<<"prompt_length\t"<<prompt.size()<<"\n"<<"length\t"<<N<<"\n"<<"next_token\t"<<next_token<<"\n"
   <<"tokens_sha256\t"<<tokens_sha<<"\n"<<"history0\t"<<e.history0<<"\n"<<"history1\t"<<e.history1<<"\n"
   <<"identity_tsv_sha256\t"<<identity_sha<<"\n"<<"binary_sha256\t"<<binary_sha<<"\n"
   <<"kvh\t"<<g.kvh<<"\nad\t"<<g.ad<<"\nih\t"<<g.ih<<"\nid\t"<<g.id<<"\nkh\t"<<g.kh<<"\nvh\t"<<g.vh<<"\nd\t"<<g.d<<"\nqh\t"<<g.qh
   <<"\ncontext\t"<<g.context<<"\nvocab\t"<<g.vocab<<"\neos\t"<<g.eos<<"\nlayers\t"<<(qsa_layers.size()+gdn_layers.size())<<"\n"
   <<"qsa_layers\t"<<checkpoint_join(qsa_layers)<<"\ngdn_layers\t"<<checkpoint_join(gdn_layers)<<"\n"
   <<"save_seconds\t"<<seconds<<"\nsave_bytes\t"<<total_bytes<<"\n"
   <<"manifest_sha256\t"<<hash(checkpoint_read(d/"manifest.json.tmp"))<<"\n";
  for(const auto& row:blob_fields)f<<row<<"\n";
  for(const auto& row:skip_fields)f<<row<<"\n";
  checkpoint_write(d/"fields.tsv",f.str().data(),f.str().size());
  // The manifest rename is the visibility point: a partial or unverified
  // checkpoint is never visible to restore.
  fs::rename(d/"manifest.json.tmp",d/"manifest.json");
  return {N,next_token,total_bytes,seconds};
}

static RestoredCheckpoint checkpoint_restore(Engine& e,const fs::path& dir,const std::string& id,
                                             const std::vector<int>& prompt) {
  const auto started=std::chrono::steady_clock::now();
  const fs::path d=dir/id;
  auto refuse=[](const std::string& check,const std::string& detail) -> void {
    throw std::runtime_error("checkpoint restore refused: "+check+": "+detail);
  };
  if(!fs::exists(d/"manifest.json"))refuse("visibility","manifest.json missing (partial or unverified checkpoint)");
  const auto fields=checkpoint_fields(d);
  const auto& v=fields.values;
  auto at=[&](const char* key)->const std::string&{auto it=v.find(key);if(it==v.end())refuse("manifest fields",std::string("missing ")+key);return it->second;};
  if(at("format")!="ownrt.session-checkpoint.v1")refuse("format",at("format"));
  if(hash(checkpoint_read(d/"manifest.json"))!=at("manifest_sha256"))refuse("manifest sha256","manifest.json differs from the verified save-time content");
  if(checkpoint_self_sha256()!=at("binary_sha256"))refuse("engine identity","binary_sha256 differs from /proc/self/exe");
  const auto& g=e.p.g;
  auto want=[&](const char* key,int64_t value){if(std::stoll(at(key))!=value)refuse("geometry",std::string(key)+" checkpoint="+at(key)+" engine="+std::to_string(value));};
  want("kvh",g.kvh);want("ad",g.ad);want("ih",g.ih);want("id",g.id);want("kh",g.kh);want("vh",g.vh);want("d",g.d);want("qh",g.qh);
  want("context",g.context);want("vocab",g.vocab);want("eos",g.eos);
  const auto qsa_layers=checkpoint_layers(e,".qsa.keys"),gdn_layers=checkpoint_layers(e,".gdn.state");
  if(checkpoint_join(qsa_layers)!=at("qsa_layers"))refuse("geometry","qsa layer set differs");
  if(checkpoint_join(gdn_layers)!=at("gdn_layers"))refuse("geometry","gdn layer set differs");
  if(std::stoll(at("layers"))!=int64_t(qsa_layers.size()+gdn_layers.size()))refuse("geometry","layer count differs");
  const int64_t N=std::stoll(at("position"));
  if(N<1||N>=g.context)refuse("token state","position outside context allocation");
  if(std::stoll(at("length"))!=N)refuse("token state","length != position");
  auto token_bytes=checkpoint_read(d/"tokens.bin");
  if(token_bytes.size()!=size_t(N)*4)refuse("token state","tokens.bin extent");
  if(hash(token_bytes)!=at("tokens_sha256"))refuse("token state","tokens.bin sha256");
  std::vector<int> tokens(size_t(N),0);
  for(int64_t i=0;i<N;++i){uint32_t x;std::memcpy(&x,token_bytes.data()+4*i,4);tokens[size_t(i)]=int(x);}
  const int64_t plen=std::stoll(at("prompt_length"));
  if(plen<1||plen>N)refuse("token state","prompt length outside prefix");
  if(int64_t(prompt.size())!=plen||!std::equal(prompt.begin(),prompt.end(),tokens.begin()))
    refuse("prefix","continue prompt does not match the recorded prefix exactly");
  if(e.a.auth.empty()) {if(!at("identity_tsv_sha256").empty())refuse("model identity","full-model checkpoint on a mini engine");}
  else if(hash(checkpoint_read(e.a.auth))!=at("identity_tsv_sha256"))refuse("model identity","identity.tsv sha256/stat pins differ");
  // Completeness proof re-derived against live plan buffers before any upload.
  std::set<std::string> saved;
  for(const auto& [name,s]:e.buffers[0]) {
    const std::string rule=checkpoint_rule(name);
    if(rule=="saved-sliced-kv"||rule=="saved-whole") {
      const size_t full=s.n*flash::scalar_bytes(s.type);
      const size_t bytes=rule=="saved-sliced-kv"?checkpoint_slice_bytes(e,name,full,N):full;
      auto it=std::find_if(fields.blobs.begin(),fields.blobs.end(),[&](const std::array<std::string,4>& b){return b[0]==name;});
      if(it==fields.blobs.end())refuse("completeness","missing blob "+name);
      if(std::stoull((*it)[1])!=bytes)refuse("geometry","blob slice extent "+name);
      saved.insert(name);
    } else {
      auto it=std::find_if(fields.skips.begin(),fields.skips.end(),[&](const std::pair<std::string,std::string>& s){return s.first==name&&s.second==rule;});
      if(it==fields.skips.end())refuse("completeness","skip classification changed for "+name);
    }
  }
  if(saved.size()!=fields.blobs.size())refuse("completeness","blob count differs from live saved set");
  std::vector<std::pair<std::string,std::vector<uint8_t>>> datas;
  for(const auto& b:fields.blobs) {
    auto data=checkpoint_read(d/(b[0]+".bin"));
    if(data.size()!=std::stoull(b[1]))refuse("blob bytes",b[0]);
    if(hash(data)!=b[2])refuse("blob sha256",b[0]);
    datas.push_back({b[0],std::move(data)});
  }
  const int next_token=std::stoi(at("next_token"));
  for(const auto& [name,data]:datas) {
    if(name=="position"||name=="next_token") {
      int32_t x;std::memcpy(&x,data.data(),4);
      if(name=="position"&&int64_t(x)!=N)refuse("token state","position blob disagrees with manifest");
      if(name=="next_token"&&x!=next_token)refuse("token state","next_token blob disagrees with manifest");
    }
  }
  int fd=::open((d/"restore.lock").c_str(),O_WRONLY|O_CREAT|O_EXCL,0644);
  if(fd<0)refuse("lock","restore.lock exists (a restore is in flight)");
  struct LockGuard { fs::path p; ~LockGuard(){std::error_code ec;fs::remove(p,ec);} } guard{d/"restore.lock"};
  ::write(fd,"locked",6);::close(fd);
  // Runs after p58_reset_request: every request allocation is zeroed with its ID
  // preserved, so sliced blobs land on zeroed tails byte-exactly (neither arm ever
  // wrote those rows); ple_metadata was re-put by the same reset.
  for(const auto& [name,data]:datas) {
    auto it=e.buffers[0].find(name);
    if(it==e.buffers[0].end())refuse("geometry","engine buffer missing "+name);
    if(data.size()>it->second.n*flash::scalar_bytes(it->second.type))refuse("geometry","blob exceeds allocation "+name);
    e.upload(0,it->second.id,0,data.data(),data.size());
  }
  e.history0=std::stoll(at("history0"));e.history1=std::stoll(at("history1"));
  e.admit_position(int(N));
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  return {tokens,next_token,e.history0,e.history1,N,seconds};
}

static int checkpoint_host_tool(const char* op,const fs::path& target) {
  if(std::string(op)=="checkpoint-delete") {
    if(fs::exists(target/"restore.lock")){std::cout<<"{\"deleted\":false,\"reason\":\"in_use\"}\n";return 1;}
    require(fs::exists(target),"checkpoint directory missing");
    fs::remove_all(target);std::cout<<"{\"deleted\":true}\n";return 0;
  }
  require(std::string(op)=="checkpoint-inspect","checkpoint host tool");
  const auto manifest=checkpoint_read(target/"manifest.json");
  std::cout.write(reinterpret_cast<const char*>(manifest.data()),std::streamsize(manifest.size()));
  const auto fields=checkpoint_fields(target);
  if(hash(manifest)!=fields.values.at("manifest_sha256"))throw std::runtime_error("manifest sha256 mismatch");
  for(const auto& b:fields.blobs) {
    const auto data=checkpoint_read(target/(b[0]+".bin"));
    require(data.size()==std::stoull(b[1])&&hash(data)==b[2],"inspect blob verification failed: "+b[0]);
    std::cout<<"{\"blob\":"<<ownrt::quote(b[0])<<",\"bytes\":"<<b[1]<<",\"sha256_verified\":true}\n";
  }
  std::cout<<"{\"inspect\":\"ok\",\"label\":\"experimental\",\"device_required\":false}\n";
  return 0;
}

} // namespace pipeline
'''

def edit(path,old,new,count=1):
    text=path.read_text()
    assert text.count(old)==count,('anchor',path.name,old[:80],text.count(old))
    path.write_text(text.replace(old,new))

def main():
    p=P/'one-card'
    parent_main=(OLD/'one-card'/NAT/'main.cpp').read_text()
    MAIN.write_text(parent_main)  # idempotent rerun: restart from the parent bytes
    text=MAIN.read_text()
    assert text==parent_main,'scaffolded main.cpp differs from packet165 before patch'
    # 1. Options fields
    text=text.replace(
"""  fs::path inputs, output, model, plan, auth, oracle, suite_inputs, bracket_inputs;
};""",
"""  fs::path inputs, output, model, plan, auth, oracle, suite_inputs, bracket_inputs;
  fs::path checkpoint_save, checkpoint_restore; std::string checkpoint_id;
};""",1)
    # 2. --help (alphabetical, between --checked and --context)
    assert text.count('--checked --context')==1
    text=text.replace('--checked --context','--checked --checkpoint-delete --checkpoint-id --checkpoint-inspect --checkpoint-restore --checkpoint-save --context',1)
    # 3. parser branches
    anchor='    else if (k == "--suite-inputs") a.suite_inputs=value();\n'
    assert text.count(anchor)==1
    text=text.replace(anchor,anchor+
"""    else if (k == "--checkpoint-save") a.checkpoint_save=value();
    else if (k == "--checkpoint-restore") a.checkpoint_restore=value();
    else if (k == "--checkpoint-id") a.checkpoint_id=value();
""",1)
    # 4. guards
    ganchor='  require(a.native_nice>=0 && a.native_nice<=19'
    assert text.count(ganchor)==1
    text=text.replace(ganchor,
"""  require(a.checkpoint_save.empty()||a.checkpoint_restore.empty(),"checkpoint save and restore are exclusive");
  require((a.checkpoint_save.empty()&&a.checkpoint_restore.empty())||a.suite_inputs.empty(),"checkpoint modes are single-request only");
  require(a.checkpoint_id.empty()||(!a.checkpoint_save.empty()||!a.checkpoint_restore.empty()),"--checkpoint-id requires a checkpoint mode");
  if(!a.checkpoint_save.empty()||!a.checkpoint_restore.empty())
    require(!a.checkpoint_id.empty()&&a.checkpoint_id.size()<=64&&
            a.checkpoint_id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")==std::string::npos,
            "checkpoint id must be nonempty and filename-safe");
"""+ganchor,1)
    # 5. include after rank.hpp include
    assert text.count('rank.hpp"\n')==1
    text=text.replace('rank.hpp"\n','rank.hpp"\n#include "checkpoint.hpp"\n',1)
    # 6. pre-parse host branches in main(), before any device/model access
    manchor='  std::unique_ptr<Engine> e;\n  std::unique_ptr<Weights> w;\n  fs::path output;\n  std::string error;'
    assert text.count(manchor)==1
    text=text.replace(manchor,
"""  // Device-free checkpoint maintenance; parse() would require device authorization.
  if(argc==3&&(std::string(argv[1])=="--checkpoint-inspect"||std::string(argv[1])=="--checkpoint-delete")) {
    try{return pipeline::checkpoint_host_tool(argv[1]+2,argv[2]);}
    catch(const std::exception& error){std::cerr<<"checkpoint "<<(argv[1]+2)<<" failed: "<<error.what()<<"\\n";return 1;}
  }
"""+manchor,1)
    # 7. restore integration replacing the prefill head
    panchor='''    int next=-1;auto prefill_start=std::chrono::steady_clock::now();
    for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
    prefill_ms=Engine::ms(prefill_start);first_token_ms=first_generated_ms;'''
    assert text.count(panchor)==1
    text=text.replace(panchor,
'''    int next=-1;auto prefill_start=std::chrono::steady_clock::now();
    // Restore runs AFTER p58_reset_request (its zeroing makes sliced-KV byte-exact
    // and its reset.json receipt stays a hard gate); the prefill loop is skipped and
    // token_index starts at N so step()/admit_position match the uninterrupted run.
    pipeline::RestoredCheckpoint restored;const bool restoring=!a.checkpoint_restore.empty();double checkpoint_restore_ms=0;
    if(restoring){auto restore_start=std::chrono::steady_clock::now();
      restored=pipeline::checkpoint_restore(*e,a.checkpoint_restore,a.checkpoint_id,input);
      checkpoint_restore_ms=Engine::ms(restore_start);next=restored.next_token;token_index=size_t(restored.position);}
    else for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
    prefill_ms=restoring?0:Engine::ms(prefill_start);first_token_ms=first_generated_ms;
    std::ostringstream restore_ms_row;restore_ms_row.precision(17);restore_ms_row<<checkpoint_restore_ms;
    const std::string restore_ms_json=restoring?restore_ms_row.str():"null";''',1)
    # 8. decode loop: restore mode steps the pending token first, exactly M continuations
    danchor='    if(!a.first)for(int i=0;i<a.tokens;++i){\n'
    assert text.count(danchor)==1
    text=text.replace(danchor,
'''    if(!a.first&&restoring)for(int i=0;i<a.tokens;++i){
      next=step(next,i+2);
      generated.push_back(next);
      std::cout<<"token_id "<<next<<'\\n';
      if(next==p.g.eos || (!a.mini && next==248046))break;
    }
    else if(!a.first)for(int i=0;i<a.tokens;++i){
''',1)
    # 9. save hook at request end (decode boundary, queues drained)
    sanchor='    require(a.bracket_inputs.empty()||generated==expected_tokens.at(request_id),"packet49 completion length mismatch");\n'
    assert text.count(sanchor)==1
    text=text.replace(sanchor,sanchor+
'    if(!a.checkpoint_save.empty())pipeline::checkpoint_save(*e,a.checkpoint_save,a.checkpoint_id,input,generated);\n',1)
    # 10. result.json additive restore field
    ranchor='      <<",\\"prefill_ms\\":"<<prefill_ms<<",\\"first_generated_token_ms\\":"<<first_token_ms'
    assert text.count(ranchor)==1, text.count(ranchor)
    text=text.replace(ranchor,ranchor+'<<",\\"checkpoint_restore_ms\\":"<<restore_ms_json',1)
    (P/'one-card/lineage/packet179-native-delta.patch').write_text(''.join(difflib.unified_diff(
        parent_main.splitlines(True),text.splitlines(True),
        fromfile='packet165/'+NAT+'/main.cpp',tofile='packet179/'+NAT+'/main.cpp')))
    MAIN.write_text(text)
    (MAIN.parent/'checkpoint.hpp').write_text(CHECKPOINT_HPP)

    # ---- harness edits ---- (re-copy from parent first so reruns are idempotent)
    for leaf in ('worker.py','measurement.py','screen.py','entry.py','native-help-flags.json','budget.json'):
        src=(OLD/'one-card'/leaf).read_text()
        if leaf.endswith('.py'):src=src.replace('packet165-warm-prefill','packet179-session-swap')
        (p/leaf).write_text(src)
    worker=p/'worker.py'
    edit(worker,"""def prove_drain(receipts):""",
'''def checkpoint_command(output,max_new,mode,ckpt_root):
 """Single-request native argv for one checkpoint leg (save or restore)."""
 cmd=read(HERE/'parent-native-argv.json')
 require(cmd.count('--suite-inputs')==1,'native flag --suite-inputs')
 at=cmd.index('--suite-inputs');del cmd[at:at+2]
 def replace(k,v):require(cmd.count(k)==1,'native flag '+k);cmd[cmd.index(k)+1]=str(v)
 cmd[0]=str(HERE/'build/device/own-rt-iq3')
 for k,v in [('--max-new',max_new),('--seconds',7200),('--wait-seconds',600),('--output',output),
  ('--input',HERE/'inputs'/CHECKPOINT_PROMPT/'tokens.txt'),('--plan',HERE/'inputs/plan.tsv'),
  ('--identity',HERE/'inputs/identity.tsv'),('--selection',HERE/'selection.json'),('--selection-sha256',sha(HERE/'selection.json')),('--dispatch',HERE/'dispatch.json')]:replace(k,v)
 return ['/usr/bin/ionice','-c3',*cmd,mode,str(ckpt_root),'--checkpoint-id','gate']

def run_native(cmd,output):
 """One fresh native process with the same polling/stop discipline as one()."""
 child=None;stop=[]
 def signal_stop(sig,frame):
  stop.append(sig)
  if child is not None and child.poll()is None:child.send_signal(signal.SIGTERM)
 handlers={s:signal.signal(s,signal_stop)for s in(signal.SIGINT,signal.SIGTERM)}
 try:
  with(output/'native.log').open('w')as log:
   exec_limits.check();child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   while child.poll()is None:
    require(not stop,'coordinator stop');time.sleep(.25)
  require(child.returncode==0 and not stop,'native failed; no retry')
 finally:
  for s,h in handlers.items():signal.signal(s,h)

def checkpoint(output,reference):
 """Design 7.1/7.2 gate: save K=256, two independent restore M=128 continuations.

 Reference is this packet's own full512 row-A run of the same prompt and binary.
 """
 require(measurement.IDS[0]==CHECKPOINT_PROMPT,'checkpoint gate prompt')
 prompt=list(map(int,(HERE/'inputs'/CHECKPOINT_PROMPT/'tokens.txt').read_text().split()))
 oracle=read(HERE/'lineage/oracle128'/(CHECKPOINT_PROMPT+'.json'))['tokens']
 reference_result=read(Path(reference)/'run/native'/CHECKPOINT_PROMPT/'result.json')
 root=output/'checkpoints';results={}
 for leg,max_new,mode in [('save',CHECKPOINT_K,'--checkpoint-save'),('restore1',CHECKPOINT_M,'--checkpoint-restore'),('restore2',CHECKPOINT_M,'--checkpoint-restore')]:
  legout=output/'run'/leg;legout.mkdir(parents=True)
  dest=legout/'native'
  cmd=checkpoint_command(dest,max_new,mode,root);save(legout/'launch.json',dict(argv=cmd))
  run_native(cmd,legout)
  require((dest/'lookup-request-complete.json').is_file(),'completion marker missing: '+leg)
  reset=read(dest/'reset.json')
  require(reset.get('passed')is True and reset.get('cached_tokens')==0 and reset.get('allocation_ids_preserved')is True,'cold request reset missing: '+leg)
  streams={'timings.jsonl':measurement.check_file_stream(dest/'timings.jsonl')}
  if leg=='save':streams['prefill-timings.jsonl']=measurement.check_file_stream(dest/'prefill-timings.jsonl')
  save(dest/'stream-proof.json',dict(passed=True,streams=streams,scope='presence/format only; restore legs have an empty prefill stream by construction'))
  results[leg]=read(dest/'result.json')
  results[leg]['request_reset_sha256']=[sha(dest/'reset.json')]
 manifest=read(root/'gate/manifest.json')
 require(manifest.get('format')=='ownrt.session-checkpoint.v1' and manifest.get('label')=='experimental','checkpoint manifest identity')
 check=measurement.checkpoint_check(results['save'],results['restore1'],results['restore2'],reference_result,oracle,CHECKPOINT_K,CHECKPOINT_M)
 save(output/'checkpoint-receipt.json',dict(check,
  prompt_id=CHECKPOINT_PROMPT,prompt_tokens=len(prompt),save_max_new=CHECKPOINT_K,restore_max_new=CHECKPOINT_M,
  save_seconds=manifest['measurements']['save_seconds'],save_bytes=manifest['measurements']['save_bytes'],
  restore_ms=results['restore1'].get('checkpoint_restore_ms'),
  manifest_sha256=sha(root/'gate/manifest.json'),manifest=manifest,
  reference=str(Path(reference)),reference_result_sha256=sha(Path(reference)/'run/native'/CHECKPOINT_PROMPT/'result.json'),
  reset_sha256={leg:results[leg]['request_reset_sha256'] for leg in results},
  scope='experimental session checkpoint restart-and-continue gate; merged K+M stream versus this packet\\'s uninterrupted full512 row-A reference; oracle cap 128 on the merged stream; not a performance claim'))
 save(output/'teardown.json',prove_drain([read(output/'run'/leg/'native/receipt.json') for leg in ('save','restore1','restore2')]))

def prove_drain(receipts):''')
    edit(worker,"""import measurement
import exec_limits
""","""import measurement
import exec_limits

CHECKPOINT_PROMPT='incident-retrospective'
CHECKPOINT_K=256
CHECKPOINT_M=128
""")
    edit(worker,""" ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--lane',choices=('A','B'),required=True);a=ap.parse_args()
 require((a.output.parent/'window.json').is_file(),'outer admitted window required')
 identity=read(a.output.parent/'identity.json');require(identity['lane']==a.lane,'lane binding')
 a.output.mkdir();items=entries()""",""" ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--lane',choices=('A','B'),required=True)
 ap.add_argument('--kind',choices=('full512','checkpoint'),default='full512');ap.add_argument('--reference',type=Path);a=ap.parse_args()
 require((a.output.parent/'window.json').is_file(),'outer admitted window required')
 identity=read(a.output.parent/'identity.json');require(identity['lane']==a.lane,'lane binding')
 a.output.mkdir()
 if a.kind=='checkpoint':
  require(a.reference is not None,"--kind checkpoint requires --reference (this packet's full512 row-A output)")
  checkpoint(a.output,a.reference);return 0
 items=entries()""")

    measurement=p/'measurement.py'
    text=measurement.read_text()
    text+='''
def checkpoint_check(save,restore1,restore2,reference,expected,k,m):
 """Restart-and-continue exactness plus repeat determinism (design 7.1/7.2/7.3)."""
 for leg in (save,restore1,restore2):stream_check(leg)
 require(len(save['tokens'])==k and not any(t in EOS for t in save['tokens']),'checkpoint save must complete K tokens without EOS')
 require(restore1['tokens']==restore2['tokens'],'repeat restore determinism')
 require(len(restore1['tokens'])==m,'restore continuation length')
 merged=save['tokens']+restore1['tokens']
 require(merged==reference.get('tokens',[])[:k+m],'merged checkpoint stream differs from the uninterrupted fresh-process reference')
 combined=dict(save)
 combined.update(tokens=merged,requested_max_new=k+m,
  timing_rows=save['timing_rows']+restore1['timing_rows'],
  request_start_monotonic=save['request_start_monotonic'],request_end_monotonic=restore1['request_end_monotonic'])
 oracle=stream_check(combined,expected)
 rows=reference.get('timing_rows',[]);require(len(rows)>=k,'reference timing stream short')
 cold_prefix_ms=1000*(rows[k-1]['completed_monotonic']-reference['request_start_monotonic'])
 return dict(passed=True,device_executed=False,merged_tokens=k+m,reference_tokens_compared=k+m,
  repeat_restore_identical=True,save_eos_free=True,oracle_check=oracle,
  cold_prefix_ms=cold_prefix_ms,
  cold_prefix_definition='uninterrupted reference request start through its K-th generated token (cold prefill plus decode of the same prefix), same prompt same binary',
  restore_continuation_wall_ms=1000*(restore1['request_end_monotonic']-restore1['request_start_monotonic']))
'''
    measurement.write_text(text)

    screen=p/'screen.py'
    edit(screen,"ap.add_argument('--kind',choices=('full512','smoke','bracket'),default='full512')",
         "ap.add_argument('--kind',choices=('full512','smoke','bracket','checkpoint'),default='full512')")
    edit(screen," command=['/usr/bin/python3','-B',str(HERE/'worker.py'),'--output',str(args.output/'run'),'--lane',args.lane]",
""" command=['/usr/bin/python3','-B',str(HERE/'worker.py'),'--output',str(args.output/'run'),'--lane',args.lane,'--kind',args.kind]
 if args.reference:command+=['--reference',str(args.reference)]""")
    edit(screen,"""  second_fresh_attempt=bool(args.reference),prefill=dict(users=1,cached_tokens=0,request_index=1,warmup_prompt=measurement.IDS[0],suite_prompt_used_once=True),submission_eligible=False)""",
"""  second_fresh_attempt=bool(args.reference),prefill=dict(users=1,cached_tokens=0,request_index=1,warmup_prompt=measurement.IDS[0],suite_prompt_used_once=True),submission_eligible=False)
 if args.kind=='checkpoint':
  plan.update(model_loads=3,request_count=3,requested_max_new=None,prefill=None,
   checkpoint=dict(prompt=measurement.IDS[0],save_max_new=256,restore_max_new=128,restore_launches=2,experimental=True,
    gate='save K=256 then two independent restore M=128 continuations; merged stream must equal this packet\\'s full512 row-A reference at [0:384); repeat-restore determinism; oracle-128 prefix on the merged stream'))""")
    edit(screen," require(args.kind=='full512','short synthetic report modes cannot launch devices')",
         " require(args.kind in('full512','checkpoint'),'short synthetic report modes cannot launch devices')")
    edit(screen,"""def report_completed(output,record,identity,coordination):
 proof=read(output/'run/report-inputs.json')""","""def report_completed(output,record,identity,coordination):
 if identity.get('bracket',{}).get('kind')=='checkpoint':
  receipt=read(output/'run/checkpoint-receipt.json')
  require(receipt.get('passed') is True and receipt.get('device_executed') is False,'checkpoint gate receipt incomplete')
  result=dict(receipt)
  result.update(kind='checkpoint',lane=identity['lane'],
   scope=coordination.get('scope','report-rehearsal'),device_executed=bool(record.get('device_executed')),
   source_receipt_sha256=sha(output/'run/checkpoint-receipt.json'),report_after_device_release=True,
   strict512=False,submission_eligible=False,experimental_checkpoint=True)
  save(output/'summary.json',result);save(output/'bracket-summary.json',result)
  return result
 proof=read(output/'run/report-inputs.json')""")

    entry=p/'entry.py'
    edit(entry,"ap.add_argument('--kind',choices=('full512','smoke','bracket'),default='full512',help='smoke/bracket accepted only by offline report compatibility tests')",
         "ap.add_argument('--kind',choices=('full512','smoke','bracket','checkpoint'),default='full512',help='smoke/bracket accepted only by offline report compatibility tests; checkpoint is the experimental session save/restore gate')")

    flags=json.loads((p/'native-help-flags.json').read_text())
    at=flags.index('--checked')+1
    for flag in ('--checkpoint-delete','--checkpoint-id','--checkpoint-inspect','--checkpoint-restore','--checkpoint-save'):
        flags.insert(at,flag);at+=1
    save(p/'native-help-flags.json',flags)

    budget=json.loads((p/'budget.json').read_text())
    budget['planned_write_bytes']=300_000_000
    budget['checkpoint_planned_blob_bytes']=200_000_000
    budget['checkpoint_note']='checkpoint blobs ~76-175 MB per save at gate fill plus a third native run; floors unchanged'
    budget['expected_seconds']=[1200,3600]
    budget['checkpoint_extra_model_loads']=2
    save(p/'budget.json',budget)

    save(p/'evidence/native-delta.json',dict(passed=True,device_executed=False,
        entry_tu_only=True,patched=[NAT+'/main.cpp'],added=[NAT+'/checkpoint.hpp'],
        parent_main_sha256=hashlib.sha256(parent_main.encode()).hexdigest(),
        patched_main_sha256=sha(MAIN),checkpoint_hpp_sha256=sha(MAIN.parent/'checkpoint.hpp'),
        patch_sha256=sha(P/'one-card/lineage/packet179-native-delta.patch'),
        harness_files=['worker.py','measurement.py','screen.py','entry.py','native-help-flags.json','budget.json'],
        kernel_arithmetic='unchanged by construction: only the entry TU textual closure changed; kernel objects relinked byte-identical from packet165 by build_checkpoint.py',
        scope='experimental session checkpoint/restore (SESSION-SWAP-DESIGN.md v1.1); argv + run() hooks + new header; device qualification pending'))
    print('native delta + harness edits applied; main.cpp patched, checkpoint.hpp written')

if __name__=='__main__':main()
