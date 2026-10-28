#!/usr/bin/env python3
"""Research-only relink; never edits canonical sources or original build outputs."""
import argparse,copy,hashlib,json,pathlib,subprocess,time

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--receipt',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True);x=a.parse_args()
 r=json.loads(x.receipt.read_text());assert r['binary_sha256']=='d0c333550717a97b730de121878fc869313a843f8d5daed84d73b218957faea0'
 assert sha(r['binary'])==r['binary_sha256'];root=x.receipt.parent
 for n,h in r['objects'].items():assert sha(root/n)==h,(n,'object changed')
 source_root=pathlib.Path(__file__).resolve().parents[4]/'engine/src'
 for n,h in r['sources'].items():assert sha(source_root/n)==h,(n,'source changed')
 x.output.mkdir(parents=False,exist_ok=False);binary=x.output/'sc117-engine';cmd=list(r['commands']['link']['cmd']);i=cmd.index('-o');cmd[i+1]=str(binary)
 flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'];assert not any(f in cmd for f in flags)
 cmd[1:1]=flags;t=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True)
 (x.output/'link.stdout').write_text(p.stdout);(x.output/'link.stderr').write_text(p.stderr)
 result={'cmd':cmd,'rc':p.returncode,'stderr':p.stderr,'seconds':time.monotonic()-t};(x.output/'link-result.json').write_text(json.dumps(result,indent=2));assert p.returncode==0,'failed relink preserved'
 for n,h in r['objects'].items():assert sha(root/n)==h
 new=copy.deepcopy(r);new.update(binary=str(binary),binary_sha256=sha(binary));new['commands']['link']=result
 new['research_relink']={'original_receipt':str(x.receipt.resolve()),'original_receipt_sha256':sha(x.receipt),'original_binary_sha256':r['binary_sha256'],'same_objects':True,'added_link_flags':flags,'helper_sha256':sha(__file__),'arithmetic_identity_changed':True,'canonical_defaults_changed':False}
 (x.output/'build-receipt.json').write_text(json.dumps(new,indent=2)+'\n');print(json.dumps({'binary_sha256':new['binary_sha256'],'receipt':str(x.output/'build-receipt.json')}))
if __name__=='__main__':main()
