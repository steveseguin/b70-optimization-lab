#include "argument_block.hpp"
#include <iostream>
#include <array>
#include <string>
struct DraftDenseOp {virtual ~DraftDenseOp()=default;unsigned a=1;};
struct DraftMergeOp {virtual ~DraftMergeOp()=default;unsigned width=16;};
struct SmallOp {virtual ~SmallOp()=default;std::string family="small.ffn";std::array<unsigned,4> metadata{1,2,3,4};unsigned count=4;};
struct Padded {bool flag;uint64_t id;};
struct SpecOp {virtual ~SpecOp()=default;Padded spec;int work=0;};
struct VectorOp {virtual ~VectorOp()=default;std::vector<Padded> matrices;unsigned variant=0;bool shared=false;};
struct Unknown {virtual ~Unknown()=default;int unregistered=1;};
struct Empty {virtual ~Empty()=default;};
int main(){
 SpecOp a,b;std::memset(&a.spec,0xaa,sizeof(a.spec));std::memset(&b.spec,0x55,sizeof(b.spec));a.spec.flag=b.spec.flag=true;a.spec.id=b.spec.id=17;
 if(ownrt::arguments::block(a)!=ownrt::arguments::block(b))return 1;
 b.spec.id=18;if(ownrt::arguments::block(a)==ownrt::arguments::block(b))return 2;
 b=a;b.work=1;if(ownrt::arguments::block(a)==ownrt::arguments::block(b))return 3;
 VectorOp x,y;x.matrices.push_back(a.spec);y=x;if(ownrt::arguments::block(x)!=ownrt::arguments::block(y))return 4;
 y.matrices[0].id++;if(ownrt::arguments::block(x)==ownrt::arguments::block(y))return 5;
 y=x;y.variant=1;if(ownrt::arguments::block(x)==ownrt::arguments::block(y))return 6;
 y=x;y.shared=true;if(ownrt::arguments::block(x)==ownrt::arguments::block(y))return 7;
 bool rejected=false;try{ownrt::arguments::block(Unknown{});}catch(const std::logic_error&){rejected=true;}if(!rejected)return 8;
 if(ownrt::arguments::block(Empty{}).empty())return 9;
 DraftDenseOp dense0,dense1;if(ownrt::arguments::block(dense0)!=ownrt::arguments::block(dense1))return 10;
 dense1.a++;if(ownrt::arguments::block(dense0)==ownrt::arguments::block(dense1))return 11;
 DraftMergeOp merge0,merge1;merge1.width++;if(ownrt::arguments::block(merge0)==ownrt::arguments::block(merge1))return 12;
 SmallOp small0,small1;if(ownrt::arguments::block(small0)!=ownrt::arguments::block(small1))return 13;
 small1.family="small.qsa";if(ownrt::arguments::block(small0)==ownrt::arguments::block(small1))return 14;
 small1=small0;small1.metadata[2]++;if(ownrt::arguments::block(small0)==ownrt::arguments::block(small1))return 15;
 small1=small0;small1.count--;if(ownrt::arguments::block(small0)==ownrt::arguments::block(small1))return 16;
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":16,\"padding_canonicalized\":true,\"unknown_operation_rejected\":true}\n";
}
