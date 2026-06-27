# Route-Cache Device-Map Experiment (Negative)

Date: 2026-06-26 / 2026-06-27 UTC
Source tree: `/home/steve/src/llama.cpp-gemma-record-stack`

## Intent

Extend the existing default-off `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` host
route-plan reuse with a second default-off device row-map reuse knob:

```text
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP=1
```

The source audit found that an immediate route-cache hit still could allocate
and copy a routed row-map for the following matching `MUL_MAT_ID`. The
experiment kept the existing host route-cache match semantics but added a
persistent `mmid_row_mapping` device buffer to the route cache so a matching
immediate consumer could reuse the device map.

## Focused Source Changes

In `ggml/src/ggml-sycl/common.hpp`, the existing `mmid_route_cache` struct was
extended with a persistent device allocation:

```cpp
std::unique_ptr<ggml_sycl_pool_alloc<mmid_row_mapping>> dev_routed_row_src;
```

In `ggml/src/ggml-sycl/ggml-sycl.cpp`:

- added `ggml_sycl_mul_mat_id_route_cache_device_map_enabled()`, reading
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP`;
- in the multi-token `ggml_sycl_mul_mat_id` route-cache path, when an immediate
  route-cache hit had a matching persistent device map, use
  `route_cache.dev_routed_row_src->get()` and skip the second route-map memcpy;
- on route-cache miss, if the new knob is enabled, allocate/reallocate the
  persistent device map and copy the just-built host row map once, so the
  following immediate matching op can reuse it;
- default/fallback path remains unchanged when the knob is unset or `0`.

The full raw diff was intentionally not committed here because the llama.cpp
source tree already contains a large dirty Gemma patch stack in these files. A
plain `git diff` would mix this small experiment with unrelated source work.
Use the bullet list above plus the source tree if recovering the exact local
state is needed.

## Validation

Run:

```text
data/gemma4-q8-gpu0-routecache-devmap-screen-20260626T235013Z/summary.json
```

Result:

- canary: 128 repeats / 512 case rows, pass;
- cached tokens: `[0, 0, 0, 0]`;
- fresh row0: `103.5829642508525 tok/s`;
- support mean: `103.71749944929736 tok/s`;
- then-current record: `103.9826628154082 tok/s`.

Decision: valid negative. Keep the idea as a default-off artifact, but do not
enable it in promoted Gemma Q8 recipes. The remaining bottleneck is not this
final device row-map copy.
