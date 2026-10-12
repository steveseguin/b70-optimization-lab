# Packet 37: do not repeat

Packet32's ownership and arithmetic restrictions still apply. Preserve its
negative history under the source packet.

| Closed mistake | Required behavior |
| --- | --- |
| Swap state buffers without command vectors | Swap buffers, prepared maps and captured vectors together after drain. |
| Clone-only prepared argument audit | Rebuild the operation from current plan/buffers and compare with the actual selected capture. |
| Port only packet35's two-device backend | Pipeline ranks use the local single-owner backend. |
| Per-launch literal converted to std::string | Construct failure text only on failure. |
| Fusion compared with one member or only on conflicts | Compare every measured fusion against the selected members' sum at every site/format; tie selects members. |
| Price HC from only the attention site | Check both attention and FFN low+inject costs. |
| Read old faults as a new fault | Latch only new lines after the wrapper's own cursor. |
| Latch admission refusal | No fault latch before the first child launch. |
| Substitute a library-path fallback | Forward the coordinator's LD_LIBRARY_PATH unchanged. |
| Store pathlib.Path in JSON | Serialize paths explicitly as strings. |
| Treat CPU/mock timing or all-hit guesses as model speed | Coordinator model windows only; all-hit remains diagnostic. |
| Compare scalar F32 split1 with split4 | Preserve each class's registered serial/reduction tree. |
| Qualify inherited expert NaNs by tolerance | Keep diagnostics separate, with exact required gates unchanged. |
