#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "gsq-rco-iq3s/state-bundle/bundle.hpp"
#include "stage2/packet194-expert-diet-engine/mtp_kernels.hpp"
#include "stage2/packet194-expert-diet-engine/p59_draft.hpp"
#include "stage2/packet194-expert-diet-engine/p59_hc.hpp"
#include "stage2/packet194-expert-diet-engine/p56_prefix.hpp"
#include "stage2/packet194-expert-diet-engine/p83_head.hpp"
#include <cfenv>
#include <poll.h>
// Included after Engine. All mutable allocations below are private to the draft.
// The target Engine supplies one lifetime owner, uploads and immutable weights.
namespace pipeline {template<class Owner> class StageCheckpointFor;}
namespace mtp36 {
struct Tensor {std::string name,file,dtype,sha;uint64_t offset,bytes,filebytes,dev,ino,mtime,ctime;unsigned rows,cols;};
struct Store {
 fs::path root;std::map<std::string,Tensor> tensors;std::map<std::string,std::string> reads;
 Store(const fs::path& manifest,const fs::path& model):root(model){
  std::ifstream f(manifest);require(bool(f),"draft manifest missing");Tensor t;
  while(f>>t.name>>t.file>>t.offset>>t.bytes>>t.dtype>>t.rows>>t.cols>>t.sha>>t.filebytes>>t.dev>>t.ino>>t.mtime>>t.ctime){
   require(t.name.starts_with("mtp.")&&fs::path(t.file).filename()==t.file&&t.bytes&&t.bytes<=64*1024*1024&&t.offset<=t.filebytes&&t.bytes<=t.filebytes-t.offset,"draft tensor manifest bounds");
   require(tensors.emplace(t.name,t).second,"duplicate draft tensor");
  }require(f.eof()&&tensors.size()==3101,"missing official draft tensors");
 }
 std::vector<uint8_t> read(const std::string& name){const auto& t=tensors.at(name);auto file=root/t.file;struct stat st{};
  require(!stat(file.c_str(),&st)&&uint64_t(st.st_size)==t.filebytes&&uint64_t(st.st_dev)==t.dev&&uint64_t(st.st_ino)==t.ino&&uint64_t(st.st_mtim.tv_sec)*1000000000+st.st_mtim.tv_nsec==t.mtime&&uint64_t(st.st_ctim.tv_sec)*1000000000+st.st_ctim.tv_nsec==t.ctime,"official draft file changed since publisher hash authentication");
  std::ifstream f(file,std::ios::binary);f.seekg(t.offset);std::vector<uint8_t> b(t.bytes);f.read(reinterpret_cast<char*>(b.data()),b.size());require(bool(f)&&hash(b)==t.sha,"official draft tensor SHA256 mismatch");reads[name]=t.sha;return b;
 }
};
inline float fp8(uint8_t b){unsigned e=(b>>3)&15,m=b&7;if(e==15&&m==7)throw std::runtime_error("nonfinite official draft FP8");float x=e?float(8+m)*std::ldexp(1.f,int(e)-10):float(m)*std::ldexp(1.f,-9);return b&128?-x:x;}
inline std::vector<uint8_t> requant(const std::vector<uint8_t>& w,const std::vector<uint8_t>& sc,unsigned rows,unsigned cols){
 require(w.size()==size_t(rows)*cols&&cols%16==0&&rows%128==0&&cols%128==0&&sc.size()==size_t(rows/128)*(cols/128)*2,"draft FP8/scales shape");
 require(std::fegetround()==FE_TONEAREST,"draft quantizer requires nearest-even");std::array<float,256> table{};for(unsigned k=0;k<256;++k)if((k&127)!=127)table[k]=fp8(uint8_t(k));
 size_t rb=cols+cols/16*4;std::vector<uint8_t> out(size_t(rows)*rb);
 for(unsigned r=0;r<rows;++r)for(unsigned g=0;g<cols/16;++g){float values[16],maximum=0;size_t si=((r/128)*(cols/128)+g/8)*2;uint16_t bits=uint16_t(sc[si])|(uint16_t(sc[si+1])<<8);float scale=iq3::bits_float(uint32_t(bits)<<16);require(std::isfinite(scale)&&scale>=0,"draft FP8 scale");
  for(unsigned k=0;k<16;++k){auto code=w[size_t(r)*cols+g*16+k];require((code&127)!=127,"nonfinite official draft FP8");values[k]=table[code]*scale;maximum=std::max(maximum,std::abs(values[k]));}
  float s=maximum==0?1.f:maximum/127.f;std::memcpy(out.data()+size_t(r)*rb+cols+g*4,&s,4);
  for(unsigned k=0;k<16;++k){int code=int(std::nearbyint(values[k]/s));code=std::clamp(code,-127,127);out[size_t(r)*rb+g*16+k]=uint8_t(int8_t(code));}
 }return out;
}
inline std::vector<uint8_t> fp8_pack(const std::vector<uint8_t>& w,const std::vector<uint8_t>& sc,unsigned rows,unsigned cols){
 // Row = cols E4M3 codes, then cols/128 F32 scales (exact widening of the checkpoint BF16 block scale).
 require(w.size()==size_t(rows)*cols&&rows%128==0&&cols%128==0&&sc.size()==size_t(rows/128)*(cols/128)*2,"draft FP8/scales shape");
 size_t rb=cols+cols/128*4;std::vector<uint8_t> out(size_t(rows)*rb);
 for(unsigned r=0;r<rows;++r){std::memcpy(out.data()+size_t(r)*rb,w.data()+size_t(r)*cols,cols);
  for(unsigned k=0;k<cols;++k)require((w[size_t(r)*cols+k]&127)!=127,"nonfinite official draft FP8");
  for(unsigned b=0;b<cols/128;++b){size_t si=((r/128)*(cols/128)+b)*2;uint16_t bits=uint16_t(sc[si])|(uint16_t(sc[si+1])<<8);uint32_t f=uint32_t(bits)<<16;float scale=iq3::bits_float(f);require(std::isfinite(scale)&&scale>=0,"draft FP8 scale");std::memcpy(out.data()+size_t(r)*rb+cols+b*4,&f,4);}
 }return out;
}
inline std::string official(const std::string& n){
 if(n.starts_with("mtp."))return n;
 for(auto [from,to]:std::vector<std::pair<std::string,std::string>>{{"blk.0.hc_attn_","mtp.layers.0.attn_hyper_connection."},{"blk.0.hc_ffn_","mtp.layers.0.mlp_hyper_connection."},{"output_hc_","mtp.hyper_connection_mixer."}})if(n.starts_with(from)){
  auto suffix=n.substr(from.size());std::map<std::string,std::string> m{{"norm.weight","hc_norm.weight"},{"down.weight","input_mix_weight_down.weight"},{"up.weight","input_mix_weight_up.weight"},{"inject.weight","block_inject_weight.weight"}};return to+m.at(suffix);}
 static const std::map<std::string,std::string> names{{"attn_q.weight","self_attn.q_proj.weight"},{"attn_k.weight","self_attn.k_proj.weight"},{"attn_v.weight","self_attn.v_proj.weight"},{"attn_output.weight","self_attn.o_proj.weight"},{"attn_q_norm.weight","self_attn.q_norm.weight"},{"attn_k_norm.weight","self_attn.k_norm.weight"},{"indexer.q_norm.weight","self_attn.indexer.q_layernorm.weight"},{"indexer.k_norm.weight","self_attn.indexer.k_layernorm.weight"},{"indexer.q_proj.weight","self_attn.indexer.index_qk_proj.weight"},{"indexer.k_proj.weight","self_attn.indexer.index_qk_proj.weight"},{"ffn_gate_inp.weight","mlp.gate.weight"},{"ffn_gate_inp_shexp.weight","mlp.shared_expert_gate.weight"},{"ffn_gate_shexp.weight","mlp.shared_expert.gate_proj.weight"},{"ffn_up_shexp.weight","mlp.shared_expert.up_proj.weight"},{"ffn_down_shexp.weight","mlp.shared_expert.down_proj.weight"}};
 return "mtp.layers.0."+names.at(n.substr(6));
}
struct Weight {Allocation id{};iq3::Type type=iq3::Type::BF16;unsigned rows{},cols{},experts=1;bool int8=false,fp8=false,raw=false;};
struct ProviderError:std::runtime_error{using std::runtime_error::runtime_error;};
class DraftRuntime {
 template<class Owner> friend class pipeline::StageCheckpointFor;
 Engine& e;std::unique_ptr<Store> store;flash::Plan p;std::map<std::string,Slot> buffers;std::map<std::string,Weight> weights;
 std::map<const flash::Launch*,Engine::Prepared> prepared;
 struct Site { std::vector<ownrt::PreparedCompute> commands; bool gemv=false; int cls=0; bool head=false; };
 std::vector<Site> issue_sites;
 std::vector<flash::Launch> merge_plan;
 bool captured=false;int context_extent=32; const void* reverse_hidden=nullptr;
 Allocation publication{},half_staging{};ownrt::Event publication_event=0;
 bool async_pending=false,pending_head=false;int pending_confirmed=0;
 std::chrono::steady_clock::time_point pending_start;
 // Discarded recursive lookahead diagnostic; packet66 mechanism, generalized to depth 2/3.
 int depth_probe=0,queued_probe=-1,queued_confirmed=-1;bool verify_depth_restore=false;
 Allocation probe_backup{};size_t probe_bytes=0;
 std::ofstream probe_trace;fs::path probe_output;
 std::vector<uint8_t> probe_reverse_hidden; // owned target input across deferred diagnostic work
 // Profiling remains owned by Engine::pending and is consumed once by drain().

 // GSQ: OWNRT_DRAFT_HEAD_Q4=1 selects the draft-only symmetric Q4 head (packet83 q4-g32, quantized at load from the
 // target's head rows; the draft runs BF16, and target verification keeps every output exact).
 bool q4_head()const{
  if(e.a.gsq_packed){static const bool q4=[]{const char* v=std::getenv("OWNRT_DRAFT_HEAD_Q4");return v&&v[0]=='1';}();if(q4)return !e.a.mini;}
  return e.sealed_selection.draft.at("head_format")=="q4-g32";}
 // GSQ: the draft head scores the first OWNRT_DRAFT_PREFIX_ROWS token ids (a multiple of 256; default the full
 // vocabulary). Draft-only: the target head and every target output are unchanged, guesses outside the prefix miss.
 unsigned prefix_rows()const{
  if(e.a.gsq_packed){static const unsigned rows=[&]{const char* v=std::getenv("OWNRT_DRAFT_PREFIX_ROWS");if(!v)return 0u;const long n=std::atol(v);
    require(n>0&&n%256==0,"OWNRT_DRAFT_PREFIX_ROWS must be a positive multiple of 256");return unsigned(n);}();
   if(!rows||e.a.mini)return p.g.vocab;require(rows<=p.g.vocab,"draft prefix exceeds the vocabulary");return rows;}
  return p83::rows(p.g.vocab,e.a.mini,e.sealed_selection.draft.at("head_prefix"));}
 bool selected(const std::string& key)const{return e.sealed_selection.draft.at(key)=="packet59";}
 bool changed(const flash::Launch& l)const{auto i=p59c::sites.find(l.label);return i!=p59c::sites.end()&&selected(i->second);}
 bool fused(const flash::Launch& l)const{auto i=p59c::consumers.find(l.label);return i!=p59c::consumers.end()&&selected(i->second);}
 void direct(const flash::Launch& l) {
  if(fused(l))return;
  if(l.op=="merge_hidden_norm") {
   e.finish(0,changed(l)?p59::norm(e.dev(0),id("merge.hidden"),weights.at("mtp.pre_fc_norm_hidden.weight").id,id("merge.norm"),1,4*p.g.h):norm_hidden(e.dev(0),id("merge.hidden"),weights.at("mtp.pre_fc_norm_hidden.weight").id,id("merge.norm"),scratch,4*p.g.h),false);return;}
  if(l.op=="norm"&&changed(l)){e.finish(0,p59::norm(e.dev(0),id(l.inputs[0]),weights.at(l.weights[0]).id,id(l.outputs[0]),l.shape[0],l.shape[1]),false);return;}
  if(l.op=="merge_add") {e.finish(0,merge(e.dev(0),id("merge.projected"),id("merge.embedding_projected"),id("streams"),p.g.h),false);return;}
  if(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")matrix(l);
  else {auto b=prepared.find(&l);auto tmp=b==prepared.end()?bind(l):Engine::Prepared{};const auto& v=b==prepared.end()?tmp:b->second;
   if(!e.a.mini&&l.op=="route"&&changed(l)){e.finish(0,e.sealed_selection.site(v.spec)(e.dev(0),v.spec,v.bindings,control,score,probability,{}),false);return;}
   e.finish(0,(l.op=="silu_div4"||l.op=="silu_product"||l.op=="hc_mix"||l.op=="moe_combine")?mtp36::elementwise(e.dev(0),v.spec,v.bindings):packet18::submit_parallel(e.dev(0),v.spec,v.bindings,control,score,probability,{}),false);}
 }
 void prepare_commands() {
  if(!e.prepared_path)return;
  e.drain();const int saved_class=e.current_cls;
  auto capture=[&](const flash::Launch& l){
   Site site;site.gemv=l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up";
   site.head=l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax";
   e.set_class("draft."+l.label);site.cls=e.current_cls;
   e.preparing_commands=true;e.dev(0).begin_capture(site.commands);
   try {direct(l);e.dev(0).end_capture();e.preparing_commands=false;}
   catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}
   issue_sites.push_back(std::move(site));
  };
  for(const auto& l:merge_plan)capture(l);
  for(const auto& l:p.launches)capture(l);
  e.current_cls=saved_class;captured=true;
 }

 Allocation scratch{},control{},score{},probability{},head_workspace{},head_fp32{};unsigned head_variant{};std::string head_candidate;
 std::set<Allocation> mutable_ids;size_t allocated=0;int position=0;bool disabled=false;std::ofstream trace;
 Allocation alloc(const std::string& name,size_t bytes,Category category=Category::scratch){auto id=e.allocate(0,"draft:"+name,bytes,category,category==Category::weights?Lifetime::process:category==Category::kv?Lifetime::request:Lifetime::transaction);allocated+=bytes;mutable_ids.insert(id);std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)));for(size_t off=0;off<bytes;off+=zero.size())e.upload(0,id,off,zero.data(),std::min(zero.size(),bytes-off));return id;}
 Allocation id(const std::string& name)const{auto allocation=buffers.at(name).id;if(e.a.pipeline_draft_partition)require(mutable_ids.count(allocation),"draft matrix/fused buffer outside provider ownership");return allocation;}
 void add(const std::string& n,size_t elements,Scalar type=Scalar::bf16){buffers[n]={alloc(n,elements*flash::scalar_bytes(type),(ends(n,".keys")||ends(n,".values")||ends(n,".raw")||ends(n,".pooled"))?Category::kv:Category::scratch),elements,type};}
 std::vector<uint8_t> synthetic(const std::string& n,unsigned rows,unsigned cols,bool gain){std::vector<uint8_t> raw(size_t(rows)*cols*(gain?4:2));for(size_t i=0;i<size_t(rows)*cols;++i){float f=flash::mock::weight("draft:"+n,int(i/cols),int(i%cols));if(gain)f+=1;if(gain)std::memcpy(raw.data()+i*4,&f,4);else {auto b=iq3::bf16_bits(f);std::memcpy(raw.data()+i*2,&b,2);}}return raw;}
 void load(const std::string& name,unsigned rows,unsigned cols,bool gain=false,bool routed=false){if(weights.count(name))return;Weight w;w.rows=rows;w.cols=cols;w.experts=routed?p.g.experts:1;w.fp8=routed&&!e.a.mini&&e.a.draft_experts_fp8;w.int8=routed&&!e.a.mini&&!w.fp8;w.type=gain?iq3::Type::F32:iq3::Type::BF16;
  size_t rb=w.int8?cols+cols/16*4:w.fp8?cols+cols/128*4:cols*(gain?4:2);w.id=alloc("weight:"+name,size_t(w.experts)*rows*rb,Category::weights);mutable_ids.erase(w.id);
  if(routed){for(unsigned expert=0;expert<w.experts;++expert){std::vector<uint8_t> raw;if(e.a.mini)raw=synthetic(name+std::to_string(expert),rows,cols,false);else {std::string kind=name.find("gate_")!=std::string::npos?"gate":name.find("up_")!=std::string::npos?"up":"down";std::string prefix="mtp.layers.0.mlp.experts."+std::to_string(expert)+"."+kind+"_proj";raw=(w.fp8?fp8_pack:requant)(store->read(prefix+".weight"),store->read(prefix+".weight_scale_inv"),rows,cols);}e.upload(0,w.id,size_t(expert)*rows*rb,raw.data(),raw.size());}}
  else {std::vector<uint8_t> raw;if(e.a.mini)raw=synthetic(name,rows,cols,gain);else {auto full=store->read(official(name));if(name=="blk.0.indexer.q_proj.weight")raw={full.begin(),full.begin()+rows*cols*2};else if(name=="blk.0.indexer.k_proj.weight")raw={full.end()-rows*cols*2,full.end()};else raw=std::move(full);require(raw.size()==size_t(rows)*cols*2,"official draft dense shape "+name);if(gain){std::vector<uint8_t> converted(size_t(rows)*cols*4);for(size_t i=0;i<size_t(rows)*cols;++i){uint16_t b;std::memcpy(&b,raw.data()+i*2,2);float f=1.f+iq3::bits_float(uint32_t(b)<<16);std::memcpy(converted.data()+i*4,&f,4);}raw=std::move(converted);}}
   e.upload(0,w.id,0,raw.data(),raw.size());}weights[name]=w;
 }
 void matrix(const flash::Launch& l){const auto& w=weights.at(l.weights[0]);
  if(l.label=="logits"){if(q4_head()){e.finish(0,p83::submit(e.dev(0),w.id,id(l.inputs[0]),id(l.outputs[0]),prefix_rows(),w.cols),true);return;}integrated::Matrix m{};m.w=w.id;m.type=w.type;m.x=id(l.inputs[0]);m.y=id(l.outputs[0]);m.rows=w.rows;m.columns=w.cols;m.span=m.rows;m.workspace=head_workspace;m.raw=w.raw;
   p56::restrict_matrix(m,prefix_rows());
   if((head_candidate.starts_with("p25.")||head_candidate.starts_with("p27."))&&!e.a.mini){Allocation prepared_input=0;if(head_candidate=="p27.fp32_input"){e.finish(0,packet26::p25bridge::prepare_input(e.dev(0),m.x,head_fp32,m.columns),true);prepared_input=head_fp32;}e.finish(0,packet26::p25bridge::submit(e.dev(0),{m},head_candidate,false,head_variant,prepared_input),true);return;}
   if(!e.a.mini && (head_candidate.starts_with("p33.")||head_candidate.starts_with("p29."))){
    if(head_candidate=="p33.dense.segment"&&m.type==iq3::Type::Q6_K&&e.dense_metadata()&&arithmetic::is_expanded(head_variant)&&e.weights[0].count("output.weight")&&w.id==e.weights[0].at("output.weight")){e.finish(0,p183::segment(e.dev(0),{m},false,head_variant),true);return;} // packet183-s1
    e.finish(0,head_candidate.starts_with("p33.")?p33::submit(e.dev(0),{m},head_candidate,false,head_variant):p29::submit(e.dev(0),{m},head_candidate,false,head_variant),true);return;
   }
   e.finish(0,(head_candidate.starts_with("p28.")&&!e.a.mini)?p28::submit(e.dev(0),{m},head_candidate,false,head_variant):integrated::dense(e.dev(0),m,head_variant),true);return;}
  if(!changed(l)){matrix_production(l);return;}
  if(l.label.ends_with(".gate")&&selected(p59c::consumers.at(l.label.substr(0,l.label.size()-4)+"mix"))){auto prefix=l.label.substr(0,l.label.size()-4);e.finish(0,p59::gate_mix(e.dev(0),w.id,id(l.inputs[0]),id(l.outputs[0]),id(prefix+"norm"),id(prefix+"mix"),p.g.h,w.cols),true);return;}
  p59::Linear a;a.w=w.id;a.x=id(l.inputs[0]);a.y=id(l.outputs[0]);a.rows=l.shape[1];a.columns=l.shape[2];a.batch=l.shape[0];a.experts=w.experts;a.int8=w.int8;require(!w.fp8,"p59 draft path has no FP8 expert kernel");
  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}
  if(l.label.ends_with(".low")&&selected(p59c::consumers.at(l.label.substr(0,l.label.size()-3)+"act"))){a.tail=p59::low;a.out=id(l.label.substr(0,l.label.size()-3)+"act");}
  if(l.label=="blk.0.expsgate"&&selected("fuse_expert_activation")){a.tail=p59::product;a.out=id("blk.0.expsact");}
  if(l.label=="blk.0.shexpup"&&selected("fuse_shared_activation")){a.tail=p59::product;a.other=id("blk.0.shexpgate");a.out=id("blk.0.shexpact");}
  if(l.label=="merge.projected"&&selected("fuse_hidden_merge")){a.tail=p59::merge_add;a.other=id("merge.embedding_projected");a.out=id("streams");}
  if(l.label=="blk.0.attention"&&selected("fuse_attention_combine")){a.tail=p59::attention;a.inject=id("blk.0.hc.a.inject");a.out=id("streams");}
  e.finish(0,p59::linear(e.dev(0),a),true);
 }
 void matrix_production(const flash::Launch& l){const auto& w=weights.at(l.weights[0]);
  // Draft BF16 projections use the same selected target class, with batch
  // rows represented as separate matrices. INT8 draft experts have no matching
  // target IQ2/IQ4 format; their registered draft-only kernel remains explicit.
  const auto candidate=packet26::dispatch.gemv_for(l.label);
  if(!e.a.mini&&l.op=="gemv"&&candidate=="p33.dense.segment") {
   require(l.shape[0]==1,"selected draft projection expects one input row");
   integrated::Matrix m{};m.w=w.id;m.type=w.type;m.x=id(l.inputs[0]);m.y=id(l.outputs[0]);m.rows=w.rows;m.columns=w.cols;m.span=m.rows;m.workspace=head_workspace;
   e.finish(0,p33::submit(e.dev(0),{m},candidate,false,0),true);
   return;
  }
  // p30.small rows4 uses Q8_0 weights on the target. Draft BF16 keeps
  // the equivalent four-subgroup rows4 schedule in mtp36::linear.
  Linear a;a.w=w.id;a.x=id(l.inputs[0]);a.y=id(l.outputs[0]);a.rows=l.shape[1];a.columns=l.shape[2];a.batch=l.shape[0];a.experts=w.experts;a.int8=w.int8;a.fp8=w.fp8;
  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}
  e.finish(0,mtp36::linear(e.dev(0),a),true);
 }
 Engine::Prepared bind(const flash::Launch& l){Spec s;s.g=p.g;s.extent=(l.op=="qsa_select"||l.op=="qsa_attention")?std::min(p.g.context,context_extent):0;s.packed_heads=!e.a.mini;s.site.parameter=l.parameter;std::copy(l.shape.begin(),l.shape.end(),s.site.shape);s.implementation=1;
  static const std::map<std::string,Op> ops={
#define OP(n) {#n,Op::n}
 OP(norm),OP(silu_div4),OP(silu_product),OP(hc_mix),OP(hc_combine),OP(route),OP(expert_gather),OP(moe_combine),OP(qsa_prepare),OP(qsa_append_pool),OP(qsa_select),OP(qsa_attention),OP(argmax)
#undef OP
  };
  if(l.op=="begin")s.special=Special::begin;else if(l.op=="commit")s.special=Special::commit;else if(l.op=="check_status")s.special=Special::check_status;else s.op=ops.at(l.op);
  std::vector<Allocation> a;int k=0;for(auto n:l.inputs){auto b=buffers.at(n);s.sizes[k]=b.n;s.types[k++]=b.type;a.push_back(b.id);++s.ni;}for(auto n:l.outputs){auto b=buffers.at(n);require(mutable_ids.count(b.id),"draft output aliases immutable or target allocation");s.sizes[k]=b.n;s.types[k++]=b.type;a.push_back(b.id);++s.no;}
  for(auto n:l.weights){auto w=weights.at(n);a.push_back(w.id);s.grids[s.nw]=w.type;s.weight_elements[s.nw++]=size_t(w.rows)*w.cols;}
  if(l.op=="argmax")p56::restrict_argmax(s,prefix_rows());
  s.implementation=packet26::dispatch.implementation_for(l.label,s.op);
  if(!e.a.mini&&l.op=="qsa_attention"&&changed(l))s.implementation=12;
  a.push_back(scratch);a.push_back(id("error"));a.push_back(id("position"));a.push_back(id("active"));a.push_back(e.ropes[0]);return {s,a};
 }
public:
#include "pipeline/recursive_provider/draft_runtime_extension.inc"
#include "pipeline/recursive_provider/pending_survival.inc"
 int live_position()const{return position;}
 int live_extent()const{return context_extent;}
 void live_reset_admission(){
  require(e.a.pipeline_live_draft&&!disabled&&!async_pending&&!reverse_hidden&&queued_probe==-1&&queued_confirmed==-1,"live reset cannot clear failed/pending draft");
  e.drain();auto bytes=e.readback(0,id("error"),4);int error=0;std::memcpy(&error,bytes.data(),4);require(!error,"live reset cannot clear draft sticky error");
 }
 std::vector<Allocation> live_mutable_inventory()const{require(e.a.pipeline_live_draft,"live draft mutable inventory mode");return {mutable_ids.begin(),mutable_ids.end()};}
 std::vector<Allocation> live_pinned_inventory()const{require(e.a.pipeline_live_draft,"live draft pinned inventory mode");return {publication,half_staging};}
 int live_step(int confirmed,int target_position,bool head,const void* hidden,size_t bytes){
  require(e.a.pipeline_live_draft&&e.a.pipeline_provider()&&e.a.mtp&&e.a.draft_rank==0,"live draft owner");
  require(!depth_probe&&!async_pending&&!disabled&&queued_probe==-1&&hidden&&bytes==e.stream_bytes(),"live draft quiescent handoff");
  probe_reverse_hidden.resize(bytes);std::memcpy(probe_reverse_hidden.data(),hidden,bytes);
  reverse_hidden=probe_reverse_hidden.data();
  // Fail closed; unlike the legacy optional provider, a broken live owner must
  // not return a plausible proposal or continue with a partially advanced cache.
  int token=-1;
  if(e.a.pipeline_draft_partition){
   const auto sources=e.fp32_sources;const auto extents=e.fp32_extents;const auto lookup=e.lookup_ids;const auto selected=e.selected;const auto loaded=e.loaded_layer;
   const auto history0=e.history0,history1=e.history1;const auto bank=e.bank_parity;const int target_extent=e.context_extent,alternate_extent=e.alternate_context_extent,old_class=e.current_cls;
   require(!e.preparing_commands&&!e.draft_timing,"live draft operator borrow must begin idle");
   token=compute(confirmed,target_position,head);
   require(!e.preparing_commands&&!e.draft_timing&&e.fp32_sources==sources&&e.fp32_extents==extents&&e.lookup_ids==lookup&&e.selected==selected&&e.loaded_layer==loaded&&e.history0==history0&&e.history1==history1&&e.bank_parity==bank&&e.context_extent==target_extent&&e.alternate_context_extent==alternate_extent,"draft mutated target operator metadata");
   e.current_cls=old_class;
  }else token=compute(confirmed,target_position,head);
  require(!disabled&&position==target_position&&!reverse_hidden&&!async_pending,"live draft canonical completion");
  require(head?(token>=0&&token<p.g.vocab):token==-1,"live draft proposal bounds");
  return token;
 }
 void set_reverse_hidden(const void* bytes){require(!async_pending,"reverse handoff while draft pending");
  if(depth_probe){require(bytes,"depth probe reverse hidden input missing");probe_reverse_hidden.resize(e.stream_bytes());
   std::memcpy(probe_reverse_hidden.data(),bytes,probe_reverse_hidden.size());reverse_hidden=probe_reverse_hidden.data();
  }else reverse_hidden=bytes;
 }
 DraftRuntime(Engine& target):e(target),trace(e.a.output/"draft-rows.jsonl"){
  if(const char* value=std::getenv("OWNRT_DRAFT_DEPTH_PROBE")){
   const std::string v=value;require(v=="0"||v=="2"||v=="3","OWNRT_DRAFT_DEPTH_PROBE must be 0, 2 or 3");depth_probe=std::stoi(v);
   if(depth_probe){
    require(e.a.draft_fault=="none"&&!e.a.tp_replicate,"depth probe requires normal draft and no TP");
    const char* early=std::getenv("OWNRT_EARLY_RANK1");
    require(early&&std::string(early)=="0","depth probe requires OWNRT_EARLY_RANK1=0 to protect reverse hidden ownership");
   }
  }
  if(const char* value=std::getenv("OWNRT_DRAFT_DEPTH_VERIFY")){
   const std::string v=value;require(v=="0"||v=="1","OWNRT_DRAFT_DEPTH_VERIFY must be 0 or 1");verify_depth_restore=v=="1";
   require(!verify_depth_restore||depth_probe,"depth restore verification requires the probe");
  }
  require((e.a.pipeline_live_draft&&e.a.pipeline_provider())||e.a.rank==e.a.draft_rank||!e.a.draft_capture.empty(),"draft placement/capture");if(!e.a.mini)store=std::make_unique<Store>(e.a.draft_manifest,e.a.draft_model);
  p=flash::Builder(e.p.g).build({true});std::erase_if(p.launches,[](const auto& l){return l.op=="lookup"||l.op=="broadcast";});
  // Keep plan shape/ops, pair routed gate/up at the same schedule point.
  for(size_t i=0;i+2<p.launches.size();++i)if(p.launches[i].label=="blk.0.expsgate"){
   auto& a=p.launches[i];auto b=p.launches[i+2];require(b.label=="blk.0.expsup","draft paired schedule");a.op="expert_gate_up";a.weights.push_back(b.weights[0]);a.outputs.insert(a.outputs.end(),b.outputs.begin(),b.outputs.end());p.launches.erase(p.launches.begin()+i+2);break;}
  for(auto b:p.buffers)add(b.name,count(b.shape),b.type);
  add("merge.hidden",4*p.g.h);add("merge.norm",4*p.g.h);add("merge.projected",4*p.g.h);add("merge.embedding_norm",p.g.h);add("merge.embedding_projected",p.g.h);
  scratch=alloc("scratch",8*1024*1024);control=alloc("controls",12);score=alloc("scores",24*(p.g.budget+3)*4);probability=alloc("probabilities",24*(p.g.budget+3)*4);head_workspace=alloc("head-workspace",size_t(p.g.vocab)*8*4);head_fp32=alloc("head-fp32",size_t(p.g.h)*4);
  publication=e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned);
  half_staging=e.allocate(0,"draft:half-staging",4+e.stream_bytes(),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
  std::memset(e.dev(0).arena.row(publication).pointer,0,8);std::memset(e.dev(0).arena.row(half_staging).pointer,0,4+e.stream_bytes());
  uint32_t active=1;e.upload(0,id("active"),0,&active,4);
  for(const auto& l:p.launches)for(size_t j=0;j<l.weights.size();++j){auto n=l.weights[j];if(n=="output.weight")continue;
   if(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")load(n,l.shape[1],l.shape[2],false,l.op!="gemv");
   else if(l.op=="norm")load(n,1,l.shape[0]*l.shape[1],true);
   else if(l.op=="qsa_prepare")load(n,1,j==2?p.g.id:p.g.ad,true);
   else if(l.op=="qsa_append_pool")load(n,1,p.g.id,true);else throw std::runtime_error("draft weight site "+n);
  }
  load("mtp.pre_fc_norm_embedding.weight",1,p.g.h,true);load("mtp.pre_fc_norm_hidden.weight",1,4*p.g.h,true);load("mtp.fc_embedding.weight",p.g.h,p.g.h);load("mtp.fc_hidden.weight",p.g.h,p.g.h);
  const flash::Launch* head=nullptr;for(const auto& l:p.launches)if(l.label=="logits")head=&l;require(head,"draft head absent");head_variant=selected_variant(e.w,e.a,p,*head);head_candidate=e.a.gsq_packed?"p33.dense.segment":packet26::dispatch.gemv_for(head->label);
  auto t=e.w.directory.at("output.weight");Weight hw;hw.rows=p.g.vocab;hw.cols=p.g.h;hw.type=flash::grid_type(t.grid);
  if(!e.a.mini){if(e.a.draft_capture.empty())require(e.a.memory=="resident"&&(e.a.rank==0||(e.a.pipeline_live_draft&&e.a.pipeline_provider())||e.weights[0].count("output.weight")),"packet79 production requires rank0 prefix or rank1 resident head");require(head_candidate=="p33.dense.segment"&&head_variant==6,"packet56 requires unchanged expanded Q6 head kernel");}
  if(q4_head()){
   const size_t rb=hw.cols/iq3::layout(hw.type).elements*iq3::layout(hw.type).bytes,er=p83::row_bytes(hw.cols);hw.rows=prefix_rows();
   hw.id=alloc("q4-head",size_t(hw.rows)*er,Category::weights);mutable_ids.erase(hw.id);
   const size_t chunk=std::max(size_t(1),size_t(4194304)/std::max(rb,er));
   for(size_t row=0;row<hw.rows;row+=chunk){auto n=std::min(chunk,size_t(hw.rows)-row);auto source=e.w.read("output.weight",row*rb,n*rb);auto raw=p83::quantize(hw.type,source.data(),n,hw.cols);e.upload(0,hw.id,row*er,raw.data(),raw.size());}
  }else if(e.a.memory=="resident"&&e.weights[0].count("output.weight")&&!e.packed_weight("output.weight")&&!e.raw_weights.count({0,"output.weight"}))hw.id=e.weights[0].at("output.weight");
  else if(denseraw::draft_head()&&e.a.gsq_packed&&!e.a.mini&&e.a.rank==0&&!e.a.pipeline_enabled()&&head_variant==6&&hw.type==iq3::Type::Q6_K&&hw.cols==2560) {
   // OWNRT_DRAFT_HEAD_RAW=1 (lab 2026-10-26, default off): the rank-0 draft head prefix as raw-size Q6_K rows
   // (dense_raw.hpp), read by the BF16-activation raw kernel; every row is checked element by element against the
   // expanded rows the default build uploads (OWNRT_DENSE_RAW_VERIFY=0 skips the check).
   hw.rows=prefix_rows();const size_t rb=hw.cols/256*210,er=arithmetic::row_bytes(hw.type,hw.cols,head_variant);
   hw.id=alloc("shared-head-host",size_t(hw.rows)*rb,Category::weights);mutable_ids.erase(hw.id);hw.raw=true;uint64_t checked=0,bad=0;
   const size_t nr=std::max(size_t(1),size_t(4194304)/er);
   for(size_t row=0;row<hw.rows;row+=nr){const auto n=std::min(nr,size_t(hw.rows)-row);auto source=e.w.read("output.weight",row*rb,n*rb);
    auto rows=denseraw::repack(hw.type,source.data(),source.size(),hw.cols);
    if(denseraw::verify()){auto expanded=iq3::expanded::expand(hw.type,source.data(),source.size(),hw.cols);bad+=denseraw::check_rows(hw.type,rows.data(),expanded.data(),n,hw.cols,er);checked+=uint64_t(n)*hw.cols;}
    require(!bad,"OWNRT_DRAFT_HEAD_RAW decode differs from the expanded rows");e.upload(0,hw.id,row*rb,rows.data(),rows.size());}
   save(e.a.output/"draft-head-raw.json","{\"rows\":"+std::to_string(hw.rows)+",\"raw_bytes\":"+std::to_string(size_t(hw.rows)*rb)+",\"expanded_bytes\":"+std::to_string(size_t(hw.rows)*er)+",\"checked_elements\":"+std::to_string(checked)+",\"mismatches\":"+std::to_string(bad)+"}");
  }
  else { /* OWNRT_DENSE_RAW: a raw target head is never shared (the draft head kernel reads expanded rows) */auto fmt=iq3::layout(hw.type);size_t rb=hw.cols/fmt.elements*fmt.bytes,er=arithmetic::row_bytes(hw.type,hw.cols,head_variant);if(e.a.rank==0||(e.a.pipeline_live_draft&&e.a.pipeline_provider())||e.packed_weight("output.weight"))hw.rows=prefix_rows();hw.id=alloc("shared-head-host",size_t(hw.rows)*er,Category::weights);mutable_ids.erase(hw.id);
   size_t nr=std::max(size_t(1),size_t(4194304)/std::max(rb,er));for(size_t row=0;row<hw.rows;row+=nr){auto n=std::min(nr,size_t(hw.rows)-row);auto raw=e.w.read("output.weight",row*rb,n*rb);if(arithmetic::is_expanded(head_variant))raw=iq3::expanded::expand(hw.type,raw.data(),raw.size(),hw.cols);e.upload(0,hw.id,row*er,raw.data(),raw.size());}}
  save(e.a.output/"draft-prefix.json","{\"schema\":\"packet83.draft-prefix.v1\",\"rows\":"+std::to_string(prefix_rows())+",\"full_rows\":"+std::to_string(p.g.vocab)+",\"calibration_sha256\":"+(e.a.gsq_packed?std::string("null"):ownrt::quote(p83::coverage_sha256))+",\"target_head_unchanged\":true,\"extra_weight_bytes\":"+std::to_string(q4_head()?size_t(hw.rows)*p83::row_bytes(hw.cols):(e.a.rank==0||(e.a.pipeline_live_draft&&e.a.pipeline_provider())||e.packed_weight("output.weight"))?size_t(hw.rows)*(hw.raw?size_t(hw.cols/256*210):arithmetic::row_bytes(hw.type,hw.cols,head_variant)):0)+",\"head_scope\":\"draft-only-Q4-or-resident-shared\"}");
  weights["output.weight"]=hw;
  for(const auto& l:p.launches)if(l.op!="gemv"&&l.op!="routed_gemv"&&l.op!="expert_gate_up")prepared.emplace(&l,bind(l));
  if(store){require(store->reads.size()==3101,"not all official draft tensors read");std::ostringstream o;o<<"{";bool comma=false;for(auto& [n,h]:store->reads){o<<(comma?",":"")<<ownrt::quote(n)<<":"<<ownrt::quote(h);comma=true;}o<<"}";save(e.a.output/"draft-tensor-reads.json",o.str());}
  merge_plan={
   {"norm","merge.embedding_norm",{"embedding"},{"merge.embedding_norm"},{"mtp.pre_fc_norm_embedding.weight"},{1,p.g.h}},
   {"merge_hidden_norm","merge.hidden_norm",{},{},{},{}},
   {"gemv","merge.embedding_projected",{"merge.embedding_norm"},{"merge.embedding_projected"},{"mtp.fc_embedding.weight"},{1,p.g.h,p.g.h}},
   {"gemv","merge.projected",{"merge.norm"},{"merge.projected"},{"mtp.fc_hidden.weight"},{4,p.g.h,p.g.h}},
   {"merge_add","merge.add",{},{},{},{}}};
  // Every mutable draft allocation is private; target access is immutable
  // head/rope weights and the explicit pre-draft hidden-state copy only.
  for(const auto& [name,slot]:e.buffers[0])require(!mutable_ids.count(slot.id),"draft/target mutable alias");
  for(const auto& [name,allocation]:e.weights[0])require(!mutable_ids.count(allocation),"draft mutable/target weight alias");
  // Fail at init if a changed site was not registered; prevents silent partial selections.
  for(const auto& l:p.launches)if((l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up"||l.op=="norm"||l.op=="route"||l.op=="qsa_attention")&&l.label!="logits")require(p59c::sites.contains(l.label),"unregistered draft site: "+l.label);
  std::ostringstream choices;choices<<"{\"schema\":\"packet59c.draft-kernel-choices.v1\",\"selection_sha256\":"<<ownrt::quote(e.sealed_selection.observed_sha256)<<",\"target_mutable_aliases\":0,\"choices\":{";bool comma=false;
  for(auto&[key,value]:e.sealed_selection.draft){choices<<(comma?",":"")<<ownrt::quote(key)<<":"<<ownrt::quote(value);comma=true;}
  choices<<"},\"sites\":{";comma=false;
  auto record=[&](const flash::Launch& l){choices<<(comma?",":"")<<ownrt::quote(l.label)<<":"<<ownrt::quote(fused(l)?"fused-at-producer":changed(l)?"packet59":"production");comma=true;};
  for(const auto& l:merge_plan)record(l);for(const auto& l:p.launches)record(l);
  choices<<"}}";save(e.a.output/"draft-kernel-choices.json",choices.str());
  prepare_commands();
  if(e.a.pipeline_ring_live_draft)prepare_recursive_depth2();
  if(depth_probe){
   for(auto allocation:mutable_ids)probe_bytes+=e.dev(0).arena.row(allocation).bytes;
   require(probe_bytes<=32ull*1024*1024,"depth probe mutable backup exceeds 32 MiB reserve");
   probe_backup=e.allocate(0,"draft:depth-probe-backup",probe_bytes,Category::runtime_overhead,Lifetime::process);
   allocated+=probe_bytes;probe_output=e.a.output;
   probe_trace.open(probe_output/"draft-depth-probe.jsonl");require(bool(probe_trace),"depth probe trace open");
   save(e.a.output/"draft-depth-probe-config.json","{\"schema\":\"ownrt.draft-depth.config.v1\",\"depth\":"+std::to_string(depth_probe)+",\"backup_bytes\":"+std::to_string(probe_bytes)+",\"diagnostic_only\":true,\"discards_proposals\":true}");
  }
  save(e.a.output/"draft-memory.json","{\"device_allocation_bytes\":"+std::to_string(allocated)+",\"cache_bytes\":"+std::to_string(size_t(p.g.context)*(2*p.g.kvh*p.g.ad+p.g.id)*2+size_t((p.g.context+3)/4)*p.g.id*2)+",\"head_weight_shared\":"+(!q4_head()&&e.a.memory=="resident"&&e.weights[0].count("output.weight")&&!e.packed_weight("output.weight")?"true":"false")+"}");
 }
 void admit_position(int restored_extent=0) {
  require(position>=0&&position<p.g.context,"draft capacity position admission");
  int bound=restored_extent?restored_extent:std::min(p.g.context,((position+32)/32)*32);
  require(bound>0&&bound<=p.g.context,"draft restored extent bound");
  if(bound==context_extent)return;
  e.drain();context_extent=bound;
  for(size_t i=0;i<p.launches.size();++i){const auto& l=p.launches[i];
   if(l.op!="qsa_select"&&l.op!="qsa_attention")continue;
   prepared[&l]=bind(l);if(!captured)continue;
   auto& site=issue_sites.at(merge_plan.size()+i);site.commands.clear();
   e.preparing_commands=true;e.dev(0).begin_capture(site.commands);
   try{direct(l);e.dev(0).end_capture();e.preparing_commands=false;}
   catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}
  }
 }
 int compute(int confirmed,int target_position,bool head,bool asynchronous=false,bool recursive=false){
  if(!recursive)flush_depth_probe();
  require(!async_pending,"draft publication still pending");if(disabled)return -1;admit_position();require(confirmed>=0&&confirmed<p.g.vocab,"draft confirmed token bound");require(target_position==position+1,"draft confirmed position sequence");auto start=std::chrono::steady_clock::now();
  if(e.a.draft_fault=="error"||e.a.draft_fault=="stall"){if(e.a.draft_fault=="stall"){auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(50);while(std::chrono::steady_clock::now()<until){e.guard();poll(nullptr,0,5);}}throw ProviderError("cooperative injected provider failure before submission");}
  e.drain();struct Timing{Engine& e;Timing(Engine& x):e(x){e.draft_timing=true;}~Timing(){e.draft_timing=false;}} timing(e);if(recursive){
   e.tail=e.io_copy(0,id("merge.hidden"),0,id("streams"),0,4*p.g.h*2);
  }else if((e.a.rank==0||(e.a.pipeline_live_draft&&e.a.pipeline_provider()))&&e.a.draft_capture.empty()){require(reverse_hidden,"missing confirmed reverse streams");
   if(e.a.f32_activations){ // exact-mode target streams are F32; the draft keeps its BF16 inputs (proposals are target-verified)
    std::vector<uint16_t> hidden(size_t(4)*p.g.h);auto* f=static_cast<const float*>(reverse_hidden);for(size_t i=0;i<hidden.size();++i)hidden[i]=iq3::bf16_bits(f[i]);
    e.upload(0,id("merge.hidden"),0,hidden.data(),hidden.size()*2);
   } else e.upload(0,id("merge.hidden"),0,reverse_hidden,4*p.g.h*2);
   reverse_hidden=nullptr;}else{require(!e.a.f32_activations,"exact F32 activations: draft must take the converted rank-1 reverse streams");e.tail=e.io_copy(0,id("merge.hidden"),0,e.buffers[0].at("streams").id,0,4*p.g.h*2);}e.drain(); // packet188: kernel when kernel_io=kernel
  // Bounded target embedding row only. No target PLE/history/token preparation.
  auto t=e.w.directory.at("token_embd.weight");auto type=flash::grid_type(t.grid);auto fmt=iq3::layout(type);size_t rb=p.g.h/fmt.elements*fmt.bytes;auto raw=e.w.read(t.name,size_t(confirmed)*rb,rb);std::vector<uint16_t> emb(p.g.h);for(int k=0;k<p.g.h;++k)emb[k]=iq3::bf16_bits(gsq::element(unsigned(type),raw,p.g.h,k));e.upload(0,id("embedding"),0,emb.data(),emb.size()*2);
  if(captured) {
   // OWNRT_DECODE_PROFILE=2: per-site device time of the draft (diagnostic; waits for the draft, no arithmetic change).
   static const bool draft_profile=[]{const char* v=std::getenv("OWNRT_DECODE_PROFILE");return v&&std::atoi(v)==2;}();
   std::vector<std::pair<int,ownrt::Event>> profiled;
   for(const auto& site:issue_sites){if(!head&&site.head)continue;
    if(Engine::ms(start)>300000.)throw ProviderError("cooperative provider deadline between submissions");
    e.guard();e.current_cls=site.cls;
    for(const auto& cmd:site.commands){auto event=e.dev(0).issue(cmd);e.finish(0,{event,event,1},site.gemv);if(draft_profile)profiled.push_back({site.cls,event});}
   }
   if(draft_profile&&!profiled.empty()){
    try{e.dev(0).wait(profiled.back().second,std::chrono::milliseconds(10000));}catch(const std::exception&){}
    std::map<std::string,std::array<double,2>> spent;uint64_t first=0,last=0;
    for(const auto& [cls,event]:profiled){ownrt::EventTiming t{};try{t=e.dev(0).timing(event);}catch(const std::exception&){continue;}
     if(!first)first=t.start_ns;last=std::max(last,t.end_ns);std::string key=cls>=0&&size_t(cls)<e.class_names.size()?e.class_names[size_t(cls)]:std::string("?");if(key.starts_with("draft."))key=key.substr(6);
     if(key.starts_with("blk.")){auto dot=key.find('.',4);if(dot!=std::string::npos)key=key.substr(dot+1);}
     auto& v=spent[key];v[0]+=double(t.end_ns-t.start_ns)/1000.0;v[1]+=1;}
    std::ofstream o(e.a.output/"draft-device-profile.jsonl",std::ios::app);o<<"{\"position\":"<<position<<",\"span_us\":"<<double(last-first)/1000.0<<",\"sites\":{";bool comma=false;
    for(const auto& [k,v]:spent){o<<(comma?",":"")<<ownrt::quote(k)<<":{\"count\":"<<v[1]<<",\"busy_us\":"<<v[0]<<"}";comma=true;}o<<"}}\n";
   }
  } else {
   for(const auto& l:merge_plan){if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);}
   for(const auto& l:p.launches){if(!head&&(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax"))continue;
    if(Engine::ms(start)>300000.)throw ProviderError("cooperative provider deadline between submissions");
    e.guard();if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);
   }
  }
  if(asynchronous) {
   // Copies belong to the same in-order queue and to private pinned memory.
   // No host access occurs until the final copy event reports completion.
   publication_event=e.io_copy(0,{{publication,0,id("error"),0,4},{publication,4,id("next_token"),0,4}});e.tail=publication_event; // packet188
   pending_start=start;pending_head=head;pending_confirmed=confirmed;async_pending=true;e.progress_pending=true;
   return -1;
  }
  e.drain();auto error=e.readback(0,id("error"),4);int status;std::memcpy(&status,error.data(),4);if(status){disabled=true;return -1;}
  ++position;if(e.a.draft_fault=="late-error")throw ProviderError("injected provider failure after cache append");int token=-1;if(head){auto b=e.readback(0,id("next_token"),4);std::memcpy(&token,b.data(),4);}
  if(recursive)return token;
  if(depth_probe&&head&&token>=0&&token<p.g.vocab){queued_probe=token;queued_confirmed=confirmed;}
  trace<<"{\"draft_position\":"<<position-1<<",\"confirmed_token\":"<<confirmed<<",\"guess\":"<<token<<",\"head\":"<<(head?"true":"false")<<",\"wall_ms\":"<<Engine::ms(start)<<"}\n";trace.flush();if(e.a.draft_fault=="suppress")return -1;if(e.a.draft_fault=="garbage")return p.g.vocab;return e.a.draft_fault=="wrong"&&head?(token+1)%p.g.vocab:token;
 }
 int run(int confirmed,int target_position,bool head){try{return compute(confirmed,target_position,head);}catch(const ProviderError& ex){e.drain();disabled=true;trace<<"{\"disabled\":true,\"reason\":"<<ownrt::quote(ex.what())<<"}\n";trace.flush();return -1;}}
 bool submitting()const{return async_pending;}
 bool begin(int confirmed,int target_position,bool head){
  try {compute(confirmed,target_position,head,true);return async_pending;}
  catch(const ProviderError& ex){e.drain();disabled=true;trace<<"{\"disabled\":true,\"reason\":"<<ownrt::quote(ex.what())<<"}\n";trace.flush();return false;}
 }
 struct Completion {int token=-1;double wall_ms=0,gpu_ms=0;};
 std::optional<Completion> poll_result(){
  if(!async_pending||!e.dev(0).complete(publication_event))return {};
  int status=0,token=-1;auto* bytes=static_cast<const uint8_t*>(e.dev(0).arena.row(publication).pointer);
  std::memcpy(&status,bytes,4);if(pending_head)std::memcpy(&token,bytes+4,4);
  Completion done;done.wall_ms=Engine::ms(pending_start);
  // Publish as soon as the ordered readback is complete. Do not synchronously
  // query all draft event timestamps here, or duplicate Engine::drain's checks.
  // Negative timing means deferred, not a zero-duration GPU measurement.
  done.gpu_ms=-1;
  async_pending=false;e.progress_pending=false;publication_event=0;
  if(status){disabled=true;token=-1;}else ++position;
  if(e.a.draft_fault=="late-error"){disabled=true;token=-1;}
  if(e.a.draft_fault=="suppress")token=-1;
  if(e.a.draft_fault=="garbage")token=p.g.vocab;
  if(e.a.draft_fault=="wrong"&&pending_head&&token>=0)token=(token+1)%p.g.vocab;
  done.token=token;
  // Completion can run inside Engine::wait: queue only, never submit/drain here.
  if(depth_probe&&pending_head&&token>=0&&token<p.g.vocab){queued_probe=token;queued_confirmed=pending_confirmed;}
  trace<<"{\"draft_position\":"<<position-1<<",\"confirmed_token\":"<<pending_confirmed<<",\"guess\":"<<token<<",\"head\":"<<(pending_head?"true":"false")<<",\"wall_ms\":"<<done.wall_ms<<",\"nonblocking\":true}\n";trace.flush();return done;
 }
 void queue_half_inputs(int token,const void* streams){
  // The previous request is fully confirmed before begin(). The draft's first
  // copy captured its target hidden input before these ordered overwrites.
  auto* bytes=static_cast<uint8_t*>(e.dev(0).arena.row(half_staging).pointer);
  std::memcpy(bytes,&token,4);std::memcpy(bytes+4,streams,e.stream_bytes());
  e.tail=e.io_copy(0,{{e.buffers[0].at("token").id,0,half_staging,0,4},{e.buffers[0].at("streams").id,0,half_staging,4,e.stream_bytes()}}); // packet188
 }
 // Reset is quiescent and never frees/reallocates a shared-owner allocation.
 // Conversation continuation: only the row trace moves to the new request directory; the draft state stays.
 void redirect(const fs::path& output){require(!async_pending,"redirect with pending draft publication");flush_depth_probe();trace.close();trace.clear();trace.open(output/"draft-rows.jsonl");require(bool(trace),"draft redirect trace");if(depth_probe)probe_output=output;}
 void reset_request(const fs::path& output) {
  flush_depth_probe();
  require(!async_pending,"reset with pending draft publication");e.drain();for(auto allocation:mutable_ids){auto bytes=e.dev(0).arena.row(allocation).bytes;
   std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)));
   for(size_t off=0;off<bytes;off+=zero.size())e.upload(0,allocation,off,zero.data(),std::min(zero.size(),bytes-off));}
  uint32_t active=1;e.upload(0,id("active"),0,&active,4);e.drain();position=0;disabled=false;reverse_hidden=nullptr;
  std::memset(e.dev(0).arena.row(publication).pointer,0,8);std::memset(e.dev(0).arena.row(half_staging).pointer,0,4+e.stream_bytes());
  publication_event=0;e.progress_pending=false;e.progress_callback={};
  if(e.a.pipeline_persistent_requests||e.a.pipeline_ring_persistent_requests){pending_start={};pending_head=false;pending_confirmed=0;queued_probe=queued_confirmed=-1;probe_reverse_hidden.clear();admit_position(32);}
  trace.close();trace.clear();trace.open(output/"draft-rows.jsonl");require(bool(trace),"draft reset trace");
  if(depth_probe)probe_output=output;
 }
 void flush_depth_probe(){
  if(queued_probe<0)return;
  require(depth_probe&&probe_backup&&!async_pending&&!e.progress_pending,"depth probe requires quiescent draft publication");
  const int d1=queued_probe,confirmed=queued_confirmed;queued_probe=-1;queued_confirmed=-1;
  require(!disabled&&d1>=0&&d1<p.g.vocab,"depth probe draft state invalid");
  e.drain();const auto total_start=std::chrono::steady_clock::now();
  const int saved_position=position,saved_extent=context_extent,saved_class=e.current_cls;
  const bool saved_disabled=disabled;const void* saved_reverse=reverse_hidden;
  auto copy_state=[&](bool restore){ownrt::CopyEngine copy(e.dev(0));size_t offset=0;
   for(auto allocation:mutable_ids){const size_t bytes=e.dev(0).arena.row(allocation).bytes;
    e.tail=restore?copy.copy(allocation,0,probe_backup,offset,bytes,{}):copy.copy(probe_backup,offset,allocation,0,bytes,{});offset+=bytes;}
   require(offset==probe_bytes,"depth probe mutable allocation inventory changed");e.drain();
  };
  copy_state(false);const double snapshot_ms=Engine::ms(total_start);
  std::vector<int> guesses{d1};std::vector<double> pass_ms;
  try {
   for(int depth=2;depth<=depth_probe&&position<p.g.context;++depth){
    auto start=std::chrono::steady_clock::now();int token=compute(guesses.back(),position+1,true,false,true);
    require(token>=0&&token<p.g.vocab&&!disabled,"recursive draft returned invalid token");
    guesses.push_back(token);pass_ms.push_back(Engine::ms(start));
   }
  }catch(const std::exception& ex){
   // Do not submit recovery copies after a device fault or continue with altered state.
   throw std::runtime_error(std::string("discarded depth probe failed; engine must halt: ")+ex.what());
  }
  auto restore_start=std::chrono::steady_clock::now();copy_state(true);
  position=saved_position;disabled=saved_disabled;reverse_hidden=saved_reverse;
  if(position<p.g.context)admit_position(saved_extent);
  else require(context_extent==saved_extent,"depth probe capacity extent changed");
  e.current_cls=saved_class;
  if(verify_depth_restore){
   const auto saved=e.readback(0,probe_backup,probe_bytes);size_t offset=0;
   for(auto allocation:mutable_ids){const auto bytes=e.readback(0,allocation,e.dev(0).arena.row(allocation).bytes);
    require(std::equal(bytes.begin(),bytes.end(),saved.begin()+offset),"depth probe mutable bytes differ after restore");offset+=bytes.size();}
   require(offset==saved.size()&&position==saved_position&&context_extent==saved_extent&&disabled==saved_disabled&&reverse_hidden==saved_reverse,"depth probe metadata restore mismatch");
  }
  probe_trace<<"{\"schema\":\"ownrt.draft-depth.cycle.v1\",\"request_output\":"<<ownrt::quote(probe_output.string())
   <<",\"rank\":"<<e.a.rank<<",\"confirmed_position\":"<<saved_position<<",\"confirmed_token\":"<<confirmed
   <<",\"d1_position\":"<<saved_position+1<<",\"requested_depth\":"<<depth_probe<<",\"guesses\":[";
  for(size_t i=0;i<guesses.size();++i)probe_trace<<(i?",":"")<<guesses[i];
  probe_trace<<"],\"extra_pass_wall_ms\":[";for(size_t i=0;i<pass_ms.size();++i)probe_trace<<(i?",":"")<<pass_ms[i];
  probe_trace<<"],\"snapshot_ms\":"<<snapshot_ms<<",\"restore_ms\":"<<Engine::ms(restore_start)
   <<",\"probe_total_ms\":"<<Engine::ms(total_start)<<",\"snapshot_bytes\":"<<probe_bytes
   <<",\"restored_position\":"<<position<<",\"restored_extent\":"<<context_extent
   <<",\"mutable_bytes_verified\":"<<(verify_depth_restore?"true":"false")
   <<",\"discarded\":true,\"diagnostic_only\":true}\n";probe_trace.flush();require(bool(probe_trace),"depth probe trace write failed");
 }
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/draft_bracket.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/draft_checkpoint.hpp"
 void live_dump(const fs::path& path){
  require(e.a.pipeline_live_draft&&!disabled&&!async_pending&&!e.progress_pending&&!reverse_hidden&&queued_probe==-1&&queued_confirmed==-1,"live draft dump quiescence");
  e.drain();require(!e.integer(0,"error"),"live draft dump target error");
  std::map<std::string,Allocation> all;for(auto id:mutable_ids)all.emplace(e.dev(0).arena.row(id).label,id);
  all.emplace(e.dev(0).arena.row(publication).label,publication);all.emplace(e.dev(0).arena.row(half_staging).label,half_staging);
  std::map<Allocation,std::string> typed;for(const auto& [name,s]:buffers)typed.emplace(s.id,name);
  fs::create_directories(path);gsq_bundle::Writer bundle(path);std::ostringstream states,layouts;
  bool comma=false;for(const auto& [name,id]:all){const auto& row=e.dev(0).arena.row(id);std::vector<uint8_t> raw;
   if(row.memory==Memory::pinned){auto* first=static_cast<const uint8_t*>(row.pointer);raw.assign(first,first+row.bytes);}
   else {require(row.memory==Memory::device,"live draft dump allocation memory");raw=e.readback(0,id,row.bytes);}
   bundle.append(name+".bin",raw.data(),raw.size());states<<(comma?",":"")<<ownrt::quote(name)<<":"<<ownrt::quote(hash(raw));
   layouts<<(comma?",":"")<<ownrt::quote(name)<<":{\"bytes\":"<<row.bytes<<",\"category\":"<<int(row.category)<<",\"memory\":"<<ownrt::quote(row.memory==Memory::pinned?"pinned":"device");
   auto found=typed.find(id);if(found!=typed.end()){const auto& slot=buffers.at(found->second);
    auto type=slot.type;layouts<<",\"semantic\":\"typed-buffer\",\"dtype\":"<<ownrt::quote(type==flash::Scalar::bf16?"BF16":type==flash::Scalar::f32?"F32":type==flash::Scalar::i32?"I32":type==flash::Scalar::u32?"U32":"I64")<<",\"shape\":[";
    auto plan_buffer=std::find_if(p.buffers.begin(),p.buffers.end(),[&](const auto& b){return b.name==found->second;});
    if(plan_buffer==p.buffers.end())layouts<<slot.n;else for(size_t k=0;k<plan_buffer->shape.size();++k)layouts<<(k?",":"")<<plan_buffer->shape[k];layouts<<"]";
   }else layouts<<",\"semantic\":\"opaque-mutable-scratch\"";
   layouts<<"}";comma=true;
  }
  std::ostringstream out;out<<"{\"schema\":\"ownrt.draft-state.v1\",\"buffers\":{"<<states.str()<<"},\"layouts\":{"<<layouts.str()<<"},\"host\":{\"position\":"<<position<<",\"context_extent\":"<<context_extent
   <<",\"disabled\":"<<(disabled?"true":"false")<<",\"async_pending\":"<<(async_pending?"true":"false")<<",\"pending_head\":"<<(pending_head?"true":"false")<<",\"pending_confirmed\":"<<pending_confirmed
   <<",\"reverse_hidden_present\":"<<(reverse_hidden?"true":"false")<<",\"queued_probe\":"<<queued_probe<<",\"queued_confirmed\":"<<queued_confirmed<<",\"depth_probe\":"<<depth_probe<<"}}";
  bundle.finish(out.str());
 }
 void dump_all_state(const fs::path& path) {
  flush_depth_probe();
  dump(path);std::ostringstream out;out<<"{\"position\":"<<position<<",\"disabled\":"<<(disabled?"true":"false")<<",\"mutable_sha256\":{";
  bool comma=false;for(auto allocation:mutable_ids){const auto& row=e.dev(0).arena.row(allocation);
   auto bytes=e.readback(0,allocation,row.bytes);out<<(comma?",":"")<<ownrt::quote(row.label)<<":"<<ownrt::quote(hash(bytes));comma=true;}
  out<<"}}";save(path/"all-state.json",out.str());
 }
 void dump(const fs::path& path,bool logits=false){fs::create_directories(path);for(auto n:{"blk.0.qsa.keys","blk.0.qsa.values","blk.0.qsa.raw","blk.0.qsa.pooled","position"}){auto s=buffers.at(n);size_t elements=s.n;if(logits&&std::string(n)!="position")elements=size_t(std::string(n).ends_with(".pooled")?position/4:position)*(std::string(n).ends_with(".keys")||std::string(n).ends_with(".values")?p.g.kvh*p.g.ad:p.g.id);auto raw=e.readback(0,s.id,elements*flash::scalar_bytes(s.type));std::ofstream f(path/(std::string(n)+".bin"),std::ios::binary);f.write(reinterpret_cast<const char*>(raw.data()),raw.size());}
  if(logits)for(auto n:{"final.mix","logits"}){auto s=buffers.at(n);size_t elements=std::string(n)=="logits"?prefix_rows():s.n;auto raw=e.readback(0,s.id,elements*flash::scalar_bytes(s.type));std::ofstream f(path/(std::string(n)+".bf16"),std::ios::binary);f.write(reinterpret_cast<const char*>(raw.data()),raw.size());}}
};
}
