// Pure production metadata traversal; no owner, Device or model constructor.
#include "production_control.hpp"
#include <array>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <set>
namespace {
void need(bool value,const char*reason){if(!value)throw std::runtime_error(reason);}
size_t number(const std::string&s){size_t used=0;auto n=std::stoull(s,&used);need(used==s.size(),"numeric metadata");return n;}
struct Input{std::vector<p212::Site> sites;std::map<std::string,p212::Tensor> tensors;std::vector<size_t> commands;};
Input read(const char*path){std::ifstream in(path);need(bool(in),"input missing");Input result;std::string line;
 while(std::getline(in,line)){need(line.size()<512&&result.sites.size()<1500,"input bound");std::istringstream row(line);std::vector<std::string> f;std::string x;while(std::getline(row,x,'\t'))f.push_back(x);need(f.size()==10,"input fields");
 p212::Site s{number(f[0]),f[1],f[2],{}};result.commands.push_back(number(f[3]));need(result.commands.back()<=8,"command bound");
 if(f[4]!="-"){s.weights.push_back(f[4]);need(result.tensors.emplace(f[4],p212::Tensor{f[5],number(f[6]),number(f[7]),unsigned(number(f[9])),number(f[8])}).second,"tensor uniqueness");}
 result.sites.push_back(std::move(s));}
 need(in.eof()&&result.sites.size()==1486&&result.tensors.size()==72,"complete production metadata");return result;}
}
int main(int argc,char**argv){try{
 need(argc==2,"fixed input argument");auto input=read(argv[1]);auto schedule=p212::build_schedule(input.sites,input.tensors);
 std::map<std::string,bool> checks;auto pass=[&](std::string name,bool value){need(value,name.c_str());checks[name]=true;};
 std::vector<size_t> original=schedule.prefix;for(auto&layer:schedule.layers)original.insert(original.end(),layer.sites.begin(),layer.sites.end());
 pass("1479_original_nonfinal_sites",original.size()==1479);std::array<std::vector<p212::Step>,2> paths;
 paths[0]=p213::ordered_steps(schedule,p213::Mode::serial_frozen2);paths[1]=p213::ordered_steps(schedule,p213::Mode::paired_frozen2);
 std::array<size_t,2> pair_count{},empty_count{},command_count{};
 for(unsigned mode=0;mode<2;++mode){std::array<std::vector<size_t>,2> rows;std::map<size_t,unsigned> counts;std::vector<unsigned> serial_rows;
  for(auto step:paths[mode]){need(step.index<input.sites.size(),"step index");need(std::find(schedule.final.begin(),schedule.final.end(),step.index)==schedule.final.end(),"final/decode excluded");
   if(step.kind==p212::StepKind::pair){need(mode==1&&step.row==2&&input.commands[step.index]==1,"pair identity");++pair_count[mode];for(unsigned row=0;row<2;++row){rows[row].push_back(step.index);++counts[step.index];}command_count[mode]+=2;}
   else{need(step.row<2,"row bound");rows[step.row].push_back(step.index);++counts[step.index];serial_rows.push_back(step.row);empty_count[mode]+=input.commands[step.index]==0;command_count[mode]+=input.commands[step.index];}}
  pass("original_chain_both_rows_mode"+std::to_string(mode),rows[0]==original&&rows[1]==original);
  pass("every_original_exactly_twice_mode"+std::to_string(mode),counts.size()==1479&&std::all_of(counts.begin(),counts.end(),[](auto p){return p.second==2;}));
  if(mode==0)pass("serial_all_row0_before_row1",serial_rows==[&]{std::vector<unsigned> v(1479,0);v.insert(v.end(),1479,1);return v;}());
 }
 pass("serial2958_original_steps",paths[0].size()==2958&&pair_count[0]==0);
 pass("paired70_replaces140_original_steps",paths[1].size()==2888&&pair_count[1]==70);
 pass("empty_followers_and_command_multiplicity_identical",empty_count[0]==empty_count[1]&&empty_count[0]>0&&command_count[0]==command_count[1]);
 pass("paired_matches_frozen_P212_traversal",[&]{auto old=p212::ordered_steps(schedule);if(old.size()!=paths[1].size())return false;for(size_t i=0;i<old.size();++i)if(old[i].kind!=paths[1][i].kind||old[i].row!=paths[1][i].row||old[i].index!=paths[1][i].index)return false;return true;}());
 for(unsigned mode=0;mode<2;++mode)for(auto&layer:schedule.layers)if(!layer.paired){size_t last0=0,first1=paths[mode].size();bool seen0=false,seen1=false;for(size_t i=0;i<paths[mode].size();++i){auto&s=paths[mode][i];if(std::find(layer.sites.begin(),layer.sites.end(),s.index)!=layer.sites.end()){if(s.row==0){last0=i;seen0=true;}if(s.row==1){first1=std::min(first1,i);seen1=true;}}}pass("fallback_causal_mode"+std::to_string(mode)+"_layer"+std::to_string(layer.id),seen0&&seen1&&last0<first1);}
 std::vector<uint32_t> routes(960);for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<48;++layer)for(unsigned slot=0;slot<10;++slot)routes[p212::route_offset(row,layer)+slot]=(row*23+layer*31+slot*7)%512;
 auto chronological=p212::chronological_routes(routes);for(size_t i=0;i<960;++i)need(chronological[i]==(i%480/10)*512+routes[i],"route chronology");
 pass("same960_chronological_routes",chronological.size()==960);auto wrong=routes;std::rotate(wrong.begin(),wrong.begin()+480,wrong.end());pass("wrong_row_replay_discriminates",p212::chronological_routes(wrong)!=chronological);
 std::cout<<"{\"schema\":\"packet213.schedule-control.v1\",\"passed\":true,\"device_executed\":false,\"model_executed\":false,\"checks\":{";bool first=true;for(auto&[n,v]:checks){std::cout<<(first?"":",")<<'"'<<n<<"\":true";first=false;}std::cout<<"},\"modes\":[";
 for(unsigned mode=0;mode<2;++mode){std::cout<<(mode?",":"")<<"{\"name\":\""<<(mode?"paired_frozen2":"serial_frozen2")<<"\",\"steps\":[";for(size_t i=0;i<paths[mode].size();++i){auto s=paths[mode][i];std::cout<<(i?",":"")<<"["<<s.index<<','<<s.row<<','<<(s.kind==p212::StepKind::pair?1:0)<<']';}std::cout<<"]}";}std::cout<<"],\"chronological_routes\":[";for(size_t i=0;i<960;++i)std::cout<<(i?",":"")<<chronological[i];std::cout<<"]}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
