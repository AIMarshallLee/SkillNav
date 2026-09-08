import json,sys
from pathlib import Path
mode,request_file,service_file=sys.argv[1:]
request=json.loads(Path(request_file).read_text())
p=Path(service_file)
objects=json.loads(p.read_text()) if p.exists() else []
if mode=='create':
 objects.append({'request_id':request['request_id'],'object_id':'object-'+str(len(objects)+1)})
 p.write_text(json.dumps(objects))
 print('Timeout waiting for acknowledgement',file=sys.stderr)
 raise SystemExit(75)
if mode=='status':
 print(json.dumps({'matches':[o for o in objects if o['request_id']==request['request_id']], 'total_objects':len(objects)}))
else:
 raise SystemExit(2)
