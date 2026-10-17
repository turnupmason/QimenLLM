#!/usr/bin/env python3
"""Portable non-secret host probe. Does not connect to another machine or load model weights."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def command(args):
    if not shutil.which(args[0]): return {'available':False}
    result=subprocess.run(args,capture_output=True,text=True,timeout=15)
    return {'available':True,'returncode':result.returncode,'stdout':result.stdout.strip()}


def main():
    info={'os':platform.platform(),'architecture':platform.machine(),'cpu_count':os.cpu_count(),
          'python':sys.version,'python_executable':sys.executable,'cwd':str(Path.cwd()),
          'git':command(['git','--version']),'disk_bytes':shutil.disk_usage('.')._asdict(),
          'nvidia':command(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'])}
    if Path('/proc/meminfo').exists():
        info['memory']=next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    elif platform.system()=='Darwin':
        info['memory']=command(['sysctl','-n','hw.memsize'])
        info['chip']=command(['sysctl','-n','machdep.cpu.brand_string'])
    else: info['memory']='Not detected; collect OS-specific report before training'
    for name in ('memory.max','cpu.max'):
        path=Path('/sys/fs/cgroup')/name
        if path.exists(): info['cgroup_'+name]=path.read_text().strip()
    info['torch']='Not imported; verify CUDA/PyTorch separately on the actual training host'
    print(json.dumps(info,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
