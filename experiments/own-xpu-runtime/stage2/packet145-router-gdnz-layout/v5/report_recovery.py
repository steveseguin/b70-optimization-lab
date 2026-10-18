"""CPU report replay for completed packet145 windows, either lane."""
from common import HERE,read,require,sha
def recover(args):
 output=args.output.resolve();suffix='smoke' if args.kind=='smoke' else 'v5'
 require(output==HERE/'evidence'/('device-'+args.variant+'-'+suffix+'-'+args.lane),'registered lane output required')
 window=read(output/'window.json');identity=read(output/'identity.json')
 require(identity['lane']==args.lane and identity['bracket']['kind']==args.kind,'lane/kind mismatch')
 require(window.get('device_complete') and window.get('device_executed') and window.get('lease_released') and not window.get('stop_reasons') and not window.get('child_still_running'),'complete released device work required')
 require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json'),'execution seal changed')
 for name,digest in window['files'].items():require(sha(output/name)==digest,'retained evidence changed')
 from screen import report_completed
 report_completed(output,window,identity,read(output/'lane-coordination.json'));return 0
def recovered_window(*args):
 raise ValueError('packet142 recovery receipts do not authorize packet145')
