import asyncio
import base64
import os
import re
import time
from urllib.parse import urlparse

import aiofiles
import datetime
import uuid
import json
import mimetypes
import inspect
from typing import Any, Dict, List, Union, Optional, TypeVar, Type, Coroutine, get_type_hints, get_origin, get_args
from dataclasses import fields, is_dataclass
from .types import (
    Environment,
    EPreProcessor,
    EPreProcessorGroup,
    ListenerType,
    IControlNet,
    File,
    GetWithPromiseCallBackType,
    IImage,
    ETaskType,
    IImageToText,
    IVideoToText,
    IEnhancedPrompt,
    IError,
    UploadImageType,
    IAsyncTaskResponse,
    IOutput,
)
import logging

logger = logging.getLogger(__name__)

if not mimetypes.guess_type("test.webp")[0]:
    mimetypes.add_type("image/webp", ".webp")

BASE_RUNWARE_URLS = {
    Environment.PRODUCTION: "wss://ws-api.runware.ai/v1",
    Environment.TEST: "ws://localhost:8080",
}


RETRY_SDK_COUNTS = {
    "GLOBAL": 2,
    "REQUEST_IMAGES": 2,
}

# WebSocket connection health check timeout (milliseconds)
# Maximum time to wait for pong response after sending ping
# Used in: server.heartBeat() to detect connection loss
PING_TIMEOUT_DURATION = 10000

# WebSocket ping interval (milliseconds)
# How often to send ping messages to keep connection alive
# Used in: server.heartBeat() for periodic health checks
PING_INTERVAL = 5000

# Image generation timeout (milliseconds)
# Maximum time to wait for image generation completion (imageInference, photoMaker)
# Used in: photoMaker(), getSimililarImage() for waiting image generation results
IMAGE_INFERENCE_TIMEOUT = int(os.environ.get(
    "RUNWARE_IMAGE_INFERENCE_TIMEOUT",
    300000
))

# Image operation timeout (milliseconds)
# Maximum time to wait for image operations (caption, background removal, upscale)
# Used in: imageCaption(), imageBackgroundRemoval(), imageUpscale()
IMAGE_OPERATION_TIMEOUT = int(os.environ.get(
    "RUNWARE_IMAGE_OPERATION_TIMEOUT",
    120000
))

# Image upload timeout (milliseconds)
# Maximum time to wait for image upload to complete
# Used in: uploadImage() for uploading local images or base64 data
IMAGE_UPLOAD_TIMEOUT = int(os.environ.get(
    "RUNWARE_IMAGE_UPLOAD_TIMEOUT",
    60000
))

# Model upload timeout (milliseconds)
# Maximum time to wait for model upload to complete
# Used in: _modelUpload() for uploading models (LoRA, checkpoints, etc.)
MODEL_UPLOAD_TIMEOUT = int(os.environ.get(
    "RUNWARE_MODEL_UPLOAD_TIMEOUT",
    900000  # 15 minutes default - models can be large
))

# Maximum number of times to retry after authentication failures (used in _retry_with_reconnect())
MAX_RETRY_ATTEMPTS = 10

# Video initial response timeout (milliseconds)
# Maximum time to wait for initial video generation response or polling response
# Used in: _handleInitialVideoResponse(), _sendPollRequest()
VIDEO_INITIAL_TIMEOUT = int(os.environ.get(
    "RUNWARE_VIDEO_INITIAL_TIMEOUT",
    30000
))

# Video polling delay (milliseconds)
# Delay between consecutive polling requests for video generation status
# Used in: _pollVideoResults() for checking video generation progress
VIDEO_POLLING_DELAY = int(os.environ.get(
    "RUNWARE_VIDEO_POLLING_DELAY",
    3000
))

# Audio initial response timeout (milliseconds)
# Maximum time to wait for the initial audio response before falling back to async handling
# Used in: _handleInitialAudioResponse() for async delivery method
AUDIO_INITIAL_TIMEOUT = int(os.environ.get(
    "RUNWARE_AUDIO_INITIAL_TIMEOUT",
    30000
))

# Audio generation timeout (milliseconds)
# Maximum time to wait for audio generation completion
# Used in: _waitForAudioCompletion() for single audio generation
AUDIO_INFERENCE_TIMEOUT = int(os.environ.get(
    "RUNWARE_AUDIO_INFERENCE_TIMEOUT",
    300000
))

# Audio polling delay (milliseconds)
# Delay between consecutive polling requests for audio generation status
# Used in: _pollForAudioResults() for checking audio generation progress
AUDIO_POLLING_DELAY = int(os.environ.get(
    "RUNWARE_AUDIO_POLLING_DELAY",
    1000
))

# Image initial response timeout (milliseconds)
# Maximum time to wait for the initial image response before falling back to async handling
# Used in: _handleInitialImageResponse() for async delivery method
IMAGE_INITIAL_TIMEOUT = int(os.environ.get(
    "RUNWARE_IMAGE_INITIAL_TIMEOUT",
    60000
))

# Image polling delay (milliseconds)
# Delay between consecutive polling requests for image generation status
# Used in: _pollResults() for checking image generation progress
IMAGE_POLLING_DELAY = int(os.environ.get(
    "RUNWARE_IMAGE_POLLING_DELAY",
    1000
))

# Prompt enhancement timeout (milliseconds)
# Maximum time to wait for prompt enhancement completion
# Used in: promptEnhance() for enhancing text prompts
PROMPT_ENHANCE_TIMEOUT = int(os.environ.get(
    "RUNWARE_PROMPT_ENHANCE_TIMEOUT",
    60000
))

# Webhook acknowledgment timeout (milliseconds)
# Maximum time to wait for webhook task acknowledgment
# Used in: videoCaption(), videoBackgroundRemoval(), videoUpscale() when webhook is provided
WEBHOOK_TIMEOUT = int(os.environ.get(
    "RUNWARE_WEBHOOK_TIMEOUT",
    30000
))

# Default timeout duration (milliseconds)
# Maximum time to wait for general operations (model upload, model search, media upload)
# Used in: RunwareBase.__init__(), uploadMedia(), modelUpload(), modelSearch()
TIMEOUT_DURATION = int(os.environ.get(
    "RUNWARE_TIMEOUT_DURATION",
    480000
))
# Maximum polling attempts for video generation
# Number of polling iterations before timing out video generation
# Used in: _pollVideoResults() for video generation status checks
MAX_POLLS_VIDEO_GENERATION = int(os.environ.get("RUNWARE_MAX_POLLS_VIDEO_GENERATION", 480))

# Maximum polling attempts for audio generation
# Number of polling iterations before timing out audio generation
# Used in: _pollAudioResults() for audio generation status checks
MAX_POLLS_AUDIO_GENERATION = int(os.environ.get("RUNWARE_MAX_POLLS_AUDIO_GENERATION", 240))


MAX_POLLS = int(os.environ.get("RUNWARE_MAX_POLLS", 480))

class LISTEN_TO_IMAGES_KEY:
    REQUEST_IMAGES = "REQUEST_IMAGES"


class RunwareAPIError(Exception):
    def __init__(self, error_data: dict):
        self.code = error_data.get("code")
        self.error_data = error_data
        super().__init__(str(error_data))

    def __str__(self):
        return f"RunwareAPIError: {self.error_data}"


class RunwareError(Exception):
    def __init__(self, ierror: IError):
        self.ierror = ierror
        super().__init__(f"Runware Error: {ierror.error_message}")

    def format_error(self):
        return {
            "errors": [
                {
                    "code": self.ierror.error_code,
                    "message": self.ierror.error_message,
                    "parameter": self.ierror.parameter,
                    "type": self.ierror.error_type,
                    "documentation": self.ierror.documentation,
                    "taskUUID": self.ierror.task_uuid,
                }
            ]
        }

    def __str__(self):
        return f"Runware Error: {self.format_error()}"


class Blob:
    """
    A Python equivalent of the Blob class to simulate file-like behavior in an immutable manner.

    This class is designed to closely align with the TypeScript implementation of the Blob class.
    It provides a way to represent and manipulate immutable binary data, similar to how files are handled.

    :param blob_parts: List[bytes], content parts of the blob, typically bytes.
    :param options: Dict[str, Any], containing options such as type (MIME type).

    Example:
        content = b"Hello, world!"
        blob = Blob([content], {"type": "text/plain"})
        print(len(blob))  # Output: 13
        print(str(blob))  # Output: "Hello, world!"
        print(blob.size())  # Output: 13
    """

    def __init__(
        self,
        blob_parts: Optional[List[bytes]] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Blob object.
        :param blob_parts: List[bytes], content parts of the blob, typically bytes.
        :param options: Dict[str, Any], containing options such as type (MIME type).
        """
        self._content = b"".join(blob_parts) if blob_parts else b""
        self.type = options.get("type", "") if options else ""

    def __len__(self) -> int:
        return len(self._content)

    def __str__(self) -> str:
        return self._content.decode("utf-8")

    def size(self) -> int:
        return len(self)


class MockFile:
    """
    A class that provides a method to create mock file objects for testing purposes.

    The `create` method generates a Blob object that simulates a file with specified attributes
    such as name, size, and MIME type. This is useful when you need to work with file-like objects
    in tests or when actual files are not available.

    Example:
        mock_file = MockFile()
        file_obj = mock_file.create(name="example.txt", size=2048, mime_type="text/plain")
        print(file_obj.name)  # Output: "example.txt"
        print(file_obj.size())  # Output: 2048
        print(file_obj.type)  # Output: "text/plain"
        print(file_obj.lastModifiedDate)  # Output: current datetime
    """

    def create(
        self, name: str = "mock.txt", size: int = 1024, mime_type: str = "plain/txt"
    ) -> Blob:
        """
        Create a mock file object with specified attributes.

        This method generates a Blob object that simulates a file. The content of the file is
        created as a sequence of 'a' characters repeated 'size' times. The Blob object is then
        enhanced with additional attributes to mimic a real file, such as name and lastModifiedDate.

        :param name: str, the name of the file (default: "mock.txt")
        :param size: int, the size of the file in bytes (default: 1024)
        :param mime_type: str, the MIME type of the file (default: "plain/txt")
        :return: Blob, a Blob object simulating a file with the specified attributes
        """
        content = ("a" * size).encode()  # Create content as bytes
        blob = Blob(blob_parts=[content], options={"type": mime_type})

        # Simulate File attributes by adding properties to the Blob object
        setattr(blob, "name", name)
        setattr(blob, "lastModifiedDate", datetime.datetime.now())
        return blob


T = TypeVar("T")


def removeFromAray(col: Optional[List[T]], targetElem: T) -> None:
    """
    Remove the first occurrence of an element from an array.

    :param col: Optional[List[T]], the collection from which to remove the element. None is safely handled.
    :param target_elem: T, the element to remove from the collection.
    """
    if col is None:
        return
    try:
        col.remove(targetElem)
    except ValueError:
        # If targetElem is not in col, do nothing
        return


def getUUID() -> str:
    """
    Generate and return a new UUID as a string.
    """
    return str(uuid.uuid4())


def isValidUUID(uuid_str: str) -> bool:
    """
    Check if a given string is a valid UUID.

    :param uuid_str: str, the UUID string to validate.
    :return: bool, True if the string is a valid UUID, otherwise False.
    """
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False


def evaluateToBoolean(*args: Any) -> bool:
    """
    Evaluate to boolean by checking if all arguments are truthy.

    :param args: Variable length argument list of any type.
    :return: Returns True if all arguments are truthy, otherwise False.
    """
    return all(args)


def compact(key: Any, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a dictionary containing the data if the key is truthy, otherwise returns an empty dictionary.

    :param key: Any, the key to check for truthiness.
    :param data: Dict[str, Any], the dictionary to return if the key is truthy.
    :return: A dictionary containing the data if key is truthy; otherwise, an empty dictionary.

    Example:
        lowThresholdCanny = 5  # or None if it should be omitted
        highThresholdCanny = 10  # or None if it should be omitted
        send_data = {
            "newPreProcessControlNet": {
                "taskUUID": "some-uuid",
                "preProcessorType": "some-type",
                "guideImageUUID": "another-uuid",
                "includeHandsAndFaceOpenPose": True,
                **compact(lowThresholdCanny, {"lowThresholdCanny": lowThresholdCanny}),
                **compact(highThresholdCanny, {"highThresholdCanny": highThresholdCanny}),
            },
        }
    """
    return data if key else {}


#  originally range() in Typescipt library, renamed nu avoid conflict with Python's built-in range function
# TODO: only used in tests/test_utils.py, consider removing
def generateString(count: int) -> str:
    return "a" * count


# TODO: function it's not used in the code anywhere else, consider removing
def remove1Mutate(col: List[Any], targetElem: Any) -> None:
    if col is None:
        return
    try:
        col.remove(targetElem)
    except ValueError:
        return


async def fileToBase64(file_path: str) -> str:
    """
    Asynchronously convert a file at a given path to a Base64-encoded string.

    :param file_path: str, the path to the file.
    :return: str, Base64-encoded content of the file.
    :raises FileNotFoundError: if the file does not exist.
    :raises IOError: if the file cannot be read.

    Example:
        try:
            if isinstance(file, str) and file.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                image_base64 = await fileToBase64(file)
            else:
                # Otherwise, use the string directly as it might be a Base64 string
                image_base64 = file

            await send({
                "newImageUpload": {
                    "imageBase64": image_base64,
                    "taskUUID": task_uuid,
                    "taskType": task_type,
                }
            })
        except FileNotFoundError as e:
            print(f"Error: {e}")
        except IOError as e:
            print(f"Error: {e}")

    """
    try:
        async with aiofiles.open(file_path, "rb") as file:
            file_contents = await file.read()
            mime_type, _ = mimetypes.guess_type(file_path)

            if mime_type is None:
                raise ValueError(
                    f"Unable to determine the MIME type for file: {file_path}"
                )

            base64_content = base64.b64encode(file_contents).decode("utf-8")
            return f"data:{mime_type};base64,{base64_content}"
    except FileNotFoundError:
        raise FileNotFoundError(f"The file at {file_path} does not exist.")
    except IOError:
        raise IOError(f"The file at {file_path} could not be read.")


def removeListener(
    listeners: List[ListenerType], listener: ListenerType
) -> List[ListenerType]:
    """
    Remove a specified listener from a list of listeners.

    This function filters out the listener whose `key` attribute matches that of the given `listener` object.
    It returns a new list without altering the original list of listeners.

    :param listeners: List[ListenerType], the list from which to remove the listener.
    :param listener: ListenerType, the listener to be removed based on its 'key'.
    :return: List[ListenerType], a new list with the specified listener removed.
    """

    return [lis for lis in listeners if lis.key != listener.key]


def removeAllKeyListener(listeners: List[ListenerType], key: str) -> List[ListenerType]:
    """
    Remove all listeners from the list that have a specific key.

    This function filters out all listeners whose `key` attribute matches the specified `key`.
    It creates a new list of listeners without those that have the matching key, without altering the original list.

    :param listeners: List[ListenerType], the list from which to remove listeners.
    :param key: str, the key associated with listeners to be removed.
    :return: List[ListenerType], a new list with all matching key listeners removed.
    """
    return [lis for lis in listeners if lis.key != key]


async def delay(time: float, milliseconds: int = 1000) -> None:
    """
    Asynchronously wait for a specified amount of time.

    :param time: float, the number of time units to wait.
    :param milliseconds: int, number of milliseconds each time unit represents.
    """
    await asyncio.sleep(time * milliseconds / 1000)


def getTaskType(
    prompt: str,
    controlNet: Optional[List[IControlNet]],
    imageMaskInitiator: Optional[Union[File, str]],
    imageInitiator: Optional[Union[File, str]],
) -> int:
    """
    Determine the task type based on the presence or absence of various parameters.

    :param prompt: str, the prompt text.
    :param control_net: Optional[List[IControlNet]], a list of settings for controlling the network, which can be None.
    :param image_initiator: Optional[Union[File, str]], a File object or a string path indicating the image initiator.
    :param image_mask_initiator: Optional[Union[File, str]], a File object or a string path indicating the image mask initiator.
    :return: int, the task type determined by the conditions.
    """
    if evaluateToBoolean(
        prompt, not controlNet, not imageMaskInitiator, not imageInitiator
    ):
        return 1
    if evaluateToBoolean(
        prompt, not controlNet, not imageMaskInitiator, imageInitiator
    ):
        return 2
    if evaluateToBoolean(prompt, not controlNet, imageMaskInitiator, imageInitiator):
        return 3
    if evaluateToBoolean(
        prompt, controlNet, not imageMaskInitiator, not imageInitiator
    ):
        return 9
    if evaluateToBoolean(prompt, controlNet, not imageMaskInitiator, imageInitiator):
        return 10
    if evaluateToBoolean(prompt, controlNet, imageMaskInitiator, imageInitiator):
        return 10
    # TODO: Better handling of invalid task types, e.g. raise an exception
    return -1


def getPreprocessorType(processor: EPreProcessor) -> EPreProcessorGroup:
    """
    Determine the preprocessor group based on the given preprocessor.

    :param processor: EPreProcessor, the preprocessor for which to determine the group.
    :return: EPreProcessorGroup, the corresponding preprocessor group for the given preprocessor.

    This function maps an EPreProcessor enum value to its corresponding EPreProcessorGroup enum value.
    It helps in identifying the group or category to which a specific preprocessor belongs.

    Example:
        preprocessor = EPreProcessor.canny
        group = getPreprocessorType(preprocessor)
        print(group)  # Output: EPreProcessorGroup.canny
    """
    if processor == EPreProcessor.canny:
        return EPreProcessorGroup.canny
    elif processor in [
        EPreProcessor.depth_leres,
        EPreProcessor.depth_midas,
        EPreProcessor.depth_zoe,
    ]:
        return EPreProcessorGroup.depth
    elif processor == EPreProcessor.inpaint_global_harmonious:
        return EPreProcessorGroup.depth
    elif processor == EPreProcessor.lineart_anime:
        return EPreProcessorGroup.lineart_anime
    elif processor in [
        EPreProcessor.lineart_coarse,
        EPreProcessor.lineart_realistic,
        EPreProcessor.lineart_standard,
    ]:
        return EPreProcessorGroup.lineart
    elif processor == EPreProcessor.mlsd:
        return EPreProcessorGroup.mlsd
    elif processor == EPreProcessor.normal_bae:
        return EPreProcessorGroup.normalbae
    elif processor in [
        EPreProcessor.openpose_face,
        EPreProcessor.openpose_faceonly,
        EPreProcessor.openpose_full,
        EPreProcessor.openpose_hand,
        EPreProcessor.openpose,
    ]:
        return EPreProcessorGroup.openpose
    elif processor in [EPreProcessor.scribble_hed, EPreProcessor.scribble_pidinet]:
        return EPreProcessorGroup.scribble
    elif processor in [
        EPreProcessor.seg_ofade20k,
        EPreProcessor.seg_ofcoco,
        EPreProcessor.seg_ufade20k,
    ]:
        return EPreProcessorGroup.seg
    elif processor == EPreProcessor.shuffle:
        return EPreProcessorGroup.shuffle
    elif processor in [
        EPreProcessor.softedge_hed,
        EPreProcessor.softedge_hedsafe,
        EPreProcessor.softedge_pidinet,
        EPreProcessor.softedge_pidisafe,
    ]:
        return EPreProcessorGroup.softedge
    elif processor == EPreProcessor.tile_gaussian:
        return EPreProcessorGroup.tile
    else:
        return EPreProcessorGroup.canny


def accessDeepObject(
    key: str,
    data: Dict[str, Any],
    useZero: bool = True,
    shouldReturnString: bool = False,
) -> Any:
    """
    Navigate deeply nested data structures based on a dot/bracket-notated key.

    :param key: str, the key path (e.g., "person.address[0].street").
    :param data: dict, the data to navigate.
    :param useZero: bool, return 0 instead of None for non-existent values.
    :param shouldReturnString: bool, return a JSON string of the object if True.
    :return: The value found at the key path or a default value.
    """

    # Get the current frame
    current_frame = inspect.currentframe()

    # Get the caller's frame
    caller_frame = current_frame.f_back

    # Get the caller's function name
    caller_name = caller_frame.f_code.co_name

    # Get the caller's line number
    caller_line_number = caller_frame.f_lineno

    logger.debug(
        f"Function {accessDeepObject.__name__} called by {caller_name} at line {caller_line_number}"
    )
    logger.debug(f"accessDeepObject key: {key}")
    logger.debug(f"accessDeepObject data: {data}")

    default_value = 0 if useZero else None

    # if "data" in data and isinstance(data["data"], list):
    #     # Iterate through each item in the data list
    #     for item in data["data"]:
    #         # Check if 'taskType' is in the item and matches the target_task_type
    #         if "taskType" in item and item["taskType"] == key:
    #             # Return the entire item if there's a match
    #             matching_tasks.append(item)
    matching_tasks = []

    for field in ["data", "errors"]:
        if field in data and isinstance(data[field], list):
            for item in data[field]:
                if "taskUUID" in item and item["taskUUID"] == key:
                    matching_tasks.append(item)

    # Check for successful messages
    if "data" in data and isinstance(data["data"], list):
        for item in data["data"]:
            if "taskUUID" in item and item["taskUUID"] == key:
                matching_tasks.append(item)

    # Check for error messages
    if "errors" in data and isinstance(data["errors"], list):
        for error in data["errors"]:
            if "taskUUID" in error and error["taskUUID"] == key:
                matching_tasks.append(error)

    if len(matching_tasks) == 0:
        return default_value

    logger.debug(f"accessDeepObject matching_tasks: {matching_tasks}")

    if shouldReturnString and isinstance(matching_tasks, (dict, list)):
        return json.dumps(matching_tasks)

    return matching_tasks

    # keys = re.split(r"\.|\[", key)
    # keys = [k.replace("]", "") for k in keys]

    # logger.debug(f"accessDeepObject keys: {keys}")

    # current_value = data
    # for k in keys:
    #     logger.debug(f"accessDeepObject key: {k}")
    #     # logger.debug(
    #     #     "isinstance(current_value, (dict, list))",
    #     #     str(isinstance(current_value, (dict, list))),
    #     # )
    #     if isinstance(current_value, (dict, list)):
    #         logger.debug(f"accessDeepObject current_value: {current_value}")
    #         logger.debug(f"k in current_value: {k in current_value}")
    #         if k.isdigit() and isinstance(current_value, list):
    #             index = int(k)
    #             if 0 <= index < len(current_value):
    #                 current_value = current_value[index]
    #             else:
    #                 return default_value
    #         elif k in current_value:
    #             current_value = current_value[k]
    #         else:
    #             return default_value
    #     else:
    #         return default_value

    # logger.debug(f"accessDeepObject current_value: {current_value}")

    # if shouldReturnString and isinstance(current_value, (dict, list)):
    #     return json.dumps(current_value)

    # return current_value


def createEnhancedPromptsFromResponse(response: List[dict]) -> List[IEnhancedPrompt]:
    def process_single_prompt(prompt_data: dict) -> IEnhancedPrompt:
        processed_fields = {}

        for field in fields(IEnhancedPrompt):
            if field.name in prompt_data:
                if field.name == "taskType":
                    processed_fields[field.name] = ETaskType(prompt_data[field.name])
                elif field.type == float or field.type == Optional[float]:
                    processed_fields[field.name] = float(prompt_data[field.name])
                else:
                    processed_fields[field.name] = prompt_data[field.name]

        return instantiateDataclass(IEnhancedPrompt, processed_fields)

    return [process_single_prompt(prompt) for prompt in response]


def createAsyncTaskResponse(response: dict) -> IAsyncTaskResponse:
    processed_fields = {}

    for field in fields(IAsyncTaskResponse):
        if field.name in response:
            processed_fields[field.name] = response[field.name]

    return instantiateDataclass(IAsyncTaskResponse, processed_fields)


def createImageFromResponse(response: dict) -> IImage:
    processed_fields = {}

    for field in fields(IImage):
        if field.name in response:
            if field.type == bool or field.type == Optional[bool]:
                processed_fields[field.name] = bool(response[field.name])
            elif field.type == float or field.type == Optional[float]:
                processed_fields[field.name] = float(response[field.name])
            else:
                processed_fields[field.name] = response[field.name]

    return instantiateDataclass(IImage, processed_fields)


def createImageToTextFromResponse(response: dict) -> IImageToText:
    processed_fields = {}

    for field in fields(IImageToText):
        if field.name in response:
            if field.name == "taskType":
                # Convert string to ETaskType enum
                processed_fields[field.name] = ETaskType(response[field.name])
            elif field.type == float or field.type == Optional[float]:
                processed_fields[field.name] = float(response[field.name])
            else:
                processed_fields[field.name] = response[field.name]

    return instantiateDataclass(IImageToText, processed_fields)


def createVideoToTextFromResponse(response: dict) -> IVideoToText:
    processed_fields = {}

    for field in fields(IVideoToText):
        if field.name in response:
            if field.type == float or field.type == Optional[float]:
                processed_fields[field.name] = float(response[field.name])
            else:
                processed_fields[field.name] = response[field.name]

    return instantiateDataclass(IVideoToText, processed_fields)


async def getIntervalWithPromise(
        callback: GetWithPromiseCallBackType,
        debugKey: str = "debugKey",
        timeOutDuration: int = TIMEOUT_DURATION,
        shouldThrowError: bool = True,
        pollingInterval: int = 350,
) -> Any:
    logger = logging.getLogger(__name__)

    start_time = time.perf_counter()
    loop = asyncio.get_event_loop()
    result_future = loop.create_future()
    interval_handle = None

    async def polling_coroutine():
        while not result_future.done():
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if elapsed_ms > timeOutDuration:
                if interval_handle:
                    logger.debug(f"Interval cleared due to timeout for {debugKey}")
                if shouldThrowError:
                    error_msg = (
                        f"Timeout error: Message could not be received for {debugKey} | "
                        f"Operation: {debugKey} | "
                        f"Timeout: {timeOutDuration}ms | "
                        f"Elapsed: {elapsed_ms:.2f}ms"
                    )
                    raise Exception(error_msg)
                return None

            iteration_resolved = False
            iteration_result = None
            iteration_error = None

            def safe_resolve(value):
                nonlocal iteration_resolved, iteration_result
                if not iteration_resolved:
                    iteration_resolved = True
                    iteration_result = value

            def safe_reject(error):
                nonlocal iteration_resolved, iteration_error
                if not iteration_resolved:
                    iteration_resolved = True
                    if isinstance(error, BaseException):
                        iteration_error = error
                    else:
                        iteration_error = Exception(str(error))

            try:
                if asyncio.iscoroutinefunction(callback):
                    callback_returned = await callback(safe_resolve, safe_reject, interval_handle)
                else:
                    callback_returned = callback(safe_resolve, safe_reject, interval_handle)
                if callback_returned and iteration_resolved:
                    if iteration_error is not None:
                        raise iteration_error
                    return iteration_result

            except Exception as e:
                logger.exception(f"Error in callback for {debugKey}: {str(e)}")
                raise

            await asyncio.sleep(pollingInterval / 1000)

    interval_handle = asyncio.ensure_future(polling_coroutine())

    def handle_polling_done(task):
        if not result_future.done():
            if task.cancelled():
                result_future.cancel()
            else:
                try:
                    result = task.result()
                    result_future.set_result(result)
                except Exception as e:
                    result_future.set_exception(e)

    interval_handle.add_done_callback(handle_polling_done)

    try:
        return await result_future
    finally:
        if interval_handle and not interval_handle.done():
            interval_handle.cancel()
            try:
                await interval_handle
            except asyncio.CancelledError:
                pass


def instantiateDataclass(dataclass_type: Type[Any], data: dict) -> Any:
    """
    Instantiates a dataclass object from a dictionary, filtering out any unknown attributes.
    Handles nested dataclasses by recursively instantiating them.

    :param dataclass_type: The dataclass type to instantiate.
    :param data: A dictionary with data.
    :return: An instantiated dataclass object.
    """
    hints = get_type_hints(dataclass_type)
    valid_fields = {f.name for f in fields(dataclass_type)}
    filtered_data = {}
    
    for k, v in data.items():
        if k not in valid_fields:
            continue
        
        if v is None:
            filtered_data[k] = None
            continue
        
        field_type = hints.get(k)
        
        # Unwrap Optional[X] -> X
        if get_origin(field_type) is Union:
            args = [a for a in get_args(field_type) if a is not type(None)]
            field_type = args[0] if args else field_type
        
        # Nested dataclass
        if is_dataclass(field_type) and isinstance(v, dict):
            filtered_data[k] = instantiateDataclass(field_type, v)
        # List[Dataclass]
        elif get_origin(field_type) is list and isinstance(v, list):
            inner = get_args(field_type)[0] if get_args(field_type) else None
            if inner and is_dataclass(inner):
                filtered_data[k] = [instantiateDataclass(inner, i) if isinstance(i, dict) else i for i in v]
            else:
                filtered_data[k] = v
        else:
            filtered_data[k] = v
    
    return dataclass_type(**filtered_data)


def instantiateDataclassList(
    dataclass_type: Type[Any], data_list: List[dict]
) -> List[Any]:
    """
    Instantiates a list of dataclass objects from a list of dictionaries,
    filtering out any unknown attributes.

    :param dataclass_type: The dataclass type to instantiate.
    :param data_list: A list of dictionaries with data.
    :return: A list of instantiated dataclass objects.
    """
    if data_list is None or len(data_list) == 0:
        raise ValueError(
            f"Cannot instantiate dataclass list: data_list is None or empty for type {getattr(dataclass_type, '__name__', str(dataclass_type))}"
        )
    
    # Get the set of valid field names for the dataclass
    instances = []
    for data in data_list:
        instances.append(instantiateDataclass(dataclass_type, data))
    return instances


def isLocalFile(file):
    if os.path.isfile(file):
        return True

    # Check if the string is a valid UUID
    if isValidUUID(file):
        return False

    # Check if the string is a valid URL
    parsed_url = urlparse(file)
    if parsed_url.scheme and parsed_url.netloc:
        return False  # Use the URL as is
    else:
        # Handle case with no scheme and no netloc
        if (
            not parsed_url.scheme
            and not parsed_url.netloc
            or parsed_url.scheme == "data"
        ):
            # Check if it's a base64 string (with or without data URI prefix)
            if file.startswith("data:") or re.match(r"^[A-Za-z0-9+/]+={0,2}$", file):
                # Assume it's a base64 string (with or without data URI prefix)
                return False

            # Assume it's a URL without scheme (e.g., 'example.com/some/path')
            # Add 'https://' in front and treat it as a valid URL
            file = f"https://{file}"
            parsed_url = urlparse(file)
            if parsed_url.netloc:  # Now it should have a valid netloc
                return False
            else:
                raise FileNotFoundError(f"File or URL '{file}' not found.")

    raise FileNotFoundError(f"File or URL '{file}' not valid or not found.")


async def process_image(
    image: Optional[Union[str, list, UploadImageType | None | File]],
) -> None | list[Any] | str:
    if image is None:
        return None
    elif isinstance(image, list):
        images = []
        for image in image:
            images.append(await process_image(image))
        return images
    elif isinstance(image, UploadImageType):
        return image.imageUUID
    if isLocalFile(image) and not image.startswith("http"):
        return await fileToBase64(image)
    return image