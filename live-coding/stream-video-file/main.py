import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

VIDEO_PATH = "large_video.mp4"


def file_reader(path: str):
    with open(path, mode="rb") as f:
        while chunk := f.read(1024 * 1024):  # 1MB chunks
            yield chunk


@app.get("/video")
async def stream_video():
    return StreamingResponse(file_reader(VIDEO_PATH), media_type="video/mp4")
