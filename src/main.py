"""
Main Application Entry Point for AI Twitter Bot

This module serves as the primary entry point for the AI Twitter bot,
coordinating all components and handling different deployment scenarios.
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import signal
import atexit
from contextlib import asynccontextmanager

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from dotenv import load_dotenv

# Import bot components
from src.dashboard import app as dashboard_app
from src.scheduler import get_scheduler, start_scheduler, stop_scheduler
from src.twitter_client import get_client, TwitterClientError
from src.tweet_generator import get_tweet

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", mode="a")
    ]
)
logger = logging.getLogger(__name__)

# Application metadata
APP_NAME = "AI Twitter Bot"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Intelligent Twitter bot powered by Gemini AI and LangGraph"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    # Startup
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    
    try:
        # Validate configuration
        twitter_bot_app._validate_config()
        
        # Initialize components
        await twitter_bot_app._initialize_components()
        
        # Start the scheduler if enabled (disabled for Vercel serverless)
        if os.getenv("AUTO_START", "true").lower() == "true" and not os.getenv("VERCEL_DEPLOYMENT"):
            start_scheduler()
            logger.info("Scheduler started automatically")
        elif os.getenv("VERCEL_DEPLOYMENT"):
            logger.info("Vercel deployment detected - using cron jobs instead of scheduler")
        
        twitter_bot_app.is_running = True
        twitter_bot_app.start_time = asyncio.get_event_loop().time()
        
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    try:
        # Stop scheduler
        stop_scheduler()
        
        # Cleanup resources
        await twitter_bot_app._cleanup_resources()
        
        twitter_bot_app.is_running = False
        
        logger.info("Application shutdown completed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

class TwitterBotApp:
    """Main application class for the Twitter bot"""
    
    def __init__(self):
        self.app = FastAPI(
            title=APP_NAME,
            version=APP_VERSION,
            description=APP_DESCRIPTION,
            docs_url="/docs",
            redoc_url="/redoc",
            lifespan=lifespan
        )
        
        self.scheduler = get_scheduler()
        self.twitter_client = get_client()
        self.is_running = False
        
        self._setup_middleware()
        self._setup_routes()
        self._setup_signal_handlers()
        
    def _setup_middleware(self):
        """Configure FastAPI middleware"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Request logging middleware
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = asyncio.get_event_loop().time()
            
            # Process request
            response = await call_next(request)
            
            # Log request details
            process_time = asyncio.get_event_loop().time() - start_time
            logger.info(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s"
            )
            
            return response
    
    def _setup_routes(self):
        """Configure application routes"""
        
        # Mount the dashboard app
        self.app.mount("/", dashboard_app)
        
        # Root redirect to dashboard
        @self.app.get("/", include_in_schema=False)
        async def root():
            return RedirectResponse(url="/dashboard", status_code=302)
        
        # Health check endpoint
        @self.app.get("/health")
        async def health_check():
            """Comprehensive health check"""
            try:
                # Check scheduler status
                scheduler_status = self.scheduler.get_status()
                
                # Check Twitter client
                account_info = self.twitter_client.get_account_info()
                twitter_healthy = account_info is not None
                
                # Check Gemini AI (try generating a test)
                try:
                    test_tweet = get_tweet()
                    gemini_healthy = len(test_tweet) > 0
                except Exception:
                    gemini_healthy = False
                
                overall_health = (
                    scheduler_status["status"] != "error" and
                    twitter_healthy and
                    gemini_healthy
                )
                
                return {
                    "status": "healthy" if overall_health else "degraded",
                    "timestamp": asyncio.get_event_loop().time(),
                    "version": APP_VERSION,
                    "components": {
                        "scheduler": scheduler_status["status"],
                        "twitter": "healthy" if twitter_healthy else "unhealthy",
                        "gemini": "healthy" if gemini_healthy else "unhealthy"
                    },
                    "uptime": self.get_uptime() if self.is_running else 0
                }
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                }
        
        # Info endpoint
        @self.app.get("/info")
        async def app_info():
            """Get application information"""
            return {
                "name": APP_NAME,
                "version": APP_VERSION,
                "description": APP_DESCRIPTION,
                "environment": os.getenv("VERCEL_ENV", "development"),
                "python_version": sys.version,
                "deployment": self.get_deployment_info()
            }
        
        # API status endpoint (for monitoring)
        @self.app.get("/api/ping")
        async def ping():
            """Simple ping endpoint"""
            return {"ping": "pong", "timestamp": asyncio.get_event_loop().time()}
        
        # Error test endpoint (for debugging)
        @self.app.get("/api/test-error")
        async def test_error():
            """Test error handling"""
            if os.getenv("VERCEL_ENV") == "production":
                raise HTTPException(status_code=404, detail="Not found")
            raise Exception("Test error for debugging")
        
        # Vercel Cron endpoints
        @self.app.post("/api/cron/tweet")
        @self.app.get("/api/cron/tweet")
        async def cron_tweet():
            """Cron endpoint for automatic tweet posting"""
            try:
                # Verify it's a Vercel cron request (basic security)
                if os.getenv("VERCEL_ENV") == "production":
                    # You can add more security checks here if needed
                    pass
                
                logger.info("Vercel cron tweet endpoint triggered")
                
                # Generate and post tweet directly without scheduler
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
                logger.error(f"Cron tweet error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                }
        
        @self.app.post("/api/cron/health")
        @self.app.get("/api/cron/health")
        async def cron_health():
            """Cron endpoint for health monitoring"""
            try:
                logger.info("Vercel cron health endpoint triggered")
                
                # Basic health checks
                health_data = {
                    "status": "healthy",
                    "timestamp": asyncio.get_event_loop().time(),
                    "environment": os.getenv("VERCEL_ENV", "development"),
                    "deployment_id": os.getenv("VERCEL_DEPLOYMENT_ID", "unknown"),
                    "checks": {}
                }
                
                # Check Twitter client
                try:
                    account_info = self.twitter_client.get_account_info()
                    health_data["checks"]["twitter"] = "healthy" if account_info else "unhealthy"
                except Exception as e:
                    health_data["checks"]["twitter"] = f"error: {str(e)}"
                
                # Check Gemini AI
                try:
                    test_tweet = get_tweet()
                    health_data["checks"]["gemini"] = "healthy" if len(test_tweet) > 0 else "unhealthy"
                except Exception as e:
                    health_data["checks"]["gemini"] = f"error: {str(e)}"
                
                # Determine overall status
                unhealthy_checks = [k for k, v in health_data["checks"].items() if "error" in str(v) or v == "unhealthy"]
                if unhealthy_checks:
                    health_data["status"] = "degraded"
                    health_data["unhealthy_components"] = unhealthy_checks
                
                logger.info(f"Health check completed: {health_data['status']}")
                return health_data
                
            except Exception as e:
                logger.error(f"Cron health error: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                }
        
        # Manual tweet trigger endpoint
        @self.app.post("/api/trigger-tweet")
        async def trigger_manual_tweet():
            """Manually trigger a tweet"""
            try:
                logger.info("Manual tweet trigger requested")
                
                # Generate tweet
                tweet_content = get_tweet()
                logger.info(f"Generated tweet: {tweet_content[:50]}...")
                
                # Post tweet
                tweet_id = post_tweet(tweet_content)
                
                if tweet_id:
                    logger.info(f"Manual tweet posted successfully with ID: {tweet_id}")
                    return {
                        "success": True,
                        "tweet_id": tweet_id,
                        "content": tweet_content,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                else:
                    logger.error("Failed to post manual tweet")
                    raise HTTPException(status_code=500, detail="Failed to post tweet")
                    
            except Exception as e:
                logger.error(f"Manual tweet error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown()
        
        # Register signal handlers (Unix-like systems)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)
        
        # Register exit handler
        atexit.register(self.shutdown)
    
    def _validate_config(self):
        """Validate application configuration"""
        required_env_vars = [
            "GEMINI_API_KEY",
            "TWITTER_API_KEY",
            "TWITTER_API_SECRET",
            "TWITTER_ACCESS_TOKEN",
            "TWITTER_ACCESS_SECRET"
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        logger.info("Configuration validation passed")
    
    async def _initialize_components(self):
        """Initialize all bot components"""
        try:
            # Test Twitter client
            account_info = self.twitter_client.get_account_info()
            if account_info:
                logger.info(f"Twitter client initialized for @{account_info.get('username', 'unknown')}")
            else:
                logger.warning("Twitter client initialization may have issues")
            
            # Test tweet generation
            test_tweet = get_tweet()
            logger.info(f"Tweet generator initialized (test: {test_tweet[:30]}...)")
            
            # Initialize scheduler
            logger.info("Scheduler initialized")
            
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            raise
    
    async def _cleanup_resources(self):
        """Cleanup application resources"""
        try:
            # Any cleanup tasks can go here
            logger.info("Resources cleaned up")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def get_deployment_info(self) -> Dict[str, Any]:
        """Get deployment environment information"""
        return {
            "platform": "vercel" if os.getenv("VERCEL") else "local",
            "environment": os.getenv("VERCEL_ENV", "development"),
            "region": os.getenv("VERCEL_REGION", "unknown"),
            "deployment_id": os.getenv("VERCEL_DEPLOYMENT_ID", "unknown"),
            "git_commit": os.getenv("VERCEL_GIT_COMMIT_SHA", "unknown")[:8] if os.getenv("VERCEL_GIT_COMMIT_SHA") else "unknown"
        }
    
    def get_uptime(self) -> float:
        """Get application uptime in seconds"""
        if hasattr(self, 'start_time'):
            return asyncio.get_event_loop().time() - self.start_time
        return 0
    
    def shutdown(self):
        """Graceful shutdown"""
        if self.is_running:
            logger.info("Initiating graceful shutdown...")
            try:
                stop_scheduler()
                self.is_running = False
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

# Global application instance
twitter_bot_app = TwitterBotApp()
app = twitter_bot_app.app

# For Vercel compatibility
def handler(request, response):
    """Vercel handler function"""
    return app(request, response)

# Development server
def run_development_server():
    """Run the development server"""
    logger.info("Starting development server...")
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        log_level=log_level.lower(),
        access_log=True
    )

# Production server (for non-Vercel deployments)
def run_production_server():
    """Run the production server"""
    logger.info("Starting production server...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=log_level.lower(),
        access_log=True,
        workers=1  # Single worker for scheduling consistency
    )

# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Twitter Bot")
    parser.add_argument(
        "--mode",
        choices=["dev", "prod", "test"],
        default="dev",
        help="Run mode (default: dev)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run on (default: 8000)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    
    args = parser.parse_args()
    
    # Set port from command line
    os.environ["PORT"] = str(args.port)
    
    try:
        if args.mode == "dev":
            run_development_server()
        elif args.mode == "prod":
            run_production_server()
        elif args.mode == "test":
            # Run basic tests
            logger.info("Running basic functionality tests...")
            
            # Test tweet generation
            tweet = get_tweet()
            logger.info(f"Test tweet generated: {tweet}")
            
            # Test Twitter client initialization
            client = get_client()
            account = client.get_account_info()
            logger.info(f"Twitter account: {account}")
            
            logger.info("Basic tests completed")
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
