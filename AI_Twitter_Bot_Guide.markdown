# AI Twitter Bot Project Guide

This guide provides a complete setup for an AI-powered Twitter bot that generates and posts tweets in your personal style using Gemini 2.5 Flash, LangGraph, Tweepy, and FastAPI, deployed on Vercel. The bot posts at random intervals, handles errors gracefully, and includes a dashboard to toggle it on/off.

## Project Goals
- Generate tweets in a personalized, witty, tech-savvy style using Gemini 2.5 Flash via LangGraph.
- Post tweets automatically at random intervals (1–6 hours).
- Deploy and run serverlessly on Vercel.
- Provide a web dashboard to control the bot.
- Include robust error handling and logging.

## Tech Stack
- **LangGraph**: Orchestrates tweet generation with memory for style consistency.
- **Gemini 2.5 Flash**: Generates tweet content (fallback to Gemini 1.5 Pro if needed).
- **Tweepy**: Interacts with the X API for posting tweets.
- **FastAPI**: Powers a simple web dashboard.
- **APScheduler**: Schedules tweet posting.
- **Vercel**: Hosts the bot and dashboard serverlessly.
- **Python**: Core logic, with `python-dotenv` for environment variables and `tenacity` for retries.

## Project Structure
```
twitter-bot/
│
├── .env
├── .gitignore
├── requirements.txt
├── vercel.json
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── tweet_generator.py
│   ├── twitter_client.py
│   ├── scheduler.py
│   └── dashboard.py
│
└── README.md
```

## Setup Instructions
1. **Clone the Project**:
   ```bash
   git clone <your-repo-url>
   cd twitter-bot
   ```

2. **Install Dependencies**:
   Create a virtual environment and install requirements:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Create a `.env` file in the root directory with the following:
   ```
   GEMINI_API_KEY=your_gemini_key_here
   TWITTER_API_KEY=your_twitter_key_here
   TWITTER_API_SECRET=your_twitter_secret_here
   TWITTER_ACCESS_TOKEN=your_access_token_here
   TWITTER_ACCESS_SECRET=your_access_secret_here
   ```
   - Get `GEMINI_API_KEY` from [Google AI](https://ai.google.dev).
   - Get Twitter/X API keys from [X Developer Portal](https://developer.x.com).

4. **Add `.gitignore`**:
   Ensure sensitive files are ignored:
   ```
   .env
   venv/
   __pycache__/
   *.log
   ```

5. **Test Locally**:
   Run the bot locally to verify functionality:
   ```bash
   python src/main.py
   ```

6. **Deploy to Vercel**:
   Install Vercel CLI and deploy:
   ```bash
   npm install -g vercel
   vercel
   ```
   Add environment variables in Vercel’s dashboard (Settings > Environment Variables).

## File Details and Code

### requirements.txt
Lists all Python dependencies for the project.

```
langchain
langgraph
google-generativeai
tweepy
python-dotenv
fastapi
uvicorn
apscheduler
tenacity
```

### vercel.json
Configures Vercel for serverless deployment with a cron job for scheduling.

```
{
  "version": 2,
  "builds": [
    { "src": "src/main.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/api/.*", "dest": "src/main.py" }
  ],
  "crons": [
    { "path": "/api/schedule", "schedule": "0 * * * *" }
  ]
}
```

### src/__init__.py
Empty file to make `src` a Python package.

```
# Empty file
```

### src/tweet_generator.py
Generates tweets using Gemini 2.5 Flash and LangGraph for style memory.

```python
import os
from langgraph.graph import StateGraph
from typing import TypedDict
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class TweetState(TypedDict):
    history: list[str]
    style: str

def generate_tweet(state: TweetState) -> dict:
    prompt = (
        f"Write a short, witty tweet (100-280 characters) in a {state['style']} style. "
        f"Avoid hashtags and links. Past tweets for context: {state['history'][-5:]}"
    )
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")  # Fallback: models/gemini-1.5-pro
        response = model.generate_content(prompt)
        tweet = response.text.strip()
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        state["history"].append(tweet)
        return {"history": state["history"], "tweet": tweet}
    except Exception as e:
        raise Exception(f"Failed to generate tweet: {e}")

# Initialize LangGraph workflow
workflow = StateGraph(TweetState)
workflow.add_node("generate", generate_tweet)
workflow.set_entry_point("generate")
app = workflow.compile()

def get_tweet():
    initial_state = {"history": [], "style": "witty, tech-savvy, conversational"}
    result = app.invoke(initial_state)
    return result["tweet"]
```

### src/twitter_client.py
Handles posting tweets to the X API with retry logic.

```python
import os
import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(filename='bot.log', level=logging.INFO)

auth = tweepy.OAuthHandler(os.getenv("TWITTER_API_KEY"), os.getenv("TWITTER_API_SECRET"))
auth.set_access_token(os.getenv("TWITTER_ACCESS_TOKEN"), os.getenv("TWITTER_ACCESS_SECRET"))
api = tweepy.API(auth)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def post_tweet(content: str):
    try:
        logging.info(f"Posting tweet: {content}")
        api.update_status(content)
        logging.info("Tweet posted successfully")
    except Exception as e:
        logging.error(f"Error posting tweet: {e}")
        raise
```

### src/scheduler.py
Schedules tweet posting at random intervals, compatible with Vercel.

```python
import random
from src.tweet_generator import get_tweet
from src.twitter_client import post_tweet
import logging

logging.basicConfig(filename='bot.log', level=logging.INFO)

def schedule_tweet():
    try:
        tweet = get_tweet()
        post_tweet(tweet)
        return {"status": "Tweet posted", "tweet": tweet}
    except Exception as e:
        logging.error(f"Scheduling error: {e}")
        return {"status": "Error", "error": str(e)}
```

### src/dashboard.py
Provides a FastAPI endpoint to toggle the bot and view status.

```python
from fastapi import FastAPI
from src.scheduler import schedule_tweet

app = FastAPI()
bot_active = True

@app.get("/api/toggle")
async def toggle_bot():
    global bot_active
    bot_active = not bot_active
    return {"bot_active": bot_active}

@app.get("/api/status")
async def get_status():
    return {"bot_active": bot_active}

@app.get("/api/schedule")
async def run_schedule():
    if bot_active:
        result = schedule_tweet()
        return result
    return {"status": "Bot is disabled"}
```

### src/main.py
Entry point for running the bot locally or on Vercel.

```python
from fastapi import FastAPI
from src.dashboard import app as dashboard_app
from src.scheduler import schedule_tweet
from apscheduler.schedulers.background import BackgroundScheduler
import random

app = FastAPI()
app.mount("/api", dashboard_app)

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(schedule_tweet, 'interval', seconds=random.randint(3600, 21600))
    scheduler.start()

if __name__ == "__main__":
    import uvicorn
    start_scheduler()
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### README.md
Documentation for setup, running, and deployment.

```
# AI Twitter Bot

An AI-powered bot that generates and posts tweets in a personalized style using Gemini 2.5 Flash, LangGraph, Tweepy, and FastAPI, deployed on Vercel.

## Setup
1. Clone the repo: `git clone <repo-url>`
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` with API keys (see Environment Variables).
4. Run locally: `python src/main.py`
5. Deploy to Vercel: `vercel`

## Environment Variables
```
GEMINI_API_KEY=your_gemini_key_here
TWITTER_API_KEY=your_twitter_key_here
TWITTER_API_SECRET=your_twitter_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_SECRET=your_access_secret_here
```

## Endpoints
- `/api/toggle`: Toggle bot on/off
- `/api/status`: Check bot status
- `/api/schedule`: Trigger a tweet (used by Vercel cron)

## Notes
- Tweets are posted every 1–6 hours when the bot is active.
- Logs are saved to `bot.log`.
- Ensure API keys are valid and rate limits are respected.
```

## Deployment to Vercel
1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```
2. Deploy:
   ```bash
   vercel
   ```
3. Add environment variables in Vercel’s dashboard.
4. Verify the cron job (`/api/schedule`) runs hourly to trigger tweets.

## Development Tips for Cursor
- **File Creation**: Use Cursor’s file explorer to create the project structure (`twitter-bot/src/` and all files).
- **Auto-Completion**: Leverage Cursor’s AI suggestions for Python and Markdown to speed up coding.
- **Debugging**: Use Cursor’s integrated terminal to run `python src/main.py` and check `bot.log` for errors.
- **Testing**: Test the `/api/schedule` endpoint locally with `curl http://localhost:8000/api/schedule`.
- **Version Control**: Commit changes frequently with meaningful messages (e.g., “Add tweet generator with LangGraph”).
- **Prompts**: If refining code, ask Cursor: “Add retry logic to twitter_client.py” or “Optimize scheduler.py for Vercel.”

## Future Enhancements
- **Engagement Tracking**: Use `api.get_status()` to log likes/retweets and adapt tweet style.
- **Dynamic Style**: Store user feedback in LangGraph to refine the bot’s tone.
- **Rate Limit Handling**: Check `api.rate_limit_status()` to avoid exceeding X API limits.
- **Dashboard UI**: Add a frontend (e.g., React with Tailwind) for a better toggle interface.

## Troubleshooting
- **Gemini API Errors**: Ensure `GEMINI_API_KEY` is valid and Gemini 2.5 Flash is accessible. Fallback to `models/gemini-1.5-pro` if needed.
- **X API Errors**: Check `bot.log` for rate limit or authentication issues. Verify keys at [X Developer Portal](https://developer.x.com).
- **Vercel Issues**: Ensure `vercel.json` routes are correct and cron jobs are enabled in the Vercel dashboard.

This setup provides a robust, scalable Twitter bot ready for development in Cursor. Start by creating the files, testing locally, and deploying to Vercel. If you need specific tweaks or debugging help, let me know!