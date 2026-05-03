from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request):
    return {"message": "Success"}


@app.get("/products")
@limiter.limit("100/minute")
async def products(request: Request):
    return {"products": ["item1", "item2", "item3"]}


@app.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(request: Request):
    return {"message": "Password reset email sent"}
