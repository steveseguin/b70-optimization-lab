// Pure checked geometry; the Engine allocator independently retains its per-allocation cap.
inline size_t checkpoint_ring_reserve(size_t bytes,size_t rows,size_t depth,size_t owned){
 constexpr size_t slot_limit=256ull*1024*1024,row_limit=4096,device_limit=30ull*1024*1024*1024;
 require(bytes&&bytes<=slot_limit&&rows&&rows<=row_limit&&(depth==2||depth==3),"ring backup geometry bound");
 const size_t reserve=depth*(bytes+2*rows*sizeof(SnapshotFlat::Item));
 require(reserve<=depth*(slot_limit+2*row_limit*sizeof(SnapshotFlat::Item)),"ring derived total backup/table reserve");
 require(owned<=device_limit&&reserve<=device_limit-owned,"ring complete reserve exceeds per-card arena admission");
 return reserve;
}
