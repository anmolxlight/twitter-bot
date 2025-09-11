"""
Intelligent Tweet Scheduler

This module provides sophisticated scheduling capabilities for the AI Twitter bot,
including adaptive timing, performance-based adjustments, and robust state management.
"""

import os
import logging
import random
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from dotenv import load_dotenv

from .tweet_generator import get_tweet
from .twitter_client import post_tweet, get_client, TwitterClientError, RateLimitError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class SchedulerStatus(Enum):
    """Scheduler status enumeration"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

@dataclass
class ScheduleAttempt:
    """Track individual scheduling attempts"""
    timestamp: datetime
    success: bool
    tweet_id: Optional[str]
    error: Optional[str]
    tweet_content: Optional[str]
    generation_time: float
    post_time: float

@dataclass
class SchedulerConfig:
    """Configuration for the scheduler"""
    min_interval_hours: int = 1
    max_interval_hours: int = 6
    optimal_hours: List[int] = None  # Best hours to tweet (0-23)
    avoid_hours: List[int] = None    # Hours to avoid tweeting
    max_daily_tweets: int = 8
    performance_adjustment: bool = True
    timezone: str = "UTC"

class IntelligentScheduler:
    """Advanced scheduler with adaptive timing and performance optimization"""
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        """Initialize the scheduler with configuration"""
        self.config = config or SchedulerConfig()
        
        # Load configuration from environment
        self.config.min_interval_hours = int(os.getenv("MIN_INTERVAL_HOURS", "1"))
        self.config.max_interval_hours = int(os.getenv("MAX_INTERVAL_HOURS", "6"))
        
        # Default optimal hours (9 AM - 9 PM in various timezones)
        self.config.optimal_hours = self.config.optimal_hours or [6, 9, 12, 15, 18, 21]
        self.config.avoid_hours = self.config.avoid_hours or [0, 1, 2, 3, 4, 5]
        
        # Initialize scheduler
        self.scheduler = AsyncIOScheduler()
        self.status = SchedulerStatus.STOPPED
        
        # Performance tracking
        self.attempt_history: List[ScheduleAttempt] = []
        self.daily_tweet_count = 0
        self.last_reset_date = datetime.now().date()
        
        # Adaptive timing
        self.success_rate = 1.0
        self.average_interval = (self.config.min_interval_hours + self.config.max_interval_hours) / 2
        
        # Twitter client reference
        self.twitter_client = get_client()
        
        # Add job listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        logger.info("Intelligent scheduler initialized")
    
    def _reset_daily_count_if_needed(self):
        """Reset daily tweet count if it's a new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_tweet_count = 0
            self.last_reset_date = current_date
            logger.info("Daily tweet count reset")
    
    def _calculate_next_interval(self) -> int:
        """Calculate the next interval based on performance and timing"""
        base_interval = random.randint(
            self.config.min_interval_hours * 3600,
            self.config.max_interval_hours * 3600
        )
        
        if not self.config.performance_adjustment:
            return base_interval
        
        # Adjust based on recent success rate
        if len(self.attempt_history) >= 5:
            recent_attempts = self.attempt_history[-5:]
            success_count = sum(1 for attempt in recent_attempts if attempt.success)
            recent_success_rate = success_count / len(recent_attempts)
            
            if recent_success_rate < 0.6:
                # Poor performance, increase interval
                base_interval = int(base_interval * 1.5)
                logger.info(f"Poor performance detected, increasing interval to {base_interval}s")
            elif recent_success_rate > 0.9:
                # Great performance, slightly decrease interval
                base_interval = int(base_interval * 0.8)
                logger.info(f"Great performance detected, decreasing interval to {base_interval}s")
        
        # Ensure we stay within bounds
        min_seconds = self.config.min_interval_hours * 3600
        max_seconds = self.config.max_interval_hours * 3600
        
        return max(min_seconds, min(max_seconds, base_interval))
    
    def _is_optimal_time(self) -> bool:
        """Check if current time is optimal for posting"""
        current_hour = datetime.now().hour
        
        # Avoid bad hours
        if current_hour in self.config.avoid_hours:
            return False
        
        # Prefer optimal hours
        if current_hour in self.config.optimal_hours:
            return True
        
        # Allow other hours but with lower probability
        return random.random() > 0.3
    
    def _should_skip_tweet(self) -> Tuple[bool, str]:
        """Determine if we should skip tweeting right now"""
        self._reset_daily_count_if_needed()
        
        # Check daily limit
        if self.daily_tweet_count >= self.config.max_daily_tweets:
            return True, f"Daily limit reached ({self.config.max_daily_tweets} tweets)"
        
        # Check if it's a good time to tweet
        if not self._is_optimal_time():
            return True, f"Not optimal time (current hour: {datetime.now().hour})"
        
        # Check recent failure rate
        if len(self.attempt_history) >= 3:
            recent_failures = [a for a in self.attempt_history[-3:] if not a.success]
            if len(recent_failures) >= 2:
                last_failure_time = max(f.timestamp for f in recent_failures)
                if datetime.now() - last_failure_time < timedelta(hours=1):
                    return True, "Too many recent failures, backing off"
        
        return False, ""
    
    async def _generate_and_post_tweet(self) -> ScheduleAttempt:
        """Generate and post a tweet, tracking the attempt"""
        start_time = datetime.now()
        attempt = ScheduleAttempt(
            timestamp=start_time,
            success=False,
            tweet_id=None,
            error=None,
            tweet_content=None,
            generation_time=0.0,
            post_time=0.0
        )
        
        try:
            # Check if we should skip
            should_skip, skip_reason = self._should_skip_tweet()
            if should_skip:
                logger.info(f"Skipping tweet: {skip_reason}")
                attempt.error = f"Skipped: {skip_reason}"
                return attempt
            
            # Generate tweet
            logger.info("Generating tweet...")
            generation_start = datetime.now()
            
            tweet_content = get_tweet()
            
            generation_time = (datetime.now() - generation_start).total_seconds()
            attempt.generation_time = generation_time
            attempt.tweet_content = tweet_content
            
            logger.info(f"Tweet generated in {generation_time:.2f}s: {tweet_content[:50]}...")
            
            # Post tweet
            post_start = datetime.now()
            
            tweet_id = post_tweet(tweet_content)
            
            post_time = (datetime.now() - post_start).total_seconds()
            attempt.post_time = post_time
            
            if tweet_id:
                attempt.success = True
                attempt.tweet_id = tweet_id
                self.daily_tweet_count += 1
                
                logger.info(f"Tweet posted successfully in {post_time:.2f}s with ID: {tweet_id}")
                logger.info(f"Daily tweet count: {self.daily_tweet_count}/{self.config.max_daily_tweets}")
            else:
                attempt.error = "Tweet posting returned no ID"
                logger.error("Tweet posting failed: no ID returned")
                
        except RateLimitError as e:
            attempt.error = f"Rate limit: {str(e)}"
            logger.warning(f"Rate limit encountered: {e}")
            
        except TwitterClientError as e:
            attempt.error = f"Twitter error: {str(e)}"
            logger.error(f"Twitter client error: {e}")
            
        except Exception as e:
            attempt.error = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error in tweet generation/posting: {e}")
        
        # Record attempt
        self.attempt_history.append(attempt)
        
        # Keep only last 100 attempts
        if len(self.attempt_history) > 100:
            self.attempt_history = self.attempt_history[-100:]
        
        return attempt
    
    async def schedule_tweet_job(self):
        """Job function for scheduled tweets"""
        logger.info("Scheduled tweet job triggered")
        
        try:
            attempt = await self._generate_and_post_tweet()
            
            if attempt.success:
                logger.info(f"Scheduled tweet successful: {attempt.tweet_id}")
                self._schedule_next_tweet()
            else:
                logger.warning(f"Scheduled tweet failed: {attempt.error}")
                # Still schedule next tweet, but with potential delay adjustment
                self._schedule_next_tweet()
                
        except Exception as e:
            logger.error(f"Critical error in scheduled tweet job: {e}")
            self.status = SchedulerStatus.ERROR
    
    def _schedule_next_tweet(self):
        """Schedule the next tweet with adaptive timing"""
        if self.status != SchedulerStatus.RUNNING:
            return
        
        interval_seconds = self._calculate_next_interval()
        next_run = datetime.now() + timedelta(seconds=interval_seconds)
        
        # Remove existing job if any
        try:
            self.scheduler.remove_job('tweet_job')
        except:
            pass
        
        # Schedule next job
        self.scheduler.add_job(
            self.schedule_tweet_job,
            trigger='date',
            run_date=next_run,
            id='tweet_job',
            max_instances=1,
            misfire_grace_time=300  # 5 minutes grace time
        )
        
        logger.info(f"Next tweet scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                   f"(in {interval_seconds/3600:.1f} hours)")
    
    def start(self):
        """Start the scheduler"""
        if self.status == SchedulerStatus.RUNNING:
            logger.warning("Scheduler is already running")
            return
        
        try:
            self.scheduler.start()
            self.status = SchedulerStatus.RUNNING
            
            # Schedule the first tweet
            self._schedule_next_tweet()
            
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            self.status = SchedulerStatus.ERROR
            raise
    
    def stop(self):
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown(wait=False)
            self.status = SchedulerStatus.STOPPED
            logger.info("Scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def pause(self):
        """Pause the scheduler"""
        if self.status != SchedulerStatus.RUNNING:
            logger.warning("Scheduler is not running")
            return
        
        try:
            self.scheduler.pause()
            self.status = SchedulerStatus.PAUSED
            logger.info("Scheduler paused")
            
        except Exception as e:
            logger.error(f"Error pausing scheduler: {e}")
    
    def resume(self):
        """Resume the scheduler"""
        if self.status != SchedulerStatus.PAUSED:
            logger.warning("Scheduler is not paused")
            return
        
        try:
            self.scheduler.resume()
            self.status = SchedulerStatus.RUNNING
            logger.info("Scheduler resumed")
            
        except Exception as e:
            logger.error(f"Error resuming scheduler: {e}")
    
    async def trigger_immediate_tweet(self) -> Dict[str, Any]:
        """Trigger an immediate tweet (for manual/API calls)"""
        logger.info("Manual tweet trigger requested")
        
        attempt = await self._generate_and_post_tweet()
        
        result = {
            "success": attempt.success,
            "timestamp": attempt.timestamp.isoformat(),
            "tweet_id": attempt.tweet_id,
            "error": attempt.error,
            "tweet_content": attempt.tweet_content,
            "generation_time": attempt.generation_time,
            "post_time": attempt.post_time,
            "daily_count": self.daily_tweet_count,
            "daily_limit": self.config.max_daily_tweets
        }
        
        if attempt.success:
            logger.info(f"Manual tweet successful: {attempt.tweet_id}")
        else:
            logger.warning(f"Manual tweet failed: {attempt.error}")
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status"""
        next_job = None
        if self.scheduler.get_job('tweet_job'):
            next_job = self.scheduler.get_job('tweet_job').next_run_time
        
        # Calculate success rate
        if self.attempt_history:
            recent_attempts = self.attempt_history[-20:]  # Last 20 attempts
            success_count = sum(1 for attempt in recent_attempts if attempt.success)
            success_rate = success_count / len(recent_attempts)
        else:
            success_rate = 0.0
        
        return {
            "status": self.status.value,
            "next_tweet": next_job.isoformat() if next_job else None,
            "daily_count": self.daily_tweet_count,
            "daily_limit": self.config.max_daily_tweets,
            "total_attempts": len(self.attempt_history),
            "success_rate": round(success_rate, 3),
            "last_attempt": self.attempt_history[-1].timestamp.isoformat() if self.attempt_history else None,
            "last_success": next((a.timestamp.isoformat() for a in reversed(self.attempt_history) if a.success), None),
            "configuration": {
                "min_interval_hours": self.config.min_interval_hours,
                "max_interval_hours": self.config.max_interval_hours,
                "max_daily_tweets": self.config.max_daily_tweets,
                "optimal_hours": self.config.optimal_hours,
                "avoid_hours": self.config.avoid_hours
            }
        }
    
    def get_recent_attempts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scheduling attempts"""
        recent = self.attempt_history[-limit:] if self.attempt_history else []
        return [
            {
                "timestamp": attempt.timestamp.isoformat(),
                "success": attempt.success,
                "tweet_id": attempt.tweet_id,
                "error": attempt.error,
                "tweet_preview": attempt.tweet_content[:50] + "..." if attempt.tweet_content and len(attempt.tweet_content) > 50 else attempt.tweet_content,
                "generation_time": attempt.generation_time,
                "post_time": attempt.post_time
            }
            for attempt in reversed(recent)
        ]
    
    def _job_executed(self, event):
        """Handle job execution events"""
        logger.debug(f"Job executed: {event.job_id}")
    
    def _job_error(self, event):
        """Handle job error events"""
        logger.error(f"Job error: {event.job_id} - {event.exception}")
        self.status = SchedulerStatus.ERROR

# Global scheduler instance
scheduler = IntelligentScheduler()

# Public interface functions
async def schedule_tweet() -> Dict[str, Any]:
    """Public interface for manual tweet scheduling"""
    return await scheduler.trigger_immediate_tweet()

def start_scheduler():
    """Start the tweet scheduler"""
    scheduler.start()

def stop_scheduler():
    """Stop the tweet scheduler"""
    scheduler.stop()

def get_scheduler_status() -> Dict[str, Any]:
    """Get scheduler status"""
    return scheduler.get_status()

def get_scheduler() -> IntelligentScheduler:
    """Get the scheduler instance"""
    return scheduler
