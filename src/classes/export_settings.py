"""Writer configuration shared by the export dialog and agent worker."""
import openshot


def configure_writer(writer, video, audio, mode='video_audio', quality_mode=None,
                     video_options=None, audio_options=None):
    if mode in ('video_audio', 'video', 'image_sequence'):
        writer.SetVideoOptions(True, video['vcodec'],
                               openshot.Fraction(video['fps']['num'], video['fps']['den']),
                               video['width'], video['height'],
                               openshot.Fraction(video['pixel_ratio']['num'], video['pixel_ratio']['den']),
                               video['interlace'], video['topfirst'], video['video_bitrate'])
    if mode in ('video_audio', 'audio'):
        writer.SetAudioOptions(True, audio['acodec'], audio['sample_rate'], audio['channels'],
                               audio['channel_layout'], audio['audio_bitrate'])
    writer.PrepareStreams()
    if video.get('spherical'):
        writer.AddSphericalMetadata('equirectangular', 0.0, 0.0, 0.0)
    stream = openshot.AUDIO_STREAM if mode == 'audio' else openshot.VIDEO_STREAM
    writer.SetOption(stream, 'muxing_preset', 'mp4_faststart')
    if mode != 'audio':
        if quality_mode in ('crf', 'cqp', 'qp'):
            writer.SetOption(openshot.VIDEO_STREAM, quality_mode, str(int(video['video_bitrate'])))
        if video['vcodec'].lower() in ('libx264', 'libx265', 'libvpx-vp9'):
            for name, value in [('g', '48'), ('allow_b_frames', '1'), ('max_b_frames', '3')]:
                writer.SetOption(openshot.VIDEO_STREAM, name, value)
    for stream, values in [(openshot.VIDEO_STREAM, video_options), (openshot.AUDIO_STREAM, audio_options)]:
        for key, value in (values or {}).items():
            writer.SetOption(stream, key, str(value))
