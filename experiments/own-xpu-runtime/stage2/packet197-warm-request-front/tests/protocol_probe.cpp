// Standalone CPU-only parser/pipe probe. Written now; compile/run requires the coordinator's later CPU build turn.
#include "../native/request_front.hpp"
#include <cassert>
#include <functional>
using namespace requestfront;
static void refuses(const std::function<void()>& f){bool refused=false;try{f();}catch(const std::exception&){refused=true;}assert(refused);}
static void pipe_case(const std::string& input,const std::function<void(Reader&)>& test){
 int fd[2];assert(::pipe(fd)==0);assert(::write(fd[1],input.data(),input.size())==ssize_t(input.size()));::close(fd[1]);Reader r(fd[0],2,1);test(r);::close(fd[0]);
}
int main(){
 auto r=parse("RUN\tr1\t4\ts1\ts2\t1 2 3",10,32);assert(r.id=="r1"&&r.max_new==4&&r.tokens.size()==3&&r.restore=="s1"&&r.save=="s2");
 for(const auto& bad:{"RUN\t../x\t4\t-\t-\t1","RUN\tx.lock\t4\t-\t-\t1","RUN\tx\t0\t-\t-\t1","RUN\tx\t513\t-\t-\t1","RUN\tx\t+4\t-\t-\t1","RUN\tx\t4\ts1\ts1\t1","RUN\tx\t4\t-\t-\t-1","RUN\tx\t4\t-\t-\t10","RUN\tx\t4\t-\t-\t1  2","RUN\tx\t4\t-\t-\t","RUN\tx\t4\t-\t-\t1\textra"})refuses([&]{parse(bad,10,32);});
 refuses([]{parse("RUN\tx\t4\t-\t-\t1 2 3",10,6);});
 volatile std::sig_atomic_t stop=0;auto end=std::chrono::steady_clock::now()+std::chrono::seconds(10);
 pipe_case("RUN\tr1\t4\t-\t-\t1\nQUIT\n",[&](Reader& p){assert(p.next(10,32,stop,end));assert(!p.next(10,32,stop,end)&&p.reason=="quit");});
 pipe_case("RUN\tr1\t4\t-\t-\t1\nRUN\tr1\t4\t-\t-\t2\n",[&](Reader& p){assert(p.next(10,32,stop,end));refuses([&]{p.next(10,32,stop,end);});});
 pipe_case("RUN\tr1\t4\t-\t-\t1\nRUN\tr2\t4\t-\t-\t2\n",[&](Reader& p){assert(p.next(10,32,stop,end));assert(p.next(10,32,stop,end));assert(!p.next(10,32,stop,end)&&p.reason=="request-limit");});
 pipe_case("RUN\tr1",[&](Reader& p){refuses([&]{p.next(10,32,stop,end);});});
 pipe_case("",[&](Reader& p){assert(!p.next(10,32,stop,end)&&p.reason=="eof");});
 pipe_case("",[&](Reader& p){assert(!p.next(10,32,stop,std::chrono::steady_clock::now())&&p.reason=="deadline");});
 stop=1;pipe_case("",[&](Reader& p){assert(!p.next(10,32,stop,end)&&p.reason=="signal");});
}
