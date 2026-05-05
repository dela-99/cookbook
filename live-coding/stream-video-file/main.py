from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI()

VIDEO_PATH = Path(__file__).parent / "large_video.mp4"
CHUNK_SIZE = 1024 * 1024  # 1MB


def file_reader(path: Path, start: int, end: int):
    with open(path, mode="rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@app.get("/video")
async def stream_video(range: str | None = Header(default=None)):
    if not VIDEO_PATH.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    file_size = VIDEO_PATH.stat().st_size

    # No Range header → stream the whole file from the start
    if range is None:
        return StreamingResponse(
            file_reader(VIDEO_PATH, 0, file_size - 1),
            media_type="video/mp4",
            headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
        )

    # Range header looks like: "bytes=START-END" (END is optional)
    start_str, _, end_str = range.replace("bytes=", "").partition("-")
    start = int(start_str)
    end = int(end_str) if end_str else file_size - 1

    return StreamingResponse(
        file_reader(VIDEO_PATH, start, end),
        status_code=206,  # Partial Content
        media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        },
    )
