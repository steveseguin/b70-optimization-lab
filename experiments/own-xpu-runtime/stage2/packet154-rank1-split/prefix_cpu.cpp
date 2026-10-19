// Host-only numerical and controller gate. Includes the production bodies;
// no imitation GEMV, argmax or pipeline implementation is used as the tested path.
#ifndef OWN_RT_HOST_ONLY
#error "packet56 CPU gate must be built with OWN_RT_HOST_ONLY"
#endif
#include "p33_submit.cpp"
#include "round2_submit.cpp"
#include "p56_prefix.hpp"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>
#include <unistd.h>
namespace fs=std::filesystem;
void require(bool yes,const std::string& why){if(!yes)throw std::runtime_error(why);}
namespace pipeline {
constexpr size_t slot_bytes=65536;
enum {half=1,accept=2,rollback=3,dump=4,draft=9};
struct Request{int32_t op,token,position,fixture,speculative,sequence,reserved[2];};
struct Reply{int32_t status,token,error,bytes,sequence,rank,reserved[2];double busy_ms,gpu_ms,redo_ms,reserved_ms;};
}
#include "native_controller.hpp"
namespace p56x { const bool sleep20 = false; } // Same sealed spin policy as packet103.

namespace {
constexpr unsigned full_vocab=248320;
unsigned numerical_cases=0,argmax_cases=0,pipeline_cases=0;

void shape_gate(unsigned n){
 integrated::Matrix target{};target.rows=full_vocab;target.span=full_vocab;
 target.columns=2560;target.count=1;target.experts=1;target.w=17;target.x=18;target.y=19;
 auto draft=target;p56::restrict_matrix(draft,n);
 require(target.rows==full_vocab&&target.span==full_vocab,"target shape changed");
 require(draft.w==target.w&&draft.x==target.x&&draft.y==target.y&&draft.columns==target.columns,"prefix changed allocation or row layout");
 integrated::Spec target_argmax{};target_argmax.op=integrated::Op::argmax;
 target_argmax.g.vocab=full_vocab;target_argmax.sizes[0]=full_vocab;
 auto draft_argmax=target_argmax;p56::restrict_argmax(draft_argmax,n);
 require(draft_argmax.g.vocab==full_vocab&&target_argmax.sizes[0]==full_vocab,"prefix changed vocabulary or target argmax");
 require(p56::rows(16,true)==16,"mini fixture vocabulary must remain complete");
 for(unsigned bad:{0u,full_vocab+1}){
  bool rejected=false;try{auto copy=target;p56::restrict_matrix(copy,bad);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"invalid matrix prefix admitted");
  rejected=false;try{auto copy=target_argmax;p56::restrict_argmax(copy,bad);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"invalid argmax prefix admitted");
 }
 for(unsigned field=0;field<3;++field){
  auto invalid=target;if(field==0)invalid.count=2;if(field==1)invalid.experts=2;if(field==2)invalid.routes=21;
  bool rejected=false;try{p56::restrict_matrix(invalid,n);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"non-contiguous prefix admitted");
 }
}

int actual_argmax(std::vector<uint16_t>& logits,unsigned rows,bool reverse=false){
 using namespace integrated;
 require(rows>0&&rows<=logits.size(),"argmax rows");
 Spec s;s.op=Op::argmax;s.ni=1;s.no=2;s.sizes[0]=logits.size();
 p56::restrict_argmax(s,rows);
 s.sizes[1]=s.sizes[2]=1;s.types[0]=flash::Scalar::bf16;
 s.types[1]=flash::Scalar::i32;s.types[2]=flash::Scalar::u32;
 int32_t output=-1;uint32_t error=0,position=0,active=1;
 std::vector<float> scratch(2*((rows+1023)/1024)),local(64);
 std::array<void*,8> ptr{logits.data(),&output,&error,scratch.data(),&error,&position,&active,nullptr};
 round2::Simple<Op::argmax,0,flash::Scalar::bf16> kernel(s);
 auto a=kernel.bind(ptr);ng::HostTeam team{local.data()};
 const int chunks=kernel.count();
 for(int j=0;j<chunks;++j)round2::simple_group<Op::argmax,0,flash::Scalar::bf16>(a,reverse?chunks-1-j:j,team);
 round2::simple_group<Op::argmax,1,flash::Scalar::bf16>(a,0,team);
 require(error==0,"finite prefix must not set argmax error");
 return output;
}
int reference_argmax(const std::vector<uint16_t>& values,unsigned rows){
 int best=0;
 for(unsigned j=0;j<rows;++j)
  if(iq3::bits_float(uint32_t(values[j])<<16)>iq3::bits_float(uint32_t(values[best])<<16))best=j;
 return best;
}
void logits_gate(){
 using namespace integrated;
 constexpr unsigned rows=1024,columns=2560;
 const unsigned variant=arithmetic::r5_variant(iq3::Type::Q6_K,full_vocab,columns,1,false);
 require(variant==6,"full production head must retain expanded SG32 variant");
 const size_t rb=arithmetic::row_bytes(iq3::Type::Q6_K,columns,variant);
 const auto fmt=iq3::layout(iq3::Type::Q6_K);
 std::vector<uint8_t> packed(rows*(columns/fmt.elements)*fmt.bytes);
 uint32_t seed=0x560149d;
 for(auto& byte:packed){seed=seed*1664525u+1013904223u;byte=seed>>24;}
 for(size_t p=0;p<packed.size();p+=fmt.bytes){uint16_t scale=0x2000+(p/fmt.bytes)%0x1000;std::memcpy(packed.data()+p+208,&scale,2);}
 auto weights=iq3::expanded::expand(iq3::Type::Q6_K,packed.data(),packed.size(),columns);
 // Q6 expanded rows are 3380 bytes: four-byte scale alignment per row;
 // 256-row prefix boundaries preserve the stronger allocation alignment.
 require(weights.size()==rows*rb&&rb==3380&&rb%4==0&&(256*rb)%16==0,"contiguous expanded Q6 rows");
 const auto original=weights;
 for(unsigned mode=0;mode<4;++mode){
  std::vector<uint16_t> input(columns);
  for(unsigned k=0;k<columns;++k){
   if(mode==0)input[k]=iq3::bf16_bits(float(int(k*31%251)-125)/128.f);
   if(mode==1)input[k]=(k%2)?0x8000:0;
   if(mode==2){constexpr uint16_t edge[]{0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};input[k]=edge[k%8];}
   if(mode==3)input[k]=iq3::bf16_bits((k%2?-1.f:1.f)*(k%3?128.f:1.f/128.f));
  }
  std::vector<uint16_t> full(rows),prefix(rows,0xdead);
  p33::Kernel<0,iq3::Type::Q6_K,columns,1> op;Matrix m{};m.type=iq3::Type::Q6_K;m.rows=rows;m.columns=columns;m.count=1;m.experts=1;m.span=rows;
  op.b.rows=m.rows;op.b.rb=rb;op.b.count=1;op.b.experts=1;op.b.has_routes=false;
  std::array<void*,9> ptr{weights.data(),weights.data(),input.data(),full.data(),nullptr,nullptr,nullptr,nullptr,nullptr};
  op.run(ptr);
  for(unsigned n:{256u,512u,768u,1024u}){
   std::fill(prefix.begin(),prefix.end(),0xdead);auto restricted=m;p56::restrict_matrix(restricted,n);
   require(restricted.columns==columns&&restricted.span==n,"prefix matrix geometry");
   op.b.rows=restricted.rows;ptr[3]=prefix.data();op.run(ptr);
   require(std::memcmp(full.data(),prefix.data(),n*2)==0,"draft prefix logits differ in bytes");
   for(unsigned r=n;r<rows;++r)require(prefix[r]==0xdead,"prefix wrote beyond row bound");
   require(weights==original,"shared expanded head modified");
   require(actual_argmax(prefix,n)==reference_argmax(full,n),"proposal is not prefix argmax");
   ++numerical_cases;
  }
 }
}
void full_geometry_logits_gate(unsigned n){
 using namespace integrated;
 constexpr unsigned columns=2560;
 const auto fmt=iq3::layout(iq3::Type::Q6_K);
 const size_t rb=arithmetic::row_bytes(iq3::Type::Q6_K,columns,6);
 std::vector<uint8_t> packed(8*(columns/fmt.elements)*fmt.bytes);
 uint32_t seed=0x56aabbcc;
 for(auto& byte:packed){seed=seed*1664525u+1013904223u;byte=seed>>24;}
 for(size_t p=0;p<packed.size();p+=fmt.bytes){uint16_t scale=0x2800+(p/fmt.bytes)%128;std::memcpy(packed.data()+p+208,&scale,2);}
 auto eight=iq3::expanded::expand(iq3::Type::Q6_K,packed.data(),packed.size(),columns);
 // One shared synthetic allocation has exactly the admitted expanded head
 // geometry. No packed model or real checkpoint bytes are opened.
 std::vector<uint8_t> weights(size_t(full_vocab)*rb);
 for(unsigned row=0;row<full_vocab;++row){
  std::memcpy(weights.data()+size_t(row)*rb,eight.data()+(row%8)*rb,rb);
  weights[size_t(row)*rb]=uint8_t(int(row%63)-31);
 }
 std::vector<uint16_t> input(columns),full(full_vocab),prefix(full_vocab,0xdead);
 for(unsigned k=0;k<columns;++k)input[k]=iq3::bf16_bits(float(int(k*31%251)-125)/128.f);
 p33::Kernel<0,iq3::Type::Q6_K,columns,1> op;
 op.b.rows=full_vocab;op.b.rb=rb;op.b.count=1;op.b.experts=1;op.b.has_routes=false;
 std::array<void*,9> ptr{weights.data(),weights.data(),input.data(),full.data(),nullptr,nullptr,nullptr,nullptr,nullptr};
 op.run(ptr);
 Matrix m{};m.rows=full_vocab;m.span=full_vocab;m.columns=columns;m.count=1;m.experts=1;
 p56::restrict_matrix(m,n);op.b.rows=m.rows;ptr[3]=prefix.data();op.run(ptr);
 require(std::memcmp(full.data(),prefix.data(),size_t(n)*2)==0,"full-geometry prefix logits differ in bytes");
 for(unsigned row=n;row<full_vocab;++row)require(prefix[row]==0xdead,"full-geometry prefix wrote suffix");
 require(actual_argmax(prefix,n)==reference_argmax(full,n),"full-geometry proposal is not prefix argmax");
}
void argmax_gate(unsigned sealed_n){
 for(unsigned n:{sealed_n}){
  require(n>0&&n<=full_vocab,"sealed N range");
  std::vector<uint16_t> values(full_vocab,iq3::bf16_bits(2.f));
  for(unsigned mode=0;mode<5;++mode){
   std::fill(values.begin(),values.end(),iq3::bf16_bits(-4.f));
   if(mode==0){values[0]=values[n-1]=iq3::bf16_bits(7.f);}
   if(mode==1){values[255]=values[n-1]=iq3::bf16_bits(7.f);}
   if(mode==2){values[n-1]=iq3::bf16_bits(7.f);}
   if(mode==3)for(unsigned j=0;j<n;++j)values[j]=(j%2)?0x8000:0;
   if(mode==4)for(unsigned j=0;j<n;++j)values[j]=iq3::bf16_bits(float(int((j*317)%997)-498));
   // A poisonous excluded suffix proves that the proposed token and finite
   // check read the prefix only. Production never consumes these stale rows.
   for(unsigned j=n;j<full_vocab;++j)values[j]=0x7fc0;
   int expected=reference_argmax(values,n);
   for(bool reverse:{false,true})require(actual_argmax(values,n,reverse)==expected,"argmax value/tie/order mismatch");
   ++argmax_cases;
  }
 }
}
struct State{
 std::vector<int> history,rows;uint32_t recurrence=7;
 bool operator==(const State&)const=default;
};
struct Mock{
 State state[2],saved;bool pending[2]{};pipeline::Request candidate[2]{};
 std::vector<std::pair<int,int>> fixtures[2];std::vector<int> draft_confirmed;
 pipeline::native38::Mailbox& box;uint8_t* shared;unsigned n;int target_mode;
 unsigned rollbacks=0,accepted_speculations=0;
 pipeline::Reply execute(int rank,const pipeline::Request& r){
  using namespace pipeline;auto& s=state[rank];int token=-1;
  if(r.op==half){
   require(!pending[rank]&&int(s.history.size())==r.position,"mock half position/pending");
   if(rank==0)saved=s;
   int incoming=0;if(rank==1)std::memcpy(&incoming,shared+slot_bytes,4);
   s.history.push_back(r.token);s.recurrence=(s.recurrence*13+uint32_t(r.token)+incoming+r.position)%104729;
   s.rows.push_back(s.recurrence);pending[rank]=true;candidate[rank]=r;
   if(rank==0)std::memcpy(shared,&s.recurrence,4);
   bool outside=target_mode==0||(target_mode==2&&r.position%2==0);
   token=outside?int(n+s.recurrence%(full_vocab-n)):int(n-1);
  }else if(r.op==accept){
   require(pending[rank],"mock accept pending");if(candidate[rank].fixture)fixtures[rank].emplace_back(candidate[rank].fixture,s.recurrence);
   if(rank==0&&candidate[rank].speculative)++accepted_speculations;pending[rank]=false;
  }else if(r.op==rollback){
   require(rank==0&&pending[rank]&&candidate[rank].speculative,"ordinary rollback preconditions");
   ++rollbacks;s=saved;pending[rank]=false;
  }else if(r.op==draft){
   require(rank==1&&!pending[1],"draft rank/commit");draft_confirmed.push_back(r.token);
   struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};
   Publication pub{1,r.position+1,int32_t(n-1),0,1,r.sequence,0,0};
   std::memcpy(shared+2*slot_bytes,&pub,sizeof pub);native38::publish(box.draft_sequence,r.sequence);
  }else if(r.op==dump)require(!pending[rank],"dump pending");else throw std::runtime_error("unexpected opcode");
  return {0,token,0,r.op==half&&rank==0?4:0,0,rank,{0,0},0,0,0,0};
 }
};
struct Run{pipeline::native38::Result result;State state[2];std::vector<std::pair<int,int>> fixtures[2];std::vector<int> draft_confirmed;unsigned rollbacks,accepted_speculations;};
Run run_pipeline(unsigned n,int target_mode,int mode,const std::vector<int>& prompt,int eos=-1){
 using namespace pipeline;
 native38::Config c;c.mode=mode;c.count=10;c.vocab=full_vocab;c.prompt=prompt;c.dumps=1;
 if(eos>=0)c.eos={eos};
 std::vector<uint8_t> shared(2*slot_bytes+4096);native38::Mailbox box;
 Mock mock{{},{},{},{},{},{},box,shared.data(),n,target_mode};
 std::exception_ptr error;
 std::thread worker([&]{try{native38::worker(box,5,[&](const Request& r){return mock.execute(1,r);},[]{});}catch(...){error=std::current_exception();native38::abort(box);}});
 native38::Backend b(box,shared.data(),5,[&](const Request& r){return mock.execute(0,r);},[]{});
 native38::Result result;
 try{result=native38::run(b,c);}catch(...){native38::abort(box);worker.join();throw;}
 worker.join();if(error)std::rethrow_exception(error);
 return {result,{mock.state[0],mock.state[1]},{mock.fixtures[0],mock.fixtures[1]},mock.draft_confirmed,mock.rollbacks,mock.accepted_speculations};
}
void pipeline_gate(unsigned n){
 require(n<full_vocab,"outside-prefix controller gate requires excluded tokens");
 for(const auto& prompt:{std::vector<int>{1},std::vector<int>{1,2,3}})
 for(int target_mode:{0,1,2}){
  auto baseline=run_pipeline(n,target_mode,0,prompt);
  for(int eos:{-1,baseline.result.tokens[3]}){
   auto reference=run_pipeline(n,target_mode,0,prompt,eos);
   auto candidate=run_pipeline(n,target_mode,3,prompt,eos);
   require(candidate.result.tokens==reference.result.tokens,"target outputs changed");
   for(int rank:{0,1}){
    require(candidate.state[rank]==reference.state[rank],"pipeline committed state changed");
    require(candidate.fixtures[rank]==reference.fixtures[rank],"pipeline fixtures changed");
   }
   unsigned outside=0,inside=0;
   for(const auto& guess:candidate.result.guesses){
    require(guess.guess==int(n-1),"unexpected proposal");
    if(guess.actual>=int(n)){++outside;require(!guess.hit,"excluded target accepted");}
    else{++inside;require(guess.hit,"in-prefix expected match rejected");}
   }
   require(candidate.result.misses==int(outside),"excluded target is not ordinary miss");
   require(candidate.result.hits==int(inside),"hit accounting");
   // EOS may discard an in-flight speculation in addition to counted misses.
   require(candidate.rollbacks>=outside,"missing rollback");
   if(eos<0&&target_mode==0)require(outside>0&&candidate.rollbacks==outside,"all misses must redo once");
   if(eos<0&&target_mode==1)require(inside>0&&candidate.rollbacks==0,"all hits must avoid rollback");
   ++pipeline_cases;
  }
 }
}
}
int main(int argc,char**argv){
 try{
  require(argc==2,"usage: p56-cpu-gate SEALED_N");unsigned n=std::stoul(argv[1]);
  require((n==91392||n==80128)&&n%256==0,"N must equal sealed aligned constant");
  shape_gate(n);logits_gate();full_geometry_logits_gate(n);argmax_gate(n);pipeline_gate(n);
  std::cout<<"{\"schema\":\"packet56.cpu-gate.v1\",\"passed\":true,\"device_executed\":false,\"model_weights_read\":false,\"sealed_n\":"<<n
   <<",\"synthetic_q6_width\":2560,\"synthetic_small_rows\":1024,\"synthetic_full_rows\":"<<full_vocab
   <<",\"full_geometry_prefix_rows_compared\":"<<n<<",\"full_geometry_prefix_bytes_compared\":"<<2*n
   <<",\"small_logit_byte_identity_cases\":"<<numerical_cases
   <<",\"argmax_cases\":"<<argmax_cases<<",\"controller_cases\":"<<pipeline_cases
   <<",\"real_model_oracle_gate\":\"pending coordinator chain\"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
