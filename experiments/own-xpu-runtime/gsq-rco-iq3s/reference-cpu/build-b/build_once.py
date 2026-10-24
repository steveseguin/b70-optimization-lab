from pathlib import Path
import hashlib,importlib.util
P=Path(__file__).resolve().parent;D=P.parent/'build_once.py'
assert hashlib.sha256(D.read_bytes()).hexdigest()=='3abc159af0e3f67db2ff5141836a928c74a542f3a078dd33a6e64d4a7d65e835'
s=importlib.util.spec_from_file_location('cpu_reference_b_private_driver',D);M=importlib.util.module_from_spec(s);s.loader.exec_module(M);M.P=P
if __name__=='__main__':M.main()
