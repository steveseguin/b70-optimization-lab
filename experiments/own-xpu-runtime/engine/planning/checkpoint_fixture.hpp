#pragma once
// CPU-only: actual checkpoint class + checked Device/CopyEngine/SnapshotFlat,
// injected small owner metadata. No model files, device API or SYCL runtime.
#define main unused_wavefront_native_entry
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp"
#undef main
#include <cassert>
struct FixtureOwner {
 struct Options {bool pipeline_wavefront=true,mtp=false,pipeline_live_draft=false,pipeline_draft_partition=false,pipeline_persistent_requests=false,pipeline_ring_persistent_requests=false,pipeline_ring_recursive_flat_copy=false;int prefill_rows=0,pipeline_stage=0,pipeline_provider_stage=0,pipeline_ring_depth=2;fs::path output;bool pipeline_enabled()const{return true;}bool pipeline_provider()const{return pipeline_stage==pipeline_provider_stage;}bool pipeline_first()const{return pipeline_stage==0;}} a;
 struct Buffer {Allocation id;};
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
 explicit FixtureOwner(const fs::path& output){a.output=output;fs::create_directory(output);}
 ownrt::Device& dev(int c){assert(c==0);return *device;}
 Allocation allocate(int c,const std::string& name,size_t n,Category category,Lifetime life,Memory memory=Memory::device){auto id=dev(c).arena.allocate("card0:"+name,n,memory,category,life);if(memory==Memory::device)allocations[id]={c,n};all_owned.push_back(id);std::memset(dev(c).arena.row(id).pointer,0,n);return id;}
 size_t stream_bytes()const{return 16;}
 void upload(int c,Allocation id,size_t offset,const void* source,size_t n){auto& row=dev(c).arena.row(id);assert(offset+n<=row.bytes);std::memcpy(static_cast<uint8_t*>(row.pointer)+offset,source,n);}
 void drain(){if(tail){assert(dev(0).wait(tail,std::chrono::seconds(5)));tail=0;}}
 std::vector<uint8_t> readback(int c,Allocation id,size_t n){drain();auto& row=dev(c).arena.row(id);assert(n<=row.bytes);auto p=static_cast<uint8_t*>(row.pointer);return {p,p+n};}
 int integer(int c,const std::string& name){int value;auto b=readback(c,buffers[c].at(name).id,4);std::memcpy(&value,b.data(),4);return value;}
 void put(const std::string& name,int n){upload(0,buffers[0].at(name).id,0,&n,4);}
 void admit_position(int n){context_extent=((n+32)/32)*32;}
 void swap_state_banks(){for(auto& [name,id]:state_spares)std::swap(buffers[0].at(name).id,id);std::swap(active_bank,spare_bank);std::swap(context_extent,alternate_context_extent);bank_parity^=1;fp32_sources[0]=0;fp32_extents[0]=0;}
 void close(){drain();for(auto id:all_owned)dev(0).arena.release(id);auto receipt=dev(0).shutdown(std::chrono::seconds(5));assert(receipt.safe_to_exit);}
};
template<class F>void refusal(F f){bool got=false;try{f();}catch(const std::exception&){got=true;}assert(got);}
