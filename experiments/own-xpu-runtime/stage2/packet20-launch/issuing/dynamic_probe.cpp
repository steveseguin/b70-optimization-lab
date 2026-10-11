#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/experimental/graph.hpp>
namespace gx=sycl::ext::oneapi::experimental;
// Compile-and-link API probe only; never called; no device execution.
void dynamic_api_probe(sycl::context c,sycl::device d,sycl::kernel k){
 gx::command_graph graph{c,d};gx::dynamic_parameter<unsigned> value(0u);
 auto node=graph.add([&](sycl::handler& h){h.set_arg(0,value);h.single_task(k);});
 auto executable=graph.finalize(sycl::property_list{gx::property::graph::updatable{}});
 value.update(1u);executable.update(node);
}
