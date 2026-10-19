#pragma once
// Packet174: process-wide maintenance fill kick (default off = packet58as).
// Set only by the owner thread at a drained view boundary.
namespace p174 {
inline thread_local bool fill_kick=false;
struct FillKick {
  virtual ~FillKick()=default;
  virtual void kick_fills()=0; // non-blocking; never waits for fill completion
};
}
