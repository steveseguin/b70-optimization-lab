#include "../packet2/loader/gguf.hpp"
#include "../packet3/kernels/mock.hpp"
#include "../packet3/step/plan.hpp"
#include "kernels.hpp"
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
  int cards = 1, card = 3, tokens = 1, context = 1024, seconds = 1800;
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
          x = -std::exp(x);
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
  std::vector<Allocation> slab, scratch;
  std::ofstream progress;
  flash::Event logical = 0;
  bool poisoned = false;
  std::chrono::steady_clock::time_point deadline;
  Engine(Weights &source, const Options &args, flash::Plan q)
      : w(source), a(args), p(std::move(q)),
        progress(a.output / "progress.jsonl"),
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
    return dev(c).arena.allocate(name, bytes, m, cat, life);
  }
  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {
    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {
      guard();
      size_t k = std::min(n - i, size_t(4 * 1024 * 1024));
      std::memcpy(dev(c).arena.row(slab[c]).pointer,
                  static_cast<const uint8_t *>(src) + i, k);
      ownrt::CopyEngine copy(dev(c));
      wait(c, copy.copy(dst, offset + i, slab[c], 0, k, {}));
      dev(c).retire_completed_events();
    }
  }
  std::vector<uint8_t> readback(int c, Allocation src, size_t n) {
    std::vector<uint8_t> b(n);
    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {
      size_t k = std::min(n - i, size_t(4 * 1024 * 1024));
      ownrt::CopyEngine copy(dev(c));
      wait(c, copy.copy(slab[c], 0, src, i, k, {}));
      dev(c).retire_completed_events();
      std::memcpy(b.data() + i, dev(c).arena.row(slab[c]).pointer, k);
    }
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
          std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card + c)));
#endif
      buffers.emplace_back();
      weights.emplace_back();
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
      uint32_t active = 1;
      put(c, "active", &active, 4);
      if (buffers[c].count("token_history")) {
        int64_t history[2] = {p.g.eos, p.g.eos};
        put(c, "token_history", history, sizeof history);
        auto meta = w.metadata();
        put(c, "ple_metadata", meta.data(), meta.size() * 8);
      }
    }
#ifndef OWN_RT_HOST_ONLY
    if (a.cards == 2 || a.first) {
      for (auto &l : p.launches)
        if (l.op != "lookup")
          for (auto &name : l.weights)
            load(l.card, name);
    }
#endif
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
#ifdef OWN_RT_HOST_ONLY
  void linear(const flash::Launch &l) {
    auto &t = w.directory.at(l.weights[0]);
    auto type = flash::grid_type(t.grid);
    int c = l.card, rows = l.shape[1], cols = l.shape[2], batch = l.shape[0];
    auto x =
        readback(c, buffers[c].at(l.inputs[0]).id, size_t(batch) * cols * 2);
    size_t rb = cols / iq3::layout(type).elements * iq3::layout(type).bytes;
    std::vector<uint32_t> routes;
    if (l.op == "routed_gemv") {
      auto b = readback(c, buffers[c].at(l.inputs[1]).id, batch * 12);
      routes.resize(batch * 3);
      std::memcpy(routes.data(), b.data(), b.size());
    }
    std::vector<uint16_t> out(batch * rows);
    for (int j = 0; j < batch; ++j) {
      size_t base = 0;
      if (!routes.empty()) {
        require(routes[j * 3] < unsigned(p.g.experts), "CPU route bounds");
        base = size_t(routes[j * 3]) * rows * rb;
      }
      int tile = std::max(1, int(128 * 1024 / rb));
      for (int r = 0; r < rows; r += tile) {
        guard();
        int nr = std::min(tile, rows - r);
        auto raw = w.read(t.name, base + size_t(r) * rb, nr * rb);
        for (int k = 0; k < nr; ++k)
          out[j * rows + r + k] = iq3::bf16_bits(iq3::gemv_row(
              type, raw.data() + k * rb,
              reinterpret_cast<const uint16_t *>(x.data()) + size_t(j) * cols,
              iq3::Type::BF16, cols));
      }
    }
    put(c, l.outputs[0], out.data(), out.size() * 2);
    if (l.outputs.size() > 1) {
      std::vector<uint32_t> status(batch);
      put(c, l.outputs[1], status.data(), status.size() * 4);
    }
  }
#endif
  flash::Event enqueue(const flash::Launch &l, flash::Event dep) override {
    guard();
    require(dep == logical, "step event order");
    int c = l.card;
    if (l.op == "lookup")
      lookup(l);
    else if (l.op == "handoff" || l.op == "handoff_result") {
      for (auto &name : l.outputs) {
        auto s = buffers[l.source_card].at(name);
        auto b =
            readback(l.source_card, s.id, s.n * flash::scalar_bytes(s.type));
        put(c, name, b.data(), b.size());
      }
    } else if (l.op == "gemv" || l.op == "routed_gemv") {
#ifdef OWN_RT_HOST_ONLY
      linear(l);
#else
      load(c, l.weights[0]);
      auto &t = w.directory.at(l.weights[0]);
      auto type = flash::grid_type(t.grid);
      auto get = [&](const std::string &n) { return buffers[c].at(n).id; };
      ownrt::Event e;
      if (l.op == "gemv")
        e = iq3::gemv(dev(c), type, weights[c].at(t.name), get(l.inputs[0]),
                      get(l.outputs[0]), l.shape[1], l.shape[2]);
      else
        e = iq3::routed_gemv(dev(c), type, weights[c].at(t.name),
                             get(l.inputs[0]), get(l.outputs[0]),
                             get(l.inputs[1]), get(l.outputs[1]), p.g.experts,
                             l.shape[1], l.shape[2], l.shape[0], l.shape[1]);
      wait(c, e);
#endif
    } else {
      Spec s;
      s.g = p.g;
      s.packed_heads = !a.mini;
      s.site.parameter = l.parameter;
      std::copy(l.shape.begin(), l.shape.end(), s.site.shape);
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
      wait(c, iq3::step_operator(dev(c), s, bindings));
    }
    // Bring-up is segmented and synchronously drained. A failed operation
    // poisons the request; there is no retry or checkpoint reuse after failure.
    if (integer(c, "error"))
      throw std::runtime_error("device sticky error at " + l.label);
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
  o << "{\"schema\":\"own-runtime.iq3.packet4.plan.v1\",\"cards\":" << cards
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
        << ",\"component\":" << ownrt::quote(t.component) << "}";
      comma = true;
    }
  o << "],\"expert_placement\":\"all experts belong to their layer owner; none "
       "pruned\",\"one_card_full_model\":\"stream one layer at a "
       "time\",\"capture\":false}";
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
    std::ofstream layers(output / "step1/layers.jsonl");
    auto step = [&](int token, bool fixture) {
      for (int c = 0; c < a.cards; ++c)
        if (e->buffers[c].count("token"))
          e->put(c, "token", &token, 4);
      for (auto &l : p.launches) {
        e->enqueue(l, e->logical);
        if (ends(l.label, ".ffn.combine")) {
          if (fixture) {
            int layer = std::stoi(l.label.substr(4));
            auto b = e->readback(l.card, e->buffers[l.card].at("streams").id,
                                 4 * p.g.h * 2);
            char name[40];
            std::snprintf(name, sizeof name, "layer-%02d.bf16", layer);
            std::ofstream f(output / "step1" / name, std::ios::binary);
            f.write(reinterpret_cast<char *>(b.data()), b.size());
            auto digest = hash(b);
            layers << "{\"layer\":" << layer << ",\"shape\":[1,4," << p.g.h
                   << "],\"dtype\":\"BF16 little-endian\",\"sha256\":"
                   << ownrt::quote(digest) << "}\n";
            layers.flush();
            if (!a.oracle.empty()) {
              std::ifstream oracle(a.oracle / name, std::ios::binary);
              require(bool(oracle), "requested oracle fixture missing");
              std::vector<uint8_t> expected(
                  (std::istreambuf_iterator<char>(oracle)), {});
              did_compare = true;
              comparison &= b == expected;
            }
          }
#ifndef OWN_RT_HOST_ONLY
          if (a.cards == 1 && !a.first)
            e->release_layer(l.card);
#endif
        }
      }
      return a.first ? -1 : e->integer(0, "next_token");
    };
    int next = -1;
    for (size_t i = 0; i < input.size(); ++i)
      next = step(input[i], i + 1 == input.size());
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
          next = step(next, false);
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
  r << "{\"schema\":\"own-runtime.iq3.packet4.run.v1\",\"passed\":"
    << (error.empty() && comparison ? "true" : "false")
    << ",\"error\":" << ownrt::quote(error) << ",\"mode\":"
    << ownrt::quote(a.mini    ? "mini"
                    : a.first ? "first-layer"
                              : "full-model")
    << ",\"arithmetic\":\"packet2-tree32-bf16-state-sigmoid-gguf-head-layout-"
       "v1\",\"device_executed\":";
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
