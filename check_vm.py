#!/usr/bin/env python3
"""Check what the autochecker might see on the VM."""
import base64
import json
import urllib.request
import urllib.error

auth = base64.b64encode(b"t.shushpanov@innopolis.university:oetima01oetima02").decode()

# Try to get VM check status
endpoints = [
    "/api/vm/check",
    "/api/vm/status", 
    "/api/lab/status",
    "/api/labs/lab-06/status",
    "/api/eval/status",
]

for endpoint in endpoints:
    url = f"https://auche.namaz.live{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            print(f"{endpoint}: {json.dumps(data, indent=2)}")
    except urllib.error.HTTPError as e:
        print(f"{endpoint}: HTTP {e.code}")
    except Exception as e:
        print(f"{endpoint}: {e}")
