# Qwen3.6 Route Overlap and Hotpack Simulation

Top-N set size: `16`
Hotpack sizes: `8, 16, 32, 64`

| Rank | Layer | Records | TopN union | TopN Jaccard | Global K=16 | Label K=16 | Best buckets K=16 | Read |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 8 | 520 | 34 | 0.2673 | 0.4010 | 0.4894 | 0.4894 | bucket/dynamic |
| 2 | 9 | 520 | 32 | 0.2840 | 0.4135 | 0.5019 | 0.5019 | bucket/dynamic |
| 3 | 21 | 520 | 33 | 0.2897 | 0.4212 | 0.5019 | 0.5019 | bucket/dynamic |
| 4 | 20 | 520 | 29 | 0.3183 | 0.4385 | 0.5106 | 0.5106 | bucket/dynamic |
| 5 | 14 | 520 | 27 | 0.4024 | 0.4231 | 0.5010 | 0.5010 | bucket/dynamic |

## Best K=16 Bucket Assignments

### Layer 8

Global K=16 coverage: `0.4010`; label-specific upper bound: `0.4894`; best bucket coverage: `0.4894`.

- Bucket 1: labels `code, long-natural, structured`, coverage `1.0000`, experts `4, 72, 84, 98, 99, 107, 110, 178, 181, 191, 220, 224, 232, 239`
- Bucket 2: labels `math`, coverage `0.5179`, experts `42, 53, 56, 57, 95, 107, 123, 126, 132, 151, 171, 191, 206, 220, 224, 249`
- Bucket 3: labels `repetitive`, coverage `0.4286`, experts `4, 41, 61, 81, 98, 110, 116, 117, 151, 173, 191, 205, 215, 220, 224, 239`

### Layer 9

Global K=16 coverage: `0.4135`; label-specific upper bound: `0.5019`; best bucket coverage: `0.5019`.

- Bucket 1: labels `code, long-natural, structured`, coverage `1.0000`, experts `2, 18, 36, 38, 59, 95, 161, 164, 170, 191, 255`
- Bucket 2: labels `math`, coverage `0.5377`, experts `21, 41, 44, 61, 70, 95, 106, 140, 161, 166, 197, 207, 227, 243, 245, 250`
- Bucket 3: labels `repetitive`, coverage `0.4345`, experts `2, 44, 47, 54, 59, 61, 73, 81, 95, 155, 161, 171, 189, 197, 243, 255`

### Layer 21

Global K=16 coverage: `0.4212`; label-specific upper bound: `0.5019`; best bucket coverage: `0.5019`.

- Bucket 1: labels `code, long-natural, structured`, coverage `1.0000`, experts `2, 13, 38, 47, 73, 95, 102, 137, 161, 164, 170, 191, 197, 203, 207`
- Bucket 2: labels `math`, coverage `0.5516`, experts `6, 21, 44, 47, 61, 95, 106, 108, 131, 187, 197, 207, 227, 243, 245, 250`
- Bucket 3: labels `repetitive`, coverage `0.4206`, experts `2, 26, 44, 47, 53, 54, 61, 73, 95, 107, 137, 161, 170, 243, 246, 251`

### Layer 20

Global K=16 coverage: `0.4385`; label-specific upper bound: `0.5106`; best bucket coverage: `0.5106`.

- Bucket 1: labels `code, long-natural, structured`, coverage `1.0000`, experts `7, 52, 83, 99, 113, 115, 116, 151, 185, 186, 191, 224, 239`
- Bucket 2: labels `math`, coverage `0.5020`, experts `7, 41, 53, 72, 107, 110, 115, 117, 135, 151, 155, 171, 186, 191, 206, 224`
- Bucket 3: labels `repetitive`, coverage `0.4881`, experts `3, 11, 41, 110, 117, 127, 151, 175, 185, 186, 191, 205, 206, 224, 237, 239`

### Layer 14

Global K=16 coverage: `0.4231`; label-specific upper bound: `0.5010`; best bucket coverage: `0.5010`.

- Bucket 1: labels `code, long-natural, structured`, coverage `1.0000`, experts `32, 51, 52, 64, 103, 137, 148, 160, 189, 225`
- Bucket 2: labels `math`, coverage `0.5456`, experts `19, 51, 52, 54, 65, 67, 72, 76, 77, 137, 160, 189, 194, 225, 231, 255`
- Bucket 3: labels `repetitive`, coverage `0.4246`, experts `28, 29, 32, 52, 61, 64, 67, 103, 107, 125, 137, 160, 189, 194, 200, 215`

