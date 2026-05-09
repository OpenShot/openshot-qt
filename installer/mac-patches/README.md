# Mac patches for OpenShot upstream

These patches apply to OpenShot's upstream `libopenshot` and `libopenshot-audio`
repositories at tag `v0.5.0`. They are required for zenvi-core to build and
run on macOS 26 / Apple Silicon / FFmpeg 8.

Apply via `scripts/build-mac-libopenshot.sh`, which clones the upstream repos,
applies these patches, and builds against Homebrew's qt@5 + libomp.

## Patches

### `libopenshot-audio-v0.5.0-mac.patch`

**File:** `CMakeLists.txt`

Removes the `-framework AGL` linker flag. AGL (Apple Graphics Library) was
deprecated in macOS 10.9 and removed entirely in macOS 10.14 — it is absent
from any modern macOS SDK. JUCE's old build configuration still references it.
Linking succeeds without it on macOS 11+.

### `libopenshot-v0.5.0-mac.patch`

Five files, four logical fixes:

#### Fix 1: Drop `avresample` from FFmpeg detection (`cmake/Modules/FindFFmpeg.cmake`, `src/CMakeLists.txt`)

`libavresample` was removed from FFmpeg in version 5. Modern FFmpeg uses
`libswresample` for the same job. libopenshot's `FindFFmpeg.cmake` still listed
`avresample` as a required component — this caused configure to fail before
compile started.

#### Fix 2: `FF_PROFILE_*` → `AV_PROFILE_*` (`src/FFmpegWriter.cpp`)

FFmpeg 8 renamed the H.264 profile macros (`FF_PROFILE_H264_BASELINE` →
`AV_PROFILE_H264_BASELINE`, etc.). The numeric values are unchanged.

#### Fix 3: `av_stream_add_side_data()` no-op (`src/FFmpegWriter.cpp`)

Function removed in FFmpeg 7. libopenshot used it to attach spherical-video
side data to streams during write. Replaced with `(void)0` — the data flow
path doesn't actually depend on the stored side data being readable.

#### Fix 4: `AVStream::nb_side_data` → `codecpar->nb_coded_side_data` (`src/FFmpegReader.cpp`)

These fields moved from `AVStream` to its `codecpar` (codec parameters)
sub-struct in FFmpeg 7. Used when reading display-matrix rotation metadata.

#### Fix 5: SWR channel layout for FFmpeg 8 (`src/FFmpegReader.cpp`, `src/FrameMapper.cpp`)

The most impactful runtime fix. FFmpeg 8 replaced the legacy `channel_layout`
(uint64) field with a new `AVChannelLayout` struct, accessed via `codecpar->ch_layout`.
The old `av_opt_set_int(swr, "in_channel_layout", X, 0)` calls are silently
ignored on FFmpeg 8 — `swr_init()` then fails with:

```
[SWR] input channel layout "" is invalid or unsupported.
[SWR] Context has not been initialized
```

Without functional audio resampling, libopenshot's playback clock never starts
and **the video preview stays black** even though the file is decoded
successfully. This was the reason for "timeline doesn't work / nothing plays /
black preview" on macOS even with the v1.0.136 source-level cache fixes.

The fix uses `av_opt_set_chlayout` with properly-initialized `AVChannelLayout`
structs (defaulting to stereo when the codecpar layout arrives empty for some
H.264/AAC streams). Guarded by `#if HAVE_CH_LAYOUT` for back-compat with
FFmpeg 4-6.

## Upstreaming

These patches should eventually go to OpenShot upstream. Until then they live
here and are applied at build time. Tag-locked to `v0.5.0` — re-evaluate when
upgrading libopenshot.
