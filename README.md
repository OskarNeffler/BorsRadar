# YouTube Podcast Subtitle Analyzer

## Project Overview

This tool extracts and analyzes subtitles from YouTube podcasts, focusing on financial content analysis using Google's Gemini AI.

## Project Structure

```
podcast_app/
│
├── google_cloud_stuff/
├── podcast_project/
│   ├── batch_podcast_api.py
│   ├── podcast_api.py
│   ├── test_gemini.py
│   └── youtube_podcast_analyzer.py
└── venv/
```

## Prerequisites

- Python 3.8+
- Google Cloud Project with Vertex AI enabled
- YouTube Data API access

## Setup

1. Ensure you're in the `podcast_app` directory

2. Activate virtual environment:

```bash
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create or update the `.env` file in the `podcast_app` directory:

```
GOOGLE_CLOUD_PROJECT=your_google_cloud_project_id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

## Usage

### Basic Usage

```bash
# From podcast_app directory
python podcast_project/youtube_podcast_analyzer.py -i "https://youtube.com/video_url" -p "Podcast Name"
```

### Advanced Options

```bash
# Specify preferred subtitle languages
python podcast_project/youtube_podcast_analyzer.py -i "video_url" -l sv en -p "Avanzapodden"

# Specify output directory
python podcast_project/youtube_podcast_analyzer.py -i "video_url" -o ./podcast_results -p "Nordnet Sparpodden"
```

## Command Line Arguments

- `-i`, `--input`: YouTube video URL (required)
- `-p`, `--podcast-name`: Name of the podcast
- `-o`, `--output`: Output directory for results (default: podcast_data)
- `-l`, `--languages`: Preferred subtitle languages (default: sv en)
- `--max-videos`: Maximum number of videos to process (default: 10)

## Logging

- Detailed logs are saved in `youtube_podcast_analyzer.log`
- Console output provides real-time progress

## Troubleshooting

- Ensure all environment variables are set correctly
- Check internet connectivity
- Verify YouTube URL and subtitle availability
- Review log files for detailed error information

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Disclaimer

This tool is for informational purposes only. Always conduct your own financial research.
