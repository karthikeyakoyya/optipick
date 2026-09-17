import json
import os

HERE = os.path.dirname(__file__)

with open(os.path.join(HERE, "trace.json")) as f:
    trace_json_text = f.read()

with open(os.path.join(HERE, "template.html")) as f:
    template = f.read()

output = template.replace("__TRACE_JSON__", trace_json_text)

with open(os.path.join(HERE, "index.html"), "w") as f:
    f.write(output)

print("wrote index.html")
