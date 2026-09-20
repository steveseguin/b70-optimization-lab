# Server 88 segfault at encoder load, 2026-09-20 17:26:49 EDT (boot 8f469374)

## What happened

Fresh server 88 (packet byte-identical to the freeze-free packet 86) was
launched 17:25 after the memtester pass; the f88 campaign started 17:26:35.
Fourteen seconds in, during warm-00's text-encoder load:

```
kernel: traps: python[5001] general protection fault ip:184cfbb sp:7db4ad1fd220 error:0 in python3.12[13f2fbb,1600000+8d5000]
Fatal Python error: Segmentation fault
  ... comfy/text_encoders/gemma4.py:1589 from_pretrained
  ... comfy/sd.py:1584 load_clip
  ... scripts/host_embedding_clip.py:291 load_clip
  ... custom_nodes/ltx_host_embedding_lab/__init__.py:155 load
```

A general-protection fault executing the python3.12 binary's own text
segment, in the Gemma encoder load path. The host stayed up (first time the
failure mode was a process death instead of a machine freeze). The warm
receipt in data/graph-capture-88/ is the FROZEN 11:45 boot's leftover —
this campaign produced nothing.

## Scoreboard, 2026-09-20 (all on packet-86-equivalent code or its 87 descendant)

| Attempt | Boot | Outcome |
| --- | --- | --- |
| packet 87 campaign | 58ae370e | freeze ~70 s in (hard lockup CPU21) |
| packet 87 retry | 5486d35a | freeze ~130 s in (storage-first hang) |
| packet 88 (=86) campaign | dff7cf53 | freeze ~130 s in |
| packet 88 retry | 8f469374 | **segfault** ~14 s in, encoder load |

Four campaign attempts, four failures, all in the warm window (encoder load
through the warm→endure transition). Yesterday evening the same code passed
three campaigns on one boot. Userspace memtester passed 64 GB today. The
load-time corruption the lane has now seen three times (two byte flips in
model loads earlier this week, now a GP fault in interpreter text during a
load) is the same disease as the freezes; the failure window is whenever the
26 GB encoder moves through page cache + host RAM + DMA while the GPUs spin
up.

## What this changes

Nothing about the code: packet 88 is byte-identical to a version that ran a
full campaign clean. Everything about procedure: the campaign's danger window
is real, probabilistic, and currently batting 1.000 today.

Procedure changes for the next attempt:

1. A 60 s idle rest between server construction and the first prompt (the
   segfault hit 14 s after construction finished — construction itself loads
   the VAE and control components; back-to-back load spikes may stack).
2. The already-added 60 s settle between warm and endure.
3. Retry budget: if the next attempt also dies in the window, campaigns stop
   until the user-run items land (memtest86+ at console, BIOS Power Supply
   Idle Control = Typical Current Idle, PSU rating vs the 12 V rail math,
   fbdev_emulation=0 for pstore). Four failures is a pattern; five is a
   habit.
