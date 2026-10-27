#include <iostream>
#include <stdexcept>
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/snapshot_geometry.hpp"
using namespace pipeline::snapshot_geometry;
void require(bool value,const char* why){if(!value)throw std::runtime_error(why);}
int main(){try{
 // Depth1/default pooled geometry: exactly the original ((context-1)/4)*stride formula.
 require(checked_max_offset(128,8,8,4,0,64,false)==120,"pooled divisor maximum");
 require(row_index(3,4,0)==0&&row_index(4,4,0)==1&&row_index(63,4,0)==15,"pooled row indices");
 require(checked_max_offset(128,8,8,4,0,64,false)+8==128,"pooled end extent");
 // Ordinary non-pooled rows retain the original divisor-one formula.
 require(checked_max_offset(512,8,8,1,0,64,false)==504,"default row maximum");
 // Raw rings use their actual row count and modulo position, not context-sized geometry.
 require(checked_max_offset(32,8,8,1,4,64,true)==24,"raw-ring maximum");
 require(row_index(5,1,4)==1&&row_index(64,1,4)==0,"raw-ring modulo indices");
 bool refused=false;try{(void)checked_max_offset(16,8,8,4,0,64,false);}catch(const std::invalid_argument&){refused=true;}
 require(refused,"out-of-range static extent must be refused");
 std::cout<<"{\"passed\":true,\"pooled_max_offset\":120,\"pooled_end\":128,\"default_max_offset\":504,\"ring_max_offset\":24,\"range_refusal\":true}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}return 0;}
