import { useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Boxes,
  ChartNoAxesColumn,
  ChevronDown,
  CircleDollarSign,
  Code2,
  Database,
  FileText,
  Gauge,
  KeyRound,
  LayoutDashboard,
  Network,
  Play,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  UserRound,
  Zap,
} from "lucide-react";

type DemoPage = "overview" | "models" | "playground" | "activity" | "logs" | "usage" | "providers" | "keys" | "settings";
type Icon = typeof LayoutDashboard;
type ModelRow = { name: string; provider: string; context: string; input: string; output: string; latency: string; capability: string; accent: string };

const nav: Array<{ id: DemoPage; label: string; icon: Icon }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "models", label: "Models", icon: Boxes },
  { id: "playground", label: "Playground", icon: Play },
  { id: "activity", label: "Activity", icon: Activity },
  { id: "logs", label: "Logs", icon: FileText },
  { id: "usage", label: "Usage", icon: ChartNoAxesColumn },
  { id: "providers", label: "Providers", icon: Database },
  { id: "keys", label: "API Keys", icon: KeyRound },
  { id: "settings", label: "Settings", icon: Settings },
];

const spark = [34, 49, 29, 58, 41, 74, 50, 67, 43, 82, 54, 91, 63, 72, 46, 79];
const bars = [41, 55, 46, 67, 52, 71, 60, 38, 45, 66, 55, 48, 69, 44, 83, 58, 91, 62, 40, 73, 52, 68, 49, 77, 55, 61, 46, 72, 81, 62, 50];

const models: ModelRow[] = [
  { name: "GLM 5.3 Flash", provider: "Zhipu", context: "128K", input: "$0.032", output: "$0.091", latency: "721 ms", capability: "Text · Vision · Tools", accent: "violet" },
  { name: "DeepSeek V4 Flash", provider: "DeepSeek", context: "128K", input: "$0.019", output: "$0.046", latency: "640 ms", capability: "Text · Coding · Tools", accent: "blue" },
  { name: "Kimi K2.5", provider: "Moonshot", context: "1M", input: "$0.118", output: "$0.354", latency: "1.2 s", capability: "Text · Coding · Tools", accent: "green" },
  { name: "Gemini Flash", provider: "Google", context: "1M", input: "$0.046", output: "$0.138", latency: "993 ms", capability: "Text · Vision · Tools", accent: "cyan" },
  { name: "Claude Sonnet 3.7", provider: "Anthropic", context: "200K", input: "$0.083", output: "$0.415", latency: "1.4 s", capability: "Text · Vision · Tools", accent: "orange" },
  { name: "GPT-4.1 Mini", provider: "OpenAI", context: "1M", input: "$0.040", output: "$0.160", latency: "1.1 s", capability: "Text · Coding · Tools", accent: "slate" },
];

const requests = [
  ["10:24:17", "GLM 5.3 Flash", "Zhipu", "prod-1", "Success", "2.1K", "$0.032", "721 ms"],
  ["10:23:41", "Kimi K2.5", "Moonshot", "prod-1", "Success", "8.4K", "$0.118", "1.2 s"],
  ["10:23:03", "DeepSeek V4", "DeepSeek", "prod-2", "Success", "1.3K", "$0.019", "640 ms"],
  ["10:22:18", "Gemini Flash", "Google", "staging", "Success", "3.9K", "$0.046", "993 ms"],
  ["10:21:52", "GLM 5.3 Flash", "Zhipu", "prod-1", "Success", "6.2K", "$0.091", "1.1 s"],
  ["10:20:11", "Claude 3.7 Sonnet", "Anthropic", "prod-2", "Success", "4.8K", "$0.142", "2.3 s"],
  ["10:19:44", "GPT-4o Mini", "OpenAI", "prod-1", "Success", "1.1K", "$0.008", "412 ms"],
  ["10:18:27", "DeepSeek V4", "DeepSeek", "prod-3", "Error", "892", "$0.000", "1.8 s"],
];

const providers = [
  ["Nebius", "99.98%", "412 ms", "$0.15", "$0.60", "Qwen 3 · Llama 3 · +4"],
  ["OpenAI", "99.99%", "721 ms", "$0.50", "$1.50", "GPT-4.1 · GPT-4o · +3"],
  ["Google", "99.95%", "646 ms", "$0.30", "$1.20", "Gemini 1.5 · Gemini 2.5 · +2"],
  ["DeepSeek", "99.92%", "892 ms", "$0.14", "$0.28", "DeepSeek V3 · DeepSeek R1"],
  ["Anthropic", "99.89%", "754 ms", "$0.40", "$2.00", "Claude 3.7 · Claude 3.5 · +1"],
  ["Together", "99.91%", "703 ms", "$0.20", "$0.80", "Llama 3 · Qwen · +3"],
];

const keys = [
  ["Personal", "My personal key", "May 1, 2025", "2 hours ago", "$2.41", "12.4K", "$10.00", "All models"],
  ["Web App", "Production web app", "May 3, 2025", "5 minutes ago", "$3.21", "28.1K", "$50.00", "Selected (8)"],
  ["Sandbox", "Testing & experiments", "May 6, 2025", "1 day ago", "$0.67", "4.2K", "$5.00", "Selected (3)"],
  ["Internal Tools", "Internal automation", "May 10, 2025", "3 hours ago", "$1.12", "9.8K", "$20.00", "All models"],
];

export function PixelRouterDemo() {
  const [page, setPage] = useState<DemoPage>("overview");
  const [query, setQuery] = useState("");
  const visibleModels = useMemo(() => models.filter((model) => `${model.name} ${model.provider} ${model.capability}`.toLowerCase().includes(query.toLowerCase())), [query]);

  return <div className="pixel-demo-shell">
    <aside className="pixel-demo-sidebar">
      <div className="pixel-demo-brand"><div className="pixel-demo-mark"><Gauge size={19} /></div><div><strong>provider.</strong><span>AI ROUTER</span></div></div>
      <nav aria-label="Demo navigation">{nav.map((entry) => <button key={entry.id} type="button" className={page === entry.id ? "is-active" : ""} aria-label={entry.label} onClick={() => setPage(entry.id)}><entry.icon size={18} /><span>{entry.label}</span></button>)}</nav>
      <div className="pixel-demo-sidebar-bottom">
        <div className="pixel-demo-allowance"><span>Monthly Usage</span><strong>$6.82 <small>/ $10 used</small></strong><div><i style={{ width: "68%" }} /></div><small>$3.18 remaining · resets in 2 days</small></div>
        <div className="pixel-demo-user"><UserRound size={15} /><span>Demo workspace</span><b>DEMO</b></div>
      </div>
    </aside>
    <main className="pixel-demo-main">
      <div className="pixel-demo-topline"><span className="pixel-demo-badge"><Sparkles size={13} /> Demo data</span><button type="button">May 1, 2025 <span>→</span> May 31, 2025 <ChevronDown size={14} /></button></div>
      {page === "overview" && <OverviewPage />}
      {page === "models" && <ModelsPage query={query} setQuery={setQuery} rows={visibleModels} />}
      {page === "playground" && <PlaygroundPage />}
      {page === "activity" && <ActivityPage />}
      {page === "logs" && <LogsPage />}
      {page === "usage" && <UsagePage />}
      {page === "providers" && <ProvidersPage />}
      {page === "keys" && <KeysPage />}
      {page === "settings" && <SettingsPage />}
    </main>
  </div>;
}

function PageTitle({ title, description }: { title: string; description: string }) {
  return <header className="pixel-demo-title"><h1>{title}</h1><p>{description}</p></header>;
}

function Panel({ title, icon: Icon, action, className = "", children }: { title: string; icon?: Icon; action?: ReactNode; className?: string; children: ReactNode }) {
  return <section className={`pixel-demo-panel ${className}`}><div className="pixel-demo-panel-heading"><div>{Icon ? <Icon size={18} /> : null}<strong>{title}</strong></div>{action}</div>{children}</section>;
}

function Metric({ icon: Icon, label, value, delta, tone = "violet" }: { icon: Icon; label: string; value: string; delta: string; tone?: string }) {
  return <div className={`pixel-demo-metric tone-${tone}`}><div><Icon size={18} /><span>{label}</span></div><strong>{value}</strong><small>{delta}</small><div className="pixel-demo-spark">{spark.map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}</div></div>;
}

function Status({ ok = true, label }: { ok?: boolean; label?: string }) {
  return <span className={`pixel-demo-status ${ok ? "ok" : "error"}`}><i />{label ?? (ok ? "Success" : "Error")}</span>;
}

function BarChart() {
  return <div className="pixel-demo-chart"><div className="pixel-demo-y"><span>$1.5</span><span>$1.0</span><span>$0.5</span><span>$0.0</span></div><div className="pixel-demo-bars">{bars.map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}</div><div className="pixel-demo-x"><span>May 1</span><span>May 9</span><span>May 17</span><span>May 25</span><span>May 31</span></div></div>;
}

function RankRows() {
  const rows = [["GLM 5.3 Flash", "37%", "$2.52", "68"], ["DeepSeek V4 Flash", "28%", "$1.91", "52"], ["Kimi K2.5", "18%", "$1.23", "38"], ["Gemini Flash", "11%", "$0.75", "24"], ["Others", "6%", "$0.41", "14"]];
  return <div className="pixel-demo-rank">{rows.map((row, index) => <div key={row[0]}><span className={`model-dot model-${index}`} /><strong>{row[0]}</strong><div><i style={{ width: `${row[3]}%` }} /></div><span>{row[1]}</span><b>{row[2]}</b></div>)}</div>;
}

function OverviewPage() {
  return <>
    <PageTitle title="AI Router Dashboard" description="Route requests across multiple providers with the best price, performance, and reliability." />
    <div className="pixel-demo-tabs"><button className="is-active">Overview</button><button>Trends</button><button>Explore</button><button>Guardrails</button></div>
    <section className="pixel-demo-metrics"><Metric icon={Gauge} label="Requests" value="133,482" delta="↑ 12% vs. previous period" /><Metric icon={FileText} label="Tokens" value="42.1M" delta="↑ 28% vs. previous period" tone="cyan" /><Metric icon={Zap} label="Avg. Latency" value="842 ms" delta="↓ 18% vs. previous period" tone="green" /><Metric icon={CircleDollarSign} label="Monthly Usage" value="$6.82" delta="↑ 20% vs. previous period" /></section>
    <Panel title="Monthly Allowance" icon={CircleDollarSign} className="pixel-demo-allowance-wide" action={<span><b>$6.82</b> / $10.00 used</span>}><div className="pixel-demo-progress"><i style={{ width: "68%" }} /></div><div className="pixel-demo-progress-meta"><span>68% of monthly allowance used</span><span>$3.18 remaining · Resets in 2 days</span></div></Panel>
    <div className="pixel-demo-grid-2"><Panel title="Usage Over Time" icon={BarChart3} action={<span>Cost ($) · Daily</span>}><BarChart /></Panel><Panel title="Model Usage Breakdown" icon={Boxes} action={<button>View all →</button>}><RankRows /></Panel></div>
    <div className="pixel-demo-grid-2 lower"><Panel title="Provider Health" icon={Database}><table className="pixel-demo-table compact"><thead><tr><th>Provider</th><th>Status</th><th>Uptime</th><th>Latency</th></tr></thead><tbody>{providers.slice(0, 4).map((row) => <tr key={row[0]}><td>{row[0]}</td><td><Status label="Operational" /></td><td>{row[1]}</td><td>{row[2]}</td></tr>)}</tbody></table></Panel><Panel title="Recent Requests" icon={FileText}><RequestTable compact /></Panel></div>
  </>;
}

function ModelsPage({ query, setQuery, rows }: { query: string; setQuery: (value: string) => void; rows: ModelRow[] }) {
  return <>
    <PageTitle title="Models" description="Browse, compare, and route across the best models from multiple providers." />
    <div className="pixel-demo-toolbar"><label><Search size={16} /><input aria-label="Search models" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models, providers, or capabilities…" /></label>{["All", "Coding", "Reasoning", "Vision", "Fast", "Cheap"].map((label, index) => <button key={label} className={index === 0 ? "is-active" : ""}>{label}</button>)}</div>
    <Panel title="Featured Models" icon={Sparkles} className="featured" action={<button>View all models →</button>}><div className="pixel-demo-featured">{models.slice(0, 4).map((model) => <article key={model.name}><span className={`pixel-demo-model-icon ${model.accent}`}>{model.name.slice(0, 1)}</span><div><strong>{model.name}</strong><small>{model.provider}</small></div><p>{model.capability}</p><footer><span>{model.latency}</span><b>{model.input}</b></footer></article>)}</div></Panel>
    <div className="pixel-demo-model-layout"><Panel title="All Models" icon={Boxes} action={<span>{rows.length} models</span>}><table className="pixel-demo-table"><thead><tr><th>Model</th><th>Provider</th><th>Context</th><th>Input / Output</th><th>Latency</th><th>Capabilities</th></tr></thead><tbody>{rows.map((model) => <tr key={model.name}><td><strong>{model.name}</strong></td><td>{model.provider}</td><td>{model.context}</td><td>{model.input} / {model.output}</td><td className="good">{model.latency}</td><td><span className="pixel-demo-tag">{model.capability}</span></td></tr>)}</tbody></table></Panel><Panel title="Quick Compare" icon={Network} action={<button>Clear all</button>} className="compare">{models.slice(0, 3).map((model) => <div className="pixel-demo-compare-row" key={model.name}><span className={`pixel-demo-model-icon ${model.accent}`}>{model.name.slice(0, 1)}</span><div><strong>{model.name}</strong><small>{model.provider}</small></div><b>{model.input}</b></div>)}<div className="pixel-demo-compare-metrics"><span>Best latency <b>640 ms</b></span><span>Longest context <b>1M</b></span><span>Lowest input <b>$0.019</b></span></div><button className="pixel-demo-primary">Compare in Playground</button></Panel></div>
  </>;
}

function PlaygroundPage() {
  return <>
    <PageTitle title="Playground" description="Test prompts, compare models, and inspect cost, speed, and routing." />
    <div className="pixel-demo-tabs"><button className="is-active">Chat</button><button>Compare</button><button>Structured Output</button><button>Tools</button></div>
    <div className="pixel-demo-playground"><section><Panel title="System Prompt" icon={FileText}><textarea defaultValue="You are a helpful, concise AI assistant. Be accurate, cite sources when relevant, and use a clear, structured format." /></Panel><Panel title="User Message" icon={UserRound}><textarea defaultValue="Explain how AI routing works in simple terms, and why it’s useful. Give a short example." /><div className="pixel-demo-tool-row"><span>＋ Add file</span><span>◎ Web search</span><span>{"{}"} Code interpreter</span><span>▣ Knowledge base</span></div><button className="pixel-demo-run"><Play size={15} /> Run</button></Panel><Panel title="Assistant" icon={Sparkles} action={<span>DeepSeek V4 Flash · 640 ms</span>} className="pixel-demo-answer"><p>AI routing automatically selects the best model and provider for each request based on cost, performance, latency, and reliability.</p><p>Instead of always using the same model, the router evaluates your request and sends it to the most suitable option.</p><ul><li>Better model fit for each task</li><li>Lower cost when cheaper models are enough</li><li>Automatic fallback when a provider fails</li></ul></Panel></section><Panel title="Configuration" icon={Settings}><label>Model<select defaultValue="deepseek"><option value="deepseek">DeepSeek V4 Flash</option><option>GLM 5.3 Flash</option></select></label><label>Routing Mode<select><option>Auto (Best price, performance, reliability)</option></select></label><RangeLine label="Temperature" value="0.7" width="35%" /><RangeLine label="Max Tokens" value="2048" width="48%" /><div className="pixel-demo-toggle-grid"><span>JSON Mode <i /></span><span>Code Interpreter <i /></span><span>Web Search <i className="on" /></span><span>Knowledge Base <i /></span></div><div className="pixel-demo-token-box"><strong>Token & Cost Breakdown</strong><div><span>Input Tokens</span><b>412 (31%)</b></div><div><span>Output Tokens</span><b>912 (69%)</b></div><div><span>Estimated Cost</span><b>$0.019</b></div></div></Panel></div>
  </>;
}

function RangeLine({ label, value, width }: { label: string; value: string; width: string }) {
  return <div className="pixel-demo-range"><div><span>{label}</span><b>{value}</b></div><div><i style={{ width }} /></div></div>;
}

function ActivityPage() {
  return <><PageTitle title="Activity" description="Track requests, tokens, spend, latency, and routing trends across your workspace." /><section className="pixel-demo-metrics five"><Metric icon={CircleDollarSign} label="Total Spend" value="$43.72" delta="↑ 18%" tone="green" /><Metric icon={Gauge} label="Requests" value="133,482" delta="↑ 12%" /><Metric icon={FileText} label="Tokens" value="42.1M" delta="↑ 28%" tone="cyan" /><Metric icon={CircleDollarSign} label="Blended Cost / 1M" value="$1.039" delta="↓ 11%" /><Metric icon={Zap} label="Avg. Latency" value="842 ms" delta="↓ 18%" tone="green" /></section><div className="pixel-demo-grid-2"><Panel title="Spend Over Time" icon={BarChart3}><BarChart /></Panel><Panel title="Requests Over Time" icon={Activity}><BarChart /></Panel></div><div className="pixel-demo-grid-3"><Panel title="Provider Distribution" icon={Database}><RankRows /></Panel><Panel title="Model Usage" icon={Boxes}><RankRows /></Panel><Panel title="Anomalies & Errors" icon={ShieldCheck}><div className="pixel-demo-error-list"><span><b>Error</b> GPT-4o · Rate limit exceeded</span><span><b>Error</b> DeepSeek V4 · 502 Bad Gateway</span><span><i>Warn</i> GLM 5.3 · High latency</span></div></Panel></div></>;
}

function RequestTable({ compact = false }: { compact?: boolean }) {
  return <table className={`pixel-demo-table${compact ? " compact" : ""}`}><thead><tr><th>Time</th><th>Model</th><th>Provider</th>{compact ? null : <th>API Key</th>}<th>Status</th><th>Tokens</th><th>Cost</th><th>Latency</th></tr></thead><tbody>{requests.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td>{compact ? null : <td>{row[3]}</td>}<td><Status ok={row[4] === "Success"} /></td><td>{row[5]}</td><td>{row[6]}</td><td>{row[7]}</td></tr>)}</tbody></table>;
}

function LogsPage() {
  return <><PageTitle title="Logs" description="Inspect individual requests, responses, routing, and cost details." /><div className="pixel-demo-toolbar"><label><Search size={16} /><input placeholder="Search logs… (request ID, prompt, model, etc.)" /></label><button>All Models⌄</button><button>All Providers⌄</button><button>All API Keys⌄</button><button>All Statuses⌄</button></div><div className="pixel-demo-log-layout"><Panel title="Request Logs" icon={FileText} action={<span>1,248 requests</span>} className="log-list"><RequestTable /></Panel><Panel title="GLM 5.3 Flash" icon={Sparkles} action={<Status />} className="log-detail"><div className="pixel-demo-detail-grid"><div><span>Total Tokens</span><strong>2,148</strong></div><div><span>Cost</span><strong>$0.032</strong></div><div><span>Latency</span><strong>721 ms</strong></div><div><span>API Key</span><strong>prod-1</strong></div></div><div className="pixel-demo-route"><strong>Provider Routing Path</strong><div><span>provider.</span><b>→</b><span>DeepSeek</span><b>→</b><span>GLM 5.3 Flash</span></div><ul><li>Best price match</li><li>Healthy (99.9%)</li><li>Low latency region</li></ul></div><pre>{`{\n  "model": "glm-5.3-flash",\n  "temperature": 0.7\n}`}</pre></Panel></div></>;
}

function UsagePage() {
  return <><PageTitle title="Usage" description="Understand your monthly allowance, spend history, and projected remaining capacity." /><Panel title="Monthly AI Allowance" icon={CircleDollarSign} className="pixel-demo-usage-hero"><h2>$6.82 <small>/ $10.00 used</small></h2><div className="pixel-demo-progress"><i style={{ width: "68%" }} /></div><div className="pixel-demo-usage-stats"><span><b>$6.82</b> Used</span><span><b>$3.18</b> Remaining</span><span><b>2 days</b> Resets on</span><span><b>$9.04</b> Projected EOM</span></div></Panel><div className="pixel-demo-grid-2"><Panel title="Daily Spend" icon={BarChart3}><BarChart /></Panel><Panel title="Allowance History" icon={ChartNoAxesColumn}><div className="pixel-demo-months">{[55, 64, 59, 54, 65, 68].map((height, index) => <div key={index}><i style={{ height: `${height}%` }} /><span>{["Dec", "Jan", "Feb", "Mar", "Apr", "May"][index]}</span></div>)}</div></Panel></div><div className="pixel-demo-grid-3"><Panel title="Cost Breakdown by Model"><RankRows /></Panel><Panel title="Usage by Provider"><RankRows /></Panel><Panel title="Estimated Remaining Tokens"><div className="pixel-demo-token-list">{[["GLM 5.3 Flash", "~1.6M"], ["DeepSeek V4 Flash", "~1.1M"], ["Kimi K2.5", "~820K"], ["Gemini Flash", "~520K"]].map(([name, value]) => <span key={name}>{name}<b>{value}</b></span>)}</div></Panel></div></>;
}

function ProvidersPage() {
  return <><PageTitle title="Providers" description="Monitor provider health, cost, latency, and fallback routing." /><div className="pixel-demo-tabs"><button className="is-active">Overview</button><button>Health</button><button>Costs</button><button>Routing</button><button>Incidents</button></div><section className="pixel-demo-metrics"><Metric icon={Database} label="Active Providers" value="6 / 6" delta="all providers operational" /><Metric icon={ShieldCheck} label="Avg. Uptime" value="99.94%" delta="↑ 0.02%" tone="green" /><Metric icon={Zap} label="Avg. Latency" value="683 ms" delta="↓ 12%" tone="cyan" /><Metric icon={Network} label="Route Strategy" value="Balanced" delta="Cost + performance + reliability" /></section><Panel title="Providers" icon={Database}><table className="pixel-demo-table"><thead><tr><th>Provider</th><th>Status</th><th>Uptime</th><th>Latency</th><th>Input Cost</th><th>Output Cost</th><th>Supported Models</th></tr></thead><tbody>{providers.map((row) => <tr key={row[0]}><td><strong>{row[0]}</strong></td><td><Status label="Operational" /></td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td><td>{row[4]}</td><td><span className="pixel-demo-tag">{row[5]}</span></td></tr>)}</tbody></table></Panel><div className="pixel-demo-grid-2"><Panel title="Routing Preferences" icon={Network}><div className="pixel-demo-route-options">{[["Cheapest", "Lowest cost"], ["Fastest", "Lowest latency"], ["Balanced", "Best overall value"], ["Highest Availability", "Maximum reliability"]].map(([name, detail], index) => <button key={name} className={index === 2 ? "is-active" : ""}>{name}<small>{detail}</small></button>)}</div></Panel><Panel title="Provider Health" icon={ShieldCheck}><div className="pixel-demo-health-bars">{providers.map((row, index) => <div key={row[0]}><b>{row[1]}</b><i style={{ height: `${72 + index * 3}%` }} /><span>{row[0]}</span></div>)}</div></Panel></div></>;
}

function KeysPage() {
  return <><PageTitle title="API Keys" description="Create, manage, and monitor keys with spending and model limits." /><div className="pixel-demo-keys-layout"><Panel title="API Keys (4)" icon={KeyRound}><table className="pixel-demo-table"><thead><tr><th>Name</th><th>Created</th><th>Last Used</th><th>Spend</th><th>Requests</th><th>Limit</th><th>Permissions</th><th>Status</th></tr></thead><tbody>{keys.map((row) => <tr key={row[0]}><td><strong>{row[0]}</strong><small>{row[1]}</small></td><td>{row[2]}</td><td>{row[3]}</td><td>{row[4]}<span className="pixel-demo-mini-progress"><i style={{ width: `${row[0] === "Web App" ? 28 : 16}%` }} /></span></td><td>{row[5]}</td><td>{row[6]}</td><td><span className="pixel-demo-tag">{row[7]}</span></td><td><Status label="Active" /></td></tr>)}</tbody></table></Panel><Panel title="Create API Key" icon={KeyRound} className="pixel-demo-key-form"><div className="pixel-demo-form-tabs"><button className="is-active">Create New</button><button>Edit Key</button></div><label>Key Name<input placeholder="e.g. Web App, Production, Sandbox" /></label><div className="pixel-demo-form-2"><label>Monthly Limit (USD)<input defaultValue="10.00" /></label><label>Rate Limit (RPM)<input defaultValue="60" /></label></div><label>Allowed Models<select><option>All models</option></select></label><label>Expiration<select><option>Never expires</option></select></label><div className="pixel-demo-permissions"><button className="is-active">✓ Read<small>Make API requests</small></button><button>Write<small>Manage resources</small></button></div><button className="pixel-demo-primary"><Plus size={14} /> Create API Key</button></Panel></div><div className="pixel-demo-grid-2 lower"><Panel title="Top Keys by Spend" icon={BarChart3}><RankRows /></Panel><Panel title="Recent Key Activity" icon={Activity}><RequestTable compact /></Panel></div></>;
}

function SettingsPage() {
  const settingsPanels = ["Appearance", "Notifications", "Routing", "Provider Keys", "Privacy", "Developer"];
  return <><PageTitle title="Settings" description="Configure your account, alerts, appearance, routing defaults, and connected provider keys." /><div className="pixel-demo-settings-layout"><aside className="pixel-demo-settings-nav"><button className="is-active">Account</button>{settingsPanels.map((item) => <button key={item}>{item}</button>)}</aside><div className="pixel-demo-settings-grid"><Panel title="Profile Information" icon={UserRound}><label>Display Name<input defaultValue="Provider Demo" /></label><label>Email Address<input defaultValue="user@example.com" /></label></Panel><Panel title="Theme & Appearance" icon={Sparkles}><div className="pixel-demo-theme-row"><span>Theme</span><button>Light</button><button className="is-active">Dark</button><button>System</button></div><div className="pixel-demo-theme-row"><span>Accent</span><i className="purple" /><i className="blue" /><i className="cyan" /><i className="green" /></div></Panel><Panel title="Usage Alerts" icon={Activity}>{["50% usage alert", "75% usage alert", "90% usage alert", "100% usage alert"].map((label) => <div className="pixel-demo-setting-row" key={label}><span><strong>{label}</strong><small>Email + in-app notification</small></span><i className="toggle on" /></div>)}</Panel><Panel title="Default Routing" icon={Network}><div className="pixel-demo-route-options"><button>Best Price<small>Lowest cost</small></button><button className="is-active">Balanced<small>Cost + performance</small></button><button>Best Performance<small>Highest quality</small></button></div></Panel><Panel title="Connected Provider Keys" icon={Database}>{["OpenAI", "DeepSeek", "Google", "Anthropic", "xAI"].map((name, index) => <div className="pixel-demo-setting-row" key={name}><span><strong>{name}</strong><small>{index < 3 ? "Connected" : "Not connected"}</small></span><b className={index < 3 ? "good" : ""}>{index < 3 ? "● Connected" : "Add key"}</b></div>)}</Panel><Panel title="API & Developer Settings" icon={Code2}><label>API Base URL<div className="pixel-demo-copy-field"><code>https://api.provider.local/v1</code><button><Code2 size={13} /></button></div></label><label>Webhook URL<div className="pixel-demo-copy-field"><code>https://your-app.com/webhook</code><button><Code2 size={13} /></button></div></label></Panel></div></div></>;
}
