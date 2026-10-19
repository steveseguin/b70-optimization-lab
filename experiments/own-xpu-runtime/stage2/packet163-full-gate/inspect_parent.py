import json, pathlib, resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
S=pathlib.Path(__file__).resolve().parents[1]
for lane, p, chain in [('two','packet136-record-bundle','build/device-cards01-a/WS128'),('one','packet58aj-onecard-resident','')]:
 root=S/p
 if lane=='two':
  w=json.loads((root/chain/'window.json').read_text())
  print('two window', {k:v for k,v in w.items() if k in ('command','native_command','selection_sha256','binary_sha256','native_files','selection','env','environment')})
  for f in (root/chain/'run').rglob('*launch.json'):
   r=json.loads(f.read_text()); print('launch',f, r.get('argv'))
 print('receipt artifacts',p, {k:v for k,v in json.loads((root/'build-receipt.json').read_text()).items() if k in ('artifacts','artifacts_sha256')})
 print('selection files', [(str(f.relative_to(root)), f.stat().st_size) for f in root.rglob('selection.json') if 'build' not in f.parts][:15])
print('one evidence directories',list((S/'packet58aj-onecard-resident/evidence').iterdir()))
