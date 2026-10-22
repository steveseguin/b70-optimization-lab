#pragma once
// packet184 two-card checkpoint, rank side (entry TU only; included by v5/native-src/rank.hpp):
// per-rank classification over request_state_inventory.hpp's enumeration, stage (save phase 1),
// verify and apply (restore). Format, manifest, strict reader, locks and the device-free tools are in
// checkpoint_format.hpp, which also builds into the standalone host tool (no SYCL, no device code).
#include "checkpoint_format.hpp"
namespace pipeline { namespace ckpt184 {
// ---------------------------------------------------------------- per-rank state classification
// The enumeration is request_state_inventory.hpp's: every plan buffer (state_dump), every spare bank
// ("alternate:" in state_dump), every live non-weight, non-slab, non-draft device allocation that the
// inventory lists as standalone_target_mutable (reserves relabelled "0:speculative-reserve:"), and
// the draft runtime's mutable allocations (DraftRuntime::dump_all_state). Every entry gets exactly
// one rule; an unknown persistent-looking name or an unknown standalone label refuses the save.
struct Item {
  std::string label,source,rule,blob;Allocation id=0;size_t full=0,bytes=0;int64_t rows=-1;
  bool saved()const{return rule=="saved-sliced-kv"||rule=="saved-whole"||rule=="saved-sliced-draft-kv";}
};
static bool control_name(const std::string& n){return n=="token"||n=="position"||n=="active"||n=="error"||n=="next_token";}
static void fail_closed_name(const std::string& n,const std::string& where) {
  for(const char* bad:{"history","state","keys","values","raw","pooled","metadata","token"})
    require(n.find(bad)==std::string::npos,"checkpoint completeness proof failed: unclassified persistent-looking "+where+" buffer "+n);
}
static std::string target_rule(const std::string& n,bool draft_owner) {
  if(kv_name(n))return "saved-sliced-kv";
  if(suffix(n,".gdn.history")||suffix(n,".gdn.state")||suffix(n,".ple.history")||n=="token_history"||control_name(n))return "saved-whole";
  if(n=="streams"&&draft_owner)return "saved-whole";   // boundary hidden stream: input of the next draft step
  if(suffix(n,".qsa.ids"))return "skip: qsa ids scratch, recomputed per token by qsa_select";
  if(n=="ple_metadata")return "skip: static GGUF-derived, re-put by the request reset; covered by model identity";
  fail_closed_name(n,"target");
  return "skip: plan intermediate fully rewritten every token step";
}
static std::string draft_rule(const std::string& n) {
  if(kv_name(n))return "saved-sliced-draft-kv";
  if(control_name(n))return "saved-whole";
  if(suffix(n,".qsa.ids"))return "skip: draft qsa ids scratch, recomputed per draft step by qsa_select";
  fail_closed_name(n,"draft");
  return "skip: draft intermediate fully rewritten every draft step";
}
static std::string standalone_rule(const Engine& e,Allocation id,const ownrt::Row& row) {
  const auto& l=row.label;
  if(l=="card0:speculative-private-image")return "skip: rollback private image, zeroed by SpeculativeImage::boundary() before the save and by the request reset; rewritten by begin() before any restore reads it";
  if(l=="card0:speculative-copy-table")return "skip: flat snapshot descriptor table, rewritten by every snapshot copy before its kernel reads it";
  if(e.head_auxiliary.count(id))return "skip: p105 head-suffix service scratch, written per head step before it is read";
  if(e.probe_auxiliary.count(id))return "skip: p149 probe exchange discard scratch, written only by the probe exchange (probe=off: never)";
  if(l=="card0:mixture-one")return "skip: constant 1.0f re-put by the request reset";
  static const std::set<std::string> scratch{"card0:parallel-controls:0","card0:attention-scores:0","card0:attention-probabilities:0",
    "card0:layer-snapshots:0","card0:prepared-fp32-input","card0:gemv-workspace","card0:compact-routes","card0:ordered-mixture","card0:operator-scratch"};
  if(scratch.count(l)){require(row.lifetime==ownrt::Lifetime::transaction,"checkpoint scratch lifetime "+l);return "skip: transaction scratch written before read within each launch";}
  require(false,"checkpoint completeness proof failed: unclassified standalone allocation "+l);return {};
}
// dim0 is the position axis of every QSA KV-family buffer (packet179 rule; pooled rows floor(N/4)).
static size_t slice_bytes(const flash::Geometry& g,const std::string& name,size_t full,int64_t rows_in,int64_t* rows_out) {
  if(suffix(name,".qsa.keys")||suffix(name,".qsa.values")) {
    const size_t row=2ull*g.kvh*g.ad;require(full==row*size_t(g.context),"checkpoint qsa kv extent "+name);*rows_out=rows_in;return size_t(rows_in)*row;
  }
  if(suffix(name,".qsa.raw")) {
    const size_t row=2ull*g.id;require(full==row*size_t(g.context),"checkpoint qsa raw extent "+name);*rows_out=rows_in;return size_t(rows_in)*row;
  }
  if(suffix(name,".qsa.pooled")) {
    const size_t row=2ull*g.id;require(full==row*size_t((g.context+3)/4),"checkpoint qsa pooled extent "+name);*rows_out=rows_in/4;return size_t(rows_in/4)*row;
  }
  require(false,"checkpoint slice of a non-KV buffer "+name);return 0;
}
static std::vector<Item> classify(Engine& e,mtp36::DraftRuntime* draft,int64_t N,int64_t draft_rows) {
  std::vector<Item> out;const auto& g=e.p.g;const bool draft_owner=e.a.mtp&&e.a.rank==e.a.draft_rank;
  std::set<Allocation> represented;
  for(const auto& [name,s]:e.buffers[0]) {
    Item it;it.label=name;it.source="plan";it.rule=target_rule(name,draft_owner);it.id=s.id;it.full=s.n*flash::scalar_bytes(s.type);
    represented.insert(s.id);
    if(it.saved()){it.blob=name;it.bytes=it.rule=="saved-sliced-kv"?slice_bytes(g,name,it.full,N,&it.rows):it.full;}
    out.push_back(std::move(it));
  }
  for(const auto& [name,id]:e.state_spares) {
    Item it;it.label="alternate:"+name;it.source="spare";it.rule="saved-whole";it.id=id;it.full=it.bytes=e.dev(0).arena.row(id).bytes;
    it.blob="spare."+name;represented.insert(id);out.push_back(std::move(it));
  }
  std::map<Allocation,std::string> reserves;for(const auto& [name,id]:e.state_reserves)reserves[id]=name;
  for(const auto& [id,owner]:e.allocations) {
    const auto& row=e.dev(owner.first).arena.row(id);
    if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab||represented.count(id)||row.label.find(":draft:")!=std::string::npos)continue;
    if(e.immutable_snapshot_tables.contains(id))continue;  // the inventory excludes them too: immutable load-time geometry
    Item it;it.id=id;it.full=row.bytes;
    if(auto r=reserves.find(id);r!=reserves.end()){it.label="0:speculative-reserve:"+r->second;it.source="reserve";it.rule="saved-whole";it.blob="reserve."+r->second;it.bytes=row.bytes;}
    else {it.label=row.label;it.source="standalone";it.rule=standalone_rule(e,id,row);}
    out.push_back(std::move(it));
  }
  if(draft) {
    const auto v=draft->checkpoint_view();std::set<Allocation> buffer_ids;
    for(const auto& [name,s]:*v.buffers) {
      Item it;it.label=e.dev(0).arena.row(s.id).label;it.source="draft";it.rule=draft_rule(name);it.id=s.id;it.full=s.n*flash::scalar_bytes(s.type);
      require(v.mutable_ids.count(s.id),"draft buffer outside the draft mutable set "+name);buffer_ids.insert(s.id);
      if(it.saved()){it.blob="draft."+name;it.bytes=it.rule=="saved-sliced-draft-kv"?slice_bytes(g,name,it.full,draft_rows,&it.rows):it.full;}
      out.push_back(std::move(it));
    }
    for(auto id:v.mutable_ids) {
      if(buffer_ids.count(id))continue;const auto& row=e.dev(0).arena.row(id);
      Item it;it.label=row.label;it.source="draft-extra";it.id=id;it.full=row.bytes;
      require(row.category!=Category::weights&&row.category!=Category::kv,"draft extra allocation category "+row.label);
      it.rule="skip: draft scratch (scores, probabilities, controls, head workspace) written before read every draft step";
      out.push_back(std::move(it));
    }
  }
  std::set<std::string> labels,blobs;
  for(const auto& it:out) {
    require(labels.insert(it.label).second,"checkpoint coverage label not unique: "+it.label);
    if(it.saved()){require(valid_id(it.blob)&&it.blob!="stage",std::string("checkpoint blob name ")+it.blob);require(blobs.insert(it.blob).second,"checkpoint blob name not unique: "+it.blob);}
  }
  return out;
}
// Host fields of request_state_inventory.hpp (plus the draft runtime's host state) and their rules.
static const std::vector<std::pair<std::string,std::string>>& host_rules() {
  static const std::vector<std::pair<std::string,std::string>> r{
    {"lookup_ids_sha256","skip: recomputed by prepare_token from (token, history) before every lookup; cleared by the request reset"},
    {"selected","skip: layer-streaming expert selection; the resident engine never reads it; cleared by the request reset"},
    {"loaded_layer","skip: layer-streaming residency; the resident engine never reads it; cleared by the request reset"},
    {"fp32_cache","skip: cache-validity metadata, invalidated by every bank swap and by the request reset"},
    {"bank_parity","recorded: restore lands after the request reset (parity 0); logical bank roles are restored by name"},
    {"launch_extent","recorded: re-derived by admit_position(N) at apply and before every half"},
    {"alternate_launch_extent","recorded: re-derived by admit_position before every half that uses the bank"},
    {"logical_event","skip: ordering-relative event counter, reset to 0 in both arms"},
    {"history0","saved: manifest token_state.token_history (rank 0 host mirror, derived from tokens.bin)"},
    {"history1","saved: manifest token_state.token_history (rank 0 host mirror, derived from tokens.bin)"},
    {"poisoned","checked: must be false at save"},
    {"draft.position","saved: manifest draft.position (draft rank)"},
    {"draft.disabled","saved: manifest draft.disabled (draft rank)"},
    {"draft.context_extent","recorded: re-derived by DraftRuntime::admit_position before every draft step"}};
  return r;
}
static std::vector<int> layers_of(const Engine& e,const std::string& sfx) {
  std::vector<int> out;
  for(const auto& [name,s]:e.buffers[0])if(suffix(name,sfx)){require(name.compare(0,4,"blk.")==0,"checkpoint layer buffer name");out.push_back(std::stoi(name.substr(4)));}
  std::sort(out.begin(),out.end());return out;
}
static std::string ints(const std::vector<int>& v){return join(std::vector<int64_t>(v.begin(),v.end()));}

// ---------------------------------------------------------------- rank stage (save, phase 1)
// Writes ROOT/ID/rankR/<blob>.bin and ROOT/ID/rankR/stage.json. The coordinator holds the
// exclusive lock and created ROOT/ID, ROOT/ID/rankR (empty) and ROOT/ID/tokens.bin.
static std::string identity_facts(const Engine& e) {
  std::ostringstream o;std::string identity_sha;std::vector<std::string> stat_rows;
  if(!e.a.auth.empty()) {
    auto bytes=read_file(e.a.auth);identity_sha=hash(bytes);
    std::istringstream lines{std::string(bytes.begin(),bytes.end())};std::string line;
    while(std::getline(lines,line)) {
      if(line.empty())continue;std::istringstream r(line);std::string name;uint64_t b,dv,ino,mt,ct;
      require(bool(r>>name>>b>>dv>>ino>>mt>>ct),"identity row parse");
      std::ostringstream j;j<<"{\"name\":"<<ownrt::quote(name)<<",\"size\":"<<b<<",\"dev\":"<<dv<<",\"ino\":"<<ino<<",\"mtime\":"<<mt<<",\"ctime\":"<<ct<<"}";
      stat_rows.push_back(j.str());
    }
    require(stat_rows.size()==3,"three admitted shards required");
  }
  const bool draft_owner=e.a.mtp&&e.a.rank==e.a.draft_rank;
  std::string draft_manifest_sha;if(draft_owner&&!e.a.mini)draft_manifest_sha=hash(read_file(e.a.draft_manifest));
  o<<"\"identity_tsv_sha256\":"<<ownrt::quote(identity_sha)<<",\"shard_stat_rows\":[";
  for(size_t i=0;i<stat_rows.size();++i)o<<(i?",":"")<<stat_rows[i];
  o<<"],\"draft_manifest_sha256\":"<<ownrt::quote(draft_manifest_sha)<<",\"binary_sha256\":"<<ownrt::quote(self_sha256())
   <<",\"selection_sha256\":"<<ownrt::quote(e.sealed_selection.observed_sha256)<<",\"arithmetic\":"<<ownrt::quote(arithmetic::version)
   <<",\"mini\":"<<(e.a.mini?"true":"false")<<",\"draft_rank\":"<<e.a.draft_rank<<",\"target_split\":"<<e.a.target_split<<",\"mtp\":"<<(e.a.mtp?"true":"false");
  const auto& g=e.p.g;
  o<<",\"geometry\":{\"h\":"<<g.h<<",\"kvh\":"<<g.kvh<<",\"ad\":"<<g.ad<<",\"ih\":"<<g.ih<<",\"id\":"<<g.id<<",\"qh\":"<<g.qh
   <<",\"kh\":"<<g.kh<<",\"vh\":"<<g.vh<<",\"d\":"<<g.d<<",\"context\":"<<g.context<<",\"vocab\":"<<g.vocab<<",\"eos\":"<<g.eos<<"}";
  return o.str();
}
struct StageResult { uint64_t bytes=0;size_t blobs=0;double seconds=0;std::string coverage,host_fields; };
static StageResult stage(Engine& e,mtp36::DraftRuntime* draft,const fs::path& request_file) {
  const std::string op="save";const auto started=std::chrono::steady_clock::now();
  const auto req=read_request(request_file,op);
  const fs::path dir=need(req,"dir",op);const int64_t N=need_int(req,"position",op),pending=need_int(req,"pending",op);
  const auto [root,id]=split_dir(dir);
  if(!valid_id(id))refuse(op,"id","invalid checkpoint id "+id);
  lock_held_proof(root,id,op);
  const auto& g=e.p.g;const int rank=e.a.rank;const bool draft_owner=e.a.mtp&&rank==e.a.draft_rank;
  require(rank==0||rank==1,"checkpoint stage rank");
  if(e.a.mtp)require(e.a.draft_rank==1&&rank==1,"packet184 checkpoints support the record placement only (MTP draft on rank 1)");
  if(N<1||N>=g.context)refuse(op,"token state","position outside the context allocation");
  if(pending<0||pending>=g.vocab)refuse(op,"token state","pending token outside vocabulary");
  e.drain();
  require(!e.poisoned,"checkpoint save of a poisoned engine refused");
  require(!e.integer(0,"error"),"checkpoint save with sticky device error refused");
  require(int64_t(uint32_t(e.integer(0,"position")))==N,"checkpoint save position mismatch on rank "+std::to_string(rank));
  if(draft_owner)require(int64_t(e.integer(0,"next_token"))==pending,"checkpoint save: rank-1 next_token differs from the coordinator's pending token");
  const fs::path rdir=dir/("rank"+std::to_string(rank));
  require(fs::is_directory(fs::symlink_status(rdir))&&fs::is_empty(rdir),"checkpoint stage directory must exist and be empty: "+rdir.string());
  const auto token_bytes=read_file(dir/"tokens.bin");require(token_bytes.size()==size_t(N)*4,"checkpoint tokens.bin extent");
  std::vector<int> tokens(static_cast<size_t>(N),0);for(int64_t i=0;i<N;++i){int32_t x;std::memcpy(&x,token_bytes.data()+4*i,4);require(x>=0&&x<g.vocab,"checkpoint tokens.bin vocabulary");tokens[size_t(i)]=x;}
  const auto [h0,h1]=history_of(tokens,g.eos);
  if(rank==0)require(e.history0==h0&&e.history1==h1,"checkpoint save: rank-0 host token-history mirror disagrees with tokens.bin");
  int64_t draft_rows=-1;bool draft_disabled=false;int draft_extent=0;
  if(draft) {
    const auto v=draft->checkpoint_view();require(!v.pending,"checkpoint save with a pending draft publication");
    draft_rows=v.position;draft_disabled=v.disabled;draft_extent=v.context_extent;
    std::vector<uint8_t> dpos=e.readback(0,v.buffers->at("position").id,4);int32_t dp=0;std::memcpy(&dp,dpos.data(),4);
    require(int64_t(dp)==draft_rows,"checkpoint save: draft device position differs from the draft host position");
    require(draft_rows==N-1||(draft_disabled&&draft_rows<N-1),"checkpoint save: draft position "+std::to_string(draft_rows)+" is not N-1 for an enabled draft");
  }
  auto items=classify(e,draft,N,draft_rows);
  std::ostringstream blobs,skips,coverage;uint64_t total=0;size_t count=0;bool cb=false,cs=false,cc=false;
  for(const auto& it:items) {
    coverage<<(cc?",":"")<<"{\"label\":"<<ownrt::quote(it.label)<<",\"source\":"<<ownrt::quote(it.source)<<",\"rule\":"<<ownrt::quote(it.rule)<<"}";cc=true;
    if(!it.saved()){skips<<(cs?",":"")<<"{\"label\":"<<ownrt::quote(it.label)<<",\"source\":"<<ownrt::quote(it.source)<<",\"rule\":"<<ownrt::quote(it.rule)<<"}";cs=true;continue;}
    auto data=e.readback(0,it.id,it.bytes);
    if(it.blob=="token_history"){require(data.size()==16,"token_history extent");int64_t x[2];std::memcpy(x,data.data(),16);require(x[0]==h0&&x[1]==h1,"checkpoint save: device token_history disagrees with tokens.bin");}
    write_file(rdir/(it.blob+".bin"),data.data(),data.size());
    blobs<<(cb?",":"")<<"{\"name\":"<<ownrt::quote(it.blob)<<",\"source\":"<<ownrt::quote(it.source)<<",\"bytes\":"<<data.size()<<",\"sha256\":"<<ownrt::quote(hash(data))<<",\"slice\":";
    if(it.rows>=0)blobs<<"[0,"<<it.rows<<"]";else blobs<<"null";blobs<<"}";cb=true;
    total+=data.size();++count;
  }
  std::ostringstream hosts;bool ch=false;for(const auto& [field,rule]:host_rules()){hosts<<(ch?",":"")<<"{\"field\":"<<ownrt::quote(field)<<",\"rule\":"<<ownrt::quote(rule)<<"}";ch=true;}
  const auto qsa=layers_of(e,".qsa.keys"),gdn=layers_of(e,".gdn.state");
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  std::ostringstream o;o.precision(17);
  o<<"{\"schema\":\"packet184.rank-stage.v1\",\"rank\":"<<rank<<","<<identity_facts(e)<<",\"position\":"<<N<<",\"pending\":"<<pending
   <<",\"tokens_sha256\":"<<ownrt::quote(hash(token_bytes))
   <<",\"rank_state\":{\"rank\":"<<rank<<",\"directory\":"<<ownrt::quote("rank"+std::to_string(rank))<<",\"qsa_layers\":["<<ints(qsa)<<"],\"gdn_layers\":["<<ints(gdn)<<"]"
   <<",\"host_state\":{\"history0\":"<<e.history0<<",\"history1\":"<<e.history1<<",\"bank_parity\":"<<e.bank_parity<<",\"active_bank\":"<<e.active_bank<<",\"spare_bank\":"<<e.spare_bank
   <<",\"miss_banks\":"<<(e.miss_banks()?"true":"false")<<",\"launch_extent\":"<<e.context_extent<<",\"alternate_launch_extent\":"<<e.alternate_context_extent
   <<",\"draft_owner\":"<<(draft?"true":"false")<<",\"draft_position\":"<<draft_rows<<",\"draft_disabled\":"<<(draft_disabled?"true":"false")<<",\"draft_context_extent\":"<<draft_extent<<"}"
   <<",\"blobs\":["<<blobs.str()<<"],\"skipped\":["<<skips.str()<<"]}"
   <<",\"coverage\":["<<coverage.str()<<"],\"host_fields\":["<<hosts.str()<<"],\"stage_seconds\":"<<seconds<<",\"stage_bytes\":"<<total<<"}\n";
  write_text(rdir/"stage.json",o.str());fsync_dir(rdir);
  return {total,count,seconds,"["+coverage.str()+"]","["+hosts.str()+"]"};
}

// ---------------------------------------------------------------- restore (rank side): verify, then apply
struct PendingRestore {
  bool held=false;std::string checkpoint_id,manifest_sha256,operation;int64_t position=0,draft_position=-1;bool draft_disabled=false;
  int64_t history0=0,history1=0;std::vector<std::pair<std::string,std::vector<uint8_t>>> blobs;uint64_t bytes_read=0;double verify_seconds=0;
};
static std::vector<int> read_tokens_file(const fs::path& path,int64_t vocab,const std::string& op) {
  std::ifstream f(path);std::vector<int> v;int x;while(f>>x){if(x<0||x>=vocab)refuse(op,"request","--input token outside vocabulary");v.push_back(x);}
  if(!f.eof()||v.empty())refuse(op,"request","malformed --input token file");return v;
}
static std::string verify_restore(Engine& e,mtp36::DraftRuntime* draft,const fs::path& request_file,PendingRestore& out) {
  const std::string op="restore";const auto started=std::chrono::steady_clock::now();
  require(!out.held,"a verified restore is already pending");
  const auto req=read_request(request_file,op);
  const fs::path dir=need(req,"dir",op);const auto [root,id]=split_dir(dir);
  if(!valid_id(id))refuse(op,"id","invalid checkpoint id "+id);
  const fs::path tokenizer_path=need(req,"tokenizer_identity",op);const int64_t max_new=need_int(req,"max_new",op);
  const auto tokenizer=tokenizer_identity(tokenizer_path,op);
  lock_held_proof(root,id,op);
  const int rank=e.a.rank;require(rank==0||rank==1,"restore rank");
  auto loaded=load(root/id,id,Verify::full,op,rank,true);const auto& m=loaded.m;
  if(self_sha256()!=m.binary_sha)refuse(op,"engine identity","binary_sha256 differs from /proc/self/exe");
  const auto& g=e.p.g;
  auto want=[&](const char* key,int64_t have,int64_t value){if(have!=value)refuse(op,"geometry",std::string(key)+" checkpoint="+std::to_string(have)+" engine="+std::to_string(value));};
  want("h",m.h,g.h);want("kvh",m.kvh,g.kvh);want("ad",m.ad,g.ad);want("ih",m.ih,g.ih);want("id",m.g_id,g.id);want("kh",m.kh,g.kh);want("vh",m.vh,g.vh);
  want("d",m.d,g.d);want("qh",m.qh,g.qh);want("context",m.context,g.context);want("vocab",m.vocab,g.vocab);want("eos",m.eos,g.eos);
  want("draft_rank",m.draft_rank,e.a.draft_rank);want("target_split",m.target_split,e.a.target_split);
  if(m.mini!=e.a.mini)refuse(op,"engine identity","mini/full-model mismatch");
  if(m.selection_sha!=e.sealed_selection.observed_sha256)refuse(op,"engine identity","selection sha256 differs");
  if(m.arithmetic!=arithmetic::version)refuse(op,"engine identity","arithmetic differs");
  const auto& rs=m.rank_states.at(size_t(rank));
  if(ints(layers_of(e,".qsa.keys"))!=join(rs.qsa_layers))refuse(op,"geometry","rank "+std::to_string(rank)+" qsa layer set differs");
  if(ints(layers_of(e,".gdn.state"))!=join(rs.gdn_layers))refuse(op,"geometry","rank "+std::to_string(rank)+" gdn layer set differs");
  if(e.a.auth.empty()){if(!m.identity_sha.empty())refuse(op,"model identity","full-model checkpoint on a mini engine");}
  else if(hash(read_file(e.a.auth))!=m.identity_sha)refuse(op,"model identity","identity.tsv sha256/stat pins differ");
  const bool draft_owner=e.a.mtp&&rank==e.a.draft_rank;
  if(draft_owner!=rs.draft_owner||(draft!=nullptr)!=draft_owner)refuse(op,"engine identity","draft placement differs");
  if(draft_owner&&!e.a.mini&&hash(read_file(e.a.draft_manifest))!=m.draft_manifest_sha)refuse(op,"model identity","draft manifest sha256 differs");
  if(tokenizer.file_sha256!=m.tokenizer.file_sha256||tokenizer.gguf_header_sha256!=m.tokenizer.gguf_header_sha256||
     tokenizer.tokenizer_source_sha256!=m.tokenizer.tokenizer_source_sha256||tokenizer.vocab_bin_sha256!=m.tokenizer.vocab_bin_sha256)
    refuse(op,"tokenizer identity","--tokenizer-identity "+tokenizer.file_sha256+" differs from the identity recorded at save "+m.tokenizer.file_sha256);
  const auto input=read_tokens_file(need(req,"input",op),g.vocab,op);
  const auto [operation,appended]=classify_input(m,loaded.tokens,input,max_new,e.a.mini,op);(void)appended;
  // Completeness proof re-derived against the live engine before any upload.
  const auto items=classify(e,draft,m.position,draft_owner?m.draft_position:-1);
  std::map<std::string,const Blob*> by_name;for(const auto& b:rs.blobs)by_name[b.name]=&b;
  std::map<std::string,const Skip*> skip_by;for(const auto& k:rs.skipped)skip_by[k.label]=&k;
  size_t saved=0,skipped=0;
  for(const auto& it:items) {
    if(it.saved()) {
      auto b=by_name.find(it.blob);if(b==by_name.end())refuse(op,"completeness","rank "+std::to_string(rank)+" missing blob "+it.blob);
      if(b->second->bytes!=it.bytes||b->second->source!=it.source||b->second->rows!=it.rows)refuse(op,"geometry","rank "+std::to_string(rank)+" blob extent/source "+it.blob);
      ++saved;
    } else {
      auto k=skip_by.find(it.label);if(k==skip_by.end()||k->second->rule!=it.rule||k->second->source!=it.source)refuse(op,"completeness","rank "+std::to_string(rank)+" skip classification changed for "+it.label);
      ++skipped;
    }
  }
  if(saved!=rs.blobs.size())refuse(op,"completeness","rank "+std::to_string(rank)+" blob count differs from the live saved set");
  if(skipped!=rs.skipped.size())refuse(op,"completeness","rank "+std::to_string(rank)+" skipped-buffer count differs from the live classification");
  out.held=true;out.checkpoint_id=id;out.manifest_sha256=m.sha256;out.operation=operation;out.position=m.position;
  out.draft_position=m.draft_position;out.draft_disabled=m.draft_disabled;out.history0=m.history0;out.history1=m.history1;
  out.blobs=std::move(loaded.blobs[size_t(rank)]);out.bytes_read=loaded.bytes_read;
  out.verify_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  // The controller prompt (history + pending [+ delta]) is returned to the coordinator.
  const auto prompt=controller_prompt(loaded.tokens,m,input,operation);
  std::ostringstream o;o.precision(17);
  o<<"{\"schema\":\"packet184.rank-restore-verify.v1\",\"rank\":"<<rank<<",\"checkpoint_id\":"<<ownrt::quote(id)<<",\"manifest_sha256\":"<<ownrt::quote(m.sha256)
   <<",\"operation\":"<<ownrt::quote(operation)<<",\"position\":"<<m.position<<",\"prompt_length\":"<<m.prompt_length<<",\"pending_token\":"<<m.next_token
   <<",\"pending_is_stop\":"<<(stop_token(m.next_token,m.eos,e.a.mini)?"true":"false")<<",\"input_length\":"<<input.size()<<",\"controller_prompt_length\":"<<prompt.size()
   <<",\"controller_prompt_sha256\":"<<ownrt::quote([&]{std::vector<uint8_t> b(prompt.size()*4);std::memcpy(b.data(),prompt.data(),b.size());return hash(b);}())
   <<",\"blobs_verified\":"<<loaded.blobs_verified<<",\"bytes_read\":"<<loaded.bytes_read<<",\"verify_seconds\":"<<out.verify_seconds<<"}";
  return o.str();
}
static std::string apply_restore(Engine& e,mtp36::DraftRuntime* draft,PendingRestore& r) {
  require(r.held,"restore apply without a verified restore");
  const auto started=std::chrono::steady_clock::now();
  e.drain();require(!e.poisoned&&!e.integer(0,"error"),"restore apply over a failed engine");
  const auto items=classify(e,draft,r.position,draft?r.draft_position:-1);
  std::map<std::string,const Item*> by_blob;for(const auto& it:items)if(it.saved())by_blob[it.blob]=&it;
  require(by_blob.size()==r.blobs.size(),"restore apply blob set");
  // Every refusal precedes this line. The restore runs after the request reset: every request
  // allocation is zeroed with its ID preserved, so sliced blobs land on zeroed tails byte-exactly.
  uint64_t uploaded=0;
  for(const auto& [name,data]:r.blobs) {
    auto it=by_blob.find(name);require(it!=by_blob.end()&&data.size()==it->second->bytes&&data.size()<=it->second->full,"restore apply extent "+name);
    e.upload(0,it->second->id,0,data.data(),data.size());uploaded+=data.size();
  }
  if(e.a.rank==0){e.history0=r.history0;e.history1=r.history1;}
  e.admit_position(int(r.position));
  if(draft)draft->checkpoint_restore_host(int(r.draft_position),r.draft_disabled);
  e.drain();
  require(int64_t(uint32_t(e.integer(0,"position")))==r.position,"restore apply: device position after upload");
  const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  std::ostringstream o;o.precision(17);
  o<<"{\"schema\":\"packet184.rank-restore-apply.v1\",\"rank\":"<<e.a.rank<<",\"checkpoint_id\":"<<ownrt::quote(r.checkpoint_id)<<",\"operation\":"<<ownrt::quote(r.operation)
   <<",\"position\":"<<r.position<<",\"uploaded_bytes\":"<<uploaded<<",\"blobs\":"<<r.blobs.size()<<",\"verify_seconds\":"<<r.verify_seconds<<",\"apply_seconds\":"<<seconds<<"}";
  r.blobs.clear();r.held=false;
  return o.str();
}


}} // namespace pipeline::ckpt184
