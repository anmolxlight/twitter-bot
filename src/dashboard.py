"""
FastAPI Dashboard for AI Twitter Bot

This module provides a comprehensive web dashboard for controlling and monitoring
the AI Twitter bot, including real-time status, controls, and analytics.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .scheduler import get_scheduler, schedule_tweet, get_scheduler_status, start_scheduler, stop_scheduler
from .twitter_client import get_client, TwitterClientError
from .tweet_generator import get_tweet

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class TweetRequest(BaseModel):
    content: Optional[str] = Field(None, description="Optional custom tweet content")
    immediate: bool = Field(False, description="Post immediately without scheduling")

class SchedulerConfigUpdate(BaseModel):
    min_interval_hours: Optional[int] = Field(None, ge=1, le=24)
    max_interval_hours: Optional[int] = Field(None, ge=1, le=24)
    max_daily_tweets: Optional[int] = Field(None, ge=1, le=50)
    optimal_hours: Optional[List[int]] = Field(None, description="List of optimal hours (0-23)")
    avoid_hours: Optional[List[int]] = Field(None, description="List of hours to avoid (0-23)")

class BotSettings(BaseModel):
    style: Optional[str] = Field(None, description="Bot personality style")
    topics: Optional[List[str]] = Field(None, description="Preferred topics")

# Create FastAPI app
app = FastAPI(
    title="AI Twitter Bot Dashboard",
    description="Comprehensive dashboard for controlling and monitoring the AI Twitter bot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
bot_enabled = True
scheduler_instance = get_scheduler()
twitter_client = get_client()

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
                <p class="text-gray-600">Monitor and control your intelligent Twitter bot</p>
            </div>
            
            <!-- Status Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">Bot Status</h3>
                    <div class="flex items-center">
                        <div class="w-3 h-3 rounded-full mr-2" :class="status.bot_enabled ? 'bg-green-500' : 'bg-red-500'"></div>
                        <span x-text="status.bot_enabled ? 'Active' : 'Inactive'" class="font-medium"></span>
                    </div>
                    <p class="text-sm text-gray-600 mt-2" x-text="'Scheduler: ' + status.scheduler_status"></p>
                </div>
                
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">Daily Progress</h3>
                    <div class="flex items-center">
                        <span x-text="status.daily_count + ' / ' + status.daily_limit" class="text-2xl font-bold text-blue-600"></span>
                        <span class="ml-2 text-gray-600">tweets</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2 mt-2">
                        <div class="bg-blue-600 h-2 rounded-full" :style="'width: ' + ((status.daily_count / status.daily_limit) * 100) + '%'"></div>
                    </div>
                </div>
                
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">Success Rate</h3>
                    <div class="flex items-center">
                        <span x-text="Math.round(status.success_rate * 100) + '%'" class="text-2xl font-bold text-green-600"></span>
                    </div>
                    <p class="text-sm text-gray-600 mt-2">Last 20 attempts</p>
                </div>
            </div>
            
            <!-- Controls -->
            <div class="bg-white rounded-lg shadow p-6 mb-6">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">Bot Controls</h3>
                <div class="flex flex-wrap gap-4">
                    <button @click="toggleBot()" 
                            class="px-4 py-2 rounded font-medium"
                            :class="status.bot_enabled ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-green-500 hover:bg-green-600 text-white'">
                        <span x-text="status.bot_enabled ? 'Disable Bot' : 'Enable Bot'"></span>
                    </button>
                    
                    <button @click="triggerTweet()" 
                            class="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded font-medium"
                            :disabled="!status.bot_enabled">
                        Post Tweet Now
                    </button>
                    
                    <button @click="refreshStatus()" 
                            class="px-4 py-2 bg-gray-500 hover:bg-gray-600 text-white rounded font-medium">
                        Refresh Status
                    </button>
                </div>
            </div>
            
            <!-- Recent Activity -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">Recent Activity</h3>
                <div class="space-y-3">
                    <template x-for="attempt in recent_attempts" :key="attempt.timestamp">
                        <div class="border-l-4 pl-4 py-2" :class="attempt.success ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'">
                            <div class="flex items-center justify-between">
                                <span class="font-medium" :class="attempt.success ? 'text-green-800' : 'text-red-800'" 
                                      x-text="attempt.success ? 'Success' : 'Failed'"></span>
                                <span class="text-sm text-gray-500" x-text="formatTime(attempt.timestamp)"></span>
                            </div>
                            <p class="text-sm text-gray-700 mt-1" x-text="attempt.tweet_preview || attempt.error"></p>
                            <div class="text-xs text-gray-500 mt-1" x-show="attempt.success">
                                <span x-text="'ID: ' + attempt.tweet_id"></span>
                                <span x-text="' | Gen: ' + attempt.generation_time.toFixed(2) + 's'"></span>
                                <span x-text="' | Post: ' + attempt.post_time.toFixed(2) + 's'"></span>
                            </div>
                        </div>
                    </template>
                </div>
            </div>
        </div>

        <script>
            function dashboard() {
                return {
                    status: {
                        bot_enabled: true,
                        scheduler_status: 'loading',
                        daily_count: 0,
                        daily_limit: 8,
                        success_rate: 0
                    },
                    recent_attempts: [],
                    
                    async init() {
                        await this.refreshStatus();
                        // Auto-refresh every 30 seconds
                        setInterval(() => this.refreshStatus(), 30000);
                    },
                    
                    async refreshStatus() {
                        try {
                            const response = await fetch('/api/status');
                            const data = await response.json();
                            this.status = data.status;
                            this.recent_attempts = data.recent_attempts;
                        } catch (error) {
                            console.error('Failed to refresh status:', error);
                        }
                    },
                    
                    async toggleBot() {
                        try {
                            const response = await fetch('/api/toggle', { method: 'POST' });
                            const data = await response.json();
                            this.status.bot_enabled = data.enabled;
                        } catch (error) {
                            console.error('Failed to toggle bot:', error);
                        }
                    },
                    
                    async triggerTweet() {
                        try {
                            const response = await fetch('/api/tweet', { 
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ immediate: true })
                            });
                            const data = await response.json();
                            if (data.success) {
                                alert('Tweet posted successfully!');
                            } else {
                                alert('Failed to post tweet: ' + data.error);
                            }
                            await this.refreshStatus();
                        } catch (error) {
                            console.error('Failed to trigger tweet:', error);
                            alert('Failed to trigger tweet');
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
    return html_content

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/status")
async def get_bot_status():
    """Get comprehensive bot status"""
    try:
        scheduler_status = get_scheduler_status()
        client_performance = twitter_client.get_performance_summary()
        account_info = twitter_client.get_account_info()
        recent_attempts = scheduler_instance.get_recent_attempts(10)
        
        return {
            "status": {
                "bot_enabled": bot_enabled,
                "scheduler_status": scheduler_status.get("status", "unknown"),
                "next_tweet": scheduler_status.get("next_tweet"),
                "daily_count": scheduler_status.get("daily_count", 0),
                "daily_limit": scheduler_status.get("daily_limit", 8),
                "success_rate": scheduler_status.get("success_rate", 0),
                "total_attempts": scheduler_status.get("total_attempts", 0),
                "last_attempt": scheduler_status.get("last_attempt"),
                "last_success": scheduler_status.get("last_success")
            },
            "performance": client_performance,
            "account": account_info,
            "recent_attempts": recent_attempts,
            "configuration": scheduler_status.get("configuration", {})
        }
        
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.post("/api/toggle")
async def toggle_bot():
    """Toggle bot enabled/disabled state"""
    global bot_enabled
    
    try:
        bot_enabled = not bot_enabled
        
        if bot_enabled:
            start_scheduler()
            logger.info("Bot enabled and scheduler started")
        else:
            stop_scheduler()
            logger.info("Bot disabled and scheduler stopped")
        
        return {
            "enabled": bot_enabled,
            "message": f"Bot {'enabled' if bot_enabled else 'disabled'} successfully"
        }
        
    except Exception as e:
        logger.error(f"Error toggling bot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle bot: {str(e)}")

@app.post("/api/tweet")
async def trigger_tweet(request: TweetRequest = TweetRequest()):
    """Trigger a tweet manually"""
    if not bot_enabled:
        raise HTTPException(status_code=400, detail="Bot is disabled")
    
    try:
        if request.content:
            # Post custom content directly
            from .twitter_client import post_tweet
            tweet_id = post_tweet(request.content)
            
            if tweet_id:
                return {
                    "success": True,
                    "tweet_id": tweet_id,
                    "content": request.content,
                    "message": "Custom tweet posted successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to post custom tweet"
                }
        else:
            # Generate and post new tweet
            result = await schedule_tweet()
            return result
            
    except TwitterClientError as e:
        logger.error(f"Twitter error in manual tweet: {e}")
        raise HTTPException(status_code=400, detail=f"Twitter error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error triggering tweet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger tweet: {str(e)}")

@app.get("/api/generate-preview")
async def generate_tweet_preview():
    """Generate a tweet preview without posting"""
    try:
        tweet_content = get_tweet()
        
        return {
            "content": tweet_content,
            "length": len(tweet_content),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")

@app.get("/api/analytics")
async def get_analytics(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze")
):
    """Get bot performance analytics"""
    try:
        # Get recent attempts from scheduler
        all_attempts = scheduler_instance.get_recent_attempts(1000)  # Get more for analysis
        
        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_attempts = [
            attempt for attempt in all_attempts 
            if datetime.fromisoformat(attempt["timestamp"]) > cutoff_date
        ]
        
        if not recent_attempts:
            return {
                "period_days": days,
                "total_attempts": 0,
                "success_rate": 0,
                "daily_average": 0,
                "performance_trend": "no_data"
            }
        
        # Calculate metrics
        successful_attempts = [a for a in recent_attempts if a["success"]]
        success_rate = len(successful_attempts) / len(recent_attempts)
        daily_average = len(recent_attempts) / days
        
        # Calculate trend (compare first and second half)
        mid_point = len(recent_attempts) // 2
        if mid_point > 0:
            first_half_success = sum(1 for a in recent_attempts[:mid_point] if a["success"]) / mid_point
            second_half_success = sum(1 for a in recent_attempts[mid_point:] if a["success"]) / (len(recent_attempts) - mid_point)
            
            if second_half_success > first_half_success + 0.1:
                trend = "improving"
            elif second_half_success < first_half_success - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Get error breakdown
        errors = [a["error"] for a in recent_attempts if a["error"]]
        error_types = {}
        for error in errors:
            error_type = error.split(":")[0] if ":" in error else error
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "period_days": days,
            "total_attempts": len(recent_attempts),
            "successful_attempts": len(successful_attempts),
            "success_rate": round(success_rate, 3),
            "daily_average": round(daily_average, 2),
            "performance_trend": trend,
            "error_breakdown": error_types,
            "avg_generation_time": round(
                sum(a["generation_time"] for a in successful_attempts) / len(successful_attempts), 2
            ) if successful_attempts else 0,
            "avg_post_time": round(
                sum(a["post_time"] for a in successful_attempts) / len(successful_attempts), 2
            ) if successful_attempts else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@app.get("/api/account")
async def get_account_info():
    """Get Twitter account information"""
    try:
        account_info = twitter_client.get_account_info()
        performance = twitter_client.get_performance_summary()
        rate_limits = twitter_client.get_rate_limit_status()
        
        return {
            "account": account_info,
            "performance": performance,
            "rate_limits": rate_limits
        }
        
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get account info: {str(e)}")

@app.post("/api/scheduler/config")
async def update_scheduler_config(config: SchedulerConfigUpdate):
    """Update scheduler configuration"""
    try:
        current_config = scheduler_instance.config
        
        if config.min_interval_hours is not None:
            current_config.min_interval_hours = config.min_interval_hours
        if config.max_interval_hours is not None:
            current_config.max_interval_hours = config.max_interval_hours
        if config.max_daily_tweets is not None:
            current_config.max_daily_tweets = config.max_daily_tweets
        if config.optimal_hours is not None:
            current_config.optimal_hours = config.optimal_hours
        if config.avoid_hours is not None:
            current_config.avoid_hours = config.avoid_hours
        
        logger.info("Scheduler configuration updated")
        
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": {
                "min_interval_hours": current_config.min_interval_hours,
                "max_interval_hours": current_config.max_interval_hours,
                "max_daily_tweets": current_config.max_daily_tweets,
                "optimal_hours": current_config.optimal_hours,
                "avoid_hours": current_config.avoid_hours
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating scheduler config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

@app.delete("/api/tweet/{tweet_id}")
async def delete_tweet(tweet_id: str):
    """Delete a specific tweet"""
    try:
        success = twitter_client.delete_tweet(tweet_id)
        
        if success:
            return {
                "success": True,
                "message": f"Tweet {tweet_id} deleted successfully"
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to delete tweet")
            
    except TwitterClientError as e:
        logger.error(f"Twitter error deleting tweet: {e}")
        raise HTTPException(status_code=400, detail=f"Twitter error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error deleting tweet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tweet: {str(e)}")

@app.get("/api/schedule")
async def vercel_cron_endpoint():
    """Endpoint for Vercel cron jobs"""
    if not bot_enabled:
        return {
            "status": "skipped",
            "message": "Bot is disabled"
        }
    
    try:
        result = await schedule_tweet()
        return result
        
    except Exception as e:
        logger.error(f"Error in Vercel cron endpoint: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "path": str(request.url)}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the bot on startup"""
    logger.info("Dashboard starting up...")
    
    if bot_enabled:
        try:
            start_scheduler()
            logger.info("Bot started automatically on startup")
        except Exception as e:
            logger.error(f"Failed to start bot on startup: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    logger.info("Dashboard shutting down...")
    
    try:
        stop_scheduler()
        logger.info("Scheduler stopped on shutdown")
    except Exception as e:
        logger.error(f"Error stopping scheduler on shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
