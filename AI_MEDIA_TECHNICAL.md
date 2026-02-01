# AI-Powered Media Management - Technical Documentation

## Architecture Overview

The AI Media Management system is built with a modular architecture consisting of multiple layers:

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface Layer                  │
│  - AI Media Panel (ai_media_panel.py)                   │
│  - AI Chat Integration (ai_chat_functionality.py)       │
│  - Files Model Extensions (files_model.py)              │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                  Core Management Layer                   │
│  - AI Media Manager (ai_media_manager.py)               │
│  - Media Analyzer (media_analyzer.py)                   │
│  - Tag Manager (tag_manager.py)                         │
│  - Face Manager (face_manager.py)                       │
│  - Search Engine (search_engine.py)                     │
│  - Collection Manager (collection_manager.py)           │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                   AI Provider Layer                      │
│  - Base Provider (ai_providers/__init__.py)             │
│  - OpenAI Provider (openai_provider.py)                 │
│  - Google Vision Provider (google_vision_provider.py)   │
│  - AWS Rekognition Provider (aws_rekognition_provider.py)│
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                   Data Storage Layer                     │
│  - Project Data (project_data.py)                       │
│  - File Metadata (query.py - File class)                │
│  - People Database (ai_people_database.json)            │
│  - Settings (settings.py)                               │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. AI Media Manager (`ai_media_manager.py`)

Main orchestrator that coordinates all AI media management features.

**Key Methods:**
- `analyze_file(file_id)`: Analyze a single file
- `analyze_multiple_files(file_ids)`: Batch analysis
- `search_files(query)`: Natural language search
- `process_command(command)`: Process chat commands

**Usage:**
```python
from classes.ai_media_manager import get_ai_media_manager

manager = get_ai_media_manager()
result = await manager.analyze_file("FILE_123")
```

### 2. Media Analyzer (`media_analyzer.py`)

Handles frame extraction and coordinates with AI providers for analysis.

**Key Classes:**
- `MediaAnalyzer`: Main analyzer class
- `AnalysisQueue`: Queue manager for batch processing

**Frame Extraction:**
```python
analyzer = MediaAnalyzer()
frames = analyzer.extract_video_frames(video_path, num_frames=5)
```

**Analysis Flow:**
1. Extract keyframes from video (or use image directly)
2. Send frames to AI provider
3. Parse and normalize response
4. Store metadata in file object
5. Update tag cache and collections

### 3. AI Providers (`ai_providers/`)

Abstract provider interface with implementations for multiple AI services.

**Base Provider Interface:**
```python
class BaseAIProvider(ABC):
    @abstractmethod
    async def analyze_image(self, image_path: str) -> AnalysisResult
    
    @abstractmethod
    async def analyze_video_frames(self, frame_paths: List[str]) -> AnalysisResult
    
    @abstractmethod
    async def detect_faces(self, image_path: str) -> List[Dict]
    
    @abstractmethod
    async def parse_search_query(self, query: str) -> Dict
```

**Provider Factory:**
```python
from classes.ai_providers import ProviderFactory, ProviderType

provider = ProviderFactory.create_provider(
    ProviderType.OPENAI,
    api_key="your-api-key"
)
```

### 4. Tag Manager (`tag_manager.py`)

Manages AI-generated tags with efficient caching and filtering.

**Tag Structure:**
```python
{
    "object:person": {"FILE_001", "FILE_003", "FILE_007"},
    "scene:outdoor": {"FILE_001", "FILE_002"},
    "mood:happy": {"FILE_003", "FILE_007"}
}
```

**Key Methods:**
- `get_all_tags()`: Get all tags organized by category
- `get_files_with_tag(tag, category)`: Find files with specific tag
- `search_files(filters)`: Search with multiple criteria
- `update_file_tags(file_id, metadata)`: Update file's tags

### 5. Face Manager (`face_manager.py`)

Handles face detection, recognition, and people database.

**Data Structures:**
```python
class Person:
    person_id: str
    name: str
    face_samples: List[Dict]
    file_appearances: Dict[str, List[float]]  # file_id -> timestamps
```

**Face Clustering:**
- Detects faces in media files
- Groups similar faces together
- Allows user to name people
- Tracks appearances across files

### 6. Search Engine (`search_engine.py`)

Natural language search with relevance ranking.

**Search Flow:**
1. Parse natural language query (using GPT-4 or fallback)
2. Convert to structured filters
3. Query files with filters
4. Rank results by relevance
5. Return sorted results

**Relevance Scoring:**
- Object matches: 30% weight
- Scene matches: 25% weight
- Activity matches: 20% weight
- Mood matches: 15% weight
- Description match: 10% weight
- Boosted by AI confidence

### 7. Collection Manager (`collection_manager.py`)

Smart collections with rule-based filtering.

**Rule System:**
```python
class CollectionRule:
    field: str  # "ai_metadata.tags.objects"
    operator: RuleOperator  # CONTAINS, EQUALS, etc.
    value: Any  # "person"
```

**Collection Types:**
- **SMART**: Auto-updating based on rules
- **MANUAL**: User-curated
- **PERSON**: Based on face recognition
- **PRESET**: Built-in collections

## Data Model

### File AI Metadata Structure

```json
{
  "ai_metadata": {
    "analyzed": true,
    "analysis_version": "1.0",
    "analysis_date": "2026-01-31T12:00:00Z",
    "provider": "openai-gpt4-vision",
    "tags": {
      "objects": ["person", "car", "building"],
      "scenes": ["outdoor", "city"],
      "activities": ["walking", "talking"],
      "mood": ["casual", "friendly"],
      "quality": {
        "resolution_score": 0.95,
        "lighting_score": 0.85,
        "stability_score": 0.90
      }
    },
    "faces": [
      {
        "face_id": "FACE_001",
        "person_name": "John Doe",
        "confidence": 0.98,
        "bounding_box": {"x": 100, "y": 50, "w": 150, "h": 180},
        "timestamps": [1.5, 5.2, 12.8]
      }
    ],
    "colors": {
      "dominant": ["#FF5733", "#33FF57"],
      "palette": "warm",
      "saturation": "high"
    },
    "description": "Outdoor city scene with people walking and talking",
    "confidence": 0.87
  }
}
```

### Collection Structure

```json
{
  "collection_id": "COLL_001",
  "name": "Outdoor Shots",
  "type": "smart",
  "auto_update": true,
  "match_all": true,
  "rules": [
    {
      "field": "ai_metadata.tags.scenes",
      "operator": "contains",
      "value": "outdoor"
    }
  ],
  "file_ids": ["FILE_001", "FILE_003"],
  "icon": "landscape",
  "color": "#4CAF50"
}
```

### People Database Structure

```json
{
  "people": [
    {
      "person_id": "PERSON_001",
      "name": "John Doe",
      "face_samples": [
        {
          "face_data": {...},
          "file_id": "FILE_001",
          "timestamp": 5.2,
          "added_at": "2026-01-31T12:00:00Z"
        }
      ],
      "file_appearances": {
        "FILE_001": [1.5, 5.2, 12.8],
        "FILE_003": [0.0]
      },
      "thumbnail_path": "path/to/thumbnail.jpg"
    }
  ],
  "face_clusters": {...},
  "version": "1.0"
}
```

## API Integration

### Async Operations

Most AI operations are async to prevent UI blocking:

```python
import asyncio

async def analyze_files():
    manager = get_ai_media_manager()
    result = await manager.analyze_file("FILE_123")
    return result

# Run in event loop
loop = asyncio.new_event_loop()
result = loop.run_until_complete(analyze_files())
loop.close()
```

### Provider Configuration

Providers are configured via settings:

```python
s = get_app().get_settings()

# OpenAI
api_key = s.get('openai-api-key')
provider = ProviderFactory.create_provider(
    ProviderType.OPENAI,
    api_key=api_key
)

# Google Cloud
credentials_path = s.get('google-credentials-path')
provider = ProviderFactory.create_provider(
    ProviderType.GOOGLE,
    credentials_path=credentials_path
)

# AWS
provider = ProviderFactory.create_provider(
    ProviderType.AWS,
    access_key_id=s.get('aws-access-key-id'),
    secret_access_key=s.get('aws-secret-access-key')
)
```

## Performance Optimization

### Caching

1. **Tag Cache**: In-memory cache of tag-to-files mappings
2. **API Response Cache**: Responses cached to avoid redundant API calls
3. **Face Embeddings**: Stored locally for fast comparison

### Batch Processing

Analysis queue processes multiple files efficiently:

```python
queue = get_analysis_queue()

# Add multiple files
for file_id in file_ids:
    queue.add_to_queue(file_id, file_path, media_type)

# Process all at once
await queue.process_queue()
```

### Background Processing

Analysis runs in background threads to avoid blocking UI:

```python
import threading

def analyze_in_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(queue.process_queue())
    loop.close()

thread = threading.Thread(target=analyze_in_background, daemon=True)
thread.start()
```

## Error Handling

### Graceful Degradation

System continues to work even if AI providers are unavailable:

```python
if not analyzer.is_available():
    log.warning("AI analyzer not available")
    return empty_metadata()
```

### Retry Logic

API calls include retry logic with exponential backoff:

```python
for attempt in range(max_retries):
    try:
        response = await provider.analyze_image(image_path)
        break
    except Exception as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
        else:
            raise
```

### Error Reporting

Comprehensive logging at all levels:

```python
log.debug("Starting analysis...")
log.info("Analysis complete")
log.warning("API rate limit approaching")
log.error("Analysis failed", exc_info=True)
```

## Testing

### Unit Tests

Test individual components:

```python
def test_tag_manager():
    manager = TagManager()
    manager.update_file_tags("FILE_001", metadata)
    tags = manager.get_all_tags()
    assert "outdoor" in tags['scenes']
```

### Integration Tests

Test full workflows:

```python
async def test_analysis_workflow():
    manager = get_ai_media_manager()
    result = await manager.analyze_file("test_file.mp4")
    assert result['success']
    
    # Verify tags were created
    tags = manager.get_file_tags("test_file.mp4")
    assert len(tags['objects']) > 0
```

### Mock Providers

For testing without API calls:

```python
class MockProvider(BaseAIProvider):
    async def analyze_image(self, image_path):
        result = AnalysisResult()
        result.objects = ["person", "car"]
        result.scenes = ["outdoor"]
        return result
```

## Deployment

### Dependencies

Required packages:

```bash
pip install openai  # For OpenAI provider
pip install google-cloud-vision  # For Google provider
pip install boto3  # For AWS provider
```

### Configuration

Settings stored in `~/.openshot_qt/openshot.settings`:

```json
[
  {
    "setting": "ai-enabled",
    "value": true
  },
  {
    "setting": "openai-api-key",
    "value": "sk-..."
  }
]
```

### Database Files

- People database: `~/.openshot_qt/ai_people_database.json`
- Temp frames: `~/.openshot_qt/ai_analysis_temp/`
- Cache: `~/.openshot_qt/cache/`

## Security Considerations

### API Key Storage

- Keys stored encrypted in settings
- Never logged or exposed in UI
- Separate keys per provider

### Data Privacy

- Media sent to cloud providers for analysis
- Face data stored locally only
- Option to exclude files from analysis
- Clear user consent required

### Rate Limiting

- Implement request throttling
- Monitor API usage
- Provide cost estimates
- Allow user-configurable limits

## Future Enhancements

### Planned Features

1. **Local AI Models**: Support for local inference (no cloud required)
2. **Video Transcription**: Automatic subtitle generation
3. **Audio Analysis**: Music detection, speech-to-text
4. **Advanced Face Recognition**: Emotion tracking, age estimation
5. **Collaborative Tagging**: Share analysis across team
6. **Custom Models**: Train on your own media library
7. **Real-time Analysis**: Analyze during recording

### API Roadmap

- REST API for external integrations
- Webhook support for automation
- Batch export/import of analysis data
- Plugin system for custom providers

## Contributing

See `CONTRIBUTING.md` for guidelines on:

- Adding new AI providers
- Extending analysis capabilities
- Improving search algorithms
- Optimizing performance

## License

GNU General Public License v3.0

---

**Version 1.0** | Last Updated: January 2026
