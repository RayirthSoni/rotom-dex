# Chat connection and prompt failures

Keep the local backend running while using the app:

```sh
uv run rotom serve --db data/build/rotom.sqlite3 --port 8000
```

Open `http://127.0.0.1:8000/`. If using the separate preview at port 8001, its server must also be running. Restart the process after backend edits; an open page can otherwise keep calling an older server. Refresh after frontend edits. Refreshing intentionally clears the tab-memory Gemini key, so reconnect afterward.

| Message | Meaning |
| --- | --- |
| Cannot reach the Rotom server | The backend is stopped or unreachable. This says nothing about key validity. |
| Google rejected this Gemini API key | Google's machine-readable response identifies an invalid/expired key. |
| Google denied access | Check the key's Gemini API permissions/restrictions. |
| Configured model is not available | Check the configured model and access for that project. |
| Service temporarily unavailable | Google returned a temporary server error after bounded retries. |
| Quota or rate limit reached | Google rejected the call with HTTP 429. Check the project's quota/billing or wait for the relevant limit to reset. Do not repeatedly retry. |
| Gemini did not respond within … | That provider call exhausted its allowed remaining time. A short value may be the remainder of the overall answer budget, not the full request timeout. |

A successful Connect verifies a small Gemini generation. A Pokémon prompt also needs tool selection, evidence retrieval and a checked answer, so it can fail separately. The stream reports those stages and ends with either an answer or an error. HTTP 200 on `/api/v2/chat/stream` only means the stream opened; it is not a success grade for the answer.

The common lookup path can now finish in two model calls via `submit_answer`. Quota errors are not automatically retried. Server diagnostics record completion/error type and elapsed time without keys, prompts or response text. Full live-answer verification remains pending if quota is exhausted; passing scripted tests does not remove that limit.

Google documents these upstream errors and bounded retries in its [Gemini troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting).
