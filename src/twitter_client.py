"""
Robust Twitter API Client

This module provides a comprehensive Twitter API client with advanced error handling,
rate limiting, retry logic, and comprehensive logging for the AI Twitter bot.
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json

import tweepy
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@dataclass
class TweetMetrics:
    """Track tweet performance metrics"""
    tweet_id: str
    text: str
    posted_at: datetime
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    impressions: int = 0

@dataclass
class RateLimitInfo:
    """Track rate limit information"""
    endpoint: str
    limit: int
    remaining: int
    reset_time: datetime

class TwitterClientError(Exception):
    """Custom exception for Twitter client errors"""
    pass

class RateLimitError(TwitterClientError):
    """Exception for rate limit issues"""
    pass

class AuthenticationError(TwitterClientError):
    """Exception for authentication issues"""
    pass

class TwitterClient:
    """Advanced Twitter API client with comprehensive error handling"""
    
    def __init__(self):
        """Initialize Twitter client with API credentials"""
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api_secret = os.getenv("TWITTER_API_SECRET")
        self.access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_secret = os.getenv("TWITTER_ACCESS_SECRET")
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        
        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            raise AuthenticationError("Missing Twitter API credentials")
        
        # Initialize APIs
        self.api_v1 = self._init_api_v1()
        self.api_v2 = self._init_api_v2()
        
        # Rate limiting tracking
        self.rate_limits: Dict[str, RateLimitInfo] = {}
        self.last_tweet_time: Optional[datetime] = None
        
        # Performance tracking
        self.tweet_history: List[TweetMetrics] = []
        
        logger.info("Twitter client initialized successfully")
    
    def _init_api_v1(self) -> tweepy.API:
        """Initialize Twitter API v1.1"""
        try:
            auth = tweepy.OAuth1UserHandler(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_secret
            )
            
            api = tweepy.API(
                auth,
                wait_on_rate_limit=True,
                retry_count=3,
                retry_delay=5,
                retry_errors=[500, 502, 503, 504]
            )
            
            # Verify credentials
            api.verify_credentials()
            logger.info("Twitter API v1.1 authentication successful")
            return api
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter API v1.1: {e}")
            raise AuthenticationError(f"Twitter API v1.1 authentication failed: {e}")
    
    def _init_api_v2(self) -> Optional[tweepy.Client]:
        """Initialize Twitter API v2 (if bearer token available)"""
        if not self.bearer_token:
            logger.warning("No bearer token provided, Twitter API v2 unavailable")
            return None
        
        try:
            client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
                wait_on_rate_limit=True
            )
            
            # Test the connection
            user = client.get_me()
            logger.info(f"Twitter API v2 authentication successful for user: {user.data.username}")
            return client
            
        except Exception as e:
            logger.warning(f"Failed to initialize Twitter API v2: {e}")
            return None
    
    def _check_rate_limits(self, endpoint: str) -> bool:
        """Check if we're within rate limits for an endpoint"""
        if endpoint in self.rate_limits:
            rate_limit = self.rate_limits[endpoint]
            if rate_limit.remaining <= 1 and datetime.now() < rate_limit.reset_time:
                wait_time = (rate_limit.reset_time - datetime.now()).total_seconds()
                logger.warning(f"Rate limit reached for {endpoint}, waiting {wait_time:.0f} seconds")
                return False
        return True
    
    def _update_rate_limits(self, response_headers: Dict[str, str], endpoint: str):
        """Update rate limit information from response headers"""
        try:
            if 'x-rate-limit-limit' in response_headers:
                limit = int(response_headers['x-rate-limit-limit'])
                remaining = int(response_headers['x-rate-limit-remaining'])
                reset_time = datetime.fromtimestamp(int(response_headers['x-rate-limit-reset']))
                
                self.rate_limits[endpoint] = RateLimitInfo(
                    endpoint=endpoint,
                    limit=limit,
                    remaining=remaining,
                    reset_time=reset_time
                )
                
                logger.debug(f"Rate limit updated for {endpoint}: {remaining}/{limit} remaining")
        except (KeyError, ValueError) as e:
            logger.debug(f"Could not parse rate limit headers: {e}")
    
    def _should_post_tweet(self) -> bool:
        """Check if enough time has passed since last tweet"""
        if self.last_tweet_time is None:
            return True
        
        # Minimum 10 minutes between tweets to avoid spam
        min_interval = timedelta(minutes=10)
        time_since_last = datetime.now() - self.last_tweet_time
        
        if time_since_last < min_interval:
            logger.warning(f"Too soon to post another tweet, waiting {(min_interval - time_since_last).total_seconds():.0f} more seconds")
            return False
        
        return True
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((tweepy.TooManyRequests, tweepy.HTTPException, ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def post_tweet(self, content: str, reply_to_id: Optional[str] = None) -> Optional[str]:
        """
        Post a tweet with comprehensive error handling and retry logic
        
        Args:
            content: Tweet content
            reply_to_id: ID of tweet to reply to (optional)
            
        Returns:
            Tweet ID if successful, None if failed
        """
        if not content or len(content.strip()) == 0:
            raise ValueError("Tweet content cannot be empty")
        
        if len(content) > 280:
            raise ValueError(f"Tweet too long: {len(content)} characters (max 280)")
        
        if not self._should_post_tweet():
            raise TwitterClientError("Rate limiting: too soon since last tweet")
        
        if not self._check_rate_limits("tweet_post"):
            raise RateLimitError("Rate limit reached for posting tweets")
        
        try:
            logger.info(f"Posting tweet: {content[:50]}{'...' if len(content) > 50 else ''}")
            
            # Use API v2 if available, fallback to v1.1
            if self.api_v2:
                response = self.api_v2.create_tweet(
                    text=content,
                    in_reply_to_tweet_id=reply_to_id
                )
                tweet_id = response.data['id']
                
            else:
                # Fallback to API v1.1
                status = self.api_v1.update_status(
                    status=content,
                    in_reply_to_status_id=reply_to_id
                )
                tweet_id = str(status.id)
            
            # Record successful tweet
            self.last_tweet_time = datetime.now()
            
            tweet_metrics = TweetMetrics(
                tweet_id=tweet_id,
                text=content,
                posted_at=self.last_tweet_time
            )
            
            self.tweet_history.append(tweet_metrics)
            
            # Keep only last 100 tweets in memory
            if len(self.tweet_history) > 100:
                self.tweet_history = self.tweet_history[-100:]
            
            logger.info(f"Tweet posted successfully with ID: {tweet_id}")
            return tweet_id
            
        except tweepy.Forbidden as e:
            error_msg = f"Permission denied when posting tweet: {e}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)
            
        except tweepy.TooManyRequests as e:
            error_msg = f"Rate limit exceeded: {e}"
            logger.error(error_msg)
            raise RateLimitError(error_msg)
            
        except tweepy.BadRequest as e:
            error_msg = f"Bad request when posting tweet: {e}"
            logger.error(error_msg)
            raise TwitterClientError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error posting tweet: {e}"
            logger.error(error_msg)
            raise TwitterClientError(error_msg)
    
    def get_tweet_metrics(self, tweet_id: str) -> Optional[TweetMetrics]:
        """Get metrics for a specific tweet"""
        if not self.api_v2:
            logger.warning("Twitter API v2 not available for metrics")
            return None
        
        try:
            tweet = self.api_v2.get_tweet(
                tweet_id,
                tweet_fields=['public_metrics', 'created_at'],
                user_fields=['public_metrics']
            )
            
            if tweet.data:
                metrics = tweet.data.public_metrics
                return TweetMetrics(
                    tweet_id=tweet_id,
                    text=tweet.data.text,
                    posted_at=tweet.data.created_at,
                    likes=metrics.get('like_count', 0),
                    retweets=metrics.get('retweet_count', 0),
                    replies=metrics.get('reply_count', 0),
                    impressions=metrics.get('impression_count', 0)
                )
                
        except Exception as e:
            logger.error(f"Failed to get tweet metrics: {e}")
            
        return None
    
    def update_tweet_metrics(self) -> List[TweetMetrics]:
        """Update metrics for recent tweets"""
        updated_metrics = []
        
        for tweet_metric in self.tweet_history[-10:]:  # Check last 10 tweets
            updated_metric = self.get_tweet_metrics(tweet_metric.tweet_id)
            if updated_metric:
                # Update the stored metric
                for i, stored_metric in enumerate(self.tweet_history):
                    if stored_metric.tweet_id == tweet_metric.tweet_id:
                        self.tweet_history[i] = updated_metric
                        updated_metrics.append(updated_metric)
                        break
        
        return updated_metrics
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information and statistics"""
        try:
            if self.api_v2:
                user = self.api_v2.get_me(user_fields=['public_metrics'])
                if user.data:
                    return {
                        'username': user.data.username,
                        'name': user.data.name,
                        'followers': user.data.public_metrics.get('followers_count', 0),
                        'following': user.data.public_metrics.get('following_count', 0),
                        'tweets': user.data.public_metrics.get('tweet_count', 0),
                        'likes': user.data.public_metrics.get('like_count', 0)
                    }
            else:
                user = self.api_v1.verify_credentials()
                return {
                    'username': user.screen_name,
                    'name': user.name,
                    'followers': user.followers_count,
                    'following': user.friends_count,
                    'tweets': user.statuses_count,
                    'likes': user.favourites_count
                }
                
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            
        return None
    
    def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet by ID"""
        try:
            if self.api_v2:
                self.api_v2.delete_tweet(tweet_id)
            else:
                self.api_v1.destroy_status(tweet_id)
                
            logger.info(f"Tweet {tweet_id} deleted successfully")
            
            # Remove from history
            self.tweet_history = [t for t in self.tweet_history if t.tweet_id != tweet_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete tweet {tweet_id}: {e}")
            return False
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        try:
            if self.api_v1:
                rate_limits = self.api_v1.get_rate_limit_status()
                return {
                    'statuses_update': rate_limits['resources']['statuses']['/statuses/update'],
                    'statuses_show': rate_limits['resources']['statuses']['/statuses/show/:id'],
                    'application_rate_limit_status': rate_limits['resources']['application']['/application/rate_limit_status']
                }
        except Exception as e:
            logger.error(f"Failed to get rate limit status: {e}")
            
        return {}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of recent tweets"""
        if not self.tweet_history:
            return {}
        
        recent_tweets = self.tweet_history[-20:]  # Last 20 tweets
        
        total_likes = sum(t.likes for t in recent_tweets)
        total_retweets = sum(t.retweets for t in recent_tweets)
        total_replies = sum(t.replies for t in recent_tweets)
        
        avg_likes = total_likes / len(recent_tweets) if recent_tweets else 0
        avg_retweets = total_retweets / len(recent_tweets) if recent_tweets else 0
        avg_replies = total_replies / len(recent_tweets) if recent_tweets else 0
        
        return {
            'total_tweets': len(self.tweet_history),
            'recent_tweets': len(recent_tweets),
            'total_likes': total_likes,
            'total_retweets': total_retweets,
            'total_replies': total_replies,
            'avg_likes': round(avg_likes, 2),
            'avg_retweets': round(avg_retweets, 2),
            'avg_replies': round(avg_replies, 2),
            'last_tweet_time': self.last_tweet_time.isoformat() if self.last_tweet_time else None
        }

# Global instance
twitter_client = TwitterClient()

def post_tweet(content: str) -> Optional[str]:
    """Public interface for posting tweets"""
    return twitter_client.post_tweet(content)

def get_client() -> TwitterClient:
    """Get the Twitter client instance"""
    return twitter_client
