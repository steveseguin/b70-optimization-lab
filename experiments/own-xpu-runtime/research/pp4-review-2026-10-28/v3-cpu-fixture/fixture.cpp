#include <algorithm>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <stdexcept>
#include <iostream>
static void require(bool p,const std::string&m){if(!p)throw std::runtime_error(m);}
struct Fixture {
 struct Args {bool pipe=false,mini=false,legacy=false;int rank=0,draft_rank=1,target_split=0;bool pipeline_enabled()const{return pipe;}}a;
 struct {std::map<std::string,std::string> choices;}sealed_selection;
 struct Launch {std::string label;};struct {std::vector<Launch> launches;}p;
 bool resident=true,v3_extended=false,v3_active=false,kio_active=false,prepare_async=false,export_copy=true,expert_diet=false;
 int v3_first=24,v3_end=26,v3_store_end=26,checks=0;
 std::vector<uint8_t>v3_skip_half;std::vector<size_t>v3_sites,v3_store_sites;std::set<std::string>v3_private;
 std::string head_choice()const{return "production";}
 void v3_check_plan(){++checks;}
  void refresh_v3(){
    auto pick=[&](const char* key,const char* fallback){auto i=sealed_selection.choices.find(key);return i==sealed_selection.choices.end()?std::string(fallback):i->second;};
    const auto layers=pick("rank0_layers","0-23"),mode=pick("boundary","none"),io=pick("kernel_io","copy"),prep=pick("rank0_prepare","sync"),exp=pick("boundary_export","copy"),gateup=pick("expert_gateup","production");
    require(layers=="0-23"||layers=="0-25"||layers=="0-26","packet188 rank0_layers domain");
    require(mode=="none"||mode=="rank0"||mode=="rank0-k3","packet188 boundary domain");
    require(io=="copy"||io=="kernel","packet188 kernel_io domain");require(prep=="sync"||prep=="async","packet188 rank0_prepare domain");
    require(exp=="copy"||exp=="kernel","packet189 boundary_export domain");
    require(gateup=="production"||gateup=="diet","packet194 expert_gateup domain");
    require(layers=="0-26"||!sealed_selection.choices.contains("expert_gateup"),"packet194 expert_gateup is a k3-storage key");
    v3_extended=layers!="0-23";v3_active=mode!="none";
    require(!v3_active||v3_extended,"V3 boundary requires an extended rank-0 layout");
    require(mode!="rank0-k3"||layers=="0-26","packet188 k3 boundary requires rank0_layers 0-26");
    require(layers=="0-26"||(io=="copy"&&prep=="sync"&&exp=="copy"),"packet188 trims require the k3 storage (pinned kernel-io staging)");
    require(layers!="0-26"||v3_active,"packet188 k3 storage runs a boundary in every view");
    require(layers!="0-26"||sealed_selection.choices.contains("boundary_export"),"packet189 k3 storage selections name boundary_export explicitly");
    kio_active=io=="kernel";prepare_async=prep=="async";export_copy=exp=="copy";expert_diet=gateup=="diet";
    if(v3_extended)require(resident&&!a.legacy&&a.draft_rank==1&&a.target_split==0&&head_choice()=="production",
      "V3 layout requires the resident prepared path, the rank-1 draft, the 24/24 base split and the full target head on rank 1");
    const int mini=a.mini?1:0;
    v3_first=a.mini?2:24;
    v3_store_end=v3_first+(layers=="0-26"?3-mini:layers=="0-25"?2-mini:0);
    v3_end=v3_first+(mode=="rank0-k3"?3-mini:2-mini); // execution set [v3_first, v3_end); U views keep the V3 set
    v3_skip_half.assign(p.launches.size(),0);v3_sites.clear();v3_store_sites.clear();
    if(a.pipeline_enabled()){
      // The general pipeline owns explicit disjoint layer ranges. It does not
      // use the legacy two-rank duplicated island or its separate boundary op.
      require(!v3_extended&&!v3_active&&!kio_active&&!prepare_async&&export_copy&&!expert_diet,
              "general pipeline requires neutral legacy V3 boundary selection");
      return;
    }
    for(size_t i=0;i<p.launches.size();++i){const auto& l=p.launches[i];if(!l.label.starts_with("blk."))continue;
      const int layer=std::stoi(l.label.substr(4));const bool stored=layer>=v3_first&&layer<v3_store_end,moved=layer>=v3_first&&layer<v3_end;
      if(a.rank==0&&layer>=v3_first){require(v3_extended&&stored,"rank 0 holds a moved layer without the V3 layout");v3_skip_half[i]=1;v3_store_sites.push_back(i);if(moved)v3_sites.push_back(i);}
      if(a.rank==1&&moved&&v3_active)v3_skip_half[i]=1;
    }
    if(a.rank==0&&v3_extended)v3_check_plan();
    if(a.rank==0&&!v3_extended)require(v3_sites.empty()&&v3_store_sites.empty()&&v3_private.empty(),"production layout holds no moved layer");
  }
};
static Fixture make(bool pipe,int rank,int first,int end){Fixture f;f.a.pipe=pipe;f.a.rank=rank;for(int n=first;n<end;++n)f.p.launches.push_back({"blk."+std::to_string(n)+".gdn"});return f;}
static int count=0;
static void neutral(int rank,int first,int end){auto f=make(true,rank,first,end);f.v3_skip_half.assign(200,1);f.v3_sites={123};f.v3_store_sites={456};f.refresh_v3();require(f.v3_skip_half.size()==f.p.launches.size(),"skip shape");require(std::all_of(f.v3_skip_half.begin(),f.v3_skip_half.end(),[](auto v){return v==0;}),"pipeline layer skipped");require(f.v3_sites.empty()&&f.v3_store_sites.empty()&&!f.checks,"legacy island in pipeline");++count;}
static void reject(Fixture f){bool refused=false;try{f.refresh_v3();}catch(const std::exception&){refused=true;}require(refused,"incompatible selection accepted");++count;}
int main(){try{
 neutral(0,0,25);neutral(0,0,31);neutral(0,27,40);neutral(1,25,40);neutral(1,40,48);neutral(0,0,48);
 for(const auto&kv:std::vector<std::pair<std::string,std::string>>{{"rank0_layers","0-25"},{"rank0_layers","0-26"},{"boundary","rank0"},{"boundary","rank0-k3"},{"kernel_io","kernel"},{"rank0_prepare","async"},{"boundary_export","kernel"},{"expert_gateup","diet"},{"rank0_layers","garbage"},{"boundary","garbage"}}){auto f=make(true,0,0,25);f.sealed_selection.choices[kv.first]=kv.second;reject(f);}
 // A fully coherent legacy V3 choice must also be refused for general pipeline.
 {auto f=make(true,0,0,27);f.sealed_selection.choices={{"rank0_layers","0-26"},{"boundary","rank0-k3"},{"kernel_io","kernel"},{"rank0_prepare","async"},{"boundary_export","kernel"},{"expert_gateup","diet"}};reject(f);}
 // Preserve legacy behavior: neutral rank0 ownership crossing layer24 refuses.
 reject(make(false,0,0,25));
 {auto f=make(false,0,0,24);f.refresh_v3();require(f.v3_sites.empty(),"legacy neutral lower layers changed");++count;}
 // Legacy rank1 retains its normal ownership; pipeline carve-out must not mask it.
 {auto f=make(false,1,24,48);f.refresh_v3();require(std::all_of(f.v3_skip_half.begin(),f.v3_skip_half.end(),[](auto v){return v==0;}),"legacy rank1 skipped");++count;}
 std::cout<<"PASS "<<count<<" exact refresh_v3 method cases; CPU fixture only, not Engine constructor coverage\n";return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
