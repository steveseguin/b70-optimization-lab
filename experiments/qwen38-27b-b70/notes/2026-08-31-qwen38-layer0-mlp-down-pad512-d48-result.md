# Qwen3.8 layer-0 MLP down M=512 D48 result

D48 passes the arithmetic repair boundary. Across four fresh processes, MLP
input, gate/up output, activation, and the complete 71-row M=512-padded down
projection output were all byte-identical. The full trace JSON was identical
4/4; the repaired down output SHA-256 was
`fd395a9f649e8f9b30727fc84a8fd90fe56d66271c0dbfb07dcc01770bf1091d`.

The full response still first differed at generated token index 60 because D48
changed only layer 0. This does not fail the isolated boundary. D49 applies the
same synchronized, prefill-only down treatment to every dense MLP in the model
and tests complete outputs across four fresh processes. Decode shapes remain
outside the branch.
