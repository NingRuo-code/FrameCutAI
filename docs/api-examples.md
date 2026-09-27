# FrameCutAI API Examples

These examples assume the backend is running at `http://127.0.0.1:8000`.

## Upload

```powershell
$video = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/videos `
  -Form @{ file = Get-Item .\sample.mp4 }
$video.id
```

## Analyze

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/videos/$($video.id)/analyze"
```

## Status

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/videos/$($video.id)"
Invoke-RestMethod http://127.0.0.1:8000/videos
```

## Events

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/videos/$($video.id)/events/history"
```

The live progress stream is available as Server-Sent Events:

```text
GET /videos/{video_id}/events
```

## Document

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/videos/$($video.id)/document"
```

## VideoContext

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/videos/$($video.id)/context"
```

The response includes `context` and `provider_calls`, including latency,
input/output units, and estimated cost fields.

## Current-Video QA

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/videos/$($video.id)/qa" `
  -ContentType application/json `
  -Body (@{ question = "How does the video use FastAPI?" } | ConvertTo-Json)
```

QA history:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/videos/$($video.id)/qa/history"
```

## Eval

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/evals/run
```

The eval run writes a machine-readable JSON file and a Markdown report under
local storage.

## Cleanup

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri "http://127.0.0.1:8000/videos/$($video.id)"
```
