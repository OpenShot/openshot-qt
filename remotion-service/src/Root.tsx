import {Composition, registerRoot} from 'remotion';
import {ProductLaunch} from './templates/ProductLaunch/index';
import type {ProductLaunchProps} from './templates/ProductLaunch/index';

const defaultProps: ProductLaunchProps = {
  repoName: 'Example Project',
  description: 'An amazing open source project',
  stars: 10000,
  forks: 2000,
  language: 'TypeScript',
  features: ['Feature One', 'Feature Two', 'Feature Three'],
  githubUrl: 'github.com/example/project',
  homepage: 'https://example.com',
};

const calculateDuration = ({props}: {props: ProductLaunchProps}) => {
  const fps = 30;
  const introDuration = fps * 3;
  const statsDuration = fps * 4;
  const featuresDuration = props.features.length > 0 ? fps * 4 : 0;
  const outroDuration = fps * 3;
  return {
    durationInFrames: introDuration + statsDuration + featuresDuration + outroDuration,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ProductLaunch"
        component={ProductLaunch as any}
        durationInFrames={14 * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
        calculateMetadata={calculateDuration as any}
      />
    </>
  );
};

registerRoot(RemotionRoot);
