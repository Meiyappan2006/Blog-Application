import urllib.request
import json
api_key = "AIzaSyAveARsqU7eR4l_QWGH4ipPcAop9MB6aiQ"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        print("Models supporting generateContent:")
        for m in models:
            print(m)
except Exception as e:
    print("Error:", e)
