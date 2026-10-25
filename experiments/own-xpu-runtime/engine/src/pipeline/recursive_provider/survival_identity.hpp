#pragma once
#include "pipeline/ring/stage_ring.hpp"
#include <sstream>
#include <iomanip>
#include <span>
#include <cmath>
namespace ownrt::provider_survival {
inline std::string quote(const std::string& value){std::ostringstream out;out<<'"';for(unsigned char c:value){if(c=='"'||c=='\\')out<<'\\'<<c;else if(c<32)out<<"\\u00"<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c)<<std::dec;else out<<c;}out<<'"';return out.str();}
inline std::string sha(std::span<const uint8_t> value){ring_next::Digest d{};SHA256(value.data(),value.size(),d.data());constexpr char hex[]="0123456789abcdef";std::string out;for(auto b:d){out+=hex[b>>4];out+=hex[b&15];}return out;}
inline std::string sha(const std::string& value){return sha({reinterpret_cast<const uint8_t*>(value.data()),value.size()});}
struct Identity {
 std::vector<uint8_t> data;
 void integer(uint64_t n){ring_next::need(data.size()<=16ull*1024*1024-8,"bounded survival integer identity");for(int i=0;i<8;++i)data.push_back(uint8_t(n>>(8*i)));}
 void bytes(std::span<const uint8_t> b){ring_next::need(data.size()<=16ull*1024*1024-8&&b.size()<=16ull*1024*1024-8-data.size(),"bounded survival host identity");integer(b.size());data.insert(data.end(),b.begin(),b.end());}
 void text(const std::string& text){bytes({reinterpret_cast<const uint8_t*>(text.data()),text.size()});}
 template<class T>void numbers(const T& values){integer(std::size(values));for(auto value:values)integer(uint64_t(value));}
 std::string digest()const{return sha(data);}
};
inline std::string row_json(const ring_next::Row& row){std::ostringstream out;out<<"{\"epoch\":"<<row.epoch<<",\"id\":"<<row.id<<",\"parent\":"<<row.parent<<",\"ticket\":"<<row.ticket<<",\"position\":"<<row.position<<",\"token\":"<<row.token<<",\"fixture\":"<<row.fixture<<",\"tentative\":"<<(row.tentative?"true":"false");auto hex=[](const ring_next::Digest& d){constexpr char h[]="0123456789abcdef";std::string s;for(auto b:d){s+=h[b>>4];s+=h[b&15];}return s;};out<<",\"request\":"<<quote(hex(row.request))<<",\"before\":"<<quote(hex(row.before))<<",\"after\":"<<quote(hex(row.after))<<"}";return out.str();}
}
