import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const IntroScene: React.FC<{
  name: string;
  description: string;
  githubUrl: string;
}> = ({name, description, githubUrl}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Smooth spring animations
  const titleProgress = spring({
    frame,
    fps,
    config: {damping: 200},
  });

  const descProgress = spring({
    frame: frame - 15,
    fps,
    config: {damping: 200},
  });

  const urlProgress = spring({
    frame: frame - 30,
    fps,
    config: {damping: 200},
  });

  // Fade out at end
  const fadeOut = interpolate(frame, [fps * 2.5, fps * 3], [1, 0], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
        opacity: fadeOut,
      }}
    >
      <div style={{textAlign: 'center', maxWidth: '80%'}}>
        {/* Title */}
        <h1
          style={{
            fontSize: 80,
            fontWeight: 'bold',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            margin: 0,
            opacity: titleProgress,
            transform: `translateY(${(1 - titleProgress) * 50}px)`,
          }}
        >
          {name}
        </h1>

        {/* Description */}
        <p
          style={{
            fontSize: 32,
            color: '#a0aec0',
            marginTop: 30,
            opacity: descProgress,
            transform: `translateY(${(1 - descProgress) * 30}px)`,
          }}
        >
          {description}
        </p>

        {/* GitHub URL */}
        <p
          style={{
            fontSize: 24,
            color: '#48bb78',
            marginTop: 40,
            opacity: urlProgress,
            transform: `translateY(${(1 - urlProgress) * 20}px)`,
          }}
        >
          {githubUrl}
        </p>
      </div>
    </AbsoluteFill>
  );
};
