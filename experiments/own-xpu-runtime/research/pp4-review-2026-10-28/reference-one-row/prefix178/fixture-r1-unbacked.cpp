#define main prefix178_tool_main
#include "exact-logits-prefix178.cpp"
#undef main
#include <cassert>
#include <filesystem>
int main(int argc,char**argv){assert(argc==2);assert(std::filesystem::create_directory(argv[1]));CombinedCapture c;c.layers.out=argv[1];c.routers.out=argv[1];c.layers.batch_tokens=c.routers.batch_tokens=178;c.routers.position=177;c.layers.output_positions=c.routers.output_positions={177};
 ggml_init_params ip{8*1024*1024,nullptr,false};auto*ctx=ggml_init(ip);auto*t=ggml_new_tensor_3d(ctx,GGML_TYPE_F32,2560,4,178);ggml_set_name(t,"l_last-0");for(int i=0;i<3;++i)assert(capture_both(t,true,&c)&&c.layers.seen.empty()&&c.routers.seen.empty());assert(capture_both(t,false,&c)&&!c.layers.failed);assert(capture_both(t,false,&c)&&c.layers.failed);
 c.layers=LayerCapture{};c.layers.out=argv[1];c.layers.batch_tokens=178;c.layers.output_positions={177};auto*u=ggml_new_tensor_3d(ctx,GGML_TYPE_F32,2560,4,1);ggml_set_name(u,"l_last-47");assert(capture_both(u,false,&c)&&!c.layers.failed);c.layers.seen.clear();c.layers.output_positions={176};assert(capture_both(u,false,&c)&&c.layers.failed);
 c.routers.seen.clear();auto*ids=ggml_new_tensor_2d(ctx,GGML_TYPE_I32,512,178);auto*view=ggml_view_2d(ctx,ids,10,178,2048,0);ggml_set_name(view,"ffn_moe_topk-4");assert(capture_both(view,true,&c)&&c.routers.seen.empty());assert(capture_both(view,false,&c)&&!c.routers.failed);assert(capture_both(view,false,&c)&&c.routers.failed);
 ggml_set_name(u,"unselected");assert(!capture_both(u,true,&c));assert(capture_both(u,false,&c));ggml_free(ctx);std::puts("PASS178 combined callback pureASK/duplicate/cropping/errors-returntrue");}
