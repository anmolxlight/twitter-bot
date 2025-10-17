"""
Advanced Tweet Generator using Gemini 2.5 Flash and LangGraph

This module provides intelligent tweet generation with style consistency,
memory management, and robust error handling.
"""

import os
import json
import logging
import random
from typing import TypedDict, List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from langgraph.graph import StateGraph, END
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@dataclass
class TweetMetrics:
    """Track tweet performance metrics"""
    length: int
    sentiment: str
    style_score: float
    generated_at: datetime

class TweetState(TypedDict):
    """State management for tweet generation workflow"""
    history: List[str]
    style: str
    context: str
    constraints: Dict[str, Any]
    metrics: List[TweetMetrics]
    current_tweet: Optional[str]
    error: Optional[str]
    retry_count: int

class TweetGenerator:
    """Advanced tweet generator with LangGraph orchestration"""
    
    def __init__(self):
        self.style = os.getenv("BOT_STYLE", "techy gen z into cinema, anime, ml, football, f1, web3, startups")
        self.max_retries = 3
        self.max_history = 20
        self.controversial_frequency = 0.35  # 35% chance of controversial tweet
        self.tweet_counter = 0
        
        # Initialize Gemini models with fallback - using correct API format
        self.primary_model = "gemini-2.5-flash"  # Latest experimental model
        self.fallback_model = "gemini-2.5-pro"  # Stable latest flash   
        
        # Tweet constraints
        self.constraints = {
            "max_length": 280,
            "min_length": 50,
            "avoid_hashtags": True,
            "avoid_links": True,
            "avoid_mentions": True,
            "lowercase_only": True,
            "topics": [
                "anime and cinema critique",
                "machine learning and AI developments",
                "football tactics and moments",
                "formula 1 drama and tech",
                "filmmaking and cinematography",
                "web3 and crypto takes",
                "startup culture and tech industry",
                "web shows and streaming content",
                "computer science and programming",
                "tech products and gadgets",
                "sports analytics and stats",
                "creative technology and tools"
            ]
        }
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for tweet generation"""
        workflow = StateGraph(TweetState)
        
        # Add nodes
        workflow.add_node("analyze_context", self._analyze_context)
        workflow.add_node("generate_tweet", self._generate_tweet)
        workflow.add_node("validate_tweet", self._validate_tweet)
        workflow.add_node("enhance_tweet", self._enhance_tweet)
        workflow.add_node("finalize", self._finalize_tweet)
        workflow.add_node("handle_error", self._handle_error)
        
        # Set entry point
        workflow.set_entry_point("analyze_context")
        
        # Add edges
        workflow.add_edge("analyze_context", "generate_tweet")
        workflow.add_conditional_edges(
            "generate_tweet",
            self._should_validate,
            {
                "validate": "validate_tweet",
                "error": "handle_error"
            }
        )
        workflow.add_conditional_edges(
            "validate_tweet",
            self._should_enhance,
            {
                "enhance": "enhance_tweet",
                "finalize": "finalize",
                "retry": "generate_tweet",
                "error": "handle_error"
            }
        )
        workflow.add_edge("enhance_tweet", "finalize")
        workflow.add_edge("finalize", END)
        workflow.add_conditional_edges(
            "handle_error",
            self._should_retry,
            {
                "retry": "generate_tweet",
                "end": END
            }
        )
        
        return workflow.compile()
    
    def _analyze_context(self, state: TweetState) -> Dict[str, Any]:
        """Analyze context for tweet generation"""
        try:
            # Determine current context based on time and recent tweets
            current_hour = datetime.now().hour
            
            if 6 <= current_hour < 12:
                context = "morning motivation and productivity"
            elif 12 <= current_hour < 18:
                context = "afternoon insights and tech discussions"
            elif 18 <= current_hour < 22:
                context = "evening reflections and industry thoughts"
            else:
                context = "late night contemplations and innovation ideas"
            
            # Add variety based on recent history
            if len(state["history"]) > 0:
                recent_topics = self._extract_topics(state["history"][-5:])
                if len(recent_topics) > 2:
                    context += f", avoiding recent topics: {', '.join(recent_topics)}"
            
            state["context"] = context
            logger.info(f"Context analyzed: {context}")
            return state
            
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            state["error"] = f"Context analysis error: {e}"
            return state
    
    def _generate_tweet(self, state: TweetState) -> Dict[str, Any]:
        """Generate tweet using Gemini AI"""
        try:
            prompt = self._build_prompt(state)
            
            # Try primary model first
            model_name = self.primary_model
            try:
                model = genai.GenerativeModel(model_name)
                # Configure safety settings to allow professional content
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        top_p=0.9,
                        top_k=40,
                        max_output_tokens=100,
                    ),
                    safety_settings=safety_settings
                )
                tweet = response.text.strip()
                
            except Exception as primary_error:
                logger.warning(f"Primary model failed: {primary_error}, trying fallback")
                model_name = self.fallback_model
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                tweet = response.text.strip()
            
            # Clean up the tweet
            tweet = self._clean_tweet(tweet)
            
            state["current_tweet"] = tweet
            state["error"] = None
            
            logger.info(f"Tweet generated using {model_name}: {tweet[:50]}...")
            return state
            
        except Exception as e:
            logger.error(f"Tweet generation failed: {e}")
            state["error"] = f"Generation error: {e}"
            state["retry_count"] = state.get("retry_count", 0) + 1
            return state
    
    def _validate_tweet(self, state: TweetState) -> Dict[str, Any]:
        """Validate generated tweet against constraints"""
        tweet = state["current_tweet"]
        
        if not tweet:
            state["error"] = "Empty tweet generated"
            return state
        
        # Length validation
        if len(tweet) > self.constraints["max_length"]:
            tweet = tweet[:self.constraints["max_length"] - 3] + "..."
            state["current_tweet"] = tweet
        
        if len(tweet) < self.constraints["min_length"]:
            state["error"] = "Tweet too short"
            return state
        
        # Content validation
        if self.constraints["avoid_hashtags"] and "#" in tweet:
            tweet = " ".join(word for word in tweet.split() if not word.startswith("#"))
            state["current_tweet"] = tweet
        
        if self.constraints["avoid_links"] and ("http" in tweet.lower() or "www." in tweet.lower()):
            state["error"] = "Tweet contains links"
            return state
        
        # Check for duplicate content
        if tweet in state["history"]:
            state["error"] = "Duplicate tweet detected"
            return state
        
        # Calculate metrics
        metrics = TweetMetrics(
            length=len(tweet),
            sentiment=self._analyze_sentiment(tweet),
            style_score=self._calculate_style_score(tweet, state["style"]),
            generated_at=datetime.now()
        )
        
        state["metrics"].append(metrics)
        logger.info(f"Tweet validated: length={metrics.length}, sentiment={metrics.sentiment}")
        
        return state
    
    def _enhance_tweet(self, state: TweetState) -> Dict[str, Any]:
        """Enhance tweet if needed"""
        tweet = state["current_tweet"]
        metrics = state["metrics"][-1] if state["metrics"] else None
        
        if metrics and metrics.style_score < 0.7:
            # Try to enhance the tweet
            enhancement_prompt = (
                f"Enhance this tweet to be more {state['style']}: '{tweet}'. "
                f"Keep it under {self.constraints['max_length']} characters. "
                f"Maintain the core message but improve the style and engagement."
            )
            
            try:
                model = genai.GenerativeModel(self.primary_model)
                response = model.generate_content(enhancement_prompt)
                enhanced_tweet = self._clean_tweet(response.text.strip())
                
                if len(enhanced_tweet) <= self.constraints["max_length"]:
                    state["current_tweet"] = enhanced_tweet
                    logger.info("Tweet enhanced successfully")
                
            except Exception as e:
                logger.warning(f"Tweet enhancement failed: {e}")
        
        return state
    
    def _finalize_tweet(self, state: TweetState) -> Dict[str, Any]:
        """Finalize the tweet and update history"""
        tweet = state["current_tweet"]
        
        # Add to history
        state["history"].append(tweet)
        
        # Trim history if too long
        if len(state["history"]) > self.max_history:
            state["history"] = state["history"][-self.max_history:]
        
        logger.info(f"Tweet finalized: {tweet}")
        return state
    
    def _handle_error(self, state: TweetState) -> Dict[str, Any]:
        """Handle errors in the generation process"""
        error = state.get("error", "Unknown error")
        retry_count = state.get("retry_count", 0)
        
        logger.error(f"Error in tweet generation (attempt {retry_count}): {error}")
        
        if retry_count >= self.max_retries:
            # Generate a fallback tweet
            fallback_tweets = [
                "ngl the intersection of tech and creativity is where the magic happens",
                "been thinking about how ml models are basically pattern matching on steroids",
                "lowkey miss when f1 cars actually sounded cool",
                "cinematography in anime hits different when you notice the composition",
                "everyone talks about disruption but most startups just copy what works",
                "the best code is the code you don't have to write tbh",
                "football tactics evolved so much but people still think it's just running around",
                "watching how streaming changed content creation is wild"
            ]
            
            state["current_tweet"] = random.choice(fallback_tweets)
            state["error"] = None
            logger.info("Using fallback tweet due to repeated failures")
        
        return state
    
    def _should_validate(self, state: TweetState) -> str:
        """Determine if tweet should be validated"""
        return "error" if state.get("error") else "validate"
    
    def _should_enhance(self, state: TweetState) -> str:
        """Determine if tweet should be enhanced"""
        if state.get("error"):
            retry_count = state.get("retry_count", 0)
            return "retry" if retry_count < self.max_retries else "error"
        
        metrics = state["metrics"][-1] if state["metrics"] else None
        if metrics and metrics.style_score < 0.7 and len(state["current_tweet"]) < 200:
            return "enhance"
        
        return "finalize"
    
    def _should_retry(self, state: TweetState) -> str:
        """Determine if generation should be retried"""
        retry_count = state.get("retry_count", 0)
        return "retry" if retry_count < self.max_retries else "end"
    
    def _build_prompt(self, state: TweetState) -> str:
        """Build the generation prompt"""
        self.tweet_counter += 1
        
        # Determine if this should be a controversial tweet
        is_controversial = random.random() < self.controversial_frequency
        
        # Diverse topics matching the personality
        regular_topics = [
            # Cinema & Shows
            "a hot take on a recent film or movie trend",
            "why some director's style is underrated or overrated",
            "unpopular opinion about a popular web series",
            "cinematography techniques that viewers don't notice",
            "how streaming changed the way we consume content",
            
            # Anime
            "why certain anime is overhyped or underrated",
            "comparing anime storytelling to western cinema",
            "discussing animation quality and studio drama",
            "manga vs anime adaptation debates",
            
            # ML & AI
            "practical thoughts on current AI developments",
            "why some ml models are overhyped",
            "real world applications of machine learning",
            "the hype vs reality in AI products",
            "llm capabilities and limitations",
            "transformer architectures and their impact",
            
            # Football
            "tactical analysis of recent matches",
            "why certain players are overrated or underrated",
            "comparing football eras and playstyles",
            "transfer market thoughts and club strategies",
            "analytics in modern football",
            
            # Formula 1
            "f1 technical regulations and their impact",
            "driver comparisons and team strategies",
            "the engineering behind f1 performance",
            "race strategy and pit stop analysis",
            "why certain teams dominate certain tracks",
            
            # Tech & CS
            "programming language preferences and why",
            "software engineering practices and trade-offs",
            "thoughts on new frameworks or tools",
            "developer culture and work experiences",
            "interesting algorithms or data structures",
            
            # Web3 & Startups
            "realistic takes on blockchain use cases",
            "startup culture observations",
            "why most web3 projects don't make sense",
            "founder mindset and building in public",
            "vc funding dynamics and startup metrics",
            
            # Filmmaking
            "practical filmmaking techniques and gear",
            "color grading and visual storytelling",
            "how budget affects creative decisions",
            "editing techniques that shape narrative",
            
            # General techy observations
            "tech product launches and their actual value",
            "how technology shapes culture",
            "productivity tools and their placebo effect",
            "social media algorithms and content creation"
        ]
        
        # Controversial/ragebait topics - intentionally wrong or provocative
        controversial_topics = [
            # Cinema & Anime ragebaits
            "say something objectively wrong about a beloved film that will make people correct you (e.g., 'nolan is overrated', 'mcu peaked with iron man 2', 'dubbed anime is better than subbed')",
            "claim a controversial opinion about cinematography or directing that cinephiles will debate (e.g., 'lens choice doesn't matter that much', 'handheld camera is lazy filmmaking')",
            "make a wrong statement about anime that fans will rush to correct (e.g., 'one piece animation is the best', 'filler episodes are the best part')",
            
            # ML & AI ragebaits
            "say something technically incorrect about AI that engineers will correct (e.g., 'transformers are just fancy if-else statements', 'ai will replace all programmers by 2025')",
            "claim a wrong understanding of ml concepts to trigger corrections (e.g., 'deep learning is just statistics', 'gpt understands what it's saying')",
            "make deliberately oversimplified takes on ai that experts will debate (e.g., 'prompt engineering is the future of coding', 'agi is 2 years away')",
            
            # Football ragebaits
            "say something factually wrong about football tactics or history (e.g., 'messi carried argentina alone', 'ronaldo invented the knuckleball', 'possession football is boring')",
            "make a hot take comparing players that will spark debate (e.g., 'current gen players are softer', '[player x] better than [legend]')",
            "state wrong stats or game analysis that football nerds will correct (e.g., 'xg is useless', 'defenders don't need technical skills')",
            
            # Formula 1 ragebaits
            "say something wrong about f1 tech or regulations (e.g., 'drs ruined f1', 'ground effect cars are slower', 'bring back v12 engines')",
            "make incorrect driver comparisons that f1 fans will debate (e.g., 'it's all the car', '[current driver] would beat [legend] easily')",
            "claim wrong things about race strategy that will be corrected (e.g., 'pit stops are just driver skill', 'weather doesn't matter much')",
            
            # Tech & CS ragebaits
            "say something wrong about programming that devs will correct (e.g., 'javascript is the best language', 'you don't need to learn data structures', 'vim users are just showing off')",
            "make controversial framework takes that spark debate (e.g., 'react is dying', 'php is better than python', 'tabs vs spaces doesn't matter')",
            "claim incorrect things about cs fundamentals (e.g., 'big o notation is overrated', 'clean code is a waste of time')",
            
            # Web3 & Startups ragebaits
            "say overly optimistic or cynical things about web3 (e.g., 'nfts will replace all contracts', 'blockchain has zero real use cases', 'web3 is just aws with extra steps')",
            "make wrong claims about startup culture (e.g., 'vcs are just gamblers', 'you need a co-founder to succeed', 'raise money or die')",
            "state incorrect things about crypto or protocols (e.g., 'proof of stake is centralized', 'bitcoin is dead', 'solana > ethereum')",
            
            # Cross-domain ragebaits
            "compare unrelated things incorrectly to spark debate (e.g., 'coding is harder than filmmaking', 'sports analytics ruined the games', 'ai-generated art is better')",
            "make sweeping generalizations that people will counter (e.g., 'all [x] are overrated', 'nobody actually uses [y]', '[z] was better 10 years ago')"
        ]
        
        selected_topic = random.choice(controversial_topics if is_controversial else regular_topics)
        
        # Build comprehensive system prompt
        system_prompt = f"""
You are a tech-savvy gen z who's genuinely into cinema, web shows, anime, machine learning, football, formula 1, filmmaking, computer science, AI, web3, startups, and technology culture.

PERSONALITY:
- You're knowledgeable but not pretentious
- You have genuine takes, not just performative hot takes (unless it's a ragebait)
- You code, watch films/anime, follow football and f1, and understand the tech behind things
- You're critical but fair, except when deliberately being controversial
- You appreciate both technical excellence and creative work
- You're skeptical of hype but excited about real innovation
- You're not trying too hard to be cool, just being yourself

WRITING STYLE:
- ALL lowercase letters, no exceptions
- Normal gen z but not overdoing the slang
- Use natural language, slight casual tone
- No hashtags, no links, no mentions
- Be specific when possible (mention actual techniques, players, shows, etc.)
- Sound like a human, not a bot
- Keep it concise and punchy
- Can use 'tbh', 'ngl', 'lowkey', 'fr' sparingly and naturally
- Vary sentence structure
- Some tweets can be single statements, others can be multi-sentence

CONTENT GUIDELINES:
- Be authentic - share actual insights or observations
- Don't just state obvious facts
- Can be analytical, observational, or thought-provoking
- Mix technical knowledge with cultural awareness
- Show personality through your interests
- Don't repeat topics or sentence structures from recent tweets

{"CONTROVERSIAL MODE: You're making a ragebait tweet - say something intentionally wrong, oversimplified, or provocative that will make people correct you or debate in comments. The goal is engagement through (harmless) controversy. Don't be offensive, just wrong or hot-takey enough that knowledgeable people will want to respond. Still maintain lowercase and casual style." if is_controversial else "REGULAR MODE: Share a genuine take, insight, or observation. Be thoughtful and interesting."}

TOPIC: {selected_topic}

Generate a tweet (under 280 characters) about this topic. Make it sound natural and genuine. Remember: all lowercase, no hashtags/links.
"""
        
        return system_prompt
    
    def _clean_tweet(self, tweet: str) -> str:
        """Clean and format tweet"""
        # Remove quotes if present
        tweet = tweet.strip('"\'')
        
        # Remove common prefixes (case insensitive)
        prefixes = ["Tweet:", "Here's a tweet:", "Generated tweet:", "@", "tweet:", "here's a tweet:", "generated tweet:"]
        for prefix in prefixes:
            if tweet.lower().startswith(prefix.lower()):
                tweet = tweet[len(prefix):].strip()
        
        # Convert to lowercase (enforcing style)
        tweet = tweet.lower()
        
        # Ensure proper sentence structure (but keep lowercase)
        tweet = tweet.strip()
        
        # Don't force periods - let tweets end naturally
        # Gen Z tweets don't always need punctuation
        
        return tweet
    
    def _extract_topics(self, tweets: List[str]) -> List[str]:
        """Extract topics from recent tweets"""
        # Simple keyword extraction
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}
        
        topics = []
        for tweet in tweets:
            words = tweet.lower().split()
            significant_words = [word.strip('.,!?') for word in words if len(word) > 4 and word.lower() not in common_words]
            topics.extend(significant_words)
        
        # Return most common topics
        from collections import Counter
        return [topic for topic, count in Counter(topics).most_common(3)]
    
    def _analyze_sentiment(self, tweet: str) -> str:
        """Simple sentiment analysis"""
        positive_words = ['great', 'awesome', 'amazing', 'excellent', 'fantastic', 'wonderful', 'brilliant', 'innovative', 'exciting', 'love']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'disappointing', 'frustrating', 'annoying', 'hate']
        
        tweet_lower = tweet.lower()
        positive_count = sum(1 for word in positive_words if word in tweet_lower)
        negative_count = sum(1 for word in negative_words if word in tweet_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _calculate_style_score(self, tweet: str, target_style: str) -> float:
        """Calculate how well tweet matches target style"""
        # Simple scoring based on style keywords
        style_keywords = {
            'witty': ['clever', 'smart', 'funny', 'ironic', 'amusing'],
            'tech-savvy': ['AI', 'technology', 'digital', 'innovation', 'code', 'programming', 'software'],
            'conversational': ['you', 'we', 'us', 'think', 'feel', 'believe', 'wonder']
        }
        
        score = 0.5  # Base score
        tweet_lower = tweet.lower()
        
        for style, keywords in style_keywords.items():
            if style in target_style.lower():
                matches = sum(1 for keyword in keywords if keyword in tweet_lower)
                score += min(matches * 0.1, 0.3)
        
        return min(score, 1.0)
    
    def generate_tweet(self) -> str:
        """Main method to generate a tweet"""
        initial_state: TweetState = {
            "history": [],
            "style": self.style,
            "context": "",
            "constraints": self.constraints,
            "metrics": [],
            "current_tweet": None,
            "error": None,
            "retry_count": 0
        }
        
        try:
            # Load existing history if available
            # In production, this would come from a database or cache
            
            result = self.workflow.invoke(initial_state)
            
            if result.get("current_tweet"):
                return result["current_tweet"]
            else:
                raise Exception("Failed to generate tweet after all retries")
                
        except Exception as e:
            logger.error(f"Tweet generation workflow failed: {e}")
            # Return a safe fallback
            return "Innovation never stops. What are you building today?"

# Global instance
tweet_generator = TweetGenerator()

def get_tweet() -> str:
    """Public interface for tweet generation"""
    return tweet_generator.generate_tweet()
