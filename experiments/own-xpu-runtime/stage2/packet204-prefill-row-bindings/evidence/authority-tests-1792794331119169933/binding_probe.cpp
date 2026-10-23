#include "row_bindings.hpp"
#include <charconv>
#include <iostream>
#include <functional>
using namespace p204;
namespace {
struct Fixture {
  uint64_t next=1;
  std::vector<Row> rows;
  std::map<std::string,Shared> shared;
  Region region(size_t bytes,Scalar scalar){return {next++,0,bytes,bytes,scalar};}
  Fixture(size_t start=342,size_t width=2,size_t context=4096) {
    for(const auto& [n,r]:persistent_requirements(context))shared.emplace(n,Shared{region(r.bytes,r.scalar),r.lifetime});
    for(auto n:{"active","error","global_position"})shared.emplace(n,Shared{region(4,Scalar::u32),Lifetime::global_control});
    shared.emplace("ple_metadata",Shared{region(280,Scalar::i64),Lifetime::immutable});
    shared.emplace("operator-scratch",Shared{region(8*1024*1024,Scalar::opaque),Lifetime::shared_scratch});
    shared.emplace("representative-weight",Shared{region(1024,Scalar::opaque),Lifetime::immutable});
    History history{43164,22843};
    for(size_t i=0;i<width;++i){int32_t token=i?248046:37574;
      rows.push_back({uint32_t(start+i),token,history,{history.old1,token},
        region(20480,Scalar::bf16),region(4,Scalar::i32),region(4,Scalar::u32),
        region(5120,Scalar::bf16),region(5120,Scalar::bf16),region(128,Scalar::i64),region(5760,Scalar::opaque)});
      history=rows.back().after;
    }
  }
  Bindings bind(size_t context=4096,size_t visible=370){return {rows,shared,context,visible};}
};
template<class F> bool refuses(F f){try{f();return false;}catch(const std::invalid_argument&){return true;}}
void run_all(Schedule& s,size_t width){for(size_t l=0;l<48;++l)for(size_t r=0;r<width;++r){auto e=s.required_dependency();s.begin(l,r,e);s.finish(e+1,e+2);}}
std::map<std::string,bool> checks() {
  std::map<std::string,bool> c;
  Fixture f;auto b=f.bind();Schedule s(b);
  c["persistent_inventory_122"]=persistent_requirements(4096).size()==122;
  c["duplicate_persistent_state_refused"]=refuses([&]{auto x=f;x.shared.emplace("row1.blk.0.gdn.state",Shared{x.region(1572864,Scalar::bf16),Lifetime::persistent});x.bind();});
  c["row_streams_distinct"]=!overlaps(b.row(0).streams,b.row(1).streams);
  c["commit_before_layers_refused"]=refuses([&]{s.commit(999,true,true);});
  c["checkpoint_before_commit_refused"]=!s.publication_ready();
  c["row1_before_row0_refused"]=refuses([&]{s.begin(0,1,0);});
  s.begin(0,0,0);
  c["concurrent_scratch_lease_refused"]=refuses([&]{s.begin(0,0,0);});
  c["route_capture_before_consumer_refused"]=refuses([&]{s.finish(2,1);});
  s.finish(2,3);
  c["missing_native_dependency_refused"]=refuses([&]{s.begin(0,1,2);});
  Schedule dependency(b);dependency.begin(0,0,100);c["terminal_before_dependency_refused"]=refuses([&]{dependency.finish(1,1);});
  s.begin(0,1,3);s.finish(4,5);
  for(size_t l=1;l<48;++l)for(size_t r=0;r<2;++r){auto e=s.required_dependency();s.begin(l,r,e);s.finish(e+1,e+2);}
  c["undrained_commit_refused"]=refuses([&]{s.commit(s.required_dependency()-1,true,true);});
  c["cache_readers_live_refused"]=refuses([&]{s.commit(s.required_dependency(),true,false);});
  auto published=s.commit(s.required_dependency(),true,true);
  c["commit_once_exact_history"]=published.position==344 && published.token==248046 && published.history==History{37574,248046} && published.streams_row==1 && s.publication_ready() && refuses([&]{s.commit(999,true,true);});
  Schedule failed(b);failed.begin(0,0,0);failed.fail();
  c["partial_failure_sticky"]=failed.poisoned() && !failed.publication_ready() && refuses([&]{failed.finish(1,2);}) && refuses([&]{failed.commit(999,true,true);}) && refuses([&]{failed.begin(0,0,0);});
  Schedule error(b);run_all(error,2);c["device_error_poisons"]=refuses([&]{error.commit(999,false,true);}) && error.poisoned();
  c["partial_row_alias_refused"]=refuses([&]{auto x=f;auto&r=x.rows[1].streams;r=x.rows[0].streams;r.offset=2;r.allocation_bytes+=2;x.rows[0].streams.allocation_bytes+=2;x.bind();});
  c["row_shared_alias_refused"]=refuses([&]{auto x=f;x.rows[0].streams=x.shared.at("blk.0.gdn.state").region;x.rows[0].streams.bytes=20480;x.bind();});
  c["short_state_refused"]=refuses([&]{auto x=f;x.shared.at("blk.0.gdn.state").region.bytes-=2;x.bind();});
  c["missing_state_refused"]=refuses([&]{auto x=f;x.shared.erase("blk.0.gdn.state");x.bind();});
  c["history_chain_refused"]=refuses([&]{auto x=f;x.rows[1].before.old0++;x.bind();});
  c["capacity_crossing_refused"]=refuses([&]{Fixture x(31);x.bind();});
  c["final_prompt_row_refused"]=refuses([&]{Fixture x(368);x.bind();});
  c["position_gap_refused"]=refuses([&]{auto x=f;x.rows[1].position++;x.bind();});
  c["vocabulary_overflow_refused"]=refuses([&]{auto x=f;x.rows[1].token=248320;x.rows[1].after.old1=248320;x.bind();});
  c["region_overflow_refused"]=refuses([&]{valid({1,SIZE_MAX-1,8,SIZE_MAX,Scalar::opaque});});
  c["typed_alignment_refused"]=refuses([&]{valid({1,1,16,32,Scalar::i64});});
  Fixture single(31,1);auto one=single.bind();Schedule os(one);run_all(os,1);c["single_boundary_tail_commits"]=os.commit(os.required_dependency(),true,true).position==32;
  c["context_extent_exact"]=b.context_extent()==352 && one.context_extent()==32;
  std::array<int32_t,7> ids{0,1,2,3,-1,-1,-1};validate_selected_ids(ids,3,4096,4);
  c["qsa_future_id_refused"]=refuses([&]{auto x=ids;x[3]=4;validate_selected_ids(x,3,4096,4);});
  std::array<int32_t,7> full{0,1,2,3,4,5,6};validate_selected_ids(full,6,4096,4);
  c["qsa_full_capacity_no_sentinel_accepted"]=true;
  c["qsa_nonempty_after_sentinel_refused"]=refuses([&]{auto x=ids;x[6]=0;validate_selected_ids(x,3,4096,4);});
  return c;
}
size_t number(const char* p){size_t n=0;auto e=p+std::char_traits<char>::length(p);auto r=std::from_chars(p,e,n);require(r.ec==std::errc{} && r.ptr==e,"invalid unsigned integer");return n;}
std::array<int64_t,35> metadata(){std::array<int64_t,35> m{};m[0]=INT64_MAX-18;m[1]=INT64_MAX-32;m[2]=INT64_MAX-56;for(int i=0;i<16;++i){m[3+i]=97+i*2;m[19+i]=i*1000;}return m;}
}
int main(int argc,char**argv){try{
  if(argc==2 && std::string(argv[1])=="--self-test"){
    auto c=checks();bool passed=true;for(auto&[k,v]:c)passed&=v;
    std::cout<<"{\"passed\":"<<(passed?"true":"false")<<",\"checks\":{";bool first=true;
    for(auto&[k,v]:c){std::cout<<(first?"":",")<<'"'<<k<<"\":"<<(v?"true":"false");first=false;}std::cout<<"}}\n";return passed?0:1;
  }
  if(argc==6 && std::string(argv[1])=="--plan"){
    auto p=p202::make_plan(number(argv[2]),number(argv[3]),number(argv[4]),number(argv[5]));
    std::cout<<"{\"spans\":[";bool first=true;for(auto&s:p.spans){std::cout<<(first?"":",")<<"{\"start\":"<<s.start<<",\"count\":"<<s.count<<",\"final\":false}";first=false;}std::cout<<"],\"final_position\":"<<p.final_position<<"}\n";return 0;
  }
  if(argc==6 && std::string(argv[1])=="--history"){
    auto tok=number(argv[2]),a=number(argv[3]),b=number(argv[4]),eos=number(argv[5]);require(tok<=INT32_MAX && a<=INT64_MAX && b<=INT64_MAX && eos<=INT64_MAX,"token/history bound");
    auto ids=ple_ids(int32_t(tok),{int64_t(a),int64_t(b)},int64_t(eos),metadata());
    std::cout<<"{\"before\":["<<a<<','<<b<<"],\"after\":["<<b<<','<<tok<<"],\"ids\":[";
    for(size_t i=0;i<ids.size();++i){std::cout<<(i?",":"")<<ids[i];}std::cout<<"]}\n";return 0;
  }
  if(argc==4 && std::string(argv[1])=="--qsa"){
    auto v=qsa_view(number(argv[2]),number(argv[3]));
    std::cout<<"{\"visible_tokens\":"<<v.visible_tokens<<",\"completed_pools\":"<<v.completed_pools<<",\"tail_tokens\":"<<v.tail_tokens<<",\"context_extent\":"<<v.context_extent<<"}\n";return 0;
  }
  throw std::invalid_argument("usage: --self-test | --plan START INPUT_COUNT CONTEXT WIDTH | --history TOKEN OLD0 OLD1 EOS");
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
