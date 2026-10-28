// Actual Host Engine bank publication, checked snapshot rollback and request
// reset. No model weights, arithmetic kernels, SYCL runtime or device opens.
#include "checkpoint_fixture.hpp"
int main(int argc,char** argv){
 setenv("OMP_NUM_THREADS","2",1);assert(argc==2);const auto root=fs::absolute(argv[1]);assert(fs::create_directory(root));
 Options args;args.mini=true;args.cards=1;args.card=0;args.rank=0;args.memory="resident";args.context=2048;args.retain_steps.ranges.clear();args.reset_dump=false;args.finish_dump=false;args.pipeline_stage=0;args.pipeline_boundaries={0,1,2};args.pipeline_ring=args.pipeline_ring_persistent_requests=true;args.pipeline_ring_depth=3;args.output=root/"owner";fs::create_directory(args.output);
 Weights weights(args);flash::Plan plan;plan.g=Geometry::tiny();plan.g.context=2048;
 for(auto name:{"position","error","token","active","next_token"})plan.buffers.push_back({name,{1},flash::Scalar::i32,0});
 plan.buffers.push_back({"streams",{plan.g.h*4},flash::Scalar::bf16,0});plan.buffers.push_back({"bank-test-state",{8},flash::Scalar::f32,0});
 Engine e(weights,args,plan);e.initialize();e.release(0,e.scratch[0]);e.scratch[0]=e.allocate(0,"bank-test-operator-scratch",4096,Category::scratch,Lifetime::transaction);
 const auto first=e.buffers[0].at("bank-test-state").id;const auto second=e.allocate(0,"alternate:bank-test-state",32,Category::recurrent,Lifetime::request);e.state_spares["bank-test-state"]=second;e.a.prefill_rows=256;
 auto fill=[&](Allocation id,uint8_t value){std::array<uint8_t,32> bytes;bytes.fill(value);e.upload(0,id,0,bytes.data(),bytes.size());};fill(first,0);fill(second,0);
 pipeline::ring_next::CheckpointRingFor<Engine> checkpoint(e,true,{});std::array<uint8_t,pipeline::slot_bytes> shared{};
 // The fourth real suite prompt used an even88-row native chunk. Include odd,
 // full, multi-chunk partial tail, replayed and mixed recurrence publications.
 const std::vector<std::vector<std::pair<int,bool>>> cases={{{88,true}},{{65,true}},{{256,true}},{{256,true},{3,true}},{{256,false}},{{3,false}},{{88,true},{65,false}},{{256,true},{256,true},{88,true}}};
 int request=0;
 for(const auto& chunks:cases){
  int position=0;Allocation expected=first,spare=second;uint8_t value=0;
  for(const auto& [rows,native]:chunks){
   // Independently model where the unchanged recurrences write: a native
   // chunk publishes its final row to spare once; replay alternates per row.
   if(native){value=uint8_t(position+rows);fill(spare,value);std::swap(expected,spare);}
   else for(int i=0;i<rows;++i){value=uint8_t(position+i+1);fill(spare,value);std::swap(expected,spare);}
   e.prefill_finish_banks(rows,native,!native);position+=rows;e.put(0,"position",&position,4);
   assert(e.buffers[0].at("bank-test-state").id==expected&&e.state_spares.at("bank-test-state")==spare);
   const auto bytes=e.readback(0,expected,32);assert(std::all_of(bytes.begin(),bytes.end(),[&](auto x){return x==value;}));
   assert(e.bank_parity==e.ring_expected_bank_parity(position));
  }
  const unsigned bias=e.prefill_bank_parity_bias;const auto before=e.readback(0,expected,32);const int slot=checkpoint.capture(shared.data());
  for(int i=0;i<3;++i){fill(e.state_spares.at("bank-test-state"),uint8_t(++value));e.swap_state_banks();++position;e.put(0,"position",&position,4);assert(e.bank_parity==e.ring_expected_bank_parity(position));}
  checkpoint.restore(slot);checkpoint.release(slot);position-=3;
  assert(e.integer(0,"position")==position&&e.prefill_bank_parity_bias==bias&&e.bank_parity==e.ring_expected_bank_parity(position));
  assert(e.buffers[0].at("bank-test-state").id==expected&&e.readback(0,expected,32)==before);
  // Accounting must still reject a genuinely wrong physical parity bit.
  e.bank_parity^=1;assert(e.bank_parity!=e.ring_expected_bank_parity(position));e.bank_parity^=1;
  pipeline::Candidate candidate;pipeline::request_reset(e,candidate,nullptr,{},0,std::pair<fs::path,std::string>{root/("reset-"+std::to_string(request++)),""});checkpoint.reset_after_owner_zero();
  assert(!e.prefill_bank_parity_bias&&!e.bank_parity&&!e.integer(0,"position")&&e.buffers[0].at("bank-test-state").id==first);
  for(auto id:{first,second}){const auto bytes=e.readback(0,id,32);assert(std::all_of(bytes.begin(),bytes.end(),[](auto x){return x==0;}));}
 }
 refusal([&]{e.prefill_finish_banks(0,true,false);});refusal([&]{e.prefill_finish_banks(257,true,false);});refusal([&]{e.prefill_finish_banks(1,true,true);});
 e.drain();e.shutdown();std::cout<<"PASS actual Host Engine native/replayed even/odd/full/partial bank publication, scalar steps, depth3 checked rollback, wrong-parity detection, and request-local reset; CPU only\n";
}
