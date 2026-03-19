import urllib.request
import json
api_key = "AIzaSyAveARsqU7eR4l_QWGH4ipPcAop9MB6aiQ"
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
payload = {
    "contents": [{"parts": [{"text": "Write a short poem about a cat."}]}]
}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        print("Success with gemini-1.5-flash")
except Exception as e:
    print("Failed with gemini-1.5-flash:", e)
    if hasattr(e, 'read'):
        print(e.read().decode())
