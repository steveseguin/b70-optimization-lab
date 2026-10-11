#include "../packet2/loader/gguf.hpp"
#include "synthetic.hpp"
#include "../packet3/step/plan.hpp"
#include "performance.hpp"
#include "adapter.hpp"
#include "dispatch.hpp"
#include "p25_bridge.hpp"
#include <unordered_map>
#ifndef OWN_RT_HOST_ONLY
#include "backend.hpp"
#endif
#ifdef OWN_RT_HOST_ONLY
#include "lifetime_mock.hpp"
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
  ownrt::Event compute(const ownrt::Operation &o, std::span<void *const> p,
                       std::span<const ownrt::Event> d) override {
    dynamic_cast<const HostOperation &>(o).run(p);
    return marker(d);
  }
};
#endif
struct Options {
  bool canary = false, mini = false, first = false, record = false, authorized = false, checked = false;
  std::string nongemv = "parallel", gemv = "frozen", stage = "first-token", timing="token";
  fs::path dispatch;
  int wait_seconds=60;
  int cards = 1, card = 3, tokens = 8, context = 128, seconds = 10800;
  std::string memory = "layer-streaming";
  fs::path inputs, output, model, plan, auth, oracle;
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
    if (k == "--canary") a.canary = true;
    else if (k == "--timing") a.timing=value();
    else if (k == "--dispatch") a.dispatch=value();
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
  require(a.cards >= 1 && a.cards <= 2 && a.card >= 0 && a.card + a.cards <= 4,
          "card range");
  require(a.tokens > 0 && a.tokens <= 64 && a.context >= 8 &&
              a.context <= 1024 && a.seconds > 0 && a.seconds <= 10800,
          "bounded generation/context/deadline");
  require(a.timing=="token" || a.timing=="launch" || a.timing=="class","timing mode");
  require(a.wait_seconds>0 && a.wait_seconds<=600,"bounded wait deadline");
  require(a.nongemv=="core" || a.nongemv=="parallel", "nongemv mode");
  require(a.gemv=="frozen" || a.gemv=="r5", "gemv mode");
  require(a.stage=="first-token" || a.stage=="decode", "stage");
  require(!a.output.empty(), "--output required");
  require((a.cards == 1 && a.memory == "layer-streaming") ||
          (a.cards == 2 && a.memory == "resident"), "memory mode/card count mismatch");
#ifdef OWN_RT_HOST_ONLY
  require(!a.authorized, "host binary cannot authorize device execution");
  // CPU full-model execution is an explicit packet18 gate.
#else
  require(a.authorized || a.record, "--authorized-device-window required");
#endif
  require(getpriority(PRIO_PROCESS, 0) == 19, "nice 19 required");
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
  g.context = a.mini ? 8 : a.context;
  auto p = a.first  ? flash::Builder(g, a.mini ? nullptr : &w.directory)
                          .build({false}, true)
           : a.mini ? flash::Builder(g).build({false, true})
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
      if(packet26::dispatch.fusion_for(fusion_class+"+norm") && next.op=="norm" && next.card==l.card && next.inputs==l.outputs) {
        l.outputs.insert(l.outputs.end(),next.outputs.begin(),next.outputs.end());
        l.weights=next.weights;l.parameter=next.parameter;++i;
      }
    }
    specialised.push_back(std::move(l));
  }
  p.launches=std::move(specialised);
  return p;
}
static unsigned selected_variant(const Weights& w,const Options& a,const flash::Plan& p,const flash::Launch& l,size_t projection=0) {
    const auto& t=w.directory.at(l.weights[projection]);
    auto choice=packet26::dispatch.gemv_for(l.label);
    if(choice.empty())choice=a.gemv;
    if(choice.starts_with("p25."))choice="r5"; // packed/expanded storage identity is unchanged
    if(choice=="r5")return arithmetic::r5_variant(flash::grid_type(t.grid),l.shape[1],l.shape[2],l.op=="gemv"?1:p.g.experts,a.mini);
    if(choice=="frozen" || choice=="packet18")return arithmetic::variant(flash::grid_type(t.grid),l.shape[1],l.shape[2],l.op=="gemv"?1:p.g.experts,a.mini);
    for(unsigned v=0;v<8;++v)if(choice==arithmetic::name(v)) {
      require(l.op=="gemv" || v==2,"expert dispatch requires registered expert kernel");
      require(!arithmetic::is_expanded(v) || iq3::expanded::quantized(flash::grid_type(t.grid)),"expanded kernel requires quantized weights");
      return v;
    }
    throw std::invalid_argument("GEMV candidate is not linked: "+choice);
}
struct Slot {
  Allocation id;
  size_t n;
  Scalar type;
};
class Engine final : public flash::Backend {
public:
  Weights &w;
  const Options &a;
  flash::Plan p;
  std::vector<std::unique_ptr<ownrt::Device>> devices;
#ifndef OWN_RT_HOST_ONLY
  std::shared_ptr<tp2::Context> peer_context;
#endif
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
    if(a.timing!="class")return;
    std::ofstream o(path);o<<"{\"profiling\":true,\"timing_definition\":\"sum of individual GPU event execution durations\",\"tokens\":"<<tokens<<",\"classes\":[";
    for(size_t i=0;i<class_names.size();++i)o<<(i?",":"")<<"{\"class\":"<<ownrt::quote(class_names[i])<<",\"device_ms\":"<<class_ms[i]<<",\"launches\":"<<class_launches[i]<<",\"groups\":"<<class_groups[i]<<"}";
    o<<"]}\n";
  }
  struct Prepared { Spec spec; std::vector<Allocation> bindings; };
  std::unordered_map<const flash::Launch*,Prepared> prepared;
  std::unordered_map<const flash::Launch*,std::vector<Matrix>> matrices;
  std::unordered_map<const flash::Launch*,std::pair<std::string,std::array<unsigned,2>>> gemv_choices;

  std::vector<Pending> pending;
  ownrt::Event tail=0;
  int submission_card=-1;
  uint64_t host_waits=0;
  int64_t history0=0,history1=0;
  std::vector<int64_t> metadata;

  std::vector<std::map<std::string, Slot>> buffers;
  std::vector<std::map<std::string, Allocation>> weights;
  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;
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
    if(a.timing!="token")pending.push_back({l,gemv,current_cls}); tail=l.last; submitted+=l.passes;
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
      if(a.timing=="class") {class_ms[item.cls]+=duration;class_launches[item.cls]+=item.launch.passes;++class_groups[item.cls];}
    }
#endif
    pending.clear();tail=0;
    if(!devices.empty())dev(0).retire_completed_events();
  }

  std::ofstream progress;
  flash::Event logical = 0;
  bool poisoned = false;
  std::chrono::steady_clock::time_point deadline;
  Engine(Weights &source, const Options &args, flash::Plan q)
      : w(source), a(args), p(std::move(q)),
        timings(a.output / "timings.jsonl"), prefill_timings(a.output/"prefill-timings.jsonl"), site_timings(a.output/"sites.jsonl"), progress(a.output / "progress.jsonl"),
        deadline(std::chrono::steady_clock::now() +
                 std::chrono::seconds(a.seconds)) {pending.reserve(4096);prepared.reserve(p.launches.size());matrices.reserve(p.launches.size());gemv_choices.reserve(p.launches.size());
    for(const auto& l:p.launches)if(l.op=="gemv"||l.op=="expert_gate_up"||l.op=="routed_gemv"){
      std::array<unsigned,2> variants{selected_variant(w,a,p,l),0};if(l.op=="expert_gate_up")variants[1]=selected_variant(w,a,p,l,1);
      gemv_choices.emplace(&l,std::make_pair(packet26::dispatch.gemv_for(l.label),variants));
    }
  }
  void guard() {
    require(!poisoned, "poisoned step");
    require(!stopped, "cooperative stop");
    require(std::chrono::steady_clock::now() < deadline,
            "cooperative deadline");
  }
  ownrt::Device &dev(int c) {
#ifndef OWN_RT_HOST_ONLY
    if(peer_context)peer_context->allocation_card=c;
#else
    (void)c;
#endif
    return *devices.at(0);
  }
  void wait(int c, ownrt::Event e) {
    ++host_waits;auto t0=std::chrono::steady_clock::now();
    require(dev(c).wait(e, std::chrono::seconds(a.wait_seconds)),
            "operation drain timeout; retain owner");
    wait_ms+=ms(t0);
  }
  Allocation allocate(int c, std::string name, size_t bytes, Category cat,
                      Lifetime life, Memory m = Memory::device) {
    if (m == Memory::device)
      require(owned_bytes.at(c) + bytes <= 30ull * 1024 * 1024 * 1024,
              "30 GiB per-card arena admission");
    auto id=dev(c).arena.allocate("card"+std::to_string(c)+":"+name, bytes, m, cat, life);
    if(m==Memory::device){owned_bytes[c]+=bytes; allocations[id]={c,bytes};}
    peak_device_bytes=std::max(peak_device_bytes,owned_bytes[c]);
    return id;
  }
  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {
    drain();
    auto started=std::chrono::steady_clock::now();
    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {
      guard();
      size_t k = std::min(n - i, size_t(4 * 1024 * 1024));
      std::memcpy(dev(c).arena.row(slab[c]).pointer,
                  static_cast<const uint8_t *>(src) + i, k);
      ownrt::CopyEngine copy(dev(c));
      wait(c, copy.copy(dst, offset + i, slab[c], 0, k, {}));
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
      wait(c, copy.copy(slab[c], 0, src, i, k, {}));
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
  void load(int c, const std::string &name) {
    if (weights[c].count(name))
      return;
    auto &t = w.directory.at(name);
    require(t.component != "embedding" && t.component != "ple_lookup",
            "lookup must be bounded rows");
    unsigned v=weight_variant(name);
    auto type=flash::grid_type(t.grid);
    size_t expanded_bytes=arithmetic::is_expanded(v)?size_t(t.shape[0])*arithmetic::row_bytes(type,t.shape[1],v):t.bytes;
    auto id = allocate(c, "weight:" + name, expanded_bytes, Category::weights,
                       Lifetime::process);
    weights[c][name] = id;
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
  void initialize() {
    owned_bytes.resize(a.cards);
#ifdef OWN_RT_HOST_ONLY
    devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
    if(a.cards==2) {
      peer_context=std::make_shared<tp2::Context>(a.card,a.card+1,a.timing!="token");
      // Device owns a forwarding backend; shared context outlives shutdown.
      struct Forward final:ownrt::Backend {
        std::shared_ptr<tp2::Context> p;
        explicit Forward(std::shared_ptr<tp2::Context> x):p(std::move(x)){}
        std::string identity()const override{return p->identity();}
        void* allocate(size_t n,Memory m)override{return p->allocate(n,m);}
        void release(void* x,Memory m)override{p->release(x,m);}
        ownrt::Event copy(void*d,const void*s,size_t n,std::span<const ownrt::Event> e)override{return p->copy(d,s,n,e);}
        ownrt::Event compute(const ownrt::Operation&o,std::span<void*const>b,std::span<const ownrt::Event>e)override{return p->compute(o,b,e);}
        ownrt::Event marker(std::span<const ownrt::Event> e)override{return p->marker(e);}
        bool complete(ownrt::Event e)override{return p->complete(e);}
        bool wait(ownrt::Event e,ownrt::Deadline t)override{return p->wait(e,t);}
        ownrt::EventTiming timing(ownrt::Event e)override{return p->timing(e);}
        void synchronize()override{p->synchronize();}
        void clear_events()override{p->clear_events();}
        void close_queue()override{p->close_queue();}
        void close_context()override{p->close_context();}
      };
      devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Forward>(peer_context)));
    } else devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card,a.timing!="token")));
#endif
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
      workspace.push_back(allocate(c,"gemv-workspace",4*1024*1024,Category::scratch,Lifetime::transaction));
      compact_routes.push_back(allocate(c,"compact-routes",p.g.top*sizeof(iq3::Route),Category::scratch,Lifetime::transaction));
      mixture_out.push_back(allocate(c,"ordered-mixture",p.g.h*2,Category::scratch,Lifetime::transaction));
      one.push_back(allocate(c,"mixture-one",4,Category::scratch,Lifetime::transaction));
      slab.push_back(allocate(c, "bounded-copy", 4 * 1024 * 1024,
                              Category::pinned_slab, Lifetime::transfer,
                              Memory::pinned));
      ropes.push_back(allocate(c,"rope-v2",rope_constants::bytes,Category::weights,Lifetime::process));
      upload(c,ropes[c],0,rope_bytes.data(),rope_bytes.size());
      scratch.push_back(allocate(c, "operator-scratch", 256ull * 1024 * 1024,
                                 Category::scratch, Lifetime::transaction));
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
    if (a.cards == 2) {
      for (auto &l : p.launches)
        if (l.op != "lookup")
          for (auto &name : l.weights)
            load(l.card, name);
    }
  }
  void prepare_plan() {
    if(a.cards!=2)return;
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
    if(a.cards!=1 || loaded_layer[c]==layer)return;
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
    if(routed && a.cards==1)load_selected(c,t.name);else load(c,t.name);
    Matrix m{};m.type=flash::grid_type(t.grid);m.w=weights[c].at(t.name);
    m.x=buffers[c].at(l.inputs[0]).id;m.y=buffers[c].at(l.outputs[projection*2]).id;
    m.rows=l.shape[1];m.columns=l.shape[2];m.span=m.rows;
    m.workspace=workspace[c];
    if(routed) {
      m.count=p.g.top;m.experts=a.cards==1?p.g.top:p.g.experts;
      m.status=buffers[c].at(l.outputs[projection*2+1]).id;
      if(a.cards==1) {
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
    auto it=matrices.find(&l);
    if(a.cards==2 && it==matrices.end()) {
      std::vector<Matrix> values{matrix(l)};
      if(l.op=="expert_gate_up")values.push_back(matrix(l,1));
      it=matrices.emplace(&l,std::move(values)).first;
    }
    auto m=a.cards==2?it->second[0]:matrix(l);
    const auto& candidate=gemv_choices.at(&l).first;
    if(candidate.starts_with("p25.")){
      std::vector<Matrix> selected{m};if(l.op=="expert_gate_up")selected.push_back(a.cards==2?it->second[1]:matrix(l,1));
      finish(c,packet26::p25bridge::submit(dev(c),selected,candidate,l.op=="expert_gate_up",variant(l)),true);return;
    }
    if(l.op=="gemv")finish(c,dense(dev(c),m,variant(l)),true);
    else if(l.op=="expert_gate_up") {
      auto up=a.cards==2?it->second[1]:matrix(l,1);finish(c,experts(dev(c),{m,up},true),true);
    } else finish(c,experts(dev(c),{m},false),true);
  }
  Prepared prepare_site(const flash::Launch& l) {int c=l.card;
      Spec s;
      s.g = p.g;
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
      s.implementation=packet26::dispatch.new_for(l.label,s.op)?1:0;
      s.fused_combine_norm=l.op=="hc_combine" && l.outputs.size()==2;
      if(s.fused_combine_norm || (l.op=="route" && l.outputs.size()==4))s.implementation=1;
      return {s,std::move(bindings)};
  }
  flash::Event enqueue(const flash::Launch &l, flash::Event dep) override {
    guard();
    require(dep == logical, "step event order");
    int c = l.card;
    if(submission_card!=c)drain(); // both queues drained and events retired on host
    if(a.timing=="class")set_class(l.label);
    submission_card=c;
    if(l.label.starts_with("blk."))stage_layer(c,std::stoi(l.label.substr(4)));
    auto site_start=std::chrono::steady_clock::now();
    double old_g=gemv_ms,old_n=nongemv_ms,old_t=transfer_ms;
    uint64_t old_submitted=submitted;
    if (l.op == "lookup") { /* Prepared once at token boundary from known input/history. */ }
    else if (l.op == "handoff" || l.op == "handoff_result") {
      for (auto &name : l.outputs) {
        drain(); // every peer copy starts with both owners drained
        auto source=buffers[l.source_card].at(name), dest=buffers[c].at(name);
        ownrt::CopyEngine copy(dev(c));
        tail=copy.copy(dest.id,0,source.id,0,source.n*flash::scalar_bytes(source.type),{});
      }
    } else if (l.op == "gemv" || l.op == "routed_gemv" || l.op=="expert_gate_up") {
      linear(l);
    } else {
      if(l.op=="moe_combine")finish(c,mixture(dev(c),buffers[c].at(l.inputs[0]).id,
          buffers[c].at(l.inputs[1]).id,mixture_out[c],p.g.h),false);
      Prepared temporary;
      const Prepared* bound=nullptr;
      if(a.cards==2)bound=&prepared.at(&l);
      else {temporary=prepare_site(l);bound=&temporary;}
      const auto& s=bound->spec;const auto& bindings=bound->bindings;
      if(a.nongemv=="parallel")finish(c,packet18::submit_parallel(dev(c),s,bindings,controls[c],scores[c],probabilities[c],{}),false);
      else finish(c, iq3::step_operator(dev(c), s, bindings));
      if(l.op=="route" && a.cards==1) {
        std::vector<std::string> evict;
        for(const auto& [name,id]:weights[c])if(name.find("_exps.weight")!=std::string::npos)evict.push_back(name);
        drain();
        for(const auto& name:evict){release(c,weights[c].at(name));weights[c].erase(name);}
        auto ids=readback(c,buffers[c].at(l.outputs[0]).id,p.g.top*4);
        selected[c].resize(p.g.top);std::memcpy(selected[c].data(),ids.data(),ids.size());
      }
    }
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
      stored[n]=arithmetic::is_expanded(v)?size_t(t.shape[0])*arithmetic::row_bytes(flash::grid_type(t.grid),t.shape[1],v):t.bytes;
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
  o << "],\"expert_placement\":\"all experts belong to their layer owner; none "
       "pruned\",\"one_card_full_model\":\"stream one layer at a "
       "time\",\"capture\":false,\"memory_plan\":{";
  size_t extra=rope_constants::bytes+256ull*1024*1024+4*1024*1024+p.g.top*sizeof(iq3::Route)+p.g.h*2+4+12+2*24*(p.g.budget+3)*4+48*4*p.g.h*2;
  std::vector<size_t> base(cards,extra),resident(cards,0);
  for(const auto& b:p.buffers)for(int c=0;c<cards;++c)
    if(b.card==-1 || b.card==c)base[c]+=count(b.shape)*flash::scalar_bytes(b.type);
  std::map<int,size_t> layer;
  for(const auto& [n,c]:owner) {
    const auto& t=w.directory.at(n);
    if(t.component=="embedding" || t.component=="ple_lookup")continue;
    resident[c]+=stored.at(n);
    int number=n.starts_with("blk.")?std::stoi(n.substr(4)):-1;
    layer[number]+=t.shape.size()==3?t.bytes/p.g.experts*p.g.top:stored.at(n);
  }
  size_t peak=0;for(auto [n,bytes]:layer)peak=std::max(peak,bytes);
  o << "\"request_and_workspace_bytes_per_card\":[";
  for(int c=0;c<cards;++c)o<<(c?",":"")<<base[c];
  o << "],\"resident_weights_per_card\":[";
  for(int c=0;c<cards;++c)o<<(c?",":"")<<resident[c];
  o << "],\"streamed_peak_weight_bytes\":" << peak
    << ",\"pinned_bytes_per_card\":4194304,\"read_chunk_bytes\":4194304"
       ",\"driver_shadows_included\":false}}";
  save(path, o.str());
  for(int c=0;c<cards;++c){auto peak_bytes=base[c]+(cards==2?resident[c]:peak);
    std::cout<<"card "<<c<<" owned_bytes "<<peak_bytes<<" weights "<<(cards==2?resident[c]:peak)<<" dispatch "<<a.gemv<<'\n';
    require(peak_bytes<=30ull*1024*1024*1024,"planned card exceeds 30 GiB");
  }
}
static void record_host_memory(const fs::path& output,const char* phase) {
  std::ifstream input("/proc/meminfo");std::string line;uint64_t available=0,active=0;bool has_active=false;
  while(std::getline(input,line)){std::istringstream row(line);std::string key;uint64_t kb=0;row>>key>>kb;
    if(key=="MemAvailable:")available=kb*1024;
    if(key=="GPUActive:"){active=kb*1024;has_active=true;}
  }
  std::ofstream out(output/"host-memory.jsonl",std::ios::app);
  out<<"{\"phase\":"<<ownrt::quote(phase)<<",\"MemAvailable\":"<<available<<",\"GPUActive\":"
     <<(has_active?std::to_string(active):"null")<<"}\n";out.flush();
}

#include "canary.hpp"
int main(int argc, char **argv) {
  std::unique_ptr<Engine> e;
  std::unique_ptr<Weights> w;
  fs::path output;
  std::string error;
  std::vector<std::string> teardown;
  bool comparison = true, did_compare = false;
  std::vector<int> generated;
  std::string text;
  uint64_t read_bytes = 0;
  size_t max_read = 0;
  Options a;
  double prefill_ms=0,first_token_ms=0,decode_ms=0;
  uint64_t max_submission_ns=0;
  std::string census = "[]";
  try {
    a = parse(argc, argv);
    if(!a.dispatch.empty())packet26::dispatch.load(a.dispatch);
    require(!fs::exists(a.output), "output already exists");
    output = a.output;
    fs::create_directories(output);
    std::signal(SIGTERM, stop);
    std::signal(SIGINT, stop);
    if(a.canary)return run_canary(a);
    w = std::make_unique<Weights>(a);
    auto p = plan(*w, a);
    write_plan(output / "plan.json", p, *w, a.cards,a);
    if (a.record) {
      save(output / "record.json",
           "{\"device_executed\":false,\"passed\":true}\n");
      return 0;
    }
    std::vector<int> input;
    if (a.inputs.empty()) {
      require(a.mini, "--input required for real weights");
      input = {2, 5, 3, 7, 1};
    } else {
      std::ifstream f(a.inputs);
      int id;
      while (f >> id) {
        require(id >= 0 && id < p.g.vocab, "token range");
        input.push_back(id);
      }
      require(f.eof() && !input.empty(), "input token file");
    }
    require(input.size() + a.tokens - 1 <= size_t(p.g.context),
            "input/generation exceeds context");
    std::vector<std::string> vocab;
    if (!a.mini) {
      std::ifstream f(a.inputs.parent_path() / "vocab.bin", std::ios::binary);
      require(bool(f), "token helper vocab.bin required");
      for (int i = 0; i < p.g.vocab; ++i) {
        uint32_t n = 0;
        f.read(reinterpret_cast<char *>(&n), 4);
        require(n < 1024 * 1024, "vocabulary token bound");
        std::string v(n, '\0');
        f.read(v.data(), n);
        require(bool(f), "vocabulary truncated");
        vocab.push_back(v);
      }
    }
    e = std::make_unique<Engine>(*w, a, p);
    record_host_memory(output,"before_load");
    e->initialize();
    e->prepare_plan();
    record_host_memory(output,"after_load");
    fs::create_directory(output / "step1");

    size_t token_index=0;
    double first_generated_ms=0;
    auto step = [&](int token, int fixture_step) {
      auto token_start=std::chrono::steady_clock::now();
      double token_g=e->gemv_ms,token_n=e->nongemv_ms,token_t=e->transfer_ms;
      auto token_sub=e->submitted,token_wait=e->host_waits;
      auto copy_before=ownrt::copy_audit(e->dev(0));
      bool capture=fixture_step>0 && fixture_step<=8;
      fs::path fixture_dir=output/("step"+std::to_string(fixture_step));
      if(capture)fs::create_directories(fixture_dir);
      std::vector<std::pair<int,int>> captured;
      for (int c=0;c<a.cards;++c)if(e->buffers[c].count("token"))e->put(c,"token",&token,4);
      double tok_wait=e->wait_ms;
      {auto t0=std::chrono::steady_clock::now();e->prepare_token(token);e->prepare_ms=Engine::ms(t0);}
      auto enqueue_start=std::chrono::steady_clock::now();double enqueue_wait=e->wait_ms;
      for(auto& l:e->p.launches) {
        if(fixture_step==0 && (l.label.starts_with("final.") || l.label=="logits" || l.label=="argmax"))continue;
        e->enqueue(l,e->logical);
        if(ends(l.label,".ffn.combine")) {
          int layer=std::stoi(l.label.substr(4));
          if(capture) {
            ownrt::CopyEngine copy(e->dev(l.card));
            e->tail=copy.copy(e->snapshots[l.card],size_t(layer)*4*p.g.h*2,
              e->buffers[l.card].at("streams").id,0,4*p.g.h*2,{});
            captured.push_back({layer,l.card});
          }
          if(a.cards==1 && !a.first){e->release_layer(l.card);e->loaded_layer[l.card]=-1;}
        }
      }
      e->enqueue_including_wait_ms=Engine::ms(enqueue_start);
      e->enqueue_ms=e->enqueue_including_wait_ms-(e->wait_ms-enqueue_wait);
      // One token-boundary readback contains sticky error and greedy output.
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
      if(a.cards==1 && !a.first)e->release_layer(0);
      auto elapsed=Engine::ms(token_start);
      if(fixture_step==1)first_generated_ms=elapsed;
      auto copies=ownrt::copy_audit(e->dev(0));
      auto& token_rows=(fixture_step>0?e->timings:e->prefill_timings);
      token_rows<<"{\"kind\":"<<ownrt::quote(fixture_step>0?"generated_token":"prefill_token")
        <<",\"token_index\":"<<token_index++<<",\"generated_index\":"<<fixture_step
        <<",\"input_token\":"<<token<<",\"token_id\":"<<result<<",\"wall_ms\":"<<elapsed
        <<",\"gemv_device_ms\":"<<device_ms(e->gemv_ms-token_g)<<",\"non_gemv_device_ms\":"<<device_ms(e->nongemv_ms-token_n)
        <<",\"transfer_wall_ms\":"<<e->transfer_ms-token_t<<",\"kernel_submissions\":"<<e->submitted-token_sub
        <<",\"host_waits\":"<<e->host_waits-token_wait<<",\"prepare_ms\":"<<e->prepare_ms<<",\"enqueue_loop_ms\":"<<e->enqueue_ms<<",\"enqueue_including_wait_ms\":"<<e->enqueue_including_wait_ms<<",\"wait_ms\":"<<e->wait_ms-tok_wait<<",\"parameter_uploads_per_launch\":0,\"copy_counts\":[";
      for(int c=0;c<a.cards;++c)token_rows<<(c?",":"")<<"{\"card\":"<<c
        <<",\"host_to_device\":"<<copies.host_to_device[c]-copy_before.host_to_device[c]
        <<",\"device_to_host\":"<<copies.device_to_host[c]-copy_before.device_to_host[c]
        <<",\"peer\":"<<copies.peer[c]-copy_before.peer[c]
        <<",\"device_local\":"<<copies.device_local[c]-copy_before.device_local[c]<<"}";
      token_rows<<"]}\n";
      e->timings.flush();e->prefill_timings.flush();return a.first?-1:result;
    };
    int next=-1;auto prefill_start=std::chrono::steady_clock::now();
    for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
    prefill_ms=Engine::ms(prefill_start);first_token_ms=first_generated_ms;
    for(auto& v:e->class_ms)v=0;for(auto& v:e->class_launches)v=0;for(auto& v:e->class_groups)v=0;
    auto decode_start=std::chrono::steady_clock::now();
    if(!a.first)for(int i=0;i<a.tokens;++i){
      generated.push_back(next);text+=a.mini?"<"+std::to_string(next)+">":vocab.at(next);
      std::cout<<"token_id "<<next<<'\n';
      if(next==p.g.eos || (!a.mini && next==248046))break;
      if(i+1<a.tokens)next=step(next,i+2);
    }
    decode_ms=Engine::ms(decode_start);
    e->dump_classes(output/"class-times.json",generated.empty()?0:int(generated.size())-1);
    std::cout << "text " << text << '\n';
    if (a.mini) {
      std::ostringstream dump;
      dump << '{';
      bool comma = false;
      for (auto &b : p.buffers) {
        int c = b.card < 0 ? (b.name == "streams" ? a.cards - 1 : 0) : b.card;
        auto slot = e->buffers[c].at(b.name);
        auto raw =
            e->readback(c, slot.id, slot.n * flash::scalar_bytes(slot.type));
        View v{raw.data(), slot.n, slot.type};
        dump << (comma ? "," : "") << ownrt::quote(b.name) << ":[";
        for (size_t i = 0; i < v.n; ++i)
          dump << (i ? "," : "") << std::bit_cast<uint32_t>(v.get(i));
        dump << ']';
        comma = true;
      }
      dump << '}';
      save(output / "buffers.json", dump.str());
    }
    std::ostringstream c;
    c << '[';
    for (size_t i = 0; i < e->devices.size(); ++i)
      c << (i ? "," : "") << e->dev(i).arena.census();
    c << ']';
    census = c.str();
    save(output / "census.json", census);
    save(output / "memory.json", "{\"peak_device_bytes_per_owner\":"+std::to_string(e->peak_device_bytes)+
      ",\"pinned_bytes_per_owner\":4194304,\"mode\":"+ownrt::quote(a.memory)+"}\n");
    read_bytes = w->read_bytes;
    max_read = w->max_read;
    max_submission_ns=e->max_submission_ns;
    teardown = e->shutdown();
    e.reset();
    w.reset();
  } catch (const std::exception &ex) {
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
