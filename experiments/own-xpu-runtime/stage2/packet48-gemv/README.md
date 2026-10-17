# Packet 48: aligned decode GEMV weights

CPU preparation in progress; no device program has run. The coordinator owns
all device windows. Packet 47 and packet 45 are read-only dependencies or
separate work; this packet changes neither.

This independently written experiment separates compact expert weight fields
into aligned planes at load time. It keeps the 32 lane accumulators, eight
consecutive products per lane, increasing 256-value tiles, adjacent-pair tree,
BF16 outputs and error/status semantics. M=2 has independent input rows and
routes. Shared decoded weights never imply shared activations or outputs.

The experiment is an operator screen, not an engine integration or speed
record. Device byte gates and both fresh timing windows remain required.
See BYTE-CENSUS.md, PREREGISTRATION.md and WINDOW.md when preparation finishes.

Build budget: one serial compiler process, less than 512 MB of new disk
artifacts, CPU affinity 4–15,20–31 at nice 19. Generated synthetic weights
exist only in memory. No model payload, packet 47 tree, host setting, service,
or GPU is accessed during preparation.
