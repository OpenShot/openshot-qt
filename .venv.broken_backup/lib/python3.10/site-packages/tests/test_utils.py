import asyncio
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import datetime
import base64
from unittest import TestCase, mock
import pytest
from runware.utils import (
    removeFromAray,
    getIntervalWithPromise,
    fileToBase64,
    getUUID,
    isValidUUID,
    getTaskType,
    evaluateToBoolean,
    compact,
    getPreprocessorType,
    accessDeepObject,
    delay,
    MockFile,
    generateString,
    remove1Mutate,
    removeListener,
    removeAllKeyListener,
)
from runware.types import Environment, EPreProcessor, EPreProcessorGroup


# @pytest.fixture
# def mock_file():
#     # Setup code before each test function
#     with patch(
#         "runware.utils.datetime",
#         MagicMock(now=MagicMock(return_value=datetime.datetime(2020, 1, 1))),
#     ):
#         yield MockFile()  # This replaces setUp and yields the MockFile object for each test

# def test_create_defaults(mock_file):


def test_create_defaults():
    with patch(
        "runware.utils.datetime",
        MagicMock(now=MagicMock(return_value=datetime.datetime(2020, 1, 1))),
    ):
        # Test default parameters
        mock_file = MockFile()
        blob = mock_file.create()
        assert blob.name == "mock.txt"
        assert len(blob) == 1024  # Testing __len__
        assert str(blob) == "a" * 1024  # Testing __str__
        assert blob.size() == 1024  # Testing size()
        assert blob.type == "plain/txt"
        # assert blob.lastModifiedDate == datetime.datetime(
        #     2020, 1, 1
        # )  # Check for mocked date


def test_create_custom_params():
    # Test custom parameters
    with patch(
        "runware.utils.datetime",
        MagicMock(now=MagicMock(return_value=datetime.datetime(2020, 1, 1))),
    ):
        mock_file = MockFile()
        blob = mock_file.create("example.txt", 2048, "text/plain")
        print(f"Blob:{blob.lastModifiedDate}:")
        assert blob.name == "example.txt"
        assert len(blob) == 2048
        assert str(blob) == "a" * 2048
        assert blob.size() == 2048
        assert blob.type == "text/plain"
        # assert blob.lastModifiedDate == datetime.datetime(
        #     2020, 1, 1
        # )  # Check for mocked date


def test_create_empty_file():
    # Test creating an empty file
    mock_file = MockFile()
    blob = mock_file.create("empty.txt", 0, "text/plain")
    assert blob.name == "empty.txt"
    assert len(blob) == 0
    assert str(blob) == ""
    assert blob.size() == 0
    assert blob.type == "text/plain"
    # assert blob.lastModifiedDate == datetime.datetime(
    #     2020, 1, 1
    # )  # Check for mocked date


def test_removeFromAray():
    arr = [1, 2, 3, 4]
    removeFromAray(arr, 2)
    assert arr == [1, 3, 4]


def test_getUUID():
    uuid = getUUID()
    assert isinstance(uuid, str)
    assert isValidUUID(uuid)


def test_isValidUUID():
    valid_uuid = "123e4567-e89b-12d3-a456-426655440000"
    invalid_uuid = "invalid-uuid"
    assert isValidUUID(valid_uuid)
    assert not isValidUUID(invalid_uuid)


def test_getTaskType():
    assert getTaskType("prompt", None, None, None) == 1
    assert getTaskType("prompt", None, None, "image") == 2
    assert getTaskType("prompt", None, "mask", "image") == 3
    assert getTaskType("prompt", "controlnet", None, None) == 9
    assert getTaskType("prompt", "controlnet", None, "image") == 10
    assert getTaskType("prompt", "controlnet", "mask", "image") == 10


def test_evaluateToBoolean():
    assert evaluateToBoolean(True, True, True)
    assert not evaluateToBoolean(True, False, True)


def test_compact():
    assert compact(True, {"a": 1}) == {"a": 1}
    assert compact(False, {"a": 1}) == {}


def test_getPreprocessorType():
    assert getPreprocessorType(EPreProcessor.canny) == EPreProcessorGroup.canny
    assert getPreprocessorType(EPreProcessor.depth_leres) == EPreProcessorGroup.depth
    assert (
        getPreprocessorType(EPreProcessor.lineart_anime)
        == EPreProcessorGroup.lineart_anime
    )
    assert (
        getPreprocessorType(EPreProcessor.openpose_face) == EPreProcessorGroup.openpose
    )
    assert getPreprocessorType(EPreProcessor.seg_ofade20k) == EPreProcessorGroup.seg


def test_accessDeepObject():
    data = {
        "a": {"b": [1, 2, 3], "c": {"d": "text"}},
        "e": [{"f": "value1"}, {"f": "value2"}],
    }

    # Test existing keys and array index
    assert accessDeepObject("a.b[1]", data) == 2
    assert accessDeepObject("a.c.d", data) == "text"

    # Test non-existent keys
    assert accessDeepObject("a.x", data, useZero=False) is None
    assert accessDeepObject("a.b[3]", data, useZero=True) == 0

    # Test boundary conditions for arrays
    assert accessDeepObject("e[0].f", data) == "value1"
    assert accessDeepObject("e[1].f", data) == "value2"
    assert accessDeepObject("e[2].f", data, useZero=False) is None

    # Test the shouldReturnString flag
    assert accessDeepObject("a", data, shouldReturnString=True) == json.dumps(data["a"])

    # Test invalid key format
    assert accessDeepObject("a..b", data, useZero=True) == 0
    assert accessDeepObject("a.[b]", data, useZero=False) is None


def test_generateString():
    assert generateString(3) == "aaa"


def test_remove1Mutate():
    arr = [1, 2, 3, 4]
    remove1Mutate(arr, 2)
    assert arr == [1, 3, 4]


def test_removeListener():
    listeners = [Mock(key="a"), Mock(key="b"), Mock(key="c")]
    listener = Mock(key="b")
    updated_listeners = removeListener(listeners, listener)
    assert len(updated_listeners) == 2
    assert listener not in updated_listeners


def test_removeAllKeyListener():
    listeners = [Mock(key="a"), Mock(key="b"), Mock(key="b"), Mock(key="c")]
    updated_listeners = removeAllKeyListener(listeners, "b")
    assert len(updated_listeners) == 2
    assert Mock(key="b") not in updated_listeners


@pytest.mark.asyncio
async def test_file_to_base64_success(tmpdir):
    # Create a temporary file
    file_path = tmpdir / "test_image.jpg"
    file_contents = b"test_file_contents"  # Sample content
    # Use the built-in 'open' to write
    with open(file_path, "wb") as f:
        f.write(file_contents)

    # Patch aiofiles.open to return an AsyncMock
    with patch("aiofiles.open") as mock_open:
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=file_contents)
        mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        result = await fileToBase64(str(file_path))

    # Assert the expected Base64 representation of file_contents
    expected_base64 = base64.b64encode(file_contents).decode("utf-8")
    assert result == expected_base64


@pytest.mark.asyncio
async def test_file_to_base64_file_not_found(tmpdir):
    file_path = tmpdir / "nonexistent_file.txt"
    # Patch aiofiles.open to raise FileNotFoundError
    with patch("aiofiles.open", side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError) as error_info:
            await fileToBase64(str(file_path))

        assert str(error_info.value) == f"The file at {file_path} does not exist."


@pytest.mark.asyncio
async def test_delay():
    with patch("asyncio.sleep") as mock_sleep:
        await delay(1.5)
        mock_sleep.assert_called_once_with(1.5)


@pytest.mark.asyncio
async def test_immediate_resolution():
    async def callback(params):
        params["resolve"]("resolved immediately")
        return True  # Stop the interval immediately

    result = await getIntervalWithPromise(
        callback, timeOutDuration=5000, pollingInterval=100
    )
    assert (
        result == "resolved immediately"
    ), "The future should have been resolved immediately."


@pytest.mark.asyncio
async def test_timeout():
    async def callback(params):
        await asyncio.sleep(
            1
        )  # Simulate delay longer than polling but not long enough to resolve
        return False  # Continue the interval

    with pytest.raises(asyncio.TimeoutError):
        await getIntervalWithPromise(
            callback,
            debugKey="timeout_test",
            timeOutDuration=500,
            shouldThrowError=True,
        )


@pytest.mark.asyncio
async def test_callback_error_handling():
    async def callback(params):
        raise Exception("Deliberate exception")

    with pytest.raises(Exception) as exc_info:
        await getIntervalWithPromise(
            callback, debugKey="error_test", timeOutDuration=2000
        )
    assert "Deliberate exception" in str(
        exc_info.value
    ), "The specific error should be caught and raised."


@pytest.mark.asyncio
async def test_proper_interval_handling():
    call_count = 0

    async def callback(params):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:  # Resolve after 3 calls
            params["resolve"]("resolved after several intervals")
            return True
        return False

    result = await getIntervalWithPromise(
        callback, debugKey="interval_test", timeOutDuration=2000, pollingInterval=500
    )
    assert (
        result == "resolved after several intervals"
    ), "Should resolve after exactly 3 intervals."
    assert call_count == 3, "Callback should be called exactly 3 times."
