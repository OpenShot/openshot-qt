import express from 'express';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import path from 'path';
import fs from 'fs';

const app = express();
app.use(express.json({limit: '10mb'}));

const PORT = 3100;
const OUTPUT_DIR = path.join(__dirname, '../../output');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, {recursive: true});
}

// Health check
app.get('/health', (_req, res) => {
  res.json({status: 'ok', service: 'remotion-render-api'});
});

// Render endpoint
app.post('/render/product-launch', async (req, res) => {
  try {
    const {
      repoName,
      description,
      stars,
      forks,
      language,
      features = [],
      githubUrl,
      homepage,
    } = req.body;

    console.log(`[Remotion] Starting render for: ${repoName}`);

    // Bundle the Remotion project
    const bundleLocation = await bundle({
      entryPoint: path.join(__dirname, '../Root.tsx'),
      webpackOverride: (config) => config,
    });

    console.log(`[Remotion] Bundle created at: ${bundleLocation}`);

    // Get composition
    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: 'ProductLaunch',
      inputProps: {
        repoName,
        description,
        stars,
        forks,
        language,
        features,
        githubUrl,
        homepage,
      },
    });

    console.log(`[Remotion] Composition selected: ${composition.id}`);

    // Output file path
    const outputFileName = `product_launch_${Date.now()}.mp4`;
    const outputPath = path.join(OUTPUT_DIR, outputFileName);

    // Render video
    console.log(`[Remotion] Rendering to: ${outputPath}`);
    await renderMedia({
      composition,
      serveUrl: bundleLocation,
      codec: 'h264',
      outputLocation: outputPath,
      inputProps: {
        repoName,
        description,
        stars,
        forks,
        language,
        features,
        githubUrl,
        homepage,
      },
      concurrency: 4, // Fast parallel rendering
    });

    console.log(`[Remotion] Render complete: ${outputPath}`);

    // Return success
    res.json({
      success: true,
      outputPath: outputPath,
      fileName: outputFileName,
      duration: composition.durationInFrames / composition.fps,
    });
  } catch (error: any) {
    console.error('[Remotion] Render error:', error);
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.listen(PORT, () => {
  console.log(`[Remotion API] Server running on http://localhost:${PORT}`);
  console.log(`[Remotion API] Output directory: ${OUTPUT_DIR}`);
});
