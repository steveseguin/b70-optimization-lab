# Packet51: second exact-order kernel round

CPU preparation started on steve-b70s after `git pull --rebase` (already current).
The packet49 oracle unit is untouched. No GPU, model payload, health probe,
service or host setting is used. Existing untracked evidence remains untouched.

[Ranking](../experiments/own-xpu-runtime/stage2/packet51-round2/RANKING.md) identifies
HC, IQ2 gate/up, route, QKV and attention as the remaining large opportunities.
The byte-floor gaps are estimates, never measured gains. Counts distinguish47
IQ2 layers,35 ordinary Q6 GDN layers and48 output projections.

[Preregistration](../experiments/own-xpu-runtime/stage2/packet51-round2/PREREGISTRATION.md)
sets the bar before device work:40 microseconds saved per ordinary M=1 layer,
or1.5x expsgate, in both fresh timing owners after two fresh byte gates. Controls
use the actual engine and accepted p48b expert kernels. M=2 covers two distinct
serial engine rows, separately labeled. Kernel, harness and independent review
work are delegated; builds and tests remain serial and low-priority.

Initial root free space was21,107,318,784 bytes. The p51 build cap is1.5 GB;
preparation reserves18 GB free before bounded writes. No old build is removed.

Implementation, CPU results, seal and exact commands will follow in focused
commits. All device performance and full-model qualification remain pending.
