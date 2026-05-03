import time
import asyncio
from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    # Start the timer
    start_time = time.perf_counter()

    # Process the request and get the response
    response = await call_next(request)

    # Calculate the duration
    process_time = time.perf_counter() - start_time

    # Add it to a custom header so the client can see it
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"

    print(f"🚀 Request to {request.url.path} took {process_time:.4f}s")
    return response


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/heavy-task")
async def heavy_task():
    await asyncio.sleep(1.5)
    return {"message": "Task complete"}
