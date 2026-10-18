"""Package every epoch adapter plus latest resumable checkpoint for Release upload.

No network mutation here. Real upload/download verification must produce a
separate receipt; local zip creation never counts as GitHub success.
"""
import argparse,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'training'))
from epoch_protocol import sha
from cache_mac_curriculum import write

def package(run,receipt):
 report=json.loads(receipt.read_bytes());latest=json.loads((run/'latest.json').read_bytes())['checkpoint'];archive=run/f'{run.name}-through-{latest}.zip'
 if archive.exists():raise FileExistsError('Version model archives')
 dirs=sorted(p for p in run.glob('epoch-*') if p.is_dir());dest=run/latest
 if dest not in dirs:dirs.append(dest)
 names=[]
 for directory in dirs:
  s=json.loads((directory/'state.json').read_bytes())
  for n,digest in s['files'].items():
   if sha(directory/n)!=digest:raise ValueError('Checkpoint changed')
  chosen=['adapters.safetensors','adapter_config.json','state.json']
  if directory==dest:chosen+=['tail-adapters.safetensors','optimizer.npz','rng.npz']
  names.extend(directory/n for n in chosen)
 names.extend([run/'identity.json',run/'latest.json',receipt]);manifest={str(p.relative_to(run)):sha(p) for p in names}
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
  for p in names:z.write(p,str(p.relative_to(run)))
  z.writestr('ARCHIVE_FILE_HASHES.json',json.dumps(manifest,sort_keys=True))
 with zipfile.ZipFile(archive) as z:
  import hashlib
  if any(hashlib.sha256(z.read(n)).hexdigest()!=h for n,h in manifest.items()):raise ValueError('Archive roundtrip differs')
 record={'scope':'local_model_package_not_upload','archive':str(archive),'archive_sha256':sha(archive),'bytes':archive.stat().st_size,'files':manifest,'checkpoint':latest,'epochs':report['completed_epochs'],'optimizer_steps':report['optimizer_steps'],'github_upload_status':'pending_normal_authenticated_release_upload','professional_pass':False};write(archive.with_suffix('.json'),record);return record
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();print(json.dumps(package(a.run,a.receipt)))
