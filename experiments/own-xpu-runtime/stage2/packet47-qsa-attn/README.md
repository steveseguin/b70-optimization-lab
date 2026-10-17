# Packet47: QSA decode attention

CPU preparation in progress. No GPU has been used. This standalone packet
keeps packet45, packet46 and their record oracles unchanged.

The [preregistration](PREREGISTRATION.md) fixes the one-card context/M matrix,
exactness gates, 3x attention bar and conditional end-to-end estimate. Device
windows are coordinator-owned and must not run until the final seal passes.
