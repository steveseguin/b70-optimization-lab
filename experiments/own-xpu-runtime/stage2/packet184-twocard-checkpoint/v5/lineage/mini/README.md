# Mini (CPU) selection

`selection.json` = `../production/selection.json` (bundle 8) with `experts` and `head` set to `production`.
Bundle 8's `exp-halfcache+down-tile16` expert layout requires production geometry (p100 locality refuses
`--mini`) and the split head needs the production head; packet153's own switch gate made the same two
overrides for tiny weights. Every other choice is bundle 8's, including `miss: banks-batch` (three
recurrent banks and the speculative reserves), `snapshot_host: production` and `probe: off`. Used only by
CPU two-rank mini sessions (`--mini`); never by a device row. The production-shape mock gate covers the
production choices (expert layout, split-head p105 auxiliaries, p149 probe scratch) at real geometry.
