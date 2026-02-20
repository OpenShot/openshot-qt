import pytest

from typing import Any
from runware.types import (
    IControlNet,
    IControlNetCanny,
    IControlNetOpenPose,
    IImageInference,
    File,
    RequireAtLeastOne,
    RequireOnlyOne,
    ListenerType,
    EPreProcessor,
    EOpenPosePreProcessor,
    EControlMode,
)


def test_icontrol_net_union():
    canny_control_net = IControlNetCanny(
        model='qatests:68487@08629',
        weight=0.5,
        startStep=0,
        endStep=10,
        guideImage="canny_image.png",
        controlMode=EControlMode.BALANCED,
        lowThresholdCanny=100,
        highThresholdCanny=200,

    )
    assert isinstance(canny_control_net, IControlNet)

    hands_face_control_net = IControlNetOpenPose(
        preprocessor=EOpenPosePreProcessor.openpose_face,
        weight=0.7,
        startStep=5,
        endStep=15,
        guideImage="hands_face_image.png",
        controlMode=EControlMode.PROMPT,
        includeHandsAndFaceOpenPose=True,
    )
    assert isinstance(hands_face_control_net, IControlNet)


def test_irequest_image():
    request_image = IImageInference(
        positivePrompt="A beautiful landscape",
        width=512,
        height=512,
        model='qatests:68487@08629',
        seedImage=File(b"image_data"),
        maskImage="mask.png",
    )
    assert request_image.positivePrompt == "A beautiful landscape"
    assert request_image.width == 512
    assert request_image.height == 512
    assert request_image.model == 'qatests:68487@08629'
    assert isinstance(request_image.seedImage, File)
    assert request_image.maskImage == "mask.png"


def test_require_at_least_one():
    data = {"key1": "value1", "key2": "value2", "key3": "value3"}
    obj = RequireAtLeastOne(data, ["key1", "key3"])
    assert obj["key1"] == "value1"
    assert "key2" in obj
    assert len(obj) == 3


def test_require_only_one():
    data = {"key1": "value1"}
    obj = RequireOnlyOne(data, ["key1"])
    assert obj["key1"] == "value1"
    data = {"key1": "value1", "key2": "value2"}
    with pytest.raises(ValueError):
        RequireOnlyOne(data, ["key1", "key2"])


def test_require_at_least_one_missing_keys():
    data = {"key1": "value1"}
    obj = RequireAtLeastOne(data, ["key1", "key2"])
    assert obj["key1"] == "value1"
    assert "key2" not in obj
    assert len(obj) == 1


def test_require_at_least_one_non_string_keys():
    data = {1: "value1", "key2": "value2"}  # One key is an integer
    obj = RequireAtLeastOne(data, [1, "key2"])
    assert obj[1] == "value1"


def test_require_at_least_one_extra_keys():
    data = {"key1": "value1", "key2": "value2", "extra_key": "extra"}
    obj = RequireAtLeastOne(data, ["key1"])
    assert obj["extra_key"] == "extra"
    assert obj["key1"] == "value1"


def test_require_at_least_one_non_dict_data():
    with pytest.raises(TypeError, match="data must be a dictionary"):
        RequireAtLeastOne("some_string", ["key1"])


def test_require_at_least_one_invalid_required_keys():
    data = {"key1": "value1"}
    with pytest.raises(TypeError):
        RequireAtLeastOne(data, 123)  # 123 as an example of a non-iterable, non-string


def test_require_at_least_one_removing_key():
    data = {"key1": "value1", "key2": "value2"}
    obj = RequireAtLeastOne(data, ["key1", "key2"])
    del obj["key1"]
    assert "key2" in obj
    assert len(obj) == 1

    del obj["key2"]
    assert len(obj) == 0

    with pytest.raises(
        ValueError,
        match="At least one of the required keys must be present: key1, key2",
    ):
        RequireAtLeastOne({"extra_key": "extra"}, ["key1", "key2"])


def test_require_only_one_adding_keys():
    data = {"key1": "value1"}
    obj = RequireOnlyOne(data, ["key1"])  # Specify only one required key

    obj["key2"] = "value2"  # Adding a non-required key should be allowed
    assert "key2" in obj
    assert len(obj) == 2

    with pytest.raises(ValueError):
        RequireOnlyOne({"key1": "value1", "key2": "value2"}, ["key1", "key2"])


def test_listener_type():
    def on_message(msg: Any):
        print(msg)

    listener = ListenerType("message_listener", on_message, group_key="group1")
    assert listener.key == "message_listener"
    assert listener.group_key == "group1"
    listener.listener("Hello")  # Prints "Hello"


def test_icontrol_net_canny_creation():
    control_net_canny = IControlNetCanny(
        model='civitai:38784@44716',
        weight=0.8,
        startStep=2,
        endStep=8,
        guideImage="canny_guide_image.png",
        controlMode=EControlMode.PROMPT,
        lowThresholdCanny=100,
        highThresholdCanny=200,
    )
    assert isinstance(control_net_canny, IControlNetCanny)
    assert isinstance(control_net_canny, IControlNet)
    assert control_net_canny.preprocessor == EPreProcessor.canny
    assert control_net_canny.weight == 0.8
    assert control_net_canny.startStep == 2
    assert control_net_canny.endStep == 8
    assert control_net_canny.guideImage == "canny_guide_image.png"
    assert control_net_canny.controlMode == EControlMode.PROMPT
    assert control_net_canny.lowThresholdCanny == 100
    assert control_net_canny.highThresholdCanny == 200


def test_icontrol_net_hands_and_face_creation():
    control_net_hands_and_face = IControlNetOpenPose(
        preprocessor=EOpenPosePreProcessor.openpose_face,
        weight=0.6,
        startStep=1,
        endStep=9,
        guideImage="hands_face_guide_image_unprocessed.png",
        controlMode=EControlMode.CONTROL_NET,
        includeHandsAndFaceOpenPose=True,
    )
    assert isinstance(control_net_hands_and_face, IControlNetOpenPose)
    assert isinstance(control_net_hands_and_face, IControlNet)
    assert (
        control_net_hands_and_face.preprocessor == EOpenPosePreProcessor.openpose_face
    )
    assert control_net_hands_and_face.weight == 0.6
    assert control_net_hands_and_face.startStep == 1
    assert control_net_hands_and_face.endStep == 9
    assert (
        control_net_hands_and_face.guideImage
        == "hands_face_guide_image_unprocessed.png"
    )
    assert control_net_hands_and_face.controlMode == EControlMode.CONTROL_NET
    assert control_net_hands_and_face.includeHandsAndFaceOpenPose == True


def test_icontrol_net_union():
    control_net_canny = IControlNetCanny(
        model='qatests:68487@08629',
        weight=0.7,
        startStep=3,
        endStep=7,
        guideImage="canny_guide_image.png",
        controlMode=EControlMode.BALANCED,
        lowThresholdCanny=150,
        highThresholdCanny=250,
    )
    control_net_hands_and_face = IControlNetOpenPose(
        preprocessor=EOpenPosePreProcessor.openpose_full,
        weight=0.9,
        startStep=4,
        endStep=6,
        guideImage="hands_face_guide_image_unprocessed.png",
        controlMode=EControlMode.PROMPT,
        includeHandsAndFaceOpenPose=False,
    )
    control_nets = [control_net_canny, control_net_hands_and_face]
    for control_net in control_nets:
        assert isinstance(control_net, IControlNet)
