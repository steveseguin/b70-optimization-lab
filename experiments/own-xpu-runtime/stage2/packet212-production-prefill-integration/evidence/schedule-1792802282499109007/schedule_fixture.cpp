// Pure CPU selector fixture: no Device, Weights, runtime backend or model files.
#include "production_schedule.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>

namespace {
void check(bool ok,const char*message){if(!ok)throw std::runtime_error(message);}
size_t number(const std::string&s){size_t used=0;auto n=std::stoull(s,&used);check(used==s.size(),"numeric metadata");return n;}
std::vector<std::string> fields(const std::string&s){std::vector<std::string> v;std::istringstream in(s);std::string x;while(std::getline(in,x,'\t'))v.push_back(x);return v;}
struct Inputs {std::vector<p212::Site> sites;std::map<std::string,p212::Tensor> tensors;std::vector<size_t> commands;};
Inputs read(const char*path){std::ifstream in(path);check(bool(in),"fixture metadata missing");Inputs value;std::string line;
 while(std::getline(in,line)){check(line.size()<512&&value.sites.size()<1500,"fixture metadata bound");auto f=fields(line);check(f.size()==10,"fixture metadata columns");
  p212::Site site{number(f[0]),f[1],f[2],{}};value.commands.push_back(number(f[3]));check(value.commands.back()<=8,"capture command bound");
  if(f[4]!="-"){site.weights.push_back(f[4]);check(value.tensors.emplace(f[4],p212::Tensor{f[5],number(f[6]),number(f[7]),6,number(f[8])}).second,"unique tensor binding");check(number(f[9])==6,"recorded variant");}
  else check(f[5]=="-"&&f[6]=="0"&&f[7]=="0"&&f[8]=="0"&&f[9]=="0","nonprojection metadata");
  value.sites.push_back(std::move(site));
 }check(in.eof()&&value.sites.size()==1486&&value.tensors.size()==72,"complete actual input inventory");return value;
}
struct Event{std::string kind;size_t site;int row;};
}
int main(int argc,char**argv){try{
 check(argc==2,"only fixed metadata path accepted");auto input=read(argv[1]);auto schedule=p212::build_schedule(input.sites,input.tensors);
 std::map<std::string,bool> checks;auto pass=[&](const std::string&n,bool v){check(v,n.c_str());checks[n]=true;};
 auto rejects=[&](const std::string&n,auto operation){bool refused=false;try{operation();}catch(const std::exception&){refused=true;}pass(n,refused);};
 pass("prefix_actual_begin_embedding_streams",schedule.prefix==std::vector<size_t>{0,1,2});
 std::vector<std::string> final;for(auto i:schedule.final)final.push_back(input.sites[i].label);
 pass("final_head_argmax_commit_excluded",final==std::vector<std::string>{"final.norm","final.low","final.gate","final.mix","logits","argmax","commit.final"});
 std::vector<Event> events;std::array<std::vector<size_t>,2> row_chains;std::map<size_t,unsigned> logical;size_t empty=0,commands=0,m1=0,pairs=0;
 auto one=[&](size_t i,unsigned row){events.push_back({"m1",i,int(row)});row_chains[row].push_back(i);++logical[i];++m1;commands+=input.commands[i];empty+=input.commands[i]==0;};
 auto pair=[&](size_t i){check(input.commands[i]==1,"pair replaces exactly one prepared command per row");events.push_back({"pair",i,-1});for(unsigned r=0;r<2;++r){row_chains[r].push_back(i);++logical[i];}++pairs;};
 for(const auto&step:p212::ordered_steps(schedule)){if(step.kind==p212::StepKind::site){check(step.row<2,"ordinary row identity");one(step.index,step.row);}else{check(step.row==2,"paired row sentinel");pair(step.index);}}
 unsigned qsa=0,gdn=0,paired=0;std::vector<size_t> expected=schedule.prefix;
 for(const auto& layer:schedule.layers){expected.insert(expected.end(),layer.sites.begin(),layer.sites.end());
  if(layer.gdn)++gdn;else{++qsa;pass("qsa_layer_"+std::to_string(layer.id),(layer.id+1)%4==0);}
  if(layer.paired)++paired;
 }
 pass("exact_production_types",gdn==36&&qsa==12&&paired==35&&!schedule.layers[2].paired&&schedule.layers[2].gdn);
 pass("seventy_pairs_replace140_original_sites",pairs==70&&schedule.pair_sites==70&&schedule.skipped_originals==140);
 pass("both_row_chains_exact_original_order",row_chains[0]==expected&&row_chains[1]==expected);
 pass("all1479_nonfinal_sites_twice",expected.size()==1479&&logical.size()==1479&&std::all_of(logical.begin(),logical.end(),[](auto x){return x.second==2;}));
 pass("all_other_m1_sites_exactly_once_per_row",m1==2*(1479-70));
 size_t expected_empty=0,expected_commands=0;for(auto i:expected){expected_empty+=2*(input.commands[i]==0);expected_commands+=2*input.commands[i];}
 pass("zero_command_followers_preserved",empty==expected_empty&&empty>0);
 pass("prepared_command_multiplicity_accounted",commands+2*pairs==expected_commands);
 for(const auto&layer:schedule.layers){size_t last0=0,first1=events.size();bool a=false,b=false;
  for(size_t n=0;n<events.size();++n)if(std::find(layer.suffix.begin(),layer.suffix.end(),events[n].site)!=layer.suffix.end()){
   if(events[n].row==0){last0=n;a=true;}if(events[n].row==1){first1=std::min(first1,n);b=true;}}
  pass("causal_suffix_layer_"+std::to_string(layer.id),a&&b&&last0<first1);
 }
 auto ple=std::find_if(input.sites.begin(),input.sites.end(),[](auto&s){return s.label=="blk.1.ple.lookup";});
 pass("actual_ple_lookup_slot_retained",ple!=input.sites.end()&&logical[ple->index]==2&&input.commands[ple->index]==0);
 for(auto [start,n]:std::array<std::pair<size_t,size_t>,5>{{{0,3},{30,33},{32,35},{4093,4096},{343,370}}}){p212::admit_chunk(start,n,4096);}
 pass("nonfinal_and_capacity_admissions",true);
 rejects("cross32_refused",[]{p212::admit_chunk(31,40,4096);});
 rejects("final_token_consumption_refused",[]{p212::admit_chunk(0,2,4096);});
 rejects("decode_position_refused",[]{p212::admit_chunk(33,33,4096);});
 rejects("past_capacity_refused",[]{p212::admit_chunk(4096,4096,4096);});
 rejects("oversize_input_refused",[]{p212::admit_chunk(0,4097,4096);});
 rejects("wrong_context_refused",[]{p212::admit_chunk(0,3,128);});
 std::vector<uint32_t> routes(960);for(unsigned r=0;r<2;++r)for(unsigned l=0;l<48;++l)for(unsigned k=0;k<10;++k)routes[p212::route_offset(r,l)+k]=(r*23+l*31+k*7)%512;routes[0]=511;
 auto chronological=p212::chronological_routes(routes);for(unsigned r=0;r<2;++r)for(unsigned l=0;l<48;++l)for(unsigned k=0;k<10;++k){size_t i=(r*48+l)*10+k;check(chronological[i]==l*512+routes[i],"chronological route identity");}
 pass("actual2x48x10_chronology",true);auto reordered=routes;std::rotate(reordered.begin(),reordered.begin()+480,reordered.end());pass("wrong_row_order_discriminates",p212::chronological_routes(reordered)!=chronological);
 rejects("incomplete_route_log_refused",[]{p212::chronological_routes(std::vector<uint32_t>(959));});
 rejects("expert512_refused",[&]{auto v=routes;v[57]=512;p212::chronological_routes(v);});
 rejects("row2_slot_refused",[]{p212::route_offset(2,0);});rejects("layer48_slot_refused",[]{p212::route_offset(0,48);});
 auto bad_tensor=[&](std::string name,auto change){rejects(name,[&]{auto t=input.tensors;change(t);p212::build_schedule(input.sites,t);});};
 bad_tensor("q6_wrong_stride_refused",[](auto&t){++t.at("blk.0.attn_qkv.weight").stored_bytes;});
 bad_tensor("q6_wrong_variant_refused",[](auto&t){t.at("blk.0.attn_qkv.weight").variant=7;});
 bad_tensor("q6_wrong_columns_refused",[](auto&t){t.at("blk.0.attn_qkv.weight").columns=6144;});
 bad_tensor("q8_cannot_silently_pair",[](auto&t){for(auto name:{"blk.2.attn_qkv.weight","blk.2.attn_gate.weight"}){auto&x=t.at(name);x.type="Q6_K";x.stored_bytes=x.rows*3380;}});
 rejects("duplicate_site_refused",[&]{auto s=input.sites;s[7].label=s[6].label;p212::build_schedule(s,input.tensors);});
 rejects("index_drift_refused",[&]{auto s=input.sites;++s[7].index;p212::build_schedule(s,input.tensors);});
 rejects("missing_final_refused",[&]{auto s=input.sites;s.resize(schedule.final.front());p212::build_schedule(s,input.tensors);});
 bad_tensor("q8_wrong_layout_refused",[](auto&t){--t.at("blk.2.attn_qkv.weight").stored_bytes;});
 bad_tensor("mismatched_projection_types_refused",[](auto&t){t.at("blk.0.attn_gate.weight").type="Q8_0";});
 rejects("missing_qkv_refused",[&]{auto s=input.sites;s[schedule.layers[0].qkv].label+=".absent";p212::build_schedule(s,input.tensors);});
 rejects("missing_z_refused",[&]{auto s=input.sites;s[schedule.layers[0].z].label+=".absent";p212::build_schedule(s,input.tensors);});
 rejects("missing_layer_refused",[&]{auto s=input.sites;std::erase_if(s,[](auto&x){return x.label.starts_with("blk.1.");});for(size_t i=0;i<s.size();++i)s[i].index=i;p212::build_schedule(s,input.tensors);});
 rejects("final_interleaving_refused",[&]{auto s=input.sites;std::swap(s[33],s.back());for(size_t i=0;i<s.size();++i)s[i].index=i;p212::build_schedule(s,input.tensors);});
 rejects("block_order_refused",[&]{auto s=input.sites;std::swap(s[3],s[33]);for(size_t i=0;i<s.size();++i)s[i].index=i;p212::build_schedule(s,input.tensors);});
 std::cout<<"{\"schema\":\"packet212.schedule-proof.v1\",\"passed\":true,\"runtime_executed\":false,\"device_executed\":false,\"model_executed\":false,\"logical_sites\":"<<input.sites.size()<<",\"nonfinal_sites\":"<<expected.size()<<",\"m1_site_invocations\":"<<m1<<",\"paired_calls\":"<<pairs<<",\"empty_site_invocations\":"<<empty<<",\"recorded_m1_commands\":"<<commands<<",\"checks\":{";
 bool first=true;for(auto&[n,v]:checks){std::cout<<(first?"":",")<<'"'<<n<<"\":true";first=false;}std::cout<<"},\"events\":[";
 for(size_t i=0;i<events.size();++i){auto&e=events[i];std::cout<<(i?",":"")<<"{\"kind\":\""<<e.kind<<"\",\"site\":"<<e.site<<",\"row\":"<<e.row<<"}";}std::cout<<"],\"chronological_routes\":[";for(size_t i=0;i<chronological.size();++i)std::cout<<(i?",":"")<<chronological[i];std::cout<<"]}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
