// Extend packet59's bounded production-width fixtures with unfused schedules.
#define main inherited_p59_fixture_main
#include "p59_fixture.cpp"
#undef main
int main(int argc,char**argv){
 if(int result=inherited_p59_fixture_main(argc,argv))return result;
 std::ofstream out(argv[1],std::ios::binary|std::ios::app);
 dense<2560,true,true,8,1>(out,p59::none,2);
 dense<2560,false,false,1,1>(out,p59::none);
 dense<640,false,false,4,1>(out,p59::none);
 dense<10240,false,false,1,4>(out,p59::none);
 dense<6144,false,false,1,4>(out,p59::none);
 return out?0:2;
}
