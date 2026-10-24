#pragma once
// Evidence bytes only. No Device, model, protocol or arithmetic dependencies.
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <filesystem>
#include <fcntl.h>
#include <limits>
#include <openssl/evp.h>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <vector>
namespace gsq_bundle {
namespace fs=std::filesystem;
inline constexpr uint64_t byte_cap=256ull*1024*1024,metadata_cap=1024*1024,row_cap=4096;
inline void need(bool b,const char*s){if(!b)throw std::runtime_error(std::string("state bundle: ")+s);}
#ifdef GSQ_BUNDLE_TESTING
inline void(*test_hook)(const char*)=nullptr;
inline std::vector<std::pair<unsigned long,unsigned long>> publication_links;
inline void point(const char*s){if(test_hook)test_hook(s);}
#else
inline void point(const char*){}
#endif
struct FD {
 int n=-1;explicit FD(int v=-1):n(v){};FD(const FD&)=delete;FD&operator=(const FD&)=delete;
 ~FD(){if(n>=0)::close(n);}
 void close_checked(){int v=n;n=-1;need(::close(v)==0,"close failed");point("closed");}
};
struct Hash {
 EVP_MD_CTX* c=EVP_MD_CTX_new();Hash(){need(c&&EVP_DigestInit_ex(c,EVP_sha256(),nullptr)==1,"SHA init");}
 Hash(const Hash&)=delete;~Hash(){EVP_MD_CTX_free(c);}
 void add(const void*p,size_t n){need(EVP_DigestUpdate(c,p,n)==1,"SHA update");}
 std::string finish(){std::array<unsigned char,32>b{};unsigned n=0;need(EVP_DigestFinal_ex(c,b.data(),&n)==1&&n==32,"SHA finish");std::string s;for(auto x:b){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
};
inline std::string digest(const void*p,size_t n){Hash h;h.add(p,n);return h.finish();}
inline std::string digest(const std::string&s){return digest(s.data(),s.size());}
inline bool hex(const std::string&s){return s.size()==64&&s.find_first_not_of("0123456789abcdef")==std::string::npos;}
inline bool same(const struct stat&a,const struct stat&b){return a.st_dev==b.st_dev&&a.st_ino==b.st_ino&&a.st_size==b.st_size&&a.st_mode==b.st_mode&&a.st_nlink==b.st_nlink&&a.st_mtim.tv_sec==b.st_mtim.tv_sec&&a.st_mtim.tv_nsec==b.st_mtim.tv_nsec&&a.st_ctim.tv_sec==b.st_ctim.tv_sec&&a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;}
inline struct stat stamp(int fd){struct stat s{};need(fstat(fd,&s)==0&&S_ISREG(s.st_mode)&&s.st_nlink==1,"regular single-link file");return s;}
inline void stable(int dir,const char*name,int fd,const struct stat&before){struct stat p{};need(fstatat(dir,name,&p,AT_SYMLINK_NOFOLLOW)==0&&same(before,stamp(fd))&&same(before,p),"file changed/replaced");}
inline uint64_t number(const std::string&s){need(!s.empty()&&(s=="0"||s[0]!='0'),"canonical integer");uint64_t n=0;for(char c:s){need(c>='0'&&c<='9'&&n<=(std::numeric_limits<uint64_t>::max()-uint64_t(c-'0'))/10,"integer overflow");n=n*10+uint64_t(c-'0');}return n;}
inline void name_ok(const std::string&s){need(!s.empty()&&s.size()<=240&&s.ends_with(".bin")&&s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")==std::string::npos&&s!="..bin","buffer filename");}
inline std::string file_hash(int fd,uint64_t bytes,uint64_t start,Hash&whole){need(start<=byte_cap&&bytes<=byte_cap-start,"payload extent");Hash h;std::array<char,65536>b{};uint64_t off=0;while(off<bytes){size_t n=std::min<uint64_t>(b.size(),bytes-off);ssize_t got=pread(fd,b.data(),n,start+off);if(got<0&&errno==EINTR)continue;need(got>0&&size_t(got)<=n,"read payload");h.add(b.data(),got);whole.add(b.data(),got);off+=got;}return h.finish();}
inline std::string read_small(int dir,const char*name){FD f(openat(dir,name,O_RDONLY|O_NOFOLLOW|O_CLOEXEC));need(f.n>=0,"open metadata");auto st=stamp(f.n);need(st.st_size>=0&&uint64_t(st.st_size)<=metadata_cap,"metadata extent");std::string s(st.st_size,'\0');size_t done=0;while(done<s.size()){ssize_t n=read(f.n,s.data()+done,s.size()-done);if(n<0&&errno==EINTR)continue;need(n>0,"read metadata");done+=n;}stable(dir,name,f.n,st);f.close_checked();return s;}
inline void write_all(int fd,const void*p,size_t n){point("before-write");const char*b=static_cast<const char*>(p);while(n){ssize_t z=write(fd,b,n);if(z<0&&errno==EINTR)continue;need(z>0&&size_t(z)<=n,"write failed");b+=z;n-=z;point("after-write");}}
inline void sync(int fd,const char*label){point(label);need(fsync(fd)==0,"fsync failed");}
inline void small(int dir,const char*name,const std::string&s){need(s.size()<=metadata_cap,"metadata limit");FD f(openat(dir,name,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));need(f.n>=0,"exclusive metadata");write_all(f.n,s.data(),s.size());sync(f.n,"file-fsync");f.close_checked();}
inline void publish(int dir,const char*from,const char*to){
 FD held(openat(dir,from,O_RDONLY|O_NOFOLLOW|O_CLOEXEC));need(held.n>=0,"open publication partial");auto before=stamp(held.n);
 if(linkat(dir,from,dir,to,0)!=0)throw std::runtime_error("state bundle: exclusive link publication errno="+std::to_string(errno));
 struct stat a{},b{};need(fstatat(dir,from,&a,AT_SYMLINK_NOFOLLOW)==0&&fstatat(dir,to,&b,AT_SYMLINK_NOFOLLOW)==0&&S_ISREG(a.st_mode)&&S_ISREG(b.st_mode)&&a.st_dev==before.st_dev&&a.st_ino==before.st_ino&&b.st_dev==before.st_dev&&b.st_ino==before.st_ino&&a.st_nlink==2&&b.st_nlink==2,"publication link identity");
 point("publication-linked");
 need(unlinkat(dir,from,0)==0,"remove published partial name");struct stat retained{};need(fstat(held.n,&retained)==0&&S_ISREG(retained.st_mode)&&retained.st_dev==before.st_dev&&retained.st_ino==before.st_ino&&retained.st_size==before.st_size,"held publication identity");held.close_checked();
 // NTFS may cache link metadata on the old handle; refresh only after our own link/unlink.
 FD final(openat(dir,to,O_RDONLY|O_NOFOLLOW|O_CLOEXEC));need(final.n>=0,"reopen publication");auto after=stamp(final.n);stable(dir,to,final.n,after);need(after.st_dev==before.st_dev&&after.st_ino==before.st_ino&&after.st_size==before.st_size&&after.st_mtim.tv_sec==before.st_mtim.tv_sec&&after.st_mtim.tv_nsec==before.st_mtim.tv_nsec,"published bytes identity");
#ifdef GSQ_BUNDLE_TESTING
 publication_links.emplace_back(retained.st_nlink,after.st_nlink);
#endif
 point("publication-reopened");final.close_checked();
}
struct Row{std::string name,sha;uint64_t offset,length;};
class Writer {
 fs::path path;FD dir,payload;bool verify=false,finished=false;uint64_t bytes=0;size_t cursor=0;std::vector<Row>rows;std::set<std::string>names;Hash whole;std::string sealed_state,sealed_payload,sealed_index,sealed_text;struct stat opened{};
 void directory(){struct stat st{};need(fstat(dir.n,&st)==0&&S_ISDIR(st.st_mode),"directory descriptor");struct stat now{};need(lstat(path.c_str(),&now)==0&&S_ISDIR(now.st_mode)&&now.st_dev==st.st_dev&&now.st_ino==st.st_ino,"directory replacement");}
 void inventory(bool fresh){std::set<std::string>actual;for(auto&f:fs::directory_iterator(path))actual.insert(f.path().filename().string());need(fresh?actual.empty():actual==std::set<std::string>{"state.bundle","state-index.tsv","state.json","state-seal.txt"},"incomplete/unexpected state files");}
public:
 explicit Writer(const fs::path&p):path(p),dir(open(p.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)){
  need(dir.n>=0,"open state directory");directory();struct stat st{};verify=fstatat(dir.n,"state-seal.txt",&st,AT_SYMLINK_NOFOLLOW)==0;
  inventory(!verify);
  if(verify){
   sealed_text=read_small(dir.n,"state-seal.txt");std::istringstream in(sealed_text);std::string magic,n,extra;need(bool(std::getline(in,magic))&&magic=="GSQ_STATE_SEAL_V1"&&bool(std::getline(in,n))&&bool(std::getline(in,sealed_payload))&&bool(std::getline(in,sealed_index))&&bool(std::getline(in,sealed_state))&&!std::getline(in,extra),"seal fields");
   uint64_t total=number(n);need(total<=byte_cap&&hex(sealed_payload)&&hex(sealed_index)&&hex(sealed_state),"seal bounds");
   std::string index=read_small(dir.n,"state-index.tsv");need(digest(index)==sealed_index,"index digest");std::istringstream stream(index);std::string line;need(bool(std::getline(stream,line))&&line=="GSQ_STATE_BUNDLE_V1","index magic");uint64_t off=0;
   while(std::getline(stream,line)){std::istringstream row(line);std::string name,a,b,h,extra;need(bool(std::getline(row,name,'\t'))&&bool(std::getline(row,a,'\t'))&&bool(std::getline(row,b,'\t'))&&bool(std::getline(row,h,'\t'))&&!std::getline(row,extra,'\t'),"index row");name_ok(name);uint64_t start=number(a),len=number(b);need(hex(h)&&names.insert(name).second&&rows.size()<row_cap&&start==off&&len<=byte_cap-off,"index inventory/range");rows.push_back({name,h,start,len});off+=len;}
   need(!rows.empty()&&off==total,"complete index");names.clear();
   payload.n=openat(dir.n,"state.bundle",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);need(payload.n>=0,"open sealed bundle");opened=stamp(payload.n);need(uint64_t(opened.st_size)==total,"sealed payload extent");stable(dir.n,"state.bundle",payload.n,opened);
   need(digest(read_small(dir.n,"state.json"))==sealed_state,"sealed state JSON");
  }else{payload.n=openat(dir.n,"state.bundle.partial",O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);need(payload.n>=0,"exclusive partial bundle");}
 }
 Writer(const Writer&)=delete;
 void append(const std::string&name,const void*p,size_t n){
  need(!finished,"append after finish");name_ok(name);need(names.insert(name).second&&names.size()<=row_cap&&n<=byte_cap-bytes,"name/extent bound");std::string h=digest(p,n);
  if(verify){need(cursor<rows.size(),"extra current buffer");const auto&r=rows[cursor++];need(r.name==name&&r.offset==bytes&&r.length==n&&r.sha==h&&file_hash(payload.n,n,bytes,whole)==h,"repeated dump differs");}
  else{write_all(payload.n,p,n);whole.add(p,n);rows.push_back({name,h,bytes,n});}bytes+=n;
 }
 void finish(const std::string&state){
  need(!finished&&!rows.empty()&&state.size()<=metadata_cap,"finish state");directory();
  if(verify){need(cursor==rows.size()&&uint64_t(opened.st_size)==bytes&&digest(state)==sealed_state&&whole.finish()==sealed_payload,"repeated inventory/JSON/payload differs");stable(dir.n,"state.bundle",payload.n,opened);need(digest(read_small(dir.n,"state-index.tsv"))==sealed_index&&read_small(dir.n,"state.json")==state&&read_small(dir.n,"state-seal.txt")==sealed_text,"metadata changed");inventory(false);payload.close_checked();finished=true;return;}
  sync(payload.n,"payload-fsync");payload.close_checked();std::string index="GSQ_STATE_BUNDLE_V1\n";
  for(auto&r:rows){index+=r.name+'\t'+std::to_string(r.offset)+'\t'+std::to_string(r.length)+'\t'+r.sha+'\n';need(index.size()<=metadata_cap,"index bound");}
  small(dir.n,"state-index.tsv.partial",index);small(dir.n,"state.json.partial",state);
  std::string seal="GSQ_STATE_SEAL_V1\n"+std::to_string(bytes)+'\n'+whole.finish()+'\n'+digest(index)+'\n'+digest(state)+'\n';
  small(dir.n,"state-seal.txt.partial",seal);
  publish(dir.n,"state.bundle.partial","state.bundle");publish(dir.n,"state-index.tsv.partial","state-index.tsv");publish(dir.n,"state.json.partial","state.json");sync(dir.n,"data-directory-fsync");
  publish(dir.n,"state-seal.txt.partial","state-seal.txt");sync(dir.n,"seal-directory-fsync");directory();inventory(false);finished=true;
 }
};
} // namespace gsq_bundle
