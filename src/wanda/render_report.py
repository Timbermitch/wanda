"""
render_report.py — converts Wanda's text reports into polished, self-contained
HTML files saved to the reports/ directory. No external CSS/JS dependencies.
"""
import html
import os
import re
from datetime import datetime
from pathlib import Path

def _reports_dir() -> Path:
    """Where reports are written — resolved at call time so it follows the
    caller's working directory (and an optional WANDA_REPORTS_DIR override),
    not the installed package location."""
    return Path(os.environ.get("WANDA_REPORTS_DIR", Path.cwd() / "reports"))

CSS = """
:root {
    --bg: #f6f8fc;
    --surface: #ffffff;
    --surface-elevated: #f4f7fc;
    --border: #d9e1ee;
    --border-subtle: #e8eef6;
    --text: #0e1626;
    --text-soft: #2b3651;
    --text-muted: #5b6680;
    --accent: #2f7df6;
    --accent-2: #1763d6;
    --success: #0e9f6e;
    --warning: #b7791f;
    --danger: #d64545;
    --code-bg: #f1f5fb;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Helvetica, Arial, sans-serif;
    color: var(--text-soft);
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background:
        radial-gradient(ellipse 1100px 680px at 50% -10%, rgba(47,125,246,0.06), transparent 62%),
        var(--bg);
    background-attachment: fixed;
}
.container { max-width: 880px; margin: 0 auto; padding: 64px 28px 96px; }

header {
    display: flex; align-items: center; gap: 18px;
    margin-bottom: 36px; padding-bottom: 28px;
    border-bottom: 1px solid var(--border-subtle);
}
.logo {
    width: 52px; height: 52px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    border-radius: 13px;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 800; color: white;
    box-shadow: 0 8px 28px rgba(88, 166, 255, 0.28), inset 0 1px 0 rgba(255,255,255,0.18);
    letter-spacing: -0.5px;
}
.brand h1 { margin: 0 0 2px 0; font-size: 22px; letter-spacing: -0.4px; color: var(--text); font-weight: 700; }
.subtitle { color: var(--text-muted); font-size: 13px; letter-spacing: 0.1px; }

.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px;
    margin-bottom: 28px;
}
.meta-card {
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 13px 15px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
    transition: border-color 160ms ease;
}
.meta-card:hover { border-color: var(--border); }
.meta-label {
    color: var(--text-muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    margin-bottom: 5px;
    font-weight: 600;
}
.meta-value { font-size: 13.5px; font-weight: 500; word-break: break-word; color: var(--text); }

.status-banner {
    padding: 20px 26px;
    border-radius: 14px;
    margin-bottom: 32px;
    font-weight: 600;
    font-size: 17px;
    border: 1px solid;
    display: flex; align-items: center; gap: 16px;
    backdrop-filter: blur(8px);
}
.status-banner .icon {
    font-size: 24px;
    width: 36px; height: 36px;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 10px;
    flex-shrink: 0;
}
.status-banner.success {
    background: linear-gradient(135deg, rgba(86,211,100,0.10), rgba(86,211,100,0.02));
    border-color: rgba(86,211,100,0.35);
    color: var(--success);
}
.status-banner.success .icon { background: rgba(86,211,100,0.15); }
.status-banner.warning {
    background: linear-gradient(135deg, rgba(227,179,65,0.10), rgba(227,179,65,0.02));
    border-color: rgba(227,179,65,0.35);
    color: var(--warning);
}
.status-banner.warning .icon { background: rgba(227,179,65,0.15); }
.status-banner.danger {
    background: linear-gradient(135deg, rgba(255,123,114,0.10), rgba(255,123,114,0.02));
    border-color: rgba(255,123,114,0.35);
    color: var(--danger);
}
.status-banner.danger .icon { background: rgba(255,123,114,0.15); }

section {
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 26px 30px;
    margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 6px 18px rgba(16,24,40,0.05);
    transition: border-color 200ms ease, transform 200ms ease;
}
section:hover { border-color: var(--border); }

section h2 {
    margin: 0 0 18px 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.6px;
    color: var(--text-muted);
    font-weight: 700;
    display: flex; align-items: center; gap: 12px;
}
section h2::before {
    content: "";
    display: block;
    width: 18px; height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
    border-radius: 2px;
}

section.root-cause {
    background: linear-gradient(180deg, #ffffff, #fff6f5);
    border: 1px solid rgba(214,69,69,0.28);
}
section.root-cause h2 { color: var(--danger); }
section.root-cause h2::before { background: var(--danger); }
section.root-cause .body-text p {
    font-size: 16px;
    font-weight: 500;
    color: var(--text);
    line-height: 1.65;
}

section.recommendation {
    border: 1px solid rgba(86,211,100,0.25);
    background: linear-gradient(180deg, rgba(86,211,100,0.04), rgba(86,211,100,0));
}
section.recommendation h2 { color: var(--success); }
section.recommendation h2::before { background: var(--success); }
section.recommendation .body-text p {
    font-size: 15px;
    color: var(--text);
    line-height: 1.65;
}

.body-text { font-size: 14.5px; }
.body-text p { margin: 0 0 14px 0; }
.body-text p:last-child { margin-bottom: 0; }
.body-text ol, .body-text ul {
    margin: 0 0 14px 0;
    padding-left: 22px;
}
.body-text ol:last-child, .body-text ul:last-child { margin-bottom: 0; }
.body-text li {
    margin-bottom: 8px;
    line-height: 1.65;
    color: var(--text-soft);
}
.body-text li:last-child { margin-bottom: 0; }
.body-text ol li::marker { color: var(--accent); font-weight: 600; }
.body-text ul li::marker { color: var(--accent-2); }
.body-text code, .body-text pre {
    font-family: "SF Mono", Monaco, "Cascadia Code", "JetBrains Mono", Consolas, monospace;
}
.body-text code {
    background: var(--code-bg);
    padding: 2px 7px;
    border-radius: 5px;
    font-size: 12.5px;
    color: var(--accent);
    border: 1px solid var(--border-subtle);
    font-weight: 500;
}
.body-text pre {
    background: var(--code-bg);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 14px 16px;
    overflow-x: auto;
    margin: 0 0 14px 0;
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--text);
}
.body-text pre code {
    background: transparent;
    border: none;
    padding: 0;
    color: inherit;
    font-size: inherit;
}
.body-text strong {
    color: var(--text);
    font-weight: 600;
}
.body-text h3 {
    margin: 18px 0 10px 0;
    font-size: 13.5px;
    color: var(--text);
    font-weight: 600;
    letter-spacing: 0.1px;
}
.body-text h3:first-child { margin-top: 0; }
.body-text h3.pass { color: var(--success); }
.body-text h3.fail { color: var(--danger); }
.body-text h3.warn { color: var(--warning); }

.evidence-item {
    padding: 16px 0;
    border-bottom: 1px solid var(--border-subtle);
}
.evidence-item:first-child { padding-top: 4px; }
.evidence-item:last-child { padding-bottom: 4px; border-bottom: none; }
.evidence-label {
    color: var(--accent);
    font-weight: 700;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 8px;
    display: flex; align-items: center; gap: 8px;
}
.evidence-label::before {
    content: "";
    display: inline-block;
    width: 6px; height: 6px;
    background: var(--accent);
    border-radius: 50%;
    box-shadow: 0 0 8px var(--accent);
}
.evidence-value {
    font-size: 14.5px;
    line-height: 1.6;
    color: var(--text-soft);
}
.evidence-note {
    margin: 12px 0 0 0;
    color: var(--text-muted);
    font-size: 13px;
    font-style: italic;
}

footer {
    margin-top: 56px;
    padding-top: 24px;
    border-top: 1px solid var(--border-subtle);
    color: var(--text-muted);
    font-size: 11.5px;
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;
    letter-spacing: 0.2px;
}
.brand-mark {
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-weight: 700;
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="container">
    <header>
        <div class="logo">W</div>
        <div class="brand">
            <h1>Wanda</h1>
            <div class="subtitle">AI Data Engineer · Microsoft Fabric</div>
        </div>
    </header>

    <div class="meta-grid">
        <div class="meta-card">
            <div class="meta-label">Pipeline</div>
            <div class="meta-value">{pipeline_name}</div>
        </div>
        <div class="meta-card">
            <div class="meta-label">Mode</div>
            <div class="meta-value">{mode}</div>
        </div>
        <div class="meta-card">
            <div class="meta-label">Generated</div>
            <div class="meta-value">{timestamp}</div>
        </div>
        <div class="meta-card">
            <div class="meta-label">Model</div>
            <div class="meta-value">{model}</div>
        </div>
        <div class="meta-card">
            <div class="meta-label">Duration</div>
            <div class="meta-value">{duration}</div>
        </div>
    </div>

    <div class="status-banner {status_class}">
        <span class="icon">{status_icon}</span>
        <span>{status_text}</span>
    </div>

    {body}

    <footer>
        <div>Generated by <span class="brand-mark">Wanda</span> · CM Labs</div>
        <div>Microsoft Fabric Pipeline Investigator</div>
    </footer>
</div>
</body>
</html>
"""

# Section names Wanda commonly emits. Used to classify markdown headings
# into the right CSS treatment and to recognise Wanda's strict colon-format.
SECTION_NAMES = [
    "PRE-RUN SCAN REPORT",
    "PRE-RUN SCAN",
    "PIPELINE SCAN",
    "ROOT CAUSE OF FAILURE",
    "ROOT CAUSE",
    "EVIDENCE",
    "RECOMMENDATION",
    "OVERALL STATUS",
    "ACTIVITIES STATUS",
    "ACTIVITY AUDIT",
    "ACTIVITIES",
    "ISSUES TO FIX BEFORE RUNNING",
    "ISSUES TO FIX",
    "FIX REQUIRED",
    "FIXES REQUIRED",
    "CRITICAL FIXES REQUIRED",
    "EXISTING RESOURCES CONFIRMED",
    "EXECUTION FLOW",
    "WHAT WILL PASS",
    "WHAT WILL FAIL",
    "VERDICT",
    "SUMMARY",
    "DEPENDENCY CHAIN",
]

ROOT_CAUSE_SECTIONS = {"ROOT CAUSE", "ROOT CAUSE OF FAILURE", "VERDICT"}
RECOMMENDATION_SECTIONS = {
    "RECOMMENDATION",
    "FIX REQUIRED",
    "FIXES REQUIRED",
    "CRITICAL FIXES REQUIRED",
    "ISSUES TO FIX",
    "ISSUES TO FIX BEFORE RUNNING",
}


def _detect_status(content):
    upper = content.upper()
    if "WILL FAIL" in upper or "❌" in content or "PIPELINE WILL FAIL" in upper:
        return ("danger", "❌", "Pipeline issues detected")
    if "READY TO RUN" in upper or "SAFE TO RUN" in upper or "COMPLETED SUCCESSFULLY" in upper:
        return ("success", "✅", "Pipeline healthy")
    if "ROOT CAUSE:" in upper or "ROOT CAUSE OF FAILURE" in upper:
        return ("danger", "❌", "Pipeline failure diagnosed")
    if "WARNINGS FOUND" in upper or "⚠️" in content or "WARNING" in upper:
        return ("warning", "⚠️", "Warnings detected")
    return ("warning", "ℹ️", "Review report")


def _format_inline(text):
    """Inline markdown: escape HTML, convert **bold** and `code`, strip orphan markers."""
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*([^\*\n]+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*+", "", escaped)
    return escaped


def _is_visible(html_fragment):
    return bool(re.sub(r"<[^>]+>", "", html_fragment).strip())


def _format_block(para):
    """Format a single paragraph or list block into HTML.
    Handles numbered lists, bulleted lists, and lead text before lists.
    Also recognises pass/fail subheadings like '✅ WILL PASS (4 of 5):'."""
    lines = [l for l in para.split("\n") if l.strip()]
    if not lines:
        return ""

    # Recognise a pass/fail subheading as <h3>
    sub_re = re.compile(r"^\s*(✅|❌|⚠️)\s*(.+?)\s*:?\s*$")

    # Walk lines, emitting blocks: subheadings (<h3>), ordered lists, unordered lists, paragraphs.
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        sub_m = sub_re.match(line)
        if sub_m:
            icon, label = sub_m.group(1), sub_m.group(2).strip()
            css_cls = {"✅": "pass", "❌": "fail", "⚠️": "warn"}.get(icon, "")
            out.append(
                f'<h3 class="{css_cls}">{html.escape(icon)} {_format_inline(label)}</h3>'
            )
            i += 1
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            items_html = "\n".join(f"<li>{_format_inline(it)}</li>" for it in items)
            out.append(f"<ol>{items_html}</ol>")
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            items_html = "\n".join(f"<li>{_format_inline(it)}</li>" for it in items)
            out.append(f"<ul>{items_html}</ul>")
            continue

        # Plain paragraph: collect contiguous non-list, non-subheading lines
        plain = []
        while i < len(lines):
            nxt = lines[i]
            if sub_re.match(nxt) or re.match(r"^\s*(\d+\.|[-*])\s+", nxt):
                break
            plain.append(nxt)
            i += 1
        formatted = _format_inline("\n".join(plain)).replace("\n", "<br>")
        if _is_visible(formatted):
            out.append(f"<p>{formatted}</p>")

    return "\n".join(out)


def _format_paragraphs(text):
    """Split text into paragraphs (blank-line separated) and emit HTML."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    blocks = []
    for para in paragraphs:
        html_block = _format_block(para)
        if html_block.strip():
            blocks.append(html_block)
    return "\n".join(blocks)


def _format_evidence(text):
    """Render an EVIDENCE block: lines like '- **Label**: value' or '**Label:** value'
    or '- Label: value' become styled evidence items."""
    lines = text.split("\n")
    items = []
    note_buffer = []

    def flush_notes():
        if note_buffer:
            content = _format_inline(" ".join(note_buffer))
            note_buffer.clear()
            if _is_visible(content):
                items.append(f'<p class="evidence-note">{content}</p>')

    # Accept: optional leading bullet, optional **, label, optional **, colon, value
    label_re = re.compile(
        r"^\s*(?:[-*]\s+)?\*{0,2}\s*([^*\n:][^*\n:]{0,80}?)\s*\*{0,2}\s*:\s*(.+)$"
    )

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped in ("**", "***", "-", "*"):
            flush_notes()
            continue
        m = label_re.match(stripped)
        if m:
            flush_notes()
            label = html.escape(m.group(1).strip())
            value_inline = _format_inline(m.group(2).strip())
            items.append(
                f'<div class="evidence-item">'
                f'<div class="evidence-label">{label}</div>'
                f'<div class="evidence-value">{value_inline}</div>'
                f"</div>"
            )
        else:
            note_buffer.append(stripped)

    flush_notes()
    return "\n".join(items) if items else _format_paragraphs(text)


def _normalize_strict_headers(content):
    """Convert Wanda's strict-format headers ('ROOT CAUSE:' at line start) into
    markdown ## headers so a single parser can handle every output style.
    Preserves any trailing content on the same line as the colon."""
    name_alt = "|".join(re.escape(n) for n in sorted(SECTION_NAMES, key=len, reverse=True))
    pattern = re.compile(
        rf"^([ \t]*)\*{{0,2}}({name_alt})\*{{0,2}}[ \t]*:[ \t]*",
        re.MULTILINE | re.IGNORECASE,
    )
    return pattern.sub(lambda m: f"{m.group(1)}## {m.group(2).upper()}\n", content)


def _parse_sections(content):
    """Split content by markdown headings. Returns list of (canonical_name, body)."""
    content = _normalize_strict_headers(content)

    # Split on markdown headings (any level). Capture the heading text.
    pieces = re.split(r"^[ \t]*#+[ \t]+(.+?)[ \t]*$", content, flags=re.MULTILINE)

    sections = []
    preamble = pieces[0].strip()
    if preamble:
        sections.append(("__PREAMBLE__", preamble))

    for i in range(1, len(pieces), 2):
        heading_raw = pieces[i].strip()
        body = pieces[i + 1].strip() if i + 1 < len(pieces) else ""
        heading_clean = re.sub(r"\*+", "", heading_raw).strip()
        if ":" in heading_clean:
            label = heading_clean.split(":", 1)[0].strip()
        else:
            label = heading_clean
        sections.append((label.upper(), body))

    return sections


def _canonical_section(name):
    """Collapse minor variants ('ROOT CAUSE OF FAILURE' -> 'ROOT CAUSE') for display."""
    if name in ROOT_CAUSE_SECTIONS:
        return "ROOT CAUSE"
    return name


def _format_body(content):
    sections = _parse_sections(content)
    if not sections or all(n == "__PREAMBLE__" for n, _ in sections):
        return (
            f'<section><h2>Report</h2>'
            f'<div class="body-text">{_format_paragraphs(content)}</div></section>'
        )

    out = []
    for name, body in sections:
        if name == "__PREAMBLE__":
            filtered = re.sub(
                r"^(Perfect|Great|Now|Let me|I'll|Based on|Here is|Here's).*$",
                "",
                body,
                flags=re.IGNORECASE | re.MULTILINE,
            ).strip()
            if len(filtered) > 60:
                out.append(
                    f'<section><h2>Overview</h2>'
                    f'<div class="body-text">{_format_paragraphs(filtered)}</div></section>'
                )
            continue

        # Skip section-title-only headers with no body (e.g. an H2 title above sub-sections)
        if not body.strip():
            continue

        css_classes = []
        if name in RECOMMENDATION_SECTIONS:
            css_classes.append("recommendation")
        if name in ROOT_CAUSE_SECTIONS:
            css_classes.append("root-cause")
        cls_attr = f' class="{" ".join(css_classes)}"' if css_classes else ""

        display_name = _canonical_section(name)

        if display_name == "EVIDENCE":
            body_html = _format_evidence(body)
        else:
            body_html = _format_paragraphs(body)

        out.append(
            f"<section{cls_attr}>"
            f"<h2>{html.escape(display_name)}</h2>"
            f'<div class="body-text">{body_html}</div>'
            f"</section>"
        )

    return "\n".join(out)


def _format_duration(seconds):
    if not seconds:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs:02d}s"


def build_html(content, pipeline_name, mode, model="unknown", duration_seconds=0.0, now=None):
    """Render a Wanda report to a self-contained HTML string (no file I/O).
    Used for inline display in notebooks; render_report wraps this to save."""
    now = now or datetime.now()
    status_class, status_icon, status_text = _detect_status(content)
    body_html = _format_body(content)
    duration_str = _format_duration(duration_seconds)

    return HTML_TEMPLATE.format(
        title=f"Wanda · {html.escape(pipeline_name)} · {html.escape(mode)}",
        css=CSS,
        pipeline_name=html.escape(pipeline_name),
        mode=html.escape(mode),
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
        model=html.escape(model),
        duration=duration_str,
        status_class=status_class,
        status_icon=status_icon,
        status_text=html.escape(status_text),
        body=body_html,
    )


def render_report(content, pipeline_name, mode, model="unknown", duration_seconds=0.0):
    """Write a polished HTML report for a Wanda run and return the file Path."""
    reports_dir = _reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp_slug = now.strftime("%Y-%m-%d_%H-%M-%S")
    mode_slug = mode.lower().replace(" ", "_").replace("-", "_")
    safe_pipeline = re.sub(r"[^A-Za-z0-9_\-]+", "_", pipeline_name)
    filename = f"{safe_pipeline}_{timestamp_slug}_{mode_slug}.html"
    out_path = reports_dir / filename

    html_doc = build_html(content, pipeline_name, mode, model, duration_seconds, now)
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path
