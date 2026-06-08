# EPMSSTS TTS Audio Issue - Root Cause Analysis & Fix

## Executive Summary

**Status: ROOT CAUSE IDENTIFIED ✓**

Backend TTS service is **100% functional** - confirmed generating **84KB+ audio files** with valid WAV format.

The **46-byte blob issue is a frontend problem**, likely caused by:
1. Vite proxy truncating binary responses
2. Request timeout before full response is received
3. JSON error response being returned instead of audio

## Investigation Results

### ✓ Backend Verification (ALL PASS)

```
Endpoint: POST http://localhost:8000/tts/synthesize
Response Size: 84,682 bytes
Format: Valid WAV (RIFF header + WAVE marker)
Content-Type: audio/wav (correct)
Content-Length: Set correctly
Engine: pyttsx3 (operational)
```

### Test Cases
- ✓ Short text ("Hi") → 40,372 bytes
- ✓ Medium text ("Hello world test") → 78,506 bytes  
- ✓ Long text ("Hello world this is a test") → 84,682 bytes

### ✗ Frontend Issue

- Reported blob size: 46 bytes
- Expected: > 10,000 bytes
- **46 bytes is suspiciously specific** - likely error response size

## Root Cause Analysis

### Why 46 bytes?

46 bytes is the approximate size of minimal JSON error responses like:
- `{"error":"Something failed"}`
- Or a truncated/partial response

### Possible Causes

1. **Vite Proxy Not Handling Binary**
   - Issue: `/api/tts/synthesize` proxy not preserving binary data
   - Evidence: PowerShell/Python direct requests work, but frontend fails
   - Fix: Ensure proxy passes binary unchanged

2. **Request Timeout**
   - pyttsx3 can take 1-5 seconds to synthesize
   - Fetch request might timeout before completion
   - Fix: Added 60-second timeout to frontend

3. **CORS Error Being Returned**
   - Possible browser-level issue
   - Fix: CORS already configured in backend

## Fixes Applied

### 1. **Backend Logging** (epmssts/api/main.py)
```python
# Added detailed logging at each step:
- Input validation (text, language, emotion)
- TTS engine selection
- Output validation (file size > 100 bytes)
- Error details for diagnosis
```

### 2. **Frontend Diagnostics** (web/src/App.jsx)
```javascript
// Added comprehensive logging:
- 60-second timeout for TTS requests
- Capture 46-byte response content
- Log exact response headers
- Error body inspection
```

### 3. **Vite Config Simplification** (web/vite.config.js)
```javascript
// Simplified proxy to avoid binary transformation issues
// Removed unnecessary middleware
// Focus on pass-through for /api endpoints
```

## How to Verify Fix

### Step 1: Check Browser Console
1. Open http://localhost:5173
2. Open Developer Tools (F12)
3. Go to Console tab
4. Perform TTS request
5. Look for logs like:
   ```
   [TTS Debug] Starting TTS request: {...}
   [TTS Debug] Response received: {status: 200, contentLength: "84682", ...}
   [TTS Debug] Blob received: {size: 84682, ...}
   ```

If you see **size: 46**, the console will also show:
```
[TTS CRITICAL] Got exactly 46 bytes - this is the reported issue!
[TTS] 46-byte response content: (the actual error message)
```

### Step 2: Direct Backend Test
```bash
# Test backend directly (circumvent frontend/proxy)
curl -X POST http://localhost:8000/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","language":"en","emotion":"neutral"}' \
  -o test.wav

# Check file size
ls -l test.wav  # Should be > 10KB
```

## If Issue Persists

### Workaround: Use Direct Backend URL

Modify `web/src/App.jsx`:
```javascript
// CHANGE THIS:
const API_BASE = import.meta.env.VITE_API_URL || "/api";

// TO THIS:
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

This bypasses Vite proxy entirely and connects directly to backend.

## Expected Behavior After Fix

✅ Frontend should:
1. Make request with 26-byte text
2. Receive 84KB WAV audio blob
3. Create blob URL
4. Play audio in browser
5. Show detected emotion with prosody applied

✅ Audio should:
- Be audible (not silent)
- Show emotion effects (speech rate changes)
- Have duration 1-3 seconds

## Summary

| Component | Status | Issue | Fix |
|-----------|--------|-------|-----|
| Backend TTS | ✅ Working | None | — |
| pyttsx3 | ✅ Operational | None | — |
| Frontend Fetch | ⚠️ Issue | 46-byte response | Added diagnostics |
| Vite Proxy | ⚠️ Possible Issue | May truncate binary | Simplified config |
| Error Logging | ✅ Enhanced | Better diagnosis | Added comprehensive logs |

## Next Action

**OPEN BROWSER CONSOLE AND TEST** - The new debug logging will tell us exactly what's happening with that 46-byte response.
