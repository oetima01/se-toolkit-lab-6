#!/usr/bin/env python3
import base64
import json
import urllib.request

auth = base64.b64encode(b"t.shushpanov@innopolis.university:oetima01oetima02").decode()

# Try to get lab status
req = urllib.request.Request(
    "https://auche.namaz.live/api/labs",
    headers={"Authorization": f"Basic {auth}"}
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
