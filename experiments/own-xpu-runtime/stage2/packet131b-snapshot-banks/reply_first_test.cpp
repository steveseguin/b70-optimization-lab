// Mock backend, real report scheduler and mailbox worker. No device library.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <unistd.h>
#include "reply_first.hpp"
namespace fs=std::filesystem;
void require(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
namespace ownrt{std::string quote(const std::string&s){return "\""+s+"\"";}}
namespace pipeline{
constexpr size_t slot_bytes=65536;
enum Command {half=1,accept=2,rollback=3,dump=4,finish=5,draft=9};
struct Request{int32_t op,token,position,fixture,speculative,sequence,reserved[2];};
struct Reply{int32_t status,token,error,bytes,sequence,rank,reserved[2];double busy_ms,gpu_ms,redo_ms,reserved_ms;};
}
#include "native_controller.hpp"
namespace p56x{const bool sleep20=false;}
using namespace pipeline;
using namespace pipeline::native38;
template<class F>void rejects(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}require(failed,"expected error propagation");}
struct MockBackend{
 std::array<uint32_t,16> state{};unsigned halves=0,drafts=0;bool error=false;
 int run(){require(!error,"injected result error");for(unsigned i=0;i<state.size();++i)state[i]=state[i]*1664525u+1013904223u+i+halves;++halves;return int(state[0]%31);}
};
std::vector<uint32_t> trial(bool early,bool inject=false){
 p92::Reports reports;reports.enabled=early;std::ostringstream diagnostics;reports.output=&diagnostics;
 Mailbox box{};MockBackend backend;std::vector<uint32_t> bytes;std::vector<std::string> order;
 auto send=[&](int op){box.request={op,0,0,0,0,int32_t(load(box.request_sequence)+1),{0,0}};publish(box.request_sequence,box.request.sequence);};
 send(half);
 auto execute=[&](const Request&r){
  reports.before(r.op);Reply reply{};reply.sequence=r.sequence;reply.rank=1;
  if(r.op==half){reply.token=backend.run();auto snapshot=backend.state;bytes.insert(bytes.end(),snapshot.begin(),snapshot.end());bytes.push_back(reply.token);reports.begin(r.sequence,backend.halves,backend.halves-1);
   reports.schedule([&,snapshot]{order.push_back("report");if(inject)throw std::runtime_error("injected deferred failure");require(snapshot[0]==bytes[(backend.halves-1)*17],"report snapshot ownership");});
  }else if(r.op==accept)order.push_back("accept");
  else if(r.op==draft){++backend.drafts;order.push_back("draft-submitted");if(inject)send(half);}
  reports.after(r.op);return reply;
 };
 auto published=[&](const Request&r){
  if(r.op==half){order.push_back("reply");require(box.reply.token==int(backend.state[0]%31),"verified token publication");reports.published();send(accept);}
  else if(r.op==accept)send(backend.halves==4?0:draft);
  else if(r.op==draft)send(half);
 };
 try{worker(box,1,execute,[]{},published,[&]{reports.flush();});}
 catch(...){abort(box);if(!inject)throw;}
 if(inject){require(load(box.abort)==1&&backend.halves==1&&reports.poisoned(),"deferred failure admitted next half");rejects([&]{reports.before(half);});return bytes;}
 require(backend.halves==4&&backend.drafts==3&&!reports.pending(),"mock completion state");
 require(order.front()==(early?"reply":"report"),"reply ordering");
 if(early)require(order[1]=="accept"&&order[2]=="draft-submitted"&&order[3]=="report","bookkeeping fails to overlap draft");
 unsigned rows=0;for(char c:diagnostics.str())rows+=c=='\n';require(rows==4,"every half must retain diagnostic fields");
 require(diagnostics.str().find("result_ready_to_reply_ms")!=std::string::npos&&diagnostics.str().find("bookkeeping_ms")!=std::string::npos,"timer fields missing");
 return bytes;
}
int main(int argc,char**argv){try{
 require(argc==2,"output directory");auto control=trial(false),candidate=trial(true);require(control==candidate,"state/token byte difference");trial(true,true);
 unsigned negatives=1;
 for(int op:std::array<int,5>{half,dump,finish,11,0}){
  p92::Reports r;std::ostringstream out;r.output=&out;r.enabled=true;r.begin(1,1,0);r.schedule([]{throw std::runtime_error("deferred I/O failure");});r.published();r.before(accept);rejects([&]{r.before(op);});require(r.poisoned(),"command boundary lost failure");++negatives;
 }
 {p92::Reports r;std::ostringstream out;r.output=&out;r.enabled=true;r.begin(1,1,0);r.schedule([]{});r.published();r.before(accept);out.setstate(std::ios::badbit);rejects([&]{r.after(draft);});require(r.poisoned(),"diagnostic failure lost");++negatives;}
 {MockBackend b;b.error=true;rejects([&]{b.run();});require(b.halves==0,"result failure accepted");++negatives;}
 {Mailbox m{};std::array<uint8_t,3*slot_bytes> memory{};Backend b(m,memory.data(),1,[](const Request&){return Reply{};},[]{});b.start(1,half);m.reply={};publish(m.reply_sequence,b.seq);abort(m);rejects([&]{b.wait(1);});++negatives;}
 for(auto pair:{std::pair{"expected.bin",&control},std::pair{"candidate.bin",&candidate}}){std::ofstream f(fs::path(argv[1])/pair.first,std::ios::binary);f.write(reinterpret_cast<const char*>(pair.second->data()),pair.second->size()*4);require(bool(f),"byte fixture write");}
 std::ofstream f(fs::path(argv[1])/"result.json");f<<"{\"passed\":true,\"device_executed\":false,\"state_token_words\":"<<control.size()<<",\"negative_cases\":"<<negatives<<"}\n";
 return 0;
 }catch(const std::exception&e){fprintf(stderr,"%s\n",e.what());return 1;}}
