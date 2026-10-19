import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowRight, BarChart3, BookOpen, Check, CheckCircle2, ChevronDown,
  ChevronLeft, ChevronRight, Clock3, Command, ExternalLink, FileText, Fingerprint, Heart,
  Image, LayoutDashboard, LoaderCircle, Megaphone, Menu, MessageSquare,
  PenLine, Plus, RefreshCw, Search, Send, Settings2,
  ShieldCheck, Sparkles, ThumbsDown, ThumbsUp, X, Zap,
} from "lucide-react";
import { api } from "./api.js";

const NAV = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "campaigns", label: "Campaigns", icon: Megaphone },
  { id: "brand", label: "Brand library", icon: BookOpen },
  { id: "memory", label: "Crew memory", icon: Fingerprint },
];
const OUTPUTS = {
  landing: { label: "Landing page", icon: Image },
  blog: { label: "Blog article", icon: FileText },
  social_linkedin: { label: "LinkedIn", icon: MessageSquare },
  social_x: { label: "X / Twitter", icon: MessageSquare },
  social_instagram: { label: "Instagram", icon: Image },
};
const SCOPES = [
  "/company/knowledge",
  "/marketing/seo",
  "/marketing/campaigns",
  "/editor/private",
  "/visual/brand",
];

function viewFromHash() {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/");
  if (parts[0] === "runs" && parts[1]) return { page: "run", runId: parts[1] };
  return { page: parts[0] || "dashboard", runId: null };
}

function dateLabel(value, compact = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en", compact
    ? { month: "short", day: "numeric" }
    : { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function titleCase(value = "") {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusLabel(status = "queued") {
  return ({
    awaiting_approval: "Needs your review",
    analyzed: "Complete",
    analyzing: "Learning",
    approved: "Approved",
    running: "In progress",
    queued: "Queued",
    failed: "Failed",
  })[status] || titleCase(status);
}

function StatusPill({ status }) {
  const working = ["queued", "running", "analyzing"].includes(status);
  return (
    <span className={`status-pill status-${status || "queued"}`}>
      {working ? <LoaderCircle size={12} className="spin" /> : <span className="status-dot" />}
      {statusLabel(status)}
    </span>
  );
}

function Score({ value, large = false }) {
  if (value == null) return <span className="score-muted">—</span>;
  const tone = value >= 80 ? "good" : value >= 60 ? "mid" : "low";
  return (
    <span className={`score score-${tone} ${large ? "score-large" : ""}`}>
      <span className="score-ring"><span /></span>
      {value}<small>/100</small>
    </span>
  );
}

function EmptyState({ icon: Icon = Sparkles, title, text, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon size={21} /></span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

function ScoreChart({ runs }) {
  const data = runs.filter((run) => run.avg_brand_score != null).slice(0, 9).reverse();
  if (!data.length) {
    return (
      <div className="chart-empty">
        <BarChart3 size={20} />
        <span>Scores appear here after your first campaign is reviewed.</span>
      </div>
    );
  }
  const width = 640;
  const height = 180;
  const pad = { top: 20, right: 22, bottom: 30, left: 30 };
  const scores = data.map((run) => run.avg_brand_score);
  const low = Math.max(0, Math.floor((Math.min(...scores) - 12) / 10) * 10);
  const high = Math.min(100, Math.ceil((Math.max(...scores) + 8) / 10) * 10 || 100);
  const x = (index) => pad.left + (data.length === 1 ? (width - pad.left - pad.right) / 2
    : index * (width - pad.left - pad.right) / (data.length - 1));
  const y = (score) => height - pad.bottom - ((score - low) / Math.max(1, high - low)) * (height - pad.top - pad.bottom);
  const points = data.map((run, index) => `${x(index)},${y(run.avg_brand_score)}`).join(" ");
  const area = `${x(0)},${height - pad.bottom} ${points} ${x(data.length - 1)},${height - pad.bottom}`;
  return (
    <div className="chart-wrap">
      <svg className="score-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Brand score trend">
        <defs>
          <linearGradient id="score-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#7775f7" stopOpacity=".2" />
            <stop offset="100%" stopColor="#7775f7" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((tick) => {
          const tickY = pad.top + tick * (height - pad.top - pad.bottom) / 3;
          const label = Math.round(high - tick * (high - low) / 3);
          return <g key={tick}>
            <line x1={pad.left} x2={width - pad.right} y1={tickY} y2={tickY} className="chart-grid" />
            <text x="0" y={tickY + 4} className="chart-axis">{label}</text>
          </g>;
        })}
        <polygon points={area} fill="url(#score-fill)" />
        {data.length > 1 && <polyline points={points} className="chart-line" />}
        {data.map((run, index) => (
          <g key={run.id}>
            <circle cx={x(index)} cy={y(run.avg_brand_score)} r="5.5" className="chart-point-outer" />
            <circle cx={x(index)} cy={y(run.avg_brand_score)} r="3" className="chart-point" />
            <text x={x(index)} y={height - 5} textAnchor="middle" className="chart-date">
              {run.week_id || dateLabel(run.created_at, true)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function Sidebar({ page, navigate, mobileOpen, closeMobile, health }) {
  return (
    <>
      {mobileOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={closeMobile} />}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <span className="brand-mark"><Sparkles size={20} fill="currentColor" /></span>
          <span><b>brandcrew</b><small>CAMPAIGN STUDIO</small></span>
          <button className="icon-button sidebar-close" onClick={closeMobile} aria-label="Close menu"><X size={18} /></button>
        </div>
        <div className="workspace-switch">
          <span className="workspace-avatar">L</span>
          <span className="workspace-copy"><b>Lumio workspace</b><small>Free workspace</small></span>
          <ChevronDown size={15} />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${page === id || (id === "campaigns" && page === "run") ? "nav-active" : ""}`}
              onClick={() => { navigate(id); closeMobile(); }}>
              <Icon size={17} strokeWidth={1.9} /><span>{label}</span>
              {id === "campaigns" && <span className="nav-count">↗</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-tip">
            <div className="tip-spark"><Zap size={14} fill="currentColor" /></div>
            <b>Better every week.</b>
            <p>Your crew learns from every approved campaign and feedback you share.</p>
            <button onClick={() => navigate("memory")}>Explore crew memory <ArrowRight size={13} /></button>
          </div>
          <button className="nav-item settings-item" onClick={() => navigate("brand")}><Settings2 size={17} /><span>Brand settings</span></button>
          <div className="connection-state"><span className={`connection-dot ${health === "ok" ? "online" : ""}`} />{health === "ok" ? "All systems operational" : "API connection unavailable"}</div>
        </div>
      </aside>
    </>
  );
}

function Header({ page, onMenu, onRefresh, refreshing }) {
  const title = page === "dashboard" ? "Overview" : page === "campaigns" ? "Campaigns"
    : page === "brand" ? "Brand library" : page === "memory" ? "Crew memory" : "Campaign review";
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-button menu-toggle" onClick={onMenu} aria-label="Open menu"><Menu size={20} /></button>
        <div className="breadcrumbs"><span>Workspace</span><ChevronRight size={13} /><b>{title}</b></div>
      </div>
      <div className="topbar-actions">
        <span className="live-indicator"><span /> LIVE WORKSPACE</span>
        <button className="icon-button refresh-button" onClick={onRefresh} disabled={refreshing} aria-label="Refresh"><RefreshCw size={16} className={refreshing ? "spin" : ""} /></button>
        <div className="avatar">S</div>
      </div>
    </header>
  );
}

function Dashboard({ runs, onOpenRun, onNewRun, loading, error }) {
  const [theme, setTheme] = useState("");
  const stats = useMemo(() => {
    const scored = runs.filter((run) => run.avg_brand_score != null);
    const mean = scored.length ? Math.round(scored.reduce((sum, run) => sum + run.avg_brand_score, 0) / scored.length) : null;
    const needsReview = runs.filter((run) => run.status === "awaiting_approval").length;
    const contentCount = runs.length * 5;
    return { mean, needsReview, contentCount };
  }, [runs]);
  const launch = (event) => {
    event.preventDefault();
    onNewRun(theme);
  };

  return (
    <div className="page-content dashboard-page">
      <section className="welcome-banner">
        <div className="welcome-copy">
          <span className="eyebrow"><span className="eyebrow-line" /> YOUR BRAND, IN GOOD COMPANY</span>
          <h1>Make this week<br />a <em>brand</em> moment.</h1>
          <p>One thoughtful campaign at a time. Your crew creates, you shape it, and it gets smarter every week.</p>
          <form className="launch-form" onSubmit={launch}>
            <Sparkles size={17} />
            <input value={theme} onChange={(event) => setTheme(event.target.value)} placeholder="What should we create this week?" aria-label="Campaign theme" />
            <button type="submit"><Plus size={16} /> New campaign</button>
          </form>
          <div className="banner-caption"><span className="avatar-stack"><i>L</i><i>✦</i><i>✹</i></span> Meet your creative crew <ArrowRight size={13} /></div>
        </div>
        <div className="banner-art" aria-hidden="true">
          <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
          <div className="art-glow" />
          <div className="art-card art-card-back"><span className="art-tiny">WEEKLY BRIEF</span><span className="art-lines"><i /><i /><i /></span><span className="art-sun">✦</span></div>
          <div className="art-card art-card-front"><span className="art-tag">YOUR NEXT BIG IDEA</span><strong>Good things<br />grow together.</strong><span className="art-pill">✷ &nbsp; MADE WITH BRANDCREW</span></div>
          <div className="art-sticker sticker-top">✦</div><div className="art-sticker sticker-side">↗</div>
        </div>
      </section>

      {error && <div className="inline-alert"><Activity size={16} /> {error} <span>Check that the backend is running at port 8000.</span></div>}

      <section className="stat-grid">
        <div className="stat-card"><div className="stat-top"><span>Campaigns created</span><span className="stat-icon purple"><Megaphone size={17} /></span></div><strong>{runs.length}</strong><small>{runs.length ? "Your crew is on a roll" : "Your first one is waiting"}</small></div>
        <div className="stat-card"><div className="stat-top"><span>Average brand score</span><span className="stat-icon green"><ShieldCheck size={17} /></span></div><strong>{stats.mean ?? "—"}{stats.mean != null && <small className="stat-unit">/100</small>}</strong><small>{stats.mean != null ? "Across reviewed content" : "Scores show up after review"}</small></div>
        <div className="stat-card"><div className="stat-top"><span>Ready for your eyes</span><span className="stat-icon amber"><Clock3 size={17} /></span></div><strong>{stats.needsReview}</strong><small>{stats.needsReview ? "A little human magic needed" : "Nothing on your review list"}</small></div>
        <div className="stat-card"><div className="stat-top"><span>Pieces of content</span><span className="stat-icon blue"><FileText size={17} /></span></div><strong>{stats.contentCount}</strong><small>Landing, blog & social posts</small></div>
      </section>

      <div className="dashboard-columns">
        <section className="panel trend-panel">
          <div className="panel-heading"><div><span className="section-kicker">THE BIG PICTURE</span><h2>Brand consistency</h2></div><span className="panel-caption"><span className="chart-legend-dot" /> Average score</span></div>
          <ScoreChart runs={runs} />
          <div className="chart-footer"><span>Every campaign makes the next one a little more <b>you.</b></span><span className="trend-foot"><Activity size={14} /> LIVE TREND</span></div>
        </section>
        <section className="panel crew-panel">
          <div className="panel-heading"><div><span className="section-kicker">YOUR CREATIVE TEAM</span><h2>Meet the crew</h2></div><span className="crew-live"><span /> 6 agents</span></div>
          <div className="crew-list">
            {[["✳", "The Strategist", "Finds your next big angle", "lavender"], ["⌕", "SEO Researcher", "Gets you seen out there", "mint"], ["✎", "The Copywriter", "Turns ideas into stories", "peach"], ["◈", "Brand Editor", "Keeps every word on-brand", "sky"]].map(([symbol, name, role, color]) => (
              <div className="crew-row" key={name}><span className={`crew-avatar ${color}`}>{symbol}</span><span><b>{name}</b><small>{role}</small></span><span className="agent-status"><i /> Ready</span></div>
            ))}
          </div>
          <button className="text-link crew-memory-link" onClick={() => window.location.hash = "#/memory"}>See what your crew has learned <ArrowRight size={14} /></button>
        </section>
      </div>

      <section className="panel campaign-panel">
        <div className="panel-heading campaign-heading"><div><span className="section-kicker">THE LATEST & GREATEST</span><h2>Your campaigns</h2></div><button className="text-link" onClick={() => window.location.hash = "#/campaigns"}>All campaigns <ArrowRight size={14} /></button></div>
        {loading && !runs.length ? <div className="loading-row"><LoaderCircle className="spin" size={19} /> Fetching your campaigns…</div>
          : runs.length ? <CampaignTable runs={runs.slice(0, 5)} onOpenRun={onOpenRun} />
            : <EmptyState icon={Megaphone} title="Your first campaign starts here" text="Give your crew a theme and they’ll put together a complete weekly campaign." action={<button className="button button-primary" onClick={() => document.querySelector(".launch-form input")?.focus()}>Start with an idea <ArrowRight size={15} /></button>} />}
      </section>
      <footer className="page-foot"><span>Thoughtfully made for <b>your brand.</b></span><span><Command size={12} /> YOUR CREW, YOUR CALL</span></footer>
    </div>
  );
}

function CampaignTable({ runs, onOpenRun }) {
  return (
    <div className="table-scroll"><table className="campaign-table">
      <thead><tr><th>CAMPAIGN</th><th>STATUS</th><th>BRAND SCORE</th><th>CREATED</th><th /></tr></thead>
      <tbody>{runs.map((run) => (
        <tr key={run.id} onClick={() => onOpenRun(run.id)}>
          <td><span className="campaign-cell"><span className="campaign-thumb"><Sparkles size={16} /></span><span><b>{run.theme_override || `Weekly campaign · ${run.week_id}`}</b><small>{run.week_id} <span>·</span> {run.plan?.primary_keyword || "Brand campaign"}</small></span></span></td>
          <td><StatusPill status={run.status} /></td>
          <td><Score value={run.avg_brand_score} /></td>
          <td className="date-cell">{dateLabel(run.created_at)}</td>
          <td><button className="row-open" aria-label="Open campaign"><ArrowRight size={16} /></button></td>
        </tr>
      ))}</tbody>
    </table></div>
  );
}

function Campaigns({ runs, onOpenRun, loading }) {
  const [filter, setFilter] = useState("all");
  const filtered = filter === "all" ? runs : runs.filter((run) => run.status === filter);
  return <div className="page-content">
    <div className="page-title-row"><div><span className="section-kicker">YOUR CREATIVE HISTORY</span><h1>Campaigns</h1><p>Every campaign your crew has brought to life.</p></div><button className="button button-primary" onClick={() => window.location.hash = "#/dashboard"}><Plus size={16} /> New campaign</button></div>
    <div className="filter-row"><div className="filter-tabs">{[["all", "All campaigns"], ["awaiting_approval", "Needs review"], ["analyzed", "Complete"]].map(([id, label]) => <button key={id} className={filter === id ? "filter-active" : ""} onClick={() => setFilter(id)}>{label}{id === "all" && <span>{runs.length}</span>}</button>)}</div><span className="results-caption">{filtered.length} campaigns</span></div>
    <section className="panel campaign-panel">
      {loading && !runs.length ? <div className="loading-row"><LoaderCircle className="spin" size={19} /> Fetching your campaigns…</div>
        : filtered.length ? <CampaignTable runs={filtered} onOpenRun={onOpenRun} />
          : <EmptyState icon={Search} title="No campaigns in this view" text="Try another filter, or kick off a new idea." />}
    </section>
  </div>;
}

function RunDetail({ runId, onBack, onRefresh, refreshing }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeOutput, setActiveOutput] = useState("");
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState({});
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [notice, setNotice] = useState("");

  const loadDetail = useCallback(async () => {
    try {
      const result = await api.run(runId);
      setDetail(result);
      setError("");
      setDrafts(Object.fromEntries((result.outputs || []).map((output) => [output.id, output.approval])));
      setActiveOutput((current) => current || result.outputs?.[0]?.id || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    setLoading(true);
    loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (!["queued", "running", "analyzing"].includes(detail?.run?.status)) return undefined;
    const timer = window.setInterval(loadDetail, 2500);
    return () => window.clearInterval(timer);
  }, [detail?.run?.status, loadDetail]);

  const outputs = detail?.outputs || [];
  const selected = outputs.find((output) => output.id === activeOutput) || outputs[0];
  const approved = outputs.filter((output) => output.approval === "approved");
  const decisions = outputs.filter((output) => (drafts[output.id] ?? output.approval) !== output.approval);

  const saveApprovals = async () => {
    setSaving(true);
    setNotice("");
    try {
      const result = await api.approve(runId, outputs.map((output) => ({
        output_id: output.id,
        approval: drafts[output.id] ?? output.approval,
      })));
      setDetail(result);
      setDrafts(Object.fromEntries(result.outputs.map((output) => [output.id, output.approval])));
      setNotice("Your review has been saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const submitFeedback = async () => {
    setSaving(true);
    setNotice("");
    try {
      const ratings = approved.filter((output) => feedback[output.id]).map((output) => ({
        output_id: output.id,
        thumbs: feedback[output.id],
        note: feedbackNote,
      }));
      await api.feedback(runId, { ratings, metrics: [] });
      setFeedbackSent(true);
      setNotice("Thanks — your crew is learning from this campaign.");
      await loadDetail();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="page-content"><div className="loading-card"><LoaderCircle className="spin" size={22} /> Opening your campaign…</div></div>;
  if (error && !detail) return <div className="page-content"><button className="back-link" onClick={onBack}><ChevronLeft size={16} /> All campaigns</button><div className="inline-alert">{error}</div></div>;
  const run = detail?.run || {};
  const reviewable = ["awaiting_approval", "approved", "analyzed"].includes(run.status);
  const report = selected?.editor_report;

  return <div className="page-content detail-page">
    <button className="back-link" onClick={onBack}><ChevronLeft size={16} /> All campaigns</button>
    <div className="detail-title-row"><div><span className="section-kicker">{run.week_id || "WEEKLY CAMPAIGN"} · {dateLabel(run.created_at)}</span><h1>{run.theme_override || `Your campaign for ${run.week_id}`}</h1><p>Your crew’s latest work, ready for a human touch.</p></div>    <div className="detail-actions"><StatusPill status={run.status} /><button className="icon-button" onClick={loadDetail} aria-label="Refresh campaign"><RefreshCw size={16} className={refreshing ? "spin" : ""} /></button></div></div>
    {error && <div className="inline-alert">{error}</div>}
    {run.status === "failed" && <div className="inline-alert error-alert"><Activity size={16} /> Campaign failed: {run.error || "The crew could not finish this run."}</div>}
    {run.progress?.length > 0 && <div className="progress-strip">{run.progress.slice(-4).map((message, index) => <span key={`${message}-${index}`}><CheckCircle2 size={13} />{message}</span>)}</div>}
    {notice && <div className="success-alert"><CheckCircle2 size={16} />{notice}</div>}

    {outputs.length ? <>
      <div className="detail-summary">
        <div><span className="summary-icon"><FileText size={17} /></span><span><small>CAMPAIGN ASSETS</small><b>{outputs.length} pieces of content</b></span></div>
        <div><span className="summary-icon summary-score"><ShieldCheck size={17} /></span><span><small>AVERAGE BRAND SCORE</small><b>{run.avg_brand_score != null ? `${run.avg_brand_score} / 100` : "Review in progress"}</b></span></div>
        <div><span className="summary-icon summary-stars"><Sparkles size={17} /></span><span><small>CAMPAIGN ANGLE</small><b>{run.plan?.angles?.[0] || run.theme_override || "Brand storytelling"}</b></span></div>
      </div>

      <div className="review-layout">
        <section className="panel output-panel">
          <div className="output-tabs">{outputs.map((output) => {
            const meta = OUTPUTS[output.type] || { label: titleCase(output.type), icon: FileText };
            const Icon = meta.icon;
            return <button key={output.id} className={selected?.id === output.id ? "output-tab-active" : ""} onClick={() => setActiveOutput(output.id)}><Icon size={15} /><span>{meta.label}</span>{output.approval === "approved" && <Check size={12} className="tab-check" />}</button>;
          })}</div>
          {selected && <div className="output-body">
            <div className="output-toolbar"><span className="content-label"><span className="content-type-icon"><Sparkles size={14} /></span>{OUTPUTS[selected.type]?.label || titleCase(selected.type)}<span className="content-separator">/</span>{titleCase(selected.meta?.angle || "campaign draft")}</span><a className="icon-button" href={selected.content_path || "#"} target="_blank" rel="noreferrer" aria-label="Open generated file" onClick={(event) => { if (!selected.content_path) event.preventDefault(); }}><ExternalLink size={15} /></a></div>
            <div className={`content-preview ${selected.type === "landing" ? "landing-preview" : ""}`}>
              {selected.type === "landing" && selected.content_path
                ? <iframe title="Landing page preview" src={selected.content_path} />
                : <div className="text-content">{selected.content.split(/\n{2,}/).filter(Boolean).map((paragraph, index) => {
                  const headline = paragraph.trim().startsWith("#");
                  return headline
                    ? <h2 key={index}>{paragraph.replace(/^#+\s*/, "")}</h2>
                    : <p key={index}>{paragraph}</p>;
                })}</div>}
            </div>
            <div className="output-score-row"><div><span className="score-label">BRAND CONSISTENCY</span><Score value={selected.brand_score} large /></div><div className="output-score-caption"><ShieldCheck size={16} /><span>Scored against your<br />brand guidelines</span></div></div>
            {selected.findings?.length > 0 && <div className="findings"><h3><Activity size={15} /> Things to take a look at</h3>{selected.findings.map((finding, index) => <div className={`finding finding-${finding.severity || "low"}`} key={`${finding.rule}-${index}`}><span className="finding-severity">{finding.severity || "note"}</span><span><b>{titleCase(finding.rule || "Brand check")}</b><small>{finding.message || finding.original || finding.description || "Review this content against your guidelines."}</small></span></div>)}</div>}
            {report?.summary && <div className="editor-note"><b><Sparkles size={14} /> Your editor’s note</b><p>{report.summary}</p></div>}
          </div>}
        </section>
        <aside className="review-aside">
          <section className="panel review-card">
            <div className="aside-heading"><span className="aside-icon"><PenLine size={16} /></span><div><span className="section-kicker">THE HUMAN TOUCH</span><h2>Your review</h2></div></div>
            <p className="aside-intro">Keep what feels right. The crew learns from your decisions.</p>
            {reviewable ? <div className="approval-options">
              {[["approved", "Looks good", CheckCircle2, "option-approved"], ["needs_changes", "Needs a tweak", PenLine, "option-changes"], ["rejected", "Not for us", X, "option-rejected"]].map(([value, label, Icon, tone]) => <button key={value} className={`approval-option ${drafts[selected?.id] === value ? `approval-selected ${tone}` : ""}`} onClick={() => selected && setDrafts((current) => ({ ...current, [selected.id]: value }))}><Icon size={16} /><span>{label}</span>{drafts[selected?.id] === value && <Check size={14} className="approval-check" />}</button>)}
              <button className="button button-primary full-button" onClick={saveApprovals} disabled={saving || !decisions.length}>{saving ? <LoaderCircle size={16} className="spin" /> : <Check size={16} />}{decisions.length ? "Save review" : "Review saved"}</button>
              <span className="aside-footnote">{outputs.filter((output) => (drafts[output.id] ?? output.approval) !== "pending").length} of {outputs.length} reviewed</span>
            </div> : <div className="review-waiting"><Clock3 size={18} /><b>Your crew is at work</b><span>The review controls will be ready when the campaign is complete.</span></div>}
          </section>
          {approved.length > 0 && <section className="panel feedback-card">
            <div className="aside-heading"><span className="aside-icon feedback-icon"><Heart size={16} /></span><div><span className="section-kicker">HELP IT LEARN</span><h2>Quick feedback</h2></div></div>
            <p className="aside-intro">What did you think of the approved pieces?</p>
            {feedbackSent || run.status === "analyzed" ? <div className="learning-done"><CheckCircle2 size={17} />Your crew has learned from this one.</div>
              : <><div className="feedback-ratings">{approved.map((output) => <div key={output.id} className="feedback-row"><span>{OUTPUTS[output.type]?.label || titleCase(output.type)}</span><div><button className={feedback[output.id] === "up" ? "thumb-active-up" : ""} onClick={() => setFeedback((current) => ({ ...current, [output.id]: current[output.id] === "up" ? undefined : "up" }))} aria-label="Liked"><ThumbsUp size={15} /></button><button className={feedback[output.id] === "down" ? "thumb-active-down" : ""} onClick={() => setFeedback((current) => ({ ...current, [output.id]: current[output.id] === "down" ? undefined : "down" }))} aria-label="Needs improvement"><ThumbsDown size={15} /></button></div></div>)}</div><textarea className="feedback-note" value={feedbackNote} onChange={(event) => setFeedbackNote(event.target.value)} placeholder="Anything the crew should remember?" /><button className="button button-secondary full-button" disabled={saving} onClick={submitFeedback}>{saving ? <LoaderCircle size={15} className="spin" /> : <Send size={14} />} Share feedback</button></>}
          </section>}
          {selected?.visual_report && <section className="panel visual-card"><span className="section-kicker">VISUAL CHECK</span><h3><Image size={15} /> Visual brand review</h3><p>{selected.visual_report.summary || selected.visual_report.overall || "Your visuals have been checked against the brand."}</p></section>}
        </aside>
      </div>
    </> : <section className="panel empty-run-panel"><EmptyState icon={Sparkles} title={run.status === "failed" ? "Let’s try that again" : "The crew is getting started"} text={run.status === "failed" ? "Review the error above, then start a fresh campaign from your overview." : "Your agents are building this week’s campaign. This page will update automatically."} action={run.status === "failed" ? <button className="button button-secondary" onClick={onBack}>Back to overview</button> : <LoaderCircle size={17} className="spin" />} /></section>}
  </div>;
}

function BrandLibrary({ brand, loading, error, onLoad }) {
  useEffect(() => { if (!brand && !loading && !error) onLoad(); }, [brand, loading, error, onLoad]);
  const palette = brand?.palette?.colors || brand?.palette || {};
  const colors = Object.entries(palette).filter(([, value]) => typeof value === "string" && value.startsWith("#"));
  return <div className="page-content">
    <div className="page-title-row"><div><span className="section-kicker">THE HEART OF YOUR BRAND</span><h1>Brand library</h1><p>The foundations your crew uses to keep everything feeling like you.</p></div><span className="read-only-pill"><ShieldCheck size={14} /> READ ONLY</span></div>
    {error && <div className="inline-alert">{error}</div>}
    {loading ? <div className="loading-card"><LoaderCircle className="spin" size={21} /> Gathering your brand details…</div>
      : brand ? <div className="brand-grid">
        <section className="panel brand-identity"><div className="identity-avatar">{(brand.brand_name || "B").slice(0, 1)}</div><span className="section-kicker">YOUR BRAND</span><h2>{brand.brand_name}</h2><p>A clear point of view, carried through every campaign.</p><div className="identity-rule" /><div className="identity-meta"><span>VOICE & TONE</span><b>{brand.guidelines ? "Guidelines available" : "Not set up yet"}</b></div><div className="identity-meta"><span>VISUAL DIRECTION</span><b>{brand.visual_guidelines ? "Guidelines available" : "Not set up yet"}</b></div></section>
        <section className="panel brand-guide"><div className="panel-heading"><div><span className="section-kicker">THE WAY YOU SHOW UP</span><h2>Brand guidelines</h2></div><BookOpen size={17} className="heading-icon" /></div>{brand.guidelines ? <pre>{brand.guidelines}</pre> : <EmptyState icon={BookOpen} title="Add your brand guidelines" text="Place brand_guidelines.md in backend/data/brand to give your crew a voice." />}</section>
        <section className="panel brand-guide"><div className="panel-heading"><div><span className="section-kicker">WHAT YOU MAKE</span><h2>Product facts</h2></div><FileText size={17} className="heading-icon" /></div>{brand.product_facts ? <pre>{brand.product_facts}</pre> : <p className="empty-copy">Product details will appear here once added to the brand library.</p>}</section>
        <section className="panel brand-guide"><div className="panel-heading"><div><span className="section-kicker">THE VISUAL LANGUAGE</span><h2>Color palette</h2></div><Image size={17} className="heading-icon" /></div>{colors.length ? <div className="palette-list">{colors.map(([name, color]) => <div className="palette-color" key={name}><span style={{ backgroundColor: color }} /><span><b>{titleCase(name)}</b><small>{color}</small></span></div>)}</div> : <p className="empty-copy">Add a palette.json file under backend/data/brand/visual to show your brand colors.</p>}{brand.visual_guidelines && <pre className="visual-guidelines">{brand.visual_guidelines}</pre>}</section>
        <section className="panel banned-panel"><span className="aside-icon warning-icon"><ShieldCheck size={16} /></span><div><span className="section-kicker">WORDS TO LEAVE BEHIND</span><h2>Keep it authentic</h2><p>Your editor checks every draft against these phrases.</p></div><div className="phrase-tags">{brand.banned_phrases?.length ? brand.banned_phrases.map((phrase) => <span key={phrase}>{phrase}</span>) : <span className="empty-copy">No banned phrases added.</span>}</div></section>
      </div> : <EmptyState icon={BookOpen} title="Couldn't load your brand library" text={error || "Try again once your backend is running."} action={<button className="button button-secondary" onClick={onLoad}><RefreshCw size={15} /> Try again</button>} />}
  </div>;
}

function MemoryExplorer({ memoryEntries, loading, error, selectedScope, setSelectedScope, query, setQuery, loadMemory }) {
  useEffect(() => { loadMemory(selectedScope, query); }, [loadMemory, selectedScope]);
  return <div className="page-content">
    <div className="page-title-row"><div><span className="section-kicker">A CREW THAT REMEMBERS</span><h1>Crew memory</h1><p>A transparent look at what your agents know and learn.</p></div><span className="read-only-pill"><Fingerprint size={14} /> PRIVATE TO YOUR CREW</span></div>
    <div className="memory-layout">
      <section className="panel scope-panel"><span className="section-kicker">MEMORY SCOPES</span><h2>Browse by topic</h2><p>Each agent gets access only to the knowledge it needs.</p><div className="scope-list">{SCOPES.map((scope) => <button key={scope} className={selectedScope === scope ? "scope-active" : ""} onClick={() => setSelectedScope(scope)}><span className="scope-dot" /><span><b>{scope.split("/").filter(Boolean).map(titleCase).join(" / ")}</b><small>{scope}</small></span>{selectedScope === scope && <ChevronRight size={15} />}</button>)}</div><div className="scope-privacy"><ShieldCheck size={15} /><span><b>Protected knowledge</b><small>Core brand knowledge is read-only for agents.</small></span></div></section>
      <section className="panel memory-panel"><div className="panel-heading"><div><span className="section-kicker">READ ONLY · {selectedScope}</span><h2>Remembered knowledge</h2></div><span className="memory-total">{memoryEntries.length} {memoryEntries.length === 1 ? "entry" : "entries"}</span></div><form className="memory-search" onSubmit={(event) => { event.preventDefault(); loadMemory(selectedScope, query); }}><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search this scope…" /><button type="submit" disabled={loading}>{loading ? <LoaderCircle size={15} className="spin" /> : <ArrowRight size={15} />}</button></form>{error && <div className="inline-alert">{error}</div>}{loading ? <div className="loading-row"><LoaderCircle className="spin" size={18} /> Looking through the memory…</div> : memoryEntries.length ? <div className="memory-entries">{memoryEntries.map((entry, index) => <article className="memory-entry" key={`${entry.text}-${index}`}><span className="memory-entry-icon"><Sparkles size={14} /></span><div><p>{entry.text}</p>{entry.score != null && <small>Relevance score · {Number(entry.score).toFixed(2)}</small>}</div></article>)}</div> : <EmptyState icon={Fingerprint} title="A fresh page" text="There aren't any saved memories in this scope yet. Your crew builds knowledge as you work together." />}</section>
    </div>
  </div>;
}

export default function App() {
  const [location, setLocation] = useState(viewFromHash);
  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [brand, setBrand] = useState(null);
  const [brandLoading, setBrandLoading] = useState(false);
  const [brandError, setBrandError] = useState("");
  const [memoryEntries, setMemoryEntries] = useState([]);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryError, setMemoryError] = useState("");
  const [selectedScope, setSelectedScope] = useState(SCOPES[0]);
  const [memoryQuery, setMemoryQuery] = useState("overview");

  useEffect(() => {
    const update = () => setLocation(viewFromHash());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  const navigate = useCallback((page, runId) => {
    window.location.hash = runId ? `#/runs/${encodeURIComponent(runId)}` : `#/${page}`;
  }, []);

  const loadRuns = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const items = await api.runs();
      setRuns(items);
      setError("");
      setHealth("ok");
      if (!quiet) setLoadingRuns(false);
    } catch (err) {
      setError(err.message);
      setHealth("error");
      setLoadingRuns(false);
    } finally {
      if (!quiet) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadRuns();
    api.health().then((result) => setHealth(result.api === "ok" ? "ok" : "error")).catch(() => setHealth("error"));
  }, [loadRuns]);

  useEffect(() => {
    if (!runs.some((run) => ["queued", "running", "analyzing"].includes(run.status))) return undefined;
    const timer = window.setInterval(() => loadRuns(true), 3000);
    return () => window.clearInterval(timer);
  }, [runs, loadRuns]);

  const startRun = async (theme) => {
    if (starting) return;
    setStarting(true);
    setError("");
    try {
      const run = await api.startRun(theme);
      setRuns((current) => [run, ...current]);
      navigate("run", run.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setStarting(false);
    }
  };

  const loadBrand = useCallback(async () => {
    setBrandLoading(true);
    setBrandError("");
    try { setBrand(await api.brand()); }
    catch (err) { setBrandError(err.message); }
    finally { setBrandLoading(false); }
  }, []);

  const loadMemory = useCallback(async (scope, query = "overview") => {
    setMemoryLoading(true);
    setMemoryError("");
    try {
      const result = await api.memory(scope, query);
      setMemoryEntries(result.entries || []);
    } catch (err) {
      setMemoryEntries([]);
      setMemoryError(err.message);
    } finally { setMemoryLoading(false); }
  }, []);

  useEffect(() => {
    document.title = location.page === "run" ? "Campaign review — Brand Crew" : `${NAV.find((item) => item.id === location.page)?.label || "Overview"} — Brand Crew`;
  }, [location.page]);

  const refresh = () => {
    if (location.page === "run") return loadRuns();
    if (location.page === "brand") return loadBrand();
    if (location.page === "memory") return loadMemory(selectedScope, memoryQuery);
    return loadRuns();
  };

  return <div className="app-shell">
    <Sidebar page={location.page} navigate={navigate} mobileOpen={mobileOpen} closeMobile={() => setMobileOpen(false)} health={health} />
    <main className="main-area">
      <Header page={location.page} onMenu={() => setMobileOpen(true)} onRefresh={refresh} refreshing={refreshing} />
      {location.page === "run" ? <RunDetail key={location.runId} runId={location.runId} onBack={() => navigate("campaigns")} onRefresh={refresh} refreshing={refreshing} />
        : location.page === "campaigns" ? <Campaigns runs={runs} onOpenRun={(id) => navigate("run", id)} loading={loadingRuns} />
          : location.page === "brand" ? <BrandLibrary brand={brand} loading={brandLoading} error={brandError} onLoad={loadBrand} />
            : location.page === "memory" ? <MemoryExplorer memoryEntries={memoryEntries} loading={memoryLoading} error={memoryError} selectedScope={selectedScope} setSelectedScope={setSelectedScope} query={memoryQuery} setQuery={setMemoryQuery} loadMemory={loadMemory} />
              : <Dashboard runs={runs} onOpenRun={(id) => navigate("run", id)} onNewRun={startRun} loading={loadingRuns || starting} error={error} />}
    </main>
    {starting && <div className="toast"><LoaderCircle size={16} className="spin" /> Waking up your creative crew…</div>}
  </div>;
}
