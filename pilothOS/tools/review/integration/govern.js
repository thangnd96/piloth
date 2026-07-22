'use strict';
/*
 * Piloth governance bridge (OPTIONAL, isolated, fail-soft).
 *
 * This is the ONLY place that knows about Piloth. The annotron-faithful core
 * (server.js/sdk.js/chrome.html) never imports it directly except behind a
 * bound task id, so the core still runs 1:1 and standalone when no Piloth task
 * is attached. Every call here is best-effort: if the guard is missing or
 * errors, we log and continue — governance never breaks the review loop.
 *
 * It maps the tool's structured feedback into the guard's `review-feedback`
 * schema and records reviewer permission decisions as `os-evidence`.
 */
const path = require('path');
const { spawn } = require('child_process');

const GUARD = process.env.PILOTH_GUARD ||
  path.join(__dirname, '..', '..', '..', 'scripts', 'pilothos_guard.py');

const SEVERITIES = new Set(['blocker', 'major', 'minor', 'nit']);
const DISPOSITIONS = new Set(['approve', 'request-changes']);
const VERDICTS = new Set(['approve', 'request-changes', 'reject']);

// Async (non-blocking) so a slow/hung guard never stalls the review loop or SSE.
function runGuard(mode, payload) {
  return new Promise((resolve) => {
    let out = '', err = '';
    let child;
    try {
      child = spawn('python3', [GUARD, mode], { stdio: ['pipe', 'pipe', 'pipe'] });
    } catch (e) {
      return resolve({ ok: false, error: String(e && e.message || e) });
    }
    const timer = setTimeout(() => { try { child.kill(); } catch (e) {} resolve({ ok: false, error: 'timeout' }); }, 15000);
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { err += d; });
    child.on('error', (e) => { clearTimeout(timer); resolve({ ok: false, error: String(e && e.message || e) }); });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) return resolve({ ok: false, error: err.trim() || ('exit ' + code) });
      let parsed = {};
      try { parsed = JSON.parse(out || '{}'); } catch (e) { parsed = { raw: out }; }
      resolve({ ok: true, out: parsed });
    });
    try { child.stdin.write(JSON.stringify(payload)); child.stdin.end(); } catch (e) {}
  });
}

// Read-only guard call that passes the task id as an argv (os-status <task>),
// unlike runGuard which writes a JSON payload to stdin. Fail-soft.
function runGuardArgv(mode, args) {
  return new Promise((resolve) => {
    let out = '', err = '';
    let child;
    try {
      child = spawn('python3', [GUARD, mode, ...args], { stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      return resolve({ ok: false, error: String(e && e.message || e) });
    }
    const timer = setTimeout(() => { try { child.kill(); } catch (e) {} resolve({ ok: false, error: 'timeout' }); }, 8000);
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { err += d; });
    child.on('error', (e) => { clearTimeout(timer); resolve({ ok: false, error: String(e && e.message || e) }); });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) return resolve({ ok: false, error: err.trim() || ('exit ' + code) });
      try { resolve({ ok: true, out: JSON.parse(out || '{}') }); }
      catch (e) { resolve({ ok: false, error: 'bad json' }); }
    });
  });
}

// Read the pipeline/gate view for the bound task straight from the guard's
// os-status (the guard resolves the task id + returns exactly the surfaced
// lifecycle / gates / phase-plan fields). Returns null on any error so the
// stepper simply stays hidden — governance never breaks the review loop.
async function readPipeline(taskId) {
  if (!taskId) return null;
  const res = await runGuardArgv('os-status', [String(taskId)]);
  if (!res.ok || !res.out || res.out.result !== 'os_status') return null;
  const s = res.out;
  return {
    governed: true,
    task_id: s.task_id || '',
    status: s.status || '',
    mode: s.mode || '',
    lifecycle: Array.isArray(s.lifecycle) ? s.lifecycle : [],
    required_gates: Array.isArray(s.required_gates) ? s.required_gates : [],
    requires_prototype: !!s.requires_prototype,
    requires_discovery: !!s.requires_discovery,
    discovery_recorded: !!s.discovery_recorded,
    prototype: s.prototype || {},
    human_review: s.human_review || {},
    phase_plan_suggestion: s.phase_plan_suggestion || {}
  };
}

// Map one tool feedback item → a guard review finding.
function toFinding(item, index, verdict) {
  const severity = SEVERITIES.has(item.severity) ? item.severity : 'minor';
  let disposition = DISPOSITIONS.has(item.disposition)
    ? item.disposition
    : (verdict === 'approve' ? 'approve' : 'request-changes');
  const location = {};
  if (item.source && item.source.file) {
    location.file = item.source.file;
    if (item.source.line != null) location.line = item.source.line;
  }
  if (item.gate) location.gate = item.gate;
  if (!location.file && !location.gate) location.gate = 'scope'; // keep the artifact valid
  return {
    id: item.id || ('f' + (index + 1)),
    location,
    note: item.note || item.label || item.text || '(no note)',
    severity,
    disposition
  };
}

function deriveVerdict(body) {
  if (VERDICTS.has(body.verdict)) return body.verdict;
  const items = Array.isArray(body.items) ? body.items : [];
  const anyChanges = items.some((it) => it.disposition === 'request-changes' ||
    ['blocker', 'major'].includes(it.severity));
  return anyChanges ? 'request-changes' : 'approve';
}

// Record a review round as guard evidence for the human_review gate.
async function recordFeedback(taskId, body) {
  if (!taskId) return { ok: false, error: 'no task' };
  const verdict = deriveVerdict(body);
  const items = Array.isArray(body.items) ? body.items : [];
  const payload = {
    task_id: taskId,
    reviewer: body.reviewer || process.env.USER || '',
    verdict,
    finalized: !!body.finalized,
    message: body.message || '',
    findings: items.map((it, i) => toFinding(it, i, verdict))
  };
  const res = await runGuard('review-feedback', payload);
  if (!res.ok) process.stderr.write('[govern] review-feedback failed: ' + res.error + '\n');
  return res;
}

// Record a reviewer permission decision as an audit evidence entry.
async function recordApproval(taskId, { tool, decision, reason }) {
  if (!taskId) return { ok: false, error: 'no task' };
  const payload = {
    task_id: taskId,
    kind: 'human_review',
    summary: `reviewer ${decision} tool ${tool}` + (reason ? `: ${reason}` : ''),
    tool: tool || '',
    status: decision || '',
    gate: 'human_review'
  };
  const res = await runGuard('os-evidence', payload);
  if (!res.ok) process.stderr.write('[govern] os-evidence (approval) failed: ' + res.error + '\n');
  return res;
}

module.exports = { recordFeedback, recordApproval, readPipeline, GUARD };
