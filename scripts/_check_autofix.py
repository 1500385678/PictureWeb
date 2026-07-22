import json
import os
import sys
import urllib.request

TOKEN = os.environ.get('GH_TOKEN', '')
if not TOKEN:
    sys.exit('GH_TOKEN 未设')

req = urllib.request.Request(
    'https://api.github.com/repos/1500385678/PictureWebWorkflowtest/issues?state=open&labels=auto-fix&per_page=20',
    headers={'Authorization': 'token ' + TOKEN, 'Accept': 'application/vnd.github+json'}
)
with urllib.request.urlopen(req, timeout=10) as r:
    issues = json.loads(r.read())
print(f'共 {len(issues)} 个 auto-fix issue:')
for i in issues:
    n = i['number']
    st = i['state']
    labels = [l['name'] for l in i['labels']]
    title = i['title'][:60]
    print(f'  #{n} state={st} labels={labels} title={title}')
