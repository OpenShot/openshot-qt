import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

const formatNumber = (num: number): string => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
};

const AnimatedCounter: React.FC<{
  value: number;
  label: string;
  icon: string;
  color: string;
  delay: number;
}> = ({value, label, icon, color, delay}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const progress = spring({
    frame: frame - delay,
    fps,
    config: {damping: 200},
  });

  const currentValue = Math.floor(interpolate(progress, [0, 1], [0, value]));

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        opacity: progress,
        transform: `scale(${progress})`,
      }}
    >
      <div style={{fontSize: 60, marginBottom: 10}}>{icon}</div>
      <div style={{fontSize: 24, color: '#a0aec0', marginBottom: 5}}>{label}</div>
      <div style={{fontSize: 56, fontWeight: 'bold', color}}>
        {formatNumber(currentValue)}
      </div>
    </div>
  );
};

export const StatsScene: React.FC<{
  stars: number;
  forks: number;
  language: string;
}> = ({stars, forks, language}) => {
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
      <h2
        style={{
          fontSize: 48,
          fontWeight: 'bold',
          color: '#fbbf24',
          marginBottom: 80,
          opacity: titleProgress,
          transform: `translateY(${(1 - titleProgress) * 30}px)`,
        }}
      >
        Repository Stats
      </h2>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-around',
          width: '80%',
          maxWidth: 1200,
        }}
      >
        <AnimatedCounter value={stars} label="Stars" icon="⭐" color="#fbbf24" delay={10} />
        <AnimatedCounter value={forks} label="Forks" icon="🔀" color="#60a5fa" delay={20} />
        <AnimatedCounter value={0} label={language} icon="💻" color="#34d399" delay={30} />
      </div>
    </AbsoluteFill>
  );
};
