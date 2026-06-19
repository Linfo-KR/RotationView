import urllib.request
import json

url = "http://localhost:8000/api/routes?search=cbx&limit=1"
r = urllib.request.urlopen(url)
d = json.loads(r.read())
for x in d:
    geom = x.get('line_geometry', {})
    out = geom.get('outbound', [])
    inb = geom.get('inbound', [])
    print(f"route_idx: {x['route_idx']}")
    print(f"outbound segments: {len(out)}")
    print(f"inbound segments: {len(inb)}")
    if out:
        print(f"outbound[0] first point: {out[0][0] if out[0] else 'empty'}")
    if inb:
        print(f"inbound[0] first point: {inb[0][0] if inb[0] else 'empty'}")
