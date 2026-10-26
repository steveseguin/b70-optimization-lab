#pragma once
// Opt-in rank-level session checkpoint (lab, 2026-10-26). Three rank commands, none sent by any existing controller:
//   17 STAGE   at a token boundary (N tokens processed, the pending token not yet stepped): classify every mutable
//              allocation with one named rule, write the saved bytes as ONE sealed gsq_bundle (state.bundle,
//              state-index.tsv, state.json, state-seal.txt) into a fresh directory.
//   18 VERIFY  only directly after the request reset (op 11): position 0, bank parity 0. Read and hash the bundle,
//              check the engine identity, re-classify the live engine and require the identical coverage, hold the
//              bytes in host memory.
//   19 APPLY   only directly after a successful VERIFY: upload every saved blob by its LOGICAL role (buffers[0].at(name),
//              so the physical bank behind a recurrent name does not matter), restore the host fields, admit position N.
// The next command is then the ordinary half at position N with the pending token.
// Request plumbing: the checkpoint directory comes in <rank --output>/checkpoint-<sequence>.txt (line 1: normalized
// absolute directory; optional line 2: an opaque prefix tag that VERIFY must match), the same convention as the
// reset (op 11) and redirect (op 16) metadata files. Request fields: position = N (all three ops), token = pending
// token or -1 (STAGE records it, VERIFY checks it when >= 0), fixture bit 0 = STAGE: require device next_token ==
// token; APPLY: read every uploaded region back and compare.
// Refusals that precede any device mutation (request/file/identity/coverage/sequence) reply status 2, error = op,
// and leave the engine as it was; device faults stay fatal as everywhere in this engine.
namespace pipeline { namespace session {
constexpr int stage_op=17,verify_op=18,apply_op=19;
inline constexpr const char* schema="ownrt.session-checkpoint.rank.v1";
struct Refusal:std::runtime_error{using std::runtime_error::runtime_error;};
static void refuse_unless(bool ok,const std::string& why){if(!ok)throw Refusal(why);}

// ------------------------------------------------------------------ classification (one named rule per allocation)
struct Item {
 std::string label,source,rule,blob;Allocation id=0;size_t full=0,bytes=0;int64_t rows=-1;bool saved=false;
};
static bool control_name(const std::string& n){return n=="token"||n=="position"||n=="active"||n=="error"||n=="next_token";}
static bool kv_suffix(const std::string& n){return ends(n,".keys")||ends(n,".values")||ends(n,".raw")||ends(n,".pooled");}
static void fail_closed(const std::string& n,const std::string& where){
 for(const char* bad:{"history",".state","keys","values","raw","pooled","metadata","token","position"})
  refuse_unless(n.find(bad)==std::string::npos,"checkpoint coverage refused: unclassified persistent-looking "+where+" buffer "+n);
}
// dim0 is the position axis of every QSA KV-family buffer; pooled holds one row per four positions and only complete
// pools are written (qsa_append_pool writes pools b < (pos+1)/4), so after N positions rows [0, N/4) are live.
static size_t kv_slice(int context,const std::string& name,size_t full,int64_t positions,int64_t& rows){
 const bool pooled=ends(name,".pooled");const size_t total=pooled?size_t((context+3)/4):size_t(context);
 require(total>0&&full%total==0,"checkpoint KV row geometry "+name);
 require(positions>=0&&positions<=context,"checkpoint KV row bound "+name);
 rows=pooled?positions/4:positions;return size_t(rows)*(full/total);
}
static const char* const kv_rule="saved: QSA KV rows [0,N) (pooled [0,N/4)); tail rows are zero after the request reset";
static const char* const temporal_rule="saved: recurrent temporal state (gdn/conv output[1]: GDN state, conv/PLE history), active logical bank";
static const char* const token_history_rule="saved: PLE token history (device token pair hashed by ple_hash)";
static const char* const control_rule="saved: control scalar";
static const char* const draft_streams_rule="saved: boundary hidden stream, input of the rank-1 draft's next step";
static const char* const reserve_rule="skip: third recurrent bank (miss banks), zeroed by SpeculativeImage::boundary() before STAGE and by the request reset; only ever rotated in as a write destination";
static std::string standalone_rule(Engine& e,Allocation id,const ownrt::Row& row) {
 const auto& l=row.label;
 if(e.immutable_snapshot_tables.contains(id)){require(l=="card0:speculative-static-copy-table","immutable snapshot registration");
  return "skip: immutable static snapshot copy table (load-time geometry), preserved by the request reset";}
 if(l=="card0:speculative-private-image")return "skip: speculative rollback image, zeroed by SpeculativeImage::boundary() before STAGE and by the request reset; rewritten by begin() before any restore reads it";
 if(l=="card0:speculative-copy-table")return "skip: flat snapshot descriptor table, zeroed at the boundary; rewritten by every snapshot copy before its kernel reads it";
 if(e.head_auxiliary.count(id))return "skip: p105 head-suffix service scratch, written per head step before it is read";
 if(e.probe_auxiliary.count(id))return "skip: p149 probe exchange scratch, written by the exchange before it is read (probe=off: never)";
 if(!e.one.empty()&&id==e.one[0]){require(l=="card0:mixture-one","mixture constant label");return "skip: constant 1.0f, re-put by the request reset";}
 if(l.starts_with("card0:prefill:")){require(row.lifetime==Lifetime::transaction,"checkpoint prefill shadow lifetime "+l);
  return "skip: batched-prefill row shadow, reached only inside prefill_chunk through row views and written there before it is read";}
 if(l=="card0:draft:depth-probe-backup")return "skip: draft depth-probe backup (diagnostic), written by each probe before it is read";
 static const std::set<std::string> scratch{"card0:parallel-controls:0","card0:attention-scores:0","card0:attention-probabilities:0",
  "card0:layer-snapshots:0","card0:prepared-fp32-input","card0:gemv-workspace","card0:compact-routes","card0:ordered-mixture","card0:operator-scratch"};
 if(scratch.count(l)){require(row.lifetime==Lifetime::transaction,"checkpoint scratch lifetime "+l);return "skip: per-launch transaction scratch, written before it is read within each launch";}
 throw Refusal("checkpoint coverage refused: unclassified standalone allocation "+l);
}
static std::vector<Item> classify(Engine& e,mtp36::DraftRuntime* draft,int64_t N,int64_t D) {
 std::vector<Item> out;std::set<Allocation> represented;std::set<std::string> kv,temporal;
 require(e.v3_skip_half.size()==e.p.launches.size(),"checkpoint V3 site table");
 for(size_t i=0;i<e.p.launches.size();++i){const auto& l=e.p.launches[i];
  if(l.op=="qsa_append_pool")kv.insert(l.outputs.begin(),l.outputs.end());
  if((l.op=="gdn"||l.op=="conv")&&!e.v3_skip_half[i]){require(l.outputs.size()==2,"checkpoint temporal output count");temporal.insert(l.outputs[1]);}
 }
 const bool rank1_draft=e.a.mtp&&e.a.rank==1&&e.a.draft_rank==1; // that draft reads the target's final streams (non-F32 lane)
 for(const auto& [name,s]:e.buffers[0]) {
  Item it;it.label=name;it.source="plan";it.id=s.id;it.full=s.n*flash::scalar_bytes(s.type);represented.insert(s.id);
  refuse_unless(name.find("#tp")==std::string::npos,"checkpoint coverage refused: TP half buffer "+name);
  if(kv.count(name)){require(kv_suffix(name),"checkpoint KV writer output name "+name);it.saved=true;it.rule=kv_rule;it.bytes=kv_slice(e.p.g.context,name,it.full,N,it.rows);}
  else if(temporal.count(name)){it.saved=true;it.rule=temporal_rule;it.bytes=it.full;}
  else if(name=="token_history"){it.saved=true;it.rule=token_history_rule;it.bytes=it.full;}
  else if(control_name(name)){it.saved=true;it.rule=control_rule;it.bytes=it.full;}
  else if(name=="streams"&&rank1_draft){it.saved=true;it.rule=draft_streams_rule;it.bytes=it.full;}
  else if(name=="streams")it.rule="skip: per-half residual stream, fully rewritten at the start of every half before it is read (rank 1: shared-slot upload; rank 0: embedding broadcast)";
  else if(name=="ple_metadata")it.rule="skip: static GGUF-derived PLE hash metadata, re-put by the request reset (covered by the model identity)";
  else {fail_closed(name,"target");it.rule="skip: plan intermediate, written by its producing launch in every token step before it is read";}
  if(it.saved)it.blob="target."+name+".bin";
  out.push_back(std::move(it));
 }
 for(const auto& [name,id]:e.state_spares) {
  Item it;it.label="alternate:"+name;it.source="spare";it.id=id;it.full=e.dev(0).arena.row(id).bytes;represented.insert(id);
  const auto proof=RedoBankProof::derive(e.p,name);
  refuse_unless(temporal.count(name)&&proof.bytes==it.full&&proof.bytes>0,"checkpoint coverage refused: alternate bank without a full-overwrite proof "+name);
  it.rule="skip: alternate recurrent bank, dead at a boundary: the next half's "+proof.writer+" overwrites all of it before any read (RedoBankProof)";
  out.push_back(std::move(it));
 }
 for(const auto& [name,id]:e.state_reserves){represented.insert(id);
  Item it;it.label="speculative-reserve:"+name;it.source="reserve";it.id=id;it.full=e.dev(0).arena.row(id).bytes;it.rule=reserve_rule;out.push_back(std::move(it));}
 std::set<Allocation> draft_ids;mtp36::DraftRuntime::CheckpointView view;
 if(draft){view=draft->checkpoint_view();draft_ids=*view.mutable_ids;}
 for(const auto& [id,owner]:e.allocations) {
  const auto& row=e.dev(owner.first).arena.row(id);
  if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab||represented.count(id)||draft_ids.count(id))continue;
  refuse_unless(owner.first==0,"checkpoint coverage refused: allocation on card "+std::to_string(owner.first));
  Item it;it.id=id;it.full=row.bytes;it.label=row.label;it.source="standalone";it.rule=standalone_rule(e,id,row);out.push_back(std::move(it));
 }
 if(draft) {
  std::set<std::string> draft_kv;for(const auto& l:view.plan->launches)if(l.op=="qsa_append_pool")draft_kv.insert(l.outputs.begin(),l.outputs.end());
  std::set<Allocation> typed;
  for(const auto& [name,s]:*view.buffers) {
   require(view.mutable_ids->count(s.id),"checkpoint draft buffer outside the draft mutable set "+name);typed.insert(s.id);
   Item it;it.label="draft:"+name;it.source="draft";it.id=s.id;it.full=s.n*flash::scalar_bytes(s.type);
   if(draft_kv.count(name)){require(kv_suffix(name),"checkpoint draft KV writer output name "+name);it.saved=true;it.rule="saved: draft KV rows [0,D) (pooled [0,D/4)); tail rows are zero after the request reset";it.bytes=kv_slice(e.p.g.context,name,it.full,D,it.rows);}
   else if(control_name(name)){it.saved=true;it.rule="saved: draft control scalar";it.bytes=it.full;}
   else {fail_closed(name,"draft");it.rule="skip: draft intermediate, written in every draft step before it is read (merge inputs are uploaded per step)";}
   if(it.saved)it.blob="draft."+name+".bin";
   out.push_back(std::move(it));
  }
  for(auto id:*view.mutable_ids){if(typed.count(id))continue;const auto& row=e.dev(0).arena.row(id);
   require(row.category!=Category::weights&&row.category!=Category::kv,"checkpoint draft scratch category "+row.label);
   Item it;it.label=row.label;it.source="draft-scratch";it.id=id;it.full=row.bytes;
   it.rule="skip: draft scratch (scratch, controls, scores, probabilities, head workspace), written before it is read in every draft step";
   out.push_back(std::move(it));
  }
 }
 // Deterministic order independent of allocation handles: by source, then label.
 std::stable_sort(out.begin(),out.end(),[](const Item& x,const Item& y){return std::tie(x.source,x.label)<std::tie(y.source,y.label);});
 std::set<std::string> labels,blobs;
 for(const auto& it:out){
  require(labels.insert(it.source+"/"+it.label).second,"checkpoint coverage label not unique: "+it.label);
  require(it.label.find_first_of("\t\n")==std::string::npos&&it.rule.find_first_of("\t\n")==std::string::npos,"checkpoint coverage text field");
  if(it.saved){gsq_bundle::name_ok(it.blob);require(blobs.insert(it.blob).second&&it.bytes<=it.full,"checkpoint blob name/extent "+it.blob);}
 }
 return out;
}
static std::string coverage_text(const std::vector<Item>& items) {
 std::ostringstream o;o<<"label\tsource\trule\tblob\tfull\tbytes\trows\n";
 for(const auto& it:items)o<<it.label<<'\t'<<it.source<<'\t'<<it.rule<<'\t'<<(it.saved?it.blob:"-")<<'\t'<<it.full<<'\t'<<it.bytes<<'\t'<<it.rows<<'\n';
 return o.str();
}
// Host fields of the rank (request_state_inventory.hpp plus the draft runtime) and their rules.
static const std::vector<std::pair<std::string,std::string>>& host_rules() {
 static const std::vector<std::pair<std::string,std::string>> r{
  {"history0","saved: host PLE history mirror (rank 0 prepare_token input; rank 1 stays eos)"},
  {"history1","saved: host PLE history mirror (rank 0 prepare_token input; rank 1 stays eos)"},
  {"lookup_ids","skip: recomputed by prepare_token from (token, history) before every lookup; cleared by the request reset"},
  {"selected","skip: layer-streaming expert selection; resident engines never read it; cleared by the request reset"},
  {"loaded_layer","skip: layer-streaming residency; resident engines never read it"},
  {"fp32_cache","skip: cache-validity metadata, invalidated by every bank swap and by the request reset"},
  {"bank_parity","recorded: restore lands after the request reset (parity 0); recurrent state is uploaded by logical name"},
  {"active_bank/spare_bank","recorded: physical bank placement; restored by logical name"},
  {"launch_extent","recorded: re-derived by admit_position(N) at apply and before every half"},
  {"alternate_launch_extent","recorded: re-derived by admit_position before every half that uses the bank"},
  {"logical_event","skip: ordering-relative event counter, reset to 0 by the request reset"},
  {"poisoned","checked: must be false"},
  {"speculative_image","checked: boundary() retired every speculation before STAGE; private host snapshot empty"},
  {"draft.position","saved: draft host position D (rank 0 provider)"},
  {"draft.disabled","saved: draft sticky disable flag"},
  {"draft.context_extent","recorded: re-derived by DraftRuntime::admit_position from the position"},
  {"draft.reverse_hidden","checked: none pending at STAGE; the coordinator saves the reverse hidden row (shared map) itself"}};
 return r;
}
// ------------------------------------------------------------------ identity
static std::string file_sha256(const fs::path& path) {
 std::ifstream f(path,std::ios::binary);refuse_unless(bool(f),"checkpoint identity: cannot read "+path.string());
 std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)),{});return hash(bytes);
}
static const std::string& self_sha256() {
 static const std::string value=[]{
  gsq_bundle::FD f(::open("/proc/self/exe",O_RDONLY|O_CLOEXEC));require(f.n>=0,"checkpoint identity: open /proc/self/exe");
  gsq_bundle::Hash h;std::vector<char> b(size_t(4)<<20);
  for(;;){auto n=::read(f.n,b.data(),b.size());if(n<0&&errno==EINTR)continue;require(n>=0,"checkpoint identity: read /proc/self/exe");if(!n)break;h.add(b.data(),size_t(n));}
  return h.finish();}();
 return value;
}
static std::string plan_sha256(const flash::Plan& p) {
 std::ostringstream o;const auto& g=p.g;
 o<<"g "<<g.h<<' '<<g.low<<' '<<g.experts<<' '<<g.top<<' '<<g.mid<<' '<<g.kh<<' '<<g.vh<<' '<<g.d<<' '<<g.qh<<' '<<g.kvh<<' '<<g.ad<<' '<<g.ih<<' '<<g.id<<' '<<g.rotary<<' '<<g.budget<<' '<<g.context<<' '<<g.vocab<<' '<<g.eos<<'\n';
 for(const auto& b:p.buffers){o<<"b "<<b.name<<' '<<int(b.type)<<' '<<b.card;for(int x:b.shape)o<<' '<<x;o<<'\n';}
 for(const auto& l:p.launches){o<<"l "<<l.op<<' '<<l.label<<' '<<l.card<<' '<<l.parameter<<' '<<l.source_card<<' '<<l.row_begin<<' '<<l.row_count<<" |";
  for(const auto& x:l.inputs)o<<' '<<x;o<<" |";for(const auto& x:l.outputs)o<<' '<<x;o<<" |";for(const auto& x:l.weights)o<<' '<<x;o<<" |";for(int x:l.shape)o<<' '<<x;o<<'\n';}
 return gsq_bundle::digest(o.str());
}
static std::vector<std::pair<std::string,std::string>> identity(Engine& e,mtp36::DraftRuntime* draft) {
 const auto& a=e.a;const auto& g=e.p.g;std::vector<std::pair<std::string,std::string>> id;
 auto put=[&](const std::string& k,const std::string& v){require(v.find_first_of("\t\n")==std::string::npos,"checkpoint identity value "+k);id.emplace_back("identity."+k,v);};
 auto flag=[](bool b){return std::string(b?"1":"0");};
 put("binary_sha256",self_sha256());put("plan_sha256",plan_sha256(e.p));put("arithmetic",arithmetic::version);
 put("selection_observed_sha256",e.sealed_selection.observed_sha256);
 {std::ostringstream s;for(const auto& [k,v]:e.sealed_selection.choices)s<<"c "<<k<<'='<<v<<'\n';for(const auto& [k,v]:e.sealed_selection.draft)s<<"d "<<k<<'='<<v<<'\n';put("selection_choices_sha256",gsq_bundle::digest(s.str()));}
 put("dispatch_sha256",a.dispatch.empty()?"none":file_sha256(a.dispatch));
 put("model_identity_sha256",a.auth.empty()?"none":file_sha256(a.auth));put("model_dir",a.model.string());
 put("draft_manifest_sha256",(draft&&!a.mini)?file_sha256(a.draft_manifest):"none");
 put("rank",std::to_string(a.rank));put("cards",std::to_string(a.cards));put("memory",a.memory);put("context",std::to_string(a.context));
 put("f32_activations",flag(a.f32_activations));put("gsq_packed",flag(a.gsq_packed));put("target_split",std::to_string(a.target_split));
 put("draft_rank",std::to_string(a.draft_rank));put("mtp",flag(a.mtp));put("draft_present",flag(draft!=nullptr));put("draft_experts_fp8",flag(a.draft_experts_fp8));
 put("mini",flag(a.mini));put("tp_replicate",flag(a.tp_replicate));put("prefill_rows",std::to_string(a.prefill_rows));put("legacy",flag(a.legacy));
 put("nongemv",a.nongemv);put("gemv",a.gemv);
 put("kernel_flags",flag(a.attention_q8_p33)+flag(a.qkv_q6_p33)+flag(a.expert_iq3xxs_block)+flag(a.dense_q6_p33)+flag(a.dense_packed_block));
 put("geometry",std::to_string(g.h)+","+std::to_string(g.kvh)+","+std::to_string(g.ad)+","+std::to_string(g.ih)+","+std::to_string(g.id)+","+std::to_string(g.qh)+","+
  std::to_string(g.kh)+","+std::to_string(g.vh)+","+std::to_string(g.d)+","+std::to_string(g.budget)+","+std::to_string(g.context)+","+std::to_string(g.vocab)+","+std::to_string(g.eos));
 for(const char* name:{"OWNRT_MISS","OWNRT_SNAPSHOT_HOST","OWNRT_DRAFT_KERNELS","OWNRT_DRAFT_PREFIX_ROWS","OWNRT_DRAFT_HEAD_Q4","OWNRT_TP_SPLIT","OWNRT_TP_EXPERTS",
   "OWNRT_MERGE_CHECKS","OWNRT_PREFILL_NATIVE","OWNRT_PREFILL_ATTN_ROWS","OWNRT_LOOKUP_COPY"}){const char* v=std::getenv(name);put(std::string("env.")+name,v?std::string(v):std::string("<unset>"));}
 return id;
}
// Paths with checkpoint state (V3 islands outside the banks, TP twins, pipeline stages, streaming) are refused.
static void supported(const Engine& e) {
 refuse_unless(!e.a.pipeline_enabled()&&!e.a.tp_replicate&&e.a.cards==1&&e.resident&&e.prepared_path&&!e.v3_extended&&!e.v3_active&&!e.prepare_async&&!e.split_head(),
  "checkpoint ops: unsupported engine path (pipeline, TP, streaming/legacy, V3, async prepare or split head)");
}
// ------------------------------------------------------------------ request file, header, bundle reader
struct Target {fs::path dir;std::string tag;std::set<std::string> compat;};
static Target read_request(const fs::path& metadata) {
 std::ifstream in(metadata);refuse_unless(bool(in),"checkpoint request file missing: "+metadata.string());
 std::string dir,tag,extra;refuse_unless(bool(std::getline(in,dir))&&!dir.empty(),"checkpoint request: directory line");
 if(!std::getline(in,tag))tag.clear();
 // Optional third line, VERIFY only: "compat <sha256>[,<sha256>...]", engine binaries whose checkpoints the coordinator
 // has gated as state-identical to this binary (service canary: a restored foreign checkpoint, continued, equals the
 // fresh read in tokens, guesses and full state). Only identity.binary_sha256 may then differ; every other identity
 // field and the live coverage must still match exactly.
 std::set<std::string> compat;
 if(std::getline(in,extra)&&!extra.empty()){
  refuse_unless(extra.rfind("compat ",0)==0,"checkpoint request: third line must be 'compat <sha256,...>'");
  std::string list=extra.substr(7);size_t start=0;
  for(;;){const size_t comma=list.find(',',start);const std::string item=list.substr(start,comma==std::string::npos?std::string::npos:comma-start);
   refuse_unless(item.size()==64&&item.find_first_not_of("0123456789abcdef")==std::string::npos,"checkpoint request: compat sha256");
   compat.insert(item);if(comma==std::string::npos)break;start=comma+1;}
  refuse_unless(compat.size()<=16,"checkpoint request: at most 16 compat binaries");
 }
 while(std::getline(in,extra))refuse_unless(extra.empty(),"checkpoint request: at most three lines");
 const fs::path p(dir);refuse_unless(p.is_absolute()&&p==p.lexically_normal()&&!p.filename().empty()&&p.has_parent_path(),"checkpoint request: normalized absolute directory "+dir);
 refuse_unless(tag.size()<=256&&tag.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")==std::string::npos,"checkpoint request: tag characters");
 return {p,tag,std::move(compat)};
}
using Header=std::map<std::string,std::string>;
static Header parse_header(const std::vector<uint8_t>& bytes) {
 Header h;std::istringstream in(std::string(bytes.begin(),bytes.end()));std::string line;
 while(std::getline(in,line)){auto tab=line.find('\t');refuse_unless(tab!=std::string::npos&&tab>0&&line.find('\t',tab+1)==std::string::npos,"checkpoint header row");
  refuse_unless(h.emplace(line.substr(0,tab),line.substr(tab+1)).second,"checkpoint header duplicate key "+line.substr(0,tab));}
 return h;
}
static const std::string& field(const Header& h,const std::string& k){auto f=h.find(k);refuse_unless(f!=h.end(),"checkpoint header lacks "+k);return f->second;}
static int64_t integer_field(const Header& h,const std::string& k){const auto& v=field(h,k);size_t n=0;int64_t x=0;
 try{x=std::stoll(v,&n);}catch(const std::exception&){throw Refusal("checkpoint header integer "+k);}refuse_unless(n==v.size(),"checkpoint header integer "+k);return x;}
struct Bundle {std::vector<std::pair<std::string,std::vector<uint8_t>>> rows;std::string state,seal;uint64_t bytes=0;};
// Strict reader of gsq_bundle::Writer output: the four files only, seal -> index/state digests -> every row's digest
// and the whole-payload digest, file identity stable across the read.
static Bundle read_bundle(const fs::path& path) {
 try {
  namespace B=gsq_bundle;
  struct stat named{};B::need(::lstat(path.c_str(),&named)==0&&S_ISDIR(named.st_mode),"checkpoint directory");
  B::FD dir(::open(path.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));B::need(dir.n>=0,"open checkpoint directory");
  std::set<std::string> actual;for(auto& f:std::filesystem::directory_iterator(path))actual.insert(f.path().filename().string());
  B::need(actual==std::set<std::string>{"state.bundle","state-index.tsv","state.json","state-seal.txt"},"incomplete/unexpected checkpoint files");
  Bundle out;out.seal=B::read_small(dir.n,"state-seal.txt");
  std::istringstream seal(out.seal);std::string magic,total,payload_sha,index_sha,state_sha,extra;
  B::need(bool(std::getline(seal,magic))&&magic=="GSQ_STATE_SEAL_V1"&&bool(std::getline(seal,total))&&bool(std::getline(seal,payload_sha))&&
       bool(std::getline(seal,index_sha))&&bool(std::getline(seal,state_sha))&&!std::getline(seal,extra),"seal fields");
  out.bytes=B::number(total);B::need(out.bytes<=B::byte_cap&&B::hex(payload_sha)&&B::hex(index_sha)&&B::hex(state_sha),"seal bounds");
  const std::string index=B::read_small(dir.n,"state-index.tsv");B::need(B::digest(index)==index_sha,"index digest");
  out.state=B::read_small(dir.n,"state.json");B::need(B::digest(out.state)==state_sha,"state JSON digest");
  std::vector<gsq_bundle::Row> rows;std::istringstream stream(index);std::string line;std::set<std::string> names;uint64_t offset=0;
  B::need(bool(std::getline(stream,line))&&line=="GSQ_STATE_BUNDLE_V1","index magic");
  while(std::getline(stream,line)){std::istringstream r(line);std::string name,a,b,h,more;
   B::need(bool(std::getline(r,name,'\t'))&&bool(std::getline(r,a,'\t'))&&bool(std::getline(r,b,'\t'))&&bool(std::getline(r,h,'\t'))&&!std::getline(r,more,'\t'),"index row");
   B::name_ok(name);const uint64_t start=B::number(a),length=B::number(b);
   B::need(B::hex(h)&&names.insert(name).second&&rows.size()<B::row_cap&&start==offset&&length<=B::byte_cap-offset,"index inventory/range");
   rows.push_back({name,h,start,length});offset+=length;}
  B::need(!rows.empty()&&offset==out.bytes,"complete index");
  B::FD payload(openat(dir.n,"state.bundle",O_RDONLY|O_NOFOLLOW|O_CLOEXEC));B::need(payload.n>=0,"open checkpoint payload");
  const auto opened=B::stamp(payload.n);B::need(uint64_t(opened.st_size)==out.bytes,"payload extent");
  B::Hash whole;
  for(const auto& row:rows){std::vector<uint8_t> bytes(row.length);size_t done=0;
   while(done<bytes.size()){const ssize_t n=::pread(payload.n,bytes.data()+done,bytes.size()-done,off_t(row.offset+done));if(n<0&&errno==EINTR)continue;B::need(n>0,"read payload");done+=size_t(n);}
   B::need(B::digest(bytes.data(),bytes.size())==row.sha,"payload row digest");whole.add(bytes.data(),bytes.size());out.rows.emplace_back(row.name,std::move(bytes));}
  B::stable(dir.n,"state.bundle",payload.n,opened);B::need(whole.finish()==payload_sha,"payload digest");
  payload.close_checked();dir.close_checked();
  return out;
 }catch(const Refusal&){throw;}
 catch(const std::exception& ex){throw Refusal(std::string("checkpoint verify refused: ")+ex.what());}
}
static std::string json_list(const std::vector<Item>& items,bool saved) {
 std::ostringstream o;bool comma=false;o<<"[";
 for(const auto& it:items){if(it.saved!=saved)continue;o<<(comma?",":"")<<"{\"label\":"<<ownrt::quote(it.label)<<",\"source\":"<<ownrt::quote(it.source)<<",\"rule\":"<<ownrt::quote(it.rule);
  if(saved){o<<",\"blob\":"<<ownrt::quote(it.blob)<<",\"bytes\":"<<it.bytes<<",\"full\":"<<it.full<<",\"rows\":";if(it.rows>=0)o<<it.rows;else o<<"null";}
  o<<"}";comma=true;}
 return o.str()+"]";
}
static double seconds_since(std::chrono::steady_clock::time_point t){return std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();}
static Reply refusal_reply(Engine& e,const Request& r,const std::string& why) {
 save(e.a.output/("checkpoint-refused-"+std::to_string(r.sequence)+".json"),"{\"schema\":\"ownrt.session-checkpoint.refusal.v1\",\"op\":"+std::to_string(r.op)+
  ",\"sequence\":"+std::to_string(r.sequence)+",\"position\":"+std::to_string(r.position)+",\"engine_state_unchanged\":true,\"reason\":"+ownrt::quote(why)+"}");
 Reply reply{};reply.status=2;reply.error=r.op;reply.sequence=r.sequence;reply.rank=e.a.rank;return reply;
}
static int32_t clamp_bytes(uint64_t n){return int32_t(std::min<uint64_t>(n,uint64_t(std::numeric_limits<int32_t>::max())));}

// ------------------------------------------------------------------ 17 STAGE
// Caller (rank.hpp) has already required no pending candidate/async half/draft publication/V3 boundary and has run
// image.boundary() and the draft's flush_depth_probe(), exactly as the continuation command (op 16) does.
static Reply stage(Engine& e,mtp36::DraftRuntime* draft,const Request& r,const fs::path& metadata) {
 const auto started=std::chrono::steady_clock::now();
 try {
  supported(e);refuse_unless(r.speculative==0&&(r.fixture&~1)==0,"checkpoint stage flags");
  const auto target=read_request(metadata);refuse_unless(target.compat.empty(),"checkpoint stage: compat line is VERIFY only");
  e.drain();require(!e.poisoned&&!e.integer(0,"error"),"checkpoint stage over a poisoned engine or sticky device error (never saved)");
  const int64_t N=r.position;refuse_unless(N>=1&&N<e.p.g.context,"checkpoint stage position outside [1, context)");
  const int64_t device_position=int64_t(uint32_t(e.integer(0,"position")));
  refuse_unless(device_position==N,"checkpoint stage: device position "+std::to_string(device_position)+" != requested "+std::to_string(N));
  refuse_unless(r.token>=-1&&r.token<e.p.g.vocab,"checkpoint stage pending token bound");
  const int next_token=e.integer(0,"next_token");
  if(r.fixture&1)refuse_unless(r.token>=0&&next_token==r.token,"checkpoint stage: device next_token "+std::to_string(next_token)+" != pending "+std::to_string(r.token));
  int64_t D=-1;bool draft_disabled=false;int draft_extent=0;
  if(draft){const auto v=draft->checkpoint_view();
   refuse_unless(!v.pending&&!v.reverse_hidden&&v.queued_probe<0,"checkpoint stage: draft publication, reverse hidden handoff or depth probe pending");
   D=v.position;draft_disabled=v.disabled;draft_extent=v.context_extent;
   const auto raw=e.readback(0,v.buffers->at("position").id,4);int32_t dp=0;std::memcpy(&dp,raw.data(),4);
   require(int64_t(dp)==D,"checkpoint stage: draft device position differs from the draft host position");
   refuse_unless(D>=0&&D<=N,"checkpoint stage: draft position "+std::to_string(D)+" outside [0, N]");
  }
  const auto items=classify(e,draft,N,D);const auto coverage=coverage_text(items);
  std::vector<std::pair<std::string,std::string>> header{{"schema",schema},{"rank",std::to_string(e.a.rank)},{"position",std::to_string(N)},
   {"pending",std::to_string(r.token)},{"next_token_device",std::to_string(next_token)},{"prefix_tag",target.tag},
   {"history0",std::to_string(e.history0)},{"history1",std::to_string(e.history1)},{"bank_parity",std::to_string(e.bank_parity)},
   {"active_bank",std::to_string(e.active_bank)},{"spare_bank",std::to_string(e.spare_bank)},{"launch_extent",std::to_string(e.context_extent)},
   {"alternate_launch_extent",std::to_string(e.alternate_context_extent)},{"draft_position",std::to_string(D)},{"draft_disabled",draft_disabled?"1":"0"},
   {"draft_context_extent",std::to_string(draft_extent)},{"coverage_sha256",gsq_bundle::digest(coverage)}};
  for(auto& kv:identity(e,draft))header.push_back(std::move(kv));
  std::string header_text;for(const auto& [k,v]:header){require(k.find_first_of("\t\n")==std::string::npos&&v.find_first_of("\t\n")==std::string::npos,"checkpoint header text "+k);header_text+=k+'\t'+v+'\n';}
  // Directory: fresh, created here (a sealed existing directory would put gsq_bundle::Writer in repeat-verify mode).
  struct stat st{};refuse_unless(::lstat(target.dir.c_str(),&st)!=0&&errno==ENOENT,"checkpoint stage: directory already exists "+target.dir.string());
  refuse_unless(::lstat(target.dir.parent_path().c_str(),&st)==0&&S_ISDIR(st.st_mode),"checkpoint stage: parent directory missing "+target.dir.parent_path().string());
  refuse_unless(::mkdir(target.dir.c_str(),0700)==0,"checkpoint stage: mkdir failed errno="+std::to_string(errno));
  auto file=[&](auto&& step){try{step();}catch(const std::exception& ex){throw Refusal(std::string("checkpoint stage write failed (engine state unchanged): ")+ex.what());}};
  std::unique_ptr<gsq_bundle::Writer> bundle;file([&]{bundle=std::make_unique<gsq_bundle::Writer>(target.dir);});
  file([&]{bundle->append("checkpoint-header.bin",header_text.data(),header_text.size());bundle->append("checkpoint-coverage.bin",coverage.data(),coverage.size());});
  uint64_t total=0;size_t blobs=0;
  for(const auto& it:items){if(!it.saved)continue;
   std::vector<uint8_t> data;if(it.bytes)data=e.readback(0,it.id,it.bytes); // device readback: failures stay fatal
   file([&]{bundle->append(it.blob,data.data(),data.size());});total+=data.size();++blobs;}
  std::ostringstream hosts;bool comma=false;for(const auto& [k,v]:host_rules()){hosts<<(comma?",":"")<<"{\"field\":"<<ownrt::quote(k)<<",\"rule\":"<<ownrt::quote(v)<<"}";comma=true;}
  std::ostringstream state;state<<"{\"schema\":"<<ownrt::quote(schema)<<",\"header\":{";comma=false;
  for(const auto& [k,v]:header){state<<(comma?",":"")<<ownrt::quote(k)<<":"<<ownrt::quote(v);comma=true;}
  state<<"},\"saved_bytes\":"<<total<<",\"saved_blobs\":"<<blobs<<",\"saved\":"<<json_list(items,true)<<",\"skipped\":"<<json_list(items,false)<<",\"host_fields\":["<<hosts.str()<<"]}";
  file([&]{bundle->finish(state.str());});
  const double seconds=seconds_since(started);
  save(e.a.output/("checkpoint-stage-"+std::to_string(r.sequence)+".json"),"{\"schema\":\"ownrt.session-checkpoint.stage.v1\",\"directory\":"+ownrt::quote(target.dir.string())+
   ",\"position\":"+std::to_string(N)+",\"pending\":"+std::to_string(r.token)+",\"draft_position\":"+std::to_string(D)+",\"saved_bytes\":"+std::to_string(total)+
   ",\"saved_blobs\":"+std::to_string(blobs)+",\"coverage_items\":"+std::to_string(items.size())+",\"stage_seconds\":"+std::to_string(seconds)+"}");
  Reply reply{};reply.sequence=r.sequence;reply.rank=e.a.rank;reply.token=r.token;reply.bytes=clamp_bytes(total);reply.reserved[0]=int32_t(blobs);reply.busy_ms=seconds*1000;
  return reply;
 }catch(const Refusal& refusal){return refusal_reply(e,r,refusal.what());}
}

// ------------------------------------------------------------------ 18 VERIFY / 19 APPLY
struct Held {
 bool valid=false;fs::path dir;int64_t N=0,D=-1,pending=-1;bool draft_disabled=false;int64_t history0=0,history1=0;
 std::string coverage;std::vector<std::pair<std::string,std::vector<uint8_t>>> blobs;uint64_t bytes=0;double verify_seconds=0;
 void clear(){*this=Held{};}
};
static void fresh_reset_state(Engine& e,mtp36::DraftRuntime* draft,const std::string& op) {
 e.drain();require(!e.poisoned&&!e.integer(0,"error"),"checkpoint "+op+" over a poisoned engine or sticky device error");
 refuse_unless(e.integer(0,"position")==0&&e.bank_parity==0,"checkpoint "+op+": engine not at a fresh request reset (position 0, bank parity 0)");
 if(draft){const auto v=draft->checkpoint_view();refuse_unless(v.position==0&&!v.disabled&&!v.pending&&!v.reverse_hidden&&v.queued_probe<0,"checkpoint "+op+": draft not at a fresh request reset");}
}
static Reply verify(Engine& e,mtp36::DraftRuntime* draft,const Request& r,const fs::path& metadata,bool after_reset,Held& held) {
 const auto started=std::chrono::steady_clock::now();held.clear();
 try {
  supported(e);refuse_unless(after_reset,"checkpoint verify: must directly follow the request reset (op 11)");
  refuse_unless(r.speculative==0&&r.fixture==0,"checkpoint verify flags");
  fresh_reset_state(e,draft,"verify");
  const auto target=read_request(metadata);
  auto bundle=read_bundle(target.dir);
  refuse_unless(bundle.rows.size()>=2&&bundle.rows[0].first=="checkpoint-header.bin"&&bundle.rows[1].first=="checkpoint-coverage.bin","checkpoint verify: header/coverage rows");
  const auto header=parse_header(bundle.rows[0].second);
  refuse_unless(field(header,"schema")==schema,"checkpoint verify: schema "+field(header,"schema"));
  refuse_unless(integer_field(header,"rank")==e.a.rank,"checkpoint verify: saved by rank "+field(header,"rank"));
  refuse_unless(field(header,"prefix_tag")==target.tag,"checkpoint verify: prefix tag differs (checkpoint '"+field(header,"prefix_tag")+"', request '"+target.tag+"')");
  const auto live=identity(e,draft);std::set<std::string> keys;
  std::string foreign;
  for(const auto& [k,v]:live){keys.insert(k);const auto& saved=field(header,k);
   if(k=="identity.binary_sha256"&&saved!=v&&target.compat.count(saved)){foreign=saved;continue;}  // gated compatible binary
   refuse_unless(saved==v,"checkpoint verify: "+k+" differs (checkpoint "+saved+", engine "+v+")");}
  for(const auto& [k,v]:header)if(k.starts_with("identity."))refuse_unless(keys.count(k),"checkpoint verify: unknown identity field "+k);
  const int64_t N=integer_field(header,"position"),pending=integer_field(header,"pending"),D=integer_field(header,"draft_position");
  refuse_unless(N==r.position,"checkpoint verify: checkpoint position "+std::to_string(N)+" != requested "+std::to_string(r.position));
  refuse_unless(N>=1&&N<e.p.g.context,"checkpoint verify: position outside the context allocation");
  refuse_unless(r.token<0||pending==r.token,"checkpoint verify: pending token "+std::to_string(pending)+" != requested "+std::to_string(r.token));
  refuse_unless((D>=0)==(draft!=nullptr)&&D<=N,"checkpoint verify: draft placement/position");
  const auto items=classify(e,draft,N,D);const auto coverage=coverage_text(items);
  const std::string saved_coverage(bundle.rows[1].second.begin(),bundle.rows[1].second.end());
  refuse_unless(gsq_bundle::digest(saved_coverage)==field(header,"coverage_sha256"),"checkpoint verify: coverage digest");
  if(coverage!=saved_coverage){std::istringstream x(saved_coverage),y(coverage);std::string a,b;size_t line=0;
   for(;;){++line;bool ga=bool(std::getline(x,a)),gb=bool(std::getline(y,b));if(!ga||!gb||a!=b){throw Refusal("checkpoint verify: live coverage differs at line "+std::to_string(line)+" (checkpoint '"+(ga?a:std::string("<end>"))+"', engine '"+(gb?b:std::string("<end>"))+"')");}}}
  size_t k=2;uint64_t bytes=0;
  for(const auto& it:items){if(!it.saved)continue;
   refuse_unless(k<bundle.rows.size()&&bundle.rows[k].first==it.blob&&bundle.rows[k].second.size()==it.bytes,"checkpoint verify: blob "+it.blob+" missing or wrong extent");
   bytes+=it.bytes;held.blobs.push_back(std::move(bundle.rows[k]));++k;}
  refuse_unless(k==bundle.rows.size(),"checkpoint verify: extra rows in the bundle");
  held.valid=true;held.dir=target.dir;held.N=N;held.D=D;held.pending=pending;held.draft_disabled=integer_field(header,"draft_disabled")!=0;
  held.history0=integer_field(header,"history0");held.history1=integer_field(header,"history1");held.coverage=coverage;held.bytes=bytes;
  held.verify_seconds=seconds_since(started);
  save(e.a.output/("checkpoint-verify-"+std::to_string(r.sequence)+".json"),"{\"schema\":\"ownrt.session-checkpoint.verify.v1\",\"directory\":"+ownrt::quote(target.dir.string())+
   ",\"position\":"+std::to_string(N)+",\"pending\":"+std::to_string(pending)+",\"draft_position\":"+std::to_string(D)+",\"held_bytes\":"+std::to_string(bytes)+
   ",\"held_blobs\":"+std::to_string(held.blobs.size())+",\"bundle_bytes\":"+std::to_string(bundle.bytes)+",\"seal_sha256\":"+ownrt::quote(gsq_bundle::digest(bundle.seal))+
   ",\"identity_fields\":"+std::to_string(live.size())+",\"foreign_binary_sha256\":"+(foreign.empty()?std::string("null"):ownrt::quote(foreign))+",\"verify_seconds\":"+std::to_string(held.verify_seconds)+"}");
  Reply reply{};reply.sequence=r.sequence;reply.rank=e.a.rank;reply.token=int32_t(pending);reply.bytes=clamp_bytes(bytes);reply.reserved[0]=int32_t(held.blobs.size());reply.busy_ms=held.verify_seconds*1000;
  return reply;
 }catch(const Refusal& refusal){held.clear();return refusal_reply(e,r,refusal.what());}
}
static Reply apply(Engine& e,mtp36::DraftRuntime* draft,const Request& r,bool after_verify,Held& held) {
 const auto started=std::chrono::steady_clock::now();
 std::vector<Item> items;
 try {
  supported(e);refuse_unless(held.valid&&after_verify,"checkpoint apply: requires a verified checkpoint from the directly preceding op 18");
  refuse_unless(r.position==held.N&&r.speculative==0&&(r.fixture&~1)==0,"checkpoint apply: position/flags differ from the verified checkpoint");
  fresh_reset_state(e,draft,"apply");
  items=classify(e,draft,held.N,held.D);
  refuse_unless(coverage_text(items)==held.coverage,"checkpoint apply: live coverage changed since verify");
 }catch(const Refusal& refusal){held.clear();return refusal_reply(e,r,refusal.what());}
 // Every refusal precedes this line. From here on a failure is fatal: the engine may hold a partial restore.
 // The request reset zeroed every request allocation with its ID preserved, so sliced blobs land on zero tails.
 uint64_t uploaded=0;size_t k=0;
 for(const auto& it:items){if(!it.saved)continue;
  require(k<held.blobs.size(),"checkpoint apply blob count");const auto& [name,data]=held.blobs[k++];
  require(name==it.blob&&data.size()==it.bytes&&it.bytes<=it.full,"checkpoint apply blob extent "+it.blob);
#ifdef OWN_RT_HOST_ONLY
  // CPU-only negative control: omit one named blob; the full-state gate after the replayed steps MUST then fail.
  if(const char* skip=std::getenv("OWNRT_CKPT_NEGATIVE_SKIP");skip&&it.blob==skip)continue;
#endif
  if(!data.empty())e.upload(0,it.id,0,data.data(),data.size());uploaded+=data.size();}
 require(k==held.blobs.size(),"checkpoint apply blob count");
 e.history0=held.history0;e.history1=held.history1;
 e.admit_position(int(held.N));
 if(draft)draft->checkpoint_restore_host(int(held.D),held.draft_disabled);
 e.drain();
 require(int64_t(uint32_t(e.integer(0,"position")))==held.N&&!e.integer(0,"error"),"checkpoint apply: device position/error after upload");
 size_t checked=0;
 if(r.fixture&1){k=0;for(const auto& it:items){if(!it.saved)continue;const auto& data=held.blobs[k++].second;
  if(!data.empty())require(e.readback(0,it.id,data.size())==data,"checkpoint apply: readback differs for "+it.blob);++checked;}}
 const double seconds=seconds_since(started);
 save(e.a.output/("checkpoint-apply-"+std::to_string(r.sequence)+".json"),"{\"schema\":\"ownrt.session-checkpoint.apply.v1\",\"directory\":"+ownrt::quote(held.dir.string())+
  ",\"position\":"+std::to_string(held.N)+",\"pending\":"+std::to_string(held.pending)+",\"draft_position\":"+std::to_string(held.D)+",\"uploaded_bytes\":"+std::to_string(uploaded)+
  ",\"blobs\":"+std::to_string(held.blobs.size())+",\"readback_checked\":"+std::to_string(checked)+",\"launch_extent\":"+std::to_string(e.context_extent)+
  ",\"verify_seconds\":"+std::to_string(held.verify_seconds)+",\"apply_seconds\":"+std::to_string(seconds)+"}");
 Reply reply{};reply.sequence=r.sequence;reply.rank=e.a.rank;reply.token=int32_t(held.pending);reply.bytes=clamp_bytes(uploaded);reply.reserved[0]=int32_t(held.blobs.size());reply.reserved[1]=int32_t(checked);reply.busy_ms=seconds*1000;
 held.clear();
 return reply;
}
}} // namespace pipeline::session
