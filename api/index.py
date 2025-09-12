"""
Vercel Serverless Function Entry Point for AI Twitter Bot
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure simple logging for serverless
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Twitter Bot",
    description="Serverless Twitter bot powered by Gemini AI",
    version="1.0.0"
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Twitter Bot is running",
        "status": "healthy",
        "platform": "vercel"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Import here to avoid startup issues
        from src.twitter_client import get_client
        from src.tweet_generator import get_tweet
        
        health_data = {
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "environment": os.getenv("VERCEL_ENV", "development"),
            "components": {}
        }
        
        # Check Twitter client
        try:
            client = get_client()
            account_info = client.get_account_info()
            health_data["components"]["twitter"] = "healthy" if account_info else "unhealthy"
        except Exception as e:
            health_data["components"]["twitter"] = f"error: {str(e)}"
            logger.error(f"Twitter health check failed: {e}")
        
        # Check Gemini AI
        try:
            test_tweet = get_tweet()
            health_data["components"]["gemini"] = "healthy" if len(test_tweet) > 0 else "unhealthy"
        except Exception as e:
            health_data["components"]["gemini"] = f"error: {str(e)}"
            logger.error(f"Gemini health check failed: {e}")
        
        # Determine overall status
        unhealthy_checks = [k for k, v in health_data["components"].items() if "error" in str(v) or v == "unhealthy"]
        if unhealthy_checks:
            health_data["status"] = "degraded"
            health_data["unhealthy_components"] = unhealthy_checks
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }

@app.post("/api/trigger-tweet")
@app.get("/api/trigger-tweet")
async def trigger_tweet():
    """Manually trigger a tweet"""
    try:
        logger.info("Tweet trigger requested")
        
        # Import here to avoid startup issues
        from src.tweet_generator import get_tweet
        from src.twitter_client import post_tweet
        
        # Generate tweet
        tweet_content = get_tweet()
        logger.info(f"Generated tweet: {tweet_content[:50]}...")
        
        # Post tweet
        tweet_id = post_tweet(tweet_content)
        
        if tweet_id:
            logger.info(f"Tweet posted successfully with ID: {tweet_id}")
            return {
                "success": True,
                "tweet_id": tweet_id,
                "content": tweet_content,
                "timestamp": asyncio.get_event_loop().time()
            }
        else:
            logger.error("Failed to post tweet")
            return {
                "success": False,
                "error": "Failed to post tweet",
                "timestamp": asyncio.get_event_loop().time()
            }
            
    except Exception as e:
        logger.error(f"Tweet error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }

@app.post("/api/cron/tweet")
@app.get("/api/cron/tweet")
async def cron_tweet():
    """Cron endpoint for automatic tweet posting"""
    try:
        logger.info("Cron tweet endpoint triggered")
        
        # Import here to avoid startup issues
        from src.tweet_generator import get_tweet
        from src.twitter_client import post_tweet
        
        # Generate tweet
        tweet_content = get_tweet()
        logger.info(f"Generated tweet: {tweet_content[:50]}...")
        
        # Post tweet
        tweet_id = post_tweet(tweet_content)
        
        if tweet_id:
            logger.info(f"Cron tweet posted successfully with ID: {tweet_id}")
            return {
                "success": True,
                "tweet_id": tweet_id,
                "content": tweet_content,
                "timestamp": asyncio.get_event_loop().time(),
                "triggered_by": "cron"
            }
        else:
            logger.error("Cron tweet posting failed")
            return {
                "success": False,
                "error": "Failed to post tweet",
                "timestamp": asyncio.get_event_loop().time(),
                "triggered_by": "cron"
            }
            
    except Exception as e:
        logger.error(f"Cron tweet error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time(),
            "triggered_by": "cron"
        }

@app.post("/api/cron/health")
@app.get("/api/cron/health")
async def cron_health():
    """Cron endpoint for health monitoring"""
    return await health_check()

@app.get("/api/ping")
async def ping():
    """Simple ping endpoint"""
    return {
        "ping": "pong",
        "timestamp": asyncio.get_event_loop().time(),
        "platform": "vercel"
    }

# For external cron services
@app.post("/api/external/tweet")
@app.get("/api/external/tweet")
async def external_tweet(request: Request):
    """External cron endpoint"""
    try:
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"External tweet trigger from {client_ip}")
        
        # Import here to avoid startup issues
        from src.tweet_generator import get_tweet
        from src.twitter_client import post_tweet
        
        # Generate tweet
        tweet_content = get_tweet()
        logger.info(f"Generated tweet: {tweet_content[:50]}...")
        
        # Post tweet
        tweet_id = post_tweet(tweet_content)
        
        result = {
            "success": bool(tweet_id),
            "tweet_id": tweet_id,
            "content": tweet_content if tweet_id else None,
            "timestamp": asyncio.get_event_loop().time(),
            "triggered_by": "external_cron",
            "source_ip": client_ip
        }
        
        if tweet_id:
            logger.info(f"External tweet posted successfully with ID: {tweet_id}")
        else:
            logger.error("External tweet posting failed")
            result["error"] = "Failed to post tweet"
        
        return result
        
    except Exception as e:
        logger.error(f"External tweet error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time(),
            "triggered_by": "external_cron"
        }

# Vercel handler
def handler(request, response):
    """Vercel serverless handler"""
    return app(request, response)

# Export the app for Vercel
# This is what Vercel will call
def app_handler():
    return app
