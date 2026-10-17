#pragma once
#include "owner_api.hpp"
#include <sycl/sycl.hpp>
#include <mutex>
#include <functional>
#include <memory>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace ownrt {
// A preparation scope intercepts command-group creation, before queue submission.
// The original kernel lambda stays in its original lexical scope/name. Captures
// are copied once; no pointer to the transient Operation or binding span survives.
struct NativeTracked { Event handle; sycl::event event; int card; };
struct NativeIssueState {
  std::vector<NativeTracked>* events;
  std::mutex* mutex;
  std::exception_ptr* error;
  int* allocation_card;
  int card;
};
struct PreparedSyclSubmission {
  virtual ~PreparedSyclSubmission() = default;
  // Called once at preparation. The resulting closure directly submits its
  // concrete F; no virtual dispatch survives on the application issue path.
  virtual std::function<Event()> make_callback(NativeIssueState) const = 0;
};
inline thread_local std::unique_ptr<PreparedSyclSubmission>* submission_capture=nullptr;
class SubmissionCapture final {
  std::unique_ptr<PreparedSyclSubmission>* previous;
 public:
  explicit SubmissionCapture(std::unique_ptr<PreparedSyclSubmission>& result)
      :previous(submission_capture) {
    if(previous)throw std::logic_error("nested native preparation");
    submission_capture=&result;
  }
  ~SubmissionCapture(){submission_capture=previous;}
  SubmissionCapture(const SubmissionCapture&)=delete;
};
template<class F> struct BoundSyclSubmission final:PreparedSyclSubmission {
  sycl::queue* queue;
  F command;
  BoundSyclSubmission(sycl::queue& q,F f):queue(&q),command(std::move(f)){}
  std::function<Event()> make_callback(NativeIssueState state)const override {
    return [queue=queue,command=command,state] {
      {std::lock_guard lock(*state.mutex);if(*state.error)std::rethrow_exception(*state.error);}
      if(*state.allocation_card!=state.card)throw std::logic_error("prepared native card mismatch");
      if(state.events->size()>=state.events->capacity())throw std::length_error("native prepared event capacity");
      const auto event=next_handle();
      state.events->push_back({event,queue->submit(command),state.card});
      return event;
    };
  }
};
template<class F> sycl::event prepared_submit(sycl::queue& q,F command) {
  if(!submission_capture)return q.submit(std::move(command));
  if(*submission_capture)throw std::logic_error("multiple native submissions in one operation");
  *submission_capture=std::make_unique<BoundSyclSubmission<F>>(q,std::move(command));
  return {}; // Placeholder is never issued, retained, waited or profiled.
}
}
