"""Lock the installed dependency closure for the declared Python tooling."""
from importlib.metadata import distribution
from packaging.requirements import Requirement
from pathlib import Path
seen={}
def visit(name):
    dist=distribution(name);key=dist.metadata['Name'].lower().replace('_','-')
    if key in seen:return
    seen[key]=dist.version
    for raw in dist.requires or []:
        requirement=Requirement(raw)
        if requirement.marker and not requirement.marker.evaluate({'extra':''}):continue
        visit(requirement.name)
for name in ['genlayer-test','genvm-linter','pytest']:visit(name)
Path('requirements.lock').write_text('# Python 3.13+ tooling lock\n'+'\n'.join(name+'=='+version for name,version in sorted(seen.items()))+'\n')
print('Locked',len(seen),'Python packages.')
