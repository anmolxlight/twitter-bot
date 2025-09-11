# Vercel Deployment Guide for AI Twitter Bot

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **Environment Variables**: All API keys and credentials ready

## Step 1: Prepare Your Repository

Your repository is already configured with:
- ✅ `vercel.json` with proper cron job configuration
- ✅ API endpoints for serverless cron execution
- ✅ Modified scheduler to work with Vercel

## Step 2: Deploy to Vercel

### Option A: Deploy via Vercel Dashboard (Recommended)

1. **Go to Vercel Dashboard**
   - Visit [vercel.com/dashboard](https://vercel.com/dashboard)
   - Click "New Project"

2. **Import Repository**
   - Connect your GitHub account if not already connected
   - Select your Twitter bot repository
   - Click "Import"

3. **Configure Project**
   - Project Name: `ai-twitter-bot` (or your preferred name)
   - Framework Preset: "Other"
   - Root Directory: `./` (leave default)
   - Build Command: Leave empty (Python doesn't need build)
   - Output Directory: Leave empty
   - Install Command: `pip install -r requirements.txt`

### Option B: Deploy via Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy from your project directory
vercel

# Follow the prompts:
# - Set up and deploy? Y
# - Which scope? (select your account)
# - Link to existing project? N
# - Project name: ai-twitter-bot
# - In which directory is your code located? ./
```

## Step 3: Set Environment Variables

In your Vercel project dashboard, go to **Settings** → **Environment Variables** and add:

### Required Variables:
```
GEMINI_API_KEY=your_gemini_api_key_here
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_ACCESS_TOKEN=your_twitter_access_token_here
TWITTER_ACCESS_SECRET=your_twitter_access_secret_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
```

### Optional Configuration Variables:
```
BOT_STYLE=witty, tech-savvy, conversational
MIN_INTERVAL_HOURS=1
MAX_INTERVAL_HOURS=6
LOG_LEVEL=INFO
VERCEL_DEPLOYMENT=true
AUTO_START=false
```

**Important**: Set these for **Production**, **Preview**, and **Development** environments.

## Step 4: Enable Cron Jobs

Vercel cron jobs are automatically configured via `vercel.json`:

- **Tweet Generation**: Every 3 hours (`0 */3 * * *`)
- **Health Check**: Every 30 minutes (`*/30 * * * *`)

### Cron Job Endpoints:
- `POST/GET /api/cron/tweet` - Generates and posts tweets
- `POST/GET /api/cron/health` - Health monitoring

## Step 5: Test Your Deployment

After deployment, test these endpoints:

1. **Health Check**:
   ```bash
   curl https://your-app.vercel.app/health
   ```

2. **Manual Tweet Trigger**:
   ```bash
   curl -X POST https://your-app.vercel.app/api/trigger-tweet
   ```

3. **Cron Tweet Endpoint**:
   ```bash
   curl https://your-app.vercel.app/api/cron/tweet
   ```

4. **Dashboard**:
   Visit `https://your-app.vercel.app/dashboard` to access the web interface

## Step 6: Monitor Your Bot

### Vercel Dashboard
- **Functions**: View function invocations and logs
- **Analytics**: Monitor performance and usage
- **Deployments**: Track deployment history

### Endpoints for Monitoring
- **Health**: `/health` - Comprehensive health check
- **Status**: `/info` - Application information
- **Ping**: `/api/ping` - Simple uptime check

### Logs
- View real-time logs in Vercel dashboard under "Functions" tab
- Each cron job execution will be logged with detailed information

## Step 7: Customize Cron Schedule (Optional)

To modify the tweet frequency, edit `vercel.json`:

```json
"crons": [
  {
    "path": "/api/cron/tweet",
    "schedule": "0 */2 * * *"  // Every 2 hours
  }
]
```

Common cron patterns:
- `0 */1 * * *` - Every hour
- `0 */2 * * *` - Every 2 hours
- `0 */4 * * *` - Every 4 hours
- `0 8,12,16,20 * * *` - At 8 AM, 12 PM, 4 PM, 8 PM

## Troubleshooting

### Common Issues:

1. **Environment Variables Not Set**
   - Error: Missing required environment variables
   - Solution: Add all required env vars in Vercel dashboard

2. **API Rate Limits**
   - Error: Twitter API rate limit exceeded
   - Solution: Increase cron interval or check daily limits

3. **Function Timeout**
   - Error: Function execution timeout
   - Solution: Increase `maxDuration` in `vercel.json` (currently 300s)

4. **Gemini API Issues**
   - Error: Gemini API key invalid or quota exceeded
   - Solution: Check API key and billing status

### Debugging Tips:

1. **Check Function Logs**:
   - Go to Vercel Dashboard → Functions → View logs
   - Look for error messages and stack traces

2. **Test Endpoints Individually**:
   ```bash
   # Test tweet generation only
   curl https://your-app.vercel.app/api/cron/health
   
   # Test manual tweet
   curl -X POST https://your-app.vercel.app/api/trigger-tweet
   ```

3. **Monitor Health Endpoint**:
   - Set up external monitoring (like UptimeRobot) to ping `/health`
   - Get alerts when the bot goes down

## Security Considerations

1. **Environment Variables**: Never commit API keys to your repository
2. **Cron Security**: Consider adding authentication headers for cron endpoints
3. **Rate Limiting**: Monitor and respect Twitter API rate limits
4. **Error Handling**: Ensure graceful failure handling for all components

## Performance Optimization

1. **Function Duration**: Monitor function execution times
2. **Memory Usage**: Check if you need to adjust memory limits
3. **Caching**: Consider implementing caching for tweet generation
4. **Monitoring**: Set up alerts for failed executions

## Support

If you encounter issues:
1. Check Vercel documentation: [vercel.com/docs](https://vercel.com/docs)
2. Review function logs in Vercel dashboard
3. Test individual components locally first
4. Check API status pages for Twitter and Google services

---

## Summary

Your Twitter bot will now:
- ✅ Generate tweets using Gemini AI every 3 hours
- ✅ Post tweets automatically via Vercel cron jobs
- ✅ Monitor health every 30 minutes
- ✅ Provide a web dashboard for monitoring
- ✅ Handle errors gracefully with proper logging
- ✅ Scale automatically with Vercel's serverless infrastructure

The bot will run continuously without any server maintenance required!
