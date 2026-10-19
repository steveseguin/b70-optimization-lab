#include "resident_lookup.hpp"
#include "math.hpp"
#include <fcntl.h>
#include <unistd.h>
#include <fstream>
#include <iostream>
#include <vector>
#include <sys/resource.h>
#include <sstream>
using p58t::check;
struct Faults {long minor,major;};
Faults faults(){std::ifstream f("/proc/self/stat");std::string s;std::getline(f,s);std::istringstream in(s.substr(s.rfind(')')+2));std::string v;long a=0,b=0;for(int field=3;field<=12;++field){in>>v;if(field==10)a=std::stol(v);if(field==12)b=std::stol(v);}return {a,b};}
struct FileRows {
 int fd;size_t bytes;uint64_t reads=0;
 FileRows(const char* path,size_t n):bytes(n){fd=open(path,O_RDWR|O_CREAT|O_EXCL,0600);check(fd>=0,"scratch create");std::vector<uint8_t> chunk(65536);for(size_t off=0;off<n;){size_t k=std::min(n-off,chunk.size());for(size_t i=0;i<k;++i)chunk[i]=uint8_t((off+i)*37+((off+i)>>8));check(write(fd,chunk.data(),k)==ssize_t(k),"scratch write");off+=k;}}
 ~FileRows(){close(fd);}
 std::vector<uint8_t> read(size_t off,size_t n){check(off<=bytes&&n<=bytes-off,"source bounds");++reads;size_t aligned=off/4096*4096,delta=off-aligned;void* p=mmap(nullptr,n+delta,PROT_READ,MAP_PRIVATE,fd,aligned);check(p!=MAP_FAILED,"file mmap");auto b=static_cast<uint8_t*>(p)+delta;std::vector<uint8_t> r(b,b+n);check(munmap(p,n+delta)==0,"file unmap");return r;}
};
int main(int argc,char**argv){try{
 check(argc==2,"scratch path required");constexpr size_t rows=8192,rb=2100,ple_rb=90;FileRows file(argv[1],rows*rb);
 p58t::ResidentLookup resident(file.bytes,[&](size_t off,size_t n){return file.read(off,n);},[]{});
 check(resident.source_sha256==resident.resident_sha256,"copy hash differs");
 // Hash ALL source/copied bytes independently of constructor streaming hashes.
 p58t::Digest src,dst;for(size_t off=0;off<file.bytes;off+=65536){auto n=std::min(size_t(65536),file.bytes-off);auto b=file.read(off,n);src.add(b.data(),n);dst.add(resident.slice(off,n),n);}check(src.finish()==dst.finish(),"full independent hash differs");
 bool bounds=false;try{resident.slice(file.bytes-1,2);}catch(const std::exception&){bounds=true;}check(bounds,"overflow not refused");
 bool guard=false;try{p58t::ResidentLookup bad(4096,[&](size_t off,size_t n){return file.read(off,n);},[]{throw std::runtime_error("stop");});}catch(const std::exception&){guard=true;}check(guard,"stop not refused");
 uint64_t rng=0x58;std::vector<std::pair<size_t,size_t>> accesses;for(size_t token=0;token<1024;++token){rng=rng*6364136223846793005ull+1;accesses.push_back({size_t(rng%rows)*rb,rb});for(int j=0;j<16;++j){rng=rng*6364136223846793005ull+1;accesses.push_back({size_t(rng%(file.bytes/ple_rb))*ple_rb,ple_rb});}}
 auto run=[&](bool copied){p58t::Digest packed,outputs;uint64_t begin_reads=file.reads;auto before=faults();for(auto [off,n]:accesses){std::vector<uint8_t> b;if(copied){auto data=resident.slice(off,n);b.assign(data,data+n);}else b=file.read(off,n);packed.add(b.data(),n);auto type=n==rb?iq3::Type::Q6_K:iq3::Type::IQ4_NL;size_t count=n==rb?2560:160;std::vector<uint16_t> bf(count);for(size_t k=0;k<count;++k)bf[k]=iq3::bf16_bits(iq3::element(type,b.data(),k));outputs.add(bf.data(),bf.size()*2);}auto after=faults();return std::tuple{packed.finish(),outputs.finish(),after.major-before.major,after.minor-before.minor,file.reads-begin_reads};};
 auto original=run(false);auto warm=run(true);auto candidate=run(true);check(std::get<0>(original)==std::get<0>(candidate)&&std::get<1>(original)==std::get<1>(candidate),"packed/BF16 outputs differ");check(std::get<2>(candidate)==0&&std::get<4>(candidate)==0,"resident preparation faults or file reads");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"tokens\":1024,\"reads_per_token\":17,\"packed_bytes_per_token\":3540,\"fixture_bytes\":"<<file.bytes<<",\"source_sha256\":\""<<resident.source_sha256<<"\",\"resident_sha256\":\""<<resident.resident_sha256<<"\",\"packed_output_sha256\":\""<<std::get<0>(candidate)<<"\",\"bf16_output_sha256\":\""<<std::get<1>(candidate)<<"\",\"original_major_faults\":"<<std::get<2>(original)<<",\"resident_major_faults\":"<<std::get<2>(candidate)<<",\"resident_minor_faults\":"<<std::get<3>(candidate)<<",\"resident_file_reads\":"<<std::get<4>(candidate)<<",\"bounds_and_stop_refused\":true,\"cold_file_state_forced\":false}\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
