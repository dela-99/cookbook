# Measure API Request Time

How to track exactly how long every API request takes in production using custom middleware.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Test

```bash
curl -i http://localhost:8000/heavy-task
```

Check the `X-Process-Time` header in the response and the terminal output.
