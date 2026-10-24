"""Private metadata-admission overlay; no arithmetic implementation or frozen edits."""
from pathlib import Path
import difflib, hashlib, json
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
S2=ROOT/'experiments/own-xpu-runtime/stage2'
FILES=('packet3/step/plan.hpp','packet3/model/directory.hpp','packet3/kernels/api.hpp','packet2/kernels/math.hpp','packet2/kernels/grids.hpp')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def overlay():
    pins=json.loads((P/'parent-pins.json').read_text())
    for path,want in pins.items():
        if sha(ROOT/path)!=want:raise ValueError('parent changed: '+path)
    changes=[];result={}
    for name in FILES:
        source=S2/name;text=source.read_text();updated=text
        if name.endswith('math.hpp'):
            updated=updated.replace('#include <bit>','#include <bit>\n#include <stdexcept>')
            updated=updated.replace('Q3_K=11,Q6_K=14,','Q3_K=11,Q4_K=12,Q5_K=13,Q6_K=14,')
            updated=updated.replace('IQ2_S=22,BF16=30','IQ2_S=22,IQ4_XS=23,BF16=30,Q2_0=42')
            updated=updated.replace('case Type::Q6_K:return {256,210};','case Type::Q4_K:return {256,144}; case Type::Q5_K:return {256,176};\n    case Type::IQ4_XS:return {256,136}; case Type::Q2_0:return {64,18};\n    case Type::Q6_K:return {256,210};')
            updated=updated.replace('inline float decode(Type t,const uint8_t* b,uint32_t i) {','inline float decode(Type t,const uint8_t* b,uint32_t i) {\n  if(t==Type::Q4_K||t==Type::Q5_K||t==Type::IQ4_XS||t==Type::Q2_0)\n    throw std::logic_error("graph-only added format: numeric execution forbidden");')
        elif name.endswith('directory.hpp'):
            extra=['F16','IQ3_XXS','Q4_K','Q5_K','IQ4_XS','Q2_0']
            updated=updated.replace('  default:\n', ''.join('  case Type::'+t+': return "'+t+'";\n' for t in extra)+'  default:\n',1)
            updated=updated.replace('Type::IQ3_S, Type::IQ4_NL})','Type::IQ3_S, Type::IQ4_NL, '+', '.join('Type::'+t for t in extra)+'})')
        target=P/'build/private'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(updated)
        result[str(target.relative_to(ROOT))]=sha(target)
        changes.extend(difflib.unified_diff(text.splitlines(True),updated.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
    patch=''.join(changes)
    (P/'overlay.patch').write_text(patch)
    record={'schema':'ownrt.gsq-rco.graph-overlay.v1','native_admitted':False,'numeric_execution':False,'parent_sha256':pins,'private_sha256':result,'patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'scope':'Only type enum/layout/name admission changes; added decoder paths explicitly throw. Actual packet3 graph topology/geometry untouched.'}
    (P/'overlay.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':overlay()
