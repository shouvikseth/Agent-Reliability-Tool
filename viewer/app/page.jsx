'use client';
import { useEffect, useMemo, useRef, useState } from 'react';

const number = value => value == null ? '—' : Number(value).toLocaleString('en-US');
const seconds = value => value == null ? '—' : `${value.toFixed(2)} s`;
const title = value => value ? value[0].toUpperCase() + value.slice(1) : '—';
const verdict = row => row.verified ? 'Verified' : row.status === 'submitted' ? 'Check failed' : title(row.status?.replaceAll('_', ' '));
async function get(url, signal) {
  const response = await fetch(url, { signal });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Could not load saved data.');
  return body;
}
function Badge({ children, tone = '' }) { return <span className={`badge ${tone}`}>{children}</span>; }
function Check({ label, result }) {
  return <div className="check"><span>{label}</span><strong className={result ? result.passed ? 'pass-text' : 'fail-text' : 'muted'}>{result ? result.passed ? '✓ Passed' : '× Failed' : 'Not graded'}</strong>{result?.output && <details><summary>Check output</summary><pre>{result.output}</pre></details>}</div>;
}

export default function Page() {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [query, setQuery] = useState(''), [architecture, setArchitecture] = useState('all');
  const [condition, setCondition] = useState('all'), [outcome, setOutcome] = useState('all');
  const [sort, setSort] = useState('order'), [incomplete, setIncomplete] = useState(false);
  const [selected, setSelected] = useState(null), [detail, setDetail] = useState(null), [detailError, setDetailError] = useState('');
  const [events, setEvents] = useState(null), [patch, setPatch] = useState(null);
  const [traceError, setTraceError] = useState(''), [patchError, setPatchError] = useState('');
  const [tab, setTab] = useState('overview'), [eventFilter, setEventFilter] = useState('all');
  const [manifestOpen, setManifestOpen] = useState(false), [manifest, setManifest] = useState(null);
  const dialog = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    get('/api/study', controller.signal).then(body => {
      setData(body);
      const linked = new URLSearchParams(window.location.hash.slice(1)).get('trial');
      setSelected(body.trials.some(t => t.attempt_id === linked) ? linked : body.trials[0]?.attempt_id);
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, []);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.trials || []).filter(t =>
      (!needle || `${t.task} ${t.category} ${t.run_id} ${t.error || ''}`.toLowerCase().includes(needle)) &&
      (architecture === 'all' || t.architecture === architecture) &&
      (condition === 'all' || t.condition === condition) &&
      (outcome === 'all' || (outcome === 'verified' ? t.verified : outcome === 'failed' ? !t.verified && t.status === 'submitted' : t.status === outcome)) &&
      (!incomplete || !t.usage_complete)
    ).sort((a, b) => sort === 'order' ? a.order - b.order : (b[sort] ?? -1) - (a[sort] ?? -1));
  }, [data, query, architecture, condition, outcome, sort, incomplete]);

  function choose(id) {
    setSelected(id);
    if (id) window.history.replaceState(null, '', `#trial=${id}`);
  }
  useEffect(() => {
    if (data && !rows.some(t => t.attempt_id === selected)) choose(rows[0]?.attempt_id || null);
  }, [data, rows, selected]);

  useEffect(() => {
    setDetail(null); setDetailError(''); setEvents(null); setPatch(null); setTraceError(''); setPatchError('');
    if (!selected) return;
    const controller = new AbortController();
    get(`/api/trials/${selected}`, controller.signal).then(body => {
      setDetail(body);
      if (body.available.events) get(`/api/trials/${selected}/events`, controller.signal).then(d => setEvents(d.events)).catch(e => { if (e.name !== 'AbortError') setTraceError(e.message); });
      if (body.available.patch) get(`/api/trials/${selected}/patch`, controller.signal).then(d => setPatch(d.patch)).catch(e => { if (e.name !== 'AbortError') setPatchError(e.message); });
    }).catch(e => { if (e.name !== 'AbortError') setDetailError(e.message); });
    return () => controller.abort();
  }, [selected]);

  useEffect(() => {
    if (manifestOpen) {
      if (!dialog.current?.open) dialog.current?.showModal();
      if (!manifest) get('/api/manifest').then(setManifest).catch(e => setManifest({ error: e.message }));
    } else dialog.current?.close();
  }, [manifestOpen, manifest]);

  function clear() { setQuery(''); setArchitecture('all'); setCondition('all'); setOutcome('all'); setIncomplete(false); setSort('order'); }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ scope: 'filtered_view', export_sha256: data.export_sha256, trials: rows }, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'reliability-trials-filtered.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (error) return <main className="startup"><div className="brand-mark">R</div><h1>Study unavailable</h1><p role="alert">{error}</p><button onClick={() => window.location.reload()}>Try again</button></main>;
  if (!data) return <main className="startup"><div className="brand-mark">R</div><h1>Opening the study</h1><p role="status">Loading recorded outcomes…</p></main>;

  const totals = data.summary.all;
  const current = data.trials.find(t => t.attempt_id === selected);
  const result = detail?.trial.result;
  const filteredEvents = (events || []).filter(e => eventFilter === 'all' || (eventFilter === 'model' ? e.kind === 'model' : eventFilter === 'tools' ? e.kind === 'tool' : e.kind === 'fault_injected'));
  const filteredVerified = rows.filter(t => t.verified).length;
  const activeFilters = query || architecture !== 'all' || condition !== 'all' || outcome !== 'all' || incomplete || sort !== 'order';

  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Agent Reliability Lab home"><span className="brand-mark">R</span><span>RELIABILITY<span className="brand-small">LAB / RESEARCH TOOLS</span></span></a>
      <div className="sidebar-section">WORKSPACE</div>
      <a className="nav-item active" href="#explorer"><span>▤</span> Study explorer <span className="nav-count">216</span></a>
      <button className="nav-item" onClick={() => setManifestOpen(true)}><span>◇</span> Study manifest</button>
      <div className="study-note"><span className="eyebrow">CURRENT STUDY</span><strong>Held-out evaluation</strong><p>Twelve defects.<br />Three control flows.<br />Every outcome retained.</p><Badge tone="teal">● Frozen configuration</Badge></div>
      <div className="sidebar-bottom"><span className="status-dot" /> Read-only workspace<p>No execution or editing controls</p></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumb">Research <span>/</span> Held-out study <span>/</span> <strong>v1</strong></div><Badge>LOCAL VIEWER</Badge></header>
      <main id="explorer">
        <section className="page-heading"><div><div className="eyebrow">EVIDENCE, AT A GLANCE</div><h1>Study explorer<span className="title-dot">.</span></h1><p>Inspect recorded behavior, from the first tool call to the final grade.</p></div><button className="secondary" onClick={() => setManifestOpen(true)}>Study manifest <span>↗</span></button></section>
        <div className="study-meta"><Badge tone="teal">COMPLETED</Badge><span>{data.model}</span><span>12 held-out tasks</span><span>3 repetitions per condition</span><span className="mono">{data.source_commit.slice(0, 7)}</span></div>
        <section className="metrics" aria-label="Whole-study totals">
          <div className="metric"><span>Recorded trials</span><strong>{number(totals.scheduled)}<small>/ {number(totals.scheduled)}</small></strong><p>Every scheduled outcome accounted for</p></div>
          <div className="metric"><span>Verified repairs</span><strong>{number(totals.verified)}<small>{totals.completion_percent.toFixed(1)}%</small></strong><p>Passed defect and regression checks</p></div>
          <div className="metric"><span>Faults triggered</span><strong>{number(totals.faults_triggered)}<small>/ {number(totals.faults_assigned)}</small></strong><p>Assignments and actual exposure differ</p></div>
          <div className="metric"><span>Incomplete usage</span><strong>{number(totals.usage_incomplete_outcomes)}<small>trials</small></strong><p>Uncertainty remains in the record</p></div>
        </section>
        <section className="architecture-strip" aria-label="Architecture outcomes">
          {['fixed', 'single', 'team'].map(a => { const m = data.summary.architectures[a].all; return <button key={a} onClick={() => setArchitecture(architecture === a ? 'all' : a)} aria-pressed={architecture === a} className={`architecture-card ${architecture === a ? 'chosen' : ''}`}><span className={`agent-icon ${a}`}>{a[0].toUpperCase()}</span><span className="architecture-body"><span><strong>{title(a)}</strong><span>{m.verified}/{m.scheduled} verified <b>{m.completion_percent.toFixed(1)}%</b></span></span><span className="progress"><i style={{ width: `${m.completion_percent}%` }} /></span></span></button>; })}
        </section>
        <p className="study-caveat">One small application, twelve authored defects. These outcomes describe this study; they do not establish a general architecture ranking.</p>

        <section className="explorer-card">
          <div className="explorer-header"><div><h2>Trial records <span>{rows.length}</span></h2><p aria-live="polite">{filteredVerified} verified · {rows.length - filteredVerified} unsuccessful in this selection</p></div><button className="text-button" onClick={download}>↓ Export selection</button></div>
          <div className="filters">
            <label className="search"><span className="sr-only">Search trials</span><span aria-hidden="true">⌕</span><input aria-label="Search trials" placeholder="Search task, category, run ID, or error…" value={query} onChange={e => setQuery(e.target.value)} /></label>
            <label>Architecture<select aria-label="Architecture" value={architecture} onChange={e => setArchitecture(e.target.value)}><option value="all">All architectures</option>{['fixed', 'single', 'team'].map(a => <option key={a}>{a}</option>)}</select></label>
            <label>Condition<select aria-label="Condition" value={condition} onChange={e => setCondition(e.target.value)}><option value="all">All conditions</option>{['clean', 'timeout', 'malformed'].map(c => <option key={c}>{c}</option>)}</select></label>
            <label>Outcome<select aria-label="Outcome" value={outcome} onChange={e => setOutcome(e.target.value)}><option value="all">All outcomes</option><option value="verified">Verified</option><option value="failed">Check failed</option><option value="agent_error">Agent error</option><option value="budget_exhausted">Budget exhausted</option><option value="infrastructure_invalid">Infrastructure invalid</option><option value="interrupted">Interrupted</option></select></label>
          </div>
          <div className="filter-secondary"><label className="checkbox"><input type="checkbox" checked={incomplete} onChange={e => setIncomplete(e.target.checked)} /> Incomplete usage only</label><div>{activeFilters && <button className="text-button" onClick={clear}>Clear filters</button>}<label className="sort">Sort by <select aria-label="Sort by" value={sort} onChange={e => setSort(e.target.value)}><option value="order">Schedule order</option><option value="seconds">Longest duration</option><option value="tokens">Most tokens</option></select></label></div></div>
          <div className="split-view">
            <div className="trial-list"><table><thead><tr><th>Task / repetition</th><th>Architecture</th><th>Condition</th><th>Outcome</th></tr></thead><tbody>{rows.map(row => <tr key={row.attempt_id} className={selected === row.attempt_id ? 'selected' : ''} onClick={() => choose(row.attempt_id)}><td><button aria-pressed={selected === row.attempt_id} className="trial-button" onClick={() => choose(row.attempt_id)} aria-label={`Inspect ${row.task}, ${row.architecture}, ${row.condition}, repetition ${row.repetition}`}><strong>{row.task}</strong><span>{row.category} <b>·</b> rep {row.repetition}</span></button></td><td><span className={`agent-label ${row.architecture}`}>{title(row.architecture)}</span></td><td><span className="condition-label">{row.condition === 'clean' ? '○' : 'ϟ'} {row.condition}</span></td><td><span className={`outcome ${row.verified ? 'verified' : row.status === 'submitted' ? 'failed' : 'error'}`}>{row.verified ? '✓ ' : '× '}{verdict(row)}</span><span className="row-time">{seconds(row.seconds)}</span></td></tr>)}</tbody></table>{!rows.length && <div className="empty"><h3>No matching trials</h3><p>Try a different task, condition, or outcome.</p><button className="secondary" onClick={clear}>Clear filters</button></div>}</div>
            <section className="detail-panel" aria-label="Selected trial">
              {!selected ? <div className="empty"><p>Select a trial to inspect its evidence.</p></div> : <>
                <div className="detail-heading"><div className="eyebrow">TRIAL {String(current?.order || '').padStart(3, '0')} / {totals.scheduled}</div><div className="detail-title"><h2>{current?.task}</h2><Badge tone={current?.verified ? 'teal' : 'amber'}>{current && verdict(current)}</Badge></div><p>{title(current?.architecture)} · {current?.condition} · repetition {current?.repetition}</p></div>
                <div className="tabs" onKeyDown={e => {
                  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
                  e.preventDefault();
                  const tabs = ['overview', 'timeline', 'patch'];
                  const index = e.key === 'Home' ? 0 : e.key === 'End' ? 2 : (tabs.indexOf(tab) + (e.key === 'ArrowRight' ? 1 : 2)) % 3;
                  setTab(tabs[index]); document.getElementById(`tab-${tabs[index]}`)?.focus();
                }} role="tablist" aria-label="Trial evidence">{['overview', 'timeline', 'patch'].map(t => <button role="tab" tabIndex={tab === t ? 0 : -1} id={`tab-${t}`} aria-controls="evidence-panel" aria-selected={tab === t} key={t} onClick={() => setTab(t)}>{title(t)}{t === 'timeline' && events && <span>{events.length}</span>}</button>)}</div>
                <div className="detail-content" role="tabpanel" id="evidence-panel" aria-labelledby={`tab-${tab}`}>
                  {detailError ? <div className="notice error-notice" role="alert">{detailError} Published list outcomes remain available.</div> : !detail ? <p className="muted" role="status">Loading saved evidence…</p> : <>
                    {tab === 'overview' && <>
                      <section className="issue"><h3>Reported issue</h3><p>{detail.issue || 'Issue text is unavailable without the optional local manifest. Published outcomes are shown below.'}</p></section>
                      {result?.error && <div className="notice error-notice"><strong>Run stopped</strong><p>{result.error}</p></div>}
                      <h3 className="section-label">INDEPENDENT VERIFICATION</h3><div className="checks"><Check label="Defect check" result={result?.verification?.verifier} /><Check label="Regression check" result={result?.verification?.regression} /></div>
                      <h3 className="section-label">RECORDED RESOURCES</h3><div className="resource-grid"><div><span>Duration</span><strong>{seconds(result?.seconds)}</strong></div><div><span>Reported tokens</span><strong>{number(result?.tokens)}</strong></div><div><span>Model requests</span><strong>{number(result?.model_requests)}</strong></div><div><span>Tool calls</span><strong>{number(result?.tool_calls)}</strong></div></div>
                      {!result?.usage_complete && <div className="notice warning"><strong>Usage is incomplete</strong><p>{number(result?.uncertain_reserved_tokens)} tokens remain reserved with uncertain consumption. This allowance is not measured additional usage.</p></div>}
                      <div className="fact"><span>Fault exposure</span><strong>{current?.condition === 'clean' ? 'Clean condition' : result?.fault_triggered ? 'Assigned · triggered' : 'Assigned · not triggered'}</strong></div>
                      <div className="fact"><span>API fees</span><strong>{result?.dollars == null ? 'Unknown' : `$${result.dollars.toFixed(2)}`}</strong></div>
                      <p className="fine-print">Local API fees exclude hardware and electricity. Duration includes grading when submitted.</p>
                      <h3 className="section-label">PROVENANCE</h3><div className="provenance"><span>Run ID</span><code>{result?.id || 'No final run artifact'}</code><span>Model</span><code>{result?.provider?.model || '—'}</code><span>Result integrity</span><strong>{detail.integrity === 'result_hash_matched' ? '✓ Matches published SHA-256' : 'Published record only'}</strong></div>
                    </>}
                    {tab === 'timeline' && <>
                      <div className="trace-filters" aria-label="Timeline filter">{['all', 'model', 'tools', 'faults'].map(f => <button key={f} aria-pressed={eventFilter === f} onClick={() => setEventFilter(f)}>{title(f)}</button>)}</div>
                      {!detail.available.events ? <div className="empty"><h3>Local trace unavailable</h3><p>This checkout has published outcomes but no matching local trace file. No model work is run by this viewer.</p></div> : traceError ? <p role="alert">{traceError}</p> : !events ? <p role="status">Loading visible trace…</p> : <div className="timeline">{filteredEvents.length === 0 && <p className="muted">No events in this category.</p>}{filteredEvents.map(e => <details key={e.index} className={`event ${e.kind === 'fault_injected' ? 'fault-event' : ''}`}><summary><span className="event-dot" /><span><strong>{e.kind === 'model' ? `${title(e.role)} response` : e.kind === 'tool' ? `Tool · ${e.name}${e.arguments?.path ? ` ${e.arguments.path}` : ''}` : e.kind.replaceAll('_', ' ')}</strong>{e.kind === 'model' && <small>{e.response?.text || 'No visible status text'}</small>}</span><time>+{Number.isFinite(e.time) && Number.isFinite(events[0]?.time) ? (e.time - events[0].time).toFixed(2) : '—'}s</time></summary><pre>{JSON.stringify(e, null, 2)}</pre></details>)}</div>}
                      <p className="fine-print">Visible model status, tools, faults, and accounting only. Raw request payloads are not served. {detail.artifact_note}</p>
                    </>}
                    {tab === 'patch' && <>{!detail.available.patch ? <div className="empty"><h3>Local patch unavailable</h3><p>The saved patch is optional and is not included in the published outcome export.</p></div> : patchError ? <p role="alert">{patchError}</p> : patch === null ? <p role="status">Loading saved patch…</p> : patch === '' ? <div className="empty"><h3>No source changes</h3><p>This trial left the candidate unchanged.</p></div> : <div className="diff" aria-label="Recorded patch">{patch.split('\n').map((line, i) => <div key={i} className={line.startsWith('+') && !line.startsWith('+++') ? 'line-add' : line.startsWith('-') && !line.startsWith('---') ? 'line-remove' : line.startsWith('@@') ? 'line-hunk' : ''}><span aria-hidden="true">{i + 1}</span><code>{line || ' '}</code></div>)}</div>}<p className="fine-print">Read-only recorded diff. {detail.artifact_note}</p></>}
                  </>}
                </div>
              </>}
            </section>
          </div>
        </section>
        <footer><span>AGENT RELIABILITY LAB <b>/</b> A record of what happened.</span><span>Local artifacts · No rerun or edit actions</span></footer>
      </main>
    </div>
    <dialog ref={dialog} onCancel={() => setManifestOpen(false)}><div className="dialog-heading"><div><div className="eyebrow">FROZEN STUDY</div><h2>Study manifest</h2></div><button className="secondary" onClick={() => setManifestOpen(false)} aria-label="Close manifest">Close ×</button></div><p className="fine-print">Source, task fingerprints, configuration, schedule, and observed preflight metadata.</p><pre>{manifest ? JSON.stringify(manifest, null, 2) : 'Loading manifest…'}</pre></dialog>
  </div>;
}
