// Reuse the exact actual-loader GGUF fixtures and extracted Weights methods.
#define main original_lookup_view_fixture_main
#include "../lookup-view-candidate/test_lookup_view.cpp"
#undef main
#include "sparse_rows.hpp"
struct SparseFixture {
 LookupFixture backing;
 ownrt::SparseRows rows;
 std::array<std::string,2> names;
 size_t reads=0,misses=0;
 SparseFixture(const Files& f,size_t cap=8192,size_t slots=32)
  :backing(fixture(f)),rows({{{96,136},{96,90}}},cap,slots),
   names{f.plan[0].name,f.plan[1].name} {backing.map_lookups();}
 void verify() const {backing.verify_lookup_views();}
 void stage(std::span<const ownrt::SparseRows::Key> keys) {
  rows.stage(keys,[&]{verify();},[&](uint32_t table,size_t off,size_t n,uint8_t* out){
   ++reads;auto source=backing.model->slice(names.at(table),off,n);
   source.verify_backing();std::memcpy(out,source.data(),n);source.verify_backing();
  });
 }
 auto read(uint32_t table,size_t off,size_t n) {
  return rows.read(table,off,n,[&]{verify();},[&]{++misses;return backing.read(names.at(table),off,n);});
 }
};
Files varied_files(const fs::path& dir) {
 auto f=files(dir);
 // Distinct valid quant nibbles per row catch wrong-row/offset staging.
 for(size_t t=0;t<2;++t) {
  std::fstream io(f.paths[t],std::ios::in|std::ios::out|std::ios::binary);
  size_t rb=f.plan[t].bytes/96;
  for(size_t row=0;row<96;++row) {
   io.seekp(f.data_offsets[t]+row*rb+rb-1);char value=char((row*37+t*11)&255);io.write(&value,1);
  }
  io.close();require(bool(io),"vary fixture rows");f.admission.shards[t]=identity(f.paths[t]);
 }
 return f;
}
int main(int argc,char**argv){try{
 require(argc==2,"exclusive fixture root required");fs::path root=argv[1];require(fs::create_directory(root),"exclusive root");
 auto f=varied_files(root/"rows");auto copied=fixture(f);copied.copy_lookups();SparseFixture sparse(f);
 require(sparse.rows.owned_bytes()==8192,"hard total includes flat index and owner");
 std::vector<ownrt::SparseRows::Key> keys{{4,1},{2,0},{1,0},{2,0},{3,0},{5,1}};
 sparse.stage(keys);require(sparse.rows.entries()==5 && sparse.reads==2,"duplicate removal and adjacent coalescing");
 size_t floats=0;
 for(size_t table=0;table<2;++table){auto& p=f.plan[table];size_t rb=p.bytes/96,columns=p.dimensions[0];
  for(size_t row=0;row<96;++row){auto a=copied.read(p.name,row*rb,rb),b=sparse.read(table,row*rb,rb);require(a==b,"all staged and cold miss bytes");
   for(size_t k=0;k<columns;++k){require(std::bit_cast<uint32_t>(gsq::element(unsigned(p.type),a,columns,k))==std::bit_cast<uint32_t>(gsq::element(unsigned(p.type),b,columns,k)),"F32 exact staged/miss");++floats;}
  }
  require(sparse.read(table,rb+7,rb+11)==copied.read(p.name,rb+7,rb+11),"partial spanning read");
  refuses([&]{sparse.read(table,p.bytes-1,2);});
 }
 auto prior_misses=sparse.misses;require(sparse.read(0,136+1,136*2)==copied.read(f.plan[0].name,137,272),"partial all-hit bytes");require(sparse.misses==prior_misses,"all-hit partial stays staged");
 std::array<ownrt::SparseRows::Key,1> replacement{{{90,0}}};sparse.stage(replacement);
 require(sparse.rows.entries()==1,"replacement eviction");prior_misses=sparse.misses;
 require(sparse.read(0,136,136)==copied.read(f.plan[0].name,136,136)&&sparse.misses==prior_misses+1,"evicted row exact backing");
 std::array<ownrt::SparseRows::Key,1> bad{{{96,0}}};refuses([&]{sparse.stage(bad);});require(sparse.rows.entries()==0,"failed stage never published");
 std::array<ownrt::SparseRows::Key,1> foreign{{{0,2}}};refuses([&]{sparse.stage(foreign);});
 refuses([&]{sparse.read(2,0,1);});
 SparseFixture tiny(f,512,4);std::array<ownrt::SparseRows::Key,3> too_big{{{0,0},{1,0},{2,0}}};refuses([&]{tiny.stage(too_big);});require(tiny.rows.entries()==0,"capacity fail no publication");
 std::array<ownrt::SparseRows::Key,5> too_many{};refuses([&]{tiny.stage(too_many);});
 sparse.rows.clear();require(sparse.rows.entries()==0,"independent request clear");
 // Identity mutation after valid arithmetic must reject before publication.
 auto m=files(root/"mutation");SparseFixture mut(m);mut.stage(replacement);auto pending=mut.read(0,90*136,136);
 mutate(m.paths[0],m.data_offsets[0]);refuses([&]{mut.verify();});refuses([&]{mut.read(0,90*136,136);});refuses([&]{mut.stage(replacement);});require(mut.rows.entries()==0,"mutated staging never published");
 // Mutation during a read group is caught by the final guard before publication.
 auto mid=files(root/"midstage");auto back=fixture(mid);back.map_lookups();ownrt::SparseRows rows({{{96,136},{96,90}}},8192,32);
 refuses([&]{rows.stage(replacement,[&]{back.verify_lookup_views();},[&](uint32_t t,size_t off,size_t n,uint8_t*out){auto s=back.model->slice(mid.plan[t].name,off,n);std::memcpy(out,s.data(),n);mutate(mid.paths[t],mid.data_offsets[t]);});});require(rows.entries()==0,"mid-stage mutation unpublished");
 std::cout<<"{\"passed\":true,\"f32_values\":"<<floats<<",\"source_reads_for_five_staged_rows\":2,\"model_payload_reads\":false,\"device_calls\":0}\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
