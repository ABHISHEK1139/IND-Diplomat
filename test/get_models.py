import urllib.request
import json
import ssl

from test._support import script_log_path

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "MyAgent"})
with urllib.request.urlopen(req, context=ctx) as r:
    data = json.loads(r.read())["data"]

free_models = []
for m in data:
    id = m.get("id", "")
    if ":free" in id:
        free_models.append(f"{id} | Context: {m.get('context_length')}")

with open(script_log_path("openrouter_models.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(free_models))
