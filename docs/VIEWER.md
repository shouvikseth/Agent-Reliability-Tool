# Read-only study viewer

## Host the results on Vercel

The hosted version is a static snapshot of the committed report. It includes all 216 outcomes, grades, resource records, filtering, selection downloads, and the study manifest. Optional local traces, patches, issue manifests, model requests, credentials, and run workspaces are not copied. The existing loopback Python server remains for local evidence inspection; do not expose it publicly.

Import `shouvikseth/Agent-Reliability-Tool` into Vercel using branch `codex/reliability-lab`. Set **Root Directory** to `viewer` and enable **Include source files outside of the Root Directory in the Build Step**, because the exporter reads the committed `docs/studies/heldout-v1-results.json` one directory above. Use Node 22.x. Select the **Other** framework preset: the checked-in `viewer/vercel.json` disables framework runtime adaptation (`framework: null`), installs with `npm ci`, builds with `npm run build:hosted`, and serves `out` as static files. Selecting the Next.js adapter with an `out` override causes it to look for runtime manifests in the exported static directory. No environment variables, API keys, Python, Docker, database, or model server are required for hosting.

Set the project's production branch to `codex/reliability-lab` if Vercel initially selects the repository default. Future pushes on that branch can redeploy the snapshot. Vercel serves only the static output, not the repository or ignored run folders. Docker/Ollama study execution remains local.

To check the hosted build locally, run `npm --prefix viewer run build:hosted`, then serve `viewer/out` with a static HTTP server. A normal `npm --prefix viewer run build` restores the frontend's local API mode. Generated published data under `viewer/public/study` is ignored and regenerated for each hosted build.

The build and root-directory settings follow [Vercel's build configuration guide](https://vercel.com/docs/builds/configure-a-build); the viewer uses [Next.js static export](https://nextjs.org/docs/app/guides/static-exports).

The viewer explores the completed 216-trial held-out study using the published result export and optional local run artifacts. It displays task and condition filters, architecture outcomes, independent grades, visible trace events, recorded patches, resource usage, and the frozen study manifest. It has no execution or editing endpoints.

## Build and launch on Windows

From the repository root, build once with Node/npm. The verified build used Node 22.20.0, Next.js 16.4.3, and React 19.3.1. Exact dependencies are pinned in `viewer/package.json` and `viewer/package-lock.json`.

```powershell
cd viewer
npm ci
npm run build
cd ..
.\.venv\Scripts\python viewer/server.py
```

Open [the local viewer](http://127.0.0.1:8765). Stop it with Ctrl+C in its PowerShell window. Rebuild after changing frontend source. The Python server uses only the standard library; viewing saved data does not require model generation or running Docker. It serves the [Next.js static export](https://nextjs.org/docs/app/guides/static-exports), so a Next.js development server is not needed for normal use.

Optional server arguments:

```powershell
.\.venv\Scripts\python viewer/server.py --port 8766 --export docs/studies/heldout-v1-results.json --study-directory runs/heldout-v1
```

The default export is the committed result JSON. The default optional artifact directory is `runs/heldout-v1`. A fresh clone without the ignored `runs/` files still shows all published outcomes, grading, usage, and manifest data. Issue text, timeline, and patch availability are explicitly marked when local artifacts are missing. An empty saved diff is shown as no source changes, not as a missing patch.

This viewer is a repository utility outside the frozen `lab/` runtime. Starting it neither changes the study configuration nor adds ledger attempts. The frontend build and dependencies stay in ignored `viewer/out`, `.next`, and `node_modules` directories.

## Inspect the evidence

- Whole-study totals distinguish 111 verified repairs, 63 triggered faults out of 108 assignments, and six incomplete usage records. Architecture cards filter the trial list without replacing the whole-study totals.
- Search task/category/run ID/error text; combine architecture, condition, outcome, and incomplete-usage filters. Sort by schedule, duration, or reported tokens. Counts and selection exports describe the filtered rows.
- Select a trial to inspect its reported issue, separate defect and regression checks, error, duration, tokens, model requests, tool calls, fault exposure, and provenance. Unsubmitted attempts show checks as not graded.
- The timeline separates visible model responses, tools, fault injection, and accounting events. Expand an event for its saved data. Raw model request payloads and unrecognized/private model-response fields are not served.
- The patch tab displays escaped, read-only diff text. Keyboard users can navigate evidence tabs with arrows, Home, and End. Trial buttons and filters have explicit accessible names.
- Export selection downloads summary rows for the current filter as JSON, including the source export hash. It does not export raw requests or change the server. A trial URL fragment links to the selected slot; filters reset on reload.

## Read-only API

| GET endpoint | Response |
| --- | --- |
| `/api/study` | Whole-study aggregates, architecture aggregates, and 216 summary rows |
| `/api/manifest` | The frozen study manifest from the published export |
| `/api/trials/<slot-id>` | Published outcome, optional issue text, availability, and result integrity |
| `/api/trials/<slot-id>/events` | An allowlisted projection of local visible events |
| `/api/trials/<slot-id>/patch` | Saved local diff text |

Filters operate in the browser over the finite published list. There are no arbitrary path or query execution endpoints. GET and HEAD are supported; write methods return 405. The service binds only to IPv4 loopback, accepts local Host headers and local same-origin requests, and sends no permissive CORS headers. Do not expose it through a public proxy; this is a local utility without user authentication.

Trial IDs and artifact path components must be hexadecimal IDs. Artifacts are resolved within the configured study directory; traversal and escaping symlinks are rejected. Local `result.json` must match the SHA-256 in its published outcome before local evidence is returned. A mismatch returns a conflict rather than silently presenting that data. Trace and patch files are labeled as local artifacts: their own hashes were not included in the published export, so a matching result does not independently authenticate those files.

The server never imports candidate application code. Files are bounded to 16 MiB per read, and trace event fields are restricted. Text and diffs render as React text, not HTML. Static files are served only from the built output without directory listing. No endpoint serves raw `requests/` files or arbitrary host paths, and there are no credential-loading, editing, or rerun controls. Saved visible text is served as recorded; use trusted study exports. These controls support local inspection; they do not make this a hosted multi-user service.

## Verification

All **116 tests passed** with Docker integration enabled. Seven viewer tests cover saved data and missing optional artifacts, visible-event projection, result/manifest/path conflicts, unknown IDs, loopback binding, same-origin checks, write-method rejection, traversal rejection, static serving, and unchanged input files after HTTP requests. The production Next.js build passed.

Browser QA against the actual study checked:

| Interaction | Observed result |
| --- | --- |
| Initial study | 216 trials, 111 verified, 63/108 faults, six incomplete records |
| Fixed architecture | 72 trial rows |
| Fixed + malformed + failed | Six rows; failed defect check and passed regression check visible |
| Fault timeline | Injection event visible; nonmatching event types filtered out |
| Patch | Saved diff rendered as text |
| Incomplete usage only | Six single-agent records with retained reservation amounts |
| Impossible search | Zero rows with clear-filter recovery |
| Longest duration | Team heldout-08, repetition 2, 51.61 seconds first |
| Manifest dialog | Opened and closed successfully |
| Export selection | Downloaded JSON contained exactly the six filtered incomplete records |
| Evidence-tab keyboard navigation | Arrow and End keys selected the expected tabs |
| 375px mobile and 1440px desktop | Responsive layouts with no page-wide horizontal overflow |
| Browser console | No errors or warnings observed |

All 216 local result hashes matched after QA, and the frozen runtime still passed its source-fingerprint check. No model requests or study attempts were started. The preview server is temporary; use the launch command above to open the viewer again.
