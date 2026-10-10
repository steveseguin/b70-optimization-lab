# Continuation periods with client pacing separated

Generated from the [v2 saved-evidence snapshot](../data/ltx25-continuation-stream-2026-10-10-pacing-v2.json). Its source hashes bind all input bytes. No new native work was run.

Primary statistics use every consecutive submit-to-submit interval with destination sequence >=10 that ends before the first pacing hold in each client invocation. A restart starts a new segment; no restart gap is bridged. The full prefix is retained, including cuts, maintenance and slow intervals. This is an early unthrottled window, not an estimate of sustained unthrottled performance.

Raw statistics retain every within-invocation interval, including client holds. The hold-free diagnostic drops only intervals containing a hold; later periods can still reflect prior pacing or drift. No historic duration is subtracted: legacy hold durations were rounded to 0.1 seconds. New precise logs contain monotonic nanosecond start, end and duration, including interrupted holds. These are client observations, not server-side chain timers.

| Client / identity | Holds | Raw n / median s | Early unthrottled n / median / mean / p90 s | Hold-free diagnostic n / median s |
| --- | ---: | --- | --- | --- |
| `s117-live01` / `f61d70f58266` | 0 | 53 / 5.3030 | 53 / 5.3030 / 5.5069 / 6.0180 | 53 / 5.3030 |
| `s117-stream01` / `c3800ed3cbe0` | 0 | 124 / 4.7620 | 124 / 4.7620 / 4.8459 / 5.1440 | 124 / 4.7620 |
| `s117-stream01` / `4466024f7b22` | 0 | 163 / 5.2050 | 163 / 5.2050 / 5.3863 / 5.8630 | 163 / 5.2050 |
| `s118b-dg1-live01` / `fa17c2ccbe8c` | 0 | 27 / 5.5590 | 27 / 5.5590 / 5.5412 / 5.7760 | 27 / 5.5590 |
| `s118b-live01` / `7f1bc39cf70d` | 0 | 91 / 5.1950 | 91 / 5.1950 / 5.3564 / 5.8500 | 91 / 5.1950 |
| `s118b-live02` / `5c2288ffec78` | 0 | 261 / 5.2790 | 261 / 5.2790 / 5.4162 / 5.8880 | 261 / 5.2790 |
| `s118b-live03` / `92344b0aabd1` | 0 | 157 / 5.2630 | 157 / 5.2630 / 5.4013 / 5.8680 | 157 / 5.2630 |
| `s119-live01` / `a524e0535342` | 0 | 51 / 5.4350 | 51 / 5.4350 / 5.4019 / 5.5520 | 51 / 5.4350 |
| `s120-live01` / `84e973208fc2` | 0 | 125 / 5.0920 | 125 / 5.0920 / 5.1319 / 5.5910 | 125 / 5.0920 |
| `s121-live01` / `f3388630d54a` | 3 | 409 / 5.7140 | 316 / 5.6660 / 5.7941 / 6.2950 | 407 / 5.7140 |
| `s121-live02` / `fb3ab76bbf94` | 5 | 306 / 5.7595 | 175 / 5.6510 / 5.8023 / 6.2960 | 301 / 5.7520 |
| `s123b-f169-live01` / `bd56510af21e` | 0 | 39 / 6.8240 | 39 / 6.8240 / 6.9814 / 7.4330 | 39 / 6.8240 |
| `s123b-legacy-live01` / `4b832cdcaf95` | 0 | 51 / 5.7700 | 51 / 5.7700 / 5.9730 / 6.4450 | 51 / 5.7700 |
| `s123b-live01` / `c7c05324860a` | 0 | 31 / 5.7330 | 31 / 5.7330 / 5.9289 / 6.4080 | 31 / 5.7330 |
| `s123b-live02` / `e88c485d0e75` | 0 | 203 / 5.8940 | 203 / 5.8940 / 6.0114 / 6.4990 | 203 / 5.8940 |
| `s124-live01` / `ef461a558710` | 0 | 35 / 5.7460 | 35 / 5.7460 / 5.9085 / 6.4400 | 35 / 5.7460 |
| `s125-live01` / `fef2afa3904c` | 0 | 207 / 5.7850 | 207 / 5.7850 / 5.9023 / 6.2370 | 207 / 5.7850 |
| `s126-live01` / `4f43b9ea47f4` | 2 | 241 / 5.7590 | 202 / 5.6970 / 5.8329 / 6.3510 | 239 / 5.7480 |
| `s127-live01` / `44cac3774e20` | 0 | 85 / 5.4670 | 85 / 5.4670 / 5.5850 / 6.0430 | 85 / 5.4670 |
| `s128-gc60-live01` / `d6251911ad80` | 0 | 61 / 5.5280 | 61 / 5.5280 / 5.6426 / 6.0090 | 61 / 5.5280 |
| `s128-live01` / `303191c278ed` | 0 | 60 / 5.4925 | 60 / 5.4925 / 5.6387 / 5.9610 | 60 / 5.4925 |
| `s129-live01` / `7f7f7e7812b3` | 25 | 599 / 5.5540 | 91 / 5.4860 / 5.6188 / 5.9260 | 574 / 5.5460 |
| `s129-live02` / `94ae079d5106` | 15 | 342 / 5.5070 | 89 / 5.5100 / 5.6337 / 6.0060 | 327 / 5.5010 |
| `s129-live03` / `5f285363d8c3` | 22 | 511 / 5.5400 | 94 / 5.4995 / 5.6446 / 5.9950 | 489 / 5.5250 |
| `s129-live04` / `4cd8661dc41e` | 7 | 205 / 5.5220 | 100 / 5.5310 / 5.6628 / 5.9830 | 198 / 5.5145 |
| `s133b-live01` / `4ad7f791dafb` | 2 | 64 / 5.2250 | 47 / 5.2210 / 5.3490 / 5.8150 | 62 / 5.2170 |
| `s133b-live02` / `313d2ae4c464` | 12 | 222 / 5.3900 | 71 / 5.4110 / 5.5334 / 5.8420 | 210 / 5.3745 |
| `s135-gc10-live01` / `df4b610410bb` | 47 | 747 / 5.5530 | 52 / 5.2415 / 5.3642 / 5.7640 | 700 / 5.5255 |
| `s135-live01` / `228b06a46f25` | 6 | 111 / 5.2480 | 52 / 5.2415 / 5.3864 / 5.8150 | 105 / 5.2360 |
