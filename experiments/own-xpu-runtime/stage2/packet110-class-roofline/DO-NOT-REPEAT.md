# Packet110 boundaries

- No packet107 specialised GDN or QSA execution; current GDN only.
- No reuse of packet77 class times or inference of GDN timings from QSA.
- No performance promotion from synthetic fixtures or the copy roofline.
- No combining per-event medians: sum events per class per call first.
- Byte floors exclude cache overfetch/reloads and are not measured DRAM traffic.
- No new lever implemented here; coordinator owns the next experiment.
