name: Main Workflow

on:
  push:
    branches:
      - main

jobs:
  generate-video:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        python -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install google-generativeai moviepy python-dotenv requests

    - name: Generate Video
      env:
        GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        YOUTUBE_CHANNEL_ID: ${{ secrets.YOUTUBE_CHANNEL_ID }}
        PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}
      run: |
        source venv/bin/activate
        python scripts/main.py \
          --gemini-api "$GEMINI_API_KEY" \
          --youtube-channel "$YOUTUBE_CHANNEL_ID" \
          --pixabay-api "$PIXABAY_API_KEY" \
          --quantidade 5
