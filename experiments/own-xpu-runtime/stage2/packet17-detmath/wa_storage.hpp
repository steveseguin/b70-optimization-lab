// Packet17 lossless, bounded reference slabs. No device API or math evaluation.
#pragma once
#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>
#include <zlib.h>
namespace census {
static_assert(std::endian::native==std::endian::little);
constexpr uint64_t slab_magic=0x3152464552373150ULL; // P17REFR1
// Delta byte planes make smooth binary32 references compact; zlib is lossless.
std::vector<unsigned char> pack_words(const std::vector<uint32_t>& words){
 std::vector<unsigned char> planes(words.size()*4);uint32_t prior=0;
 for(size_t i=0;i<words.size();++i){uint32_t d=words[i]-prior;prior=words[i];for(unsigned k=0;k<4;++k)planes[k*words.size()+i]=d>>(8*k);}
 uLongf n=compressBound(planes.size());std::vector<unsigned char> packed(n);
 if(compress2(packed.data(),&n,planes.data(),planes.size(),1)!=Z_OK)throw std::runtime_error("reference compression");packed.resize(n);return packed;
}
std::vector<uint32_t> unpack_words(const std::vector<unsigned char>& packed,size_t count){
 std::vector<unsigned char> planes(count*4);uLongf n=planes.size();
 if(uncompress(planes.data(),&n,packed.data(),packed.size())!=Z_OK||n!=planes.size())throw std::runtime_error("reference slab corrupt");
 std::vector<uint32_t> words(count);uint32_t prior=0;
 for(size_t i=0;i<count;++i){uint32_t d=0;for(unsigned k=0;k<4;++k)d|=uint32_t(planes[k*count+i])<<(8*k);words[i]=prior+=d;}return words;
}
void write_slab(std::ostream& f,uint64_t start,const std::vector<uint32_t>& refs,const std::vector<Trace>& args){
 Stats h;for(size_t i=0;i<refs.size();++i){uint64_t v=mix((uint64_t(refs[i])<<32)^(start+i));h.sum+=v;h.xor_hash^=v;}
 auto words=refs;if(!args.empty()){if(args.size()!=refs.size())throw std::runtime_error("argument count");size_t old=words.size();words.resize(old+args.size()*4);std::memcpy(words.data()+old,args.data(),args.size()*16);}
 auto packed=pack_words(words);std::array<uint64_t,7> header{slab_magic,start,refs.size(),args.empty()?0ULL:1ULL,packed.size(),h.sum,h.xor_hash};
 f.write(reinterpret_cast<const char*>(header.data()),sizeof(header));f.write(reinterpret_cast<const char*>(packed.data()),packed.size());if(!f)throw std::runtime_error("reference write failed");
}
std::pair<uint64_t,uint64_t> read_slab(std::istream& f,uint64_t start,uint64_t n,bool explicit_args,uint32_t* refs,Trace* args){
 std::array<uint64_t,7> h{};f.read(reinterpret_cast<char*>(h.data()),sizeof(h));
 if(!f||h[0]!=slab_magic||h[1]!=start||h[2]!=n||h[3]!=uint64_t(explicit_args)||n>262144||h[4]>compressBound(n*(explicit_args?20:4)))throw std::runtime_error("reference slab header/coverage");
 std::vector<unsigned char> packed(h[4]);f.read(reinterpret_cast<char*>(packed.data()),packed.size());if(!f)throw std::runtime_error("reference slab truncated");
 auto words=unpack_words(packed,n*(explicit_args?5:1));std::copy_n(words.data(),n,refs);if(explicit_args)std::memcpy(args,words.data()+n,n*16);return {h[5],h[6]};
}
void end_slabs(std::istream& f){if(f.peek()!=std::char_traits<char>::eof())throw std::runtime_error("trailing reference slabs");}
}
