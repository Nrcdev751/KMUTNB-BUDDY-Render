# Render Deployment Guide for KMUTNB Buddy LINE Bot

## Prerequisites
- Render account (sign up at [render.com](https://render.com))
- GitHub repository with your code
- LINE Bot channel with access token and secret
- Google Gemini API key

## Step 1: Prepare Your Code

Your project is already configured with:
- `requirements.txt` with compatible dependencies (pandas==2.1.4 for Python 3.11 compatibility)
- `render.yaml` for Render deployment configuration
- `.env.example` showing required environment variables

## Step 2: Push to GitHub

1. Make sure all your changes are committed to Git:
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

## Step 3: Deploy to Render

1. Log in to [Render](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure your service:
   - Name: kmutnb-buddy (or your preferred name)
   - Environment: Python 3
   - Region: Choose the nearest region
   - Branch: main
   - Root Directory: Leave empty if your app is in the root
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn line_his2:app`
   - Instance Type: Free (to start)

5. Click "Create Web Service"

## Step 4: Configure Environment Variables

In your Render service dashboard, add these environment variables:

1. Go to your service → "Environment" tab
2. Add these environment variables:
   ```
   LINE_CHANNEL_ACCESS_TOKEN=your_actual_line_channel_access_token
   LINE_CHANNEL_SECRET=your_actual_line_channel_secret
   GEMINI_API_KEY=your_actual_gemini_api_key
   ```
3. Click "Save Changes"

## Step 5: Update LINE Bot Webhook

1. Once deployed, get your Render URL from the service dashboard
2. Go to your LINE Bot console
3. Update the webhook URL to: `https://your-app-name.onrender.com/callback`

## Step 6: Verify Deployment

1. Check the "Logs" tab in your Render dashboard
2. Test the `/hello` endpoint: `https://your-app-name.onrender.com/hello`
3. Test your LINE Bot by sending a message

## Important Notes About Render

### Free Tier Limitations
- Free tier instances spin down after 15 minutes of inactivity
- Cold starts can take 30-60 seconds
- Limited to 750 hours/month (about 24 hours/day)

### Persistence
- Your ChromaDB data will persist between deployments
- Render provides persistent disk storage

### SSL
- Render automatically provides SSL certificates
- Your app will be accessible via HTTPS

## Troubleshooting

### Build Errors
- If you encounter pandas build errors, ensure you're using pandas==2.1.4 (already fixed in requirements.txt)
- Check that Python version is set to 3.11.5 in render.yaml

### Runtime Errors
- Check that all environment variables are set correctly
- Verify your LINE Bot webhook URL is correct
- Check the logs in Render dashboard

### Performance Issues
- Consider upgrading to a paid plan for better performance
- Monitor your API usage to avoid rate limits
- The free tier has a 512MB RAM limit

## Scaling for Production

For production use:
1. Upgrade to a paid Render plan:
   - Starter: $7/month (no spin-down)
   - Standard: $25/month (more resources)
2. Consider using a managed database for ChromaDB
3. Set up monitoring and alerts
4. Implement proper logging

## Alternative: Using render.yaml

Your project includes a `render.yaml` file that automates configuration:
- When connected to GitHub, Render will automatically detect this file
- It sets Python version to 3.11.5
- Configures build and start commands
- Enables auto-deployment on push to main branch

## Monitoring Your App

1. Check the "Metrics" tab for performance data
2. Monitor the "Logs" tab for errors
3. Set up alerts in Render dashboard
4. Monitor your LINE Bot usage in LINE Developers Console

## Next Steps

After successful deployment:
1. Test all LINE Bot features
2. Monitor for any errors
3. Consider adding health checks
4. Set up backup for your ChromaDB data
5. Plan for scaling if needed