#include <cstddef>
#include <cassert>
#include <stdexcept>
#include <limits>
using std::size_t;
void require(bool b,const char*){if(!b)throw std::runtime_error("refused");}
struct SnapshotFlat{struct Item{size_t x[4];};};
// Pure checked geometry; the Engine allocator independently retains its per-allocation cap.
inline size_t checkpoint_ring_reserve(size_t bytes,size_t rows,size_t depth,size_t owned){
 constexpr size_t slot_limit=256ull*1024*1024,row_limit=4096,device_limit=30ull*1024*1024*1024;
 require(bytes&&bytes<=slot_limit&&rows&&rows<=row_limit&&(depth==2||depth==3),"ring backup geometry bound");
 const size_t reserve=depth*(bytes+2*rows*sizeof(SnapshotFlat::Item));
 require(reserve<=depth*(slot_limit+2*row_limit*sizeof(SnapshotFlat::Item)),"ring derived total backup/table reserve");
 require(owned<=device_limit&&reserve<=device_limit-owned,"ring complete reserve exceeds per-card arena admission");
 return reserve;
}

template<class F>void refuses(F f){bool caught=false;try{f();}catch(const std::runtime_error&){caught=true;}assert(caught);}
int main(){constexpr size_t cap=30ull*1024*1024*1024;
 assert(checkpoint_ring_reserve(225525896,1205,3,0)==676809048);
 assert(checkpoint_ring_reserve(225498248,1187,2,0)==451148432);
 assert(checkpoint_ring_reserve(225525896,1205,3,cap-676809048)==676809048);
 refuses([&]{checkpoint_ring_reserve(225525896,1205,3,cap-676809048+1);});
 assert(checkpoint_ring_reserve(256ull*1024*1024,4096,3,0)==806092800);
 for(size_t bytes:{size_t(0),size_t(256ull*1024*1024+1),std::numeric_limits<size_t>::max()})refuses([&]{checkpoint_ring_reserve(bytes,1,3,0);});
 for(size_t rows:{size_t(0),size_t(4097),std::numeric_limits<size_t>::max()})refuses([&]{checkpoint_ring_reserve(1,rows,3,0);});
 for(size_t depth:{size_t(0),size_t(1),size_t(4),std::numeric_limits<size_t>::max()})refuses([&]{checkpoint_ring_reserve(1,1,depth,0);});
 refuses([&]{checkpoint_ring_reserve(1,1,3,cap+1);});
 auto item=[](size_t saved,size_t total){require(saved&&saved<=256ull*1024*1024&&total<=256ull*1024*1024-saved,"item");};
 item(256ull*1024*1024,0);refuses([&]{item(256ull*1024*1024+1,0);});refuses([&]{item(std::numeric_limits<size_t>::max(),0);});refuses([&]{item(1,256ull*1024*1024);});
}
