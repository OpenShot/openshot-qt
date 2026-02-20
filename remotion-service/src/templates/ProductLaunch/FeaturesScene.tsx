import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';

const FeatureItem: React.FC<{
  text: string;
  index: number;
}> = ({text, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const progress = spring({
    frame: frame - index * 8,
    fps,
    config: {damping: 200},
  });

  return (
    <div
      style={{
        fontSize: 32,
        color: '#e2e8f0',
        marginBottom: 20,
        opacity: progress,
        transform: `translateX(${(1 - progress) * 100}px)`,
      }}
    >
      <span style={{color: '#34d399', marginRight: 15}}>●</span>
      {text}
    </div>
  );
};

export const FeaturesScene: React.FC<{
  features: string[];
}> = ({features}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const titleProgress = spring({
    frame,
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
      <div style={{maxWidth: '70%'}}>
        <h2
          style={{
            fontSize: 48,
            fontWeight: 'bold',
            color: '#2dd4bf',
            marginBottom: 60,
            opacity: titleProgress,
            transform: `translateY(${(1 - titleProgress) * 30}px)`,
          }}
        >
          Key Features
        </h2>

        <div>
          {features.slice(0, 3).map((feature, i) => (
            <FeatureItem key={i} text={feature} index={i} />
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
