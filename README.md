# KMUTNB Buddy - LINE Bot

A LINE bot that provides information about King Mongkut's University of Technology North Bangkok (KMUTNB).

## Features

- Answer questions about KMUTNB using RAG (Retrieval-Augmented Generation)
- Provide contact information for faculty and staff
- Display dress code information with images
- Show campus maps
- Powered by Google Gemini AI

## Deployment on Render

### Prerequisites

1. A Render account (free tier is sufficient)
2. A GitHub repository with this code
3. LINE Developer account with channel access token and secret
4. Google Gemini API key

### Environment Variables

Set these environment variables in your Render dashboard:

```
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret
GEMINI_API_KEY=your_gemini_api_key
```

### Deployment Steps

1. Push your code to a GitHub repository
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Render will automatically detect the Python environment
5. Set the environment variables in the Render dashboard
6. Deploy!

### Manual Deployment

If you prefer to configure manually:

1. Create a new Web Service
2. Set the following:
   - Name: kmutnb-buddy (or your preferred name)
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn line_his2:app`
   - Instance Type: Free (or paid for better performance)

### Webhook Configuration

After deployment:

1. Get your Render service URL (e.g., `https://kmutnb-buddy.onrender.com`)
2. Set your LINE webhook URL to: `https://your-service-url.onrender.com/callback`
3. Verify the webhook in your LINE Developer Console

## Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your API keys
4. Run the app: `python line_his2.py`

## Project Structure

```
.
├── line_his2.py          # Main Flask application
├── rag_handler.py        # RAG implementation for document Q&A
├── contact_data.py       # Contact information database
├── requirements.txt      # Python dependencies
├── Procfile             # Heroku/Render process definition
├── render.yaml          # Render deployment configuration
├── .env                 # Environment variables (local only)
├── .gitignore           # Git ignore file
├── chroma_db/           # Vector database (auto-generated)
└── kmutnbBuddy.md       # Knowledge base for RAG
```

## Troubleshooting

### Common Issues

1. **Application fails to start**: Check that all environment variables are set correctly
2. **Webhook errors**: Ensure your webhook URL is correct and uses HTTPS
3. **Memory issues on free tier**: The ChromaDB might use significant memory, consider upgrading to a paid tier if needed

### Logs

Check your Render service logs for debugging information.

## License

This project is for educational purposes.