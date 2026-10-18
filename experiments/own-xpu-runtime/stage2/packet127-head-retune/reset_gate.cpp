// CPU only. Uses the frozen production argmax, pack and merge implementations.
// reset_fragment.inc and service_*.inc are extracted verbatim by cpu_gate.py.
#include "round2_submit.cpp"
#include "p105_submit.cpp"
#include <iostream>
#include <map>
#include <string>
#include <vector>

using ownrt::Allocation;
using ownrt::Category;
struct Row {
  bool live=true;
  Category category=Category::runtime_overhead;
  size_t bytes=4;
  std::vector<uint8_t> data=std::vector<uint8_t>(4);
};
struct Arena {
  std::map<Allocation,Row> rows;
  Row& row(Allocation id){return rows.at(id);}
};
struct Device {Arena arena;};
struct Engine {
  Device device;
  std::map<Allocation,std::pair<int,int>> allocations;
  std::vector<std::map<std::string,Allocation>> buffers{1};
  std::vector<Allocation> one{1};
  struct {int cards=1;} a;
  struct {struct {int eos=248044;} g;} p;
  std::vector<int64_t> metadata;
  Engine(){
    for(Allocation id=1;id<=7;++id){device.arena.rows.emplace(id,Row{});allocations[id]={0,0};}
    buffers[0]["active"]=2;
  }
  Device& dev(int){return device;}
  void upload(int,Allocation id,size_t off,const void* data,size_t n){
    auto& r=device.arena.row(id);
    if(off+n>r.bytes)throw std::runtime_error("CPU upload extent");
    std::memcpy(r.data.data()+off,data,n);
  }
  void put(int card,const std::string& name,const void* data,size_t n){upload(card,buffers[card].at(name),0,data,n);}
  uint32_t value(Allocation id){uint32_t v;std::memcpy(&v,device.arena.row(id).data.data(),4);return v;}
};
static void reset(Engine& e){
#include "reset_fragment.inc"
}
static void original_service(Engine& e,Allocation error,Allocation active){
#include "service_original.inc"
}
static void fixed_service(Engine& e,Allocation error,Allocation active){
#include "service_fixed.inc"
}
static p105::Best reduce(const std::vector<uint16_t>& logits,unsigned off,uint32_t active,int32_t& index,uint32_t& error){
  integrated::Spec s;
  s.op=integrated::Op::argmax;s.ni=1;s.no=1;s.sizes[0]=logits.size();s.sizes[1]=1;
  s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
  uint32_t position=0;
  std::vector<float> scratch(2*((logits.size()+1023)/1024),0);
  std::array<void*,7> ids{const_cast<uint16_t*>(logits.data()),&index,scratch.data(),&error,&position,&active,&position};
  round2::Simple<integrated::Op::argmax,0,flash::Scalar::bf16>(s).run(ids);
  round2::Simple<integrated::Op::argmax,1,flash::Scalar::bf16>(s).run(ids);
  p105::Best best{};
  p105::Pack pack;pack.rows=logits.size();pack.offset=off;
  std::array<void*,4> bound{const_cast<uint16_t*>(logits.data()),&index,&error,&best};
  pack.run(bound);return best;
}
static void require(bool condition,const char* why){if(!condition)throw std::runtime_error(why);}
int main(int argc,char**argv){try{
  require(argc==2,"suffix argument");const unsigned suffix=std::stoul(argv[1]),boundary=p105::vocab-suffix;require(suffix==46080||suffix==81920||suffix==122880,"registered suffix");
  constexpr Allocation suffix_active=3,suffix_error=4;
  unsigned cases=0,broken_mismatches=0;
  // Finite suffix winner, prefix winner, cross-partition tie, boundary winners,
  // signed zero, and a suffix nonfinite. Values are diagnostic fixtures, not
  // retained logits from architecture-tradeoff or performance measurements.
  for(int mode=0;mode<7;++mode){
    Engine e;uint32_t one=1;e.upload(0,suffix_active,0,&one,4);
    require(e.value(suffix_active)==1,"constructor active");
    for(int request=0;request<3;++request){
    if(request)reset(e);
    require(e.value(suffix_active)==uint32_t(!request),"reset must reproduce suffix active loss");
    if(request)require(e.value(2)==1,"canonical active must be restored");
    std::vector<uint16_t> logits(p105::vocab,iq3::bf16_bits(-2.f));
    logits[440]=iq3::bf16_bits(3.f);logits[215495]=iq3::bf16_bits(4.f);
    if(mode==1)logits[440]=iq3::bf16_bits(5.f);
    if(mode==2)logits[440]=iq3::bf16_bits(4.f);
    if(mode==3)logits[boundary]=iq3::bf16_bits(6.f);
    if(mode==4)logits[p105::vocab-1]=iq3::bf16_bits(6.f);
    if(mode==5){std::fill(logits.begin(),logits.end(),0x8000);logits[boundary]=0;}
    if(mode==6)logits[215495]=0x7fc1;
    int32_t whole_index=0,prefix_index=0;uint32_t whole_error=0,prefix_error=0;
    auto whole=reduce(logits,0,1,whole_index,whole_error);
    std::vector<uint16_t> left(logits.begin(),logits.begin()+boundary),right(logits.begin()+boundary,logits.end());
    auto prefix=reduce(left,0,1,prefix_index,prefix_error);
    original_service(e,suffix_error,suffix_active);
    int32_t index=0;uint32_t error=e.value(suffix_error);
    auto broken=p105::merge(prefix,reduce(right,boundary,e.value(suffix_active),index,error),boundary);
    if(request){require(index==0,"disabled argmax must leave index zero");
      if(mode==0)require(whole.index==215495&&broken.index==440,"exact observed IDs must be reproducible");
    }
    if(whole.error!=broken.error||(!whole.error&&whole.index!=broken.index))++broken_mismatches;
    fixed_service(e,suffix_error,suffix_active);
    require(e.value(suffix_active)==1,"repair must restore private active");
    index=0;error=e.value(suffix_error);
    auto fixed=p105::merge(prefix,reduce(right,boundary,e.value(suffix_active),index,error),boundary);
    require(fixed.error==whole.error,"nonfinite sticky status");
    if(!whole.error)require(std::memcmp(&whole,&fixed,sizeof whole)==0,"exact finite best payload");
    else require(fixed.error!=0,"nonfinite must block token output");
    ++cases;
    }
  }
  require(broken_mismatches==6,"negative control must detect lost suffix winners and nonfinite");
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases
           <<",\"negative_control_mismatches\":"<<broken_mismatches
           <<",\"fixed_exact_cases\":"<<cases<<",\"observed_token_ids_reproduced_with_synthetic_logits\":true}\n";
  return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
