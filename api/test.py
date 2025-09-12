"""
Simple test endpoint for Vercel with proper ASGI handler
"""

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from Vercel!", "status": "working"}

@app.get("/test")
def test_endpoint():
    return {"test": "success", "platform": "vercel"}

@app.get("/health")
def health():
    return {"status": "healthy", "platform": "vercel"}

# This is the correct way to export for Vercel
# Vercel will automatically handle the ASGI interface