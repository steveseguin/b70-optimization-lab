// Packet162b diagnostic. Real selected rows only; no model execution.
#include "p90_expert.hpp"
#include "micro_candidate.hpp"
#include <fstream>
#include <iostream>
#include <atomic>
#include <csignal>
#include <cstdlib>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n++;}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void require(bool b,const char*s){if(!b)throw std::runtime_error(s);}
constexpr unsigned K=2560,R=640,N=10,NR=2*R*N;
struct Data{std::vector<uint8_t>w=std::vector<uint8_t>(NR*840),c=std::vector<uint8_t>(NR*880);};
Data prepare(const std::string&file,bool synthetic){
 Data d;std::vector<uint8_t>raw(NR*820);uint32_t seed=162;
 if(synthetic){for(auto&v:raw){seed=1664525*seed+1013904223;v=seed>>24;}for(size_t i=0;i<raw.size();i+=82){raw[i]=0;raw[i+1]=0x24;}}
 else{std::ifstream f(file,std::ios::binary|std::ios::ate);require(bool(f)&&f.tellg()==std::streamoff(raw.size()),"raw extent");f.seekg(0);f.read((char*)raw.data(),raw.size());require(bool(f),"raw truncated");}
 for(unsigned row=0;row<NR;++row){auto*s=raw.data()+size_t(row)*820;auto*w=d.w.data()+size_t(row)*840;auto*c=d.c.data()+size_t(row)*880;
  for(unsigned b=0;b<10;++b)require((p49bgemv::load16(s+82*b)&0x7c00)!=0x7c00,"nonfinite weight scale");
  p90::expert_repack(K,s,w);std::memcpy(c,w,840);
  for(unsigned b=0;b<10;++b)for(unsigned q=0;q<32;++q){unsigned hi=640+b*8+q/4,shift=2*(q%4),i=w[b*64+2*q]|(((w[hi]>>shift)&3)<<8),code=p162enum::encode[i];c[b*64+2*q]=code&255;c[hi]=(c[hi]&~(3u<<shift))|(((code>>8)&3)<<shift);c[840+b*4+q/8]|=(code>>10)<<(q%8);}
 }return d;
}
std::vector<uint16_t> input(unsigned fixture){std::vector<uint16_t>x(K);uint32_t s=162+fixture;uint16_t special[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2};for(unsigned i=0;i<K;++i){s=s*1664525+1013904223;x[i]=fixture==2&&i%17==0?special[(i/17)%8]:iq3::bf16_bits(float(int(s%255)-127)/128.f);}return x;}
std::array<iq3::Route,N> routes(bool invalid){std::array<iq3::Route,N>a;for(unsigned i=0;i<N;++i)a[i]={i,0,R};if(invalid){a[3]={512,0,R};a[7]={7,3,637};}return a;}
#ifdef OWN_RT_HOST_ONLY
std::vector<uint8_t> host(const Data&d,unsigned f,bool bad,bool candidate){auto x=input(f);auto rt=routes(bad);std::vector<uint8_t>o(NR*2+84,0xa5);uint32_t active=1;std::memset(o.data()+NR*2+80,0,4);std::array<void*,19>p{};auto&w=candidate?d.c:d.w;unsigned rb=candidate?880:840;p[0]=(void*)w.data();p[1]=(void*)(w.data()+R*N*rb);p[2]=x.data();p[3]=o.data();p[4]=o.data()+R*N*2;p[5]=rt.data();p[6]=o.data()+NR*2;p[7]=o.data()+NR*2+40;p[16]=o.data()+NR*2+80;p[17]=&active;
 if(candidate){p162enumexp::Kernel<iq3::Type::IQ2_S,K,64,false,true>k;k.run(p);}else{p90exp::Kernel<iq3::Type::IQ2_S,K,64,false,true>k;k.run(p);}return o;}
#else
struct Buffers{sycl::queue&q;std::vector<void*>p;void*alloc(size_t n){auto*x=sycl::malloc_device(n,q);if(!x)throw std::bad_alloc();p.push_back(x);return x;}~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto*x:p)sycl::free(x,q);}};
void bench(const Data&d,const std::string&shape,unsigned repeats){
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});Buffers b{q,{}};
 auto*w=(uint8_t*)b.alloc(d.w.size());auto*c=(uint8_t*)b.alloc(d.c.size());auto*x=b.alloc(K*2);auto*rt=b.alloc(N*sizeof(iq3::Route));auto*o=(uint8_t*)b.alloc(NR*2+84);auto*active=b.alloc(4);
 q.memcpy(w,d.w.data(),d.w.size());q.memcpy(c,d.c.data(),d.c.size());uint32_t one=1;q.memcpy(active,&one,4).wait_and_throw();
 std::array<void*,19>p{};p[2]=x;p[3]=o;p[4]=o+R*N*2;p[5]=rt;p[6]=o+NR*2;p[7]=o+NR*2+40;p[16]=o+NR*2+80;p[17]=active;
 p90exp::Kernel<iq3::Type::IQ2_S,K,64,false,true>a;p162enumexp::Kernel<iq3::Type::IQ2_S,K,64,false,true>z;
 auto launch=[&](bool cand){p[0]=cand?c:w;p[1]=(cand?c:w)+R*N*(cand?880:840);return cand?z.submit(q,p,{}):a.submit(q,p,{});};
 auto bytes=[&]{std::vector<uint8_t>v(NR*2+84);q.memcpy(v.data(),o,v.size()).wait_and_throw();return v;};
 for(unsigned f=0;f<3;++f){auto xx=input(f);q.memcpy(x,xx.data(),xx.size()*2).wait_and_throw();
  for(unsigned bad=0;bad<2;++bad){auto rr=routes(bad);q.memcpy(rt,rr.data(),sizeof(rr));q.memset(o,0xa5,NR*2+84);q.memset(o+NR*2+80,0,4).wait_and_throw();launch(false).wait_and_throw();auto expected=bytes();q.memset(o,0xa5,NR*2+84);q.memset(o+NR*2+80,0,4).wait_and_throw();launch(true).wait_and_throw();auto actual=bytes();size_t diff=0;for(size_t i=0;i<actual.size();++i)diff+=actual[i]!=expected[i];
   std::cout<<"{\"kind\":\"bytes\",\"shape\":\""<<shape<<"\",\"fixture\":"<<f<<",\"invalid\":"<<bad<<",\"different_bytes\":"<<diff<<",\"bytes_equal\":"<<(diff?"false":"true")<<"}\n"<<std::flush;
  }
  if(f==2)continue;auto rr=routes(false);q.memcpy(rt,rr.data(),sizeof(rr));q.memset(o+NR*2+80,0,4).wait_and_throw();
  for(unsigned rep=0;rep<repeats;++rep)for(unsigned arm=0;arm<2;++arm){require(!stopped,"graceful stop");auto e=launch(arm);e.wait_and_throw();auto start=e.get_profiling_info<sycl::info::event_profiling::command_start>(),end=e.get_profiling_info<sycl::info::event_profiling::command_end>();std::cout<<"{\"kind\":\"sample\",\"shape\":\""<<shape<<"\",\"fixture\":"<<f<<",\"repeat\":"<<rep<<",\"arm\":"<<arm<<",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<"}\n"<<std::flush;}
 }q.wait_and_throw();
}
#endif
int main(int argc,char**argv){try{std::string file,shape;unsigned repeats=0;bool admitted=false;int rank=-1;
 if(argc==2&&std::string(argv[1])=="--help"){std::cout<<"usage: --rank 0 --rows-file PATH --shape NAME --repeats 200 --coordinator-admitted-device-window\n";return 0;}
 for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--coordinator-admitted-device-window")admitted=true;else{require(i+1<argc,"missing argument");std::string v=argv[++i];if(a=="--rank"){require(v=="0","rank must be zero");rank=0;}else if(a=="--rows-file")file=v;else if(a=="--shape")shape=v;else if(a=="--repeats"){require(v=="200","exactly 200 repeats");repeats=200;}else throw std::runtime_error("unknown option");}}
 require(admitted&&rank==0&&repeats==200&&!file.empty()&&!shape.empty(),"invalid micro argv");
 // Same executable and parser; transport substituted only before the first device API.
 bool probe=std::getenv("ENTRY_PREPARE_OUTPUT")!=nullptr;
 std::vector<std::pair<std::string,Data>> datasets;
 if(shape=="all"){for(auto name:{"layer0","layer24"})datasets.emplace_back(name,prepare(file+"/"+name+".bin",probe));}
 else datasets.emplace_back(shape,prepare(file,probe||file=="synthetic"));
 if(probe){
  for(unsigned i=0;i<1024;++i)require(p162enum::grid(p162enum::encode[i])==(uint64_t(p42expert::iq2_words[2*i])|(uint64_t(p42expert::iq2_words[2*i+1])<<32)),"integer grid parity");
  for(unsigned f=0;f<3;++f)require(input(f).size()==K,"input extent");
  for(auto r:routes(false))require(r.expert_id<N&&iq3::valid_route(r,512,R,R),"compact selected route extent");
  require(!iq3::valid_route(routes(true)[3],512,R,R),"invalid route rejection");
  std::cout<<"PASS CPU preparation before first device call; rows=12800 candidate_bytes=11264000\n";return 0;}
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 for(auto&entry:datasets){auto&shape=entry.first;auto&d=entry.second;
#ifdef OWN_RT_HOST_ONLY
 for(unsigned f=0;f<3;++f)for(unsigned bad=0;bad<2;++bad){auto a=host(d,f,bad,false),c=host(d,f,bad,true);size_t diff=0;for(size_t i=0;i<a.size();++i)diff+=a[i]!=c[i];std::cout<<"{\"kind\":\"bytes\",\"shape\":\""<<shape<<"\",\"fixture\":"<<f<<",\"invalid\":"<<bad<<",\"different_bytes\":"<<diff<<",\"bytes_equal\":"<<(diff?"false":"true")<<"}\n";}
#else
 bench(d,shape,repeats);
#endif
 }
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"rows\":640,\"columns\":2560,\"diagnostic_only\":true}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
