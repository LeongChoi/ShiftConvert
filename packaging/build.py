"""Assemble Windows payload from official embedded Python and Windows wheels.
Run from the directory containing shiftconvert/ and build-cache/.
"""
from pathlib import Path
import zipfile,shutil,hashlib,json
root=Path(__file__).resolve().parents[1]
cache=root.parent/'build-cache'
payload=root.parent/'windows-payload'
if payload.exists(): shutil.rmtree(payload)
runtime=payload/'runtime'; runtime.mkdir(parents=True)
with zipfile.ZipFile(cache/'python-embed.zip') as z: z.extractall(runtime)
site=runtime/'Lib'/'site-packages'; site.mkdir(parents=True)
versions=[]; inputs={}
for p in sorted((cache/'wheels').glob('*.whl')):
 inputs[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 with zipfile.ZipFile(p) as z:
  # Wheel RECORD is retained. No installation hooks or scripts are executed.
  for name in z.namelist():
   if name.endswith('/'): continue
   parts=Path(name).parts
   if '..' in parts or Path(name).is_absolute(): raise ValueError(name)
   if parts[0].endswith('.data'):
    if len(parts)<3 or parts[1] not in ('purelib','platlib'): continue
    target=site.joinpath(*parts[2:])
   else: target=site/name
   target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(name))
  meta=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')][0]
  text=z.read(meta).decode()
  pkg=next(l[6:] for l in text.splitlines() if l.startswith('Name: '))
  ver=next(l[9:] for l in text.splitlines() if l.startswith('Version: '))
  versions.append(f'{pkg}=={ver}')
# Isolated Python paths. Do not depend on a system Python or user's PYTHONPATH.
(runtime/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n..\nimport site\n')
shutil.copytree(root/'shiftconvert',payload/'shiftconvert',ignore=shutil.ignore_patterns('__pycache__'))
for name in ['launch.pyw','START_HERE.html','LICENSE']: shutil.copy2(root/name,payload/name)
lock='\n'.join(versions)+'\n'; (root/'requirements-windows-lock.txt').write_text(lock)
inputs['python-embed.zip']=hashlib.sha256((cache/'python-embed.zip').read_bytes()).hexdigest()
(root/'packaging'/'input-sha256.json').write_text(json.dumps(inputs,indent=2))
shutil.copytree(root,payload/'source',ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
# Include shared VC runtime DLLs next to pythonw for libraries which load them before Qt.
for dll in (site/'PySide6').glob('*140*.dll'):
 if not (runtime/dll.name).exists(): shutil.copy2(dll,runtime/dll.name)
print('Payload:',payload)
print('Bytes:',sum(p.stat().st_size for p in payload.rglob('*') if p.is_file()))
