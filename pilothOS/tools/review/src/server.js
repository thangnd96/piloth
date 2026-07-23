'use strict';
/*
 * Piloth Review server — a faithful, zero-dependency reimplementation of
 * annotron's coordination server. Node built-ins only (http/fs/path/crypto/url/
 * os/child_process). It is a PASSIVE service: Claude Code (running externally)
 * pushes hook events here and polls /poll for feedback; the browser annotates
 * and receives live updates over SSE. The server never spawns the agent.
 *
 * Design DNA (kept 1:1 with annotron): zero runtime dependency, disk files stay
 * clean (SDK injected at serve time), loopback-only, fail-open hooks.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const url = require('url');
const os = require('os');
const { execSync } = require('child_process');
const { renderMarkdown } = require('./mdRender');

const PORT = parseInt(process.env.REVIEW_PORT || '7321', 10);
const HOST = process.env.REVIEW_HOST || '127.0.0.1';
const SDK_PATH = path.join(__dirname, 'sdk.js');
const CHROME_PATH = path.join(__dirname, 'chrome.html');

const sessions = new Map();   // canonical file path -> session
const allowList = new Set();  // registered canonical paths
const watchIntervals = new Map();

// ---------- helpers ----------
function isMarkdown(p) { return /\.(md|markdown)$/i.test(p); }
function canon(p) { return path.resolve(p); }

function send(res, code, body, headers) {
  const h = Object.assign({ 'Cache-Control': 'no-store' }, headers || {});
  if (typeof body === 'string') {
    if (!h['Content-Type']) h['Content-Type'] = 'text/plain; charset=utf-8';
    res.writeHead(code, h);
    res.end(body);
  } else {
    h['Content-Type'] = 'application/json; charset=utf-8';
    res.writeHead(code, h);
    res.end(JSON.stringify(body));
  }
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = '';
    req.on('data', (c) => { data += c; if (data.length > 40 * 1024 * 1024) req.destroy(); });
    req.on('end', () => resolve(data));
    req.on('error', () => resolve(data));
  });
}

async function readJSON(req) {
  const raw = await readBody(req);
  if (!raw) return {};
  try { return JSON.parse(raw); } catch (e) { return {}; }
}

function getSession(file) {
  if (!sessions.has(file)) {
    sessions.set(file, {
      hash: null,
      sseClients: new Set(),
      pollWaiters: [],
      pendingFeedback: null,
      finalized: false,
      working: false,
      cancelRequested: false,
      remoteApprove: false,
      autoAllowTools: new Set(),
      permWaiters: new Map(),
      pendingPerms: new Map(),
      _suppressReload: false,
      pilothTask: null            // bound Piloth OS task id (governance is off when null)
    });
  }
  return sessions.get(file);
}

function sidecarPath(file) {
  const ext = path.extname(file);
  return file.slice(0, file.length - ext.length) + '.annotron.json';
}
function uploadsDir(file) {
  return path.join(path.dirname(file), '.annotron-uploads');
}

function readSidecar(file) {
  try {
    const raw = fs.readFileSync(sidecarPath(file), 'utf8');
    const j = JSON.parse(raw);
    if (!Array.isArray(j.annotations)) j.annotations = [];
    if (!Array.isArray(j.rounds)) j.rounds = [];
    return j;
  } catch (e) {
    return { version: 1, annotations: [], rounds: [] };
  }
}
function writeSidecar(file, data) {
  fs.writeFileSync(sidecarPath(file), JSON.stringify(data, null, 2), 'utf8');
}

function hashFile(file) {
  try { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
  catch (e) { return null; }
}

function broadcastSSE(file, event, data) {
  const sess = sessions.get(file);
  if (!sess) return;
  const msg = `event: ${event}\ndata: ${data}\n\n`;
  for (const res of sess.sseClients) { try { res.write(msg); } catch (e) {} }
}

function wakePoll(file, payload) {
  const sess = sessions.get(file);
  if (!sess) return;
  const waiters = sess.pollWaiters;
  sess.pollWaiters = [];
  for (const resolve of waiters) { try { resolve(payload); } catch (e) {} }
}

function permJSON(decision, reason) {
  return JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: decision,      // 'allow' | 'deny' | 'ask'
      permissionDecisionReason: reason || ''
    }
  });
}

function watchFile(file) {
  if (watchIntervals.has(file)) return;
  let lastHash = hashFile(file);
  const iv = setInterval(() => {
    const h = hashFile(file);
    if (h && h !== lastHash) {
      lastHash = h;
      const sess = sessions.get(file);
      if (!sess) return;
      if (sess._suppressReload) { sess._suppressReload = false; return; }
      broadcastSSE(file, 'reload', '{}');
    }
  }, 800);
  if (iv.unref) iv.unref();
  watchIntervals.set(file, iv);
}

function findActiveSession(cwd) {
  // Resolve the session a hook event belongs to. Prefer a session whose file
  // lives under cwd; among several under the same cwd, prefer a live, non-final
  // one, then a non-cancelled one, so a lingering cancelled review does not
  // hijack a fresh review in the same directory. Falls back to any active/first.
  const c = cwd ? canon(cwd) : null;
  const underCwd = [];
  let activeFallback = null;
  for (const [file, sess] of sessions) {
    if (c && file.startsWith(c)) underCwd.push([file, sess]);
    if (sess.sseClients.size > 0 || sess.working) activeFallback = [file, sess];
  }
  if (underCwd.length) {
    const live = underCwd.find(([, s]) => !s.finalized && (s.working || s.sseClients.size > 0));
    const fresh = underCwd.find(([, s]) => !s.finalized && !s.cancelRequested);
    return live || fresh || underCwd[0];
  }
  if (activeFallback) return activeFallback;
  const first = sessions.entries().next();
  return first.done ? null : [first.value[0], first.value[1]];
}

function injectSDK(html) {
  const sdkJs = fs.readFileSync(SDK_PATH, 'utf8');
  const tag = `<script data-review="1">\n${sdkJs}\n</script>`;
  if (html.includes('</body>')) return html.replace('</body>', tag + '\n</body>');
  return html + '\n' + tag;
}

function whoami() {
  let login = process.env.GITHUB_LOGIN || '';
  let name = '';
  try { name = execSync('git config user.name', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); } catch (e) {}
  const user = (os.userInfo().username || '') + '@' + os.hostname();
  return { login: login || name || os.userInfo().username, name, user };
}

function renderArtifact(file) {
  const raw = fs.readFileSync(file, 'utf8');
  let html;
  if (isMarkdown(file)) {
    html = `<!doctype html><html><head><meta charset="utf-8">
<style>body{max-width:820px;margin:0 auto;padding:32px;font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a}
pre{background:#f4f4f5;padding:12px;border-radius:8px;overflow:auto}code{font-family:ui-monospace,Menlo,monospace}
table{border-collapse:collapse}th,td{border:1px solid #ddd;padding:6px 10px}img{max-width:100%}
.mermaid{background:#f4f4f5;padding:12px;border-radius:8px}</style></head><body>${renderMarkdown(raw)}</body></html>`;
  } else {
    html = raw;
  }
  return injectSDK(html);
}

// ---------- request router ----------
const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);
  const pathname = parsed.pathname;
  const method = req.method;
  const q = parsed.query;
  const fileQ = q.file ? canon(q.file) : null;

  try {
    if (pathname === '/health' && method === 'GET') return send(res, 200, { ok: true });

    // Quiet the browser's default favicon probe (avoids a spurious 404 console error).
    if (pathname === '/favicon.ico' && method === 'GET') { res.writeHead(204); return res.end(); }

    if (pathname === '/whoami' && method === 'GET') return send(res, 200, whoami());

    // Piloth-only pipeline/gate view for the stepper. Delegates to the isolated
    // governance bridge and only when a task is bound — the core stays 1:1 and
    // standalone (ungoverned → { governed: false }, stepper stays hidden).
    if (pathname === '/pipeline' && method === 'GET') {
      if (!fileQ || !allowList.has(fileQ)) return send(res, 200, { governed: false });
      const sess = getSession(fileQ);
      if (!sess.pilothTask) return send(res, 200, { governed: false });
      let pipeline = null;
      try { pipeline = await require('../integration/govern').readPipeline(sess.pilothTask); }
      catch (e) { pipeline = null; }
      return send(res, 200, pipeline || { governed: false });
    }

    if (pathname === '/' && method === 'GET') {
      return send(res, 200, fs.readFileSync(CHROME_PATH, 'utf8'), { 'Content-Type': 'text/html; charset=utf-8' });
    }

    if (pathname === '/sdk.js' && method === 'GET') {
      return send(res, 200, fs.readFileSync(SDK_PATH, 'utf8'), { 'Content-Type': 'application/javascript; charset=utf-8' });
    }

    if (pathname === '/session' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      if (!abs || !fs.existsSync(abs)) return send(res, 404, { error: 'file not found' });
      if (!abs.endsWith('.html') && !isMarkdown(abs)) return send(res, 400, { error: 'only .html or markdown' });
      allowList.add(abs);
      const sess = getSession(abs);
      if (body.pilothTask) sess.pilothTask = String(body.pilothTask);
      watchFile(abs);
      return send(res, 200, { ok: true, file: abs, markdown: isMarkdown(abs), pilothTask: sess.pilothTask });
    }

    if (pathname === '/artifact' && method === 'GET') {
      if (!fileQ || !allowList.has(fileQ)) return send(res, 403, { error: 'not registered' });
      return send(res, 200, renderArtifact(fileQ), { 'Content-Type': 'text/html; charset=utf-8' });
    }

    if (pathname === '/source' && method === 'GET') {
      if (!fileQ || !allowList.has(fileQ)) return send(res, 403, { error: 'not registered' });
      return send(res, 200, fs.readFileSync(fileQ, 'utf8'), { 'Content-Type': 'text/plain; charset=utf-8' });
    }

    if (pathname === '/save-md' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      if (!allowList.has(abs)) return send(res, 403, { error: 'not registered' });
      const sess = getSession(abs);
      sess._suppressReload = true;
      fs.writeFileSync(abs, String(body.content == null ? '' : body.content), 'utf8');
      broadcastSSE(abs, 'reload', '{}');
      return send(res, 200, { ok: true });
    }

    if (pathname === '/annotations') {
      if (!fileQ || !allowList.has(fileQ)) return send(res, 403, { error: 'not registered' });
      if (method === 'GET') return send(res, 200, readSidecar(fileQ));
      if (method === 'POST') {
        const body = await readJSON(req);
        writeSidecar(fileQ, { version: 1, annotations: body.annotations || [], rounds: body.rounds || [] });
        return send(res, 200, { ok: true });
      }
    }

    if (pathname === '/feedback' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      if (!allowList.has(abs)) return send(res, 403, { error: 'not registered' });
      const sess = getSession(abs);
      const who = whoami();
      const now = new Date().toISOString();
      const sidecar = readSidecar(abs);
      const items = Array.isArray(body.items) ? body.items : [];
      for (const it of items) {
        sidecar.annotations.push({
          id: 'ann_' + crypto.randomBytes(6).toString('hex'),
          kind: it.kind || 'element',
          selector: it.selector || null,
          label: it.label || null,
          text: it.text || null,
          textStart: it.textStart, textEnd: it.textEnd,
          textPrefix: it.textPrefix, textSuffix: it.textSuffix,
          gate: it.gate || null,
          severity: it.severity || null,
          disposition: it.disposition || null,
          images: it.images || [],
          author: who.login, authorDetail: who.user,
          thread: [{ role: 'human', author: who.login, message: it.note || '', timestamp: now }],
          createdAt: now, status: 'open'
        });
      }
      sidecar.rounds.push({ at: now, message: body.message || '', verdict: body.verdict || null, finalized: !!body.finalized, itemCount: items.length });
      writeSidecar(abs, sidecar);

      sess.pendingFeedback = body;
      sess.working = true;
      if (body.finalized) sess.finalized = true;
      broadcastSSE(abs, 'agent-thinking', '{}');
      broadcastSSE(abs, 'agent-status', JSON.stringify({ status: 'working' }));
      wakePoll(abs, { feedback: body, finalized: !!body.finalized });
      // Governance bridge: when a Piloth task is bound, record this round as
      // human_review evidence (fire-and-forget, fail-soft). Core stays 1:1 when
      // no task is bound — nothing here runs.
      if (sess.pilothTask) {
        try { require('../integration/govern').recordFeedback(sess.pilothTask, body); } catch (e) {}
      }
      return send(res, 200, { ok: true });
    }

    if (pathname === '/poll' && method === 'GET') {
      if (!fileQ || !allowList.has(fileQ)) return send(res, 403, { error: 'not registered' });
      const sess = getSession(fileQ);
      if (sess.pendingFeedback) {
        const payload = { feedback: sess.pendingFeedback, finalized: sess.finalized };
        sess.pendingFeedback = null;
        return send(res, 200, payload);
      }
      if (sess.finalized) return send(res, 200, { feedback: null, finalized: true });
      // long-poll up to 25s
      const payload = await new Promise((resolve) => {
        sess.pollWaiters.push(resolve);
        setTimeout(() => resolve({ feedback: null, finalized: sess.finalized }), 25000);
      });
      return send(res, 200, payload);
    }

    if (pathname === '/agent-reply' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      if (!allowList.has(abs)) return send(res, 403, { error: 'not registered' });
      const sess = getSession(abs);
      const now = new Date().toISOString();
      if (body.annotationId) {
        const sidecar = readSidecar(abs);
        const a = sidecar.annotations.find((x) => x.id === body.annotationId);
        if (a) {
          a.thread.push({ role: 'agent', author: 'agent', message: body.message || '', timestamp: now });
          if (body.failed) { a.applyFailed = true; }
          else { a.status = 'resolved'; a.resolvedAt = now; }
          writeSidecar(abs, sidecar);
        }
      }
      sess.working = false;
      broadcastSSE(abs, 'agent-reply', JSON.stringify({ message: body.message || '', annotationId: body.annotationId || null, failed: !!body.failed }));
      broadcastSSE(abs, 'agent-status', JSON.stringify({ status: 'idle' }));
      return send(res, 200, { ok: true });
    }

    if (pathname === '/done' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      const sess = getSession(abs);
      sess.finalized = true;
      sess.working = false;
      wakePoll(abs, { feedback: null, finalized: true });
      broadcastSSE(abs, 'session-done', '{}');
      return send(res, 200, { ok: true });
    }

    if (pathname === '/finalize' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      if (!allowList.has(abs)) return send(res, 403, { error: 'not registered' });
      if (isMarkdown(abs)) return send(res, 400, { error: 'markdown source: use /save-md' });
      const sess = getSession(abs);
      sess._suppressReload = true;
      fs.writeFileSync(abs, String(body.html || ''), 'utf8');
      return send(res, 200, { ok: true });
    }

    if (pathname === '/upload' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      if (!allowList.has(abs)) return send(res, 403, { error: 'not registered' });
      const dir = uploadsDir(abs);
      fs.mkdirSync(dir, { recursive: true });
      const b64 = (body.data || '').replace(/^data:[^;]+;base64,/, '');
      const buf = Buffer.from(b64, 'base64');
      if (buf.length > 20 * 1024 * 1024) return send(res, 413, { error: 'too large' });
      const name = crypto.randomBytes(8).toString('hex') + '_' + (body.name || 'image.png').replace(/[^\w.\-]/g, '_');
      const p = path.join(dir, name);
      fs.writeFileSync(p, buf);
      return send(res, 200, { ok: true, name: body.name || name, path: p });
    }

    if (pathname === '/agent-progress' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      broadcastSSE(abs, 'agent-progress', JSON.stringify({ step: body.step || '', done: !!body.done }));
      return send(res, 200, { ok: true });
    }

    if (pathname === '/cancel' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      const sess = getSession(abs);
      sess.cancelRequested = true;
      broadcastSSE(abs, 'agent-cancelled', '{}');
      return send(res, 200, { ok: true });
    }

    if (pathname === '/cancelled' && method === 'GET') {
      const sess = fileQ ? sessions.get(fileQ) : null;
      return send(res, 200, { cancelled: !!(sess && sess.cancelRequested) });
    }

    if (pathname === '/cancel-check' && method === 'GET') {
      let any = false;
      for (const [, sess] of sessions) if (sess.cancelRequested) any = true;
      return send(res, 200, { cancelled: any });
    }

    // ---- hook bridge ----
    if (pathname === '/hook/pretool' && method === 'POST') {
      const body = await readJSON(req);
      const tool = body.tool_name || body.tool || '';
      const cmd = (body.tool_input && (body.tool_input.command || '')) || '';
      // Never gate our own review CLI/hook calls.
      if (tool === 'Bash' && /review-hook\.sh|piloth-review\b/.test(cmd)) return send(res, 200, '');
      const found = findActiveSession(body.cwd);
      if (!found) return send(res, 200, '');
      const [file, sess] = found;
      // Mirror the activity into the browser.
      broadcastSSE(file, 'agent-progress', JSON.stringify({ step: activityLabel(tool, body.tool_input), done: false }));
      if (sess.cancelRequested) {
        return send(res, 200, permJSON('deny', 'piloth-review: the user cancelled this round.'));
      }
      if (!sess.remoteApprove) return send(res, 200, '');
      if (sess.autoAllowTools.has(tool)) return send(res, 200, permJSON('allow'));
      const requestId = 'perm_' + Date.now().toString(36) + crypto.randomBytes(3).toString('hex');
      const summary = activityLabel(tool, body.tool_input);
      sess.pendingPerms.set(requestId, { tool, summary });
      broadcastSSE(file, 'permission-request', JSON.stringify({ requestId, tool, summary }));
      broadcastSSE(file, 'agent-status', JSON.stringify({ status: 'permission_prompt' }));
      const decision = await new Promise((resolve) => {
        sess.permWaiters.set(requestId, resolve);
        setTimeout(() => {
          if (sess.permWaiters.has(requestId)) { sess.permWaiters.delete(requestId); resolve(null); }
        }, 170000);
      });
      sess.pendingPerms.delete(requestId);
      broadcastSSE(file, 'permission-resolved', JSON.stringify({ requestId }));
      if (!decision) return send(res, 200, permJSON('ask', 'piloth-review: no response, falling back to the terminal prompt.'));
      if (decision.always) sess.autoAllowTools.add(tool);
      if (decision.decision === 'deny') return send(res, 200, permJSON('deny', decision.reason || 'Denied by reviewer.'));
      return send(res, 200, permJSON('allow'));
    }

    if (pathname === '/hook/posttool' && method === 'POST') {
      const body = await readJSON(req);
      const found = findActiveSession(body.cwd);
      if (found) broadcastSSE(found[0], 'agent-progress-done', '{}');
      return send(res, 200, '');
    }

    if (pathname === '/hook/notify' && method === 'POST') {
      const body = await readJSON(req);
      const found = findActiveSession(body.cwd);
      if (found) broadcastSSE(found[0], 'agent-status', JSON.stringify({ status: 'permission_prompt' }));
      return send(res, 200, '');
    }

    if (pathname === '/hook/stop' && method === 'POST') {
      const body = await readJSON(req);
      const found = findActiveSession(body.cwd);
      if (found) {
        found[1].working = false;
        broadcastSSE(found[0], 'agent-status', JSON.stringify({ status: 'idle' }));
      }
      return send(res, 200, '');
    }

    if (pathname === '/permission/decision' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      const sess = sessions.get(abs);
      if (sess) {
        const resolve = sess.permWaiters.get(body.requestId);
        if (resolve) {
          sess.permWaiters.delete(body.requestId);
          const decision = body.decision === 'deny' ? 'deny' : 'allow';
          resolve({ decision, always: !!body.always, reason: body.reason || '' });
          // Governance bridge: record the reviewer's decision as Piloth evidence.
          if (sess.pilothTask) {
            const pending = sess.pendingPerms.get(body.requestId) || {};
            try { require('../integration/govern').recordApproval(sess.pilothTask, { tool: pending.tool || '', decision, reason: body.reason || '' }); } catch (e) {}
          }
        }
      }
      return send(res, 200, { ok: true });
    }

    if (pathname === '/permission/mode' && method === 'POST') {
      const body = await readJSON(req);
      const abs = canon(body.file || '');
      const sess = getSession(abs);
      sess.remoteApprove = !!body.enabled;
      broadcastSSE(abs, 'permission-mode', JSON.stringify({ enabled: sess.remoteApprove }));
      return send(res, 200, { ok: true });
    }

    if (pathname === '/events' && method === 'GET') {
      if (!fileQ) return send(res, 400, { error: 'file required' });
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
      });
      res.write(': connected\n\n');
      const sess = getSession(fileQ);
      sess.sseClients.add(res);
      const ping = setInterval(() => { try { res.write(': ping\n\n'); } catch (e) {} }, 20000);
      req.on('close', () => { clearInterval(ping); sess.sseClients.delete(res); });
      return;
    }

    if (pathname === '/stop' && method === 'POST') {
      send(res, 200, { ok: true });
      setTimeout(() => process.exit(0), 100);
      return;
    }

    return send(res, 404, { error: 'not found' });
  } catch (err) {
    return send(res, 500, { error: String(err && err.message || err) });
  }
});

function activityLabel(tool, input) {
  input = input || {};
  if (tool === 'Bash') return 'Bash: ' + String(input.command || '').slice(0, 80);
  if (tool === 'Read') return 'Read ' + (input.file_path || '');
  if (tool === 'Edit' || tool === 'Write' || tool === 'MultiEdit') return tool + ' ' + (input.file_path || '');
  if (tool === 'Grep') return 'Grep ' + (input.pattern || '');
  if (tool === 'Glob') return 'Glob ' + (input.pattern || '');
  return tool || 'tool';
}

server.listen(PORT, HOST, () => {
  process.stdout.write(`piloth-review server on http://${HOST}:${PORT}\n`);
});

module.exports = { server };
