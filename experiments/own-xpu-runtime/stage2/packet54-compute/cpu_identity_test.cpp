#include "recurrence_test.hpp"
#include "route_test.hpp"
#include "hc_ffn_test.hpp"
#include <openssl/sha.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
namespace {
std::string sha256(const uint8_t*data,size_t size){unsigned char digest[SHA256_DIGEST_LENGTH];SHA256(data,size,digest);std::ostringstream out;for(auto c:digest)out<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return out.str();}
struct Range {const char*name;size_t begin,end;};
}
int main(int argc,char**argv){try{
 std::string dump_path;
 if(argc!=1){if(argc!=3||std::string(argv[1])!="--dump-bytes"||!argv[2][0])throw std::invalid_argument("usage: cpu-identity-test [--dump-bytes PATH]");dump_path=argv[2];}
 std::vector<uint8_t> bytes,exception_bytes;std::vector<Range> ranges;std::vector<p54hc_test::ByteRange>hc_ranges;unsigned checks=0;
 auto run=[&](const char*name,auto test){size_t begin=bytes.size();checks+=test(bytes);ranges.push_back({name,begin,bytes.size()});};
 run("gdn.recurrence",p54test::test_recurrence);run("route",test_route);size_t hc_legacy_begin=bytes.size();run("hc_ffn",[&](std::vector<uint8_t>&v){return test_hc_ffn(v,exception_bytes,&hc_ranges);});
 if(!dump_path.empty()){auto write=[&](const std::string&path,const std::vector<uint8_t>&v){std::ofstream out(path,std::ios::binary|std::ios::trunc);if(!out)throw std::runtime_error("cannot open diagnostic byte dump");out.write(reinterpret_cast<const char*>(v.data()),std::streamsize(v.size()));out.close();if(!out)throw std::runtime_error("incomplete diagnostic byte dump");};write(dump_path,bytes);write(dump_path+".exceptions",exception_bytes);}
 unsigned exception_checks=0;for(const auto&r:hc_ranges)exception_checks+=r.exceptional;
 std::cout<<"{\"schema\":\"ownrt.packet54.cpu_identity.v1\",\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"rows_checked\":"<<checks<<",\"output_bytes\":"<<bytes.size()<<",\"output_sha256\":\""<<sha256(bytes.data(),bytes.size())<<"\",\"exception_bytes\":"<<exception_bytes.size()<<",\"exception_sha256\":\""<<sha256(exception_bytes.data(),exception_bytes.size())<<"\",\"exception_checks\":"<<exception_checks;
 if(!dump_path.empty()){std::cout<<",\"diagnostic_ranges\":[";for(size_t i=0;i<ranges.size();++i){const auto&r=ranges[i];std::cout<<(i?",":"")<<"{\"class\":\""<<r.name<<"\",\"begin\":"<<r.begin<<",\"end\":"<<r.end<<",\"bytes\":"<<r.end-r.begin<<",\"sha256\":\""<<sha256(bytes.data()+r.begin,r.end-r.begin)<<"\"}";}std::cout<<"],\"hc_check_ranges\":[";for(size_t i=0;i<hc_ranges.size();++i){const auto&r=hc_ranges[i];std::cout<<(i?",":"")<<"{\"check\":\""<<r.label<<"\",\"stream\":\""<<(r.exceptional?"exceptions":"output")<<"\",\"legacy_begin\":"<<hc_legacy_begin+r.legacy_begin<<",\"legacy_end\":"<<hc_legacy_begin+r.legacy_end<<",\"begin\":"<<r.begin<<",\"end\":"<<r.end<<"}";}std::cout<<"]";}
 std::cout<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
