#include "reset_descriptor.hpp"
#include <cassert>
#include <fstream>
#include <iostream>
namespace r=ownrt::ring_next::reset;namespace fs=std::filesystem;
template<class F>void refusal(F fn){bool refused=false;try{fn();}catch(const std::exception&){refused=true;}assert(refused);}
std::string descriptor(const fs::path& destination){return "{\"schema\":\"ownrt.ring-reset-request.v1\",\"stage_id\":0,\"global_sequence\":5,\"previous_epoch\":0,\"next_epoch\":1,\"previous_request_sha256\":\""+std::string(64,'a')+"\",\"next_request_sha256\":\""+std::string(64,'b')+"\",\"destination\":\""+destination.string()+"\",\"oracle\":\"\"}";}
void write(const fs::path& path,const std::string& text){std::ofstream out(path);out<<text;assert(out.good());}
int main(int argc,char** argv){assert(argc==2);fs::path root=fs::absolute(argv[1]);assert(fs::create_directory(root));const auto file=root/"reset-5.json",destination=root/"requests"/"request-1";const auto text=descriptor(destination);write(file,text);
 auto parsed=r::load(file,root,0,std::string(64,'a'),0,5,"");assert(parsed.next_epoch==1&&parsed.destination==destination&&parsed.raw==text&&r::digest(parsed.next_request)[0]==0xbb);
 for(const auto& bad:std::vector<std::string>{text+"{}",text.substr(0,text.size()-1)+",\"stage_id\":0}",text.substr(0,text.size()-1)+",\"extra\":0}","[]",std::string(8193,' '),"{\"schema\":true}"})refusal([&]{r::parse(bad);});
 auto replace=[&](const std::string& from,const std::string& to){auto bad=text;auto at=bad.find(from);assert(at!=std::string::npos);bad.replace(at,from.size(),to);return bad;};
 for(const auto& bad:std::vector<std::string>{replace("\"stage_id\":0","\"stage_id\":-1"),replace("\"stage_id\":0","\"stage_id\":00"),replace("\"stage_id\":0","\"stage_id\":2147483648"),replace("\"next_epoch\":1","\"next_epoch\":2"),replace("\"previous_epoch\":0","\"previous_epoch\":18446744073709551616"),replace("\"oracle\":\"\"","\"oracle\":\"\\u0000\""),replace(std::string(64,'b'),std::string(64,'a'))})refusal([&]{r::parse(bad);});
 refusal([&]{r::load(file,root,1,std::string(64,'a'),0,5,"");});refusal([&]{r::load(file,root,0,std::string(64,'a'),1,5,"");});refusal([&]{r::load(file,root,0,std::string(64,'a'),0,6,"");});refusal([&]{r::load(file,root,0,std::string(64,'a'),0,5,"different");});
 auto fifo=root/"fifo";assert(!::mkfifo(fifo.c_str(),0600));refusal([&]{r::read(fifo);});write(root/"large",std::string(8193,'x'));refusal([&]{r::read(root/"large");});
 fs::create_symlink(file,root/"metadata-link");refusal([&]{r::read(root/"metadata-link");});
 fs::create_symlink(root/"missing",root/"dangling");refusal([&]{r::destination(root/"dangling",root);});refusal([&]{r::destination(root/"dangling"/"child",root);});refusal([&]{r::destination(root.parent_path()/"outside",root);});refusal([&]{r::destination(root/"a"/".."/"b",root);});
 // Source-only candidate extension: preserve all existing v1 adverse cases above.
 auto v2=descriptor(destination);auto swap=[&](std::string& x,const std::string&a,const std::string&b){auto i=x.find(a);assert(i!=std::string::npos);x.replace(i,a.size(),b);};
 swap(v2,"ownrt.ring-reset-request.v1","ownrt.dedicated-reset-request.v2");swap(v2,"stage_id","owner_index");v2.pop_back();
 v2+=",\"role\":\"target\",\"suite_sha256\":\""+std::string(64,'c')+"\",\"prompt_sha256\":\""+std::string(64,'d')+"\",\"prompt_index\":1,\"prompt_tokens\":1677}";
 r::PromptAuthority selected{std::string(64,'c'),std::string(64,'d'),1,1677};write(file,v2);
 auto next=r::load_dedicated(file,root,0,std::string(64,'a'),0,5,selected,true);assert(next.dedicated&&next.role=="target"&&next.prompt.tokens==1677&&next.stage==0);
 refusal([&]{r::parse(v2);});refusal([&]{r::parse(text,true);});refusal([&]{r::load_dedicated(file,root,0,std::string(64,'a'),0,5,selected,false);});
 for(int field=0;field<4;++field){auto wrong=selected;if(field==0)wrong.suite_sha[0]='e';if(field==1)wrong.prompt_sha[0]='e';if(field==2)wrong.index=2;if(field==3)wrong.tokens=178;refusal([&]{r::load_dedicated(file,root,0,std::string(64,'a'),0,5,wrong,true);});}
 refusal([&]{r::load_dedicated(file,root,1,std::string(64,'a'),0,5,selected,true);});refusal([&]{r::load_dedicated(file,root,0,std::string(64,'a'),-1,5,selected,true);});refusal([&]{r::load_dedicated(file,root,0,std::string(64,'a'),0,6,selected,true);});
 auto bad=[&](const std::string&a,const std::string&b){auto x=v2;swap(x,a,b);refusal([&]{r::parse(x,true);});};
 bad("\"prompt_index\":1","\"prompt_index\":12");bad("\"prompt_tokens\":1677","\"prompt_tokens\":2");bad("\"prompt_tokens\":1677","\"prompt_tokens\":262145");bad("\"role\":\"target\"","\"role\":\"unknown\"");bad("\"oracle\":\"\"","\"oracle\":\"output-token-file\"");
 auto provider=v2;swap(provider,"\"role\":\"target\"","\"role\":\"provider\"");write(file,provider);auto pd=r::load_dedicated(file,root,0,std::string(64,'a'),-1,5,selected,true);assert(pd.stage==-1&&pd.role=="provider");refusal([&]{r::load_dedicated(file,root,0,std::string(64,'a'),0,5,selected,true);});swap(provider,"\"owner_index\":0","\"owner_index\":1");refusal([&]{r::parse(provider,true);});
 auto added=v2;added.pop_back();added+=",\"prompt_path\":\"unregistered\"}";refusal([&]{r::parse(added,true);});write(file,text);
 fs::create_directories(destination);refusal([&]{r::load(file,root,0,std::string(64,'a'),0,5,"");});
 std::cout<<"PASS ring reset exact JSON/epoch/sequence/owner binding, bounded regular metadata, FIFO/large/duplicate/stale/symlink/outside/existing destination refusals\n";
}
