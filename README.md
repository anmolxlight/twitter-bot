# 🤖 AI Twitter Bot

An intelligent, production-ready Twitter bot powered by **Gemini 2.5 Flash**, **LangGraph**, and **FastAPI**. Features adaptive scheduling, sophisticated content generation, comprehensive monitoring, and seamless Vercel deployment.

## ✨ Features

- **🧠 Intelligent Content Generation**: Uses Gemini 2.5 Flash with LangGraph for consistent, high-quality tweets
- **⏰ Adaptive Scheduling**: Smart timing with performance-based adjustments (1-6 hours intervals)
- **📊 Comprehensive Dashboard**: Real-time monitoring, controls, and analytics
- **🔧 Robust Error Handling**: Retry logic, rate limiting, and graceful degradation
- **☁️ Vercel-Ready**: Optimized for serverless deployment with cron jobs
- **📈 Performance Tracking**: Detailed analytics and success rate monitoring
- **🎛️ Easy Configuration**: Environment-based settings and API controls

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Twitter Developer Account ([Apply here](https://developer.x.com))
- Google AI API Key ([Get one here](https://ai.google.dev))

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd twitter-bot
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Gemini AI API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Twitter/X API Credentials
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_ACCESS_TOKEN=your_twitter_access_token_here
TWITTER_ACCESS_SECRET=your_twitter_access_secret_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# Bot Configuration (Optional)
BOT_STYLE=witty, tech-savvy, conversational
MIN_INTERVAL_HOURS=1
MAX_INTERVAL_HOURS=6
LOG_LEVEL=INFO
```

### 4. Run Locally

```bash
# Development mode with auto-reload
python src/main.py --mode dev

# Production mode
python src/main.py --mode prod

# Test mode (verify setup)
python src/main.py --mode test
```

Visit `http://localhost:8000` to access the dashboard.

## 📋 API Documentation

### Dashboard Endpoints

- `GET /` - Main dashboard interface
- `GET /health` - Comprehensive health check
- `GET /info` - Application information

### Bot Control API

- `GET /api/status` - Get bot status and metrics
- `POST /api/toggle` - Enable/disable the bot
- `POST /api/tweet` - Trigger immediate tweet
- `GET /api/generate-preview` - Generate tweet preview
- `GET /api/analytics?days=7` - Get performance analytics
- `DELETE /api/tweet/{tweet_id}` - Delete specific tweet

### Monitoring API

- `GET /api/account` - Twitter account information
- `GET /api/ping` - Simple health ping
- `POST /api/scheduler/config` - Update scheduler settings

### Vercel Cron Endpoint

- `GET /api/schedule` - Cron job endpoint (auto-triggered)

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ | - | Google AI API key |
| `TWITTER_API_KEY` | ✅ | - | Twitter API key |
| `TWITTER_API_SECRET` | ✅ | - | Twitter API secret |
| `TWITTER_ACCESS_TOKEN` | ✅ | - | Twitter access token |
| `TWITTER_ACCESS_SECRET` | ✅ | - | Twitter access secret |
| `TWITTER_BEARER_TOKEN` | ❌ | - | Twitter bearer token (v2 API) |
| `BOT_STYLE` | ❌ | `witty, tech-savvy, conversational` | Bot personality |
| `MIN_INTERVAL_HOURS` | ❌ | `1` | Minimum hours between tweets |
| `MAX_INTERVAL_HOURS` | ❌ | `6` | Maximum hours between tweets |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `AUTO_START` | ❌ | `true` | Auto-start on deployment |

### Scheduler Configuration

The bot includes intelligent scheduling with these features:

- **Adaptive Timing**: Adjusts intervals based on performance
- **Optimal Hours**: Prefers posting during 6AM-9PM
- **Daily Limits**: Maximum 8 tweets per day (configurable)
- **Performance-Based**: Increases intervals after failures
- **Time Zone Aware**: Respects optimal posting times

Update via API:
```bash
curl -X POST "http://localhost:8000/api/scheduler/config" \
  -H "Content-Type: application/json" \
  -d '{
    "min_interval_hours": 2,
    "max_interval_hours": 4,
    "max_daily_tweets": 6,
    "optimal_hours": [9, 12, 15, 18],
    "avoid_hours": [0, 1, 2, 3, 4, 5]
  }'
```

## 🌐 Deployment

### Vercel Deployment (Recommended)

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel
   ```

3. **Configure Environment Variables**:
   - Go to your Vercel dashboard
   - Navigate to Settings → Environment Variables
   - Add all required environment variables from your `.env` file

4. **Verify Cron Jobs**:
   - Check that the cron job is enabled in Vercel dashboard
   - The bot will automatically post every 2 hours when enabled

### Alternative Deployments

#### Heroku
```bash
# Install Heroku CLI
heroku create your-twitter-bot
heroku config:set GEMINI_API_KEY=your_key
heroku config:set TWITTER_API_KEY=your_key
# ... add other env vars
git push heroku main
```

#### Railway
```bash
# Install Railway CLI
railway login
railway init
railway add
# Configure environment variables in Railway dashboard
railway deploy
```

#### Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "src/main.py", "--mode", "prod"]
```

## 📊 Monitoring and Analytics

### Dashboard Features

- **Real-time Status**: Bot state, scheduler status, daily progress
- **Performance Metrics**: Success rate, response times, error tracking
- **Tweet Management**: View recent tweets, delete if needed
- **Configuration**: Update settings without redeployment

### Key Metrics

- **Success Rate**: Percentage of successful tweet attempts
- **Daily Progress**: Tweets posted vs. daily limit
- **Response Times**: Generation and posting performance
- **Error Analysis**: Categorized error breakdown

### Logging

All activities are logged with configurable levels:
- `DEBUG`: Detailed execution information
- `INFO`: General operational messages
- `WARNING`: Important notices and recoverable errors
- `ERROR`: Error conditions requiring attention

Log files are saved to `bot.log` with automatic rotation.

## 🛠️ Development

### Project Structure

```
twitter-bot/
├── src/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Application entry point
│   ├── tweet_generator.py   # AI-powered tweet generation
│   ├── twitter_client.py    # Twitter API integration
│   ├── scheduler.py         # Intelligent scheduling
│   └── dashboard.py         # FastAPI dashboard
├── .env.example             # Environment template
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
├── vercel.json            # Vercel configuration
└── README.md              # This file
```

### Adding Features

1. **Custom Tweet Types**: Extend `TweetGenerator` class
2. **New Endpoints**: Add routes to `dashboard.py`
3. **Enhanced Analytics**: Modify metrics collection
4. **Additional AI Models**: Integrate with `tweet_generator.py`

### Testing

```bash
# Run basic functionality tests
python src/main.py --mode test

# Test tweet generation
python -c "from src.tweet_generator import get_tweet; print(get_tweet())"

# Test Twitter client
python -c "from src.twitter_client import get_client; print(get_client().get_account_info())"
```

## 🔍 Troubleshooting

### Common Issues

#### "Missing environment variables"
- Ensure all required API keys are in `.env` file
- Check that `.env` is in the project root
- Verify no extra spaces in environment variable values

#### "Twitter authentication failed"
- Verify API keys are correct and active
- Check Twitter developer portal for account status
- Ensure elevated access for v2 API features

#### "Gemini API errors"
- Confirm API key is valid and has quota
- Check if Gemini 2.5 Flash is available in your region
- Monitor API usage limits

#### "Rate limit exceeded"
- Bot automatically handles rate limits with backoff
- Check daily/monthly Twitter API limits
- Review posting frequency settings

#### "Vercel deployment issues"
- Ensure all environment variables are set in Vercel dashboard
- Check function timeout settings (max 60s for hobby plan)
- Verify cron job is enabled

### Getting Help

1. **Check Logs**: Review `bot.log` for detailed error information
2. **Dashboard Status**: Use `/health` endpoint for system status
3. **API Testing**: Use `/api/ping` to verify connectivity
4. **Environment Check**: Run in test mode to validate setup

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⭐ Support

If you find this project helpful, please give it a star! For issues and feature requests, please use the GitHub issue tracker.

---

**Built with ❤️ using Gemini AI, LangGraph, FastAPI, and modern Python practices.**
