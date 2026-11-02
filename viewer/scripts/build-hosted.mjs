import { spawnSync } from 'node:child_process';
import { exportHosted } from './export-hosted.mjs';
console.log(`Exported ${await exportHosted()} published trial outcomes.`);
const build = spawnSync(process.execPath, ['node_modules/next/dist/bin/next', 'build'], {
  stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_VIEWER_MODE: 'static' },
});
process.exit(build.status ?? 1);
