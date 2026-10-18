// CPU-only direct test of the exact tile routine compiled into the device kernel.
#define main p62_unused_model_main
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet64-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet64-record-bundle/main.cpp"
#undef main
int main(int argc,char** argv){try{
 require(argc==2,"fixture output");fs::create_directories(argv[1]);
 using F=pipeline::SnapshotFlat;
 size_t total=1;std::vector<size_t> sizes,offsets;
 for(size_t i=0;i<975;++i){size_t n=std::array<size_t,10>{1,2,3,4,15,16,17,4095,4096,4097}[i%10];if(i==974)n=8388608;if(i==973)n=1609936;if(i==972)n=696320;offsets.push_back(total);sizes.push_back(n);total+=n+7;}
 std::vector<uint8_t> input(total),expected(total,0xcd),actual(total,0xcd);
 uint32_t random=0x62;for(auto& b:input){random=random*1664525+1013904223;b=random>>24;}
 ownrt::Device device(std::make_unique<Host>());
 auto source=device.arena.allocate("flat-source",total,Memory::device,Category::scratch,Lifetime::transaction);
 auto dest=device.arena.allocate("flat-destination",total,Memory::device,Category::scratch,Lifetime::transaction);
 auto table=device.arena.allocate("flat-descriptors",975*sizeof(F::Item),Memory::device,Category::runtime_overhead,Lifetime::process);
 std::memcpy(device.arena.row(source).pointer,input.data(),total);std::memcpy(device.arena.row(dest).pointer,actual.data(),total);
 std::vector<ownrt::PreparedCompute> checked;ownrt::CopyEngine copy(device);device.begin_capture(checked);
 for(size_t i=0;i<sizes.size();++i){copy.copy(dest,offsets[i],source,offsets[i],sizes[i],{});std::memcpy(expected.data()+offsets[i],input.data()+offsets[i],sizes[i]);}
 device.end_capture();require(checked.size()==975,"975 checked extents");
 std::vector<F::Item> rows;size_t tiles=0;
 for(size_t i=0;i<checked.size();++i){tiles+=(sizes[i]+F::tile-1)/F::tile;rows.push_back({static_cast<uint8_t*>(checked[i].pointers[0]),static_cast<const uint8_t*>(checked[i].pointers[1]),sizes[i],tiles});}
 std::memcpy(device.arena.row(table).pointer,rows.data(),rows.size()*sizeof(F::Item));
 F op;op.count=rows.size();op.tiles=tiles;std::array<Allocation,3> ids{table,source,dest};auto event=device.compute(op,ids,{});require(device.wait(event,std::chrono::seconds(30)),"fixture completion");
 std::memcpy(actual.data(),device.arena.row(dest).pointer,total);require(expected==actual,"flat tiles, tails or sentinel gaps differ");
 auto before=hash(expected),after=hash(actual);
 save(fs::path(argv[1])/"flat-fixture.json","{\"passed\":true,\"device_executed\":false,\"extent_count\":975,\"tile_count\":"+std::to_string(tiles)+",\"bytes_compared_including_sentinels\":"+std::to_string(total)+",\"expected_sha256\":"+ownrt::quote(before)+",\"actual_sha256\":"+ownrt::quote(after)+",\"same_device_copy_lane_body\":true}");
 device.arena.release(table);device.arena.release(dest);device.arena.release(source);auto receipt=device.shutdown(std::chrono::seconds(5));require(receipt.safe_to_exit,"fixture teardown");
 std::cout<<"flat 975 descriptors PASS "<<total<<" bytes\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
