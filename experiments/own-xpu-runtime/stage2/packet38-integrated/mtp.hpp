#pragma once
#include "mtp_kernels.hpp"
#include <cfenv>
#include <poll.h>
// Included after Engine. All mutable allocations below are private to the draft.
// The target Engine supplies one lifetime owner, uploads and immutable weights.
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
inline std::string official(const std::string& n){
 if(n.starts_with("mtp."))return n;
 for(auto [from,to]:std::vector<std::pair<std::string,std::string>>{{"blk.0.hc_attn_","mtp.layers.0.attn_hyper_connection."},{"blk.0.hc_ffn_","mtp.layers.0.mlp_hyper_connection."},{"output_hc_","mtp.hyper_connection_mixer."}})if(n.starts_with(from)){
  auto suffix=n.substr(from.size());std::map<std::string,std::string> m{{"norm.weight","hc_norm.weight"},{"down.weight","input_mix_weight_down.weight"},{"up.weight","input_mix_weight_up.weight"},{"inject.weight","block_inject_weight.weight"}};return to+m.at(suffix);}
 static const std::map<std::string,std::string> names{{"attn_q.weight","self_attn.q_proj.weight"},{"attn_k.weight","self_attn.k_proj.weight"},{"attn_v.weight","self_attn.v_proj.weight"},{"attn_output.weight","self_attn.o_proj.weight"},{"attn_q_norm.weight","self_attn.q_norm.weight"},{"attn_k_norm.weight","self_attn.k_norm.weight"},{"indexer.q_norm.weight","self_attn.indexer.q_layernorm.weight"},{"indexer.k_norm.weight","self_attn.indexer.k_layernorm.weight"},{"indexer.q_proj.weight","self_attn.indexer.index_qk_proj.weight"},{"indexer.k_proj.weight","self_attn.indexer.index_qk_proj.weight"},{"ffn_gate_inp.weight","mlp.gate.weight"},{"ffn_gate_inp_shexp.weight","mlp.shared_expert_gate.weight"},{"ffn_gate_shexp.weight","mlp.shared_expert.gate_proj.weight"},{"ffn_up_shexp.weight","mlp.shared_expert.up_proj.weight"},{"ffn_down_shexp.weight","mlp.shared_expert.down_proj.weight"}};
 return "mtp.layers.0."+names.at(n.substr(6));
}
struct Weight {Allocation id{};iq3::Type type=iq3::Type::BF16;unsigned rows{},cols{},experts=1;bool int8=false;};
struct ProviderError:std::runtime_error{using std::runtime_error::runtime_error;};
class DraftRuntime {
 Engine& e;std::unique_ptr<Store> store;flash::Plan p;std::map<std::string,Slot> buffers;std::map<std::string,Weight> weights;
 std::map<const flash::Launch*,Engine::Prepared> prepared;
 struct Site { std::vector<ownrt::PreparedCompute> commands; bool gemv=false; int cls=0; bool head=false; };
 std::vector<Site> issue_sites;
 std::vector<flash::Launch> merge_plan;
 bool captured=false;
 void direct(const flash::Launch& l) {
  if(l.op=="merge_hidden_norm") {e.finish(0,norm_hidden(e.dev(0),id("merge.hidden"),weights.at("mtp.pre_fc_norm_hidden.weight").id,id("merge.norm"),scratch,4*p.g.h),false);return;}
  if(l.op=="merge_add") {e.finish(0,merge(e.dev(0),id("merge.projected"),id("merge.embedding_projected"),id("streams"),p.g.h),false);return;}
  if(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")matrix(l);
  else {auto b=prepared.find(&l);auto tmp=b==prepared.end()?bind(l):Engine::Prepared{};const auto& v=b==prepared.end()?tmp:b->second;
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
 Allocation id(const std::string& name)const{return buffers.at(name).id;}
 void add(const std::string& n,size_t elements,Scalar type=Scalar::bf16){buffers[n]={alloc(n,elements*flash::scalar_bytes(type),(ends(n,".keys")||ends(n,".values")||ends(n,".raw")||ends(n,".pooled"))?Category::kv:Category::scratch),elements,type};}
 std::vector<uint8_t> synthetic(const std::string& n,unsigned rows,unsigned cols,bool gain){std::vector<uint8_t> raw(size_t(rows)*cols*(gain?4:2));for(size_t i=0;i<size_t(rows)*cols;++i){float f=flash::mock::weight("draft:"+n,int(i/cols),int(i%cols));if(gain)f+=1;if(gain)std::memcpy(raw.data()+i*4,&f,4);else {auto b=iq3::bf16_bits(f);std::memcpy(raw.data()+i*2,&b,2);}}return raw;}
 void load(const std::string& name,unsigned rows,unsigned cols,bool gain=false,bool routed=false){if(weights.count(name))return;Weight w;w.rows=rows;w.cols=cols;w.experts=routed?p.g.experts:1;w.int8=routed&&!e.a.mini;w.type=gain?iq3::Type::F32:iq3::Type::BF16;
  size_t rb=w.int8?cols+cols/16*4:cols*(gain?4:2);w.id=alloc("weight:"+name,size_t(w.experts)*rows*rb,Category::weights);mutable_ids.erase(w.id);
  if(routed){for(unsigned expert=0;expert<w.experts;++expert){std::vector<uint8_t> raw;if(e.a.mini)raw=synthetic(name+std::to_string(expert),rows,cols,false);else {std::string kind=name.find("gate_")!=std::string::npos?"gate":name.find("up_")!=std::string::npos?"up":"down";std::string prefix="mtp.layers.0.mlp.experts."+std::to_string(expert)+"."+kind+"_proj";raw=requant(store->read(prefix+".weight"),store->read(prefix+".weight_scale_inv"),rows,cols);}e.upload(0,w.id,size_t(expert)*rows*rb,raw.data(),raw.size());}}
  else {std::vector<uint8_t> raw;if(e.a.mini)raw=synthetic(name,rows,cols,gain);else {auto full=store->read(official(name));if(name=="blk.0.indexer.q_proj.weight")raw={full.begin(),full.begin()+rows*cols*2};else if(name=="blk.0.indexer.k_proj.weight")raw={full.end()-rows*cols*2,full.end()};else raw=std::move(full);require(raw.size()==size_t(rows)*cols*2,"official draft dense shape "+name);if(gain){std::vector<uint8_t> converted(size_t(rows)*cols*4);for(size_t i=0;i<size_t(rows)*cols;++i){uint16_t b;std::memcpy(&b,raw.data()+i*2,2);float f=1.f+iq3::bits_float(uint32_t(b)<<16);std::memcpy(converted.data()+i*4,&f,4);}raw=std::move(converted);}}
   e.upload(0,w.id,0,raw.data(),raw.size());}weights[name]=w;
 }
 void matrix(const flash::Launch& l){const auto& w=weights.at(l.weights[0]);
  if(l.label=="logits"){integrated::Matrix m{};m.w=w.id;m.type=w.type;m.x=id(l.inputs[0]);m.y=id(l.outputs[0]);m.rows=w.rows;m.columns=w.cols;m.span=m.rows;m.workspace=head_workspace;
   if((head_candidate.starts_with("p25.")||head_candidate.starts_with("p27."))&&!e.a.mini){Allocation prepared_input=0;if(head_candidate=="p27.fp32_input"){e.finish(0,packet26::p25bridge::prepare_input(e.dev(0),m.x,head_fp32,m.columns),true);prepared_input=head_fp32;}e.finish(0,packet26::p25bridge::submit(e.dev(0),{m},head_candidate,false,head_variant,prepared_input),true);return;}
   if(!e.a.mini && (head_candidate.starts_with("p33.")||head_candidate.starts_with("p29."))){
    e.finish(0,head_candidate.starts_with("p33.")?p33::submit(e.dev(0),{m},head_candidate,false,head_variant):p29::submit(e.dev(0),{m},head_candidate,false,head_variant),true);return;
   }
   e.finish(0,(head_candidate.starts_with("p28.")&&!e.a.mini)?p28::submit(e.dev(0),{m},head_candidate,false,head_variant):integrated::dense(e.dev(0),m,head_variant),true);return;}
  Linear a;a.w=w.id;a.x=id(l.inputs[0]);a.y=id(l.outputs[0]);a.rows=l.shape[1];a.columns=l.shape[2];a.batch=l.shape[0];a.experts=w.experts;a.int8=w.int8;
  if(l.op=="routed_gemv"||l.op=="expert_gate_up"){a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);if(l.op=="expert_gate_up"){a.paired=true;a.peer=weights.at(l.weights[1]).id;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}}
  e.finish(0,mtp36::linear(e.dev(0),a),true);
 }
 Engine::Prepared bind(const flash::Launch& l){Spec s;s.g=p.g;s.packed_heads=!e.a.mini;s.site.parameter=l.parameter;std::copy(l.shape.begin(),l.shape.end(),s.site.shape);s.implementation=1;
  static const std::map<std::string,Op> ops={
#define OP(n) {#n,Op::n}
 OP(norm),OP(silu_div4),OP(silu_product),OP(hc_mix),OP(hc_combine),OP(route),OP(expert_gather),OP(moe_combine),OP(qsa_prepare),OP(qsa_append_pool),OP(qsa_select),OP(qsa_attention),OP(argmax)
#undef OP
  };
  if(l.op=="begin")s.special=Special::begin;else if(l.op=="commit")s.special=Special::commit;else if(l.op=="check_status")s.special=Special::check_status;else s.op=ops.at(l.op);
  std::vector<Allocation> a;int k=0;for(auto n:l.inputs){auto b=buffers.at(n);s.sizes[k]=b.n;s.types[k++]=b.type;a.push_back(b.id);++s.ni;}for(auto n:l.outputs){auto b=buffers.at(n);require(mutable_ids.count(b.id),"draft output aliases immutable or target allocation");s.sizes[k]=b.n;s.types[k++]=b.type;a.push_back(b.id);++s.no;}
  for(auto n:l.weights){auto w=weights.at(n);a.push_back(w.id);s.grids[s.nw]=w.type;s.weight_elements[s.nw++]=size_t(w.rows)*w.cols;}
  if(l.op=="qsa_attention")s.implementation=packet26::dispatch.implementation_for(l.label,s.op);
  a.push_back(scratch);a.push_back(id("error"));a.push_back(id("position"));a.push_back(id("active"));a.push_back(e.ropes[0]);return {s,a};
 }
public:
 DraftRuntime(Engine& target):e(target),trace(e.a.output/"draft-rows.jsonl"){
  require(e.a.rank==1||!e.a.draft_capture.empty(),"draft only on rank1/capture");if(!e.a.mini)store=std::make_unique<Store>(e.a.draft_manifest,e.a.draft_model);
  p=flash::Builder(e.p.g).build({true});std::erase_if(p.launches,[](const auto& l){return l.op=="lookup"||l.op=="broadcast";});
  // Keep plan shape/ops, pair routed gate/up at the same schedule point.
  for(size_t i=0;i+2<p.launches.size();++i)if(p.launches[i].label=="blk.0.expsgate"){
   auto& a=p.launches[i];auto b=p.launches[i+2];require(b.label=="blk.0.expsup","draft paired schedule");a.op="expert_gate_up";a.weights.push_back(b.weights[0]);a.outputs.insert(a.outputs.end(),b.outputs.begin(),b.outputs.end());p.launches.erase(p.launches.begin()+i+2);break;}
  for(auto b:p.buffers)add(b.name,count(b.shape),b.type);
  add("merge.hidden",4*p.g.h);add("merge.norm",4*p.g.h);add("merge.projected",4*p.g.h);add("merge.embedding_norm",p.g.h);add("merge.embedding_projected",p.g.h);
  scratch=alloc("scratch",8*1024*1024);control=alloc("controls",12);score=alloc("scores",24*(p.g.budget+3)*4);probability=alloc("probabilities",24*(p.g.budget+3)*4);head_workspace=alloc("head-workspace",size_t(p.g.vocab)*8*4);head_fp32=alloc("head-fp32",size_t(p.g.h)*4);
  uint32_t active=1;e.upload(0,id("active"),0,&active,4);
  for(const auto& l:p.launches)for(size_t j=0;j<l.weights.size();++j){auto n=l.weights[j];if(n=="output.weight")continue;
   if(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")load(n,l.shape[1],l.shape[2],false,l.op!="gemv");
   else if(l.op=="norm")load(n,1,l.shape[0]*l.shape[1],true);
   else if(l.op=="qsa_prepare")load(n,1,j==2?p.g.id:p.g.ad,true);
   else if(l.op=="qsa_append_pool")load(n,1,p.g.id,true);else throw std::runtime_error("draft weight site "+n);
  }
  load("mtp.pre_fc_norm_embedding.weight",1,p.g.h,true);load("mtp.pre_fc_norm_hidden.weight",1,4*p.g.h,true);load("mtp.fc_embedding.weight",p.g.h,p.g.h);load("mtp.fc_hidden.weight",p.g.h,p.g.h);
  const flash::Launch* head=nullptr;for(const auto& l:e.p.launches)if(l.label=="logits")head=&l;require(head,"target shared head absent");head_variant=e.variant(*head);head_candidate=e.gemv_choices.at(head).first;
  auto t=e.w.directory.at("output.weight");Weight hw;hw.rows=p.g.vocab;hw.cols=p.g.h;hw.type=flash::grid_type(t.grid);
  if(e.a.memory=="resident")hw.id=e.weights[0].at("output.weight");else {auto fmt=iq3::layout(hw.type);size_t rb=hw.cols/fmt.elements*fmt.bytes,er=arithmetic::row_bytes(hw.type,hw.cols,head_variant);hw.id=alloc("shared-head-host",size_t(hw.rows)*er,Category::weights);mutable_ids.erase(hw.id);
   size_t nr=std::max(size_t(1),size_t(4194304)/std::max(rb,er));for(size_t row=0;row<hw.rows;row+=nr){auto n=std::min(nr,size_t(hw.rows)-row);auto raw=e.w.read("output.weight",row*rb,n*rb);if(arithmetic::is_expanded(head_variant))raw=iq3::expanded::expand(hw.type,raw.data(),raw.size(),hw.cols);e.upload(0,hw.id,row*er,raw.data(),raw.size());}}
  weights["output.weight"]=hw;
  for(const auto& l:p.launches)if(l.op!="gemv"&&l.op!="routed_gemv"&&l.op!="expert_gate_up")prepared.emplace(&l,bind(l));
  if(store){require(store->reads.size()==3101,"not all official draft tensors read");std::ostringstream o;o<<"{";bool comma=false;for(auto& [n,h]:store->reads){o<<(comma?",":"")<<ownrt::quote(n)<<":"<<ownrt::quote(h);comma=true;}o<<"}";save(e.a.output/"draft-tensor-reads.json",o.str());}
  merge_plan={
   {"norm","merge.embedding_norm",{"embedding"},{"merge.embedding_norm"},{"mtp.pre_fc_norm_embedding.weight"},{1,p.g.h}},
   {"merge_hidden_norm","merge.hidden_norm",{},{},{},{}},
   {"gemv","merge.embedding_projected",{"merge.embedding_norm"},{"merge.embedding_projected"},{"mtp.fc_embedding.weight"},{1,p.g.h,p.g.h}},
   {"gemv","merge.projected",{"merge.norm"},{"merge.projected"},{"mtp.fc_hidden.weight"},{4,p.g.h,p.g.h}},
   {"merge_add","merge.add",{},{},{},{}}};
  prepare_commands();
  save(e.a.output/"draft-memory.json","{\"device_allocation_bytes\":"+std::to_string(allocated)+",\"cache_bytes\":"+std::to_string(size_t(p.g.context)*(2*p.g.kvh*p.g.ad+p.g.id)*2+size_t((p.g.context+3)/4)*p.g.id*2)+",\"head_weight_shared\":"+(e.a.memory=="resident"?"true":"false")+"}");
 }
 int compute(int confirmed,int target_position,bool head){
  if(disabled)return -1;require(confirmed>=0&&confirmed<p.g.vocab,"draft confirmed token bound");require(target_position==position+1,"draft confirmed position sequence");auto start=std::chrono::steady_clock::now();
  if(e.a.draft_fault=="error"||e.a.draft_fault=="stall"){if(e.a.draft_fault=="stall"){auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(50);while(std::chrono::steady_clock::now()<until){e.guard();poll(nullptr,0,5);}}throw ProviderError("cooperative injected provider failure before submission");}
  e.drain();struct Timing{Engine& e;Timing(Engine& x):e(x){e.draft_timing=true;}~Timing(){e.draft_timing=false;}} timing(e);ownrt::CopyEngine copy(e.dev(0));e.tail=copy.copy(id("merge.hidden"),0,e.buffers[0].at("streams").id,0,4*p.g.h*2,{});e.drain();
  // Bounded target embedding row only. No target PLE/history/token preparation.
  auto t=e.w.directory.at("token_embd.weight");auto type=flash::grid_type(t.grid);auto fmt=iq3::layout(type);size_t rb=p.g.h/fmt.elements*fmt.bytes;auto raw=e.w.read(t.name,size_t(confirmed)*rb,rb);std::vector<uint16_t> emb(p.g.h);for(int k=0;k<p.g.h;++k)emb[k]=iq3::bf16_bits(iq3::element(type,raw.data(),k));e.upload(0,id("embedding"),0,emb.data(),emb.size()*2);
  if(captured) {
   for(const auto& site:issue_sites){if(!head&&site.head)continue;
    if(Engine::ms(start)>300000.)throw ProviderError("cooperative provider deadline between submissions");
    e.guard();e.current_cls=site.cls;
    for(const auto& cmd:site.commands){auto event=e.dev(0).issue(cmd);e.finish(0,{event,event,1},site.gemv);}
   }
  } else {
   for(const auto& l:merge_plan){if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);}
   for(const auto& l:p.launches){if(!head&&(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax"))continue;
    if(Engine::ms(start)>300000.)throw ProviderError("cooperative provider deadline between submissions");
    e.guard();if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);
   }
  }
  e.drain();auto error=e.readback(0,id("error"),4);int status;std::memcpy(&status,error.data(),4);if(status){disabled=true;return -1;}
  ++position;if(e.a.draft_fault=="late-error")throw ProviderError("injected provider failure after cache append");int token=-1;if(head){auto b=e.readback(0,id("next_token"),4);std::memcpy(&token,b.data(),4);}
  trace<<"{\"draft_position\":"<<position-1<<",\"confirmed_token\":"<<confirmed<<",\"guess\":"<<token<<",\"head\":"<<(head?"true":"false")<<",\"wall_ms\":"<<Engine::ms(start)<<"}\n";trace.flush();if(e.a.draft_fault=="suppress")return -1;if(e.a.draft_fault=="garbage")return p.g.vocab;return e.a.draft_fault=="wrong"&&head?(token+1)%p.g.vocab:token;
 }
 int run(int confirmed,int target_position,bool head){try{return compute(confirmed,target_position,head);}catch(const ProviderError& ex){e.drain();disabled=true;trace<<"{\"disabled\":true,\"reason\":"<<ownrt::quote(ex.what())<<"}\n";trace.flush();return -1;}}
 // Reset is quiescent and never frees/reallocates a shared-owner allocation.
 void reset_request(const fs::path& output) {
  e.drain();for(auto allocation:mutable_ids){auto bytes=e.dev(0).arena.row(allocation).bytes;
   std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)));
   for(size_t off=0;off<bytes;off+=zero.size())e.upload(0,allocation,off,zero.data(),std::min(zero.size(),bytes-off));}
  uint32_t active=1;e.upload(0,id("active"),0,&active,4);e.drain();position=0;disabled=false;
  trace.close();trace.open(output/"draft-rows.jsonl");require(bool(trace),"draft reset trace");
 }
 void dump_all_state(const fs::path& path) {
  dump(path);std::ostringstream out;out<<"{\"position\":"<<position<<",\"disabled\":"<<(disabled?"true":"false")<<",\"mutable_sha256\":{";
  bool comma=false;for(auto allocation:mutable_ids){const auto& row=e.dev(0).arena.row(allocation);
   auto bytes=e.readback(0,allocation,row.bytes);out<<(comma?",":"")<<ownrt::quote(row.label)<<":"<<ownrt::quote(hash(bytes));comma=true;}
  out<<"}}";save(path/"all-state.json",out.str());
 }
 void dump(const fs::path& path,bool logits=false){fs::create_directories(path);for(auto n:{"blk.0.qsa.keys","blk.0.qsa.values","blk.0.qsa.raw","blk.0.qsa.pooled","position"}){auto s=buffers.at(n);auto raw=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));std::ofstream f(path/(std::string(n)+".bin"),std::ios::binary);f.write(reinterpret_cast<const char*>(raw.data()),raw.size());}
  if(logits)for(auto n:{"final.mix","logits"}){auto s=buffers.at(n);auto raw=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));std::ofstream f(path/(std::string(n)+".bf16"),std::ios::binary);f.write(reinterpret_cast<const char*>(raw.data()),raw.size());}}
};
}
