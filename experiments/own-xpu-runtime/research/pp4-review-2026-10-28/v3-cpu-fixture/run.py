#!/usr/bin/env python3
"""Extract and compile the current exact method, with explicit CPU-only stubs."""
from pathlib import Path
import hashlib,json,subprocess
r=Path(__file__).resolve().parent
src=r.parents[3]/'engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native/engine_bracket.hpp'
# Resolve from known repo root to avoid depending on invocation directory.
src=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native/engine_bracket.hpp')
s=src.read_text();a=s.index('  void refresh_v3(){');start=s.index('{',a);depth=1;b=start+1
while depth:
 if s[b]=='{':depth+=1
 elif s[b]=='}':depth-=1
 b+=1
method=s[a:b]
prefix='''#include <algorithm>
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
'''
tests='''
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
 std::cout<<"PASS "<<count<<" exact refresh_v3 method cases; CPU fixture only, not Engine constructor coverage\\n";return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\\n";return 1;}}
'''
(r/'fixture.cpp').write_text(prefix+method+tests)
(r/'identity.json').write_text(json.dumps({'source':str(src),'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'exact_method_sha256':hashlib.sha256(method.encode()).hexdigest(),'scope':'Exact method extraction with stub metadata/plan fields; not real Engine construction or device initialization'},indent=2)+'\n')
subprocess.run(['g++','-std=c++20','-O0','-Wall','-Wextra','-Werror',str(r/'fixture.cpp'),'-o','/tmp/test_refresh_v3_pipeline'],check=True)
subprocess.run(['/tmp/test_refresh_v3_pipeline'],check=True)
