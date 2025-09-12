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
from fastapi.responses import JSONResponse, HTMLResponse
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

@app.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Serve the main dashboard HTML"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Twitter Bot Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    </head>
    <body class="bg-gray-100">
        <div class="container mx-auto px-4 py-8" x-data="dashboard()">
            <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
                <h1 class="text-3xl font-bold text-gray-800 mb-2">AI Twitter Bot Dashboard</h1>
                <p class="text-gray-600">Monitor and control your intelligent Twitter bot on Vercel</p>
            </div>
            
            <!-- Status Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">Bot Status</h3>
                    <div class="flex items-center">
                        <div class="w-3 h-3 rounded-full mr-2 bg-green-500"></div>
                        <span class="font-medium">Active on Vercel</span>
                    </div>
                    <p class="text-sm text-gray-600 mt-2" x-text="'Health: ' + status.health"></p>
                </div>
                
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">Twitter API</h3>
                    <div class="flex items-center">
                        <div class="w-3 h-3 rounded-full mr-2" :class="status.twitter === 'healthy' ? 'bg-green-500' : 'bg-red-500'"></div>
                        <span x-text="status.twitter || 'checking...'" class="font-medium capitalize"></span>
                    </div>
                    <p class="text-sm text-gray-600 mt-2">API Connection</p>
                </div>
                
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">Gemini AI</h3>
                    <div class="flex items-center">
                        <div class="w-3 h-3 rounded-full mr-2" :class="status.gemini === 'healthy' ? 'bg-green-500' : 'bg-red-500'"></div>
                        <span x-text="status.gemini || 'checking...'" class="font-medium capitalize"></span>
                    </div>
                    <p class="text-sm text-gray-600 mt-2">AI Generation</p>
                </div>
            </div>
            
            <!-- Controls -->
            <div class="bg-white rounded-lg shadow p-6 mb-6">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">Bot Controls</h3>
                <div class="flex flex-wrap gap-4">
                    <button @click="triggerTweet()" 
                            class="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium shadow">
                        🚀 Generate & Post Tweet
                    </button>
                    
                    <button @click="refreshStatus()" 
                            class="px-6 py-3 bg-gray-500 hover:bg-gray-600 text-white rounded-lg font-medium shadow">
                        🔄 Refresh Status
                    </button>
                    
                    <button @click="testHealth()" 
                            class="px-6 py-3 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium shadow">
                        🏥 Health Check
                    </button>
                </div>
            </div>
            
            <!-- Last Tweet -->
            <div class="bg-white rounded-lg shadow p-6 mb-6" x-show="lastTweet.content">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">Last Tweet</h3>
                <div class="bg-gray-50 rounded-lg p-4">
                    <p class="text-gray-800 mb-2" x-text="lastTweet.content"></p>
                    <div class="flex items-center justify-between text-sm text-gray-600">
                        <span x-text="'ID: ' + lastTweet.id"></span>
                        <span x-text="'Posted: ' + formatTime(lastTweet.timestamp)"></span>
                    </div>
                </div>
            </div>
            
            <!-- Activity Log -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">Activity Log</h3>
                <div class="space-y-3" id="activity-log">
                    <div class="text-gray-500 text-center py-4">
                        Activity will appear here...
                    </div>
                </div>
            </div>
        </div>

        <script>
            function dashboard() {
                return {
                    status: {
                        health: 'checking...',
                        twitter: 'checking...',
                        gemini: 'checking...'
                    },
                    lastTweet: {},
                    
                    async init() {
                        await this.refreshStatus();
                    },
                    
                    async refreshStatus() {
                        try {
                            this.addActivity('🔄 Checking system status...');
                            const response = await fetch('/health');
                            const data = await response.json();
                            this.status.health = data.status;
                            this.status.twitter = data.components?.twitter || 'unknown';
                            this.status.gemini = data.components?.gemini || 'unknown';
                            this.addActivity('✅ Status refreshed successfully');
                        } catch (error) {
                            this.addActivity('❌ Failed to refresh status: ' + error.message);
                            console.error('Failed to refresh status:', error);
                        }
                    },
                    
                    async triggerTweet() {
                        try {
                            this.addActivity('🚀 Generating tweet...');
                            const response = await fetch('/api/trigger-tweet', { method: 'POST' });
                            const data = await response.json();
                            
                            if (data.success) {
                                this.lastTweet = {
                                    content: data.content,
                                    id: data.tweet_id,
                                    timestamp: new Date().toISOString()
                                };
                                this.addActivity('✅ Tweet posted successfully! ID: ' + data.tweet_id);
                            } else {
                                this.addActivity('❌ Tweet failed: ' + data.error);
                            }
                        } catch (error) {
                            this.addActivity('❌ Tweet error: ' + error.message);
                            console.error('Failed to trigger tweet:', error);
                        }
                    },
                    
                    async testHealth() {
                        await this.refreshStatus();
                        this.addActivity('🏥 Health check completed');
                    },
                    
                    addActivity(message) {
                        const log = document.getElementById('activity-log');
                        const timestamp = new Date().toLocaleTimeString();
                        const entry = document.createElement('div');
                        entry.className = 'border-l-4 border-blue-500 pl-4 py-2 bg-blue-50';
                        entry.innerHTML = `
                            <div class="flex items-center justify-between">
                                <span class="text-blue-800">${message}</span>
                                <span class="text-sm text-gray-500">${timestamp}</span>
                            </div>
                        `;
                        
                        // Remove placeholder text
                        if (log.children.length === 1 && log.children[0].textContent.includes('Activity will appear')) {
                            log.innerHTML = '';
                        }
                        
                        log.insertBefore(entry, log.firstChild);
                        
                        // Keep only last 10 entries
                        while (log.children.length > 10) {
                            log.removeChild(log.lastChild);
                        }
                    },
                    
                    formatTime(timestamp) {
                        return new Date(timestamp).toLocaleString();
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

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

# For external cron services like cron-job.org
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

# Vercel will automatically use this app as an ASGI application
# No need for custom handler functions