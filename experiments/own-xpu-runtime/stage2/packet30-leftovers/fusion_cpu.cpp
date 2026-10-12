#include "fusion.hpp"
#include <cstdio>
int main(){size_t checks=0,cases=0,rejections=0;for(int op:{int(ng::combine_norm),int(ng::norm),int(ng::mix)})for(int width:{1,3,17,31,32,33,255,2560})for(int flags:{0,1,8,9})for(int position:{1,3,87,255})for(auto variant:{"sg32","tiled"}){
 ng::Shape s;s.op=op;s.width=width;s.flags=flags;s.capacity=256;p30::fusion::Fixture a(s),b(s),c(s);a.args.i(17)[0]=b.args.i(17)[0]=c.args.i(17)[0]=position;
 p30::fusion::cpu(s,a.args,a.sizes,variant);ng::cpu(s,b.args);specialised::cpu(s,c.args);for(int slot:{op==ng::combine_norm?4:2,op==ng::combine_norm?5:2}){if(a.storage[slot]!=b.storage[slot]||a.storage[slot]!=c.storage[slot]){std::fprintf(stderr,"FAIL op=%d width=%d flags=%d pos=%d\n",op,width,flags,position);return 1;}checks+=a.storage[slot].size()*2;}++cases;
 auto bad=a.sizes;bad[0]=1;try{p30::fusion::validate(s,a.args,bad,variant);return 2;}catch(const std::invalid_argument&){++rejections;}
 auto shifted=a.args;shifted.p[0]=reinterpret_cast<void*>(reinterpret_cast<uintptr_t>(shifted.p[0])+1);try{p30::fusion::validate(s,shifted,a.sizes,variant);return 3;}catch(const std::invalid_argument&){++rejections;}
 shifted=a.args;shifted.p[15]=a.args.p[0];try{p30::fusion::validate(s,shifted,a.sizes,variant);return 4;}catch(const std::invalid_argument&){++rejections;}
 }std::printf("{\"passed\":true,\"cases\":%zu,\"compared_bytes\":%zu,\"validation_rejections\":%zu}\n",cases,checks,rejections);return 0;}
