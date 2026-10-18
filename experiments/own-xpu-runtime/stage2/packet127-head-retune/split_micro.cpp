// Diagnostic synthetic weights and hidden vectors. Never a model speed result.
// These are the exact production head, two-stage argmax and partition pack bodies.
#include "p33_submit.cpp"
#include "round2_submit.cpp"
#include "p105_submit.cpp"
#include <atomic>
#include <csignal>
#include <iostream>
#include <chrono>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void require(bool yes,const char* why){if(!yes)throw std::runtime_error(why);}
struct Buffers {
 sycl::queue&q;std::vector<void*>owned;
 ~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto*p:owned)sycl::free(p,q);}
 template<class T>T* alloc(size_t n){auto*p=sycl::malloc_device<T>(n,q);if(!p)throw std::bad_alloc();owned.push_back(p);return p;}
};
struct Upload {
 sycl::queue&q;
 void upload(int,void*dst,size_t offset,const void*src,size_t bytes){q.memcpy(static_cast<char*>(dst)+offset,src,bytes).wait_and_throw();}
};
static void rearm(Upload&e,uint32_t*error,uint32_t*active){
#include "micro_service.inc"
}
struct Reduction {
 sycl::queue&q;uint16_t*logits;unsigned rows,offset;
 int32_t*index;uint32_t*error,*active,*position;float*scratch;p105::Best*best;
 Reduction(Buffers&b,uint16_t*y,unsigned n,unsigned off):q(b.q),logits(y),rows(n),offset(off){
  index=b.alloc<int32_t>(1);error=b.alloc<uint32_t>(1);active=b.alloc<uint32_t>(1);position=b.alloc<uint32_t>(1);
  scratch=b.alloc<float>(2*((n+1023)/1024));best=b.alloc<p105::Best>(1);reset();
 }
 void reset(){q.memset(index,0,4);q.memset(error,0,4);q.memset(active,0,4);q.memset(position,0,4);q.memset(scratch,0,8*((rows+1023)/1024));q.memset(best,0,16);q.wait_and_throw();}
 p105::Best run(bool enable=true){
  Upload e{q};if(enable)rearm(e,error,active);
  integrated::Spec s;s.op=integrated::Op::argmax;s.ni=1;s.no=1;s.sizes[0]=rows;s.sizes[1]=1;s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
  std::array<void*,7> ids{logits,index,scratch,error,position,active,position};
  round2::Simple<integrated::Op::argmax,0,flash::Scalar::bf16>(s).submit(q,ids,{});
  round2::Simple<integrated::Op::argmax,1,flash::Scalar::bf16>(s).submit(q,ids,{});
  p105::Pack pack;pack.rows=rows;pack.offset=offset;
  std::array<void*,4> bound{logits,index,error,best};pack.submit(q,bound,{});
  p105::Best result{};q.memcpy(&result,best,16).wait_and_throw();return result;
 }
};
int main(int argc,char**argv){try{
 require(argc==3&&std::string(argv[1])=="--coordinator-admitted-device-window","coordinator admission required");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 const auto begin=std::chrono::steady_clock::now();
 const unsigned R=std::stoul(argv[2]),L=p105::vocab-R;require(R==81920||R==122880,"registered candidate");
 unsigned cases=0,suffix_winners=0,ties=0,nonfinite=0,resets=0,negative=0;
 {
 sycl::queue q(sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order{}});
 Buffers b{q};constexpr unsigned K=2560,N=p105::vocab;
 constexpr size_t stride=3380;
 auto*w=b.alloc<uint8_t>(size_t(N)*stride);auto*x=b.alloc<uint16_t>(K);
 auto*whole=b.alloc<uint16_t>(N);auto*split=b.alloc<uint16_t>(N);
 std::vector<uint8_t> weights(size_t(N)*stride,0);
 uint32_t rng=0x105b106b;auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
 // Special sentinel columns create provable suffix and cross-boundary winners.
 const unsigned winners[4]={440,215495,L,N-1};
 for(unsigned r=0;r<N;++r){auto*row=weights.data()+size_t(r)*stride;
  for(unsigned k=0;k<K-5;++k)row[k]=uint8_t(int(next()%7)-3);
  for(unsigned k=0;k<K/16;++k){float scale=1.f/128;std::memcpy(row+K+4*k,&scale,4);}
 }
 for(unsigned j=0;j<4;++j){auto*row=weights.data()+size_t(winners[j])*stride;std::fill_n(row,K,0);row[K-5+j]=31;}
 // Prefix boundary has its own coordinate, with exactly equal reduction/rounding.
 auto*boundary=weights.data()+size_t(L-1)*stride;std::fill_n(boundary,K,0);boundary[K-1]=31;
 q.memcpy(w,weights.data(),weights.size()).wait_and_throw();weights.clear();weights.shrink_to_fit();
 auto head=[&](uint8_t*weight,unsigned rows,uint16_t*y){
  p33::Kernel<0,iq3::Type::Q6_K,K,1>op;op.b.rows=rows;op.b.count=op.b.experts=1;op.b.rb=stride;
  std::array<void*,9>ptrs{weight,weight,x,y,y,x,y,y,y};op.submit(q,ptrs,{});
 };
 Reduction full(b,whole,N,0),left(b,split,L,0),right(b,split+L,R,L);
 std::vector<uint16_t>hidden(K),expected(N),actual(N);
 // 4096 independent vectors; reset every 16 and once before the negative control.
 for(unsigned test=0;test<4096;++test){
  require(!stopped,"coordinator graceful stop");
  if(test%16==0){full.reset();left.reset();right.reset();++resets;}
  unsigned mode=test%16;
  for(unsigned k=0;k<K;++k)hidden[k]=iq3::bf16_bits(float(int(next()%113)-56)/64.f);
  for(unsigned k=K-5;k<K;++k)hidden[k]=0;
  int forced=-1;
  if(mode>=1&&mode<=4){unsigned j=mode%4;hidden[K-5+j]=iq3::bf16_bits(float(1024+(test%7)*128));forced=winners[j];}
  if(mode==5){std::fill(hidden.begin(),hidden.end(),0);hidden[K-3]=hidden[K-1]=iq3::bf16_bits(4096.f);forced=L-1;++ties;}
  if(mode==6){std::fill(hidden.begin(),hidden.end(),0x8000);forced=0;}
  // More suffix-heavy finite vectors with random background and scaling.
  if(mode>=10){unsigned j=1+test%3;hidden[K-5+j]=iq3::bf16_bits(8192.f);forced=winners[j];}
  q.memcpy(x,hidden.data(),K*2);
  head(w,N,whole);head(w,L,split);head(w+size_t(L)*stride,R,split+L);
  if(mode>=7&&mode<=9){
   // Inject NaN/+Inf/-Inf rows in each partition, after genuine head execution.
   uint16_t bad=mode==7?0x7fc1:mode==8?0x7f80:0xff80;
   unsigned at=(test/16)%2?L+17:L-1;
   q.memcpy(whole+at,&bad,2).wait_and_throw();q.memcpy(split+at,&bad,2).wait_and_throw();++nonfinite;
  }
  q.memcpy(expected.data(),whole,N*2).wait_and_throw();q.memcpy(actual.data(),split,N*2).wait_and_throw();
  require(expected==actual,"full/split head logit bytes mismatch");
  auto reference=full.run(),prefix=left.run();
  // Deliberately disable suffix after reset once: prove the workload catches the old bug.
  if(test==1){right.reset();auto broken=p105::merge(prefix,right.run(false),L);require(!reference.error&&reference.index==215495&&broken.index!=reference.index,"negative reset control did not detect old bug");++negative;}
  auto candidate=p105::merge(prefix,right.run(),L);
  require(reference.error==candidate.error,"nonfinite status mismatch");
  if(!reference.error){require(std::memcmp(&reference,&candidate,16)==0,"split/full argmax payload mismatch");
   if(forced>=0)require(reference.index==forced,"forced winner not exercised");
   suffix_winners+=unsigned(reference.index>=int(L));
  }else require(mode>=7&&mode<=9,"unexpected nonfinite head");
  ++cases;
  if(test%256==255)std::cout<<"{\"kind\":\"batch\",\"completed\":"<<cases<<",\"suffix_rows\":"<<R<<",\"mismatches\":0,\"suffix_winners\":"<<suffix_winners<<",\"resets\":"<<resets<<"}\n"<<std::flush;
 }
 q.wait_and_throw();
 } // Every device allocation and the queue drain before the final success receipt.
 require(cases==4096&&suffix_winners>=2000&&ties==256&&nonfinite==768&&resets==256&&negative==1,"coverage incomplete");
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"cases\":"<<cases<<",\"suffix_rows\":"<<R<<",\"mismatches\":0,\"suffix_winners\":"<<suffix_winners<<",\"ties\":"<<ties<<",\"nonfinite\":"<<nonfinite<<",\"resets\":"<<resets<<",\"negative_control_mismatches\":"<<negative<<",\"diagnostic\":true,\"model_weights\":false,\"seconds\":"<<std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()<<"}\n";
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
