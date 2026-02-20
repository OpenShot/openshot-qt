import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const OutroScene: React.FC<{
  githubUrl: string;
  homepage?: string;
}> = ({githubUrl, homepage}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const ctaProgress = spring({
    frame,
    fps,
    config: {damping: 200},
  });

  const urlProgress = spring({
    frame: frame - 15,
    fps,
    config: {damping: 200},
  });

  const homepageProgress = spring({
    frame: frame - 25,
    fps,
    config: {damping: 200},
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <div style={{textAlign: 'center'}}>
        <h1
          style={{
            fontSize: 72,
            fontWeight: 'bold',
            background: 'linear-gradient(135deg, #667eea 0%, #34d399 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            marginBottom: 50,
            opacity: ctaProgress,
            transform: `scale(${ctaProgress})`,
          }}
        >
          Check it out!
        </h1>

        <p
          style={{
            fontSize: 36,
            color: '#ffffff',
            marginBottom: 20,
            opacity: urlProgress,
            transform: `translateY(${(1 - urlProgress) * 30}px)`,
          }}
        >
          {githubUrl}
        </p>

        {homepage && (
          <p
            style={{
              fontSize: 28,
              color: '#a0aec0',
              opacity: homepageProgress,
              transform: `translateY(${(1 - homepageProgress) * 20}px)`,
            }}
          >
            {homepage}
          </p>
        )}
      </div>
    </AbsoluteFill>
  );
};
