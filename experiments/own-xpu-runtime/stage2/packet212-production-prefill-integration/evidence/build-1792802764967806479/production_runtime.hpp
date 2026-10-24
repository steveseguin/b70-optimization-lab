#pragma once
#ifdef OWN_RT_HOST_ONLY
#error P212 production Engine integration is native compile-only
#endif
#include "../packet208-sycl-paired-projections/paired_sycl.hpp"
namespace p212 {
class ProductionChunks {
 Engine& e;Schedule schedule;std::vector<Step> steps;
 using BufferMap=decltype(Engine::buffers)::value_type;using MatrixMap=decltype(Engine::matrices);using PreparedMap=decltype(Engine::prepared);
 struct Bank{BufferMap buffers;MatrixMap matrices;PreparedMap prepared;std::vector<Engine::IssueSite> sites;int extent=32;unsigned row=0;};
 struct Pair{const flash::Launch*original=nullptr;std::array<Matrix,2> matrix;std::vector<ownrt::PreparedCompute> commands;};
 std::array<Bank,2> banks;std::array<Allocation,2> pair_workspace{};std::map<size_t,Pair> pairs;
 int captured_extent=0;bool running=false;size_t row_payload_bytes=0;
 struct Scope{Engine&e;Bank&bank;void swap()noexcept{e.buffers[0].swap(bank.buffers);e.matrices.swap(bank.matrices);e.prepared.swap(bank.prepared);e.issue_sites.swap(bank.sites);std::swap(e.context_extent,bank.extent);e.fp32_sources[0]=0;e.fp32_extents[0]=0;}Scope(Engine&engine,Bank&b):e(engine),bank(b){swap();if(e.prefill_interval&&e.prefill_interval->running())e.prefill_interval->row(bank.row);}~Scope(){swap();}};
 const flash::Launch& site(const std::string& label)const{auto it=std::find_if(e.p.launches.begin(),e.p.launches.end(),[&](const auto&l){return l.label==label;});need(it!=e.p.launches.end(),"p212 required production site");return *it;}
 void cheap_guard(){e.guard();need(!e.poisoned&&!e.bank_parity,"p212 poisoned/parity owner");if(e.prefill_interval)e.prefill_interval->admit();}
 void boundary(){e.drain();e.verify_configuration();cheap_guard();need(!e.integer(0,"error")&&e.integer(0,"active"),"p212 sticky device boundary");}
 void metadata(){std::vector<Site> sites;std::map<std::string,Tensor> tensors;
  for(size_t i=0;i<e.p.launches.size();++i){const auto&l=e.p.launches[i];need(l.card==0,"p212 single-card plan only");sites.push_back({i,l.label,l.op,l.weights});
   if(!l.label.ends_with(".gdn.qkv")&&!l.label.ends_with(".gdn.z"))continue;
   need(e.gemv_choices.at(&l).first=="p33.dense.segment","p212 selected dense arithmetic identity");need(l.weights.size()==1,"p212 selected projection weight");const auto&t=e.w.directory.at(l.weights[0]);need(t.shape.size()==2,"p212 projection tensor dimensions");auto type=flash::grid_type(t.grid);need(type==iq3::Type::Q6_K||type==iq3::Type::Q8_0,"p212 unsupported GDN quantization");auto id=e.weights[0].at(l.weights[0]);const auto&r=e.dev(0).arena.row(id);need(r.live&&r.memory==Memory::device,"p212 resident projection");tensors[l.weights[0]]={type==iq3::Type::Q6_K?"Q6_K":"Q8_0",size_t(t.shape[0]),size_t(t.shape[1]),e.variant(l),r.bytes};
  }schedule=build_schedule(sites,tensors);steps=ordered_steps(schedule);
 }
 void progress(const char*phase,size_t start,size_t paired,size_t position,double ms){std::ofstream out(e.a.output/"p212-chunks.jsonl",std::ios::app);need(bool(out),"p212 chunk evidence open");out<<"{\"phase\":"<<ownrt::quote(phase)<<",\"start\":"<<start<<",\"count\":2,\"paired_commands\":"<<paired<<",\"skipped_originals\":"<<paired*2<<",\"canonical_position\":"<<position<<",\"cache_interval_complete\":"<<(paired==70?"true":"false")<<",\"elapsed_ms\":"<<ms<<"}\n";out.flush();need(bool(out),"p212 chunk evidence write");}
public:
 explicit ProductionChunks(Engine&engine):e(engine){
  need(e.a.p212_prefill&&!e.a.mini&&e.a.cards==1&&e.a.rank==-1&&!e.a.legacy&&!e.a.mtp&&e.a.draft_capture.empty()&&e.a.bracket_inputs.empty()&&e.a.memory=="resident"&&e.a.miss_path=="zero-copy"&&e.a.cache_maintenance=="serial"&&e.a.retirement=="ordered-foreground","p212 exact production owner configuration");
  need(e.p.g.h==2560&&e.p.g.low==320&&e.p.g.mid==640&&e.p.g.top==10&&e.p.g.experts==512&&e.p.g.context==4096&&e.expert_cache&&e.expert_banks.size()==144&&e.route_sources.size()==48&&!e.prefill_interval,"p212 production cache geometry");
  e.drain();metadata();
  // All row allocations precede canonical and row captures. Shared recurrent,
  // expert weights/tables, scratch, scores and mixtures remain the Engine's.
  for(unsigned row=0;row<2;++row){banks[row].row=row;banks[row].buffers=e.buffers[0];
   for(const auto&name:std::array<std::string,5>{"token","position","streams","embedding","blk.1.ple.lookup"}){auto value=e.buffers[0].at(name);size_t bytes=value.n*flash::scalar_bytes(value.type);value.id=e.allocate(0,"p212:row"+std::to_string(row)+":"+name,bytes,Category::scratch,Lifetime::transaction);banks[row].buffers.at(name)=value;row_payload_bytes+=bytes;std::vector<uint8_t> zero(bytes);e.upload(0,value.id,0,zero.data(),bytes);}
   pair_workspace[row]=e.allocate(0,"p212:pair-workspace"+std::to_string(row),4,Category::scratch,Lifetime::transaction);row_payload_bytes+=4;
   const auto&q=site("blk.0.gdn.qkv");const std::array<std::string,4> first{q.inputs.at(0),site("blk.0.hc.a.inject").outputs.at(0),q.outputs.at(0),site("blk.0.gdn.z").outputs.at(0)};
   for(size_t n=0;n<first.size();++n){auto value=e.buffers[0].at(first[n]);size_t bytes=value.n*flash::scalar_bytes(value.type);value.id=e.allocate(0,"p212:row"+std::to_string(row)+":retained"+std::to_string(n),bytes,Category::scratch,Lifetime::transaction);row_payload_bytes+=bytes;std::vector<uint8_t> zero(bytes);e.upload(0,value.id,0,zero.data(),bytes);
    for(const auto&layer:schedule.layers)if(layer.paired){auto prefix="blk."+std::to_string(layer.id)+".";const auto&ql=e.p.launches[layer.qkv];const std::array<std::string,4> names{ql.inputs.at(0),site(prefix+"hc.a.inject").outputs.at(0),ql.outputs.at(0),e.p.launches[layer.z].outputs.at(0)};const auto&original=banks[row].buffers.at(names[n]);need(original.n==value.n&&original.type==value.type,"p212 retained row type/extent");banks[row].buffers.at(names[n])=value;}
   }
  }
  auto routes=e.allocate(0,"p212:row-layer-routes",960*sizeof(iq3::Route),Category::pinned_slab,Lifetime::transfer,Memory::pinned);std::vector<Allocation> retained{e.cache_arena};for(const auto&[name,b]:e.expert_banks){retained.push_back(b.host);retained.push_back(b.table);}e.prefill_interval=std::make_unique<CacheInterval>(e.dev(0),*e.expert_cache,routes,std::move(retained));
  std::ostringstream receipt;receipt<<"{\"row_payload_bytes\":"<<row_payload_bytes<<",\"route_bytes\":"<<960*sizeof(iq3::Route)<<",\"layers\":48,\"paired_layers\":35,\"q8_original_layer\":2,\"shared_persistent_state\":true,\"capture_bytes_not_included\":true}\n";save(e.a.output/"p212-row-storage.json",receipt.str());
 }
 void prepare(){e.drain();cheap_guard();if(captured_extent==e.context_extent)return;
  for(auto&bank:banks){bank.matrices.clear();bank.prepared.clear();bank.sites.clear();bank.extent=e.context_extent;Scope selected(e,bank);e.prepare_plan();e.prepare_commands();need(e.issue_sites.size()==e.p.launches.size(),"p212 all original logical slots captured");}
  pairs.clear();for(const auto&layer:schedule.layers)if(layer.paired)for(auto index:{layer.qkv,layer.z}){Pair pair;pair.original=&e.p.launches[index];need(!e.small_followers.count(pair.original)&&!e.small_groups.count(pair.original),"p212 original projection standalone");
   for(unsigned row=0;row<2;++row){pair.matrix[row]=banks[row].matrices.at(pair.original).at(0);pair.matrix[row].workspace=pair_workspace[row];need(pair.matrix[row].x==banks[row].buffers.at(pair.original->inputs.at(0)).id&&pair.matrix[row].y==banks[row].buffers.at(pair.original->outputs.at(0)).id,"p212 actual captured pair row bindings");need(banks[row].sites.at(index).commands.size()==1,"p212 original single selected projection command");}
   auto&d=e.dev(0);d.begin_capture(pair.commands);try{p208::paired_projection(d,pair.matrix[0],pair.matrix[1],e.variant(*pair.original));d.end_capture();}catch(...){d.end_capture();throw;}need(pair.commands.size()==1&&pair.commands[0].ids.size()==7,"p212 single native pair capture");pairs.emplace(index,std::move(pair));
  }need(pairs.size()==70,"p212 exactly70capturedpairs");captured_extent=e.context_extent;
 }
 void run(const std::vector<int>&input,size_t start){admit_chunk(start,input.size(),e.p.g.context);need(!running&&e.integer(0,"position")==int(start),"p212 canonical chunk position");running=true;const int64_t old0=e.history0,old1=e.history1;int64_t final0=old0,final1=old1;
  try{const auto started=std::chrono::steady_clock::now();progress("start",start,0,start,0);boundary();e.admit_position(int(start));prepare();
   for(unsigned row=0;row<2;++row){Scope selected(e,banks[row]);int token=input.at(start+row);uint32_t position=uint32_t(start+row);e.put(0,"token",&token,4);e.put(0,"position",&position,4);e.prepare_token(token);}final0=e.history0;final1=e.history1;e.history0=old0;e.history1=old1;e.drain();e.prefill_interval->begin();size_t issued=0;
   for(size_t cursor=0;cursor<steps.size();){const auto&step=steps[cursor];cheap_guard();if(step.kind==StepKind::pair){auto&pair=pairs.at(step.index);e.set_class(pair.original->label);e.last_site=&pair.original->label;auto event=e.dev(0).issue(pair.commands.at(0));e.finish(0,{event,event,1},true);++e.logical;++issued;++cursor;continue;}
    unsigned row=step.row;Scope selected(e,banks[row]);do{e.enqueue(e.p.launches.at(steps[cursor].index),e.logical);++cursor;}while(cursor<steps.size()&&steps[cursor].kind==StepKind::site&&steps[cursor].row==row);
   }
   need(issued==70,"p212 exact paired issue count");e.drain();boundary();auto routes=e.prefill_interval->finish();e.fill_cache(routes);e.prefill_interval->committed();
   // Canonical publication is ordered, not atomic. Failure poisons the owner;
   // there is no serial fallback or partial-chunk checkpoint.
   ownrt::CopyEngine copy(e.dev(0));for(const auto&name:std::array<std::string,2>{"streams","token"}){const auto&to=e.buffers[0].at(name);const auto&from=banks[1].buffers.at(name);e.tail=copy.copy(to.id,0,from.id,0,to.n*flash::scalar_bytes(to.type),{});}e.drain();uint32_t position=uint32_t(start+2);e.put(0,"position",&position,4);e.drain();auto raw=e.readback(0,e.buffers[0].at("token_history").id,16);std::array<int64_t,2> native{};std::memcpy(native.data(),raw.data(),16);need(native==std::array<int64_t,2>{final0,final1},"p212 staged/native PLE history");e.history0=final0;e.history1=final1;e.fp32_sources[0]=0;e.fp32_extents[0]=0;boundary();progress("complete",start,issued,start+2,std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count());running=false;
  }catch(...){e.history0=old0;e.history1=old1;e.poisoned=true;if(e.prefill_interval)e.prefill_interval->poison();running=false;throw;}
 }
};
} // namespace p212
