#include "fused.hpp"
#include "snapshot/reference.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
namespace fs=std::filesystem;
struct Fixture {
 ng::Shape s;std::array<std::vector<uint8_t>,16>d;std::array<int,16>out{};
 Fixture(const fs::path&p){std::ifstream f(p,std::ios::binary);f.read(reinterpret_cast<char*>(&s),sizeof s);ng::validate(s);
 for(int j=0;j<16;++j){uint32_t n,o;f.read(reinterpret_cast<char*>(&n),4);f.read(reinterpret_cast<char*>(&o),4);if(!n||n>128*1024*1024)throw std::runtime_error("fixture size");d[j].resize(n);out[j]=o;f.read(reinterpret_cast<char*>(d[j].data()),n);if(o)f.seekg(n,std::ios::cur);}if(!f||f.peek()!=EOF)throw std::runtime_error("fixture bytes");}
 ng::Args a(){ng::Args r;for(int j=0;j<16;++j)r.p[j]=d[j].data();return r;}
};
void need(bool b,const std::string&why){if(!b)throw std::runtime_error(why);}
int integrated_chains(const fs::path&dir,std::ofstream&bytes){
 int checks=0;
 for(int tokens:{1,3})for(int kind=0;kind<3;++kind){
  std::vector<std::string> names=kind==0?std::vector<std::string>{"combine-norm-","mix-"}:kind==1?std::vector<std::string>{"conv-10240-","gdn-","gdn-gated-"}:std::vector<std::string>{"qsa-prepare-","qsa-pool-","qsa-select-","qsa-attention-"};
  std::vector<Fixture> ref,cand;for(auto&n:names)ref.emplace_back(dir/(n+std::to_string(tokens)+".fixture"));cand=ref;
  auto execute=[&](std::vector<Fixture>& f,bool fused){
   std::vector<ng::Args>a;for(auto&v:f)a.push_back(v.a());
   if(kind==0)a[1].p[0]=a[0].p[5];
   if(kind==1){a[1].p[0]=a[0].p[3];a[2].p[0]=a[1].p[6];}
   if(kind==2){a[1].p[0]=a[0].p[8];a[2].p[0]=a[0].p[9];a[2].p[1]=a[1].p[7];a[3].p[0]=a[0].p[6];a[3].p[1]=a[0].p[7];a[3].p[2]=a[1].p[4];a[3].p[3]=a[1].p[5];a[3].p[4]=a[2].p[2];}
   if(!fused){for(size_t j=0;j<f.size();++j)ng::reference::cpu(f[j].s,a[j]);}
   else{std::vector<fusion::Site> sites;for(size_t j=0;j<f.size();++j){auto shape=f[j].s;sites.emplace_back(shape,a[j]);if(shape.op==ng::attention_score){shape.op=ng::attention_softmax;sites.emplace_back(shape,a[j]);shape.op=ng::attention_value;sites.emplace_back(shape,a[j]);}}fusion::cpu_chain(sites.data(),sites.size());}
  };
  execute(ref,false);execute(cand,true);
  for(size_t j=0;j<ref.size();++j)for(int slot=0;slot<16;++slot)if(ref[j].out[slot]){need(ref[j].d[slot]==cand[j].d[slot],"integrated chain kind="+std::to_string(kind)+" stage="+std::to_string(j)+" slot="+std::to_string(slot));bytes.write(reinterpret_cast<char*>(cand[j].d[slot].data()),cand[j].d[slot].size());}
  ++checks;
 }
 return checks;
}
int rejected_controls(const fs::path&dir){
 int checks=0;for(auto name:{"route-varied.fixture","qsa-attention-3.fixture"})for(int mode=0;mode<4;++mode){Fixture ref(dir/name),cand=ref;
 auto adjust=[&](Fixture& f){if(mode==0)f.a().i(15)[1]=0;if(mode==1)f.a().i(15)[2]=1;if(mode==2)f.a().i(15)[0]=-1;if(mode==3&&f.s.op==ng::attention_score)f.a().i(4)[(f.s.tokens-1)*(f.s.budget+3)]=f.s.capacity;};adjust(ref);adjust(cand);
 ng::reference::cpu(ref.s,ref.a());if(cand.s.op==ng::route_gather)fusion::cpu_route(cand.s,cand.a());else fusion::cpu_attention(cand.s,cand.a());
 need(ref.d[15]==cand.d[15],"control sticky parity");
 if(mode<3)for(int j=0;j<16;++j)if(ref.out[j]&&!(ref.s.op==ng::route_gather&&j==4))need(ref.d[j]==cand.d[j],"control output parity");
 if(mode==3&&ref.s.op==ng::attention_score){Fixture untouched(dir/name);need(cand.d[5]==untouched.d[5],"all-row invalid attention precheck failed closed");}
 ++checks;
 }return checks;
}
int main(int argc,char**argv){try{need(argc==4,"args fixtures receipt outputs");std::ifstream list(fs::path(argv[1])/"cases.txt");std::ofstream bytes(argv[3],std::ios::binary);std::string name;int checks=0,routes=0,attn=0,boundaries=0;size_t compared=0;
 while(list>>name){Fixture ref(fs::path(argv[1])/name),candidate=ref;ng::reference::cpu(ref.s,ref.a());auto before=candidate.d;
 if(ref.s.op==ng::route_gather){fusion::cpu_route(candidate.s,candidate.a());++routes;
   // Compare logical routed input without materializing it in candidate ABI.
   need(candidate.d[4]==before[4],name+" wrote removed gather allocation");
   if(candidate.a().i(15)[1]&&!candidate.a().i(15)[2])for(int r=0;r<ref.s.tokens;++r)for(int e=0;e<ref.s.extra;++e)for(int k=0;k<2560;++k)need(candidate.a().b(1,r*2560+k)==ref.a().b(4,(r*ref.s.extra+e)*2560+k),name+" single row indexing");
 }else if(ref.s.op==ng::attention_score){fusion::cpu_attention(candidate.s,candidate.a());++attn;}
 else{fusion::Site site{candidate.s,candidate.a()};fusion::cpu_chain(&site,1);}
 for(int j=0;j<16;++j)if(ref.out[j]&&!(ref.s.op==ng::route_gather&&j==4)){need(candidate.d[j]==ref.d[j],name+" slot "+std::to_string(j));bytes.write(reinterpret_cast<char*>(candidate.d[j].data()),candidate.d[j].size());compared+=candidate.d[j].size();}
 // Exercise a real fused producer/consumer boundary with the first producer
 // output bound directly to the next stage input. Norm -> activation retains
 // the BF16 store before activation; no recomputation from unrounded values.
 if(ref.s.op==ng::norm){Fixture x(fs::path(argv[1])/name),y=x;auto shape=x.s;shape.op=ng::activation;shape.width=x.s.heads*x.s.width;shape.heads=1;shape.extra=0;
  std::vector<uint16_t> xo(shape.tokens*shape.width),yo(xo.size());auto xa=x.a(),ya=y.a();ng::Args ax=xa,ay=ya;ax.p[0]=xa.p[2];ay.p[0]=ya.p[2];ax.p[2]=xo.data();ay.p[2]=yo.data();
  ng::cpu(x.s,xa);ng::cpu(shape,ax);fusion::Site chain[]={{y.s,ya},{shape,ay}};fusion::cpu_chain(chain,2);need(xo==yo,name+" chain");bytes.write(reinterpret_cast<char*>(yo.data()),yo.size()*2);++boundaries;
 }
 ++checks;
 }
 need(checks==72,"all72");int integrated=integrated_chains(argv[1],bytes);int controls=rejected_controls(argv[1]);std::ofstream out(argv[2]);out<<"{\"passed\":true,\"device_executed\":false,\"fixtures\":"<<checks<<",\"integrated_chains\":"<<integrated<<",\"control_checks\":"<<controls<<",\"route_cases\":"<<routes<<",\"attention_cases\":"<<attn<<",\"chained_boundaries\":"<<boundaries<<",\"compared_bytes\":"<<compared<<"}\n";
 return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
