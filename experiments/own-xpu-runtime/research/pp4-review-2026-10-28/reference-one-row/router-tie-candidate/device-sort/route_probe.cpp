// Includes the complete pinned adapter overlay: original and treatment classes.
#include "adapter.cpp"
#include <fstream>
#include <filesystem>
#include <iostream>
#include <atomic>
#include <bit>
#include <numeric>
namespace ownrt {uint64_t next_handle(){static std::atomic<uint64_t>n{1};return n++;}}
namespace packet18 { namespace {
#include "route-capture-classes.inc"
}}
constexpr int rows=64,width=512;
static void need(bool b,const char* why){if(!b)throw std::runtime_error(why);}
static void save(const std::filesystem::path& p,const std::vector<uint32_t>& a){std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(a.data()),a.size()*4);need(bool(f),"artifact write");}
struct Output{std::vector<uint32_t> words,probability;uint32_t error;};
struct Harness {
 sycl::queue& q;
 uint32_t* arena;
 static constexpr size_t units=rows*width+2 + rows*80+8 + rows*width+2 + 8;
 static constexpr size_t bytes=units*4;
 size_t next=0;
 std::array<void*,10> bindings{};
 std::array<size_t,4> counts{},offsets{};
 uint32_t* captured;
 integrated::Spec spec;
 std::vector<size_t> guards;
 explicit Harness(sycl::queue& queue):q(queue){arena=sycl::malloc_device<uint32_t>(units,q);need(arena,"bounded route arena allocation");}
 ~Harness(){sycl::free(arena,q);}
 uint32_t* alloc(size_t count){need(next+count+2<=units,"arena extent");guards.push_back(next);guards.push_back(next+count+1);auto* p=arena+next+1;next+=count+2;return p;}
 void configure(int outputs,int batch){
  next=0;guards.clear();spec={};spec.op=integrated::Op::route;spec.special=integrated::Special::normal;
  spec.implementation=1;spec.f32_activations=true;spec.ni=1;spec.no=outputs;spec.nw=0;
  spec.tokens=batch;spec.site.shape[1]=10;spec.g.top=10;spec.g.mid=640;spec.g.h=2560;
  spec.sizes[0]=width;spec.types[0]=integrated::Scalar::f32;spec.row_bytes[0]=width*4;
  bindings.fill(nullptr);bindings[0]=alloc(rows*width);
  for(int k=0;k<outputs;++k){counts[k]=k<2?10:30;spec.sizes[k+1]=counts[k];spec.row_bytes[k+1]=counts[k]*4;spec.types[k+1]=k==1?integrated::Scalar::f32:integrated::Scalar::i32;bindings[k+1]=alloc(rows*counts[k]);offsets[k]=static_cast<uint32_t*>(bindings[k+1])-arena;}
  captured=alloc(rows*width);
  const int tail=1+outputs;
  need(next+5<=units,"controls extent");for(int k=0;k<5;++k)bindings[tail+k]=arena+next++;
  bindings[tail]=captured; // Original route never uses scratch; capture adds no kernel argument.
 }
 template<bool Merge> Output run(const std::vector<uint32_t>& input,int outputs,int batch,int variant,uint32_t active=1,uint32_t error=0){
  configure(outputs,batch);
  q.memset(arena,0xa5,bytes);q.memcpy(bindings[0],input.data(),input.size()*4);
  const int tail=1+outputs;const uint32_t position=177;
  q.memcpy(bindings[tail+1],&error,4);q.memcpy(bindings[tail+2],&position,4);q.memcpy(bindings[tail+3],&active,4);q.wait_and_throw();
  std::span<void*const> binding_span(bindings.data(),tail+5);
  if(variant==0){packet18::RouteFast2<512,10,Merge> operation(spec);operation.submit(q,binding_span,{}).wait_and_throw();}
  if(variant==1){packet18::RouteOriginalCapture2<512,10,Merge> operation(spec);operation.submit(q,binding_span,{}).wait_and_throw();}
  if(variant==2){packet18::RouteReferenceTie2<512,10,Merge> operation(spec);operation.submit(q,binding_span,{}).wait_and_throw();}
  if(variant==3){packet18::RouteReferenceCapture2<512,10,Merge> operation(spec);operation.submit(q,binding_span,{}).wait_and_throw();}
  std::vector<uint32_t> all(units);q.memcpy(all.data(),arena,bytes).wait_and_throw();
  for(size_t at:guards)need(all[at]==0xa5a5a5a5,"device arena canary");
  const size_t input_at=static_cast<uint32_t*>(bindings[0])-arena;
  need(std::equal(input.begin(),input.end(),all.begin()+input_at),"native input unchanged");
  Output out;out.error=all[static_cast<uint32_t*>(bindings[tail+1])-arena];
  for(int k=0;k<outputs;++k)out.words.insert(out.words.end(),all.begin()+offsets[k],all.begin()+offsets[k]+rows*counts[k]);
  const size_t prob_at=captured-arena;out.probability.assign(all.begin()+prob_at,all.begin()+prob_at+rows*width);
  return out;
 }
};
template<bool Merge> size_t gate(Harness& h,const std::vector<uint32_t>& input,const std::filesystem::path& out,int outputs){
 const auto original=h.run<Merge>(input,outputs,rows,0);
 const auto original_capture=h.run<Merge>(input,outputs,rows,1);
 const auto treatment=h.run<Merge>(input,outputs,rows,2);
 const auto treatment_capture=h.run<Merge>(input,outputs,rows,3);
 need(!original.error&&!original_capture.error&&!treatment.error&&!treatment_capture.error,"valid route status");
 need(original.words==original_capture.words&&treatment.words==treatment_capture.words,"capture output neutrality");
 need(original_capture.probability==treatment_capture.probability,"all 512 native probability words unchanged");
 size_t changed=0;
 for(int row=0;row<rows;++row){
  std::array<float,width> probabilities;for(int j=0;j<width;++j)probabilities[j]=std::bit_cast<float>(original_capture.probability[row*width+j]);
  std::array<int,width> reference;std::iota(reference.begin(),reference.end(),0);
  std::sort(reference.begin(),reference.end(),[&](int a,int b){return probabilities[a]>probabilities[b];});
  for(int rank=0;rank<10;++rank){
   const int old=int(original.words[row*10+rank]),next=int(treatment.words[row*10+rank]);
   need(next==reference[rank],"actual reference ID permutation");
   need(original.words[rows*10+row*10+rank]==treatment.words[rows*10+row*10+rank],"selected weight bits unchanged");
   if(old!=next){++changed;need(input[row*width+old]==input[row*width+next],"changed ID exact raw score words");}
   if(outputs==4)for(int route=0;route<2;++route)for(int c=0;c<3;++c){
    const size_t at=rows*20+route*rows*30+row*30+rank*3+c;
    need(c==0?treatment.words[at]==uint32_t(next):treatment.words[at]==original.words[at],"fused route fields");
   }
  }
 }
 const std::string name=std::string(Merge?"merge":"guard")+"-outputs"+std::to_string(outputs);
 save(out/(name+"-original.bin"),original.words);save(out/(name+"-treatment.bin"),treatment.words);
 save(out/(name+"-native-probabilities.f32"),original_capture.probability);
 return changed;
}
int main(int argc,char** argv){try{
 need(argc==3,"input64x512.f32 fresh-output");
 const char* bdf=std::getenv("FilterBdfPath");const char* enabled=std::getenv("OWNRT_REFERENCE_ROUTE_PROBE");
 need(bdf&&enabled&&std::string(enabled)=="1","explicit device and probe admission");
 std::vector<uint32_t> input(rows*width);std::ifstream f(argv[1],std::ios::binary);
 f.read(reinterpret_cast<char*>(input.data()),input.size()*4);need(f.gcount()==input.size()*4&&f.peek()==EOF,"exact input extent");
 for(auto word:input)need(std::isfinite(std::bit_cast<float>(word)),"finite input");
 std::filesystem::path output=argv[2];need(std::filesystem::create_directory(output),"fresh output");
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order()});auto device=q.get_device();
 need(device.has(sycl::aspect::ext_intel_pci_address),"PCI identity capability");need(device.get_info<sycl::ext::intel::info::device::pci_address>()==bdf,"physical BDF mismatch");
 std::cout<<"bdf="<<bdf<<" explicit_device_bytes="<<Harness::bytes<<"\n"<<std::flush;
 Harness h(q);size_t changed=0;
 for(int outputs:{2,4}){changed+=gate<true>(h,input,output,outputs);changed+=gate<false>(h,input,output,outputs);}
 // Uniform inactive and pre-existing-error workgroups leave every output untouched.
 for(int treatment:{0,2})for(int mode:{0,1}){
  auto value=h.run<true>(input,4,rows,treatment,mode?1:0,mode?1:0);
  need(value.error==uint32_t(mode),"guard state unchanged");for(auto word:value.words)need(word==0xa5a5a5a5,"inactive/error outputs untouched");
 }
 // Signed-zero logits have equal probabilities but differing raw words: refuse.
 auto refusal=input;for(int j=0;j<width;++j)refusal[j]=0;refusal[336]=0x80000000;
 auto rejected=h.run<true>(refusal,4,1,2);need(rejected.error==1,"distinct raw equal probability refuses");
 auto poisoned=input;poisoned[13]=0x7fc00000;
 auto nonfinite=h.run<true>(poisoned,4,1,2);need(nonfinite.error==1,"nonfinite refuses");
 for(auto word:nonfinite.words)need(word==0xa5a5a5a5,"nonfinite outputs untouched");
 std::ofstream result(output/"result.json");result<<"{\"passed\":true,\"rows\":64,\"merge_modes\":2,\"output_geometries\":2,\"changed_slots_all_modes\":"<<changed<<",\"native_probabilities_exact\":true,\"native_weights_exact\":true,\"capture_neutral\":true,\"distinct_raw_probability_tie_refused\":true,\"inactive_and_error_guards\":true,\"explicit_device_bytes\":"<<Harness::bytes<<",\"speed_claim\":false}\n";
 need(bool(result),"result write");
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 3;}}
