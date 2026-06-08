import requests

payload = {
  'text': 'Hello world testing one two three',
  'language': 'en',
  'emotion': 'neutral'
}

res = requests.post('http://localhost:8000/tts/synthesize', json=payload, timeout=10)
print(f'Status: {res.status_code}')
print(f'Content length: {len(res.content)} bytes')
print(f'Content-Type: {res.headers.get("Content-Type")}')
print(f'First 50 bytes (hex): {res.content[:50].hex()}')
print(f'WAV header: RIFF={res.content[0:4]}, WAVE={res.content[8:12]}')
print(f'WAV footer: data={res.content[-8:-4]}')

# Save to file for inspection
with open('test_output.wav', 'wb') as f:
    f.write(res.content)
print('Saved to test_output.wav')
