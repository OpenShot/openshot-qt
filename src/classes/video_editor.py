"""
Video Segment Editor with Runware Integration
Ports logic from 'halftime' repo to use Runware (Kling) for video-to-video editing.
"""
import os
import sys
import time
import requests
from classes.logger import log
from classes.video_generation.runware_client import runware_generate_video, download_video_to_path

def upload_to_temp_hosting(file_path: str) -> str:
    """
    Upload a file to temporary hosting to get a public URL for Runware.
    Ports logic from halftime/backend/videos/wavespeed_client.py
    """
    log.info(f"Uploading {file_path} to temporary hosting...")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    errors = []
    
    # Option 1: tmpfiles.org
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://tmpfiles.org/api/v1/upload',
                files={'file': f},
                timeout=120
            )
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                # Convert view URL to direct download URL
                url = result['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                log.info(f"Uploaded to tmpfiles.org: {url}")
                return url
        errors.append(f"tmpfiles.org: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        errors.append(f"tmpfiles.org: {str(e)}")

    # Option 2: litterbox (catbox)
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://litterbox.catbox.moe/resources/internals/api.php',
                data={'reqtype': 'fileupload', 'time': '1h'},
                files={'fileToUpload': f},
                timeout=120
            )
        if response.status_code == 200 and response.text.startswith('http'):
            url = response.text.strip()
            log.info(f"Uploaded to litterbox: {url}")
            return url
        errors.append(f"litterbox: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        errors.append(f"litterbox: {str(e)}")

    raise RuntimeError(f"All upload services failed: {'; '.join(errors)}")

def edit_segment(
    input_video_path: str,
    output_video_path: str,
    prompt: str,
    api_key: str,
    duration_seconds: float = 5.0
) -> str:
    """
    Edit a video segment using Runware (Kling) video-to-video.
    1. Upload input video
    2. Call Runware API
    3. Download result
    """
    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"Input video not found: {input_video_path}")

    # 1. Upload
    public_url = upload_to_temp_hosting(input_video_path)
    
    # 2. Generate
    log.info(f"Generating video with Runware (Kling)... Prompt: {prompt}")
    video_url, error = runware_generate_video(
        api_key=api_key,
        prompt=prompt,
        duration_seconds=duration_seconds,
        model="klingai:kling@o1",  # Kling O1 supports video-edit via inputs.video
        width=None,   # O1 infers dimensions from input video
        height=None,
        input_video_url=public_url
    )
    
    if error:
        raise RuntimeError(f"Runware generation failed: {error}")
    
    if not video_url:
        raise RuntimeError("Runware returned no URL and no error.")

    # 3. Download
    log.info(f"Downloading result from {video_url} to {output_video_path}...")
    success, dl_error = download_video_to_path(video_url, output_video_path)
    
    if not success:
        raise RuntimeError(f"Failed to download result: {dl_error}")
    
    return output_video_path
