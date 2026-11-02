// Publish only the committed report. Never inspect ignored run artifacts or credentials.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

export async function exportHosted(destination = new URL('../public/study/', import.meta.url)) {
  const raw = await readFile(new URL('../../docs/studies/heldout-v1-results.json', import.meta.url));
  const data = JSON.parse(raw);
  if (data.schema !== 'heldout-report-v1') throw new Error('Unsupported report schema');
  const categories = Object.fromEntries(data.manifest.design.tasks.map(t => [t.task, t.category]));
  const ids = new Set();
  const trials = data.trials.map((trial, index) => {
    if (!/^[a-f0-9]{32}$/.test(trial.attempt_id) || ids.has(trial.attempt_id)) throw new Error('Invalid trial ID');
    ids.add(trial.attempt_id);
    const result = trial.result || {};
    return {
      ...Object.fromEntries(['attempt_id', 'execution_id', 'task', 'architecture', 'condition', 'repetition'].map(k => [k, trial[k]])),
      order: index + 1, category: categories[trial.task] || '', run_id: result.id ?? null,
      status: result.status ?? trial.outcome, verified: result.verified_completion ?? false,
      fault_triggered: result.fault_triggered ?? false, usage_complete: result.usage_complete ?? false,
      seconds: result.seconds ?? null, tokens: result.tokens ?? null,
      model_requests: result.model_requests ?? null, error: result.error ?? null,
    };
  });
  await mkdir(new URL('trials/', destination), { recursive: true });
  const save = (name, value) => writeFile(new URL(name, destination), JSON.stringify(value));
  await save('study.json', {
    schema: 'viewer-v1', summary: data.summary, trials,
    source_commit: data.manifest.source_commit,
    export_sha256: createHash('sha256').update(raw).digest('hex'),
    model: data.manifest.design.configuration.provider_expected.model,
    local_artifacts_present: false, hosting: 'static',
  });
  await save('manifest.json', data.manifest);
  for (const trial of data.trials) await save(`trials/${trial.attempt_id}.json`, {
    trial, issue: null, available: { events: false, patch: false },
    integrity: 'local_result_unavailable',
    artifact_note: 'Hosted copy contains the committed outcome report only. Local traces and patches are not published.',
  });
  return trials.length;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  console.log(`Exported ${await exportHosted()} published trial outcomes.`);
}
