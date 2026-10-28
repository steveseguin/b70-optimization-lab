#pragma once
// CPU-only: actual checkpoint class + checked Device/CopyEngine/SnapshotFlat,
// injected small owner metadata. No model files, device API or SYCL runtime.
#define main unused_wavefront_native_entry
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp"
#undef main
#include <cassert>
struct FixtureOwner {
 struct Options {bool pipeline_wavefront=true,mtp=false,pipeline_live_draft=false,pipeline_draft_partition=false,pipeline_persistent_requests=false,pipeline_ring_persistent_requests=false,pipeline_ring_recursive_flat_copy=false;int prefill_rows=0,pipeline_stage=0,pipeline_provider_stage=0,pipeline_ring_depth=2;fs::path output;bool pipeline_enabled()const{return true;}bool pipeline_provider()const{return pipeline_stage==pipeline_provider_stage;}bool pipeline_first()const{return pipeline_stage==0;}} a;
 struct Buffer {Allocation id;};flash::Plan p;size_t max_readback_bytes=0;
 std::unique_ptr<ownrt::Device> device=std::make_unique<ownrt::Device>(std::make_unique<Host>());
 bool resident=true,poisoned=false,progress_pending=false,prepare_async=false;
 std::function<void()> progress_callback,correction_exchange,head_export,head_publish,head_merge;
 struct Reports {bool pending()const{return false;}} reply_report;
 std::map<Allocation,std::pair<int,size_t>> allocations;std::vector<Allocation> all_owned;
 std::vector<std::map<std::string,Buffer>> buffers{1};std::map<std::string,Allocation> state_spares;
 unsigned bank_parity=0;int active_bank=0,spare_bank=1,context_extent=32,alternate_context_extent=32;
 int64_t history0=0,history1=0;
 std::map<std::string,std::vector<uint8_t>> lookup_ids;
 std::vector<std::vector<uint32_t>> selected{{1,2}};
 std::vector<int> loaded_layer{-1};std::vector<Allocation> fp32_sources{0};std::vector<size_t> fp32_extents{0};
 ownrt::Event tail=0;
 explicit FixtureOwner(const fs::path& output){a.output=output;p.g.context=64;fs::create_directory(output);}
 ownrt::Device& dev(int c){assert(c==0);return *device;}
 Allocation allocate(int c,const std::string& name,size_t n,Category category,Lifetime life,Memory memory=Memory::device){auto id=dev(c).arena.allocate("card0:"+name,n,memory,category,life);if(memory==Memory::device)allocations[id]={c,n};all_owned.push_back(id);std::memset(dev(c).arena.row(id).pointer,0,n);return id;}
 std::array<Allocation,4> add_qsa(const std::string& prefix="blk.0.qsa",size_t key_row=16,size_t raw_row=4){
  std::array<Allocation,4> ids{};std::array<size_t,4> rows{key_row,key_row,raw_row,raw_row};
  for(int i=0;i<4;++i){const std::string suffix=i==0?".keys":i==1?".values":i==2?".raw":".pooled";const std::string name=prefix+suffix;const size_t count=i==3?size_t((p.g.context+3)/4):size_t(p.g.context);const size_t bytes=rows[size_t(i)]*count;
   ids[size_t(i)]=allocate(0,name,bytes,Category::kv,Lifetime::request);buffers[0][name]={ids[size_t(i)]};p.buffers.push_back({name,{int(count),int(rows[size_t(i)]/2)},Scalar::bf16,0});
  }
  p.launches.push_back({"qsa_append_pool",prefix+".append",{},{prefix+".keys",prefix+".values",prefix+".raw",prefix+".pooled"},{},{}});return ids;
 }
 std::array<Allocation,4> add_builder_qsa(){
  auto geometry=Geometry::tiny();geometry.context=p.g.context;flash::Builder builder(geometry);p=builder.build({true,true},true);std::erase_if(p.launches,[](const auto& launch){return launch.label.starts_with("blk.1.qsa.");});std::array<Allocation,4> ids{};bool recurrent=false;
  for(const auto& b:p.buffers){int i=b.name.ends_with(".qsa.keys")?0:b.name.ends_with(".qsa.values")?1:b.name.ends_with(".qsa.raw")?2:b.name.ends_with(".qsa.pooled")?3:-1;size_t elements=1;for(int d:b.shape)elements*=size_t(d);if(i>=0&&b.name.starts_with("blk.0.")){ids[size_t(i)]=allocate(0,b.name,elements*flash::scalar_bytes(b.type),Category::kv,Lifetime::request);buffers[0][b.name]={ids[size_t(i)]};}else if(b.name.ends_with(".ple.history")){auto id=allocate(0,b.name,elements*flash::scalar_bytes(b.type),Category::kv,Lifetime::request);buffers[0][b.name]={id};recurrent=true;}}
  for(auto id:ids)assert(id);assert(recurrent);return ids;
 }
 size_t stream_bytes()const{return 16;}
 void upload(int c,Allocation id,size_t offset,const void* source,size_t n){auto& row=dev(c).arena.row(id);assert(offset+n<=row.bytes);std::memcpy(static_cast<uint8_t*>(row.pointer)+offset,source,n);}
 void drain(){if(tail){assert(dev(0).wait(tail,std::chrono::seconds(5)));tail=0;}}
 std::vector<uint8_t> readback_range(int c,Allocation id,size_t offset,size_t n){drain();auto& row=dev(c).arena.row(id);assert(offset<=row.bytes&&n<=row.bytes-offset);max_readback_bytes=std::max(max_readback_bytes,n);auto p=static_cast<uint8_t*>(row.pointer)+offset;return {p,p+n};}
 std::vector<uint8_t> readback(int c,Allocation id,size_t n){return readback_range(c,id,0,n);}
 int integer(int c,const std::string& name){int value;auto b=readback(c,buffers[c].at(name).id,4);std::memcpy(&value,b.data(),4);return value;}
 void put(const std::string& name,int n){upload(0,buffers[0].at(name).id,0,&n,4);}
 void admit_position(int n){context_extent=((n+32)/32)*32;}
 void swap_state_banks(){for(auto& [name,id]:state_spares)std::swap(buffers[0].at(name).id,id);std::swap(active_bank,spare_bank);std::swap(context_extent,alternate_context_extent);bank_parity^=1;fp32_sources[0]=0;fp32_extents[0]=0;}
 void close(){drain();for(auto id:all_owned)dev(0).arena.release(id);auto receipt=dev(0).shutdown(std::chrono::seconds(5));assert(receipt.safe_to_exit);}
};
template<class F>void refusal(F f){bool got=false;try{f();}catch(const std::exception&){got=true;}assert(got);}
