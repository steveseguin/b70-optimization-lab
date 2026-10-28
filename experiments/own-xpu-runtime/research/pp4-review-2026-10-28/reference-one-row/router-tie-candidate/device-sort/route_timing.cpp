// Verbatim prefix of the gated route_probe.cpp, excluding its main function.
#include "route-probe-harness.inc"
#include <iomanip>
struct Timing {int batch;std::vector<uint64_t> original,candidate;};
static double median(std::vector<uint64_t> values){std::sort(values.begin(),values.end());return (double(values[values.size()/2-1])+values[values.size()/2])/2;}
static Timing measure(Harness& h,const std::vector<uint32_t>& input,int batch){
 const auto original=h.run<true>(input,4,batch,0);
 const auto candidate=h.run<true>(input,4,batch,2);
 need(!original.error&&!candidate.error,"timing setup status");
 Timing result;result.batch=batch;
 std::span<void*const> bindings(h.bindings.data(),10);
 for(int iteration=-4;iteration<32;++iteration){
  for(int which=0;which<2;++which){
   const bool treatment=bool((iteration&1)^which);
   sycl::event event;
   if(treatment){packet18::RouteReferenceTie2<512,10,true> op(h.spec);event=op.submit(h.q,bindings,{});}
   else{packet18::RouteFast2<512,10,true> op(h.spec);event=op.submit(h.q,bindings,{});}
   event.wait_and_throw();
   const auto start=event.get_profiling_info<sycl::info::event_profiling::command_start>();
   const auto end=event.get_profiling_info<sycl::info::event_profiling::command_end>();
   need(end>=start,"profiling monotonic");
   if(iteration>=0)(treatment?result.candidate:result.original).push_back(end-start);
  }
 }
 // The final odd pair ends with the original route; verify its complete output.
 std::vector<uint32_t> state(Harness::units);h.q.memcpy(state.data(),h.arena,Harness::bytes).wait_and_throw();
 for(size_t at:h.guards)need(state[at]==0xa5a5a5a5,"timed arena canary");
 need(state[static_cast<uint32_t*>(h.bindings[6])-h.arena]==0,"timed status");
 const size_t first=static_cast<uint32_t*>(h.bindings[0])-h.arena;
 need(std::equal(input.begin(),input.end(),state.begin()+first),"timed input unchanged");
 std::vector<uint32_t> output;
 for(int k=0;k<4;++k)output.insert(output.end(),state.begin()+h.offsets[k],state.begin()+h.offsets[k]+rows*h.counts[k]);
 need(output==original.words,"timed output retained correctness");
 return result;
}
static void emit(std::ostream& f,const std::vector<uint64_t>& values){f<<'[';for(size_t i=0;i<values.size();++i){if(i)f<<',';f<<values[i];}f<<']';}
int main(int argc,char** argv){try{
 need(argc==3,"input64x512.f32 fresh-output");
 const char* bdf=std::getenv("FilterBdfPath");const char* enabled=std::getenv("OWNRT_REFERENCE_ROUTE_TIMING");
 need(bdf&&enabled&&std::string(enabled)=="1","explicit device and timing admission");
 std::vector<uint32_t> input(rows*width);std::ifstream f(argv[1],std::ios::binary);
 f.read(reinterpret_cast<char*>(input.data()),input.size()*4);need(f.gcount()==input.size()*4&&f.peek()==EOF,"exact input extent");
 for(auto word:input)need(std::isfinite(std::bit_cast<float>(word)),"finite input");
 std::filesystem::path output=argv[2];need(std::filesystem::create_directory(output),"fresh output");
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()});
 auto device=q.get_device();need(device.has(sycl::aspect::ext_intel_pci_address),"PCI identity capability");
 need(device.get_info<sycl::ext::intel::info::device::pci_address>()==bdf,"physical BDF mismatch");
 std::cout<<"bdf="<<bdf<<" explicit_device_bytes="<<Harness::bytes<<"\n"<<std::flush;
 Harness h(q);const auto captured=h.run<true>(input,4,rows,1);need(!captured.error,"native selection status");
 int chosen=-1;
 for(int row=0;row<48&&chosen<0;++row){
  bool tie=false;
  for(int k=0;k<10;++k){const int selected=int(captured.words[row*10+k]);const float value=std::bit_cast<float>(captured.probability[row*width+selected]);
   for(int j=0;j<width;++j)if(j!=selected&&value==std::bit_cast<float>(captured.probability[row*width+j]))tie=true;
  }
  if(!tie)chosen=row;
 }
 need(chosen>=0,"actual native row without selected ties");
 std::vector<uint32_t> untied(rows*width),all_tied(rows*width,0);
 for(int row=0;row<rows;++row)std::copy_n(input.begin()+chosen*width,width,untied.begin()+row*width);
 std::ofstream result(output/"result.json");result<<std::setprecision(12);
 result<<"{\"schema\":\"ownrt.reference-route-event-timing.v1\",\"passed\":true,\"native_untied_layer\":"<<chosen<<",\"iterations_per_variant\":32,\"warmup_pairs\":4,\"explicit_device_bytes\":"<<Harness::bytes<<",\"microkernel_only\":true,\"endpoint_speed_claim\":false,\"scenarios\":[";
 int count=0;
 for(const auto& [name,pattern]:std::array<std::pair<const char*,const std::vector<uint32_t>*>,2>{{{"native-untied",&untied},{"all-equal-stress",&all_tied}}}){
  const auto directory=output/name;std::filesystem::create_directory(directory);
  gate<true>(h,*pattern,directory,4); // Matched compiled capture/oracle gate before timing.
  for(int batch:{1,64}){
   const auto timed=measure(h,*pattern,batch);if(count++)result<<',';
   result<<"{\"case\":\""<<name<<"\",\"rows\":"<<batch<<",\"original_ns\":";emit(result,timed.original);
   result<<",\"candidate_ns\":";emit(result,timed.candidate);
   result<<",\"original_median_ns\":"<<median(timed.original)<<",\"candidate_median_ns\":"<<median(timed.candidate)<<",\"candidate_over_original\":"<<median(timed.candidate)/median(timed.original)<<'}';
  }
 }
 result<<"]}\n";need(bool(result),"timing result write");
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 3;}}
