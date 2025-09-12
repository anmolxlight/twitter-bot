"""
Simple test endpoint for Vercel
"""

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from Vercel!", "status": "working"}

@app.get("/test")
def test_endpoint():
    return {"test": "success", "platform": "vercel"}

# For Vercel
def handler(request, response):
    return app(request, response)
