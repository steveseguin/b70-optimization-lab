// Prepared for coordinator; never invoked during CPU-only preparation.
#include "tiny_native.hpp"
#include "tiny_fixture.hpp"
using namespace p42tiny;using namespace p42launch;
std::string class_keys(const Fixture&f){
 if(f.name=="hc-act-1.fixture")return "hc.a.act,hc.f.act,final.act";
 if(f.name=="ffn-act-1.fixture")return "shexpact";
 if(f.name=="ffn-routed-act-1.fixture")return "expsact";
 if(f.name=="mix-1.fixture")return "hc.a.mix,hc.f.mix,final.mix";
 if(f.name=="moe-combine-1.fixture")return "moe";
 if(f.name=="production-conv-10240-1.fixture.inplace")return "gdn.conv";
 if(f.name=="production-gdn-gated-1.fixture")return "gdn.gated";
 if(f.name=="production-qsa-prepare-1.fixture")return "qsa.prepare";
 if(f.name=="production-qsa-pool-1.fixture"||f.name=="production-pool-position255.fixture")return "qsa.pool";
 return "";
}

std::string difference(const Fixture&a,const Fixture&b){for(int j=0;j<19;++j)if(a.outputs[j])for(size_t k=0;k<a.output_bytes(j).size();++k)if(a.output_bytes(j)[k]!=b.output_bytes(j)[k])return "slot="+std::to_string(j)+" byte="+std::to_string(k)+" incumbent="+std::to_string(a.output_bytes(j)[k])+" candidate="+std::to_string(b.output_bytes(j)[k]);return "";}
void copy_into(Runner&r,const Fixture&f,std::array<ownrt::Allocation,19>&a){for(int j=0;j<19;++j)if(!(f.alias_history&&j==4))r.upload(a[j],f.data[j].data(),f.data[j].size());}
void snapshot(Runner&r,Fixture&f,const std::array<ownrt::Allocation,19>&a){for(int j=0;j<19;++j)if(f.outputs[j])r.download(a[j],f.output_bytes(j).data(),f.output_bytes(j).size());}
ownrt::Event issue(Runner&r,const Fixture&f,const std::array<ownrt::Allocation,19>&a,int impl){if(impl<0)return ng::submit(r.d,f.s,a,{});if(impl==0)return p42tiny::submit<0>(r.d,f.s,a);if(impl==32)return p42tiny::submit<32>(r.d,f.s,a);return p42tiny::submit<256>(r.d,f.s,a);}
int main(int argc,char**argv){std::filesystem::path out;try{Options o(argc,argv);out=o.output;Runner r(o.card);try{if(o.smoke)return smoke(r,o);auto all=fixtures();unsigned gates=0,failed=0,rows=0;std::ostringstream summary;summary<<"{\"rows\":[";
 for(auto&f:all){std::array<ownrt::Allocation,19>a;for(int j=0;j<19;++j)a[j]=f.alias_history&&j==4?a[1]:r.alloc(f.data[j].size());auto reference=f;copy_into(r,f,a);auto control=issue(r,f,a,-1);r.finish(control);snapshot(r,reference,a);
  for(int geometry:{0,32,256}){if(geometry==0&&(f.s.op==ng::gated_norm||f.s.op==ng::prepare||f.s.op==ng::pool))continue;check_stop();bool passed=true,postflight_passed=false;std::string error;std::vector<double>control_gpu,candidate_gpu,control_wall,candidate_wall;std::string name=f.name+"-wg"+std::to_string(geometry);std::ostringstream scenario_rows;scenario_rows<<"[";unsigned scenario_count=0;
   try{copy_into(r,f,a);auto e=issue(r,f,a,geometry);r.finish(e);auto candidate=f;snapshot(r,candidate,a);auto first_diff=difference(reference,candidate);scenario_rows<<"{\"scenario\":0,\"timing_eligible\":false,\"passed\":"<<(first_diff.empty()?"true":"false")<<",\"difference\":"<<ownrt::quote(first_diff)<<"}";++scenario_count;if(!first_diff.empty())throw CaseFailure("device bytes differ "+first_diff);++gates;
    if(f.s.tokens==1)for(int scenario=1;scenario<=4;++scenario){auto poison=f;if(scenario==1)poison.data[18]=Fixture::integer(0);if(scenario==2)poison.data[15]=Fixture::integer(7);if(scenario==3)poison.data[17]=Fixture::integer(poison.s.capacity);if(scenario==4){uint16_t nan=0x7fc1;std::memcpy(poison.data[0].data(),&nan,2);}copy_into(r,poison,a);auto ce=issue(r,poison,a,-1);r.finish(ce);auto oracle=poison;snapshot(r,oracle,a);copy_into(r,poison,a);auto ve=issue(r,poison,a,geometry);r.finish(ve);auto observed=poison;snapshot(r,observed,a);auto diff=difference(oracle,observed);scenario_rows<<",{\"scenario\":"<<scenario<<",\"timing_eligible\":false,\"passed\":"<<(diff.empty()?"true":"false")<<",\"difference\":"<<ownrt::quote(diff)<<"}";++scenario_count;if(!diff.empty())throw CaseFailure("scenario "+std::to_string(scenario)+" "+diff);++gates;}

    // Full existing fixtures gate correctness. Timings use single-token full-size
    // fixtures; no tiny/odd diagnostic fixture contributes a speed verdict.
    if(!class_keys(f).empty())for(unsigned rep=0;rep<200;++rep)for(int arm=0;arm<2;++arm){bool which=bool(arm^(rep&1));copy_into(r,f,a);auto start=std::chrono::steady_clock::now();auto e=issue(r,f,a,which?geometry:-1);r.finish(e);auto end=std::chrono::steady_clock::now();(which?candidate_wall:control_wall).push_back(std::chrono::duration<double,std::micro>(end-start).count());(which?candidate_gpu:control_gpu).push_back(r.event_us({e}));r.d.retire_completed_events();}
    if(!candidate_gpu.empty()){copy_into(r,f,a);auto final_event=issue(r,f,a,geometry);r.finish(final_event);auto postflight=f;snapshot(r,postflight,a);if(!postflight.equal(reference))throw CaseFailure("post-timing device bytes differ "+difference(reference,postflight));postflight_passed=true;++gates;}
   }catch(const CaseFailure&e){passed=false;error=e.what();++failed;}
   scenario_rows<<"]";std::ostringstream row;row<<"{\"class\":"<<ownrt::quote(name)<<",\"klass\":"<<ownrt::quote(class_keys(f))<<",\"candidate\":"<<ownrt::quote(geometry==0?"p42.tiny.range":geometry==32?"p42.tiny.wg32":"p42.tiny.wg256")<<",\"timing_eligible\":"<<(!class_keys(f).empty()?"true":"false")<<",\"in_place_history\":"<<(f.alias_history?"true":"false")<<",\"op\":"<<f.s.op<<",\"width\":"<<f.s.width<<",\"capacity\":"<<f.s.capacity<<",\"flags\":"<<f.s.flags<<",\"position\":"<<*reinterpret_cast<const int*>(f.data[17].data())<<",\"tokens\":"<<f.s.tokens<<",\"geometry\":"<<geometry<<",\"passed\":"<<(passed?"true":"false")<<",\"error\":"<<ownrt::quote(error)<<",\"postflight_passed\":"<<(postflight_passed?"true":"false")<<",\"byte_scenarios\":"<<scenario_rows.str()<<",\"control_gpu_us\":"<<array(control_gpu)<<",\"candidate_gpu_us\":"<<array(candidate_gpu)<<",\"control_wall_us\":"<<array(control_wall)<<",\"candidate_wall_us\":"<<array(candidate_wall)<<"}";
   write(out/(name+".json"),row.str());summary<<(rows++?",":"")<<row.str();
  }r.clear();
 }
 summary<<"],\"infrastructure_passed\":true}";write(out/"summary.json",summary.str());write(out/"receipt.json","{\"passed\":"+std::string(failed?"false":"true")+",\"infrastructure_passed\":true,\"device_executed\":true,\"byte_identity_checks\":"+std::to_string(gates)+",\"failed_cases\":"+std::to_string(failed)+",\"cases_completed\":"+std::to_string(rows)+"}");return 0;
 }catch(const std::exception&e){write(out/"failure.json","{\"passed\":false,\"infrastructure_passed\":false,\"error\":"+ownrt::quote(e.what())+"}");throw;}}catch(const std::exception&e){std::cerr<<e.what()<<'\n';try{if(!out.empty())write(out/"failure.json","{\"passed\":false,\"error\":"+ownrt::quote(e.what())+"}");}catch(const std::exception&w){std::cerr<<"FAILED WINDOW: "<<w.what()<<'\n';}return 1;}}
