"""
OpenAI provider: LangChain ChatOpenAI for chat, and GPT-4 Vision for media analysis.
"""

from classes.logger import log


def is_available(model_id, settings):
    """Return True if OpenAI is configured (API key set) and model_id is for this provider."""
    if not model_id.startswith("openai/"):
        return False
    key = (settings.get("openai-api-key") or "").strip()
    return bool(key)


def build_chat_model(model_id, settings):
    """Build ChatOpenAI for the given model_id. Requires openai-api-key in settings."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        log.warning("langchain-openai not installed")
        return None

    api_key = (settings.get("openai-api-key") or "").strip()
    if not api_key:
        return None

    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0.2,
    )


# --- OpenAI GPT-4 Vision for media analysis (from nilay branch) ---
import asyncio
import base64
import json
from typing import Dict, List, Any, Optional

from classes.ai_providers import BaseAIProvider, AnalysisResult, ProviderType, ProviderFactory


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT-4 Vision provider for comprehensive media analysis"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize OpenAI provider
        
        Args:
            api_key: OpenAI API key
            **kwargs: Additional configuration (model, max_tokens, etc.)
        """
        self.model = kwargs.get('model', 'gpt-4-vision-preview')
        self.max_tokens = kwargs.get('max_tokens', 1000)
        self.temperature = kwargs.get('temperature', 0.7)
        super().__init__(api_key, **kwargs)
    
    def _validate_configuration(self) -> bool:
        """Validate OpenAI configuration"""
        if not self.api_key or len(self.api_key) < 10:
            log.warning("OpenAI API key not configured")
            self.is_configured = False
            return False
        
        self.is_configured = True
        return True
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode image to base64
        
        Args:
            image_path: Path to image file
        
        Returns:
            Base64 encoded image string
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            log.error(f"Failed to encode image {image_path}: {e}")
            raise
    
    async def _call_api(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Call OpenAI API
        
        Args:
            messages: List of message objects for the API
        
        Returns:
            API response dictionary
        """
        if not self.is_configured:
            raise ValueError("OpenAI provider not configured")
        
        try:
            # Import here to avoid dependency issues if not installed
            import openai
            
            # Configure OpenAI client
            openai.api_key = self.api_key
            
            # Make async call to OpenAI API
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response
        except ImportError:
            log.error("OpenAI package not installed. Install with: pip install openai")
            raise
        except Exception as e:
            log.error(f"OpenAI API call failed: {e}")
            raise
    
    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        """
        Analyze a single image using GPT-4 Vision
        
        Args:
            image_path: Path to the image file
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with analysis data
        """
        log.debug(f"Analyzing image with OpenAI: {image_path}")
        
        try:
            # Encode image
            base64_image = self._encode_image(image_path)
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(**kwargs)
            
            # Prepare messages for API
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Call API
            response = await self._call_api(messages)
            
            # Parse response
            result = self._parse_analysis_response(response)
            result.provider = "openai-gpt4-vision"
            
            log.debug(f"OpenAI analysis complete for {image_path}")
            return result
            
        except Exception as e:
            log.error(f"Failed to analyze image with OpenAI: {e}")
            # Return empty result on error
            result = AnalysisResult()
            result.provider = "openai-gpt4-vision"
            return result
    
    async def analyze_video_frames(self, frame_paths: List[str], **kwargs) -> AnalysisResult:
        """
        Analyze multiple video frames
        
        Args:
            frame_paths: List of paths to frame images
            **kwargs: Additional analysis parameters
        
        Returns:
            AnalysisResult object with aggregated analysis
        """
        log.debug(f"Analyzing {len(frame_paths)} frames with OpenAI")
        
        try:
            # Encode all frames
            base64_frames = []
            for frame_path in frame_paths[:5]:  # Limit to first 5 frames for cost
                try:
                    base64_frames.append(self._encode_image(frame_path))
                except Exception as e:
                    log.warning(f"Failed to encode frame {frame_path}: {e}")
            
            if not base64_frames:
                raise ValueError("No frames could be encoded")
            
            # Create video analysis prompt
            prompt = self._create_video_analysis_prompt(**kwargs)
            
            # Prepare messages with multiple frames
            content = [{"type": "text", "text": prompt}]
            for base64_frame in base64_frames:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_frame}"
                    }
                })
            
            messages = [{"role": "user", "content": content}]
            
            # Call API
            response = await self._call_api(messages)
            
            # Parse response
            result = self._parse_analysis_response(response)
            result.provider = "openai-gpt4-vision"
            
            log.debug(f"OpenAI video analysis complete")
            return result
            
        except Exception as e:
            log.error(f"Failed to analyze video frames with OpenAI: {e}")
            result = AnalysisResult()
            result.provider = "openai-gpt4-vision"
            return result
    
    def _create_analysis_prompt(self, **kwargs) -> str:
        """Create detailed analysis prompt for GPT-4 Vision"""
        return """Analyze this image/video frame in detail and provide a structured response in JSON format.

Identify and return:
1. Objects: List all significant objects visible (people, vehicles, animals, buildings, nature elements, etc.)
2. Scenes: Classify the scene type (indoor/outdoor, studio, nature, city, etc.)
3. Activities: Describe what activities or actions are happening
4. Mood: Describe the mood or tone (happy, serious, energetic, calm, dramatic, etc.)
5. Colors: Identify dominant colors and overall color palette (warm/cool, saturation level)
6. Quality: Assess technical quality (resolution appearance, lighting quality, composition, stability)
7. Description: Provide a concise natural language description of the content

Return ONLY valid JSON in this exact format:
{
  "objects": ["person", "car", "building"],
  "scenes": ["outdoor", "city", "daytime"],
  "activities": ["walking", "talking"],
  "mood": ["casual", "friendly"],
  "colors": {
    "dominant": ["#FF5733", "#33FF57"],
    "palette": "warm",
    "saturation": "medium"
  },
  "quality": {
    "resolution_score": 0.85,
    "lighting_score": 0.90,
    "composition_score": 0.88
  },
  "description": "Brief description of the scene"
}"""
    
    def _create_video_analysis_prompt(self, **kwargs) -> str:
        """Create video analysis prompt for multiple frames"""
        return """Analyze these video frames and provide a comprehensive analysis in JSON format.

These frames represent different moments from a video. Analyze the overall content:
1. Objects: All significant objects across frames
2. Scenes: Overall scene classification
3. Activities: Main activities happening in the video
4. Mood: Overall mood/tone of the video
5. Colors: Dominant color scheme across frames
6. Quality: Technical quality assessment
7. Description: Comprehensive description of the video content

Return ONLY valid JSON in the same format as before."""
    
    def _parse_analysis_response(self, response: Dict[str, Any]) -> AnalysisResult:
        """
        Parse OpenAI API response into AnalysisResult
        
        Args:
            response: Raw API response
        
        Returns:
            AnalysisResult object
        """
        result = AnalysisResult()
        
        try:
            # Extract content from response
            content = response['choices'][0]['message']['content']
            
            # Try to parse as JSON
            try:
                # Remove markdown code blocks if present
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()
                
                data = json.loads(content)
                
                # Populate result
                result.objects = data.get('objects', [])
                result.scenes = data.get('scenes', [])
                result.activities = data.get('activities', [])
                result.mood = data.get('mood', [])
                result.colors = data.get('colors', {})
                result.quality_scores = data.get('quality', {})
                result.description = data.get('description', '')
                result.confidence = 0.85  # GPT-4 Vision generally high confidence
                
            except json.JSONDecodeError:
                # If not JSON, use as description
                result.description = content
                result.confidence = 0.5
            
            result.raw_response = response
            
        except Exception as e:
            log.error(f"Failed to parse OpenAI response: {e}")
            result.confidence = 0.0
        
        return result
    
    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Detect faces in an image
        Note: GPT-4 Vision doesn't provide bounding boxes, this is basic detection
        
        Args:
            image_path: Path to the image file
        
        Returns:
            List of face detection results
        """
        log.debug(f"Detecting faces with OpenAI: {image_path}")
        
        try:
            base64_image = self._encode_image(image_path)
            
            prompt = """Analyze this image and detect all human faces. For each face, provide:
1. Estimated position (left, center, right, top, bottom)
2. Approximate age range
3. Gender (if determinable)
4. Expression/emotion

Return as JSON array of face objects."""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            response = await self._call_api(messages)
            content = response['choices'][0]['message']['content']
            
            # Parse JSON response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            faces = json.loads(content)
            return faces if isinstance(faces, list) else []
            
        except Exception as e:
            log.error(f"Failed to detect faces with OpenAI: {e}")
            return []
    
    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language search query into structured filters
        
        Args:
            query: Natural language query string
        
        Returns:
            Structured search parameters
        """
        log.debug(f"Parsing search query with OpenAI: {query}")
        
        try:
            prompt = f"""Parse this natural language search query into structured filters for a media library:

Query: "{query}"

Return JSON with these fields:
- objects: List of objects to search for
- scenes: List of scene types
- activities: List of activities
- mood: List of mood/tone keywords
- people: Boolean if searching for people
- quality: Quality requirements (high/medium/low)
- time: Time of day (morning/afternoon/evening/night)

Example:
{{
  "objects": ["person", "car"],
  "scenes": ["outdoor"],
  "activities": ["talking"],
  "mood": [],
  "people": true,
  "quality": "any",
  "time": "any"
}}

Return ONLY valid JSON:"""
            
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_api(messages)
            content = response['choices'][0]['message']['content']
            
            # Parse JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            filters = json.loads(content)
            return filters
            
        except Exception as e:
            log.error(f"Failed to parse search query with OpenAI: {e}")
            return {}


# Register the provider
ProviderFactory.register_provider(ProviderType.OPENAI, OpenAIProvider)
