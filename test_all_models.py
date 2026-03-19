import os
import django
import json
import urllib.request

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()
from django.conf import settings

api_key = getattr(settings, 'GEMINI_API_KEY', '')

models_to_test = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro-latest", "gemini-flash-latest"]

for model in models_to_test:
    print(f"--- Testing Model: {model} ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": "Success?"}]}]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            print(f"RESULT: SUCCESS for {model}")
            break
    except Exception as e:
        status = getattr(e, 'code', 'Unknown')
        print(f"RESULT: FAILED for {model} (Status: {status})")
        if hasattr(e, 'read'):
            details = json.loads(e.read().decode())
            print(f"MESSAGE: {details.get('error', {}).get('message', 'No message')}")
