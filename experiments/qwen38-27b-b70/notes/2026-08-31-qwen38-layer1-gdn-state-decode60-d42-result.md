# Qwen3.8 layer-1 GDN state at token 60 D42 result

D42 found four different convolution states and four different SSM states
before the synchronized call-62 core. Hidden/QKVZ/BA inputs remained exact.
The core and post-call states stayed four-way different, so the late difference
was accumulated earlier rather than created at call 62.

The deliberate pre-core synchronization also changed the eventual token
outcome: all four 64-token outputs matched in this diagnostic. That is useful
ordering evidence but not a production repair; a per-token device-wide sync is
not acceptable without locating the missing dependency. D43 moves the state
probe to prefill call 2 to determine whether state divergence begins there.
