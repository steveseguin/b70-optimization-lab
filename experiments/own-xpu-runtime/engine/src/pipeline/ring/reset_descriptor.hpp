#pragma once
#include "stage_ring.hpp"
#include <charconv>
#include <filesystem>
#include <map>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
namespace ownrt::ring_next::reset {
namespace fs=std::filesystem;
struct Value {std::string text;bool quoted=false;};
// A deliberately small flat-object JSON grammar: only strings and unsigned
// decimal integers. No ignored keys, duplicate keys, coercion or trailing data.
class Json {
 const std::string& s;size_t p=0;
 void ws(){while(p<s.size()&&(s[p]==' '||s[p]=='\t'||s[p]=='\r'||s[p]=='\n'))++p;}
 char get(){need(p<s.size(),"reset JSON truncated");return s[p++];}
 unsigned hex4(){unsigned x=0;for(int i=0;i<4;++i){const char c=get();need((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F'),"reset JSON unicode");x=16*x+(c<='9'?c-'0':(c<='F'?c-'A'+10:c-'a'+10));}return x;}
 std::string str(){need(get()=='"',"reset JSON string");std::string out;
  for(;;){char c=get();if(c=='"')break;need(uint8_t(c)>=32,"reset JSON raw control");
   if(c!='\\'){out+=c;continue;}c=get();
   if(c=='"'||c=='\\'||c=='/')out+=c;
   else if(c=='b')out+='\b';else if(c=='f')out+='\f';else if(c=='n')out+='\n';else if(c=='r')out+='\r';else if(c=='t')out+='\t';
   else {need(c=='u',"reset JSON escape");unsigned x=hex4();if(x>=0xd800&&x<=0xdbff){need(get()=='\\'&&get()=='u',"reset JSON surrogate");unsigned y=hex4();need(y>=0xdc00&&y<=0xdfff,"reset JSON surrogate pair");x=0x10000+((x-0xd800)<<10)+(y-0xdc00);}else need(x<0xdc00||x>0xdfff,"reset JSON unpaired surrogate");
    if(x<0x80)out+=char(x);else if(x<0x800){out+=char(0xc0|(x>>6));out+=char(0x80|(x&63));}else if(x<0x10000){out+=char(0xe0|(x>>12));out+=char(0x80|((x>>6)&63));out+=char(0x80|(x&63));}else{out+=char(0xf0|(x>>18));out+=char(0x80|((x>>12)&63));out+=char(0x80|((x>>6)&63));out+=char(0x80|(x&63));}}
  }return out;
 }
public:
 explicit Json(const std::string& input):s(input){}
 std::map<std::string,Value> parse(){std::map<std::string,Value> out;ws();need(get()=='{',"reset JSON object");ws();
  if(p<s.size()&&s[p]=='}'){++p;}else for(;;){ws();const auto key=str();ws();need(get()==':',"reset JSON colon");ws();Value value;
   if(p<s.size()&&s[p]=='"'){value.quoted=true;value.text=str();}else{size_t start=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;need(p>start&&(p-start==1||s[start]!='0'),"reset JSON unsigned number");value.text=s.substr(start,p-start);}
   need(out.emplace(key,std::move(value)).second,"reset JSON duplicate key");ws();const char end=get();if(end=='}')break;need(end==',',"reset JSON separator");
  }ws();need(p==s.size(),"reset JSON trailing data");return out;
 }
};
struct Descriptor {uint64_t previous_epoch=0,next_epoch=0;int stage=0,sequence=0;std::string previous_request,next_request,oracle,raw;fs::path destination;};
inline bool sha(const std::string& text){return text.size()==64&&std::all_of(text.begin(),text.end(),[](char c){return(c>='0'&&c<='9')||(c>='a'&&c<='f');});}
inline Digest digest(const std::string& text){need(sha(text),"reset request digest");Digest out{};for(size_t i=0;i<out.size();++i){unsigned value=0;auto result=std::from_chars(text.data()+2*i,text.data()+2*i+2,value,16);need(result.ec==std::errc{},"reset digest parse");out[i]=uint8_t(value);}return out;}
inline Descriptor parse(const std::string& raw){need(!raw.empty()&&raw.size()<=8192,"reset descriptor bounded bytes");const auto values=Json(raw).parse();need(values.size()==9,"reset descriptor exact fields");
 auto string=[&](const char* key){auto it=values.find(key);need(it!=values.end()&&it->second.quoted,"reset descriptor string field");need(std::none_of(it->second.text.begin(),it->second.text.end(),[](char c){return uint8_t(c)<32;}),"reset descriptor control character");return it->second.text;};
 auto integer=[&](const char* key){auto it=values.find(key);need(it!=values.end()&&!it->second.quoted,"reset descriptor integer field");uint64_t result=0;const auto& v=it->second.text;auto parsed=std::from_chars(v.data(),v.data()+v.size(),result);need(parsed.ec==std::errc{}&&parsed.ptr==v.data()+v.size(),"reset descriptor integer range");return result;};
 need(string("schema")=="ownrt.ring-reset-request.v1","reset descriptor schema");Descriptor d;d.raw=raw;d.previous_epoch=integer("previous_epoch");d.next_epoch=integer("next_epoch");const auto stage=integer("stage_id"),sequence=integer("global_sequence");need(stage<=INT32_MAX&&sequence>0&&sequence<=INT32_MAX,"reset descriptor stage/sequence range");d.stage=int(stage);d.sequence=int(sequence);d.previous_request=string("previous_request_sha256");d.next_request=string("next_request_sha256");d.destination=string("destination");d.oracle=string("oracle");need(sha(d.previous_request)&&sha(d.next_request)&&d.previous_request!=d.next_request,"reset distinct request identity");need(d.previous_epoch!=UINT64_MAX&&d.next_epoch==d.previous_epoch+1,"reset epoch progression");return d;
}
inline bool same(const struct stat& a,const struct stat& b){return a.st_dev==b.st_dev&&a.st_ino==b.st_ino&&a.st_size==b.st_size&&a.st_mtim.tv_sec==b.st_mtim.tv_sec&&a.st_mtim.tv_nsec==b.st_mtim.tv_nsec&&a.st_ctim.tv_sec==b.st_ctim.tv_sec&&a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;}
inline std::string read(const fs::path& path){const int fd=::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);need(fd>=0,"reset descriptor open");struct Close{int fd;~Close(){::close(fd);}}close{fd};struct stat before{},after{},named{};need(!::fstat(fd,&before)&&S_ISREG(before.st_mode)&&before.st_size>0&&before.st_size<=8192,"reset descriptor bounded regular file");std::string raw(size_t(before.st_size),'\0');size_t n=0;while(n<raw.size()){auto got=::pread(fd,raw.data()+n,raw.size()-n,off_t(n));if(got<0&&errno==EINTR)continue;need(got>0,"reset descriptor read");n+=size_t(got);}need(!::fstat(fd,&after)&&!::lstat(path.c_str(),&named)&&S_ISREG(named.st_mode)&&same(before,after)&&same(before,named),"reset descriptor identity changed");return raw;}
inline void destination(const fs::path& path,const fs::path& original){need(path.is_absolute()&&path==path.lexically_normal(),"reset normalized absolute destination");const auto owner=fs::canonical(original),relative=path.lexically_relative(owner);need(!relative.empty()&&relative!="."&&!relative.is_absolute()&&*relative.begin()!="..","reset destination outside original owner");auto status=[](const fs::path& p){std::error_code error;auto s=fs::symlink_status(p,error);need(!error||error==std::errc::no_such_file_or_directory,"reset destination status");return s.type();};need(status(path)==fs::file_type::not_found,"reset destination not fresh");for(auto parent=path.parent_path();parent!=owner;parent=parent.parent_path()){need(!parent.empty()&&parent!=parent.parent_path(),"reset destination ancestry");auto kind=status(parent);need(kind==fs::file_type::not_found||kind==fs::file_type::directory,"reset symlink/non-directory ancestor");}}
inline Descriptor load(const fs::path& path,const fs::path& original,uint64_t epoch,const std::string& request,int stage,int sequence,const std::string& oracle){auto d=parse(read(path));need(d.previous_epoch==epoch&&d.previous_request==request&&d.stage==stage&&d.sequence==sequence&&d.oracle==oracle,"reset descriptor current owner binding");destination(d.destination,original);return d;}
}
