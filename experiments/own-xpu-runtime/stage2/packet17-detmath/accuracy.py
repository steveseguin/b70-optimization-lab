#!/usr/bin/env python3
"""Independent 100-decimal-digit recomputation of sampled worst vectors.

The C++ checker supplies bit-pattern inputs and outputs, not its reference value.
Decimal exp/ln have independently rounded arbitrary-precision implementations.
"""
import argparse
import decimal
import json
import pathlib
import struct

def binary32(bits):
    return struct.unpack("<f", struct.pack("<I", int(bits, 16)))[0]

def verify(path):
    data = json.loads(path.read_text())
    rows = []
    with decimal.localcontext() as ctx:
        ctx.prec = 100
        D = decimal.Decimal
        two = D(2)
        for function in ("exp", "log"):
            stats = data[function]
            x = D.from_float(binary32(stats["worst_input_bits"]))
            got = D.from_float(binary32(stats["worst_output_bits"]))
            reference = x.exp() if function == "exp" else x.ln()
            spacing = two ** -149
            if abs(reference) >= two ** -126:
                # Output may sit at a binade edge: determine true-reference binade.
                exponent = int(abs(reference).ln() / two.ln())
                while two ** exponent > abs(reference):
                    exponent -= 1
                while two ** (exponent + 1) <= abs(reference):
                    exponent += 1
                spacing = two ** (exponent - 23)
            error = abs(got - reference) / spacing
            rows.append({"function": function,
                         "input_bits": stats["worst_input_bits"],
                         "output_bits": stats["worst_output_bits"],
                         "input_exact": str(x), "reference_100_digits": str(reference),
                         "true_ulp_error": str(error), "at_most_one_ulp": error <= 1})
    return {"reference": "Python standard-library Decimal exp/ln, precision 100",
            "scope": "Worst vectors from sampled long-double checker; not a whole-domain proof",
            "rows": rows}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=pathlib.Path(__file__).with_name("accuracy-results.json"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path(__file__).with_name("accuracy-high-precision.json"))
    args = parser.parse_args()
    result = verify(args.input)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
