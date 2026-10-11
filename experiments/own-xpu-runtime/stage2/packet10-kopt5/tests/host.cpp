#include <filesystem>
#include "fixture.hpp"
#include "case.hpp"
#include "dense_case.hpp"
#include "../../packet9-kopt4/tests/mock_experts.hpp"
#include <filesystem>
#include <iostream>
using namespace iq3;
uint64_t checks=0,rows=0;
void equal(float a,float b){if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b))throw std::runtime_error("FP32 bit mismatch");++checks;}
int main(int argc,char** argv){try{
 if(argc!=2)throw std::runtime_error("fixtures required");unsigned fixtures=0;
 for(auto& path:std::filesystem::directory_iterator(argv[1]))if(path.path().extension()==".fixture"){
  Fixture f(path.path());++fixtures;
  for(size_t k:{size_t(1),size_t(7),size_t(32),size_t(320),size_t(640),size_t(256),size_t(768),size_t(2560),size_t(10240),size_t(17408)}){
   auto l=layout(f.type);if(k%l.elements)continue;size_t rb=k/l.elements*l.bytes;std::vector<uint8_t> packed(5*rb);for(size_t i=0;i<packed.size();++i)packed[i]=f.packed[i%f.packed.size()];
   auto e=expanded::expand(f.type,packed.data(),packed.size(),k);size_t erb=expanded::row_bytes(f.type,k);
   for(unsigned r=0;r<5;++r)for(size_t i=0;i<k;++i)equal(expanded::value(f.type,e.data()+r*erb,k,i),element(f.type,packed.data()+r*rb,i));
   for(unsigned mutation=0;mutation<3;++mutation){std::vector<uint16_t> x(k);for(size_t i=0;i<k;++i)x[i]=f.x[i%f.x.size()]^(mutation==1?0x8000:0);if(mutation==2)for(size_t i=0;i<k;++i)x[i]=i%2?0x8000:0;
    for(unsigned s:{1u,4u})for(unsigned r=0;r<5;++r){float a=expanded::row(f.type,e.data()+r*erb,x.data(),f.activation,k,s);float b=kopt2::row(f.type,packed.data()+r*rb,x.data(),f.activation,k,s==1?kopt2::Variant::wide32:kopt2::Variant::split4);equal(a,b);if(output_bits(a,f.output_type)!=output_bits(b,f.output_type))throw std::runtime_error("cast");++rows;}
   }
  }
 }
 unsigned mock_cases=0;
 for(unsigned split:{1u,4u}){
  auto backend=std::make_unique<expert_test::CpuDevice>();ownrt::Device d(std::move(backend));
  auto launch=[](ownrt::Device& device,const kopt3::Matrix& m,unsigned parts){
   expert_test::CpuOperation op;op.run=[=](std::span<void* const> ptrs){
    auto w=static_cast<const uint8_t*>(ptrs[0]);auto x=static_cast<const uint16_t*>(ptrs[1]);auto y=static_cast<uint16_t*>(ptrs[2]);auto fp=static_cast<float*>(ptrs[3]);auto rb=expanded::row_bytes(m.type,m.columns);
    for(unsigned r=0;r<m.rows;++r){fp[r]=expanded::row(m.type,w+r*rb,x,m.activation,m.columns,parts);y[r]=output_bits(fp[r],m.output_type);}
   };std::array ids{m.w,m.x,m.y,m.fp32};auto e=device.compute(op,ids,{});return kopt3::Launch{e,e,1};
  };
  for(auto& path:std::filesystem::directory_iterator(argv[1]))if(path.path().extension()==".fixture"){
   Fixture f(path.path());for(unsigned mutation=0;mutation<2;++mutation){dense_test::exercise_dense(launch,d,f,mutation,split);++mock_cases;}
  }
  auto receipt=d.shutdown(std::chrono::seconds(10));if(!receipt.safe_to_exit || receipt.live_bytes || receipt.in_flight)throw std::runtime_error("mock teardown");
 }
 if(fixtures!=27)throw std::runtime_error("fixture count");unsigned cases=0;
 auto directory=std::filesystem::path(argv[1]).parent_path()/"cases";
 if(std::filesystem::exists(directory))for(auto& path:std::filesystem::directory_iterator(directory)){
  ExpandedCase c(path.path());auto e=expanded::expand(c.type,c.packed.data(),c.packed.size(),c.k);if(e!=c.expected)throw std::runtime_error("Python/C++ expansion bytes: "+path.path().string());
  size_t rb=expanded::row_bytes(c.type,c.k);for(unsigned r=0;r<c.rows;++r)for(unsigned i=0;i<c.k;++i)equal(expanded::value(c.type,e.data()+r*rb,c.k,i),c.values[r*c.k+i]);++cases;
 }
 std::cout<<"{\"passed\":true,\"fixtures\":"<<fixtures<<",\"value_and_row_comparisons\":"<<checks<<",\"rows\":"<<rows<<",\"python_format_cases\":"<<cases<<",\"mock_dense_cases\":"<<mock_cases<<"}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
