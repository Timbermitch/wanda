/**
 * Wanda beta — telemetry collector (Google Apps Script web app).
 *
 * Catches the fire-and-forget JSON that src/wanda/telemetry.py POSTs and appends
 * one row per event to the bound Google Sheet. Free, no Azure, runs on your
 * Google account. See beta/TELEMETRY_SETUP.md for the 5-minute deploy.
 *
 * The client sends (telemetry.py -> emit):
 *   run    : event, install_id, wanda_version, python, os, status, mode,
 *            duration_seconds, tool_calls, turns, usage{input/output/cache_* tokens}
 *   run/err: event, ..., status="error", mode, error=<ExceptionClassName>
 *   feedback: event, ..., mode, useful=<bool>, note=<str <=500>
 *
 * By design the payload NEVER contains pipeline/table/column names, query text,
 * report content, workspace ids, or secrets — so this sheet is safe to keep.
 */

// Fixed columns we break out for easy filtering; everything is also kept verbatim
// in raw_json so a new field added later is never silently dropped.
var HEADERS = [
  'received_at', 'event', 'status', 'mode', 'install_id', 'wanda_version',
  'python', 'os', 'duration_seconds', 'tool_calls', 'turns',
  'input_tokens', 'output_tokens', 'cache_creation_input_tokens',
  'cache_read_input_tokens', 'error', 'useful', 'note', 'raw_json'
];

function doPost(e) {
  try {
    var data = {};
    if (e && e.postData && e.postData.contents) {
      data = JSON.parse(e.postData.contents);
    }
    var usage = (data.usage && typeof data.usage === 'object') ? data.usage : {};

    var sheet = _sheet();
    sheet.appendRow([
      new Date(),                       // received_at — server clock, not the client's
      data.event || '',
      data.status || '',
      data.mode || '',
      data.install_id || '',
      data.wanda_version || '',
      data.python || '',
      data.os || '',
      _num(data.duration_seconds),
      _num(data.tool_calls),
      _num(data.turns),
      _num(usage.input_tokens),
      _num(usage.output_tokens),
      _num(usage.cache_creation_input_tokens),
      _num(usage.cache_read_input_tokens),
      data.error || '',
      (typeof data.useful === 'boolean') ? data.useful : '',
      data.note || '',
      e && e.postData ? e.postData.contents : ''
    ]);

    return _json({ ok: true });
  } catch (err) {
    // Never surface details; the client ignores the response anyway.
    return _json({ ok: false });
  }
}

// A GET on the URL is handy for a quick "is it live?" check from a browser.
function doGet() {
  return _json({ ok: true, service: 'wanda-telemetry', rows: _sheet().getLastRow() - 1 });
}

function _sheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('events') || ss.insertSheet('events');
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function _num(v) {
  return (typeof v === 'number') ? v : '';
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
