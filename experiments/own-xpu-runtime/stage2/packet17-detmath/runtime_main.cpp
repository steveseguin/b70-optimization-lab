#include "detmath.hpp"
#include "rope.hpp"
#include "../packet2/loader/gguf.hpp"
#include "../packet3/kernels/mock.hpp"
#include "../packet3/step/plan.hpp"
#include "performance.hpp"
#ifdef OWN_RT_HOST_ONLY
#include "mock_device.hpp"
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
class Host final : public ownrt::MockDevice {
public:
  ownrt::Event copy(void *a, const void *b, size_t n,
                    std::span<const ownrt::Event> d) override {
    auto e = MockDevice::copy(a, b, n, d);
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
  bool mini = false, first = false, record = false, authorized = false;
  int cards = 1, card = 3, tokens = 8, context = 128, seconds = 10800;
  std::string memory = "layer-streaming";
  fs::path inputs, output, model, plan, auth, oracle;
};
static Options parse(int argc, char **argv) {
  Options a;
  for (int i = 1; i < argc; ++i) {
    std::string k = argv[i];
    auto value = [&] {
      require(i + 1 < argc, "missing " + k);
      return std::string(argv[++i]);
    };
    if (k == "--mini")
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
    else if (k == "--tokens")
      a.tokens = std::stoi(value());
    else if (k == "--context")
      a.context = std::stoi(value());
    else if (k == "--seconds")
      a.seconds = std::stoi(value());
    else if (k == "--input")
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
  require(a.cards >= 1 && a.cards <= 2 && a.card >= 0 && a.card + a.cards <= 4,
          "card range");
  require(a.tokens > 0 && a.tokens <= 64 && a.context >= 8 &&
              a.context <= 1024 && a.seconds > 0 && a.seconds <= 10800,
          "bounded generation/context/deadline");
  require(!a.output.empty(), "--output required");
  require((a.cards == 1 && a.memory == "layer-streaming") ||
          (a.cards == 2 && a.memory == "resident"), "memory mode/card count mismatch");
#ifdef OWN_RT_HOST_ONLY
  require(!a.authorized, "host binary cannot authorize device execution");
  require(a.mini || a.first || a.record,
          "CPU real model limited to first layer");
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
  return p;
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
  std::vector<std::map<std::string, Slot>> buffers;
  std::vector<std::map<std::string, Allocation>> weights;
  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;
  std::vector<std::vector<uint32_t>> selected;
  std::vector<int> loaded_layer;
  std::ofstream timings;
  double gemv_ms=0, nongemv_ms=0, transfer_ms=0;
  uint64_t submitted=0;
  size_t peak_device_bytes=0;
  static double ms(std::chrono::steady_clock::time_point t) {
    return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t).count();
  }
  void finish(int c, Launch l, bool gemv) {
    wait(c,l.last);
#ifndef OWN_RT_HOST_ONLY
    auto first=dev(c).timing(l.first), last=dev(c).timing(l.last);
    double elapsed=double(last.end_ns-first.start_ns)/1e6;
    (gemv?gemv_ms:nongemv_ms)+=elapsed;
#else
    (void)gemv;
#endif
    submitted+=l.passes;
    dev(c).retire_completed_events();
  }
  void finish(int c, ownrt::Event e) {finish(c,{e,e,1},false);}

  std::ofstream progress;
  flash::Event logical = 0;
  bool poisoned = false;
  std::chrono::steady_clock::time_point deadline;
  Engine(Weights &source, const Options &args, flash::Plan q)
      : w(source), a(args), p(std::move(q)),
        timings(a.output / "timings.jsonl"), progress(a.output / "progress.jsonl"),
        deadline(std::chrono::steady_clock::now() +
                 std::chrono::seconds(a.seconds)) {}
  void guard() {
    require(!poisoned, "poisoned step");
    require(!stopped, "cooperative stop");
    require(std::chrono::steady_clock::now() < deadline,
            "cooperative deadline");
  }
  ownrt::Device &dev(int c) { return *devices.at(c); }
  void wait(int c, ownrt::Event e) {
    require(dev(c).wait(e, std::chrono::seconds(60)),
            "operation drain timeout; retain owner");
  }
  Allocation allocate(int c, std::string name, size_t bytes, Category cat,
                      Lifetime life, Memory m = Memory::device) {
    if (m == Memory::device)
      require(dev(c).arena.total(m) + bytes <= 30ull * 1024 * 1024 * 1024,
              "30 GiB per-card arena admission");
    auto id=dev(c).arena.allocate(name, bytes, m, cat, life);
    peak_device_bytes=std::max(peak_device_bytes,dev(c).arena.total(Memory::device));
    return id;
  }
  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {
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
  void load(int c, const std::string &name) {
    if (weights[c].count(name))
      return;
    auto &t = w.directory.at(name);
    require(t.component != "embedding" && t.component != "ple_lookup",
            "lookup must be bounded rows");
    auto id = allocate(c, "weight:" + name, t.bytes, Category::weights,
                       Lifetime::process);
    weights[c][name] = id;
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
    for (int c = 0; c < a.cards; ++c) {
#ifdef OWN_RT_HOST_ONLY
      devices.push_back(
          std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
      devices.push_back(
          std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card + c, true)));
#endif
      buffers.emplace_back();
      weights.emplace_back();selected.emplace_back();loaded_layer.push_back(-1);
      workspace.push_back(allocate(c,"gemv-workspace",4*1024*1024,Category::scratch,Lifetime::transaction));
      compact_routes.push_back(allocate(c,"compact-routes",p.g.top*sizeof(iq3::Route),Category::scratch,Lifetime::transaction));
      mixture_out.push_back(allocate(c,"ordered-mixture",p.g.h*2,Category::scratch,Lifetime::transaction));
      one.push_back(allocate(c,"mixture-one",4,Category::scratch,Lifetime::transaction));
      slab.push_back(allocate(c, "bounded-copy", 4 * 1024 * 1024,
                              Category::pinned_slab, Lifetime::transfer,
                              Memory::pinned));
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
  void lookup(const flash::Launch &l) {
    int c = l.card;
    auto input = buffers[c].at(l.inputs[0]);
    auto ids = readback(c, input.id, input.n * flash::scalar_bytes(input.type));
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
    int c=l.card;auto m=matrix(l);
    if(l.op=="gemv")finish(c,dense(dev(c),m,arithmetic::variant(m.type,m.rows,m.columns,1,a.mini)),true);
    else if(l.op=="expert_gate_up") {
      auto up=matrix(l,1);finish(c,experts(dev(c),{m,up},true),true);
    } else finish(c,experts(dev(c),{m},false),true);
  }
  flash::Event enqueue(const flash::Launch &l, flash::Event dep) override {
    guard();
    require(dep == logical, "step event order");
    int c = l.card;
    if(l.label.starts_with("blk."))stage_layer(c,std::stoi(l.label.substr(4)));
    auto site_start=std::chrono::steady_clock::now();
    double old_g=gemv_ms,old_n=nongemv_ms,old_t=transfer_ms;
    uint64_t old_submitted=submitted;
    if (l.op == "lookup")
      lookup(l);
    else if (l.op == "handoff" || l.op == "handoff_result") {
      for (auto &name : l.outputs) {
        auto s = buffers[l.source_card].at(name);
        auto b =
            readback(l.source_card, s.id, s.n * flash::scalar_bytes(s.type));
        put(c, name, b.data(), b.size());
      }
    } else if (l.op == "gemv" || l.op == "routed_gemv" || l.op=="expert_gate_up") {
      linear(l);
    } else {
      if(l.op=="moe_combine")finish(c,mixture(dev(c),buffers[c].at(l.inputs[0]).id,
          buffers[c].at(l.inputs[1]).id,mixture_out[c],p.g.h),false);
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
      finish(c, iq3::step_operator(dev(c), s, bindings));
      if(l.op=="route" && a.cards==1) {
        std::vector<std::string> evict;
        for(const auto& [name,id]:weights[c])if(name.find("_exps.weight")!=std::string::npos)evict.push_back(name);
        for(const auto& name:evict){dev(c).arena.release(weights[c].at(name));weights[c].erase(name);}
        auto ids=readback(c,buffers[c].at(l.outputs[0]).id,p.g.top*4);
        selected[c].resize(p.g.top);std::memcpy(selected[c].data(),ids.data(),ids.size());
      }
    }
    // Bring-up is segmented and synchronously drained. A failed operation
    // poisons the request; there is no retry or checkpoint reuse after failure.
    if (integer(c, "error"))
      throw std::runtime_error("device sticky error at " + l.label);
    timings << "{\"kind\":\"site\",\"label\":" << ownrt::quote(l.label)
            << ",\"wall_ms\":" << ms(site_start) << ",\"gemv_device_ms\":" << device_ms(gemv_ms-old_g)
            << ",\"non_gemv_device_ms\":" << device_ms(nongemv_ms-old_n)
            << ",\"transfer_wall_ms\":" << transfer_ms-old_t
            << ",\"kernel_submissions\":" << submitted-old_submitted << "}\n";
    timings.flush();
    progress << "{\"phase\":\"site\",\"label\":" << ownrt::quote(l.label)
             << ",\"card\":" << c << "}\n";
    progress.flush();
    return ++logical;
  }
  void submission_failed() noexcept override { poisoned = true; }
  std::vector<std::string> shutdown() {
    std::vector<std::string> receipts;
    for (auto &d : devices) {
      auto r = d->shutdown(std::chrono::seconds(60));
      receipts.push_back(r.json());
      if (!r.safe_to_exit) {
        save(a.output / "retained-owner.json", r.json());
        ownrt::hold_for_supervisor();
      }
    }
    return receipts;
  }
  void release_layer(int c) {
    for (auto &[name, id] : weights[c])
      dev(c).arena.release(id);
    weights[c].clear();
  }
};
static void write_plan(const fs::path &path, const flash::Plan &p,
                       const Weights &w, int cards) {
  std::map<std::string, int> owner;
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
      o << (comma ? "," : "") << "{\"name\":" << ownrt::quote(n)
        << ",\"card\":" << (l.op == "lookup" ? -1 : l.card)
        << ",\"bytes\":" << t.bytes
        << ",\"component\":" << ownrt::quote(t.component);
      if(l.op=="gemv" || l.op=="routed_gemv" || l.op=="expert_gate_up")
        o << ",\"variant\":" << ownrt::quote(arithmetic::name(arithmetic::variant(
          flash::grid_type(t.grid),l.shape[1],l.shape[2],l.op=="gemv"?1:p.g.experts,w.mini)));
      o << "}";
      comma = true;
    }
  o << "],\"expert_placement\":\"all experts belong to their layer owner; none "
       "pruned\",\"one_card_full_model\":\"stream one layer at a "
       "time\",\"capture\":false,\"memory_plan\":{";
  size_t extra=256ull*1024*1024+4*1024*1024+p.g.top*sizeof(iq3::Route)+p.g.h*2+4;
  std::vector<size_t> base(cards,extra),resident(cards,0);
  for(const auto& b:p.buffers)for(int c=0;c<cards;++c)
    if(b.card==-1 || b.card==c)base[c]+=count(b.shape)*flash::scalar_bytes(b.type);
  std::map<int,size_t> layer;
  for(const auto& [n,c]:owner) {
    const auto& t=w.directory.at(n);
    if(t.component=="embedding" || t.component=="ple_lookup")continue;
    resident[c]+=t.bytes;
    int number=n.starts_with("blk.")?std::stoi(n.substr(4)):-1;
    layer[number]+=t.shape.size()==3?t.bytes/p.g.experts*p.g.top:t.bytes;
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
}
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
  std::string census = "[]";
  try {
    a = parse(argc, argv);
    require(!fs::exists(a.output), "output already exists");
    output = a.output;
    fs::create_directories(output);
    std::signal(SIGTERM, stop);
    std::signal(SIGINT, stop);
    w = std::make_unique<Weights>(a);
    auto p = plan(*w, a);
    write_plan(output / "plan.json", p, *w, a.cards);
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
    e->initialize();
    fs::create_directory(output / "step1");

    size_t token_index=0;
    auto step = [&](int token, int fixture_step) {
      auto token_start=std::chrono::steady_clock::now();
      double token_g=e->gemv_ms,token_n=e->nongemv_ms,token_t=e->transfer_ms;
      double layer_g=token_g,layer_n=token_n,layer_t=token_t;
      auto layer_start=token_start;
      fs::path fixture_dir=output/("step"+std::to_string(fixture_step));
      if(fixture_step>0)fs::create_directories(fixture_dir);
      std::ofstream layer_hashes;
      if(fixture_step>0)layer_hashes.open(fixture_dir/"layers.jsonl");
      for (int c = 0; c < a.cards; ++c)
        if (e->buffers[c].count("token"))
          e->put(c, "token", &token, 4);
      for (auto &l : p.launches) {
        e->enqueue(l, e->logical);
        if (ends(l.label, ".ffn.combine")) {
          int layer_number=std::stoi(l.label.substr(4));
          e->timings << "{\"kind\":\"layer\",\"token_index\":" << token_index
            << ",\"layer\":" << layer_number << ",\"wall_ms\":" << Engine::ms(layer_start)
            << ",\"gemv_device_ms\":" << device_ms(e->gemv_ms-layer_g)
            << ",\"non_gemv_device_ms\":" << device_ms(e->nongemv_ms-layer_n)
            << ",\"transfer_wall_ms\":" << e->transfer_ms-layer_t << "}\n";
          layer_start=std::chrono::steady_clock::now();layer_g=e->gemv_ms;layer_n=e->nongemv_ms;layer_t=e->transfer_ms;
          if (fixture_step>0) {
            int layer = std::stoi(l.label.substr(4));
            auto b = e->readback(l.card, e->buffers[l.card].at("streams").id,
                                 4 * p.g.h * 2);
            char name[40];
            std::snprintf(name, sizeof name, "layer-%02d.bf16", layer);
            std::ofstream f(fixture_dir / name, std::ios::binary);
            f.write(reinterpret_cast<char *>(b.data()), b.size());
            auto digest = hash(b);
            layer_hashes << "{\"layer\":" << layer << ",\"shape\":[1,4," << p.g.h
                   << "],\"dtype\":\"BF16 little-endian\",\"sha256\":"
                   << ownrt::quote(digest) << "}\n";
            layer_hashes.flush();
            if (!a.oracle.empty() && fixture_step==1) {
              std::ifstream oracle(a.oracle / name, std::ios::binary);
              require(bool(oracle), "requested oracle fixture missing");
              std::vector<uint8_t> expected(
                  (std::istreambuf_iterator<char>(oracle)), {});
              did_compare = true;
              comparison &= b == expected;
            }
          }
          if (a.cards == 1 && !a.first) {
            e->release_layer(l.card);e->loaded_layer[l.card]=-1;
          }
        }
      }
      e->timings << "{\"kind\":\"token\",\"token_index\":" << token_index++
        << ",\"input_token\":" << token << ",\"wall_ms\":" << Engine::ms(token_start)
        << ",\"gemv_device_ms\":" << device_ms(e->gemv_ms-token_g)
        << ",\"non_gemv_device_ms\":" << device_ms(e->nongemv_ms-token_n)
        << ",\"transfer_wall_ms\":" << e->transfer_ms-token_t << "}\n";
      e->timings.flush();
      if(a.cards==1 && !a.first)e->release_layer(0);
      return a.first ? -1 : e->integer(0, "next_token");
    };
    int next = -1;
    for (size_t i = 0; i < input.size(); ++i)
      next = step(input[i], i + 1 == input.size() ? 1 : 0);
    if (!a.first)
      for (int i = 0; i < a.tokens; ++i) {
        generated.push_back(next);
        if (a.mini)
          text += "<" + std::to_string(next) + ">";
        else
          text += vocab.at(next);
        std::cout << "token_id " << next << '\n';
        if (next == p.g.eos || (!a.mini && next == 248046))
          break;
        if (i + 1 < a.tokens)
          next = step(next, i+2);
      }
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
    if (e) {
      e->poisoned = true;
      teardown = e->shutdown();
      e.reset();
    }
  }
  if (output.empty() || !fs::is_directory(output))
    return 1;
  std::ostringstream r;
  r << "{\"schema\":\"own-runtime.iq3.packet13.run.v1\",\"passed\":"
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
