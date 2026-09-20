#!/usr/bin/env python3
"""Install only this skill's isolated geometry/CAD dependencies."""
from pathlib import Path
import subprocess
import venv
root = Path(__file__).resolve().parents[1]
environment = root / '.venv'
if not (environment / 'bin/python').exists():
    venv.EnvBuilder(with_pip=True).create(environment)
subprocess.run([str(environment/'bin/python'),'-m','pip','install','-r',str(root/'scripts/requirements.txt')],check=True)
print(f'技能环境已就绪：{environment}/bin/python')
