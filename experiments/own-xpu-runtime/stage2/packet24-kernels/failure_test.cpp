#include "failure.hpp"
#include <cstring>
struct Mock:ownrt::Backend {
 bool parameters_mode=false;
 std::string identity()const override{return "failure-mock";}
 void* allocate(size_t n,ownrt::Memory)override{return ::operator new(n);}void release(void* p,ownrt::Memory)override{::operator delete(p);}
 ownrt::Event copy(void* d,const void* s,size_t n,std::span<const ownrt::Event>)override{std::memcpy(d,s,n);return ownrt::next_handle();}
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>)override{if(parameters_mode){int values[4]{1,2,3,4};auto a=ownrt::submission_parameters(values,sizeof values);auto b=ownrt::submission_parameters(values,sizeof values);if(a!=b)throw std::runtime_error("parameter cache miss");return ownrt::next_handle();}throw std::runtime_error("injected first kernel build failure");}
 bool complete(ownrt::Event)override{return true;}bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
int main(int argc,char**argv){if(argc!=3)return 2;auto backend=std::make_unique<Mock>();backend->parameters_mode=std::string(argv[1])=="parameters";ownrt::Device d(std::move(backend));try {
 auto a=d.arena.allocate("test",4,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);
 if(std::string(argv[1])=="borrower"){ownrt::register_borrower(d,"injected executable bundle");throw std::runtime_error("borrower alive at shutdown");}
 ownrt::Operation op;auto e=d.compute(op,std::span(&a,1),{});if(!d.wait(e,std::chrono::seconds(1)))return 2;auto receipt=d.shutdown(std::chrono::seconds(1));if(!receipt.safe_to_exit||receipt.live_bytes)return 2;
 }catch(const std::exception& e){packet23::failure(d,argv[2],e.what());packet23::failure(d,argv[2],e.what());return 1;}return 0;}
