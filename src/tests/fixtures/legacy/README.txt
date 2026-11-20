Controlled OpenShot 1.x project fixtures

openshot-1.4.3/ contains an additional REAL application-saved project, generated
with the official 1.4.3 PPA package in an isolated historical Ubuntu container.
It samples animated geometry, effects, mute/hide, volume, fades, transitions,
markers, and project settings. See its README.txt for provenance, reproduction,
the original native-save hash, and current modern conversion limitations.
The descriptions below apply to the older synthetic fixtures in THIS folder.

project-v1-protocol0.osp and project-v1-protocol2.osp are generated from the
bundled legacy class definitions using historical classes.* module names.
Protocol 0 exercises copy_reg._reconstructor and __builtin__.object; protocol 2
exercises NEWOBJ. project-v1-inst.osp uses Python 2 old-style INST opcodes.
These are controlled compatibility fixtures, not archived projects authored by
an actual historical OpenShot release. They contain NO executable payloads.

generate.py reproduces all fixtures and the small PPM image. Run it in a
separate Python process with PYTHONPATH=src from the repository root. The fixtures
cover media, folders, sequences, tracks, clips, fades, transition, effect,
keyframe and marker records, plus shared references and cycles. Tests also
rewrite aliases to openshot.classes.* and current compatibility module names.
Media paths are relative to this folder. Tests copy fixtures into temporary
folders and use that folder as the working directory for conversion.

project-v1-obj.osp reproduces the OBJ instance representation and shared
video_fade_amount/audio_fade_amount fields observed in a real historical
1.x project. Its contents remain generated, free of customer data. Active fades
are normalized to the newer direction-specific fields; inactive fade amounts
need not exist. Explicit direction-specific amounts take precedence.

The shared-schema fixtures intentionally use different video (0.5s) and audio
(0.25s) fades. project-v1-audio-only.osp disables video fades entirely. These
catch the old converter's accidental use of video durations for audio fades.
