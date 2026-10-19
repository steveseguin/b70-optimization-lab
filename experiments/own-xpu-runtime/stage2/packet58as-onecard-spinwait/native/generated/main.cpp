#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/spin_wait.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/resident_lookup.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/drm_size.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/async_backend.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/cache_protocol.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/publish.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/ordered_retirement.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/p60_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/main.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p30_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p33_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p33r2.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet2/loader/gguf.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/synthetic.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/performance.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/small_gemv.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/dispatch.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p39_plan.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49b_expert_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p100_down.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49c_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49d_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/cache_table.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p25_bridge.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p28/submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/expert_down.hpp"
#include <unordered_map>
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/p109_fusion.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/p58ag_submit.hpp"
#include <optional>
#include <thread>
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
#ifdef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/lifetime_mock.hpp"
#endif
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <openssl/evp.h>
#include <set>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sched.h>
using namespace integrated;
namespace fs = std::filesystem;
using ownrt::Allocation;
using ownrt::Category;
using ownrt::Lifetime;
using ownrt::Memory;
static volatile std::sig_atomic_t stopped = 0;
static void stop(int) { stopped = 1; }
static void require(bool b, const std::string &s) {
  if (!b)
    throw std::runtime_error(s);
}
static std::string hash(const std::vector<uint8_t> &b) {
  unsigned char digest[32];
  unsigned n;
  EVP_Digest(b.data(), b.size(), digest, &n, EVP_sha256(), nullptr);
  std::string s;
  for (auto v : digest) {
    s += "0123456789abcdef"[v >> 4];
    s += "0123456789abcdef"[v & 15];
  }
  return s;
}
static void save(const fs::path &p, const std::string &s) {
  std::ofstream f(p);
  f << s;
  require(bool(f), "write " + p.string());
}
static size_t count(const std::vector<int> &s) {
  size_t n = 1;
  for (int x : s) {
    require(x > 0, "shape");
    n *= x;
  }
  return n;
}
static std::string device_ms(double v) {
#ifdef OWN_RT_HOST_ONLY
  (void)v;return "null";
#else
  std::ostringstream s;s.precision(12);s<<v;return s.str();
#endif
}
static bool ends(const std::string &s, const std::string &suffix) {
  return s.ends_with(suffix);
}
#ifdef OWN_RT_HOST_ONLY
class Host final : public packet18::LifetimeMock {
public:
  ownrt::Event copy(void *a, const void *b, size_t n,
                    std::span<const ownrt::Event> d) override {
    auto e = LifetimeMock::copy(a, b, n, d);
    finish(e);
    return e;
  }
  std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const> p) override {
    auto host=std::dynamic_pointer_cast<const HostOperation>(op);if(!host)throw std::logic_error("host operation type");
    return [this,host,pointers=std::vector<void*>(p.begin(),p.end())]{host->run(pointers);return marker({});};
  }
  ownrt::Event compute(const ownrt::Operation &o, std::span<void *const> p,
                       std::span<const ownrt::Event> d) override {
    dynamic_cast<const HostOperation &>(o).run(p);
    return marker(d);
  }
};
#endif
static int pipeline_stop_fd=-1;
static void pipeline_cancel_check();
struct RetainSteps {
  std::vector<std::pair<int,int>> ranges{{1,8}};
  bool contains(int step) const { for(auto [first,last]:ranges)if(step>=first&&step<=last)return true;return false; }
  void parse(const std::string& value) {
    ranges.clear();if(value=="none")return;
    require(!value.empty()&&value.back()!=',',"invalid retain-steps");
    std::istringstream input(value);std::string item;
    while(std::getline(input,item,',')) {
      auto dash=item.find('-');auto number=[](const std::string& text){require(!text.empty()&&std::all_of(text.begin(),text.end(),[](unsigned char c){return c>='0'&&c<='9';}),"invalid retain-steps integer");size_t n=0;int v=std::stoi(text,&n);require(n==text.size()&&v>0&&v<=1024,"retain-steps range");return v;};
      int first=number(item.substr(0,dash)),last=dash==std::string::npos?first:number(item.substr(dash+1));
      require(first<=last,"reversed retain-steps range");ranges.push_back({first,last});
    }
    require(!ranges.empty(),"empty retain-steps");
  }
};
struct Options {
  std::string hc="p60fusion",hc_geometry="production",experts="production",other_fusion="production",retirement="production";
  uint64_t cache_bytes=21552729600ull;std::string cache_cap="max";std::string miss_path="zero-copy",cache_maintenance="serial";
  RetainSteps retain_steps;
  int cancel_launch=-1;
  int draft_rank=0,target_split=0; bool mtp=false; fs::path draft_capture;
  fs::path draft_manifest=fs::path(__FILE__).parent_path()/"mtp-manifest.tsv";
  fs::path draft_model="/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8";
  std::string draft_fault="none",draft_head="full";
  int rank=-1, channel=-1, stop_fd=-1;
  fs::path shared;
  bool pipeline_mini=false,pipeline_canary=false;
  bool priority_probe = false;
  int native_nice=19;
  bool canary = false, mini = false, first = false, record = false, authorized = false, checked = false;
  std::string nongemv = "parallel", gemv = "r5", stage = "first-token", timing="token";
  fs::path dispatch;
  fs::path selection;
  std::string selection_sha256;
  bool legacy=false,argument_audit=false,audit_prepare_each=false;
  std::string wait_policy="poll"; bool wait_policy_supplied=false;
  int wait_seconds=60;
  int cards = 1, card = 3, tokens = 8, context = 128, seconds = 10800;
  std::string memory = "layer-streaming";
  bool resident_lookups=false;
  fs::path inputs, output, model, plan, auth, oracle, suite_inputs, bracket_inputs;
};
static Options parse(int argc, char **argv) {
  Options a;
  bool seconds_supplied = false;
  for (int i = 1; i < argc; ++i) {
    std::string k = argv[i];
    auto value = [&] {
      require(i + 1 < argc, "missing " + k);
      return std::string(argv[++i]);
    };
    if(k=="--cache-cap")a.cache_cap=value();
    else if(k=="--cache-maintenance")a.cache_maintenance=value();
    else if(k=="--cache-bytes")a.cache_bytes=std::stoull(value());
    else if(k=="--miss-path")a.miss_path=value();
    else if (k == "--retain-steps") a.retain_steps.parse(value());
    else if (k == "--cancel-launch") a.cancel_launch=std::stoi(value());
    else if (k == "--draft-rank") a.draft_rank=std::stoi(value());
    else if (k == "--target-split") a.target_split=std::stoi(value());
    else if (k == "--draft-mtp") a.mtp=true;
    else if (k == "--draft-head") a.draft_head=value();
    else if (k == "--draft-fault") a.draft_fault=value();
    else if (k == "--draft-capture") a.draft_capture=value();
    else if (k == "--draft-manifest") a.draft_manifest=value();
    else if (k == "--draft-model") a.draft_model=value();
    else if (k == "--rank") a.rank=std::stoi(value());
    else if (k == "--channel") a.channel=std::stoi(value());
    else if (k == "--stop-fd") a.stop_fd=std::stoi(value());
    else if (k == "--shared") a.shared=value();
    else if (k == "--pipeline-canary") a.pipeline_canary=true;
    else if (k == "--pipeline-mini") a.pipeline_mini=true;
    else if(k=="--argument-audit")a.argument_audit=true;
    else if(k=="--audit-prepare-each") {a.argument_audit=true;a.audit_prepare_each=true;}
    else if(k=="--host-path") {auto v=value();require(v=="legacy"||v=="prepared","host path");a.legacy=v=="legacy";}
    else if (k == "--native-nice") a.native_nice=std::stoi(value());
    else if (k == "--priority-probe") a.priority_probe=true;
    else if (k == "--canary") a.canary = true;
    else if (k == "--timing") a.timing=value();
    else if (k == "--dispatch") a.dispatch=value();
    else if (k == "--selection") a.selection=value();
    else if (k == "--selection-sha256") a.selection_sha256=value();
    else if (k == "--wait-policy") {a.wait_policy=value();a.wait_policy_supplied=true;require(a.wait_policy=="poll"||a.wait_policy=="spin","wait policy dimension");}
    else if (k == "--wait-seconds") a.wait_seconds=std::stoi(value());
    else if (k == "--checked") a.checked = true;
    else if (k == "--nongemv") a.nongemv = value();
    else if (k == "--gemv") a.gemv = value();
    else if (k == "--stage") a.stage = value();
    else if (k == "--mini")
      a.mini = true;
    else if (k == "--first-layer")
      a.first = true;
    else if (k == "--record")
      a.record = true;
    else if (k == "--authorized-device-window")
      a.authorized = true;
    else if (k == "--memory")
      a.memory = value();
    else if (k == "--cards")
      a.cards = std::stoi(value());
    else if (k == "--card")
      a.card = std::stoi(value());
    else if (k == "--tokens" || k == "--max-new")
      a.tokens = std::stoi(value());
    else if (k == "--context")
      a.context = std::stoi(value());
    else if (k == "--seconds")
      { a.seconds = std::stoi(value()); seconds_supplied = true; }
    else if (k == "--retirement") {a.retirement=value();require(a.retirement=="production"||a.retirement=="ordered-foreground","retirement dimension");}
    else if (k == "--hc-geometry") {a.hc_geometry=value();require(a.hc_geometry=="production"||a.hc_geometry=="hc-wide","HC geometry");}
    else if (k == "--experts") {a.experts=value();require(a.experts=="production"||a.experts=="wide64"||a.experts=="wide64+halfcache","expert dimension");}
    else if (k == "--other-fusion") {a.other_fusion=value();require(a.other_fusion=="production"||a.other_fusion=="fused","fusion dimension");}
    else if (k == "--hc") {a.hc=value();require(a.hc=="production"||a.hc=="p60fusion","HC dimension");}
    else if (k == "--lookups") {auto v=value();require(v=="mapped"||v=="resident","lookup dimension");a.resident_lookups=v=="resident";}
    else if (k == "--bracket-inputs") a.bracket_inputs=value();
    else if (k == "--suite-inputs") a.suite_inputs=value();
    else if (k == "--input" || k == "--prompt-tokens")
      a.inputs = value();
    else if (k == "--output")
      a.output = value();
    else if (k == "--model-dir")
      a.model = value();
    else if (k == "--plan")
      a.plan = value();
    else if (k == "--identity")
      a.auth = value();
    else if (k == "--oracle")
      a.oracle = value();
    else
      throw std::runtime_error("unknown option " + k);
  }
  if (a.canary && !seconds_supplied) a.seconds = 600;
  require(a.cancel_launch>=-1,"cancel launch bound");
#ifndef OWN_RT_HOST_ONLY
  require(a.cancel_launch==-1,"forced cancellation is CPU diagnostic only");
#endif
  require(a.draft_rank==0||a.draft_rank==1,"draft rank must be0 or1");
  require(a.target_split==0||a.target_split==23||a.target_split==24,"target split must be0 (placement default),23 or24");
  require(a.target_split!=23||a.mini||a.context==4096||(a.draft_rank==0&&a.context==32768),"23/25 rank1 draft admitted at context4096 only; rank0 at4096/32768");
  require(a.target_split!=24||a.draft_rank!=0||a.mini||a.context==4096,"24/24 rank0 draft admitted at context4096 only");
  require(a.draft_head=="full","draft shortlist head not qualified; use full");
  require(a.cards >= 1 && a.cards <= 2 && a.card >= 0 && a.card + a.cards <= 4,
          "card range");
  require(a.tokens > 0 && a.tokens <= 128 && a.context >= 8 &&
              a.context <= 32768 && a.seconds > 0 && a.seconds <= 172800,
          "bounded generation/context/deadline");
  require(a.timing=="token" || a.timing=="launch" || a.timing=="class","timing mode");
  require(a.wait_seconds>0 && a.wait_seconds<=600,"bounded wait deadline");
  require(a.nongemv=="core" || a.nongemv=="parallel", "nongemv mode");
  require(a.gemv=="frozen" || a.gemv=="r5", "gemv mode");
  require(a.stage=="first-token" || a.stage=="decode", "stage");
  require(!a.output.empty(), "--output required");
  require(a.cards==1 && a.rank==-1 && !a.mtp && (a.memory=="layer-streaming" || a.memory=="resident"), "packet58 target-only single-device process required");
  require(a.cache_cap=="18GB"||a.cache_cap=="max","cache capacity mode");
  require(a.mini||a.cache_bytes==21552729600ull,"single admitted maximum allocation required");
  require(a.cache_maintenance=="serial"||a.cache_maintenance=="overlap","cache maintenance mode");
  require(a.cache_maintenance!="overlap"||a.miss_path=="zero-copy","overlap requires zero-copy misses");
  require((a.mini||a.cache_bytes>=24000000ull)&&a.cache_bytes<=21552729600ull && (a.mini||a.memory=="resident"),"packet58 cache bounds/residency");
  require(a.miss_path=="zero-copy"||a.miss_path=="streamed","unknown miss path");
  require(a.rank>=-1 && a.rank<=1,"rank range");
#ifdef OWN_RT_HOST_ONLY
  require(!a.authorized, "host binary cannot authorize device execution");
  // CPU full-model execution is an explicit packet18 gate.
#else
  require(a.authorized || a.record, "--authorized-device-window required");
#endif
  require(a.native_nice>=0 && a.native_nice<=19 && getpriority(PRIO_PROCESS, 0) == a.native_nice, "native priority differs from declared --native-nice");
  require(getenv("OMP_NUM_THREADS") &&
              std::string(getenv("OMP_NUM_THREADS")) == "2",
          "OMP_NUM_THREADS=2 required");
  return a;
}
struct Weights {
  bool mini;
  std::unique_ptr<iq3::Model> model;
  flash::Directory directory;
  std::map<std::string, std::vector<uint8_t>> synthetic;
  uint64_t read_bytes = 0;
  size_t max_read = 0;
  std::string residency="{\"enabled\":false}";
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/resident_weights.hpp"
  Weights(const Options &a) : mini(a.mini) {
    if (mini)
      return;
    require((syscall(SYS_ioprio_get, 1, 0) >> 13) == 3,
            "ionice -c3 required for model reads");
    require(!a.plan.empty() && !a.auth.empty() && !a.model.empty(),
            "model, plan, identity required");
    std::ifstream identity(a.auth);
    require(bool(identity), "identity open");
    std::vector<fs::path> paths;
    std::string name;
    uint64_t bytes, dev, ino, mtime, ctime;
    while (identity >> name >> bytes >> dev >> ino >> mtime >> ctime) {
      require(fs::path(name).filename() == name, "identity basename");
      auto p = a.model / name;
      struct stat st{};
      require(!stat(p.c_str(), &st), "model stat");
      require(
          uint64_t(st.st_size) == bytes && uint64_t(st.st_dev) == dev &&
              uint64_t(st.st_ino) == ino &&
              uint64_t(st.st_mtim.tv_sec) * 1000000000 + st.st_mtim.tv_nsec ==
                  mtime &&
              uint64_t(st.st_ctim.tv_sec) * 1000000000 + st.st_ctim.tv_nsec ==
                  ctime,
          "admitted shard changed");
      paths.push_back(p);
    }
    require(identity.eof() && paths.size() == 3,
            "three admitted shards required");
    model = std::make_unique<iq3::Model>(paths, iq3::read_plan(a.plan));
    directory = flash::directory_from_loader(model->plan);
  }
  void synthesize(const flash::Plan &p) {
    using flash::mock::weight;
    auto add = [&](const std::string &name, std::vector<int> shape,
                   bool control = false) {
      if (directory.count(name))
        return;
      size_t n = count(shape);
      std::vector<float> v(n);
      int cols = shape.back(),
          rows = shape.size() > 1 ? shape[shape.size() - 2] : 1;
      for (size_t i = 0; i < n; ++i) {
        int e = int(i / (cols * rows)), r = int(i / cols) % rows,
            k = int(i % cols);
        float x = weight(name, control ? 0 : r, control ? int(i) : k, e);
        if (name.find("norm") != std::string::npos &&
            name.find("ssm_norm") == std::string::npos)
          x += 1;
        if (ends(name, "ssm_a"))
          x = -detmath::exp(x);
        if (name.find("conv1d") != std::string::npos)
          x = weight(name, int(i / 4), int(i % 4));
        v[i] = x;
      }
      std::vector<uint8_t> raw(n * 4);
      std::memcpy(raw.data(), v.data(), raw.size());
      synthetic[name] = std::move(raw);
      directory[name] = {name, "F32", "synthetic", shape, n * 4};
    };
    for (auto &l : p.launches)
      for (size_t w = 0; w < l.weights.size(); ++w) {
        auto name = l.weights[w];
        auto &g = p.g;
        if (l.op == "gemv")
          add(name, {l.shape[1], l.shape[2]});
        else if (l.op == "routed_gemv")
          add(name, {g.experts, l.shape[1], l.shape[2]});
        else if (l.op == "lookup")
          add(name, {name == "token_embd.weight" ? g.vocab : 272, l.shape[1]});
        else if (l.op == "norm")
          add(name, {l.shape[0] * l.shape[1]}, true);
        else if (l.op == "conv")
          add(name, {l.shape[0], 4});
        else if (l.op == "gdn")
          add(name, {g.vh}, true);
        else if (l.op == "gdn_norm_gate")
          add(name, {g.d}, true);
        else if (l.op == "qsa_prepare")
          add(name, {w == 2 ? g.id : g.ad}, true);
        else if (l.op == "qsa_append_pool")
          add(name, {g.id}, true);
        else
          throw std::runtime_error("synthetic weight " + name);
      }
  }
  std::vector<uint8_t> read(const std::string &name, size_t off, size_t n) {
    require(n && n <= 4 * 1024 * 1024, "bounded read (4 MiB)");
    read_bytes += n;
    max_read = std::max(max_read, n);
    if(use_resident_lookups) {
      if(auto it=resident_lookups.find(name);it!=resident_lookups.end()) {
        const auto* data=it->second->slice(off,n);return {data,data+n};
      }
      require(name!="token_embd.weight"&&name!="per_layer_token_embd.weight","resident lookup missing; no file fallback");
    }
    if (mini) {
      auto &b = synthetic.at(name);
      require(off <= b.size() && n <= b.size() - off, "synthetic bounds");
      return {b.begin() + off, b.begin() + off + n};
    }
    auto slice = model->slice(name, off, n);
    return {slice.data(), slice.data() + n};
  }
  std::vector<int64_t> metadata() {
    if (mini) {
      std::vector<int64_t> v{3, 5, 7};
      v.insert(v.end(), 16, 17);
      for (int i = 0; i < 16; ++i)
        v.push_back(17 * i);
      return v;
    }
    std::vector<int64_t> v;
    auto &m = model->shards[0].metadata;
    for (auto key :
         {"qwen4exp.ple.layer_multipliers", "qwen4exp.ple.head_vocab_sizes",
          "qwen4exp.ple.head_offsets"})
      for (auto &x : std::get<std::vector<iq3::Meta>>(m.at(key).value))
        v.push_back(std::bit_cast<int64_t>(x.integer()));
    require(v.size() == 35, "PLE metadata");
    return v;
  }
};
static flash::Plan plan(Weights &w, const Options &a) {
  auto g =
      a.mini ? Geometry::tiny() : flash::geometry_from_directory(w.directory);
  g.context = a.mini && !a.pipeline_mini ? 8 : a.context;
  auto p = a.first  ? flash::Builder(g, a.mini ? nullptr : &w.directory)
                          .build({false}, true)
           : a.mini ? flash::Builder(g).build(a.pipeline_mini?std::vector<bool>{false,true,false,true}:std::vector<bool>{false,true})
                    : flash::model_plan(w.directory);
  p.g.context = g.context;
  // Rebuild at bounded request capacity, maintaining packet3's layer schedule.
  if (!a.mini && !a.first) {
    std::vector<bool> full;
    for (int i = 0; i < 48; ++i)
      full.push_back(
          w.directory.count("blk." + std::to_string(i) + ".attn_q.weight"));
    p = flash::Builder(g, &w.directory).build(full);
  }
  if (a.cards == 1) {
    for (auto &b : p.buffers)
      b.card = 0;
    for (auto &l : p.launches) {
      l.card = 0;
      l.source_card = -1;
    }
    std::erase_if(p.launches, [](auto &l) {
      return l.op == "handoff" || l.op == "handoff_result" ||
             l.label == "begin.1" || l.label == "commit.0";
    });
  }
  if (a.mini && a.cards == 2 && !a.first) {
    for (auto &b : p.buffers) {
      if (b.name.starts_with("blk.1.") || b.name.starts_with("final.") ||
          b.name == "logits" || b.name == "token_history" ||
          b.name == "ple_metadata")
        b.card = 1;
      if (b.name == "streams" || b.name == "token" || b.name == "position" ||
          b.name == "active" || b.name == "error" || b.name == "next_token")
        b.card = -1;
    }
    std::vector<flash::Launch> sites;
    bool second = false;
    for (auto l : p.launches) {
      if (l.label == "blk.1.ple.hash") {
        second = true;
        flash::Launch handoff;
        handoff.op = "handoff";
        handoff.label = "handoff";
        handoff.card = 1;
        handoff.source_card = 0;
        handoff.inputs = handoff.outputs = {"streams", "token", "position",
                                            "active", "error"};
        sites.push_back(handoff);
      }
      if (second)
        l.card = 1;
      if (l.op == "commit") {
        flash::Launch back;
        back.op = "handoff_result";
        back.label = "handoff.result";
        back.card = 0;
        back.source_card = 1;
        back.inputs = back.outputs = {"next_token", "error"};
        sites.push_back(back);
        auto first = l;
        first.card = 0;
        first.label = "commit.0";
        sites.push_back(first);
      }
      sites.push_back(l);
      if (l.op == "begin") {
        auto begin = l;
        begin.card = 1;
        begin.label = "begin.1";
        sites.push_back(begin);
      }
    }
    p.launches = std::move(sites);
  }
  if (a.mini)
    w.synthesize(p);
  std::vector<flash::Launch> fused;
  for (size_t i=0;i<p.launches.size();++i) {
    auto l=p.launches[i];
    if(l.op=="routed_gemv" && l.weights[0].find("ffn_gate_exps")!=std::string::npos) {
      require(i+2<p.launches.size(),"gate/up schedule");
      const auto& up=p.launches[i+2];
      require(up.op=="routed_gemv" && up.inputs==l.inputs && up.shape==l.shape &&
              up.weights[0].find("ffn_up_exps")!=std::string::npos,"gate/up dependency");
      l.op="expert_gate_up";
      l.weights.push_back(up.weights[0]);
      l.outputs.insert(l.outputs.end(),up.outputs.begin(),up.outputs.end());
      fused.push_back(l);fused.push_back(p.launches[i+1]);i+=2;
    } else fused.push_back(l);
  }
  p.launches=std::move(fused);
  // Optional arithmetic-preserving specialised fusions. The default schedule is
  // byte-for-byte packet18. The route consumer uses the single source row.
  std::vector<flash::Launch> specialised;
  std::map<std::string,std::string> routed_source;
  for(size_t i=0;i<p.launches.size();++i) {
    auto l=p.launches[i];
    if(a.nongemv=="parallel" && l.op=="route" && i+1<p.launches.size() && p.launches[i+1].op=="expert_gather" &&
       packet26::dispatch.fusion_for("route+gather")) {
      const auto& gather=p.launches[++i];
      l.outputs.push_back(gather.outputs[0]);l.outputs.push_back(gather.outputs[1]);
      routed_source[gather.outputs[2]]=gather.inputs[1];
    }
    if(l.op=="expert_gate_up" && routed_source.count(l.inputs[0]))l.inputs[0]=routed_source.at(l.inputs[0]);
    if(a.nongemv=="parallel" && l.op=="hc_combine" && i+1<p.launches.size()) {
      const auto& next=p.launches[i+1];
      auto fusion_class=l.label;if(fusion_class.starts_with("blk."))fusion_class=fusion_class.substr(fusion_class.find('.',4)+1);
      if(packet26::dispatch.fusion_choice(fusion_class=="attn.combine"?"attention-combine":"shared-down-combine")!="p39.epilogue" && packet26::dispatch.fusion_for(fusion_class+"+norm") && next.op=="norm" && next.card==l.card && next.inputs==l.outputs && !(a.hc=="p60fusion" && !a.mini && a.memory=="resident" && p60::stage(next.label)==0)) {
        l.outputs.insert(l.outputs.end(),next.outputs.begin(),next.outputs.end());
        l.weights=next.weights;l.parameter=next.parameter;++i;
      }
    }
    specialised.push_back(std::move(l));
  }
  p.launches=std::move(specialised);
  if(!a.mini)p39::fuse_plan(p,[&](const std::string&name){return flash::grid_type(w.directory.at(name).grid);});
  return p;
}
static unsigned selected_variant(const Weights& w,const Options& a,const flash::Plan& p,const flash::Launch& l,size_t projection=0) {
    const auto& t=w.directory.at(l.weights[projection]);
    auto choice=packet26::dispatch.gemv_for(l.label);
    if(choice.empty())choice=a.gemv;
    if(choice.starts_with("p25.")||choice.starts_with("p27.")||choice.starts_with("p28.")||choice.starts_with("p29.")||choice.starts_with("p33.")||choice.starts_with("p42.")||choice.starts_with("p30."))choice="r5"; // packed/expanded storage identity is unchanged
    if(choice=="r5")return arithmetic::r5_variant(flash::grid_type(t.grid),l.shape[1],l.shape[2],l.op=="gemv"?1:p.g.experts,a.mini);
    if(choice=="frozen" || choice=="packet18")return arithmetic::variant(flash::grid_type(t.grid),l.shape[1],l.shape[2],l.op=="gemv"?1:p.g.experts,a.mini);
    for(unsigned v=0;v<8;++v)if(choice==arithmetic::name(v)) {
      require(l.op=="gemv" || v==2,"expert dispatch requires registered expert kernel");
      require(!arithmetic::is_expanded(v) || iq3::expanded::quantized(flash::grid_type(t.grid)),"expanded kernel requires quantized weights");
      return v;
    }
    throw std::invalid_argument("GEMV candidate is not linked: "+choice);
}
// The measured P48b expert layouts are used for both rows of verification.
// The engine submits those rows separately; no new batching arithmetic is added.
static bool p49b_site(const Weights& w,const Options& a,const flash::Launch& l){
 if(a.mini||a.memory!="resident"||!p39::tagged(l)||l.weights.empty())return false;
 const auto type=flash::grid_type(w.directory.at(l.weights[0]).grid);
 return (p39::kind(l)==p39::Kind::expert_checks&&type==iq3::Type::IQ2_S&&l.shape[2]==2560)||
        (p39::kind(l)==p39::Kind::down_status&&type==iq3::Type::IQ4_NL&&l.shape[2]==640);
}
static bool p49b_weight(const Weights& w,const Options& a,const flash::Plan& p,const std::string& name){
 for(const auto& l:p.launches)if(p49b_site(w,a,l)&&std::find(l.weights.begin(),l.weights.end(),name)!=l.weights.end())return true;
 return false;
}
static size_t p49b_weight_bytes(const flash::Tensor& t){
 const auto type=flash::grid_type(t.grid);const unsigned k=t.shape.back();
 return t.bytes/p49bgemv::source_row_bytes(type,k)*p49bgemv::layout(type,k).row_bytes;
}
struct Slot {
  Allocation id;
  size_t n;
  Scalar type;
};
static size_t target_scratch_bytes(const flash::Plan&,const Options&);
class Engine final : public flash::Backend {
public:
  struct ExpertBank {Allocation host=0,table=0;size_t expert_bytes=0;int layer=-1,projection=-1;};
  std::map<std::string,ExpertBank> expert_banks;
  Allocation halfcache=0;
  std::unique_ptr<p58::Cache> expert_cache;
  Allocation cache_arena=0,route_log=0,table_staging=0;uint64_t cache_epoch=0,cache_fill_bytes=0,cache_fills=0;
  std::vector<std::pair<int,Allocation>> route_sources;
  std::vector<uint8_t> host_routes;
  std::ofstream cache_log;
  Allocation publication_device=0;
  p58v::Protocol maintenance;
  std::vector<uint32_t> previous_routes;
  uint64_t maintenance_position=0;
  double maintenance_plan_ms=0;
  uint64_t publication_uploads=0,publication_bytes=0;
  double publication_host_ms=0;
  bool overlapping()const{return a.cache_maintenance=="overlap";}
  void cache_quiesce() {
    if(!expert_cache||!overlapping())return;
    require(!maintenance.running,"cache switch during position");
    cache_boundary();
    if(maintenance.state==p58v::Protocol::State::filling) {
      auto* b=p58v::backend(dev(0));require(b,"missing maintenance backend");b->finish_fills();cache_boundary();
    }
    require(maintenance.state==p58v::Protocol::State::idle,"pending cache switch");previous_routes.clear();
  }
  void cache_mode(const std::string& mode) {
    require(mode=="serial"||mode=="overlap","unsupported cache mode");
    drain();cache_quiesce();a.cache_maintenance=mode;
    require(mode!="overlap"||a.miss_path=="zero-copy","overlap requires zero-copy");
  }
  void cache_capacity(const std::string& cap) {
    require(cap=="18GB"||cap=="max","cache capacity dimension");
    drain();cache_quiesce();
    require(!maintenance.running&&maintenance.state==p58v::Protocol::State::idle,"capacity boundary has unfinished work");
    a.cache_cap=cap;
    if(!expert_cache){require(a.mini,"full model requires cache");return;}
    const auto& arena=dev(0).arena.row(cache_arena);
    require(arena.live&&arena.bytes==21552729600ull,"maximum arena must remain allocated");
    expert_cache->reset_capacity(cap=="18GB"?18000000000ull:21552729600ull);
    previous_routes.clear();publish_cache_table(expert_cache->table());drain();
    require(expert_cache->resident_bytes()==0,"view must start empty");
  }
  void cache_boundary() {
    require(!maintenance.running,"cache publication during position");
    if(maintenance.state==p58v::Protocol::State::filling) {
      // Query once; a late fill is left unpublished, with safe host pointers.
      auto* b=p58v::backend(dev(0));require(b,"missing maintenance backend");
      if(!maintenance.ticket||b->fill_complete(maintenance.ticket)) {
        publish_cache_table(maintenance.plan->table);maintenance.commit(*expert_cache,true,true);
      }
    }
    if(maintenance.state==p58v::Protocol::State::planned) {
      auto safe=maintenance.revoked(*expert_cache);
      publish_cache_table(safe); // prior compute and host-pointer publication are complete
      ownrt::Event last=0;
      for(const auto& f:maintenance.plan->fills) {
        size_t offset=f.offset;
        for(int projection=0;projection<3;++projection)for(const auto& [name,b]:expert_banks)
          if(b.layer==int(f.expert/p.g.experts)&&b.projection==projection) {
            last=p58v::copy(dev(0),cache_arena,offset,b.host,size_t(f.expert%p.g.experts)*b.expert_bytes,b.expert_bytes);
            offset+=b.expert_bytes;
          }
        require(offset==f.offset+f.bytes,"async projection byte coverage");
      }
      cache_fill_bytes+=maintenance.plan->fill_bytes;cache_fills+=maintenance.plan->fills.size();
      maintenance.submitted(true,last);
    }
  }
  void cache_plan_during_position() {
    if(!expert_cache||!overlapping()||previous_routes.empty()||maintenance.state!=p58v::Protocol::State::idle)return;
    auto start=std::chrono::steady_clock::now();maintenance.prepare(*expert_cache,previous_routes);
    maintenance_plan_ms=ms(start);previous_routes.clear();
  }

  bool caching()const{return !a.mini && a.memory=="resident";}
  Weights &w;
  Options a;
  const bool class_timing,profile_events,resident,prepared_path;
  flash::Plan p; // Replaced only at the drained HC view boundary.
  const packet26::Dispatch sealed_dispatch=packet26::dispatch;
  std::vector<std::unique_ptr<ownrt::Device>> devices;

  std::vector<size_t> owned_bytes;
  std::map<Allocation,std::pair<int,size_t>> allocations;
  std::vector<Allocation> ropes, controls, scores, probabilities, snapshots;
  struct Pending { Launch launch; bool gemv; int cls; };
  std::map<std::string,int> class_ids;
  std::vector<std::string> class_names;
  std::vector<double> class_ms;
  std::vector<uint64_t> class_launches,class_groups;
  int current_cls=0;
  double wait_ms=0,prepare_ms=0,enqueue_ms=0,enqueue_including_wait_ms=0;
  void set_class(const std::string& label) {
    std::string name=label;
    if(name.starts_with("blk.")){auto dot=name.find('.',4);if(dot!=std::string::npos)name=name.substr(dot+1);}
    auto [it,added]=class_ids.try_emplace(name,int(class_names.size()));
    if(added){class_names.push_back(name);class_ms.push_back(0);class_launches.push_back(0);class_groups.push_back(0);}
    current_cls=it->second;
  }
  void dump_classes(const fs::path& path,int tokens) {
    if(!class_timing)return;
    std::ofstream o(path);o<<"{\"profiling\":true,\"timing_definition\":\"sum of individual GPU event execution durations\",\"tokens\":"<<tokens<<",\"classes\":[";
    for(size_t i=0;i<class_names.size();++i)o<<(i?",":"")<<"{\"class\":"<<ownrt::quote(class_names[i])<<",\"device_ms\":"<<class_ms[i]<<",\"launches\":"<<class_launches[i]<<",\"groups\":"<<class_groups[i]<<"}";
    o<<"]}\n";
  }
  // Selection is resolved once while preparing each site, before capture.
  // Token replay contains no selection lookup or candidate-name branch.
  p49d::Selection sealed_selection;
  struct Prepared { Spec spec; std::vector<Allocation> bindings; p49d::Submit submit=packet18::submit_parallel; };
  std::unordered_map<const flash::Launch*,Prepared> prepared;
  std::unordered_map<const flash::Launch*,std::vector<Matrix>> matrices;
  std::unordered_map<const flash::Launch*,std::pair<std::string,std::array<unsigned,2>>> gemv_choices;
  struct SmallGroup {std::string name;std::vector<const flash::Launch*> members;};
  std::unordered_map<const flash::Launch*,SmallGroup> small_groups;
  std::unordered_map<const flash::Launch*,const flash::Launch*> small_followers;


  struct IssueSite {
    std::vector<ownrt::PreparedCompute> commands;
    int card=0, layer=-1, cls=0, family=0;
    bool copy=false, layer_end=false, prefill_skip=false;
    Allocation fp32_source=0;size_t fp32_extent=0;
  };
  std::vector<IssueSite> issue_sites, alternate_issue_sites;
  unsigned bank_parity=0;uint64_t parity_argument_checks=0;
  bool preparing_commands=false,fresh_arguments=false;
  const std::array<const char*,10> families{"dense_r5","experts_r5","p25_p27_gemv","p28_p29_gemv","small_fusions","specialised_round2","parallel18","combine","check_commit","copy"};
  std::array<double,10> family_ms{};
  std::vector<Pending> pending;
  ownrt::Event tail=0;
  int submission_card=-1;
  uint64_t host_waits=0;
  int64_t history0=0,history1=0;
  std::vector<int64_t> metadata;

  std::vector<std::map<std::string, Slot>> buffers;
  std::vector<std::map<std::string, Allocation>> weights;
  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;
  std::vector<Allocation> fp32_inputs, fp32_sources;
  std::vector<size_t> fp32_extents;
  std::vector<std::vector<uint32_t>> selected;
  std::vector<int> loaded_layer;
  std::ofstream timings, prefill_timings, site_timings;
  double gemv_ms=0, nongemv_ms=0, transfer_ms=0;
  uint64_t submitted=0,max_submission_ns=0;
  size_t peak_device_bytes=0;
  static double ms(std::chrono::steady_clock::time_point t) {
    return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count();
  }
  void finish(int, Launch l, bool gemv) {
    // Submission only. Owner::compute appends the preceding owned event.
    if(preparing_commands)return;
    if(profile_events||draft_timing)pending.push_back({l,gemv,current_cls}); tail=l.last; submitted+=l.passes;
  }
  void finish(int c, ownrt::Event event) { finish(c,{event,event,1},false); }
  void drain() {
    if(!tail && pending.empty())return;
    if(tail)wait(0,tail);
#ifndef OWN_RT_HOST_ONLY
    for(auto item:pending) {
      require(item.launch.last-item.launch.first+1==item.launch.passes,"non-contiguous event group");
      double duration=0;
      for(auto id=item.launch.first;id<=item.launch.last;++id) {
        auto t=dev(0).timing(id);require(t.start_ns && t.end_ns>=t.start_ns,"invalid profiling interval");
        max_submission_ns=std::max(max_submission_ns,t.end_ns-t.start_ns);
        require(t.end_ns-t.start_ns<=4000000000ull,"GPU submission exceeded declared 4-second budget");
        duration+=double(t.end_ns-t.start_ns)/1e6;
      }
      (item.gemv?gemv_ms:nongemv_ms)+=duration;
      if(class_timing) {class_ms[item.cls]+=duration;class_launches[item.cls]+=item.launch.passes;++class_groups[item.cls];}
    }
#endif
    pending.clear();tail=0;
    if(!devices.empty())dev(0).retire_completed_events();
  }

  std::ofstream argument_log;
  std::ofstream progress;
  flash::Event logical = 0;
  bool poisoned = false;bool draft_timing=false;
  std::chrono::steady_clock::time_point deadline;
  Engine(Weights &source, const Options &args, flash::Plan q)
      : w(source), a(args), class_timing(args.timing=="class"),profile_events(args.timing!="token"),resident(args.memory=="resident"),prepared_path(resident&&!args.legacy),p(std::move(q)),
        timings(a.output / "timings.jsonl"), prefill_timings(a.output/"prefill-timings.jsonl"), site_timings(a.output/"sites.jsonl"), progress(a.output / "progress.jsonl"),
        deadline(std::chrono::steady_clock::now() +
                 std::chrono::seconds(a.seconds)) {pending.reserve(4096);prepared.reserve(p.launches.size());matrices.reserve(p.launches.size());gemv_choices.reserve(p.launches.size());
    if(!a.selection.empty()){require(!a.selection_sha256.empty(),"selection requires sealed --selection-sha256");sealed_selection.load(a.selection.string(),a.selection_sha256);}
    else require(a.selection_sha256.empty(),"selection SHA256 requires selection file");
    index_plan();
  }
  void index_plan() {
    gemv_choices.clear();small_groups.clear();small_followers.clear();
    for(const auto& l:p.launches)if(l.op=="gemv"||l.op=="expert_gate_up"||l.op=="routed_gemv"){
      std::array<unsigned,2> variants{selected_variant(w,a,p,l),0};if(l.op=="expert_gate_up")variants[1]=selected_variant(w,a,p,l,1);
      gemv_choices.emplace(&l,std::make_pair(packet26::dispatch.gemv_for(l.label),variants));
    }
    // Only move sibling projections whose shared input already exists here.
    // The immutable plan stays intact for the reference oracle and fixtures.
    auto enabled=[&](const std::string& key){auto i=packet26::dispatch.fusions.find(key);return i!=packet26::dispatch.fusions.end()&&(i->second=="round2"||i->second=="p30.small.rows4");};
    for(const auto& first:p.launches){if(first.op!="gemv")continue;
      auto cls=packet26::Dispatch::class_name(first.label);std::string key,name;std::vector<std::string> labels;
      if((cls=="hc.a.low"||cls=="hc.f.low")&&enabled("small.hc")){
        key="small.hc";labels={first.label,first.label.substr(0,first.label.size()-3)+"inject"};
      }else if(cls=="gdn.a"&&enabled("small.gdn.ab")){
        key="small.gdn.ab";labels={first.label,first.label.substr(0,first.label.size()-1)+"b"};
      }else if(cls=="router"&&enabled("small.ffn")){
        key="small.ffn";auto prefix=first.label.substr(0,first.label.size()-6);labels={first.label,prefix+"shexpgate",prefix+"shexpup",prefix+"shared_gate"};
      }else continue;
      SmallGroup group;bool available=true;
      for(const auto& label:labels){const flash::Launch* found=nullptr;for(const auto& member:p.launches)if(member.label==label){require(!found,"duplicate small GEMV site");found=&member;}
        // A partial plan or an earlier P39 epilogue rewrite has no complete
        // primitive GEMV tuple here. Keep its existing schedule and arithmetic.
        if(!found||p39::tagged(*found))available=false;
        group.members.push_back(found);
      }
      if(!available)continue;
      for(const auto* found:group.members)
        require(found->op=="gemv"&&found->card==first.card&&found->inputs==first.inputs,"small GEMV sibling schedule/input");
      // Reordering is legal only while inputs remain unchanged, outputs are not
      // overwritten, and no intervening site reads the not-yet-original output.
      // Builder appends active/error control labels to every GEMV's metadata.
      // Dense GEMV binds only inputs[0]; check_status writes error between the
      // router and shared branch. That is not a write to the GEMV input vector.
      const size_t first_index=size_t(&first-p.launches.data());
      for(size_t member_index=1;member_index<group.members.size();++member_index){
        const auto& member=*group.members[member_index];const size_t original=size_t(&member-p.launches.data());
        require(original>first_index,"small GEMV follower precedes first member");
        for(size_t between=first_index+1;between<original;++between){const auto& site=p.launches[between];
          require(site.card==first.card,"small GEMV crosses card ownership boundary");
          for(const auto& output:site.outputs){require(output!=first.inputs.at(0),"small GEMV input vector overwritten before follower");require(std::find(member.outputs.begin(),member.outputs.end(),output)==member.outputs.end(),"small GEMV early output overwritten");}
          for(const auto& input:site.inputs)require(std::find(member.outputs.begin(),member.outputs.end(),input)==member.outputs.end(),"small GEMV output read before original site");
        }
      }
      name=a.mini?(key=="small.hc"?"small.mini.hc":key=="small.gdn.ab"?"small.mini.gdn.ab":"small.mini.ffn"):key;
      if(!a.mini&&key=="small.ffn"){
        auto gate=flash::grid_type(w.directory.at(group.members[1]->weights[0]).grid),up=flash::grid_type(w.directory.at(group.members[2]->weights[0]).grid);
        require(gate==up&&(gate==iq3::Type::Q6_K||gate==iq3::Type::Q8_0),"unregistered small FFN format tuple");name+=gate==iq3::Type::Q6_K?".q6":".q8";
      }
      const auto expected=packet27::small::shapes(name);
      for(size_t i=0;i<expected.size();++i){const auto& member=*group.members[i];const auto& e=expected[i];
        require(flash::grid_type(w.directory.at(member.weights[0]).grid)==e.type&&member.shape[1]==int(e.rows)&&member.shape[2]==int(e.columns)&&variant(member)==e.variant,"small GEMV dispatch arithmetic tuple mismatch");
      }
      group.name=name;small_groups.emplace(&first,group);
      for(size_t i=1;i<group.members.size();++i)require(small_followers.emplace(group.members[i],&first).second,"overlapping small GEMV groups");
    }
  }
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/engine_bracket.hpp"
  void guard() {
    pipeline_cancel_check();
    require(!poisoned, "poisoned step");
    require(!stopped, "cooperative stop");
    require(std::chrono::steady_clock::now() < deadline,
            "cooperative deadline");
  }
  ownrt::Device &dev(int c) {
    if(c!=0)throw std::logic_error("rank-local device only");
    return *devices.at(0);
  }
  bool progress_pending=false;
  std::function<void()> progress_callback; // same-thread draft readback publication
  // Failure-only event details and six first-prefill checkpoints. No per-site I/O.
  const char* request_phase="load";
  const std::string* last_site=nullptr;
  size_t request_token_index=0;
  fs::path request_diagnostics;
  void checkpoint(const char* phase) {
    request_phase=phase;
    if(request_token_index==0&&!request_diagnostics.empty()) {
      std::ofstream f(request_diagnostics/"first-prefill-progress.jsonl",std::ios::app);
      f<<"{\"phase\":"<<ownrt::quote(phase)<<",\"submitted\":"<<submitted
       <<",\"host_waits\":"<<host_waits<<"}\n";f.flush();
    }
  }
  void check_wait(bool ok,int c,ownrt::Event event,const char* kind,Allocation allocation,size_t bytes,
                  std::chrono::steady_clock::time_point started) {
    if(ok)return;
    std::ostringstream row;
    row<<"{\"phase\":"<<ownrt::quote(request_phase)<<",\"token_index\":"<<request_token_index
      <<",\"kind\":"<<ownrt::quote(kind)<<",\"event\":"<<event<<",\"card\":"<<c
      <<",\"allocation\":"<<allocation<<",\"bytes\":"<<bytes
      <<",\"last_submitted_site\":"<<ownrt::quote(last_site?*last_site:"")
      <<",\"submitted\":"<<submitted<<",\"host_waits\":"<<host_waits
      <<",\"wait_seconds\":"<<a.wait_seconds<<",\"elapsed_ms\":"<<ms(started)<<"}\n";
    save((request_diagnostics.empty()?a.output:request_diagnostics)/"wait-timeout.json",row.str());
    throw std::runtime_error("operation drain timeout; retain owner");
  }
  void wait(int c, ownrt::Event e,const char* kind="compute-or-copy-tail",Allocation allocation=0,size_t bytes=0) {
    ++host_waits;auto t0=std::chrono::steady_clock::now();
    if(progress_callback) {
      auto end=std::chrono::steady_clock::now()+std::chrono::seconds(a.wait_seconds);
      while(!dev(c).complete(e)){if(progress_pending)progress_callback();guard();check_wait(std::chrono::steady_clock::now()<end,c,e,kind,allocation,bytes,t0);std::this_thread::yield();}
      if(progress_pending)progress_callback();
    }
    check_wait(dev(c).wait(e, std::chrono::seconds(a.wait_seconds)),c,e,kind,allocation,bytes,t0);
    wait_ms+=ms(t0);
  }
  Allocation allocate(int c, std::string name, size_t bytes, Category cat,
                      Lifetime life, Memory m = Memory::device) {
    if (m == Memory::device)
      require(owned_bytes.at(c) + bytes <= 29963128848ull,
              "29,963,128,848-byte admitted device allocation bound");
    auto id=dev(c).arena.allocate("card"+std::to_string(c)+":"+name, bytes, m, cat, life);
    if(m==Memory::device){owned_bytes[c]+=bytes; allocations[id]={c,bytes};}
    peak_device_bytes=std::max(peak_device_bytes,owned_bytes[c]);
    return id;
  }
  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {
    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");
    drain();
    auto started=std::chrono::steady_clock::now();
    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {
      guard();
      size_t k = std::min(n - i, size_t(4 * 1024 * 1024));
      std::memcpy(dev(c).arena.row(slab[c]).pointer,
                  static_cast<const uint8_t *>(src) + i, k);
      ownrt::CopyEngine copy(dev(c));
      wait(c, copy.copy(dst, offset + i, slab[c], 0, k, {}),"upload",dst,k);
      dev(c).retire_completed_events();
    }
    transfer_ms+=ms(started);
  }
  std::vector<uint8_t> readback(int c, Allocation src, size_t n) {
    drain();
    auto started=std::chrono::steady_clock::now();
    std::vector<uint8_t> b(n);
    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {
      size_t k = std::min(n - i, size_t(4 * 1024 * 1024));
      ownrt::CopyEngine copy(dev(c));
      wait(c, copy.copy(slab[c], 0, src, i, k, {}),"readback",src,k);
      dev(c).retire_completed_events();
      std::memcpy(b.data() + i, dev(c).arena.row(slab[c]).pointer, k);
    }
    transfer_ms+=ms(started);
    return b;
  }
  void put(int c, const std::string &name, const void *b, size_t n) {
    auto s = buffers[c].at(name);
    require(n == s.n * flash::scalar_bytes(s.type), "control extent");
    upload(c, s.id, 0, b, n);
  }
  int integer(int c, const std::string &name) {
    auto b = readback(c, buffers[c].at(name).id, 4);
    int v;
    std::memcpy(&v, b.data(), 4);
    return v;
  }
  unsigned variant(const flash::Launch& l,size_t projection=0)const {return gemv_choices.at(&l).second.at(projection);}
  unsigned weight_variant(const std::string& name)const {
    for(const auto& l:p.launches)if(l.op=="gemv" && l.weights[0]==name)return variant(l);
    return 2;
  }
#ifdef OWN_RT_HOST_ONLY
  bool allocation_probe=false, legacy_pointer_probe=false; // Only the CPU gate sets these.
#else
  static constexpr bool allocation_probe=false, legacy_pointer_probe=false;
#endif
  void load_expert_bank(const std::string& name) {
    const auto& t=w.directory.at(name);require(t.shape.size()==3&&p.g.experts==512,"expert bank shape");
    bool planes=p49b_weight(w,a,p,name);auto type=flash::grid_type(t.grid);unsigned k=t.shape.back();
    size_t src_stride=k/iq3::layout(type).elements*iq3::layout(type).bytes;
    size_t stride=planes?p49bgemv::layout(type,k).row_bytes:src_stride;
    size_t total=t.bytes/src_stride,bytes=total*stride;
    int layer=std::stoi(name.substr(4)),projection=name.find("ffn_gate_")!=std::string::npos?0:name.find("ffn_up_")!=std::string::npos?1:2;
    auto host=allocate(0,"pinned-experts:"+name,bytes,Category::weights,Lifetime::process,Memory::pinned);
    auto dest=static_cast<uint8_t*>(dev(0).arena.row(host).pointer);require(dest,"pinned expert allocation failed");
    const bool tile=projection==2&&sealed_selection.choices.at("down")=="down-tile16";
    if(tile)require(planes&&type==iq3::Type::IQ4_NL&&k==640&&t.shape[1]%16==0,"p58j down layout");
    size_t chunk=std::max(size_t(1),size_t(4*1024*1024)/std::max(src_stride,stride));if(tile)chunk=(chunk/16)*16;
    for(size_t row=0;!allocation_probe && row<total;row+=chunk){guard();size_t n=std::min(chunk,total-row);auto raw=w.read(name,row*src_stride,n*src_stride);
      if(planes)for(size_t r=0;r<n;++r)p49bgemv::repack_row(type,k,raw.data()+r*src_stride,dest+(row+r)*stride);
      else std::memcpy(dest+row*stride,raw.data(),raw.size());
      if(tile){auto transposed=p100::transpose(dest+row*stride,n);std::memcpy(dest+row*stride,transposed.data(),transposed.size());}
    }
    auto table=allocate(0,"expert-table:"+name,p.g.experts*sizeof(p58::Pointer),Category::weights,Lifetime::process);
    weights[0][name]=table;expert_banks[name]={host,table,bytes/size_t(p.g.experts),layer,projection};
    progress<<"{\"phase\":\"pinned-expert\",\"name\":"<<ownrt::quote(name)<<",\"bytes\":"<<bytes<<"}\n";progress.flush();
  }
  void publish_cache_table(const std::vector<p58::Entry>& table) {
    auto publication_start=std::chrono::steady_clock::now();
    auto* staging=static_cast<p58::Pointer*>(dev(0).arena.row(table_staging).pointer);ownrt::CopyEngine copy(dev(0));size_t base=0;
    std::array<uint64_t*,144> destinations{};size_t table_index=0;
    for(auto& [name,b]:expert_banks){
      destinations[table_index++]=static_cast<uint64_t*>(dev(0).arena.row(b.table).pointer);
      for(int id=0;id<p.g.experts;++id){const auto& e=table.at(b.layer*p.g.experts+id);staging[base+id]={b.projection==0?e.gate:b.projection==1?e.up:e.down,e.generation};}
      if(!overlapping())tail=copy.copy(b.table,0,table_staging,base*sizeof(p58::Pointer),p.g.experts*sizeof(p58::Pointer),{});base+=p.g.experts;
    }
    if(overlapping()) {
      require(dev(0).arena.row(table_staging).live&&dev(0).arena.row(table_staging).memory==Memory::pinned,"publication source lifetime");
      p58v::Publish op(destinations,p.g.experts*2,staging);
      std::vector<Allocation> ids{publication_device};for(const auto& [name,b]:expert_banks)ids.push_back(b.table);
      if(allocation_probe) {
        std::vector<ownrt::PreparedCompute> captured;dev(0).begin_capture(captured);
        try {dev(0).compute(op,ids,{});dev(0).end_capture();}catch(...){dev(0).end_capture();throw;}
      } else tail=dev(0).compute(op,ids,{});
    }
    drain(); // pinned staging remains immutable until every publication completes
    publication_uploads+=overlapping()?1:144;publication_bytes+=144*p.g.experts*sizeof(p58::Pointer);
    publication_host_ms+=ms(publication_start);
  }
  void initialize_cache() {
    require(expert_banks.size()==144,"all 48 target expert banks required");
    ownrt::set_ordered_retirement(dev(0),a.retirement=="ordered-foreground");
    halfcache=allocate(0,"exact-half-decode-table",65536*4,Category::weights,Lifetime::process);
    std::vector<float> half_values(65536);for(unsigned i=0;i<65536;++i)half_values[i]=iq3::half(uint16_t(i));
    upload(0,halfcache,0,half_values.data(),half_values.size()*4);

    cache_arena=allocate(0,"immutable-expert-cache",a.cache_bytes,Category::weights,Lifetime::process);
    std::vector<p58::Expert> experts(48*p.g.experts);
    for(auto& [name,b]:expert_banks)for(int id=0;id<p.g.experts;++id){auto& e=experts[b.layer*p.g.experts+id];auto ptr=uint64_t(dev(0).arena.row(b.host).pointer)+id*b.expert_bytes;
      if(b.projection==0){e.host_gate=ptr;e.gate_bytes=b.expert_bytes;}else if(b.projection==1){e.host_up=ptr;e.up_bytes=b.expert_bytes;}else{e.host_down=ptr;e.down_bytes=b.expert_bytes;}}
    expert_cache=std::make_unique<p58::Cache>(std::move(experts),uint64_t(dev(0).arena.row(cache_arena).pointer),a.cache_bytes);
    table_staging=allocate(0,"cache-table-staging",expert_banks.size()*p.g.experts*sizeof(p58::Pointer),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
    publication_device=allocate(0,"cache-publication-staging",144*p.g.experts*sizeof(p58::Pointer),Category::weights,Lifetime::process);
    publish_cache_table(expert_cache->table());
    for(const auto& l:p.launches)if(l.op=="expert_gate_up")route_sources.emplace_back(std::stoi(l.label.substr(4)),buffers[0].at(l.inputs[1]).id);
    require(route_sources.size()==48,"route census must cover every layer");
    route_log=allocate(0,"cache-route-readback",48*p.g.top*sizeof(iq3::Route),Category::pinned_slab,Lifetime::transfer,Memory::pinned);
    cache_log.open(a.output/"cache.jsonl");
  }
  void cache_begin_position(){
    if(!expert_cache||a.miss_path!="zero-copy")return;
    ++maintenance_position;
    if(overlapping()){cache_boundary();maintenance.begin();}
    else cache_epoch=expert_cache->begin_position();
  }
  void fill_cache(const std::vector<uint32_t>& routes) {
    auto start=std::chrono::steady_clock::now();auto plan=expert_cache->prepare(routes);ownrt::CopyEngine copy(dev(0));
    // Device owns every source and victim allocation until this queue is drained.
    // In-order fill publication is intentionally conservative: no overlap claim.
    for(const auto& f:plan.fills){const auto& e=expert_cache->experts()[f.expert];size_t off=f.offset;
      for(int projection=0;projection<3;++projection){const ExpertBank* bank=nullptr;for(auto& [name,b]:expert_banks)if(b.layer==int(f.expert/p.g.experts)&&b.projection==projection){bank=&b;break;}
        require(bank,"fill bank missing");tail=copy.copy(cache_arena,off,bank->host,size_t(f.expert%p.g.experts)*bank->expert_bytes,bank->expert_bytes,{});off+=bank->expert_bytes;}
    }
    drain();publish_cache_table(plan.table);drain();expert_cache->commit(plan.epoch,true,true);
    cache_fill_bytes+=plan.fill_bytes;cache_fills+=plan.fills.size();
    cache_log<<"{\"epoch\":"<<plan.epoch<<",\"fill_bytes\":"<<plan.fill_bytes<<",\"fills\":"<<plan.fills.size()<<",\"evictions\":"<<plan.evictions<<",\"resident_bytes\":"<<expert_cache->resident_bytes()<<",\"wall_ms\":"<<ms(start)<<"}\n";cache_log.flush();
    save(a.output/"cache-stats.json","{\"fill_bytes_total\":"+std::to_string(cache_fill_bytes)+",\"fills_total\":"+std::to_string(cache_fills)+",\"initial_cache_policy\":\"empty-content-independent\",\"miss_path\":"+ownrt::quote(a.miss_path)+"}\n");
  }
  std::vector<uint32_t> route_ids(const iq3::Route* routes,int layer) {
    std::vector<uint32_t> ids;for(int j=0;j<p.g.top;++j){require(routes[j].expert_id<unsigned(p.g.experts),"cache route outside expert bank");ids.push_back(layer*p.g.experts+routes[j].expert_id);}return ids;
  }
  void stream_layer(int layer,Allocation source){
    drain();auto epoch=expert_cache->begin_position();expert_cache->finish_position(epoch,true);auto b=readback(0,source,p.g.top*sizeof(iq3::Route));auto ids=route_ids(reinterpret_cast<const iq3::Route*>(b.data()),layer);fill_cache(ids);
    for(auto id:ids)require(expert_cache->resident(id),"streamed expert did not fit cache");
  }
  void cache_after_position(){
    if(!expert_cache||a.miss_path!="zero-copy")return;
    drain();if(overlapping())maintenance.end(true);else expert_cache->finish_position(cache_epoch,true);ownrt::CopyEngine copy(dev(0));size_t n=p.g.top*sizeof(iq3::Route);
    for(size_t i=0;i<route_sources.size();++i)tail=copy.copy(route_log,i*n,route_sources[i].second,0,n,{});
    drain();std::vector<uint32_t> ids;auto bytes=static_cast<const uint8_t*>(dev(0).arena.row(route_log).pointer);
    for(size_t i=0;i<route_sources.size();++i){auto row=route_ids(reinterpret_cast<const iq3::Route*>(bytes+i*n),route_sources[i].first);ids.insert(ids.end(),row.begin(),row.end());}
    if(overlapping()) {
      expert_cache->observe(ids);previous_routes=std::move(ids);
      cache_log<<"{\"position\":"<<maintenance_position<<",\"mode\":\"overlap\",\"plan_ms\":"<<maintenance_plan_ms
        <<",\"state\":"<<int(maintenance.state)<<",\"fill_bytes_total\":"<<cache_fill_bytes<<",\"fills_total\":"<<cache_fills
        <<",\"publication_uploads_total\":"<<publication_uploads<<",\"publication_bytes_total\":"<<publication_bytes
        <<",\"publication_host_ms_total\":"<<publication_host_ms<<"}\n";
      cache_log.flush();
      save(a.output/"cache-stats.json","{\"fill_bytes_total\":"+std::to_string(cache_fill_bytes)+",\"fills_total\":"+std::to_string(cache_fills)+",\"miss_path\":\"zero-copy\",\"mode\":\"overlap\"}\n");
    } else fill_cache(ids);
  }
  void load(int c, const std::string &name) {
    if (weights[c].count(name))
      return;
    auto &t = w.directory.at(name);
    require(t.component != "embedding" && t.component != "ple_lookup",
            "lookup must be bounded rows");
    if(caching()&&t.component=="routed_experts"){load_expert_bank(name);return;}
    unsigned v=weight_variant(name);
    auto type=flash::grid_type(t.grid);
    const bool planes=p49b_weight(w,a,p,name);
    size_t expanded_bytes=planes?p49b_weight_bytes(t):arithmetic::is_expanded(v)?size_t(t.shape[0])*arithmetic::row_bytes(type,t.shape[1],v):t.bytes;
    auto id = allocate(c, "weight:" + name, expanded_bytes, Category::weights,
                       Lifetime::process);
    weights[c][name] = id;
    if(allocation_probe)return;
    if(planes){
      const unsigned k=t.shape.back();const size_t raw_stride=p49bgemv::source_row_bytes(type,k),stride=p49bgemv::layout(type,k).row_bytes;
      const size_t total=t.bytes/raw_stride,chunk=std::max(size_t(1),size_t(4*1024*1024)/std::max(raw_stride,stride));
      for(size_t row=0;row<total;row+=chunk){
        guard();const size_t n=std::min(chunk,total-row);auto raw=w.read(name,row*raw_stride,n*raw_stride);
        std::vector<uint8_t> packed(n*stride);
        for(size_t r=0;r<n;++r)p49bgemv::repack_row(type,k,raw.data()+r*raw_stride,packed.data()+r*stride);
        upload(c,id,row*stride,packed.data(),packed.size());
      }
      return;
    }
    if(arithmetic::is_expanded(v)) {
      auto fmt=iq3::layout(type);size_t rb=t.shape[1]/fmt.elements*fmt.bytes;
      size_t er=arithmetic::row_bytes(type,t.shape[1],v);
      size_t rows_per=std::max(size_t(1),size_t(4*1024*1024)/std::max(rb,er));
      for(size_t row=0;row<size_t(t.shape[0]);row+=rows_per){
        auto nr=std::min(rows_per,size_t(t.shape[0])-row);auto raw=w.read(name,row*rb,nr*rb);
        auto expanded=iq3::expanded::expand(type,raw.data(),raw.size(),t.shape[1]);
        upload(c,id,row*er,expanded.data(),expanded.size());
      }
      return;
    }
    for (size_t off = 0; off < t.bytes; off += 4 * 1024 * 1024) {
      guard();
      auto b = w.read(name, off,
                      std::min(size_t(t.bytes - off), size_t(4 * 1024 * 1024)));
      upload(c, id, off, b.data(), b.size());
      progress << "{\"phase\":\"upload\",\"card\":" << c
               << ",\"tensor\":" << ownrt::quote(name)
               << ",\"completed_bytes\":" << off + b.size()
               << ",\"tensor_bytes\":" << t.bytes << "}\n";
      progress.flush();
    }
  }
  std::map<std::string,Allocation> state_spares;
  int context_extent=32, alternate_context_extent=32;
  uint64_t capacity_reprepares=0;
  std::unordered_map<const flash::Launch*,Prepared> alternate_prepared;
  void swap_state_banks() {
    drain();
    for(auto& [name,id]:state_spares)std::swap(buffers[0].at(name).id,id);
    prepared.swap(alternate_prepared);
    std::swap(context_extent,alternate_context_extent);
    issue_sites.swap(alternate_issue_sites);bank_parity^=1;
    fp32_sources[0]=0;fp32_extents[0]=0;
  }
  void initialize() {
    // Validate the allocation policy before constructing any device/backend.
    const size_t operator_scratch_bytes=target_scratch_bytes(p,a);
    owned_bytes.resize(a.cards);
#ifdef OWN_RT_HOST_ONLY
    if(!allocation_probe)devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
    devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card,profile_events||a.mtp||!a.draft_capture.empty())));
    save(a.output/"device-contact.json","{\"device_contact\":true}");
#endif
    if(a.argument_audit){argument_log.open(a.output/"argument-equivalence.jsonl");dev(0).argument_audit=&argument_log;dev(0).audit_prepare_each=a.audit_prepare_each;}
    std::ifstream rope_file(fs::path(__FILE__).parent_path()/"rope.bf16",std::ios::binary);
    require(bool(rope_file),"RoPE model constant missing");
    std::vector<uint8_t> rope_bytes((std::istreambuf_iterator<char>(rope_file)),{});
    require(rope_bytes.size()==rope_constants::bytes && hash(rope_bytes)==rope_constants::sha256,"RoPE model constant hash/extent mismatch");
    require(p.g.context<=rope_constants::positions,"RoPE position bound");
    history0=history1=p.g.eos;metadata=w.metadata();
    for (int c = 0; c < a.cards; ++c) {
      controls.push_back(allocate(c,"parallel-controls:"+std::to_string(c),12,Category::scratch,Lifetime::transaction));
      scores.push_back(allocate(c,"attention-scores:"+std::to_string(c),24*(p.g.budget+3)*4,Category::scratch,Lifetime::transaction));
      probabilities.push_back(allocate(c,"attention-probabilities:"+std::to_string(c),24*(p.g.budget+3)*4,Category::scratch,Lifetime::transaction));
      snapshots.push_back(allocate(c,"layer-snapshots:"+std::to_string(c),48*4*p.g.h*2,Category::scratch,Lifetime::transaction));
      buffers.emplace_back();
      weights.emplace_back();selected.emplace_back();loaded_layer.push_back(-1);
      fp32_inputs.push_back(allocate(c,"prepared-fp32-input",174080*4,Category::scratch,Lifetime::transaction));fp32_sources.push_back(0);fp32_extents.push_back(0);
      workspace.push_back(allocate(c,"gemv-workspace",8*1024*1024,Category::scratch,Lifetime::transaction));
      compact_routes.push_back(allocate(c,"compact-routes",p.g.top*sizeof(iq3::Route),Category::scratch,Lifetime::transaction));
      mixture_out.push_back(allocate(c,"ordered-mixture",p.g.h*2,Category::scratch,Lifetime::transaction));
      one.push_back(allocate(c,"mixture-one",4,Category::scratch,Lifetime::transaction));
      slab.push_back(allocate(c, "bounded-copy", 4 * 1024 * 1024,
                              Category::pinned_slab, Lifetime::transfer,
                              Memory::pinned));
      ropes.push_back(allocate(c,"rope-v2",rope_constants::bytes,Category::weights,Lifetime::process));
      upload(c,ropes[c],0,rope_bytes.data(),rope_bytes.size());
      scratch.push_back(allocate(c, "operator-scratch", operator_scratch_bytes,
                                 Category::scratch, Lifetime::transaction));
    }
    // Some dispatches do not touch controls/compact routes, and kernels may
    // leave unused scratch tails alone. Initialize the complete standalone
    // mutable storage once, outside every request timing span, so fresh-process
    // retention/state gates compare deterministic bytes rather than allocator dirt.
    {
      std::vector<uint8_t> zero(4*1024*1024,0);
      for(const auto& [id,owner]:allocations){const auto& row=dev(owner.first).arena.row(id);
        if(row.category==Category::weights)continue;
        for(size_t off=0;off<row.bytes;off+=zero.size())upload(owner.first,id,off,zero.data(),std::min(zero.size(),row.bytes-off));
      }
    }
    for (auto &b : p.buffers)
      for (int c = 0; c < a.cards; ++c)
        if (b.card == -1 || b.card == c) {
          Category cat = Category::scratch;
          Lifetime life = Lifetime::transaction;
          if (ends(b.name, ".state") || ends(b.name, "history") ||
              b.name == "token_history") {
            cat = Category::recurrent;
            life = Lifetime::request;
          }
          if (ends(b.name, ".keys") || ends(b.name, ".values") ||
              ends(b.name, ".pooled") || ends(b.name, ".raw")) {
            cat = Category::kv;
            life = Lifetime::request;
          }
          size_t n = count(b.shape), bytes = n * flash::scalar_bytes(b.type);
          auto id = allocate(c, b.name, bytes, cat, life);
          buffers[c][b.name] = {id, n, b.type};
          std::vector<uint8_t> zero(std::min(bytes, size_t(4 * 1024 * 1024)),
                                    0);
          for (size_t off = 0; off < bytes; off += zero.size())
            upload(c, id, off, zero.data(), std::min(zero.size(), bytes - off));
        }
    for (int c = 0; c < a.cards; ++c) {
      std::vector<uint8_t> snapshot_zero(48*4*p.g.h*2,0);
      upload(c,snapshots[c],0,snapshot_zero.data(),snapshot_zero.size());
      if (!buffers[c].count("active"))
        continue;
      float unit=1; upload(c,one[c],0,&unit,4);
      uint32_t active = 1;
      put(c, "active", &active, 4);
      if (buffers[c].count("token_history")) {
        int64_t history[2] = {p.g.eos, p.g.eos};
        put(c, "token_history", history, sizeof history);
        auto meta = w.metadata();
        put(c, "ple_metadata", meta.data(), meta.size() * 8);
      }
    }
    if (a.memory == "resident") {
      for (auto &l : p.launches)
        if (l.op != "lookup")
          for (auto &name : l.weights)
            load(l.card, name);
    }
    if(caching())initialize_cache();
  }
  void prepare_plan() {
    if(a.memory!="resident")return;
    for(const auto& l:p.launches) {
      if(l.op=="lookup" || l.op=="handoff" || l.op=="handoff_result")continue;
      if(l.op=="gemv" || l.op=="routed_gemv" || l.op=="expert_gate_up") {
        std::vector<Matrix> values{matrix(l)};
        if(l.op=="expert_gate_up")values.push_back(matrix(l,1));
        matrices.emplace(&l,std::move(values));
      } else prepared.emplace(&l,prepare_site(l));
    }
  }
  std::map<std::string,std::vector<uint8_t>> lookup_ids;
  void prepare_token(int token) {
    lookup_ids.clear();
    for(const auto& l:p.launches)if(l.op=="lookup") {
      auto input=buffers[l.card].at(l.inputs[0]);
      std::vector<uint8_t> raw(input.n*flash::scalar_bytes(input.type));
      if(input.type==Scalar::i32)std::memcpy(raw.data(),&token,4);
      else {
        int64_t old0=history0,old1=history1;
        if(old1==p.g.eos)old0=p.g.eos;
        for(int n=2;n<=3;++n) {
          uint64_t bits=uint64_t(token)*uint64_t(metadata[0]);
          bits^=uint64_t(old1)*uint64_t(metadata[1]);
          if(n==3)bits^=uint64_t(old0)*uint64_t(metadata[2]);
          int64_t v=std::bit_cast<int64_t>(bits);
          for(int h=0;h<8;++h){int i=(n-2)*8+h;auto size=metadata[3+i];require(size>0,"PLE host size");
            int64_t id=(v%size+size)%size+metadata[19+i];std::memcpy(raw.data()+i*8,&id,8);}
        }
      }
      lookup_ids[l.label]=std::move(raw);lookup(l);
    }
    history0=history1;history1=token;
  }
  void lookup(const flash::Launch &l) {
    int c = l.card;
    auto input = buffers[c].at(l.inputs[0]);
    auto ids = lookup_ids.at(l.label);
    auto &t = w.directory.at(l.weights[0]);
    auto type = flash::grid_type(t.grid);
    auto fmt = iq3::layout(type);
    size_t rb = t.shape.back() / fmt.elements * fmt.bytes;
    std::vector<uint16_t> values;
    for (size_t j = 0; j < input.n; ++j) {
      int64_t id;
      if (input.type == Scalar::i64)
        std::memcpy(&id, ids.data() + j * 8, 8);
      else {
        int32_t v;
        std::memcpy(&v, ids.data() + j * 4, 4);
        id = v;
      }
      require(id >= 0 && id < t.shape[0], "lookup bounds");
      auto row = w.read(t.name, id * rb, rb);
      for (int k = 0; k < t.shape.back(); ++k)
        values.push_back(iq3::bf16_bits(iq3::element(type, row.data(), k)));
    }
    put(c, l.outputs[0], values.data(), values.size() * 2);
  }
  void stage_layer(int c,int layer) {
    if(a.memory!="layer-streaming" || loaded_layer[c]==layer)return;
    release_layer(c);loaded_layer[c]=layer;
    std::string prefix="blk."+std::to_string(layer)+".";
    for(const auto& l:p.launches) for(const auto& name:l.weights) {
      const auto& t=w.directory.at(name);
      if(name.starts_with(prefix) && t.component!="routed_experts" &&
         name.find("_exps.weight")==std::string::npos && l.op!="lookup")load(c,name);
    }
  }
  void load_selected(int c,const std::string& name) {
    if(weights[c].count(name))return;
    const auto& t=w.directory.at(name);
    require(t.shape.size()==3 && selected[c].size()==size_t(p.g.top),"selected bank geometry");
    size_t expert_bytes=t.bytes/p.g.experts;
    auto id=allocate(c,"selected:"+name,expert_bytes*p.g.top,Category::weights,Lifetime::process);
    weights[c][name]=id;
    for(int slot=0;slot<p.g.top;++slot) {
      require(selected[c][slot]<unsigned(p.g.experts),"route outside bank");
      for(size_t off=0;off<expert_bytes;off+=4*1024*1024) {
        auto b=w.read(name,size_t(selected[c][slot])*expert_bytes+off,
                      std::min(expert_bytes-off,size_t(4*1024*1024)));
        upload(c,id,size_t(slot)*expert_bytes+off,b.data(),b.size());
      }
    }
  }
  Matrix matrix(const flash::Launch& l,size_t projection=0) {
    int c=l.card;bool routed=l.op!="gemv";
    const auto& t=w.directory.at(l.weights[projection]);
    if(routed && a.memory=="layer-streaming")load_selected(c,t.name);else load(c,t.name);
    Matrix m{};m.type=flash::grid_type(t.grid);m.w=weights[c].at(t.name);
    m.x=buffers[c].at(l.inputs[0]).id;m.y=buffers[c].at(l.outputs[projection*2]).id;
    m.rows=l.shape[1];m.columns=l.shape[2];m.span=m.rows;
    m.workspace=workspace[c];
    if(routed) {
      m.count=p.g.top;m.experts=a.memory=="layer-streaming"?p.g.top:p.g.experts;
      m.status=buffers[c].at(l.outputs[projection*2+1]).id;
      if(a.memory=="layer-streaming") {
        std::vector<iq3::Route> routes;
        for(int j=0;j<p.g.top;++j)routes.push_back({uint32_t(j),0,uint32_t(m.rows)});
        upload(c,compact_routes[c],0,routes.data(),routes.size()*sizeof(iq3::Route));
        m.routes=compact_routes[c];
      } else m.routes=buffers[c].at(l.inputs[1]).id;
    }
    return m;
  }
  void linear(const flash::Launch& l) {
    int c=l.card;
    if(small_followers.count(&l))return; // output was written by its earlier sibling tuple
    if(auto grouped=small_groups.find(&l);grouped!=small_groups.end()){
      std::vector<Matrix> members;std::vector<unsigned> variants;
      for(const auto* site:grouped->second.members){
        auto found=matrices.find(site);if(a.memory=="resident"&&found==matrices.end())found=matrices.emplace(site,std::vector<Matrix>{matrix(*site)}).first;
        members.push_back(a.memory=="resident"?found->second[0]:matrix(*site));variants.push_back(variant(*site));
      }
      if(class_timing)set_class(grouped->second.name);
      auto name=grouped->second.name;auto key=name.starts_with("small.ffn")?"small.ffn":name;
      finish(c,!a.mini&&a.memory=="resident"&&name=="small.ffn.q6"?p49d::small(dev(c),name,members,variants):!a.mini&&packet26::dispatch.fusion_choice(key)=="p30.small.rows4"?p30integrated::small(dev(c),name,members,variants):packet27::small::submit(dev(c),name,members,variants),true);return;
    }
    auto it=matrices.find(&l);
    if(a.memory=="resident" && it==matrices.end()) {
      std::vector<Matrix> values{matrix(l)};
      if(l.op=="expert_gate_up")values.push_back(matrix(l,1));
      it=matrices.emplace(&l,std::move(values)).first;
    }
    auto m=a.memory=="resident"?it->second[0]:matrix(l);
    if(p39::tagged(l)){
      auto kind=p39::kind(l);auto cls=packet26::Dispatch::class_name(l.label);auto prefix=l.label.substr(0,l.label.size()-cls.size());
      auto id=[&](const std::string&name){return buffers[c].at(name).id;};
      p39::Bindings b;b.indirect=caching()&&(l.op=="expert_gate_up"||l.op=="routed_gemv");b.error=id("error");b.active=id("active");b.position=id("position");b.capacity=p.g.context;
      if(kind==p39::Kind::silu_div4)b.out=id(l.label.substr(0,l.label.size()-3)+"act");
      if(kind==p39::Kind::shared_act){b.other=id(prefix+"shexpgate");b.out=id(prefix+"shexpact");}
      if(kind==p39::Kind::attention_combine){b.streams=id("streams");b.inject=id(prefix+"hc.a.inject");}
      if(kind==p39::Kind::shared_combine){
        finish(c,mixture(dev(c),id(prefix+"expsdown"),id(prefix+"prob"),mixture_out[c],p.g.h),false);
        b.streams=id("streams");b.inject=id(prefix+"hc.f.inject");b.mixture=mixture_out[c];b.shared_gate=id(prefix+"shared_gate");b.out=id(prefix+"moe");b.one=one[c];
      }
      std::vector<Matrix> selected{m};if(l.op=="expert_gate_up")selected.push_back(a.memory=="resident"?it->second[1]:matrix(l,1));
      // Same engine call for ordinary decode and each serial M=2 row.
      const bool round2=!a.mini&&a.memory=="resident"&&((kind==p39::Kind::silu_div4&&(cls=="hc.a.low"||cls=="hc.f.low"))||kind==p39::Kind::attention_combine);
      finish(c,round2?p49c::dense_submit(dev(c),m,kind,b):p49b_site(w,a,l)?(kind==p39::Kind::expert_checks&&a.experts!="production"?p58ag::expert(dev(c),selected,b,halfcache,a.experts=="wide64+halfcache"):p49d::expert(dev(c),selected,kind,b,sealed_selection.choices.at("down"))):p39::submit(dev(c),selected,kind,b),true);return;
    }
    const auto cls=packet26::Dispatch::class_name(l.label);
    if(!a.mini&&a.memory=="resident"&&(cls=="hc.a.gate"||cls=="hc.f.gate")){
      p39::Bindings b;b.error=buffers[c].at("error").id;b.active=buffers[c].at("active").id;b.position=buffers[c].at("position").id;b.capacity=p.g.context;
      finish(c,p49c::dense_submit(dev(c),m,p39::Kind::expert_checks,b),true);return;
    }
    const auto& candidate=gemv_choices.at(&l).first;
    if(candidate=="p30.small.rows4"&&!a.mini) {
      std::vector<Matrix> selected{m};
      std::array<unsigned,1> variants{variant(l)};
      auto cls=packet26::Dispatch::class_name(l.label);
      finish(c,p30integrated::small(dev(c),cls.ends_with(".gate")?"hc.gate":"shexpdown",selected,variants),true);return;
    }
    if((candidate.starts_with("p28.")||candidate.starts_with("p29.")||candidate.starts_with("p33.")||candidate.starts_with("p42."))&&!a.mini){
      std::vector<Matrix> selected{m};if(l.op=="expert_gate_up")selected.push_back(a.memory=="resident"?it->second[1]:matrix(l,1));
      finish(c,candidate.starts_with("p28.")?p28::submit(dev(c),selected,candidate,l.op=="expert_gate_up",variant(l),caching() && l.op=="expert_gate_up" && !legacy_pointer_probe):(candidate.starts_with("p33.")||candidate.starts_with("p42."))?p33::submit(dev(c),selected,candidate,l.op=="expert_gate_up",variant(l)):p29::submit(dev(c),selected,candidate,l.op=="expert_gate_up",variant(l)),true);return;
    }
    if((candidate.starts_with("p25.")||candidate.starts_with("p27."))&&!a.mini){ // model-shape candidates; mini retains registered packed arithmetic
      std::vector<Matrix> selected{m};if(l.op=="expert_gate_up")selected.push_back(a.memory=="resident"?it->second[1]:matrix(l,1));
      Allocation prepared_input=0;
      if(candidate=="p27.fp32_input"){
        size_t n=size_t(m.columns)*(l.op=="expert_gate_up"?1:m.count);
        if(fp32_sources[c]!=m.x||fp32_extents[c]!=n){finish(c,packet26::p25bridge::prepare_input(dev(c),m.x,fp32_inputs[c],n),true);fp32_sources[c]=m.x;fp32_extents[c]=n;}
        prepared_input=fp32_inputs[c];
      }
      finish(c,packet26::p25bridge::submit(dev(c),selected,candidate,l.op=="expert_gate_up",variant(l),prepared_input),true);return;
    }
    if(l.op=="gemv")finish(c,dense(dev(c),m,variant(l)),true);
    else if(l.op=="expert_gate_up") {
      auto up=a.memory=="resident"?it->second[1]:matrix(l,1);finish(c,experts(dev(c),{m,up},true),true);
    } else finish(c,experts(dev(c),{m},false),true);
  }
  Prepared prepare_site(const flash::Launch& l) {int c=l.card;
      Spec s;
      s.g = p.g;
      s.extent = (l.op=="qsa_select"||l.op=="qsa_attention")?std::min(p.g.context,context_extent):0;
      s.packed_heads = !a.mini;
      s.site.parameter = l.parameter;
      std::copy(l.shape.begin(), l.shape.end(), s.site.shape);
      if(l.op=="moe_combine")s.site.shape[0]=1;
      static const std::map<std::string, Op> ops = {
#define OP(n) {#n, Op::n}
          OP(norm),
          OP(silu_div4),
          OP(silu_product),
          OP(hc_mix),
          OP(hc_combine),
          OP(conv),
          OP(gdn),
          OP(gdn_norm_gate),
          OP(route),
          OP(expert_gather),
          OP(moe_combine),
          OP(qsa_prepare),
          OP(qsa_append_pool),
          OP(qsa_select),
          OP(qsa_attention),
          OP(ple_gate),
          OP(ple_add),
          OP(argmax)
#undef OP
      };
      if (l.op == "begin")
        s.special = Special::begin;
      else if (l.op == "commit")
        s.special = Special::commit;
      else if (l.op == "broadcast")
        s.special = Special::broadcast;
      else if (l.op == "ple_hash")
        s.special = Special::ple_hash;
      else if (l.op == "check_status")
        s.special = Special::check_status;
      else
        s.op = ops.at(l.op);
      std::vector<Allocation> bindings;
      int k = 0;
      for (auto &name : l.inputs) {
        auto b = buffers[c].at(name);
        if(l.op=="moe_combine" && k==0)b={mixture_out[c],size_t(p.g.h),Scalar::bf16};
        if(l.op=="moe_combine" && k==1)b={one[c],1,Scalar::f32};
        s.sizes[k] = b.n;
        s.types[k++] = b.type;
        bindings.push_back(b.id);
        ++s.ni;
      }
      for (auto &name : l.outputs) {
        auto b = buffers[c].at(name);
        if(state_spares.count(name))b.id=state_spares.at(name);
        s.sizes[k] = b.n;
        s.types[k++] = b.type;
        bindings.push_back(b.id);
        ++s.no;
      }
      for (auto &name : l.weights) {
        load(c, name);
        auto &t = w.directory.at(name);
        s.grids[s.nw] = flash::grid_type(t.grid);
        s.weight_elements[s.nw] = count(t.shape);
        ++s.nw;
        bindings.push_back(weights[c].at(name));
      }
      bindings.push_back(scratch[c]);
      for (auto name : {"error", "position", "active"})
        bindings.push_back(buffers[c].at(name).id);
      bindings.push_back(ropes[c]);
      s.implementation=packet26::dispatch.implementation_for(l.label,s.op);
      // Packet49 arithmetic identity: both verification rows take split32 QSA.
      if(l.op=="qsa_attention" && p.g.h==2560)s.implementation=12;
      s.fused_combine_norm=l.op=="hc_combine" && l.outputs.size()==2;
      if(s.fused_combine_norm)s.implementation=1;
      if(l.op=="route" && l.outputs.size()==4)s.implementation=packet26::dispatch.fusion_choice("route+gather")=="p42.route.production_rank32"?6:packet26::dispatch.fusion_choice("route+gather")=="round2"?2:1;
      auto submit=!a.mini&&a.memory=="resident"?sealed_selection.site(s):packet18::submit_parallel;
      return {s,std::move(bindings),submit};
  }
  // Packet60: target-only HC. Both ordinary decode and each serial M=2
  // row use this same dispatch. Preserve one capture slot per original site.
  bool fused_hc(const flash::Launch& l) {
    const int stage=p60::stage(l.label);
    if(a.hc!="p60fusion"||a.mini||a.memory!="resident"||a.nongemv!="parallel"||stage<0)return false;
    if(stage==3)return true; // act/mix/inject are written by earlier stages
    const int c=l.card;
    const std::string tag=l.label.substr(0,l.label.rfind('.'));
    const std::string prefix=tag.substr(0,tag.find(".hc."));
    const std::string wt=prefix+(tag.ends_with(".a")?".hc_attn_":".hc_ffn_");
    auto id=[&](const std::string&name){return buffers[c].at(name).id;};
    auto weight=[&](const std::string&name){load(c,name);return weights[c].at(name);};
    p60::IDs ids{id("streams"),weight(wt+"norm.weight"),weight(wt+"down.weight"),
      weight(wt+"up.weight"),weight(wt+"inject.weight"),id(tag+".norm"),
      id(tag+".low"),id(tag+".act"),id(tag+".gate"),id(tag+".mix"),
      id(tag+".inject"),scratch[c],workspace[c],id("error"),id("active"),id("position")};
    require(p.g.h==2560&&p.g.low==320,"packet60 production HC geometry");
    require(flash::grid_type(w.directory.at(wt+"norm.weight").grid)==iq3::Type::F32 &&
      flash::grid_type(w.directory.at(wt+"inject.weight").grid)==iq3::Type::F32 &&
      flash::grid_type(w.directory.at(wt+"down.weight").grid)==iq3::Type::Q8_0 &&
      flash::grid_type(w.directory.at(wt+"up.weight").grid)==iq3::Type::Q8_0,
      "packet60 production HC weight formats");
    finish(c,p60::submit(dev(c),ids,stage,p.g.context,a.hc_geometry=="hc-wide"),stage!=0);
    return true;
  }
// Included in Engine. Empty sites remain in the plan for stable recapture indexes.
 bool other_fused_site(const flash::Launch& l){
  if(a.other_fusion!="fused"||a.mini)return false;
  require(a.memory=="resident"&&a.nongemv=="parallel"&&p.g.h==2560&&p.g.mid==640&&p.g.top==10,"p109 exact production geometry");
  const auto cls=packet26::Dispatch::class_name(l.label);int c=l.card;
  const auto prefix=l.label.substr(0,l.label.size()-cls.size());
  auto id=[&](const std::string& n){return buffers[c].at(n).id;};
  if(cls=="route"){
   // The p109 fused router includes exact route-fast; no standalone route arm.
   const auto& bound=prepared.at(&l);
   finish(c,p109::route_activation(dev(c),bound.spec,bound.bindings,{id(prefix+"shexpgate"),id(prefix+"shexpup"),id(prefix+"shexpact")}),false);
   return true;
  }
  if(cls=="shexpact"||l.op=="moe_combine")return true;
  if(cls=="shexpdown"){
   require(l.op=="gemv"&&l.shape[1]==2560&&l.shape[2]==640&&variant(l)==6&&flash::grid_type(w.directory.at(l.weights[0]).grid)==iq3::Type::Q8_0,"p109 shared-down production ABI");
   auto m=matrix(l);
   finish(c,p109::shared_down(dev(c),{m.w,m.x,m.y,id(prefix+"expsdown"),id(prefix+"prob"),mixture_out[c],id(prefix+"shared_gate"),one[c],id(prefix+"moe"),id("error"),id("position"),id("active")},p.g.context),true);
   return true;
  }
  return false;
 }

  void execute_site(const flash::Launch& l) {int c=l.card;
    if(other_fused_site(l)) { /* Common BF16-writer invalidation below. */ }
    else if(fused_hc(l)) { /* Common BF16-writer invalidation remains below. */ }
    else if (l.op == "lookup") { fp32_sources[c]=0; /* Prepared once at token boundary from known input/history. */ }
    else if (l.op == "handoff" || l.op == "handoff_result") {
      for (auto &name : l.outputs) {
        if(!preparing_commands)drain(); // every peer copy starts with both owners drained
        auto source=buffers[l.source_card].at(name), dest=buffers[c].at(name);
        ownrt::CopyEngine copy(dev(c));
        auto event=copy.copy(dest.id,0,source.id,0,source.n*flash::scalar_bytes(source.type),{});if(!preparing_commands)tail=event;
      }
    } else if (l.op == "gemv" || l.op == "routed_gemv" || l.op=="expert_gate_up") {
      linear(l);
    } else {
      if(l.op=="moe_combine")finish(c,mixture(dev(c),buffers[c].at(l.inputs[0]).id,
          buffers[c].at(l.inputs[1]).id,mixture_out[c],p.g.h),false);
      Prepared temporary;
      const Prepared* bound=nullptr;
      if(a.memory=="resident"&&!fresh_arguments)bound=&prepared.at(&l);
      else {temporary=prepare_site(l);bound=&temporary;}
      const auto& s=bound->spec;const auto& bindings=bound->bindings;
      if(a.nongemv=="parallel")finish(c,bound->submit(dev(c),s,bindings,controls[c],scores[c],probabilities[c],{}),false);
      else finish(c, iq3::step_operator(dev(c), s, bindings));
      if(l.op=="route" && a.memory=="layer-streaming") {
        std::vector<std::string> evict;
        for(const auto& [name,id]:weights[c])if(name.find("_exps.weight")!=std::string::npos)evict.push_back(name);
        drain();
        for(const auto& name:evict){release(c,weights[c].at(name));weights[c].erase(name);}
        auto ids=readback(c,buffers[c].at(l.outputs[0]).id,p.g.top*4);
        selected[c].resize(p.g.top);std::memcpy(selected[c].data(),ids.data(),ids.size());
      }
    }
    // A cached FP32 input is valid only until a scheduled writer touches its
    // BF16 source. Every token lookup invalidates it, including host uploads.
    for(const auto& output:l.outputs){auto found=buffers[c].find(output);if(found!=buffers[c].end()&&found->second.id==fp32_sources[c])fp32_sources[c]=0;}
  }
  void verify_configuration() const {
    if(packet26::dispatch.classes!=sealed_dispatch.classes||packet26::dispatch.gemv!=sealed_dispatch.gemv||packet26::dispatch.fusions!=sealed_dispatch.fusions)
      throw std::logic_error("dispatch changed; construct a new Engine and re-prepare");
    if(prepared_path&&issue_sites.size()!=p.launches.size())throw std::logic_error("plan changed; rebuild Engine");
  }
  void prepare_commands() {
    if(a.memory!="resident" || a.legacy)return;
    drain();issue_sites.clear();issue_sites.resize(p.launches.size());
    std::fill(fp32_sources.begin(),fp32_sources.end(),0);
    for(size_t i=0;i<p.launches.size();++i) {
      const auto& l=p.launches[i];auto& site=issue_sites[i];site.card=l.card;
      site.layer=l.label.starts_with("blk.")?std::stoi(l.label.substr(4)):-1;
      site.layer_end=ends(l.label,".ffn.combine");
      site.prefill_skip=l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax";
      site.copy=l.op=="handoff"||l.op=="handoff_result";
      if(site.copy)site.family=9;
      else if(small_groups.count(&l))site.family=4;
      else if(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up") {
        const auto& candidate=gemv_choices.at(&l).first;
        site.family=(candidate.starts_with("p28.")||candidate.starts_with("p29.")||candidate.starts_with("p33.")||candidate.starts_with("p30."))?3:(candidate.starts_with("p25.")||candidate.starts_with("p27."))?2:l.op=="gemv"?0:1;
      }else if(l.op=="moe_combine")site.family=7;
      else if(l.op=="check_status"||l.op=="begin"||l.op=="commit")site.family=8;
      else {auto found=prepared.find(&l);site.family=found!=prepared.end()&&found->second.spec.implementation?5:6;}
      set_class(l.label);site.cls=current_cls;
      site.fp32_source=fp32_sources[l.card];site.fp32_extent=fp32_extents[l.card];
      preparing_commands=true;auto& d=dev(l.card);d.begin_capture(site.commands);
      try {execute_site(l);d.end_capture();preparing_commands=false;}
      catch(const std::exception& error){d.end_capture();preparing_commands=false;throw std::runtime_error(l.label+": "+error.what());}
      site.cls=current_cls;
    }
    std::fill(fp32_sources.begin(),fp32_sources.end(),0);
    std::ofstream log(a.output/("prepared-arguments-parity"+std::to_string(bank_parity)+".jsonl"));
    for(size_t i=0;i<issue_sites.size();++i)for(const auto& cmd:issue_sites[i].commands){
      log<<"{\"site\":"<<i<<",\"label\":"<<ownrt::quote(p.launches[i].label)<<",\"card\":"<<cmd.queue<<",\"argument_hex\":\"";
      for(auto b:cmd.argument_bytes)log<<"0123456789abcdef"[b>>4]<<"0123456789abcdef"[b&15];log<<"\"}\n";
    }
  }
  void admit_position(int position) {
    require(position>=0&&position<p.g.context,"capacity position admission");
    const int bound=std::min(p.g.context,((position+32)/32)*32);
    if(context_extent==bound)return;
    drain();context_extent=bound;++capacity_reprepares;
    if(!resident)return; // streaming prepares each site with the current bound
    for(size_t i=0;i<p.launches.size();++i) {
      const auto& l=p.launches[i];
      if(l.op!="qsa_select"&&l.op!="qsa_attention")continue;
      prepared[&l]=prepare_site(l);
      if(!prepared_path)continue;
      auto& site=issue_sites.at(i);site.commands.clear();
      preparing_commands=true;auto& d=dev(l.card);d.begin_capture(site.commands);
      try {execute_site(l);d.end_capture();preparing_commands=false;}
      catch(...){d.end_capture();preparing_commands=false;throw;}
    }
  }
  void audit_issue_site(size_t index) {
#ifdef OWN_RT_HOST_ONLY
    if(!a.argument_audit)return;
    const auto& l=p.launches[index];std::vector<ownrt::PreparedCompute> fresh;
    auto old_sources=fp32_sources;auto old_extents=fp32_extents;auto old_cls=current_cls;
    fresh_arguments=true;fp32_sources[l.card]=issue_sites[index].fp32_source;fp32_extents[l.card]=issue_sites[index].fp32_extent;
    preparing_commands=true;auto& d=dev(l.card);d.begin_capture(fresh);
    try {execute_site(l);d.end_capture();preparing_commands=false;}
    catch(...){d.end_capture();preparing_commands=false;throw;}
    fresh_arguments=false;fp32_sources=old_sources;fp32_extents=old_extents;current_cls=old_cls;
    const auto& selected=issue_sites[index].commands;
    require(fresh.size()==selected.size(),"parity prepared command count");
    for(size_t j=0;j<fresh.size();++j){
      const auto& x=fresh[j];const auto& y=selected[j];
      require(x.ids==y.ids&&x.pointers==y.pointers&&x.argument_bytes==y.argument_bytes&&x.operation_bytes==y.operation_bytes,
              "stale parity prepared argument block");++parity_argument_checks;
    }
    argument_log<<"{\"parity\":"<<bank_parity<<",\"site\":"<<index<<",\"fresh_argument_blocks\":"<<fresh.size()<<",\"passed\":true}\n";
#endif
  }
  flash::Event issue_site(size_t index,flash::Event dep) {
    if(poisoned||stopped)throw std::runtime_error("prepared guard closed");
    if(dep!=logical)throw std::logic_error("step event order");
    auto& site=issue_sites.at(index);int c=site.card;
    if(submission_card!=c)drain();submission_card=c;current_cls=site.cls;
    auto previous_submitted=submitted;
    auto started=class_timing?std::chrono::steady_clock::now():std::chrono::steady_clock::time_point{};
    double waited=wait_ms;
    for(const auto& cmd:site.commands){if(site.copy)drain();auto event=dev(c).issue(cmd);if(site.copy)tail=event;else finish(c,{event,event,1},site.family<=4);}
    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);
    if(a.checked&&site.layer_end&&integer(c,"error"))throw std::runtime_error("device sticky error at layer end "+p.launches[index].label);
    if(a.mini||a.checked)site_timings<<"{\"kind\":\"site\",\"label\":"<<ownrt::quote(p.launches[index].label)<<",\"wall_ms\":null,\"kernel_submissions\":"<<submitted-previous_submitted<<"}\n";
    return ++logical;
  }
  flash::Event enqueue(const flash::Launch &l, flash::Event dep) override {
    last_site=&l.label;
    if(caching() && a.miss_path=="streamed" && l.op=="expert_gate_up")stream_layer(std::stoi(l.label.substr(4)),buffers[0].at(l.inputs[1]).id);
    if(prepared_path){auto index=size_t(&l-p.launches.data());audit_issue_site(index);return issue_site(index,dep);}
    guard();
    require(dep == logical, "step event order");
    int c = l.card;
    if(submission_card!=c)drain(); // both queues drained and events retired on host
    if(class_timing)set_class(l.label);
    submission_card=c;
    if(l.label.starts_with("blk."))stage_layer(c,std::stoi(l.label.substr(4)));
    auto site_start=std::chrono::steady_clock::now();
    double old_g=gemv_ms,old_n=nongemv_ms,old_t=transfer_ms;
    uint64_t old_submitted=submitted;
    execute_site(l);
    // Bring-up is segmented and synchronously drained. A failed operation
    // poisons the request; there is no retry or checkpoint reuse after failure.
    if(a.checked && ends(l.label,".ffn.combine") && integer(c,"error"))
      throw std::runtime_error("device sticky error at layer end " + l.label);
    if(a.mini || a.checked)site_timings << "{\"kind\":\"site\",\"label\":" << ownrt::quote(l.label)
            << ",\"wall_ms\":" << ms(site_start) << ",\"gemv_device_ms\":" << device_ms(gemv_ms-old_g)
            << ",\"non_gemv_device_ms\":" << device_ms(nongemv_ms-old_n)
            << ",\"transfer_wall_ms\":" << transfer_ms-old_t
            << ",\"kernel_submissions\":" << submitted-old_submitted << "}\n";
    if(a.checked)timings.flush();
    if(a.checked)progress << "{\"phase\":\"site\",\"label\":" << ownrt::quote(l.label)
             << ",\"card\":" << c << "}\n";
    if(a.checked)progress.flush();
    return ++logical;
  }
  void submission_failed() noexcept override { poisoned = true; }
  std::vector<std::string> shutdown() {
    std::vector<std::string> receipts;
    for (auto &d : devices) {
      auto r = d->shutdown(std::chrono::seconds(60));
      receipts.push_back(r.json());
      if (!r.safe_to_exit || r.exit_code) {
        save(a.output / "retained-owner.json", r.json());
        if(r.in_flight)ownrt::hold_for_supervisor();
        throw std::runtime_error("owner teardown failed after drain: "+r.error);
      }
    }
    return receipts;
  }
  void release(int c,Allocation id) {
    dev(c).arena.release(id);owned_bytes[c]-=allocations.at(id).second;allocations.erase(id);
  }
  void release_layer(int c) {
    drain();
    for (auto &[name, id] : weights[c])
      release(c,id);
    weights[c].clear();
  }
};
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/mtp.hpp"
static void write_plan(const fs::path &path, const flash::Plan &p,
                       const Weights &w, int cards, const Options& a) {
  std::map<std::string, int> owner;
  std::map<std::string,size_t> stored;
  auto dispatch=[&](const flash::Launch& l,const auto&){return selected_variant(w,a,p,l);};
  std::ostringstream o;
  o << "{\"schema\":\"own-runtime.iq3.packet13.plan.v1\",\"cards\":" << cards
    << ",\"dispatch_sites\":" << p.launches.size() << ",\"tensor_owners\":[";
  bool comma = false;
  for (auto &l : p.launches)
    for (auto &n : l.weights) {
      if (owner.count(n)) {
        require(owner[n] == l.card, "tensor has conflicting owners");
        continue;
      }
      owner[n] = l.card;
      auto &t = w.directory.at(n);
      auto v=l.op=="gemv"?dispatch(l,t):2;
      stored[n]=p49b_weight(w,a,p,n)?p49b_weight_bytes(t):arithmetic::is_expanded(v)?size_t(t.shape[0])*arithmetic::row_bytes(flash::grid_type(t.grid),t.shape[1],v):t.bytes;
      o << (comma ? "," : "") << "{\"name\":" << ownrt::quote(n)
        << ",\"card\":" << (l.op == "lookup" ? -1 : l.card)
        << ",\"bytes\":" << t.bytes << ",\"stored_bytes\":" << stored[n]
        << ",\"component\":" << ownrt::quote(t.component);
      if(l.op=="gemv" || l.op=="routed_gemv" || l.op=="expert_gate_up")
        o << ",\"variant\":" << ownrt::quote(arithmetic::name(dispatch(l,t)));
      o << "}";
      comma = true;
    }
  o << "],\"launch_census\":[";
  bool first_site=true;
  for(const auto& l:p.launches){
    unsigned before=1,after=1;
    if(l.op=="lookup" || l.op=="handoff" || l.op=="handoff_result")before=after=0;
    else if(l.op=="gemv") {auto v=dispatch(l,w.directory.at(l.weights[0]));before=after=(v==1||v==4)?2:1;}
    else if(l.op=="moe_combine") {before=2;after=2;}
    else if(l.op=="norm"||l.op=="silu_div4"||l.op=="silu_product"||l.op=="hc_mix"||l.op=="conv"||l.op=="gdn"||l.op=="gdn_norm_gate"||l.op=="qsa_prepare"||l.op=="qsa_append_pool"||l.op=="qsa_select")after=1;
    else if(l.op=="qsa_attention")after=3;
    o<<(first_site?"":",")<<"{\"label\":"<<ownrt::quote(l.label)<<",\"op\":"<<ownrt::quote(l.op)<<",\"card\":"<<l.card
      <<",\"core_kernels\":"<<before<<",\"parallel_kernels\":"<<after<<"}";first_site=false;
  }
  o << "],\"expert_placement\":\"all expert banks pinned; pointer table selects VRAM cache or host; none "
       "pruned\",\"one_card_full_model\":\"resident nonexperts/head/KV/state and immutable cache; no "
       "pruning\",\"capture\":false,\"memory_plan\":{";
  size_t extra=174080*4+rope_constants::bytes+target_scratch_bytes(p,a)+8*1024*1024+p.g.top*sizeof(iq3::Route)+p.g.h*2+4+12+2*24*(p.g.budget+3)*4+48*4*p.g.h*2;
  std::vector<size_t> base(cards,extra),resident(cards,0);size_t pinned_expert_bytes=0;
  for(const auto& b:p.buffers)for(int c=0;c<cards;++c)
    if(b.card==-1 || b.card==c)base[c]+=count(b.shape)*flash::scalar_bytes(b.type);
  std::map<int,size_t> layer;
  for(const auto& [n,c]:owner) {
    const auto& t=w.directory.at(n);
    if(t.component=="embedding" || t.component=="ple_lookup")continue;
    if(!a.mini&&a.memory=="resident"&&t.component=="routed_experts")pinned_expert_bytes+=stored.at(n);
    resident[c]+=(!a.mini&&a.memory=="resident"&&t.component=="routed_experts")?size_t(p.g.experts)*sizeof(p58::Pointer):stored.at(n);
    int number=n.starts_with("blk.")?std::stoi(n.substr(4)):-1;
    layer[number]+=t.shape.size()==3?t.bytes/p.g.experts*p.g.top:stored.at(n);
  }
  if(!a.mini&&a.memory=="resident")resident[0]+=a.cache_bytes+1179648; // exact-half table charged inside existing workspace bound
  size_t peak=0;for(auto [n,bytes]:layer)peak=std::max(peak,bytes);
  o << "\"request_and_workspace_bytes_per_card\":[";
  for(int c=0;c<cards;++c)o<<(c?",":"")<<base[c];
  o << "],\"resident_weights_per_card\":[";
  for(int c=0;c<cards;++c)o<<(c?",":"")<<resident[c];
  o << "],\"streamed_peak_weight_bytes\":" << peak
    << ",\"pinned_bytes_per_card\":"<<(4194304+pinned_expert_bytes+(!a.mini&&a.memory=="resident"?(144*p.g.experts*sizeof(p58::Pointer)+48*p.g.top*sizeof(iq3::Route)):0))<<",\"pinned_expert_bytes\":"<<pinned_expert_bytes<<",\"expert_cache_bytes\":"<<a.cache_bytes<<",\"read_chunk_bytes\":4194304"
       ",\"driver_shadows_included\":false}}";
  save(path, o.str());
  for(int c=0;c<cards;++c){auto peak_bytes=base[c]+(a.memory=="resident"?resident[c]:peak);
    std::cout<<"card "<<c<<" owned_bytes "<<peak_bytes<<" weights "<<(a.memory=="resident"?resident[c]:peak)<<" dispatch "<<a.gemv<<'\n';
    require(peak_bytes<=29963128848ull,"planned card exceeds admitted packet58x device bound");
  }
}
static void record_host_memory(const fs::path& output,const char* phase) {
  {std::ifstream status("/proc/self/status");save(output/(std::string("host-status-")+phase+".txt"),std::string((std::istreambuf_iterator<char>(status)),{}));}
  {std::ofstream counters(output/(std::string("drm-memory-")+phase+".txt"));
   for(const auto& entry:fs::directory_iterator("/proc/self/fdinfo")){std::ifstream f(entry.path());std::string row;while(std::getline(f,row))if(row.starts_with("drm-"))counters<<row<<"\n";}}
  std::ifstream input("/proc/meminfo");std::string line;uint64_t available=0,active=0;bool has_active=false;
  while(std::getline(input,line)){std::istringstream row(line);std::string key;uint64_t kb=0;row>>key>>kb;
    if(key=="MemAvailable:")available=kb*1024;
    if(key=="GPUActive:"){active=kb*1024;has_active=true;}
  }
  std::ofstream out(output/"host-memory.jsonl",std::ios::app);
  out<<"{\"phase\":"<<ownrt::quote(phase)<<",\"MemAvailable\":"<<available<<",\"GPUActive\":"
     <<(has_active?std::to_string(active):"null")<<"}\n";out.flush();
}
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rank.hpp"

// SPEED6_SCRATCH_POLICY_BEGIN
// Scope the footprint reduction to the previously refused split23/dr1 arm.
// The reference interpreter advertises a 64M-float pool: never shrink it.
// Unknown writers fail closed, rather than silently using an understated ledger.
static size_t target_scratch_bytes(const flash::Plan& p,const Options& a) {
 constexpr size_t legacy=256ull*1024*1024, bounded=8ull*1024*1024;
 if(a.target_split!=23||a.draft_rank!=1||a.nongemv!="parallel"||
    (!a.mini&&a.context!=4096))return legacy;
 require((a.mini||p.g.h==2560)&&p.g.context==a.context&&
         p.g.context>0&&p.g.context<=32768&&p.g.budget>0&&p.g.budget<=2048,
         "unproved bounded scratch geometry");
 const size_t required=pipeline::SnapshotWriteSet::scratch(p,legacy,true);
 require(!p.launches.empty()&&required<=bounded,"unproved bounded scratch extent");
 // SPEED6 plan gate also checks this writer union against the kernels' full
 // scratch_floats read/write requirements. Binding-time extent guards stay on.
 return bounded;
}
// SPEED6_SCRATCH_POLICY_END

static int run_draft_capture(Options a) {
 a.rank=1;pipeline_stop_fd=a.stop_fd;std::unique_ptr<Weights> w;std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;std::string error,selection_observed_sha256;std::vector<std::string> teardown;
 try {w=std::make_unique<Weights>(a);auto p=pipeline::split(plan(*w,a),1,a.mini);e=std::make_unique<Engine>(*w,a,p);selection_observed_sha256=e->sealed_selection.observed_sha256;e->initialize();e->prepare_plan();draft=std::make_unique<mtp36::DraftRuntime>(*e);
  std::ifstream rows(a.draft_capture);require(bool(rows),"capture table missing");int pos,token,head;std::string path;std::ofstream out(a.output/"draft-capture.jsonl");
  while(rows>>pos>>token>>head>>path){std::ifstream f(path,std::ios::binary);std::vector<uint8_t> raw((std::istreambuf_iterator<char>(f)),{});require(raw.size()==4*p.g.h*2,"capture streams extent");e->put(0,"streams",raw.data(),raw.size());int result=draft->run(token,pos+1,head);out<<"{\"position\":"<<pos<<",\"token\":"<<result<<"}\n";out.flush();if(head)draft->dump(a.output/("row-"+std::to_string(pos)),true);}
  require(rows.eof(),"capture table malformed");draft->dump(a.output/"draft-final-state");
 }catch(const std::exception& ex){error=ex.what();save(a.output/"failure-before-teardown.json","{\"passed\":false,\"error\":"+ownrt::quote(error)+"}");}
 draft.reset();if(e){try{teardown=e->shutdown();}catch(const std::exception& ex){error+=ex.what();}e.reset();}
 std::ostringstream receipt;receipt<<"{\"passed\":"<<(error.empty()?"true":"false")<<",\"error\":"<<ownrt::quote(error)<<",\"device_executed\":"
#ifdef OWN_RT_HOST_ONLY
 <<"false"
#else
 <<"true"
#endif
 <<",\"selection_sha256\":"<<ownrt::quote(selection_observed_sha256)<<",\"teardown\":[";for(size_t i=0;i<teardown.size();++i)receipt<<(i?",":"")<<teardown[i];receipt<<"]}";save(a.output/"receipt.json",receipt.str());return error.empty()?0:1;
}

// Reset request state in place. Immutable experts, pointer tables and cache survive.
static void p58_reset_request(Engine& e,const fs::path& destination) {
  fs::create_directories(destination);record_host_memory(destination,"before_reset");
  e.drain();require(!e.poisoned && !e.integer(0,"error"),"reset cannot clear failure");
  require(!e.bank_parity,"plain target must use primary state bank");
  std::vector<uint8_t> zero(4*1024*1024,0);size_t bytes=0,allocations=0;
  for(const auto& [id,owner]:e.allocations) {
    const auto& row=e.dev(owner.first).arena.row(id);
    if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab)continue;
    for(size_t off=0;off<row.bytes;off+=zero.size())
      e.upload(owner.first,id,off,zero.data(),std::min(zero.size(),row.bytes-off));
    bytes+=row.bytes;++allocations;
  }
  float unit=1;e.upload(0,e.one[0],0,&unit,4);uint32_t active=1;e.put(0,"active",&active,4);
  if(e.buffers[0].count("token_history")) {
    int64_t history[2]={e.p.g.eos,e.p.g.eos};e.put(0,"token_history",history,sizeof history);
    e.put(0,"ple_metadata",e.metadata.data(),e.metadata.size()*8);
  }
  e.history0=e.history1=e.p.g.eos;e.lookup_ids.clear();
  for(auto& selected:e.selected)selected.clear();
  std::fill(e.fp32_sources.begin(),e.fp32_sources.end(),0);
  std::fill(e.fp32_extents.begin(),e.fp32_extents.end(),0);
  e.logical=0;e.drain();e.submission_card=-1;e.current_cls=0;e.host_waits=0;
  e.wait_ms=e.prepare_ms=e.enqueue_ms=e.enqueue_including_wait_ms=0;
  e.gemv_ms=e.nongemv_ms=e.transfer_ms=0;e.submitted=e.max_submission_ns=0;
  e.family_ms.fill(0);
  for(auto& v:e.class_ms)v=0;for(auto& v:e.class_launches)v=0;for(auto& v:e.class_groups)v=0;
  fs::create_directories(destination);e.a.output=destination;
  auto reopen=[&](std::ofstream& stream,const char* name) {
    stream.close();stream.clear();stream.open(destination/name);require(bool(stream),"reset log");
  };
  reopen(e.timings,"timings.jsonl");reopen(e.prefill_timings,"prefill-timings.jsonl");
  reopen(e.site_timings,"sites.jsonl");reopen(e.progress,"progress.jsonl");
  record_host_memory(destination,"after_reset");
  save(destination/"reset.json","{\"passed\":true,\"cached_tokens\":0,\"allocation_ids_preserved\":true,\"allocations\":"+
       std::to_string(allocations)+",\"bytes\":"+std::to_string(bytes)+"}\n");
}

#ifdef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/postload_allocation_test.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/fullshape_submit_test.hpp"
#endif

#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native/bracket_table.hpp"
int main(int argc, char **argv) {
  if(argc==2&&std::string(argv[1])=="--help"){std::cout<<"--argument-audit --audit-prepare-each --authorized-device-window --bracket-inputs --cache-bytes --cache-cap --cache-maintenance --canary --cancel-launch --card --cards --channel --checked --context --dispatch --draft-capture --draft-fault --draft-head --draft-manifest --draft-model --draft-mtp --draft-rank --experts --first-layer --gemv --hc --hc-geometry --host-path --identity --input --lookups --max-new --memory --mini --miss-path --model-dir --native-nice --nongemv --oracle --other-fusion --output --pipeline-canary --pipeline-mini --plan --priority-probe --prompt-tokens --rank --record --retain-steps --retirement --seconds --selection --selection-sha256 --shared --stage --stop-fd --suite-inputs --target-split --timing --tokens --wait-policy poll|spin (default:poll) --wait-seconds --p58r-parse-test --help\n";return 0;}
#ifdef OWN_RT_HOST_ONLY
  if(argc>2&&std::string(argv[1])=="--p58r-parse-test") {
    try {
      auto parsed=parse(argc-1,argv+1);auto views=bracket_table(parsed);
      require(views.size()==1||views.size()==5,"parser bracket coverage");
      require(!fs::exists(parsed.output),"fresh parser output required");fs::create_directories(parsed.output);
      save(parsed.output/"parser.json","{\"passed\":true,\"device_executed\":false,\"model_reads\":false,\"views\":"+std::to_string(views.size())+",\"wait_policy\":"+ownrt::quote(parsed.wait_policy)+",\"cache_allocation_bytes\":"+std::to_string(parsed.cache_bytes)+"}\n");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
  }
#endif

#ifdef OWN_RT_HOST_ONLY
  if(argc>=3 && argc<=6 && std::string(argv[1])=="--fullshape-submit-test") {
    try {return fullshape_submit_test(argv[2],argc>3?argv[3]:(fs::path(__FILE__).parent_path()/"selection.json").string(),argc>4?argv[4]:"KD",argc>5?argv[5]:"zero-copy");}
    catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
  }
  if(argc==3 && std::string(argv[1])=="--postload-allocation-test") {
    try {return postload_allocation_test(argv[2]);}
    catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
  }
#endif
  std::unique_ptr<Engine> e;
  std::unique_ptr<Weights> w;
  fs::path output;
  std::string error;
  std::vector<std::string> teardown;
  bool comparison = true, did_compare = false, compute_started = false;
  std::vector<int> generated;
  std::string text;
  uint64_t read_bytes = 0;
  size_t max_read = 0;
  Options a;
  double prefill_ms=0,first_token_ms=0,decode_ms=0;
  uint64_t max_submission_ns=0;
  std::string census = "[]",affinity_json="[]",residency_json="{}",selection_observed_sha256;
  double load_average=0;getloadavg(&load_average,1);
  {cpu_set_t cpus;CPU_ZERO(&cpus);if(sched_getaffinity(0,sizeof cpus,&cpus)==0){std::ostringstream o;o<<'[';bool comma=false;for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&cpus)){o<<(comma?",":"")<<i;comma=true;}o<<']';affinity_json=o.str();}}
  try {
    a = parse(argc, argv);
    require(!a.wait_policy_supplied||(a.draft_capture.empty()&&a.rank<0),"wait policy applies to single-owner request views");
    if(a.priority_probe){
#ifdef OWN_RT_HOST_ONLY
      require(!fs::exists(a.output), "priority output exists");fs::create_directories(a.output);
      save(a.output/"priority.json", "{\"passed\":true,\"device_executed\":false,\"requested_nice\":"+std::to_string(a.native_nice)+",\"actual_nice\":"+std::to_string(getpriority(PRIO_PROCESS,0))+"}\n");return 0;
#else
      throw std::invalid_argument("priority probe is host only");
#endif
    }
    if(!a.dispatch.empty())packet26::dispatch.load(a.dispatch);
    require(!fs::exists(a.output), "output already exists");
    output = a.output;
    fs::create_directories(output);
    std::signal(SIGTERM, stop);
    std::signal(SIGINT, stop);
    require(!a.canary,"use W0p two-rank concurrency canary");
    if(!a.draft_capture.empty())return run_draft_capture(a);
    if(a.rank>=0)return run_rank(a);
    const auto bracket_views=bracket_table(a);
    const auto cold_load_start=std::chrono::steady_clock::now();
    w = std::make_unique<Weights>(a);
    auto p = plan(*w, a);
    write_plan(output / "plan.json", p, *w, a.cards,a);
    if (a.record) {
      save(output / "record.json",
           "{\"device_executed\":false,\"passed\":true}\n");
      return 0;
    }
    std::map<std::string,std::vector<int>> expected_tokens;
    std::vector<std::pair<std::string,fs::path>> requests;
    if(!a.suite_inputs.empty()) {
      require(!a.mtp && a.rank<0 && a.cards==1,"suite requires plain single owner");
      std::ifstream f(a.suite_inputs);std::string id,path;std::set<std::string> ids;
      while(f>>id>>path) {
        require(!id.empty()&&id!="."&&id!=".."&&fs::path(id).filename()==id&&ids.insert(id).second,"suite id");
        require(fs::path(path).is_absolute(),"suite input path absolute");requests.push_back({id,path});
        if(!a.bracket_inputs.empty()) {
          std::string oracle_path;require(bool(f>>oracle_path)&&fs::path(oracle_path).is_absolute(),"bracket oracle path");
          std::ifstream oracle(oracle_path);int token;std::vector<int> tokens;
          while(oracle>>token){require(token>=0&&token<p.g.vocab,"oracle token range");tokens.push_back(token);}
          require(oracle.eof()&&!tokens.empty()&&tokens.size()<=size_t(a.tokens),"bounded oracle tokens");
          expected_tokens[id]=std::move(tokens);
        }
      }
      require(f.eof()&&!requests.empty()&&requests.size()<=12,"bounded suite inputs");
      require(a.bracket_inputs.empty()||a.mini||requests.size()==12,"twelve bracket prompts required");
    }else requests.push_back({"",a.inputs});
    const auto root_output=output;
    e = std::make_unique<Engine>(*w, a, p);
    selection_observed_sha256=e->sealed_selection.observed_sha256;
    record_host_memory(output,"before_load");
    e->initialize();
    // Keep a complete owner available for the normal drain-on-error proof.
    if(a.resident_lookups||!a.bracket_inputs.empty())w->load_resident_lookups();
    w->use_resident_lookups=a.resident_lookups;e->cache_capacity(a.cache_cap);
    e->dev(0).before_compute=[&]{compute_started=true;};
    e->prepare_plan();
    e->prepare_commands();
    residency_json=w->residency;
    record_host_memory(output,"after_load");
#ifndef OWN_RT_HOST_ONLY
    {std::ifstream f(output/"drm-memory-after_load.txt");std::string line;uint64_t peak=0;bool seen=false;
      while(std::getline(f,line))if(line.starts_with("drm-total-vram0:")){
        peak=std::max(peak,p58xd::drm_size(line.substr(line.find(':')+1)));seen=true;
      }
      require(seen&&peak<=30500000000ull,"device reserve violated before compute");
    }
#endif
    save(output/"cold-start.json","{\"load_and_pin_ms\":"+std::to_string(Engine::ms(cold_load_start))+
      ",\"initial_cache_fill_bytes\":0,\"initial_cache_policy\":\"empty-content-independent\",\"first_prompt_fills_charged_in_request\":true}\n");


    e->bracket_weights_locked=!a.bracket_inputs.empty();
    const auto loaded_arena=e->bracket_arena_hash(),loaded_weights=e->bracket_arena_hash(true);
    if(!a.bracket_inputs.empty())save(root_output/"loaded-arena-descriptors.txt",e->bracket_arena_descriptors());
    for(const auto& view:bracket_views) {
    w->use_resident_lookups=view.resident;
    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":view.hc=="spin";
    const auto view_output=view.label.empty()?root_output:root_output/view.label;
    if(!view.label.empty()) {
      fs::create_directories(view_output);record_host_memory(view_output,"before_view_reset");e->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");e->cache_mode(view.maintenance);e->cache_capacity(view.capacity);record_host_memory(view_output,"after_view_reset");
      require(loaded_arena==e->bracket_arena_hash()&&loaded_weights==e->bracket_arena_hash(true),"bracket loaded identity changed");
      save(view_output/"lookup-backing.json","{\"resident\":"+std::string(view.resident?"true":"false")+",\"copies\":"+w->residency+"}\n");
      save(view_output/"boundary.json","{\"passed\":true,\"selection_sha256\":"+ownrt::quote(view.digest)+
        ",\"cache_maintenance\":"+ownrt::quote(view.maintenance)+
        ",\"hc\":\"p60fusion\",\"lookups\":"+ownrt::quote(view.resident?"resident":"mapped")+",\"wait_policy\":"+ownrt::quote(view.hc)+
        ",\"cache_cap\":"+ownrt::quote(view.capacity)+",\"cache_allocation_bytes\":21552729600,\"cache_started_empty\":true"+
        ",\"arena_descriptors_sha256\":"+ownrt::quote(loaded_arena)+",\"weight_descriptors_sha256\":"+ownrt::quote(loaded_weights)+
        ",\"allocation_ids_preserved\":true,\"weight_uploads_during_switch\":0,\"cache_fill_bytes_total\":"+std::to_string(e->cache_fill_bytes)+
        ",\"context_extent\":32,\"model_loads\":1}\n");
    }
    for(const auto& [request_id,input_path]:requests) {
    output=request_id.empty()?view_output:view_output/request_id;
    auto monotonic=[](){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();};
    const double request_start_seconds=monotonic();
    p58_reset_request(*e,output);
    timespec owner_cpu_start{},owner_cpu_end{};clock_gettime(CLOCK_THREAD_CPUTIME_ID,&owner_cpu_start);auto owner_wall_start=std::chrono::steady_clock::now();
    e->request_diagnostics=output;e->request_token_index=0;e->last_site=nullptr;
    generated.clear();text.clear();
    std::vector<int> input;
    if(input_path.empty()){require(a.mini,"input required");input={2,5,3,7,1};}
    else {std::ifstream f(input_path);int id;while(f>>id){require(id>=0&&id<p.g.vocab,"token range");input.push_back(id);}
      require(f.eof()&&!input.empty(),"input token file");}
    require(input.size()+a.tokens<=size_t(p.g.context),"input/generation exceeds context");
    std::vector<double> generated_stamps;
    size_t token_index=0;
    double first_generated_ms=0;
    auto step = [&](int token, int fixture_step) {
      e->request_token_index=token_index;e->checkpoint(fixture_step==0?"prefill-start":"decode-start");
      e->admit_position(int(token_index));e->verify_configuration();
      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();
      struct rusage process_before{},thread_before{},process_after{},thread_after{};
      getrusage(RUSAGE_SELF,&process_before);getrusage(RUSAGE_THREAD,&thread_before);
      double token_g=e->gemv_ms,token_n=e->nongemv_ms,token_t=e->transfer_ms;
      auto token_sub=e->submitted,token_wait=e->host_waits;
      auto copy_before=ownrt::copy_audit(e->dev(0));
      bool capture=a.retain_steps.contains(fixture_step);
      fs::path fixture_dir=output/("step"+std::to_string(fixture_step));
      if(capture)fs::create_directories(fixture_dir);
      std::vector<std::pair<int,int>> captured;
      e->checkpoint("token-control-upload");
      for (int c=0;c<a.cards;++c)if(e->buffers[c].count("token"))e->put(c,"token",&token,4);
      double tok_wait=e->wait_ms;
      struct rusage prepare_before{},prepare_after{};
      getrusage(RUSAGE_SELF,&prepare_before);
      e->checkpoint("resident-lookup-prepare");
      {auto t0=std::chrono::steady_clock::now();e->prepare_token(token);e->prepare_ms=Engine::ms(t0);}
      getrusage(RUSAGE_SELF,&prepare_after);
      e->checkpoint(fixture_step==0?"prefill-enqueue":"decode-enqueue");
      auto enqueue_start=std::chrono::steady_clock::now();double enqueue_wait=e->wait_ms;
      e->guard();e->family_ms.fill(0);
      for(auto& l:e->p.launches) {
        const auto* ready=(a.memory=="resident"&&!a.legacy)?&e->issue_sites[size_t(&l-e->p.launches.data())]:nullptr;
        if(fixture_step==0 && (ready?ready->prefill_skip:(l.label.starts_with("final.") || l.label=="logits" || l.label=="argmax")))continue;
        e->enqueue(l,e->logical);
        if(ready?ready->layer_end:ends(l.label,".ffn.combine")) {
          int layer=ready?ready->layer:std::stoi(l.label.substr(4));
          if(capture) {
            ownrt::CopyEngine copy(e->dev(l.card));
            e->tail=copy.copy(e->snapshots[l.card],size_t(layer)*4*p.g.h*2,
              e->buffers[l.card].at("streams").id,0,4*p.g.h*2,{});
            captured.push_back({layer,l.card});
          }
          if(a.memory=="layer-streaming" && a.cards==1 && !a.first){e->release_layer(l.card);e->loaded_layer[l.card]=-1;}
        }
      }
      e->enqueue_including_wait_ms=Engine::ms(enqueue_start);
      e->enqueue_ms=e->enqueue_including_wait_ms-(e->wait_ms-enqueue_wait);
      e->cache_plan_during_position(); // previous routes, current kernels already enqueued
      // One token-boundary readback contains sticky error and greedy output.
      e->checkpoint(fixture_step==0?"prefill-compute-drain":"decode-compute-drain");
      e->drain(); // commit.final is Q1; readback is Q0
      auto& owner=e->dev(0);ownrt::CopyEngine copy(owner);
      auto start_transfer=std::chrono::steady_clock::now();
      e->tail=copy.copy(e->slab[0],0,e->buffers[0].at("error").id,0,4,{});
      e->tail=copy.copy(e->slab[0],4,e->buffers[0].at("next_token").id,0,4,{});
      e->drain();
      int status=0,result=-1;auto ptr=owner.arena.row(e->slab[0]).pointer;
      std::memcpy(&status,ptr,4);std::memcpy(&result,static_cast<char*>(ptr)+4,4);
      e->transfer_ms+=Engine::ms(start_transfer);
      require(!status,"sticky device error at token "+std::to_string(token_index)+"; rerun --checked for layer localization");
      e->cache_after_position();
      if(fixture_step>0)generated_stamps.push_back(monotonic());
      if(capture) {
        std::vector<std::vector<uint8_t>> raw(a.cards);
        for(int c=0;c<a.cards;++c)raw[c]=e->readback(c,e->snapshots[c],48*4*p.g.h*2);
        std::ofstream hashes(fixture_dir/"layers.jsonl");
        for(auto [layer,c]:captured){size_t size=4*p.g.h*2,off=size*layer;
          std::vector<uint8_t> b(raw[c].begin()+off,raw[c].begin()+off+size);
          char name[40];std::snprintf(name,sizeof name,"layer-%02d.bf16",layer);
          std::ofstream f(fixture_dir/name,std::ios::binary);f.write(reinterpret_cast<char*>(b.data()),b.size());
          hashes<<"{\"layer\":"<<layer<<",\"shape\":[1,4,"<<p.g.h<<"],\"dtype\":\"BF16 little-endian\",\"sha256\":"<<ownrt::quote(hash(b))<<"}\n";
          if(!a.oracle.empty()){
            auto oracle_path=a.oracle/("step"+std::to_string(fixture_step))/name;
            if(fixture_step==1 && fs::exists(a.oracle/name))oracle_path=a.oracle/name;
            std::ifstream oracle(oracle_path,std::ios::binary);require(bool(oracle),"oracle missing "+oracle_path.string());
            std::vector<uint8_t> expected((std::istreambuf_iterator<char>(oracle)),{});did_compare=true;
            if(b!=expected)comparison=false;
            require(b==expected,"first differing layer "+std::to_string(layer)+" step "+std::to_string(fixture_step));
          }
        }
      }
      if(capture)for(int c=0;c<a.cards;++c){std::vector<uint8_t> zero(48*4*p.g.h*2,0);e->upload(c,e->snapshots[c],0,zero.data(),zero.size());}
      if(a.memory=="layer-streaming" && a.cards==1 && !a.first)e->release_layer(0);
      getrusage(RUSAGE_SELF,&process_after);getrusage(RUSAGE_THREAD,&thread_after);
      auto elapsed=Engine::ms(token_start);
      if(fixture_step==1)first_generated_ms=elapsed;
      auto copies=ownrt::copy_audit(e->dev(0));
      auto& token_rows=(fixture_step>0?e->timings:e->prefill_timings);
      token_rows<<"{\"kind\":"<<ownrt::quote(fixture_step>0?"generated_token":"prefill_token")
        <<",\"token_index\":"<<token_index++<<",\"generated_index\":"<<fixture_step
        <<",\"input_token\":"<<token<<",\"token_id\":"<<result<<",\"wall_ms\":"<<elapsed
        <<",\"gemv_device_ms\":"<<device_ms(e->gemv_ms-token_g)<<",\"non_gemv_device_ms\":"<<device_ms(e->nongemv_ms-token_n)
        <<",\"transfer_wall_ms\":"<<e->transfer_ms-token_t<<",\"kernel_submissions\":"<<e->submitted-token_sub
        <<",\"host_waits\":"<<e->host_waits-token_wait<<",\"prepare_major_faults\":"<<prepare_after.ru_majflt-prepare_before.ru_majflt<<",\"prepare_minor_faults\":"<<prepare_after.ru_minflt-prepare_before.ru_minflt<<",\"resident_lookups\":"<<(w->use_resident_lookups?"true":"false")<<",\"prepare_ms\":"<<e->prepare_ms<<",\"enqueue_loop_ms\":"<<e->enqueue_ms<<",\"enqueue_including_wait_ms\":"<<e->enqueue_including_wait_ms<<",\"wait_ms\":"<<e->wait_ms-tok_wait<<",\"process_major_faults\":"<<process_after.ru_majflt-process_before.ru_majflt
        <<",\"process_minor_faults\":"<<process_after.ru_minflt-process_before.ru_minflt
        <<",\"thread_voluntary_context_switches\":"<<thread_after.ru_nvcsw-thread_before.ru_nvcsw
        <<",\"thread_involuntary_context_switches\":"<<thread_after.ru_nivcsw-thread_before.ru_nivcsw
        <<",\"enqueue_family_ms\":";
      if(a.timing!="class")token_rows<<"null";
      else {token_rows<<'{';for(size_t j=0;j<e->families.size();++j)token_rows<<(j?",":"")<<ownrt::quote(e->families[j])<<':'<<e->family_ms[j];token_rows<<'}';}
      token_rows<<",\"parameter_uploads_per_launch\":0,\"copy_counts\":[";
      for(int c=0;c<a.cards;++c)token_rows<<(c?",":"")<<"{\"card\":"<<c
        <<",\"host_to_device\":"<<copies.host_to_device[c]-copy_before.host_to_device[c]
        <<",\"device_to_host\":"<<copies.device_to_host[c]-copy_before.device_to_host[c]
        <<",\"peer\":"<<copies.peer[c]-copy_before.peer[c]
        <<",\"device_local\":"<<copies.device_local[c]-copy_before.device_local[c]<<"}";
      token_rows<<"]}\n";
      if(token_index==1)e->checkpoint("first-prefill-complete");
      e->timings.flush();e->prefill_timings.flush();return a.first?-1:result;
    };
    int next=-1;auto prefill_start=std::chrono::steady_clock::now();
    for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
    prefill_ms=Engine::ms(prefill_start);first_token_ms=first_generated_ms;
    for(auto& v:e->class_ms)v=0;for(auto& v:e->class_launches)v=0;for(auto& v:e->class_groups)v=0;
    auto decode_start=std::chrono::steady_clock::now();
    if(!a.first)for(int i=0;i<a.tokens;++i){
      if(!a.bracket_inputs.empty()) {
        const auto& expected=expected_tokens.at(request_id);
        require(generated.size()<expected.size()&&next==expected[generated.size()],"packet49 oracle token mismatch: "+view.label+"/"+request_id+" token "+std::to_string(generated.size()));
      }
      generated.push_back(next);
      std::cout<<"token_id "<<next<<'\n';
      if(next==p.g.eos || (!a.mini && next==248046))break;
      if(i+1<a.tokens)next=step(next,i+2);
    }
    require(a.bracket_inputs.empty()||generated==expected_tokens.at(request_id),"packet49 completion length mismatch");
    decode_ms=Engine::ms(decode_start);
    e->dump_classes(output/"class-times.json",generated.empty()?0:int(generated.size())-1);
    std::ostringstream rr;rr.precision(17);
    rr<<"{\"schema\":\"own-runtime.iq3.packet26.run.v1\",\"passed\":true,\"arithmetic\":"<<ownrt::quote(arithmetic::version)
      <<",\"cached_tokens\":0,\"gpu_count\":1,\"decode_mode\":\"plain\",\"context\":"<<a.context
      <<",\"request_start_monotonic\":"<<request_start_seconds<<",\"request_end_monotonic\":"<<monotonic()
      <<",\"prompt_tokens\":"<<input.size()<<",\"requested_max_new\":"<<a.tokens
      <<",\"prefill_ms\":"<<prefill_ms<<",\"first_generated_token_ms\":"<<first_token_ms
      <<",\"tokens\":[";
    for(size_t i=0;i<generated.size();++i)rr<<(i?",":"")<<generated[i];
    rr<<"],\"timing_rows\":[";
    for(size_t i=0;i<generated_stamps.size();++i)rr<<(i?",":"")<<"{\"completed_monotonic\":"<<generated_stamps[i]<<"}";
    rr<<"]}";save(output/"result.json",rr.str());
    if(!request_id.empty())save(output/"receipt.json",rr.str());
    save(output/"lookup-request-complete.json","{\"passed\":true}\n");
    clock_gettime(CLOCK_THREAD_CPUTIME_ID,&owner_cpu_end);
    const double cpu_seconds=owner_cpu_end.tv_sec-owner_cpu_start.tv_sec+(owner_cpu_end.tv_nsec-owner_cpu_start.tv_nsec)*1e-9;
    const double wall_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-owner_wall_start).count();
    save(output/"owner-cpu.json","{\"cpu_seconds\":"+std::to_string(cpu_seconds)+",\"wall_seconds\":"+std::to_string(wall_seconds)+",\"one_core_percent\":"+std::to_string(100*cpu_seconds/wall_seconds)+"}\n");
    }
    } // bracket views; weights and owner stay resident
    output=root_output;
    std::ostringstream c;
    c << '[';
    for (size_t i = 0; i < e->devices.size(); ++i)
      c << (i ? "," : "") << e->dev(i).arena.census();
    c << ']';
    census = c.str();
    save(output / "census.json", census);
    save(output / "memory.json", "{\"peak_device_bytes_per_owner\":"+std::to_string(e->peak_device_bytes)+
      ",\"pinned_bytes_per_owner\":"+std::to_string(e->dev(0).arena.total(Memory::pinned))+",\"mode\":"+ownrt::quote(a.memory)+"}\n");
    read_bytes = w->read_bytes;
    max_read = w->max_read;
    max_submission_ns=e->max_submission_ns;
    teardown = e->shutdown();
    e.reset();
    w.reset();
  } catch (const std::exception &ex) {
    if(!a.bracket_inputs.empty()&&!a.output.empty())output=a.output;
    error = ex.what();
    if (w) {
      read_bytes = w->read_bytes;
      max_read = w->max_read;
    }
    std::cerr << error << '\n';
    if(!output.empty() && fs::is_directory(output)) {save(output/"failure.txt",error+"\n");save(output/"receipt.json","{\"passed\":false,\"error\":"+ownrt::quote(error)+",\"teardown_pending\":true}\n");}
    if (e) {
      e->poisoned = true;
      try {teardown=e->shutdown();}catch(const std::exception& close_error) {error+="; ";error+=close_error.what();}
      e.reset();
    }
  }
  if (output.empty() || !fs::is_directory(output))
    return 1;
  record_host_memory(output,"end");
  std::ostringstream r;
  r << "{\"schema\":\"own-runtime.iq3.packet26.run.v1\",\"passed\":"
    << (error.empty() && comparison ? "true" : "false")
    << ",\"error\":" << ownrt::quote(error) << ",\"mode\":"
    << ownrt::quote(a.mini    ? "mini"
                    : a.first ? "first-layer"
                              : "full-model")
    << ",\"arithmetic\":" << ownrt::quote(arithmetic::version)
    << ",\"memory_mode\":" << ownrt::quote(a.memory)
    << ",\"real_model_qualified\":false,\"device_executed\":";
#ifdef OWN_RT_HOST_ONLY
  r << "false";
#else
  r << "true";
#endif
  r << ",\"compute_started\":"<<(compute_started?"true":"false");
  r << ",\"safe_to_exit\":true,\"cpu_affinity\":"<<affinity_json<<",\"load_average_1m\":"<<load_average<<",\"lookup_residency\":"<<residency_json<<",\"host_path\":"<<ownrt::quote(a.memory=="resident"&&!a.legacy?"prepared":"legacy-streaming-or-explicit");
  r << ",\"selection_sha256\":"<<ownrt::quote(selection_observed_sha256);
  r << ",\"native_nice\":"<<a.native_nice<<",\"observed_nice\":"<<getpriority(PRIO_PROCESS,0);
  r << ",\"owner_cards\":"<<a.cards<<",\"nongemv\":"<<ownrt::quote(a.nongemv)<<",\"gemv\":"<<ownrt::quote(a.gemv)
    <<",\"timing\":"<<ownrt::quote(a.timing)<<",\"profiling\":"<<(a.timing!="token"?"true":"false")<<",\"context\":"<<a.context<<",\"prefill_ms\":"<<prefill_ms<<",\"first_generated_token_ms\":"<<first_token_ms
    <<",\"decode_wall_ms\":"<<decode_ms<<",\"decode_tokens\":"<<(generated.empty()?0:generated.size()-1)
    <<",\"decode_tok_s\":"<<(generated.size()>1 && decode_ms>0 ? std::to_string((generated.size()-1)*1000./decode_ms):"null");
  r << ",\"submission_budget_ns\":4000000000,\"submission_budget_measured\":"<<(a.timing!="token"?"true":"false")<<",\"max_submission_ns\":"<<max_submission_ns;
  r << ",\"oracle_compared\":" << (did_compare ? "true" : "false")
    << ",\"oracle_exact\":"
    << (!did_compare ? "null"
        : comparison ? "true"
                     : "false")
    << ",\"model_payload_bytes_read\":" << read_bytes
    << ",\"max_read_bytes\":" << max_read << ",\"tokens\":[";
  for (size_t i = 0; i < generated.size(); ++i)
    r << (i ? "," : "") << generated[i];
  r << "],\"teardown\":[";
  for (size_t i = 0; i < teardown.size(); ++i)
    r << (i ? "," : "") << teardown[i];
  r << "]}\n";
  save(output / "receipt.json", r.str());
  return error.empty() && comparison ? 0 : 1;
}
