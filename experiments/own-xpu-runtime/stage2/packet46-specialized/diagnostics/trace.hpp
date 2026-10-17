#pragma once
// Independently authored diagnostic adapter. No SYCL, model or arithmetic dependency.
#include <array>
#include <cstdint>
#include <initializer_list>
#include <map>
#include <ostream>
#include <span>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace packet46::diagnostics {
enum class Mode { off, diagnostic, speed_claim };
struct Config {
  Mode mode = Mode::off;
  bool routes = false, phases = false;
  std::string run_id, model_identity, runtime_identity, prompt_sha256;
  std::string dataset_role; // calibration, evaluation, or mock
  int rank = 0, physical_card = 0;
  uint64_t max_records = 1000000;
};
struct Command {
  uint64_t request_id, sequence, position, token_id, occupied_context;
  std::string_view stage; // prefill or decode
  std::string_view attempt; // ordinary, speculative, corrected, or draft
};
inline void require(bool ok, const char* message) {
  if (!ok) throw std::invalid_argument(message);
}
inline std::string quote(std::string_view s) {
  constexpr char hex[] = "0123456789abcdef";
  std::string o = "\"";
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += char(c); }
    else if (c < 32) { o += "\\u00"; o += hex[c >> 4]; o += hex[c & 15]; }
    else o += char(c);
  }
  return o + '"';
}
inline bool one_of(std::string_view x, std::initializer_list<std::string_view> xs) {
  for (auto y : xs) if (x == y) return true;
  return false;
}
inline bool phase_name(std::string_view s) {
  return one_of(s, {"prepare", "enqueue", "wait", "dense", "routing", "expert_gate_up",
    "expert_down", "shared_expert", "attention", "gdn", "hc", "sampler_head",
    "snapshot_capture", "snapshot_restore", "draft", "handoff_copy", "handoff_mailbox",
    "lookup_copy", "command", "accept", "diagnostic_route_copy"});
}
class Trace {
  Config c_;
  std::ostream* out_ = nullptr;
  uint64_t records_ = 0;
  bool closed_ = false, failed_ = false;
  using Key = std::pair<uint64_t,uint64_t>;
  std::map<Key,std::string> commands_;
  std::set<Key> resolved_;
  struct Attempt {
    Trace& owner;
    bool complete=false;
    ~Attempt(){ if(!complete) owner.failed_=true; }
  };
  void ready() const {
    require(!closed_, "trace already closed");
    require(!failed_, "diagnostic collector previously failed");
    require(records_ < c_.max_records, "diagnostic record budget exhausted; abort diagnostic run");
  }
  void begin(std::string_view kind) {
    ready();
    *out_ << "{\"schema\":\"ownrt.packet46.diagnostics.v1\",\"kind\":" << quote(kind)
          << ",\"record\":" << records_++ << ",\"rank\":" << c_.rank
          << ",\"physical_card\":" << c_.physical_card;
  }
  void finish() {
    *out_ << "}\n";
    if (!*out_) throw std::runtime_error("diagnostic trace write failed");
  }
  std::string check_command(const Command& k) const {
    require(one_of(k.stage,{"prefill","decode"}), "invalid command stage");
    require(one_of(k.attempt,{"ordinary","speculative","corrected","draft"}), "invalid command attempt");
    Key key{k.request_id,k.sequence};
    require(!resolved_.contains(key), "record after command resolution");
    std::string identity=std::to_string(k.position)+":"+std::to_string(k.token_id)+":"+
      std::to_string(k.occupied_context)+":"+std::string(k.stage)+":"+std::string(k.attempt);
    auto it=commands_.find(key);
    require(it==commands_.end() || it->second==identity, "command identity changed");
    return identity;
  }
  void command(const Command& k) {
    commands_.emplace(Key{k.request_id,k.sequence},check_command(k));
    *out_ << ",\"request_id\":" << k.request_id << ",\"command_sequence\":" << k.sequence
      << ",\"position\":" << k.position << ",\"token_id\":" << k.token_id
      << ",\"occupied_context\":" << k.occupied_context
      << ",\"stage\":" << quote(k.stage) << ",\"attempt\":" << quote(k.attempt);
  }
 public:
  explicit Trace(Config c, std::ostream* output=nullptr) : c_(std::move(c)) {
    require(!(c_.mode != Mode::diagnostic && (c_.routes || c_.phases)),
            "route/phase instrumentation requires diagnostic mode; forbidden in speed claim");
    if (c_.mode != Mode::diagnostic) return;
    require(output && (c_.routes || c_.phases), "diagnostics require output and a selected collector");
    require(c_.rank >= 0 && c_.rank <= 1 && c_.physical_card >= 0, "invalid rank/card");
    require(!c_.run_id.empty() && !c_.model_identity.empty() && !c_.runtime_identity.empty(), "missing immutable run identity");
    require(c_.prompt_sha256.size() == 64 && c_.prompt_sha256.find_first_not_of("0123456789abcdef") == std::string::npos, "prompt digest must be SHA256");
    require(one_of(c_.dataset_role,{"calibration","evaluation","mock"}), "invalid dataset role");
    require(c_.max_records >= 2, "diagnostic record budget too small");
    out_ = output;
    begin("header");
    *out_ << ",\"run_id\":" << quote(c_.run_id) << ",\"model_identity\":" << quote(c_.model_identity)
      << ",\"runtime_identity\":" << quote(c_.runtime_identity) << ",\"prompt_sha256\":" << quote(c_.prompt_sha256)
      << ",\"dataset_role\":" << quote(c_.dataset_role)
      << ",\"diagnostic_only\":true,\"speed_claim_eligible\":false,\"routes\":" << (c_.routes?"true":"false")
      << ",\"phases\":" << (c_.phases?"true":"false")
      << ",\"target_experts_per_layer\":512,\"target_top_k\":10";
    finish();
  }
  bool routes_enabled() const noexcept { return out_ && c_.routes; }
  bool phases_enabled() const noexcept { return out_ && c_.phases; }
  // Invoke immediately after the route producer, before allocation reuse. The
  // callback must wait for that producer and copy the ten ORIGINAL ordered IDs.
  // A synchronous readback is intentional: this is never a speed-claim path.
  // Disabled calls execute no callback and therefore submit/copy/wait nothing.
  template<class ReadOrderedIds>
  void capture_routes(const Command& k, int layer, ReadOrderedIds&& read) {
    if (!routes_enabled()) return;
    Attempt attempt{*this}; ready(); check_command(k);
    require(k.attempt != "draft", "v1 route schema covers target routes only");
    require(layer >= 0 && layer < 48, "target layer outside range");
    const std::array<uint32_t,10> ids = read();
    for (unsigned i=0;i<ids.size();++i) {
      require(ids[i]<512, "expert ID outside bank");
      for (unsigned j=0;j<i;++j) require(ids[i]!=ids[j], "duplicate top-k expert");
    }
    begin("routes"); command(k);
    *out_ << ",\"layer\":" << layer << ",\"expert_ids\":[";
    for (unsigned i=0;i<ids.size();++i) *out_ << (i?",":"") << ids[i];
    *out_ << "]"; finish(); attempt.complete=true;
  }
  // Use existing device event timestamps after completion, BEFORE retirement.
  // Query never enqueues a profiling kernel. Each event is emitted separately:
  // overlapping events and ranks must not become an additive wall-time budget.
  template<class Event, class Timing>
  void gpu_events(const Command& k, int layer, std::string_view phase,
                  std::span<const Event> events, Timing&& timing) {
    if (!phases_enabled()) return;
    Attempt attempt{*this}; ready(); check_command(k);
    require(phase_name(phase), "unknown phase");
    require(layer>=-1 && layer<=48, "phase layer outside range");
    for (auto event : events) {
      auto t = timing(event);
      require(event > 0 && t.start_ns > 0 && t.end_ns >= t.start_ns, "invalid GPU profiling interval");
      begin("phase"); command(k);
      *out_ << ",\"layer\":" << layer << ",\"phase\":" << quote(phase)
        << ",\"clock\":\"gpu_event\",\"event_id\":" << event
        << ",\"start_ns\":" << t.start_ns << ",\"end_ns\":" << t.end_ns
        << ",\"duration_ns\":" << t.end_ns-t.start_ns;
      finish();
    }
    attempt.complete=true;
  }
  void host_span(const Command& k, int layer, std::string_view phase, uint64_t start, uint64_t end) {
    if (!phases_enabled()) return;
    Attempt attempt{*this}; ready(); check_command(k);
    require(phase_name(phase) && end >= start, "invalid host phase interval");
    require(layer>=-1 && layer<=48, "phase layer outside range");
    begin("phase"); command(k);
    *out_ << ",\"layer\":" << layer << ",\"phase\":" << quote(phase)
      << ",\"clock\":\"host_steady\",\"event_id\":null,\"start_ns\":" << start
      << ",\"end_ns\":" << end << ",\"duration_ns\":" << end-start;
    finish(); attempt.complete=true;
  }
  // One resolution for each command represented in this rank's trace. Preserve
  // rejected/cancelled execution for actual work, select accepted for popularity.
  void resolve(const Command& k, std::string_view outcome) {
    if (!out_) return;
    Attempt attempt{*this}; ready(); check_command(k);
    require(one_of(outcome,{"accepted","rejected","cancelled","error","draft_proposal"}), "invalid command outcome");
    require((k.attempt=="draft")== (outcome=="draft_proposal") || outcome=="error" || outcome=="cancelled", "draft outcome mismatch");
    begin("resolution"); command(k); *out_ << ",\"outcome\":" << quote(outcome); finish();
    resolved_.insert({k.request_id,k.sequence});
    attempt.complete=true;
  }
  void close() {
    if (!out_) return;
    Attempt attempt{*this}; ready();
    require(commands_.size()==resolved_.size(), "unresolved command cannot close a complete trace");
    begin("footer"); *out_ << ",\"complete\":true"; finish(); out_->flush();
    if (!*out_) throw std::runtime_error("diagnostic trace flush failed");
    closed_ = true;
    attempt.complete=true;
  }
};
} // namespace packet46::diagnostics
