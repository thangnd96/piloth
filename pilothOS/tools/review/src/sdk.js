/* Piloth Review SDK — injected into the artifact iframe at serve time.
 * Faithful to annotron's sdk.js: capture point-and-click element + text
 * selections, compute stable locators (CSS path + text offsets), and talk to
 * the parent chrome via postMessage. The disk file is never modified — this
 * script is spliced in only when the server serves /artifact.
 */
(function () {
  'use strict';
  var TAG = 'piloth-review-sdk';
  var annotating = false;
  var annotations = [];
  var overlayEls = [];

  function post(type, payload) {
    var msg = Object.assign({}, payload || {});
    msg[TAG] = true;
    msg.type = type;
    window.parent.postMessage(msg, '*');
  }

  // Build a CSS selector path for an element: body > div > p:nth-of-type(2)
  function cssPath(el) {
    if (!(el instanceof Element)) return '';
    var path = [];
    while (el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html') {
      var selector = el.tagName.toLowerCase();
      if (el.id) {
        selector += '#' + cssEscape(el.id);
        path.unshift(selector);
        break;
      }
      var parent = el.parentElement;
      if (parent) {
        var sameTag = Array.prototype.filter.call(
          parent.children, function (c) { return c.tagName === el.tagName; });
        if (sameTag.length > 1) {
          var idx = sameTag.indexOf(el) + 1;
          selector += ':nth-of-type(' + idx + ')';
        }
      }
      path.unshift(selector);
      el = parent;
    }
    return path.join(' > ');
  }

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^\w-]/g, '\\$&');
  }

  // Human-readable label: tag#id.class "first 40 chars of text"
  function labelFor(el) {
    var t = el.tagName.toLowerCase();
    if (el.id) t += '#' + el.id;
    else if (el.className && typeof el.className === 'string') {
      var cls = el.className.trim().split(/\s+/).slice(0, 2).join('.');
      if (cls) t += '.' + cls;
    }
    var txt = (el.textContent || '').trim().replace(/\s+/g, ' ');
    if (txt) t += ' "' + txt.slice(0, 40) + (txt.length > 40 ? '…' : '') + '"';
    return t;
  }

  // Offset of a (container,offset) point inside root, measured in string length.
  function textOffsetWithin(root, container, offset) {
    var range = document.createRange();
    range.selectNodeContents(root);
    try { range.setEnd(container, offset); } catch (e) { return 0; }
    return range.toString().length;
  }

  function extractSelectedTextData() {
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
    var range = sel.getRangeAt(0);
    var text = sel.toString().trim();
    if (!text) return null;
    var container = range.commonAncestorContainer;
    if (container.nodeType === 3) container = container.parentElement;
    var start = textOffsetWithin(container, range.startContainer, range.startOffset);
    var end = textOffsetWithin(container, range.endContainer, range.endOffset);
    var full = container.textContent || '';
    return {
      selector: cssPath(container),
      text: text,
      label: labelFor(container),
      textStart: start,
      textEnd: end,
      textPrefix: full.slice(Math.max(0, start - 24), start),
      textSuffix: full.slice(end, end + 24)
    };
  }

  // ---- capture handlers ----
  document.addEventListener('click', function (e) {
    if (!annotating) return;
    // Ignore clicks on our own UI.
    if (e.target.closest && e.target.closest('[data-review-ui]')) return;
    var sel = window.getSelection();
    if (sel && sel.toString().trim()) return; // handled by mouseup
    e.preventDefault();
    e.stopPropagation();
    var el = e.target;
    post('element-selected', {
      kind: 'element',
      selector: cssPath(el),
      label: labelFor(el),
      note: ''
    });
  }, true);

  document.addEventListener('mouseup', function () {
    if (!annotating) return;
    var data = extractSelectedTextData();
    if (!data) return;
    post('text-selected', Object.assign({ kind: 'text', note: '' }, data));
  });

  // ---- annotation overlay ----
  function clearOverlay() {
    overlayEls.forEach(function (el) { if (el.parentNode) el.parentNode.removeChild(el); });
    overlayEls = [];
  }

  function markFor(a) {
    var target = null;
    try { target = a.selector ? document.querySelector(a.selector) : null; } catch (e) {}
    if (!target) return;
    var rect = target.getBoundingClientRect();
    var mark = document.createElement('div');
    mark.setAttribute('data-review-ui', 'annotation-mark');
    mark.style.position = 'absolute';
    mark.style.left = (rect.left + window.scrollX) + 'px';
    mark.style.top = (rect.top + window.scrollY) + 'px';
    mark.style.width = rect.width + 'px';
    mark.style.height = rect.height + 'px';
    mark.style.pointerEvents = 'none';
    mark.style.zIndex = '2147483000';
    var resolved = a.status === 'resolved';
    if (a.kind === 'text') {
      mark.style.borderBottom = '2px solid ' + (resolved ? '#16a34a' : '#2741f1');
      mark.style.background = resolved ? 'rgba(22,163,74,0.10)' : 'rgba(39,65,241,0.12)';
    } else {
      mark.style.outline = '2px solid ' + (resolved ? '#16a34a' : '#2741f1');
      mark.style.background = resolved ? 'rgba(22,163,74,0.06)' : 'rgba(39,65,241,0.06)';
    }
    document.body.appendChild(mark);
    overlayEls.push(mark);
  }

  function renderAnnotationsOverlay() {
    clearOverlay();
    annotations.forEach(markFor);
  }

  // Serialize current DOM (strip scripts + our UI) for finalize.
  function serialize() {
    var clone = document.documentElement.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll('script[data-review], [data-review-ui]'),
      function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
    return '<!doctype html>\n' + clone.outerHTML;
  }

  // ---- parent -> iframe messages ----
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || !d[TAG]) return;
    switch (d.type) {
      case 'set-annotate':
        annotating = !!d.value;
        document.body.style.cursor = annotating ? 'crosshair' : '';
        break;
      case 'set-annotations':
        annotations = Array.isArray(d.annotations) ? d.annotations : [];
        renderAnnotationsOverlay();
        break;
      case 'serialize':
        post('serialized', { reqId: d.reqId, html: serialize() });
        break;
      case 'jump-to-element':
        try {
          var el = document.querySelector(d.selector);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch (err) {}
        break;
      case 'clear-highlight':
        clearOverlay();
        break;
    }
  });

  window.addEventListener('resize', renderAnnotationsOverlay);
  window.addEventListener('scroll', renderAnnotationsOverlay, true);

  // Handshake: tell the parent we're ready and hand over headings for the outline.
  function headings() {
    var out = [];
    Array.prototype.forEach.call(document.querySelectorAll('h1,h2,h3,h4'), function (h) {
      out.push({ level: Number(h.tagName[1]), text: (h.textContent || '').trim(), id: h.id || '' });
    });
    return out;
  }
  post('sdk-ready', { headings: headings() });
})();
