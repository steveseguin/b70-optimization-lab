#pragma once
// Only the historical timing TU consumes these defaults in this normal Host
// Engine closure. No fixture-only validation wrapper or synthetic arithmetic
// is installed. GSQ admission rejects record/diagnostic entry modes.
namespace fixture_validation { inline bool only=false,poison_dense=false,inject=false; }
