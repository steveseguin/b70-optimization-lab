"""CPU report replay for completed packet188 rows, either lane."""
from common import HERE,read,require,sha
def recover(args):
 from p194_v5_compare import row_output
 output=args.output.resolve()
 require(output==row_output(args.index,args.lane),'registered lane/row output required')
 window=read(output/'window.json');identity=read(output/'identity.json')
 require(identity['lane']==args.lane and identity['bracket']['kind']==args.kind and identity['bracket']['row_index']==args.index,'lane/kind/row mismatch')
 require(window.get('device_complete') and window.get('device_executed') and window.get('lease_released') and not window.get('stop_reasons') and not window.get('child_still_running'),'complete released device work required')
 require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json'),'execution seal changed')
 for name,digest in window['files'].items():require(sha(output/name)==digest,'retained evidence changed')
 from screen import report_completed
 report_completed(output,window,identity,read(output/'lane-coordination.json'));return 0
def recovered_window(*args):
 raise ValueError('packet142 recovery receipts do not authorize packet188')
