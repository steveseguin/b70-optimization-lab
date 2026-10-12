// Coordinator-only binary. CPU preparation never executes this program.
#include "launch_native.hpp"
using namespace p42launch;
struct Params{const uint16_t* in;uint16_t* out;unsigned begin,end;};
static_assert(sizeof(Params)<=1024);
template<int Geometry,bool SG,bool Local,bool Barrier,bool Pointer>class FloorKernel;
template<int G,bool SG,bool Local,bool Barrier,bool Pointer>struct Floor:ownrt::SyclOperation{
 unsigned begin,end;Floor(unsigned a,unsigned b):begin(a),end(b){}
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  Params value{static_cast<const uint16_t*>(p[0]),static_cast<uint16_t*>(p[1]),begin,end};const Params* block=static_cast<const Params*>(p[2]);unsigned n=std::max(end-begin,1u);
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   // This accessor is deliberately unused. Whether codegen removes it is an axis.
   if constexpr(Local){sycl::local_accessor<float,1> unused(1024,h);}
   auto body=[=](unsigned index){Params a;if constexpr(Pointer)a=*block;else a=value;unsigned i=a.begin+index;if(i<a.end)a.out[i]=bf(std::bit_cast<float>(uint32_t(a.in[i])<<16)+1.f);};
   static_assert(sizeof(body)<=1024);
   if constexpr(G==0){
    if constexpr(SG)h.parallel_for<FloorKernel<G,SG,Local,Barrier,Pointer>>(sycl::range<1>(n),[=](sycl::id<1>i)[[sycl::reqd_sub_group_size(32)]]{body(i[0]);});
    else h.parallel_for<FloorKernel<G,SG,Local,Barrier,Pointer>>(sycl::range<1>(n),[=](sycl::id<1>i){body(i[0]);});
   }else{
    constexpr unsigned wg=G==3?256:32;unsigned global=G==1?n*wg:((n+wg-1)/wg)*wg;
    auto work=[=](sycl::nd_item<1>it){if constexpr(Barrier)it.barrier(sycl::access::fence_space::global_and_local);if constexpr(G==1){if(it.get_local_linear_id()==0)body(it.get_group_linear_id());}else body(it.get_global_linear_id());};
    if constexpr(SG)h.parallel_for<FloorKernel<G,SG,Local,Barrier,Pointer>>(sycl::nd_range<1>(global,wg),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{work(it);});
    else h.parallel_for<FloorKernel<G,SG,Local,Barrier,Pointer>>(sycl::nd_range<1>(global,wg),[=](sycl::nd_item<1>it){work(it);});
   }
  });
 }
};
struct Row{std::string label;unsigned n,parts,burst;int geometry;bool sg,local,barrier,pointer,passed;std::string error;std::vector<double> gpu,wall;};
template<int G,bool SG,bool L,bool B,bool P>void measure(Runner&r,const Options&o,unsigned n,unsigned parts,unsigned burst,std::vector<Row>&rows){
 Row row{std::string("g")+std::to_string(G)+"-sg"+std::to_string(SG)+"-l"+std::to_string(L)+"-b"+std::to_string(B)+"-p"+std::to_string(P)+"-n"+std::to_string(n)+"-split"+std::to_string(parts)+"-burst"+std::to_string(burst),n,parts,burst,G,SG,L,B,P,true,"",{}, {}};
 try{check_stop();auto x=r.alloc(n*2),y=r.alloc(n*2);std::vector<uint16_t>input(n),expected(n),output(n);for(unsigned i=0;i<n;++i){input[i]=bf(float(int(i%97)-48)/8);expected[i]=bf(std::bit_cast<float>(uint32_t(input[i])<<16)+1.f);}r.upload(x,input.data(),n*2);
  std::vector<ownrt::Allocation> params;for(unsigned j=0;j<parts;++j){Params v{static_cast<uint16_t*>(r.d.arena.row(x).pointer),static_cast<uint16_t*>(r.d.arena.row(y).pointer),n*j/parts,n*(j+1)/parts};auto a=r.alloc(sizeof v);r.upload(a,&v,sizeof v);params.push_back(a);}
  auto issue=[&](){std::vector<ownrt::Event>es;for(unsigned b=0;b<burst;++b)for(unsigned j=0;j<parts;++j){Floor<G,SG,L,B,P>op(n*j/parts,n*(j+1)/parts);std::array bound{x,y,params[j]};std::array<ownrt::Event,1>dep{es.empty()?0:es.back()};es.push_back(r.d.compute(op,bound,es.empty()?std::span<const ownrt::Event>{}:dep));}return es;};
  auto gate=issue();r.finish(gate.back());r.download(y,output.data(),n*2);if(output!=expected)throw CaseFailure("BF16 byte mismatch");
  for(unsigned rep=0;rep<o.repetitions;++rep){check_stop();auto start=std::chrono::steady_clock::now();auto es=issue();r.finish(es.back());auto end=std::chrono::steady_clock::now();row.wall.push_back(std::chrono::duration<double,std::micro>(end-start).count());row.gpu.push_back(r.event_us(es));r.d.retire_completed_events();}
 }catch(const CaseFailure&e){row.passed=false;row.error=e.what();}
 catch(const sycl::exception&e){if(e.code()!=sycl::errc::kernel_not_supported)throw;row.passed=false;row.error=e.what();}
 std::ostringstream json;json.precision(17);json<<"{\"class\":"<<ownrt::quote(row.label)<<",\"passed\":"<<(row.passed?"true":"false")<<",\"N\":"<<n<<",\"parts\":"<<parts<<",\"burst\":"<<burst<<",\"geometry\":"<<G<<",\"subgroup32\":"<<SG<<",\"unused_local\":"<<L<<",\"barrier\":"<<B<<",\"parameter_pointer\":"<<P<<",\"gpu_us\":"<<array(row.gpu)<<",\"wall_us\":"<<array(row.wall)<<",\"error\":"<<ownrt::quote(row.error)<<"}";
 // Failure is durable before releasing allocations. Storage failure escapes.
 write(o.output/(row.label+".json"),json.str());rows.push_back(std::move(row));r.clear();
}
template<int G,bool SG,bool L,bool B,bool P>void cases(Runner&r,const Options&o,std::vector<Row>&rows){for(unsigned n:{1,32,640,2560,6400,10240,25600})for(unsigned parts:{1,2,4})measure<G,SG,L,B,P>(r,o,n,parts,1,rows);if constexpr(!L&&!B&&!P&&SG)measure<G,SG,L,B,P>(r,o,1,1,1000,rows);}
template<int G,bool SG,bool L,bool B>void pointers(Runner&r,const Options&o,std::vector<Row>&rows){cases<G,SG,L,B,false>(r,o,rows);cases<G,SG,L,B,true>(r,o,rows);}
template<int G,bool SG,bool L>void barriers(Runner&r,const Options&o,std::vector<Row>&rows){pointers<G,SG,L,false>(r,o,rows);if constexpr(G!=0)pointers<G,SG,L,true>(r,o,rows);}
template<int G,bool SG>void locals(Runner&r,const Options&o,std::vector<Row>&rows){barriers<G,SG,false>(r,o,rows);barriers<G,SG,true>(r,o,rows);}
template<int G>void geometry(Runner&r,const Options&o,std::vector<Row>&rows){locals<G,false>(r,o,rows);locals<G,true>(r,o,rows);}
int main(int argc,char**argv){std::filesystem::path out;try{Options o(argc,argv);out=o.output;Runner r(o.card);try{if(o.smoke)return smoke(r,o);std::vector<Row>rows;geometry<0>(r,o,rows);geometry<1>(r,o,rows);geometry<2>(r,o,rows);geometry<3>(r,o,rows);unsigned failed=0;for(auto&v:rows)failed+=!v.passed;write(out/"receipt.json","{\"passed\":"+std::string(failed?"false":"true")+",\"infrastructure_passed\":true,\"device_executed\":true,\"repetitions\":200,\"cases_completed\":"+std::to_string(rows.size())+",\"failed_cases\":"+std::to_string(failed)+"}");return 0;}catch(const std::exception&e){write(out/"failure.json","{\"passed\":false,\"infrastructure_passed\":false,\"error\":"+ownrt::quote(e.what())+"}");throw;}}catch(const std::exception&e){std::cerr<<e.what()<<'\n';try{if(!out.empty())write(out/"failure.json","{\"passed\":false,\"error\":"+ownrt::quote(e.what())+"}");}catch(const std::exception&w){std::cerr<<"FAILED WINDOW: "<<w.what()<<'\n';}return 1;}}
