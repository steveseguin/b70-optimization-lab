#pragma once
// Bounded token-ID transport only. No model/device code and no client-selected paths.
#include <charconv>
#include <chrono>
#include <csignal>
#include <cerrno>
#include <fcntl.h>
#include <optional>
#include <poll.h>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unistd.h>
#include <vector>
namespace requestfront {
inline constexpr size_t frame_limit=262144;
inline void check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
inline bool valid_id(std::string_view s){
 auto alnum=[](char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');};
 if(s.empty()||s.size()>64||!alnum(s.front())||s.ends_with(".lock"))return false;
 for(char c:s)if(!alnum(c)&&c!='.'&&c!='_'&&c!='-')return false;return true;
}
inline int number(std::string_view s,int low,int high){
 int n=0;auto result=std::from_chars(s.data(),s.data()+s.size(),n);
 check(!s.empty()&&result.ec==std::errc()&&result.ptr==s.data()+s.size()&&n>=low&&n<=high,"invalid bounded decimal integer");
 for(char c:s)check(c>='0'&&c<='9',"nondecimal integer");return n;
}
struct Request {std::string id,restore,save;int max_new=0;std::vector<int> tokens;};
inline Request parse(std::string_view line,int vocab,int context){
 check(!line.empty()&&line.size()+1<=frame_limit,"request frame size");
 std::vector<std::string_view> f;size_t start=0;
 for(size_t i=0;i<=line.size();++i)if(i==line.size()||line[i]=='\t'){f.push_back(line.substr(start,i-start));start=i+1;}
 check(f.size()==6&&f[0]=="RUN","expected six-field RUN frame");
 Request r;r.id=f[1];check(valid_id(r.id),"invalid request id");r.max_new=number(f[2],1,512);
 r.restore=f[3]=="-"?"":std::string(f[3]);r.save=f[4]=="-"?"":std::string(f[4]);
 check(r.restore.empty()||valid_id(r.restore),"invalid restore id");check(r.save.empty()||valid_id(r.save),"invalid save id");
 check(r.restore.empty()||r.save.empty()||r.restore!=r.save,"restore cannot overwrite saved checkpoint");
 check(!f[5].empty(),"empty input tokens");start=0;
 for(size_t i=0;i<=f[5].size();++i)if(i==f[5].size()||f[5][i]==' '){
  r.tokens.push_back(number(f[5].substr(start,i-start),0,vocab-1));start=i+1;
  check(r.tokens.size()<=size_t(context),"input context bound");
 }
 check(r.tokens.size()+size_t(r.max_new)<=size_t(context),"input/generation context bound");return r;
}
class Reader {
 int fd_,idle_;size_t maximum_,count_=0;std::set<std::string> ids_;
public:
 std::string reason;
 Reader(int fd,size_t maximum,int idle):fd_(fd),idle_(idle),maximum_(maximum){check(maximum>=1&&maximum<=1024&&idle>=1&&idle<=3600,"front bounds required");}
 size_t count()const{return count_;}
 std::optional<Request> next(int vocab,int context,const volatile std::sig_atomic_t& stop,std::chrono::steady_clock::time_point deadline){
  if(count_==maximum_){reason="request-limit";return {};}
  auto idle_deadline=std::chrono::steady_clock::now()+std::chrono::seconds(idle_);std::string line;
  for(;;){
   if(stop){reason="signal";return {};}
   auto now=std::chrono::steady_clock::now();
   if(now>=deadline){reason="deadline";return {};}
   if(now>=idle_deadline){check(line.empty(),"partial request idle timeout");reason="idle-timeout";return {};}
   pollfd p{fd_,POLLIN,0};int rc=::poll(&p,1,100);
   if(rc<0){if(errno==EINTR)continue;throw std::runtime_error("stdin poll failed");}
   if(!rc)continue;check(!(p.revents&(POLLERR|POLLNVAL)),"stdin poll error");
   char c;auto n=::read(fd_,&c,1);
   if(n<0){if(errno==EINTR||errno==EAGAIN)continue;throw std::runtime_error("stdin read failed");}
   if(n==0){check(line.empty(),"partial request at EOF");reason="eof";return {};}
   if(c=='\n'){
    if(line=="QUIT"){reason="quit";return {};}
    auto r=parse(line,vocab,context);check(ids_.insert(r.id).second,"duplicate request id");++count_;return r;
   }
   check(c!='\0'&&c!='\r'&&line.size()+2<=frame_limit,"invalid or oversized request frame");line.push_back(c);
  }
 }
};
class Channel {
 int output_=-1;
public:
 Reader reader;
 Channel(size_t maximum,int idle):reader(STDIN_FILENO,maximum,idle){
  output_=::dup(STDOUT_FILENO);check(output_>=0,"protocol stdout duplication failed");
  check(::dup2(STDERR_FILENO,STDOUT_FILENO)>=0,"diagnostic stdout redirect failed");
  int flags=::fcntl(output_,F_GETFL);check(flags>=0&&::fcntl(output_,F_SETFL,flags|O_NONBLOCK)==0,"protocol nonblocking setup failed");
  std::signal(SIGPIPE,SIG_IGN);
 }
 ~Channel(){if(output_>=0)::close(output_);}
 void emit(const std::string& object){
  std::string bytes=object+"\n";size_t offset=0;auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
  while(offset<bytes.size()){
   check(std::chrono::steady_clock::now()<deadline,"protocol output deadline");
   pollfd p{output_,POLLOUT,0};int rc=::poll(&p,1,100);
   if(rc<0){if(errno==EINTR)continue;throw std::runtime_error("protocol output poll failed");}
   if(!rc)continue;check(!(p.revents&(POLLERR|POLLHUP|POLLNVAL)),"protocol consumer closed");
   auto n=::write(output_,bytes.data()+offset,bytes.size()-offset);
   if(n<0){if(errno==EINTR||errno==EAGAIN)continue;throw std::runtime_error("protocol output failed");}
   check(n>0,"protocol output made no progress");offset+=size_t(n);
  }
 }
 void token(const std::string& id,size_t index,int value){emit("{\"event\":\"token\",\"id\":\""+id+"\",\"index\":"+std::to_string(index)+",\"token_id\":"+std::to_string(value)+"}");}
};
}
