import urllib.request
import json
import sys

req = urllib.request.Request(
    'http://localhost:8000/api/assess',
    data=json.dumps({'query':'Assess recent military movements near the border', 'country':'IND'}).encode('utf-8'),
    headers={'Content-Type':'application/json'}
)

try:
    res = urllib.request.urlopen(req)
    data = res.read().decode('utf-8')
    with open("api_response.json", "w", encoding="utf-8") as f:
        f.write(data)
    print("Response saved to api_response.json")
except Exception as e:
    print("Error:", e)
