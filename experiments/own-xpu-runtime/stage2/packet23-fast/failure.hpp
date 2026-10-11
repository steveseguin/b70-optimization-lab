#pragma once
#include "owner.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <openssl/sha.h>
#include <iomanip>
#include <sstream>
namespace packet23 {
struct Borrower {ownrt::Device& d;std::string name;Borrower(ownrt::Device& d,std::string n):d(d),name(std::move(n)){ownrt::register_borrower(d,name);}~Borrower(){ownrt::unregister_borrower(d,name);}};
inline std::string hash(const void* p,size_t n){unsigned char h[32];SHA256(static_cast<const unsigned char*>(p),n,h);std::ostringstream s;for(auto b:h)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);return s.str();}
inline void row(const std::filesystem::path& out,const std::string& label,const void* p,size_t n,bool passed=true){if(out.empty())return;std::filesystem::create_directories(out);std::ofstream f(out/"fixture-rows.jsonl",std::ios::app);f<<"{\"label\":"<<ownrt::quote(label)<<",\"passed\":"<<(passed?"true":"false")<<",\"sha256\":"<<ownrt::quote(hash(p,n))<<",\"bytes\":"<<n<<"}\n";f.flush();}
inline void failure(ownrt::Device& d,const std::filesystem::path& out,const std::string& error) {
 auto write=[&](const ownrt::Receipt& r){auto text="{\"passed\":false,\"error\":"+ownrt::quote(error)+",\"teardown\":"+r.json()+"}\n";std::cerr<<text<<std::flush;if(!out.empty()){std::filesystem::create_directories(out);std::ofstream f(out/"failure.json");f<<text;f.flush();}};
 write(ownrt::snapshot(d,error));auto r=d.shutdown(std::chrono::seconds(60));write(r);
 if(r.in_flight){std::cerr<<"Work genuinely still in flight; event list above.\n"<<std::flush;ownrt::hold_for_supervisor();}
}
}
