# Preparation closeout: strengthen generation restoration gate

The six-token diagnostic ended naturally after three generated tokens. Its
prefill restoration passed exactly, but its second checkpoint was terminal and
therefore did not exercise generation after restoration. Preserve that valid but
narrow proof as resume-equality-proof-short-eog.json. LONG-A had only begun prefill
and was stopped cooperatively before a checkpoint; no output oracle is claimed.

The replacement test uses the known incident prompt, stops in prefill after80
positions and in generation after90, then compares all eight generated tokens,
384 fixtures, eight ledgers and mid-prompt records to the first eight predictions
of the uninterrupted, sealed 4096-capacity incident run. It must generate four
tokens after the second restoration. The numerical binary is unchanged.
