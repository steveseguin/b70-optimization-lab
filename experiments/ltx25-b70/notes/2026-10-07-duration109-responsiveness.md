#109 delivery throughput and clip responsiveness

Existing109 pilot metadata measures **15.9065 generated frames/s** from two
server-success intervals (3.264s and2.897s):98 frames /6.161s. This describes
spacing between delivered clips after fills. It does not describe first-clip
latency or24FPS playback speed.

| Clip | Producer start → sample finished | → decode marker | → preview save marker | → emission success |
| --- | ---: | ---: | ---: | ---: |
| Boat |4.713s|9.060s|9.562s|10.480s|
| Marble |5.940s|10.855s|11.260s|12.504s|
| Bird |7.516s|12.463s|12.872s|14.074s|

The source-bound gate maps producer rows0–2 to sampler collection/decode queue
rows2–4 and scored emission rows4–6. Matching clip IDs—not request names
alone—bind the sample/decode/save markers. The boat starts at1791413748202ms
and its emission succeeds at1791413758682ms. This10.480s latency is excluded
from the15.9065FPS interval numerator/denominator.

Preview saves finish0.918–1.244s before server emission success. This is **not
proof of an earlier usable preview**: the save node reports queued-to-writer,
and these records contain no client-viewability or first-frame event. Sample
markers include stream drains and finite/hash evidence; decode markers include
preview CPU-copy/enqueue work. Marker differences are not pure kernel timings.
All timestamps here use the server wall clock; they exclude submission/network
latency and have no demonstrated client receipt boundary.

The high-value implication is to track individual-clip responsiveness alongside
throughput. Once full-suite exact quality is established, an explicit
latency/throughput operating point or clip-ready delivery path is a more useful
product target than shaving tiny bookkeeping costs. These three clips do not
identify which scheduling change wins, establish steady state, or justify
changing pipeline depth without another exact qualification.

[Structured audit and exact source/metadata hashes](../data/resume-20261007/duration109-responsiveness-audit.json)
records the sealed109 sources and checked history/done-marker identities. This
was a small metadata-only retrospective: no raw tensors/previews, live process,
GPU, endpoint, test, or new benchmark was accessed. The existing quality gate
was not rerun, and its original scope remains unchanged.

Root cross-check of the same emitted decode receipts shows boat VAE service
4.2803s and decode stage4.2949s, with reported decode wait0.0s. Its sample-to-decode
marker span is about4.346s. This is principally observed decoding service, not
an identified four-second scheduler delay. The structured audit binds all three
emitted decode receipts; these overlapping service measurements cannot simply
be added or subtracted to predict a faster implementation.
