// packet184 device-free two-card checkpoint tool: commit (save phase 2), inspect, inspect-metadata,
// delete. Host-only build (g++ -std=gnu++20, linked with libcrypto only): no SYCL, no Level Zero, no
// engine object, so it cannot open or touch a device. The coordinator (tp2_checkpoint.py) runs it on
// CPU and during device windows alike; the engine binary carries the same tools behind its
// --checkpoint-* entry for packet181 CLI parity.
#include <stdexcept>
#include "checkpoint_format.hpp"
int main(int argc,char** argv) {
  try{const int rc=pipeline::ckpt184::host_tool(argc,argv);if(rc>=0)return rc;}
  catch(const std::exception& x){std::cerr<<x.what()<<'\n';return 2;}
  std::cerr<<"usage: own-rt-ckpt-tool --checkpoint-inspect DIR | --checkpoint-inspect-metadata DIR | --checkpoint-delete DIR |\n"
             "       --checkpoint-commit DIR --tokenizer-identity FILE --prompt-length P [--parent-id ID --parent-manifest-sha256 SHA]\n";
  return 2;
}
