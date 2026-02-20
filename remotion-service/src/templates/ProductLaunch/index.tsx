import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {IntroScene} from './IntroScene';
import {StatsScene} from './StatsScene';
import {FeaturesScene} from './FeaturesScene';
import {OutroScene} from './OutroScene';

export interface ProductLaunchProps {
  repoName: string;
  description: string;
  stars: number;
  forks: number;
  language: string;
  features: string[];
  githubUrl: string;
  homepage?: string;
}

export const ProductLaunch: React.FC<ProductLaunchProps> = ({
  repoName,
  description,
  stars,
  forks,
  language,
  features,
  githubUrl,
  homepage,
}) => {
  const {fps} = useVideoConfig();

  // Scene durations (in frames)
  const introDuration = fps * 3;      // 3 seconds
  const statsDuration = fps * 4;      // 4 seconds
  const featuresDuration = fps * 4;   // 4 seconds
  const outroDuration = fps * 3;      // 3 seconds

  return (
    <AbsoluteFill style={{backgroundColor: '#0f0f0f'}}>
      {/* Intro: 0-90 frames */}
      <Sequence from={0} durationInFrames={introDuration}>
        <IntroScene name={repoName} description={description} githubUrl={githubUrl} />
      </Sequence>

      {/* Stats: 90-210 frames */}
      <Sequence from={introDuration} durationInFrames={statsDuration}>
        <StatsScene stars={stars} forks={forks} language={language} />
      </Sequence>

      {/* Features: 210-330 frames (if any) */}
      {features.length > 0 && (
        <Sequence from={introDuration + statsDuration} durationInFrames={featuresDuration}>
          <FeaturesScene features={features} />
        </Sequence>
      )}

      {/* Outro: 330-420 frames */}
      <Sequence
        from={introDuration + statsDuration + (features.length > 0 ? featuresDuration : 0)}
        durationInFrames={outroDuration}
      >
        <OutroScene githubUrl={githubUrl} homepage={homepage} />
      </Sequence>
    </AbsoluteFill>
  );
};
