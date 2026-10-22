"""Check immutable packet files, without model reads or device access."""
from common import HERE,read,require,sha

def verify():
 pins=read(HERE/'seal.json')
 require(pins['arithmetic']=='iq3-p49-split32-v1','seal arithmetic')
 for name,expected in pins['files'].items():
  path=HERE/name
  require(path.resolve().is_relative_to(HERE),'seal escapes private packet')
  require(sha(path)==expected,'sealed packet file changed: '+name)
 native=read(HERE/'inherited-native.json')
 from common import ROOT
 for name,expected in native['embedded_readonly_dependencies'].items():
  require(sha(ROOT/name)==expected,'frozen embedded native dependency changed: '+name)
 return pins
