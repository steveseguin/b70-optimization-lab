// Existing standalone actual Bucket+Tiles fixture policies; no engine changes.
#include "fixture_policies.inc"
#include "harness_span.hpp"
#include "stage2/packet2/loader/gguf.hpp"
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
static void need(bool value,const char* why){if(!value)throw std::runtime_error(why);}
struct Scratch {
 sycl::queue& q;uint32_t n,rows;float* y;uint32_t* status;uint32_t* order;uint32_t* tiles;uint32_t* count;
 Scratch(sycl::queue& queue,uint32_t slots,uint32_t output_rows):q(queue),n(slots),rows(output_rows) {
  y=sycl::malloc_shared<float>(size_t(n)*rows,q);status=sycl::malloc_shared<uint32_t>(n,q);
  order=sycl::malloc_shared<uint32_t>(n,q);tiles=sycl::malloc_shared<uint32_t>(n*5,q);count=sycl::malloc_shared<uint32_t>(16,q);
  need(y&&status&&order&&tiles&&count,"scratch allocation");
 }
 ~Scratch(){sycl::free(y,q);sycl::free(status,q);sycl::free(order,q);sycl::free(tiles,q);sycl::free(count,q);}
};
template<class F,unsigned RW>
Batch issue(sycl::queue&q,Scratch&s,const Case&c,const uint8_t*w,const float*x,const Route*r,uint32_t start,uint32_t n) {
 need(n&&start+n<=s.n,"issue slots");
 xgroup::Bucket bucket{r+start,s.status+start,s.order,s.tiles,s.count,n,c.experts,c.rows,c.rows,4,{}};
 auto first=q.submit([&](sycl::handler&h){auto b=bucket;b.keys=sycl::local_accessor<uint32_t,1>(sycl::range<1>(n),h);h.parallel_for(sycl::nd_range<1>(xgroup::bucket_items,xgroup::bucket_items),b);});
 auto p=xgroup::prepare<F,RW,4,4,128>(w,x+size_t(start)*c.k,s.y+size_t(start)*c.rows,s.order,s.tiles,s.count,c.rows,c.k,c.rb,n,c.experts);
 auto last=q.submit([&](sycl::handler&h){h.parallel_for(p.range,p.kernel);});
 return {{first,last}};
}
template<class F,unsigned RW>
void screen(sycl::queue&q,const Case&c,const uint8_t*w,const std::vector<Route>& captured) {
 const uint32_t slots=5120;Route*r=sycl::malloc_shared<Route>(slots,q);float*x=sycl::malloc_shared<float>(size_t(slots)*c.k,q);
 need(r&&x,"input allocation");std::mt19937 g(4321);std::uniform_real_distribution<float> u(-1,1);
 // Synthetic fixed activations; actual model weights and actual captured route IDs.
 for(size_t i=0;i<size_t(slots)*c.k;++i)x[i]=u(g);
 Scratch paired(q,slots,c.rows),whole(q,slots,c.rows);
 auto launch_pair=[&](uint32_t n){auto a=issue<F,RW>(q,paired,c,w,x,r,0,std::min(n,2560u));
  if(n>2560){auto b=issue<F,RW>(q,paired,c,w,x,r,2560,n-2560);a.events.insert(a.events.end(),b.events.begin(),b.events.end());}return a;};
 auto launch_whole=[&](uint32_t n){return issue<F,RW>(q,whole,c,w,x,r,0,n);};
 auto check=[&](uint32_t n){
  std::fill(paired.y,paired.y+size_t(n)*c.rows,-12345.f);std::fill(whole.y,whole.y+size_t(n)*c.rows,-54321.f);
  std::fill(paired.status,paired.status+n,77u);std::fill(whole.status,whole.status+n,88u);
  launch_pair(n).wait();const uint32_t tail_tiles=*paired.count;
  launch_whole(n).wait();need(!std::memcmp(paired.y,whole.y,size_t(n)*c.rows*4),"all F32 output words512 versus paired256");
  need(!std::memcmp(paired.status,whole.status,n*4),"every output status512 versus paired256");
  for(uint32_t i=0;i<n;++i){bool valid=iq3::valid_route(r[i],c.experts,c.rows,c.rows);need(whole.status[i]==(valid?0u:1u),"host route status oracle");
   for(uint32_t row=0;row<c.rows;++row)if(!valid||row>=r[i].row_count)need(std::bit_cast<uint32_t>(whole.y[size_t(i)*c.rows+row])==0x7fc00000u,"invalid/partial NaN oracle");
  }
  std::printf("GATE %s slots=%u words=%zu statuses=%u whole_tiles=%u paired_tail_tiles=%u PASS\n",c.name,n,size_t(n)*c.rows,n,*whole.count,tail_tiles);
 };
 for(unsigned malformed:{0u,1u}) {
  std::copy(captured.begin(),captured.end(),r);
  if(malformed){r[3].expert_id=c.experts;r[2570].row_begin=3;r[2570].row_count=c.rows-7;r[5100].row_count=c.rows+1;}
  for(uint32_t tokens:{512u,257u,511u})check(tokens*10);
 }
 std::copy(captured.begin(),captured.end(),r);check(slots);
 auto baseline=[&](){return launch_pair(slots);};
 auto candidate=[&](){return launch_whole(slots);};
 Bench bench(q,paired.y,size_t(slots)*c.rows);bench.add("paired256_bucket_plus_tile_span",baseline);bench.add("whole512_bucket_plus_tile_span",candidate,whole.y);bench.run(3,4);
 // Final post-timing status/output gate (not a repeat performance run).
 check(slots);q.wait_and_throw();sycl::free(r,q);sycl::free(x,q);
}
int main(int argc,char**argv){try{
 need(std::getenv("OWNRT_PREFILL_EXPERTS_GDIV")&&std::string(std::getenv("OWNRT_PREFILL_EXPERTS_GDIV"))=="4","explicit GDIV4");
 need(std::getenv("OWNRT_PREFILL_EXPERTS_RLOOP")&&std::string(std::getenv("OWNRT_PREFILL_EXPERTS_RLOOP"))=="4","explicit RLOOP4");
 need(argc==7,"model-dir placement shard-auth tensor routes case-label required");
 const std::filesystem::path modeldir=argv[1];auto plan=iq3::read_plan(argv[2]);iq3::Admission admission;admission.expected=plan;
 std::ifstream auth(argv[3]);iq3::ShardIdentity id;std::vector<std::filesystem::path> paths;
 while(auth>>id.basename>>id.bytes>>id.dev>>id.ino>>id.mtime_ns>>id.ctime_ns){admission.shards.push_back(id);paths.push_back(modeldir/id.basename);}need(auth.eof()&&paths.size()==2,"pinned shard admission");
 iq3::Model model(paths,plan,admission);auto it=std::find_if(plan.begin(),plan.end(),[&](const auto&p){return p.name==argv[4];});need(it!=plan.end(),"registered tensor");
 need(it->dimensions.size()==3&&it->dimensions[2]==512,"actual512 expert tensor");
 const uint32_t k=it->dimensions[0],rows=it->dimensions[1],experts=it->dimensions[2];auto layout=iq3::layout(it->type);uint32_t rb=k/layout.elements*layout.bytes;
 need((k==2560&&rows==640)||(k==640&&rows==2560),"actual routed shapes");need(it->bytes==size_t(experts)*rows*rb,"actual packed tensor extent");
 std::vector<Route> routes(5120);std::ifstream input(argv[5],std::ios::binary);input.read(reinterpret_cast<char*>(routes.data()),routes.size()*sizeof(Route));need(bool(input)&&input.peek()==EOF,"exact512 actual routes");
 for(auto r:routes)need(iq3::valid_route(r,experts,rows,rows)&&r.row_begin==0&&r.row_count==rows,"unaltered full captured routes");
 auto dev=sycl::device(sycl::gpu_selector_v);need(dev.get_info<sycl::info::device::local_mem_size>()>=5120*4,"20KiB bucket SLM admission");need(dev.get_info<sycl::info::device::max_work_group_size>()>=512,"bucket workgroup admission");
 sycl::queue q(dev,{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()});
 std::printf("IDENTITY %s tensor=%s type=%u rows=%u k=%u experts=%u model_weights=true synthetic_activations=true historical_synthetic_prompt_routes=true device=%s\n",argv[6],argv[4],unsigned(it->type),rows,k,experts,dev.get_info<sycl::info::device::name>().c_str());
 auto backing=model.slice(it->name,0,it->bytes);backing.verify_backing();uint8_t*w=sycl::malloc_shared<uint8_t>(it->bytes,q);need(w,"weight allocation");std::memcpy(w,backing.data(),it->bytes);backing.verify_backing();
 Case c{argv[6],rows,k,rb,experts,{},{}};
 switch(unsigned(it->type)){
 case 22:screen<xgroup::C8<Kopt<Type::IQ2_S>>,2>(q,c,w,routes);break;
 case 18:screen<xgroup::S32<Iq3Words>,1>(q,c,w,routes);break;
 case 20:screen<xgroup::C8<Kopt<Type::IQ4_NL>>,1>(q,c,w,routes);break;
 case 42:screen<xgroup::S32<Elem<42>>,1>(q,c,w,routes);break;
 default:throw std::runtime_error("unregistered format");}
 q.wait_and_throw();backing.verify_backing();sycl::free(w,q);std::puts("TOTAL FAILS 0");return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"REFUSED: %s\n",e.what());return 1;}}
