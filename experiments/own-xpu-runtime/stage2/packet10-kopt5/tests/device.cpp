#include "../kernels.hpp"
#include "../../packet9-kopt4/tests/expert_case.hpp"
#include "case.hpp"
#include "dense_case.hpp"
#include <filesystem>
#include <memory>
using namespace iq3;
using namespace expert_test;
void stop(int){stopping=1;}

int main(int argc,char** argv){
 if(argc!=7 || std::string(argv[1])!="--authorized-device-window")return 2;
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);std::unique_ptr<ownrt::Device> d;std::string error,failure_kind;unsigned checks=0;ownrt::Receipt teardown;
 try{require(std::string(argv[2])=="3","card3 only");std::string mode=argv[6];require(mode=="expanded_sg32" || mode=="expanded_split4","mode");unsigned split=mode=="expanded_split4"?4:1;
  d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3));
  for(auto& path:std::filesystem::directory_iterator(argv[3]))if(path.path().extension()==".fixture"){Fixture f(path.path());for(unsigned mutation=0;mutation<2;++mutation){dense_test::exercise_dense(expanded::gemv,*d,f,mutation,split);++checks;}}
  for(auto& path:std::filesystem::directory_iterator(std::filesystem::path(argv[3]).parent_path()/"cases")){
   ExpandedCase c(path.path());auto ex=expanded::expand(c.type,c.packed.data(),c.packed.size(),c.k);require(ex==c.expected,"Python/C++ expansion");Buffers b(*d,path.path().stem());
   auto w=b.allocate("weights",ex.size(),ownrt::Category::weights),y=b.allocate("values",c.values.size()*4,ownrt::Category::scratch);b.upload(w,ex.data(),ex.size(),"stage");require(!stopping,"stop before decode");wait(*d,expanded::dequant(*d,c.type,w,y,c.rows,c.k));b.equal(y,c.values.data(),c.values.size()*4,"dequantized bits");
   std::vector<uint16_t> x(c.k);for(unsigned i=0;i<c.k;++i)x[i]=bf16_bits(float(int(i%31)-15)/32);
   auto input=b.allocate("x",c.k*2,ownrt::Category::scratch),out=b.allocate("out",c.rows*2,ownrt::Category::scratch),fp=b.allocate("fp",c.rows*4,ownrt::Category::scratch);b.upload(input,x.data(),c.k*2,"x-stage");
   std::vector<float> expected(c.rows);std::vector<uint16_t> rounded(c.rows);
   for(unsigned r=0;r<c.rows;++r){float parts[4]{};for(unsigned s=0;s<split;++s){auto [lo,hi]=kopt2::bounds(c.k,s,split);float lanes[32]{};
    for(unsigned l=0;l<32;++l)for(size_t i=lo+l*8;i<hi;i+=256)for(unsigned j=0;j<8 && i+j<hi;++j){float product=c.values[r*c.k+i+j]*bits_float(uint32_t(x[i+j])<<16);lanes[l]=lanes[l]+product;}parts[s]=tree32(lanes);}
    expected[r]=split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);rounded[r]=bf16_bits(expected[r]);}
   kopt3::Matrix m;m.type=c.type;m.rows=c.rows;m.columns=c.k;m.w=w;m.x=input;m.y=out;m.fp32=fp;require(!stopping,"stop before case GEMV");wait(*d,expanded::gemv(*d,m,split).last);b.equal(fp,expected.data(),c.rows*4,"format GEMV FP32");b.equal(out,rounded.data(),c.rows*2,"format GEMV BF16");
   b.release();++checks;
  }
  // Full output-head geometry: bounded four-row real Q6 seed tiled in memory.
  Fixture head((std::filesystem::path(argv[3])/"real-Q6_K.fixture").string());require(head.columns==2560 && head.rows==4,"head K/rows");
  std::ifstream headfile(std::filesystem::path(argv[3]).parent_path()/"timing-input/output.weight.packed",std::ios::binary);headfile.read(reinterpret_cast<char*>(head.packed.data()),head.packed.size());char tail;require(bool(headfile) && !headfile.get(tail),"exact head seed extent");dense_test::exercise_dense(expanded::gemv,*d,head,0,split,true);++checks;
 }catch(const ExactnessFailure& e){error=e.what();failure_kind="exactness";}catch(const std::exception& e){error=e.what();failure_kind="infrastructure";}
 if(d){std::ofstream out(argv[5]);out<<d->arena.census()<<'\n';out.close();teardown=d->shutdown(std::chrono::seconds(10));}
 std::ofstream out(argv[4]);out<<"{\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<",\"failure_kind\":"<<ownrt::quote(failure_kind)<<",\"teardown\":"<<teardown.json()<<"}\n";out.close();if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty() || !teardown.safe_to_exit;
}
