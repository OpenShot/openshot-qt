"""
NVIDIA Edge Vision provider: Phi-3.5-vision on GX10 for media analysis.
Uses the OpenAI-compatible /v1/chat/completions endpoint on the edge device.
"""

import asyncio
import base64
import json
from typing import Dict, List, Any, Optional

from classes.logger import log
from classes.ai_providers import BaseAIProvider, AnalysisResult, ProviderType, ProviderFactory


class NvidiaEdgeVisionProvider(BaseAIProvider):
    """NVIDIA Edge (Phi-3.5-vision) provider for media analysis via GX10."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.base_url = kwargs.get('base_url', 'http://10.19.183.5:8000/v1')
        self.model = kwargs.get('model', 'llava')
        self.max_tokens = kwargs.get('max_tokens', 1000)
        self.temperature = kwargs.get('temperature', 0.7)
        super().__init__(api_key=api_key or "not-needed", **kwargs)

    def _validate_configuration(self) -> bool:
        """Validate edge device configuration (just needs a URL)."""
        if not self.base_url:
            log.warning("NVIDIA Edge API URL not configured")
            self.is_configured = False
            return False
        self.is_configured = True
        return True

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    async def _call_api(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call the edge device's OpenAI-compatible chat/completions endpoint."""
        if not self.is_configured:
            raise ValueError("NVIDIA Edge provider not configured")

        import requests

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        try:
            resp = await asyncio.to_thread(
                requests.post, url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error("NVIDIA Edge API call failed: %s", e)
            raise

    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        """Analyze a single image using Phi-3.5-vision on the edge device."""
        log.debug("Analyzing image with NVIDIA Edge: %s", image_path)
        try:
            base64_image = self._encode_image(image_path)
            prompt = self._create_analysis_prompt()
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
            result = self._parse_response(response)
            result.provider = "nvidia-edge-vision"
            return result
        except Exception as e:
            log.error("Failed to analyze image with NVIDIA Edge: %s", e)
            result = AnalysisResult()
            result.provider = "nvidia-edge-vision"
            return result

    async def analyze_video_frames(self, frame_paths: List[str], **kwargs) -> AnalysisResult:
        """Analyze multiple video frames using Phi-3.5-vision."""
        log.debug("Analyzing %d frames with NVIDIA Edge", len(frame_paths))
        try:
            content: List[Dict[str, Any]] = [
                {"type": "text", "text": self._create_video_analysis_prompt()}
            ]
            for frame_path in frame_paths[:5]:
                try:
                    b64 = self._encode_image(frame_path)
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                    })
                except Exception as e:
                    log.warning("Failed to encode frame %s: %s", frame_path, e)

            if len(content) < 2:
                raise ValueError("No frames could be encoded")

            messages = [{"role": "user", "content": content}]
            response = await self._call_api(messages)
            result = self._parse_response(response)
            result.provider = "nvidia-edge-vision"
            return result
        except Exception as e:
            log.error("Failed to analyze video frames with NVIDIA Edge: %s", e)
            result = AnalysisResult()
            result.provider = "nvidia-edge-vision"
            return result

    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect faces in an image."""
        log.debug("Detecting faces with NVIDIA Edge: %s", image_path)
        try:
            base64_image = self._encode_image(image_path)
            prompt = (
                "Analyze this image and detect all human faces. For each face, provide:\n"
                "1. Estimated position (left, center, right, top, bottom)\n"
                "2. Approximate age range\n"
                "3. Gender (if determinable)\n"
                "4. Expression/emotion\n\n"
                "Return as JSON array of face objects."
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
            response = await self._call_api(messages)
            content = response['choices'][0]['message']['content']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            faces = json.loads(content)
            return faces if isinstance(faces, list) else []
        except Exception as e:
            log.error("Failed to detect faces with NVIDIA Edge: %s", e)
            return []

    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language search query into structured filters."""
        log.debug("Parsing search query with NVIDIA Edge: %s", query)
        try:
            prompt = (
                f'Parse this natural language search query into structured filters '
                f'for a media library:\n\nQuery: "{query}"\n\n'
                'Return JSON with: objects, scenes, activities, mood, people (bool), '
                'quality (high/medium/low), time (morning/afternoon/evening/night).\n'
                'Return ONLY valid JSON.'
            )
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_api(messages)
            content = response['choices'][0]['message']['content']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            return json.loads(content)
        except Exception as e:
            log.error("Failed to parse search query with NVIDIA Edge: %s", e)
            return {}

    # ── Shared prompt helpers ───────────────────────────────────────

    def _create_analysis_prompt(self) -> str:
        return (
            "Analyze this image/video frame in detail and provide a structured response in JSON format.\n\n"
            "Identify and return:\n"
            "1. Objects: List all significant objects visible\n"
            "2. Scenes: Classify the scene type (indoor/outdoor, etc.)\n"
            "3. Activities: Describe what activities are happening\n"
            "4. Mood: Describe the mood or tone\n"
            "5. Colors: Identify dominant colors and palette\n"
            "6. Quality: Assess technical quality\n"
            "7. Description: Provide a concise description\n\n"
            'Return ONLY valid JSON in this format:\n'
            '{"objects": [], "scenes": [], "activities": [], "mood": [], '
            '"colors": {"dominant": [], "palette": "warm", "saturation": "medium"}, '
            '"quality": {"resolution_score": 0.85, "lighting_score": 0.90, "composition_score": 0.88}, '
            '"description": ""}'
        )

    def _create_video_analysis_prompt(self) -> str:
        return (
            "Analyze these video frames and provide a comprehensive analysis in JSON format.\n"
            "These frames represent different moments from a video. Analyze the overall content:\n"
            "1. Objects  2. Scenes  3. Activities  4. Mood  5. Colors  6. Quality  7. Description\n\n"
            "Return ONLY valid JSON in the same format as a single image analysis."
        )

    def _parse_response(self, response: Dict[str, Any]) -> AnalysisResult:
        result = AnalysisResult()
        try:
            content = response['choices'][0]['message']['content']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            data = json.loads(content)
            result.objects = data.get('objects', [])
            result.scenes = data.get('scenes', [])
            result.activities = data.get('activities', [])
            result.mood = data.get('mood', [])
            result.colors = data.get('colors', {})
            result.quality_scores = data.get('quality', {})
            result.description = data.get('description', '')
            result.confidence = 0.80
        except json.JSONDecodeError:
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            result.description = content
            result.confidence = 0.4
        except Exception as e:
            log.error("Failed to parse NVIDIA Edge response: %s", e)
            result.confidence = 0.0
        result.raw_response = response
        return result


# Register the provider
ProviderFactory.register_provider(ProviderType.NVIDIA_EDGE, NvidiaEdgeVisionProvider)
