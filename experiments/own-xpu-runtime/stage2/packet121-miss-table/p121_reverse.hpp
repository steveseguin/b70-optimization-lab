#pragma once
// Packet121: reverse the admitted capture table without another host upload.
// The table has the original SnapshotFlat ABI and owns no model arithmetic.
#ifdef OWN_RT_HOST_ONLY
struct SnapshotReverse final:integrated::HostOperation {
#else
struct SnapshotReverse final:ownrt::SyclOperation {
#endif
 size_t count=0,tiles=0,first_tile=0;
 static void copy_lane(const SnapshotFlat::Item* rows,size_t n,size_t tile_id,size_t lane) {
  size_t lo=0,hi=n;
  while(lo<hi){size_t mid=(lo+hi)/2;if(rows[mid].end_tile<=tile_id)lo=mid+1;else hi=mid;}
  auto row=rows[lo];size_t start=lo?rows[lo-1].end_tile:0;
  size_t off=(tile_id-start)*SnapshotFlat::tile+lane*16;
  auto dst=const_cast<uint8_t*>(row.src);const auto* src=row.dst;
  for(size_t j=0;j<16&&off+j<row.bytes;++j)dst[off+j]=src[off+j];
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto rows=static_cast<const SnapshotFlat::Item*>(p[0]);
  for(size_t t=first_tile;t<first_tile+tiles;++t)
   for(size_t lane=0;lane<SnapshotFlat::lanes;++lane)copy_lane(rows,count,t,lane);
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto rows=static_cast<const SnapshotFlat::Item*>(p[0]);auto n=count,total=tiles,first=first_tile;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(total*SnapshotFlat::lanes,SnapshotFlat::lanes),[=](sycl::nd_item<1> id){
    copy_lane(rows,n,first+id.get_group_linear_id(),id.get_local_linear_id());
   });
  });
 }
#endif
};
