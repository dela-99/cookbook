# Measure API Request Time

Track how long every API request takes — without touching your route logic.

## The Idea

Instead of adding timers to every endpoint, you write **one middleware** that wraps all requests automatically.

Here's what happens on every request:

1. Request comes in → middleware starts a timer
2. Request goes through your normal route logic
3. Response comes back → middleware stops the timer
4. The duration gets added to a response header (`X-Process-Time`)

That's it. Every single endpoint is now timed with zero extra code in your routes.

## Why `time.perf_counter()`?

- Higher precision than `time.time()`
- Monotonic (won't jump if the system clock updates)
- Built specifically for measuring durations

## Run

```bash
uv run uvicorn main:app --reload
```

## Test

```bash
curl -i http://localhost:8000/heavy-task
```

You'll see `X-Process-Time: 1.5003s` in the response headers and a log in your terminal.
