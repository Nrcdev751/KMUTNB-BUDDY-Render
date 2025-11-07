# Railway Deployment Guide for KMUTNB Buddy LINE Bot

## Prerequisites
- Railway account (sign up at [railway.app](https://railway.app))
- GitHub repository with your code
- LINE Bot channel with access token and secret
- Google Gemini API key

## Step 1: Prepare Your Code

Your project is already configured with:
- `requirements.txt` with compatible dependencies
- `Procfile` for Railway deployment
- `.env.example` showing required environment variables

## Step 2: Push to GitHub

1. Make sure all your changes are committed to Git:
```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

## Step 3: Deploy to Railway

1. Log in to [Railway](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway will automatically detect your Python application

## Step 4: Configure Environment Variables

In your Railway project settings, add these environment variables:

```
LINE_CHANNEL_ACCESS_TOKEN=your_actual_line_channel_access_token
LINE_CHANNEL_SECRET=your_actual_line_channel_secret
GEMINI_API_KEY=your_actual_gemini_api_key
```

## Step 5: Update LINE Bot Webhook

1. Once deployed, get your Railway URL from the dashboard
2. Go to your LINE Bot console
3. Update the webhook URL to: `https://your-app-name.railway.app/callback`

## Step 6: Verify Deployment

1. Check the logs in Railway dashboard
2. Test the `/hello` endpoint: `https://your-app-name.railway.app/hello`
3. Test your LINE Bot by sending a message

## Troubleshooting

### Build Errors
- If you encounter pandas build errors, ensure you're using pandas==2.1.4 (already fixed in requirements.txt)

### Runtime Errors
- Check that all environment variables are set correctly
- Verify your LINE Bot webhook URL is correct

### Performance Issues
- Consider upgrading to a paid plan for better performance
- Monitor your API usage to avoid rate limits

## Important Notes

- Railway's free tier has limited hours per month
- Your ChromaDB data will persist between deployments
- Railway automatically handles SSL certificates
- The app will automatically restart if it crashes

## Scaling

For production use:
1. Upgrade to a paid Railway plan
2. Consider using a managed database for ChromaDB
3. Set up monitoring and alerts
4. Implement proper logging