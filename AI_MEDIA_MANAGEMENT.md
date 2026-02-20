# AI-Powered Media Management - User Guide

## Overview

Flowcut includes powerful AI-powered media management features that automatically analyze, tag, organize, and search your media files using advanced AI technologies.

## Features

### 1. Automatic Media Analysis

When you import media files, Flowcut can automatically analyze them using AI to extract:

- **Objects**: People, cars, buildings, animals, nature elements, and more
- **Scenes**: Indoor/outdoor, city, nature, studio classifications
- **Activities**: Walking, talking, running, and other actions
- **Mood**: Happy, serious, energetic, calm, dramatic tones
- **Colors**: Dominant colors and color palettes
- **Quality**: Resolution, lighting, and composition scores
- **Faces**: Automatic face detection and recognition

### 2. Natural Language Search

Search your media library using conversational queries:

- "Find clips with people talking outdoors"
- "Show me all sunset scenes"
- "Videos with cars and buildings"
- "Clips with happy people celebrating"
- "Indoor interviews with good lighting"

The AI understands your intent and finds relevant clips based on their analyzed content.

### 3. Face Recognition & People Management

- Automatically detect faces in all videos and images
- Group similar faces together
- Name people and track their appearances
- Search for specific people across your entire library
- See timeline visualizations of when people appear

### 4. Smart Collections

Automatically organize media into intelligent collections:

- **By Content**: Interviews, B-Roll, Drone Footage, Product Shots
- **By Quality**: High Quality, Needs Color Correction, Low Light
- **By Scene**: Indoor, Outdoor, Studio, Nature, Urban
- **By People**: Collections for each recognized person
- **Custom Rules**: Create your own smart folders with custom criteria

## Getting Started

### 1. Configure AI Providers

1. Open **Edit > Preferences**
2. Go to the **AI Features** tab
3. Enable AI Features
4. Choose your AI provider (OpenAI, Google Cloud Vision, or AWS Rekognition)
5. Enter your API credentials:
   - **OpenAI**: API Key
   - **Google Cloud**: Credentials file path
   - **AWS**: Access Key ID and Secret Access Key

### 2. Import and Analyze Media

1. Import media files as usual (**File > Import Files**)
2. If "Auto-Analyze on Import" is enabled, files will be queued for analysis automatically
3. Or manually analyze files:
   - Select files in the Project Files panel
   - Right-click and choose "Analyze with AI"

### 3. View AI Media Panel

1. Open **View > Docks > AI Media Manager**
2. The panel shows three tabs:
   - **Tags**: Browse all detected tags
   - **Analysis**: Monitor analysis queue and progress
   - **Collections**: View and manage smart collections

### 4. Search Your Media

Use the AI Assistant to search:

1. Open **View > Docks > AI Assistant**
2. Type natural language queries like:
   - "search for outdoor scenes with people"
   - "find videos with cars"
   - "show me happy moments"

Or use the enhanced search bar in the Files panel (coming soon).

## AI Provider Setup

### OpenAI GPT-4 Vision

**Best for**: Comprehensive scene understanding and natural language processing

1. Sign up at https://platform.openai.com
2. Create an API key
3. Enter the key in Preferences > AI Features > OpenAI API Key

**Cost**: Pay-per-use based on images analyzed

### Google Cloud Vision

**Best for**: Detailed object and label detection

1. Create a Google Cloud project at https://console.cloud.google.com
2. Enable the Cloud Vision API
3. Create a service account and download credentials JSON
4. Enter the file path in Preferences > AI Features

**Cost**: Free tier available, then pay-per-use

### AWS Rekognition

**Best for**: Face detection and recognition

1. Sign up for AWS at https://aws.amazon.com
2. Create IAM user with Rekognition permissions
3. Generate access keys
4. Enter credentials in Preferences > AI Features

**Cost**: Free tier available, then pay-per-use

## Using Smart Collections

### Create a Smart Collection

1. Open AI Media Panel > Collections tab
2. Click "New Collection"
3. Name your collection
4. Add rules:
   - Field: Choose what to filter (objects, scenes, quality, etc.)
   - Operator: equals, contains, greater than, etc.
   - Value: The value to match
5. Choose AND/OR logic for multiple rules
6. Enable "Auto-Update" to keep collection current

### Preset Collections

Flowcut includes preset collections:

- **High Quality**: Files with resolution score > 0.8
- **Outdoor Shots**: Files tagged as outdoor scenes
- **With People**: Files containing detected people

## Managing People

### Recognize and Name People

1. After analysis, faces are automatically detected
2. Open AI Media Panel to see detected faces
3. Click on a face cluster to name the person
4. The system will track that person across all files

### Merge Duplicate People

If the same person appears in multiple clusters:

1. Select both clusters
2. Click "Merge"
3. Choose which name to keep

### Search by Person

- Use AI Assistant: "show me all clips with John"
- Or browse the People collection in AI Media Panel

## Tips & Best Practices

### Optimize Analysis Speed

- Adjust "Number of Frames to Analyze" in Preferences (fewer = faster, less accurate)
- Analyze in batches during off-hours
- Use "High Quality" filter to analyze only important files

### Improve Search Accuracy

- Use specific terms: "outdoor interview" vs just "interview"
- Combine multiple criteria: "outdoor scene with people talking"
- Check AI-generated tags to learn what terms work best

### Manage API Costs

- Enable auto-analysis only for important projects
- Use local caching (responses are cached automatically)
- Analyze keyframes only for long videos
- Review cost estimates before bulk analysis

### Privacy & Security

- API keys are stored encrypted
- Media is sent to cloud providers for analysis (read their privacy policies)
- Option to exclude sensitive files from analysis
- Face data is stored locally, not in the cloud

## Troubleshooting

### Analysis Not Working

1. Check API credentials in Preferences
2. Verify internet connection
3. Check API quota/limits with your provider
4. Review logs: `~/.openshot_qt/openshot-qt.log`

### Search Returns No Results

1. Ensure files have been analyzed (check AI Media Panel)
2. Try broader search terms
3. Check that AI features are enabled
4. Refresh tag cache: AI Media Panel > Tags > Refresh

### Poor Recognition Quality

1. Use higher quality source media
2. Increase "Number of Frames to Analyze"
3. Try a different AI provider
4. Ensure good lighting in source footage

## Keyboard Shortcuts

- **Ctrl+Shift+A**: Open AI Media Panel
- **Ctrl+Shift+F**: Focus search bar
- **Ctrl+Shift+T**: Show tags panel

## Advanced Features

### Command-Line Analysis

Use AI Assistant for batch operations:

- "analyze all files"
- "analyze selected files"
- "show statistics"
- "create collection Nature"

### Export Analysis Data

Analysis results are saved in project files (.osp) and can be:

- Exported to JSON
- Shared across team members
- Backed up separately

### API Integration

Developers can access AI features programmatically:

```python
from classes.ai_media_manager import get_ai_media_manager

manager = get_ai_media_manager()
results = await manager.search_files("outdoor scenes")
```

## Support

- Documentation: https://flowcut.app/docs/
- Forums: https://flowcut.app/community/
- GitHub Issues: https://github.com/OpenShot/openshot-qt/issues

## Credits

AI-Powered Media Management developed by the Flowcut team, built on Flowcut (OpenShot Video Editor fork).

Powered by:
- OpenAI GPT-4 Vision
- Google Cloud Vision API
- AWS Rekognition
- OpenShot libopenshot

---

**Version 1.0** | Last Updated: January 2026
