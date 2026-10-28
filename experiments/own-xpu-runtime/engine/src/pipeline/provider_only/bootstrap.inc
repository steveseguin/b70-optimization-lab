// Included after Engine, DraftRuntime and the existing socket helpers.
// This process has a provider role, no target stage and no target-layer plan.
#include "pipeline/provider_only/runtime.hpp"
static int run_provider_only(const Options& a) {
 using namespace pipeline;
 std::unique_ptr<Weights> weights;
 std::unique_ptr<Engine> engine;
 std::unique_ptr<mtp36::DraftRuntime> draft;
 int fd=-1;void* mapping=MAP_FAILED;
 std::string error;std::vector<std::string> teardown;
 pipeline_stop_fd=a.stop_fd;
 try {
  require(a.provider_only&&!a.pipeline_enabled(),"explicit dedicated provider bootstrap");
  fd=::open(a.shared.c_str(),O_RDWR|O_NOFOLLOW);
  require(fd>=0,"provider shared open");struct stat st{};
  require(!fstat(fd,&st)&&st.st_size==shared_bytes,"provider shared extent");
  mapping=mmap(nullptr,shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
  require(mapping!=MAP_FAILED,"provider shared mmap");
  weights=std::make_unique<Weights>(a);
  auto shell=plan(*weights,a); // Geometry and model identity, never target execution.
  shell.launches.clear();
  std::erase_if(shell.buffers,[](const auto& b){
   return b.name!="error"&&b.name!="active"&&b.name!="position"&&b.name!="token";
  });
  require(shell.buffers.size()==4,"provider shell control inventory");
  for(auto& b:shell.buffers){require(count(b.shape)==1,"provider scalar control");b.card=0;}
  dump_plan(a.output/"launch-plan.json",shell);
  write_plan(a.output/"plan.json",shell,*weights,1,a);
  if(const char* only=std::getenv("OWNRT_PLAN_ONLY");only&&std::string(only)=="1") {
   save(a.output/"plan-only.json","{\"role\":\"dedicated-mtp\",\"device_contact\":false}");
  }else{
   record_host_memory(a.output,"before_load");
   engine=std::make_unique<Engine>(*weights,a,std::move(shell));
   require(!engine->v3_active&&!engine->kio_active&&!engine->prepare_async&&!engine->split_head(),
           "provider-only refuses target-specific optional runtime");
   engine->initialize();
   require(engine->weights.size()==1&&engine->weights[0].empty()&&engine->p.launches.empty()&&engine->state_spares.empty(),
           "provider-only must not allocate target weights or state banks");
   draft=std::make_unique<mtp36::DraftRuntime>(*engine);
   require(draft->recursive_image&&draft->recursive_healthy(),"provider recursive initialization");
   engine->bracket_weights_locked=true;
   save(a.output/"census.json",engine->dev(0).arena.census());
   save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());
   record_host_memory(a.output,"after_load");
   ownrt::provider_only::run_loop(*engine,*draft,a,static_cast<uint8_t*>(mapping));
  }
 }catch(const std::exception& ex){
  error=ex.what();
  try{save(a.output/"failure.txt",error+"\n");
      save(a.output/"receipt.json","{\"role\":\"dedicated-mtp\",\"passed\":false,\"teardown_pending\":true,\"error\":"+ownrt::quote(error)+"}");}
  catch(const std::exception& record){error+="; failure evidence: "+std::string(record.what());}
 }
 if(engine)engine->progress_callback={};
 draft.reset();
 if(engine){try{teardown=engine->shutdown();}catch(const std::exception& ex){error+=(error.empty()?"":"; ")+std::string(ex.what());}engine.reset();}
 weights.reset();
 if(mapping!=MAP_FAILED)munmap(mapping,shared_bytes);
 if(fd>=0)::close(fd);
 std::ostringstream receipt;
 receipt<<"{\"schema\":\"ownrt.dedicated-provider-process.v1\",\"role\":\"dedicated-mtp\",\"passed\":"
   <<(error.empty()?"true":"false")<<",\"error\":"<<ownrt::quote(error)<<",\"target_stage\":null,\"teardown\":[";
 for(size_t i=0;i<teardown.size();++i)receipt<<(i?",":"")<<teardown[i];
 receipt<<"]}";save(a.output/"receipt.json",receipt.str());
 return error.empty()?0:1;
}
