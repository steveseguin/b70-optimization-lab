from pathlib import Path
P=Path(__file__).resolve().parents[1]
ROOT=P.parents[3]
def check_pins(root,pins):
    assert isinstance(pins,dict) and pins
    oracle=__import__("json").loads((P/"oracle-binding.json").read_text())["files_sha256"]
    for n,h in pins.items():
        p=(root/n).resolve()
        assert p.is_relative_to(P) or oracle.get(str(p.relative_to(ROOT)))==h,(n,"external mutable pin")
