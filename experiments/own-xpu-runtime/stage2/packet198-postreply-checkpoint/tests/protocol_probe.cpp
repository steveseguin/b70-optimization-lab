// Actual standalone v2 parser/state tests. Compilation/execution requires the later authorized CPU turn.
#include "../native/request_front.hpp"
#include <cassert>
#include <functional>
using namespace requestfront;
static void refuses(const std::function<void()>& f){bool refused=false;try{f();}catch(const std::exception&){refused=true;}assert(refused);}
static void pipe_case(const std::string& input,size_t maximum,const std::function<void(Reader&)>& test){
 int fd[2];assert(::pipe(fd)==0);assert(::write(fd[1],input.data(),input.size())==ssize_t(input.size()));
 ::close(fd[1]);Reader r(fd[0],maximum,1);test(r);::close(fd[0]);
}
int main(){
 auto run=parse("RUN\tr1\t4\ts1\t-\t1 2 3",10,32);
 assert(run.kind==Kind::run&&run.id=="r1"&&run.max_new==4&&run.tokens.size()==3&&run.restore=="s1"&&run.save.empty());
 auto save=parse("SAVE\top1\tr1\ts2\t1 2 3 4",10,32);
 assert(save.kind==Kind::save&&save.id=="op1"&&save.request_id=="r1"&&save.checkpoint_id=="s2"&&save.tokens.size()==4);
 auto release=parse("RELEASE\top2\tr2",10,32);assert(release.kind==Kind::release&&release.request_id=="r2");
 for(const auto& bad:{"RUN\t../x\t4\t-\t-\t1","RUN\tx\t4\t-\ts1\t1","RUN\tx.lock\t4\t-\t-\t1",
                     "RUN\tx\t0\t-\t-\t1","RUN\tx\t513\t-\t-\t1","RUN\tx\t+4\t-\t-\t1",
                     "SAVE\to\tr\t../escape\t1","SAVE\to\tr\tx.lock\t1","SAVE\to\tr\ts\t-1",
                     "SAVE\to\tr\ts\t10","SAVE\to\tr\ts\t1  2","SAVE\to\tr\ts\t",
                     "SAVE\to\tr\ts\t1\textra","RELEASE\to\t../r","RELEASE\to\tr\textra","INSPECT\to\ts"})
  refuses([&]{parse(bad,10,32);});
 refuses([]{parse("RUN\tr\t4\t-\t-\t1 2 3",10,6);});
 refuses([]{parse("SAVE\to\tr\ts\t1 2 3",10,2);});
 refuses([]{parse(std::string(frame_limit,'x'),10,32);});
 volatile std::sig_atomic_t stop=0;auto end=std::chrono::steady_clock::now()+std::chrono::seconds(10);
 pipe_case("RUN\tr1\t4\t-\t-\t1\nSAVE\to1\tr1\ts1\t1 2 3\nRUN\tr2\t4\t-\t-\t2\nRELEASE\to2\tr2\n",2,[&](Reader& p){
  assert(p.next(10,32,stop,end)->kind==Kind::run);p.complete_request("r1");
  assert(p.next(10,32,stop,end)->kind==Kind::save);p.complete_control("r1");
  assert(p.next(10,32,stop,end)->kind==Kind::run);p.complete_request("r2");
  assert(p.final_request());assert(p.next(10,32,stop,end)->kind==Kind::release);p.complete_control("r2");
  assert(p.count()==2&&p.control_count()==2);assert(!p.next(10,32,stop,end)&&p.reason=="request-limit");
 });
 pipe_case("RUN\tr1\t4\t-\t-\t1\nSAVE\to1\tr1\ts1\t1 2 3\n",1,[&](Reader& p){
  assert(p.next(10,32,stop,end));p.complete_request("r1");
  assert(p.next(10,32,stop,end)->kind==Kind::save);p.complete_control("r1");
  assert(!p.next(10,32,stop,end)&&p.reason=="request-limit");
 });
 for(const auto& second:{"RUN\tr2\t4\t-\t-\t1\n","RELEASE\to\twrong\n","SAVE\to\twrong\ts\t1\n"})
  pipe_case(std::string("RUN\tr1\t4\t-\t-\t1\n")+second,2,[&](Reader& p){assert(p.next(10,32,stop,end));p.complete_request("r1");refuses([&]{p.next(10,32,stop,end);});});
 pipe_case("RELEASE\to\tr\n",2,[&](Reader& p){refuses([&]{p.next(10,32,stop,end);});});
 pipe_case("RUN\tr1\t4\t-\t-\t1\nRELEASE\to\tr1\nRUN\tr2\t4\t-\t-\t2\nRELEASE\to\tr2\n",2,[&](Reader& p){
  assert(p.next(10,32,stop,end));p.complete_request("r1");assert(p.next(10,32,stop,end));p.complete_control("r1");
  assert(p.next(10,32,stop,end));p.complete_request("r2");refuses([&]{p.next(10,32,stop,end);});
 });
 pipe_case("RUN\tr1\t4\t-\t-\t1\n",1,[&](Reader& p){assert(p.next(10,32,stop,end));refuses([&]{p.next(10,32,stop,end);});p.complete_request("r1");assert(!p.next(10,32,stop,end)&&p.reason=="eof");});
 pipe_case("RUN\tr1\t4\t-\t-\t1\nQUIT\n",1,[&](Reader& p){assert(p.next(10,32,stop,end));p.complete_request("r1");assert(!p.next(10,32,stop,end)&&p.reason=="quit");});
 pipe_case("SAVE\top",1,[&](Reader& p){refuses([&]{p.next(10,32,stop,end);});});
 pipe_case("",1,[&](Reader& p){assert(!p.next(10,32,stop,std::chrono::steady_clock::now())&&p.reason=="deadline");});
 stop=1;pipe_case("",1,[&](Reader& p){assert(!p.next(10,32,stop,end)&&p.reason=="signal");});
}
