# One bounded nonblocking stack profile

Purpose: identify Python call sites accounting for the remaining warm clip wall
time before choosing a compile/transfer candidate. This is diagnostic evidence,
not a performance promotion. One unchanged boat request on the current loaded
split server; preserve 256x256, 25 frames, 24 fps, native BF16 and 8+3 steps.

Attach installed py-spy 0.4.2 to PID24848 for 15 seconds at 100 Hz, with Python
frames, thread IDs, idle threads and `--nonblocking`. Do not capture locals,
pause the target, change ptrace policy or create another GPU context. Local
sudo is required by the host's existing ptrace_scope=1; the existing secret file
is passed only through stdin and never logged. If attachment fails, halt the
diagnostic without submitting or retrying a request.

Once the profiler confirms attachment, submit exactly one `stack-profile-01`
request with the existing profile client and selected graph. Require all four
output tensors to match baseline-01 afterward. Sampling can miss/inconsistently
read frames and changes observation overhead. Python stack occupancy is not
GPU kernel duration; retain the event timing and the full trace so the sampled
worker can be distinguished from idle threads. Prune the verified diagnostic
media/tensors after preserving identity, capture hashes and comparison receipts.

No server restart, code injection, runtime patch, power, swap or page-cache
change. Faults halt new requests. The profiler exits by its fixed duration;
the existing inference server remains running.
