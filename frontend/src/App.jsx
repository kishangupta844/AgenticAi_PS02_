import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Briefcase,
  GitBranch,
  CheckCircle2,
  AlertCircle,
  XCircle,
  ExternalLink,
  RefreshCw,
  Upload,
  Terminal,
  ShieldCheck,
  Zap,
  TrendingUp,
  FileCode,
  Layers,
  ChevronRight,
  Code,
  Key,
  Sparkles,
  Video,
  BookOpen,
  Clock,
  Target,
  ArrowUpRight,
  Download,
  Calendar,
  CheckSquare,
  PlayCircle,
  MapPin,
  Printer,
  FileText
} from 'lucide-react';

import RepoCombobox from './components/RepoCombobox.jsx';
import { downloadReportAsPdf } from './utils/pdfGenerator.js';
import NaukriPage from './pages/NaukriPage.jsx';

const API_BASE = "/api/v1";

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [repos, setRepos] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [isRepoValid, setIsRepoValid] = useState(true);
  const [assessmentResult, setAssessmentResult] = useState(null);
  const [events, setEvents] = useState([]);
  const [history, setHistory] = useState([]);
  const [llmTest, setLlmTest] = useState(null);
  const [loading, setLoading] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const page = ({
    '/': 'dashboard',
    '/naukri': 'naukri',
    '/jobs': 'jobs',
    '/repos': 'repos',
    '/gap': 'gap',
    '/roadmap': 'roadmap',
    '/evidence': 'evidence',
    '/history': 'history',
    '/settings': 'settings',
  })[location.pathname] || 'dashboard';
  const [error, setError] = useState(null);

  // Gemini state
  const [geminiConfigured, setGeminiConfigured] = useState(false);
  const [maskedKey, setMaskedKey] = useState(null);
  const [inputGeminiKey, setInputGeminiKey] = useState("");

  // Form states
  const [rawJobText, setRawJobText] = useState(`Job Title: Staff Full-Stack AI Engineer
Company: Apex Innovations
Responsibilities:
- Build and scale high throughput REST APIs using FastAPI and Python.
- Architect schema migrations and relational storage in PostgreSQL.
- Package container images with Docker and orchestrate workloads.
- Write robust integration test suites and CI pipelines.`);
  const [sourceUrl, setSourceUrl] = useState("");
  const [loadingUrl, setLoadingUrl] = useState(false);
  const [newRepoFullName, setNewRepoFullName] = useState("tiangolo/fastapi");

  const [feedback, setFeedback] = useState(null); // { type: 'success' | 'error', message: string }

  useEffect(() => {
    loadInitialData();
    checkGeminiConfig();
  }, []);

  async function checkGeminiConfig() {
    try {
      const res = await fetch(`${API_BASE}/config`).then(r => r.json());
      setGeminiConfigured(res.gemini_configured);
      setMaskedKey(res.masked_key);
    } catch (e) {
      console.warn("Could not check Gemini config:", e);
    }
  }

  async function handleSaveGeminiKey(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!inputGeminiKey.trim()) {
      setFeedback({ type: 'error', message: "Please provide a valid Gemini API Key." });
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setFeedback(null);
      const res = await fetch(`${API_BASE}/config/gemini-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gemini_api_key: inputGeminiKey.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to update Gemini API Key");
      setFeedback({ type: 'success', message: "Gemini API Key configured successfully! Assessments will now use Gemini LLM." });
      setInputGeminiKey("");
      checkGeminiConfig();
    } catch (err) {
      setFeedback({ type: 'error', message: `Error setting Gemini key: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }

  async function loadInitialData() {
    try {
      setLoading(true);
      setError(null);
      const [jobsRes, reposRes, eventsRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/jobs/`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/repos/`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/webhooks/events`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/assessments/history`).then(r => r.json()).catch(() => []),
      ]);

      setJobs(Array.isArray(jobsRes) ? jobsRes : []);
      setRepos(Array.isArray(reposRes) ? reposRes : []);
      setEvents(Array.isArray(eventsRes) ? eventsRes : []);
      setHistory(Array.isArray(historyRes) ? historyRes : []);

      if (jobsRes.length > 0) setSelectedJob(jobsRes[0]);
      if (reposRes.length > 0) setSelectedRepo(reposRes[0]);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch initial backend state. Ensure FastAPI server is running on port 8000.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConnectRepo(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!newRepoFullName.trim()) {
      setFeedback({ type: 'error', message: "Please provide a valid repository name in 'owner/repo' format." });
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setFeedback(null);
      const res = await fetch(`${API_BASE}/repos/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: newRepoFullName.trim() })
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText);
      }
      const data = await res.json();
      setRepos(prev => [data, ...prev.filter(r => r.id !== data.id)]);
      setSelectedRepo(data);
      setFeedback({ type: 'success', message: `Repository connected successfully: ${data.full_name} (Commit: ${data.latest_commit_sha ? data.latest_commit_sha.slice(0, 8) : 'HEAD'})` });
    } catch (err) {
      setFeedback({ type: 'error', message: `Error connecting repository: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }

  function handleDownloadRepo(repo) {
    const target = repo || selectedRepo;
    if (!target || !target.full_name) {
      setFeedback({ type: 'error', message: "No repository selected to download." });
      return;
    }
    const ref = target.latest_commit_sha || target.default_branch || 'main';
    const downloadUrl = `https://github.com/${target.full_name}/archive/${ref}.zip`;
    window.open(downloadUrl, '_blank', 'noopener,noreferrer');
    setFeedback({
      type: 'success',
      message: `Downloading repository archive for ${target.full_name} (${ref.slice(0, 7)})...`
    });
  }

  async function handleFetchAndSummarizeUrl(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!sourceUrl.trim()) {
      setFeedback({ type: 'error', message: "Please enter a valid job URL to fetch and summarize." });
      return;
    }
    try {
      setLoading(true);
      setLoadingUrl(true);
      setError(null);
      setFeedback({ type: 'info', message: `Fetching ${sourceUrl.trim()} and summarizing with Groq AI...` });

      const res = await fetch(`${API_BASE}/jobs/fetch-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: sourceUrl.trim(),
          save_job: true,
          raw_text: rawJobText.trim() || undefined
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();

      // Update raw job text in description area with short necessary summarized data
      if (data.summary_text) {
        setRawJobText(data.summary_text);
      }

      // Directly set in the Target Job Profile part on the top
      if (data.job) {
        setJobs(prev => [data.job, ...prev.filter(j => j.id !== data.job.id)]);
        setSelectedJob(data.job);
        setFeedback({
          type: 'success',
          message: `Job #${data.job.id} "${data.job.title}" (${data.job.company || 'Direct'}) summarized by Groq AI (${data.llm_model || 'Groq'}) and directly set in Target Job Profile above!`
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    } catch (err) {
      let msg = err.message || "";
      const isNetworkError = err.name === 'TypeError' && (msg.toLowerCase() === 'failed to fetch' || msg.includes('networkerror') || msg === 'load failed');
      if (isNetworkError) {
        msg = "Backend server is not reachable. Please verify the backend API server is running on port 8000.";
      }
      setFeedback({ type: 'error', message: `Error summarizing job URL: ${msg}` });
    } finally {
      setLoading(false);
      setLoadingUrl(false);
    }
  }

  async function handleSummarizeText(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!rawJobText || !rawJobText.trim() || rawJobText.trim().length < 20) {
      setFeedback({ type: 'error', message: "Please enter or paste at least 20 characters of job description text to summarize." });
      return;
    }
    try {
      setLoading(true);
      setLoadingUrl(true);
      setError(null);
      setFeedback({ type: 'info', message: "Summarizing job description text with Groq AI..." });

      const res = await fetch(`${API_BASE}/jobs/summarize-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_text: rawJobText.trim(),
          source_url: sourceUrl.trim() || undefined,
          save_job: true
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();

      if (data.summary_text) {
        setRawJobText(data.summary_text);
      }

      if (data.job) {
        setJobs(prev => [data.job, ...prev.filter(j => j.id !== data.job.id)]);
        setSelectedJob(data.job);
        setFeedback({
          type: 'success',
          message: `Job #${data.job.id} "${data.job.title}" (${data.job.company || 'Direct'}) summarized by Groq AI (${data.llm_model || 'Groq'}) and directly set in Target Job Profile above!`
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    } catch (err) {
      let msg = err.message || "";
      const isNetworkError = err.name === 'TypeError' && (msg.toLowerCase() === 'failed to fetch' || msg.includes('networkerror') || msg === 'load failed');
      if (isNetworkError) {
        msg = "Backend server is not reachable. Please verify the backend API server is running on port 8000.";
      }
      setFeedback({ type: 'error', message: `Error summarizing job text: ${msg}` });
    } finally {
      setLoading(false);
      setLoadingUrl(false);
    }
  }

  async function handleImportJob(e) {
    if (e && e.preventDefault) e.preventDefault();
    const hasUrl = Boolean(sourceUrl && sourceUrl.trim());
    const hasText = Boolean(rawJobText && rawJobText.trim());

    if (!hasUrl && !hasText) {
      setFeedback({ type: 'error', message: "Please enter a Job Source URL or paste job description text." });
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setFeedback(null);

      const res = await fetch(`${API_BASE}/jobs/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_url: sourceUrl.trim() || undefined,
          raw_text: hasText ? rawJobText.trim() : undefined
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();

      if (data.raw_text) {
        setRawJobText(data.raw_text);
      }

      setJobs(prev => [data, ...prev.filter(j => j.id !== data.id)]);
      setSelectedJob(data);
      setFeedback({
        type: 'success',
        message: `Job #${data.id} "${data.title}" (${data.company || 'Direct'}) parsed by ${data.llm_model || data.extraction_source || 'extractor'} and directly set in Target Job Profile above! Extracted ${data.requirements?.length || 0} requirements.`
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      let msg = err.message || "";
      const isNetworkError = err.name === 'TypeError' && (msg.toLowerCase() === 'failed to fetch' || msg.includes('networkerror') || msg === 'load failed');
      if (isNetworkError) {
        msg = "Backend server is not reachable. Please verify the backend API server is running on port 8000.";
      }
      setFeedback({ type: 'error', message: `Error parsing job requirements: ${msg}` });
    } finally {
      setLoading(false);
    }
  }

  async function handleRunAssessment() {
    if (!selectedJob || !selectedRepo) {
      setFeedback({ type: 'error', message: "Please select both a Target Job and a Connected Repository from the dropdowns above." });
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setFeedback(null);
      const res = await fetch(`${API_BASE}/assessments/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: selectedJob.id, repo_id: selectedRepo.id })
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText);
      }
      const data = await res.json();
      setAssessmentResult(data);
      setFeedback({ type: 'success', message: `Assessment complete: ${data.summary?.overall_match_percentage}% Match (${data.summary?.met} Met, ${data.summary?.partial} Partial, ${data.summary?.unmet} Unmet, ${data.summary?.needs_review || 0} Needs Review)` });
    } catch (err) {
      setFeedback({ type: 'error', message: `Assessment failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }

  async function handleTriggerPoll() {
    if (!selectedRepo) {
      setFeedback({ type: 'error', message: "Please select a repository to poll." });
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setFeedback(null);
      const res = await fetch(`${API_BASE}/webhooks/poll/${selectedRepo.id}`, { method: "POST" });
      const data = await res.json();
      setFeedback({ type: 'success', message: `Polled repository '${selectedRepo.full_name}': ${data.message || (data.changed ? 'New commits detected & reassessed' : 'Already at latest commit')}` });
      loadInitialData();
    } catch (err) {
      setFeedback({ type: 'error', message: `Polling check failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navigation */}
      <header style={{
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        padding: '14px 32px',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)'
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 38,
              height: 38,
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #e11d48, #be123c)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(225, 29, 72, 0.35)'
            }}>
              <Zap size={22} color="#fff" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.2rem', lineHeight: 1.2 }}>TrueSkill</h1>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Deterministic Skill Verification & Gap Analysis</p>
            </div>
          </div>

          <nav style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
            <NavLink to="/" end className="nav-link"><Layers size={15} /> Dashboard</NavLink>
            <NavLink to="/naukri" className="nav-link"><Briefcase size={15} /> Naukri Hub</NavLink>
            <NavLink to="/jobs" className="nav-link"><FileCode size={15} /> Jobs</NavLink>
            <NavLink to="/repos" className="nav-link"><GitBranch size={15} /> Repositories</NavLink>
            <NavLink to="/gap" className="nav-link"><TrendingUp size={15} /> Skill Gap</NavLink>
            <NavLink to="/roadmap" className="nav-link"><Calendar size={15} /> 15-Day Roadmap</NavLink>
            <NavLink to="/evidence" className="nav-link"><CheckCircle2 size={15} /> Evidence</NavLink>
            <NavLink to="/history" className="nav-link"><Terminal size={15} /> History</NavLink>
            <NavLink to="/settings" className="nav-link"><Sparkles size={15} /> Settings {geminiConfigured ? "✓" : ""}</NavLink>
            <button id="refresh-btn" onClick={() => { loadInitialData(); checkGeminiConfig(); }} className="btn btn-secondary" title="Refresh Data">
              <RefreshCw size={16} className={loading ? "pulse" : ""} />
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main style={{ maxWidth: 1400, margin: '0 auto', padding: '28px 32px', width: '100%', flex: 1 }}>

        {/* Selection Bar */}
        <section className="glass-panel" style={{ padding: '18px 24px', marginBottom: 28, display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <label htmlFor="select-job" style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700 }}>
                1. Target Job Profile
              </label>
              {selectedJob && (
                <span style={{ fontSize: '0.72rem', color: 'var(--accent-primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Sparkles size={11} /> Active Target
                </span>
              )}
            </div>
            <select
              id="select-job"
              value={selectedJob ? selectedJob.id : ''}
              onChange={e => setSelectedJob(jobs.find(j => j.id === parseInt(e.target.value)))}
              style={{
                width: '100%',
                padding: '9px 12px',
                background: 'var(--bg-secondary)',
                border: selectedJob ? '1px solid rgba(225, 29, 72, 0.4)' : '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-main)',
                fontFamily: 'inherit',
                fontSize: '0.9rem',
                boxShadow: selectedJob ? '0 0 0 1px rgba(225, 29, 72, 0.15)' : 'none'
              }}
            >
              {jobs.map(j => (
                <option key={j.id} value={j.id}>
                  #{j.id} - {j.title} ({j.company || 'Direct Posting'})
                </option>
              ))}
              {jobs.length === 0 && <option value="">No jobs imported yet</option>}
            </select>
          </div>

          <div style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="select-repo-combobox" style={{ display: 'block', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6, fontWeight: 700 }}>
              2. Connected GitHub Repository
            </label>
            <RepoCombobox
              repos={repos}
              selectedRepo={selectedRepo}
              onChange={repo => setSelectedRepo(repo)}
              onValidationChange={isValid => setIsRepoValid(isValid)}
              apiBase={API_BASE}
            />
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', paddingTop: 18 }}>
            <button
              id="run-assessment-btn"
              onClick={handleRunAssessment}
              disabled={loading || !selectedJob || !selectedRepo || !isRepoValid}
              className="btn btn-primary"
            >
              <Zap size={16} /> Run Full Assessment
            </button>
            <button
              id="poll-repo-btn"
              onClick={handleTriggerPoll}
              disabled={loading || !selectedRepo || !isRepoValid}
              className="btn btn-secondary"
              title="Poll GitHub for latest commit changes"
            >
              <RefreshCw size={15} /> Poll Repo
            </button>
            <button
              id="download-repo-btn"
              onClick={() => handleDownloadRepo(selectedRepo)}
              disabled={!selectedRepo || !selectedRepo.full_name}
              className="btn btn-secondary"
              title="Download repository source as .zip archive"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Download size={15} /> Download Repo
            </button>
            {assessmentResult && (
              <button
                id="download-pdf-btn"
                onClick={() => downloadReportAsPdf({ assessmentResult })}
                className="btn btn-secondary"
                title="Download Assessment & 15-Day Roadmap as PDF"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  color: 'var(--accent-primary)',
                  borderColor: 'rgba(225, 29, 72, 0.3)'
                }}
              >
                <FileText size={15} /> Download PDF
              </button>
            )}
          </div>
        </section>

        {feedback && (
          <div style={{
            background: feedback.type === 'success' ? 'var(--status-met-bg)' : 'var(--status-unmet-bg)',
            border: `1px solid ${feedback.type === 'success' ? 'var(--status-met-border)' : 'var(--status-unmet-border)'}`,
            borderRadius: 'var(--radius-md)',
            padding: '14px 18px',
            marginBottom: 24,
            color: feedback.type === 'success' ? 'var(--status-met)' : 'var(--status-unmet)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 500 }}>
              {feedback.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
              <span>{feedback.message}</span>
            </div>
            <button
              onClick={() => setFeedback(null)}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit', fontWeight: 700 }}
            >
              ✕
            </button>
          </div>
        )}

        {error && (
          <div style={{
            background: 'var(--status-unmet-bg)',
            border: '1px solid var(--status-unmet-border)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 18px',
            marginBottom: 24,
            color: 'var(--status-unmet)',
            display: 'flex',
            alignItems: 'center',
            gap: 12
          }}>
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        {/* TAB 1: ASSESSMENT & GAP ANALYSIS */}
        {page === 'dashboard' && (
          <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 18 }}>
            {[
              ['Jobs imported', jobs.length],
              ['Repositories', repos.length],
              ['Webhook events', events.length],
              ['Status changes', history.length],
            ].map(([label, value]) => (
              <div key={label} className="glass-panel" style={{ padding: 22 }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
                <div style={{ fontSize: '2.2rem', fontWeight: 800 }}>{value}</div>
              </div>
            ))}
            <div className="glass-panel" style={{ padding: 22, gridColumn: '1 / -1' }}>
              <h2 style={{ fontSize: '1.1rem', marginBottom: 8 }}>Latest assessment</h2>
              {assessmentResult ? (
                <p>{assessmentResult.job_title} against {assessmentResult.repo_full_name}: {assessmentResult.summary?.overall_match_percentage}% match. {assessmentResult.skill_assessments?.filter(s => s.llm_used).length || 0} skills decided by Gemini.</p>
              ) : (
                <p style={{ color: 'var(--text-muted)' }}>No assessment yet. Import a job, connect a repository, then open Skill Gap.</p>
              )}
              <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                <button className="btn btn-primary" onClick={() => navigate('/gap')}><Zap size={15} /> Skill Gap</button>
                <button className="btn btn-secondary" onClick={() => navigate('/settings')}><Sparkles size={15} /> Gemini settings</button>
              </div>
            </div>
          </div>
        )}

        {page === 'gap' && (
          <div className="animate-fade-in">
            {assessmentResult ? (
              <div>
                {/* Summary Metrics */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 18, marginBottom: 28 }}>
                  <div className="glass-panel" style={{ padding: '20px 24px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                      Match Score
                    </div>
                    <div style={{ fontSize: '2.4rem', fontWeight: 800, color: 'var(--accent-primary)' }}>
                      {assessmentResult.summary?.overall_match_percentage}%
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      Weighted: {assessmentResult.summary?.weighted_score} pts
                    </div>
                  </div>

                  <div className="glass-panel" style={{ padding: '20px 24px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                      Demonstrated (Met)
                    </div>
                    <div style={{ fontSize: '2.4rem', fontWeight: 800, color: 'var(--status-met)' }}>
                      {assessmentResult.summary?.met}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      Verified in executable code
                    </div>
                  </div>

                  <div className="glass-panel" style={{ padding: '20px 24px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                      Partial Skills
                    </div>
                    <div style={{ fontSize: '2.4rem', fontWeight: 800, color: 'var(--status-partial)' }}>
                      {assessmentResult.summary?.partial}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      Manifest / shallow references
                    </div>
                  </div>

                  <div className="glass-panel" style={{ padding: '20px 24px' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                      Gaps (Unmet)
                    </div>
                    <div style={{ fontSize: '2.4rem', fontWeight: 800, color: 'var(--status-unmet)' }}>
                      {assessmentResult.summary?.unmet}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      Target areas for project work
                    </div>
                  </div>
                </div>

                <div className="glass-panel" style={{
                    padding: '16px 20px',
                    marginBottom: 24,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 16,
                    background: 'linear-gradient(135deg, rgba(225, 29, 72, 0.05), rgba(99, 102, 241, 0.05))',
                    border: '1px solid rgba(225, 29, 72, 0.2)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                      <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
                        <Calendar size={22} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-main)' }}>
                          Personalized 15-Day Implementation Roadmap Available
                        </div>
                        <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                          Custom step-by-step daily code milestones tailored to your {assessmentResult.repo_full_name} gaps with verified video references.
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => navigate('/roadmap')}
                      className="btn btn-primary"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.88rem' }}
                    >
                      <Calendar size={16} /> View 15-Day Roadmap <ChevronRight size={16} />
                    </button>
                  </div>

                  {/* Skill Assessments List */}
                  <h2 style={{ fontSize: '1.25rem', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Layers size={20} color="var(--accent-primary)" /> Skill Breakdown & Verified Citations
                  </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {assessmentResult.skill_assessments?.map(skill => {
                    const isMet = skill.status === 'met';
                    const isPartial = skill.status === 'partial';
                    const isUnmet = skill.status === 'unmet';

                    return (
                      <div
                        key={skill.requirement_id}
                        className="glass-panel"
                        style={{
                          padding: 22,
                          borderLeft: `4px solid ${isMet ? 'var(--status-met)' : isPartial ? 'var(--status-partial)' : 'var(--status-unmet)'}`
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                              <h3 style={{ fontSize: '1.1rem' }}>{skill.requirement_title}</h3>
                              <span className="badge badge-cyan">{skill.category}</span>
                              <span className={`badge ${isMet ? 'badge-met' : isPartial ? 'badge-partial' : 'badge-unmet'}`}>
                                {isMet && <CheckCircle2 size={13} />}
                                {isPartial && <AlertCircle size={13} />}
                                {isUnmet && <XCircle size={13} />}
                                {skill.status === 'needs_review' && <AlertCircle size={13} />}
                                {skill.status.replace('_', ' ')}
                              </span>
                              <span className={`badge ${skill.llm_used ? 'badge-cyan' : 'badge-partial'}`} title={skill.llm_used ? 'Verdict produced by a real Gemini response' : 'LLM unavailable: deterministic fallback rules used'}>
                                <Sparkles size={12} /> {skill.llm_used ? (skill.llm_model || 'Gemini') : 'rule-based fallback'}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>
                              Job Excerpt: "{skill.source_snippet}"
                            </div>
                          </div>

                          <div style={{ textAlign: 'right' }}>
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', display: 'block' }}>Weight: {skill.weight}x</span>
                            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: isMet ? 'var(--status-met)' : isPartial ? 'var(--status-partial)' : 'var(--text-muted)' }}>
                              Confidence: {Math.round(skill.confidence_score * 100)}%
                            </span>
                          </div>
                        </div>

                        <p style={{ fontSize: '0.92rem', color: 'var(--text-main)', marginBottom: 14 }}>
                          {skill.reason}
                        </p>

                        {/* Citations section */}
                        {skill.citations && skill.citations.length > 0 && (
                          <div style={{ marginTop: 12, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', padding: 14, border: '1px solid var(--border-subtle)' }}>
                            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Code size={14} /> Deterministic Code Citations ({skill.citations.length})
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                              {skill.citations.map((c, idx) => (
                                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <FileCode size={16} color="var(--accent-primary)" />
                                    <span className="mono" style={{ fontSize: '0.85rem' }}>
                                      {c.file_path}<span style={{ color: '#d97706', fontWeight: 600 }}>#L{c.start_line}-L{c.end_line}</span>
                                    </span>
                                  </div>
                                  <a
                                    href={c.github_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none', fontSize: '0.8rem', fontWeight: 600 }}
                                  >
                                    View on GitHub <ExternalLink size={13} />
                                  </a>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* LEARN THIS: VERIFIED LEARNING RESOURCES (VIDEOS & DOCS) */}
                        {skill.resources && skill.resources.length > 0 && (
                          <div style={{
                            marginTop: 14,
                            background: '#f8fafc',
                            borderRadius: 'var(--radius-md)',
                            padding: 14,
                            border: '1px solid var(--border-subtle)'
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                              <div style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#0284c7', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <BookOpen size={14} /> Learn this: Real Verified Resources ({skill.resources.length})
                              </div>
                              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                                Links verified via HTTP/oEmbed
                              </span>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                              {skill.resources.map((res, rIdx) => (
                                <div
                                  key={rIdx}
                                  style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    background: '#ffffff',
                                    padding: '10px 14px',
                                    borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-subtle)',
                                    gap: 12
                                  }}
                                >
                                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                    {res.type === 'youtube' ? (
                                      <Video size={18} color="#ef4444" style={{ marginTop: 2, flexShrink: 0 }} />
                                    ) : (
                                      <BookOpen size={18} color="#0284c7" style={{ marginTop: 2, flexShrink: 0 }} />
                                    )}
                                    <div>
                                      <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#0f172a' }}>{res.title}</div>
                                      <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
                                        <span>{res.channel_or_site || (res.type === 'youtube' ? 'YouTube' : 'Documentation')}</span>
                                        {res.duration_minutes && (
                                          <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                            <Clock size={11} /> {res.duration_minutes}m
                                          </span>
                                        )}
                                        {res.why_relevant && <span>• {res.why_relevant}</span>}
                                      </div>
                                    </div>
                                  </div>

                                  <a
                                    href={res.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-secondary"
                                    style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none', flexShrink: 0 }}
                                  >
                                    Open <ArrowUpRight size={13} />
                                  </a>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* TARGET PRACTICE TASK */}
                        {skill.practice_task && (
                          <div style={{
                            marginTop: 12,
                            padding: '10px 14px',
                            background: 'rgba(99, 102, 241, 0.08)',
                            borderLeft: '3px solid #6366f1',
                            borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                            fontSize: '0.86rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10
                          }}>
                            <Target size={16} color="#6366f1" style={{ flexShrink: 0 }} />
                            <span><strong>Target Practice Task:</strong> {skill.practice_task}</span>
                          </div>
                        )}

                        {/* Next Step / Action Plan */}
                        {skill.next_step && (
                          <div style={{
                            marginTop: 10,
                            padding: '10px 14px',
                            background: '#fff1f2',
                            borderLeft: '3px solid var(--accent-primary)',
                            borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                            fontSize: '0.88rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10
                          }}>
                            <Zap size={16} color="var(--accent-primary)" />
                            <span><strong>Actionable Next Step:</strong> {skill.next_step}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="glass-panel" style={{ padding: 48, textAlign: 'center' }}>
                <Briefcase size={44} color="var(--accent-primary)" style={{ margin: '0 auto 16px auto', display: 'block' }} />
                <h3 style={{ fontSize: '1.25rem', marginBottom: 8 }}>Ready for Skill Verification</h3>
                <p style={{ color: 'var(--text-muted)', maxWidth: 500, margin: '0 auto 20px auto', fontSize: '0.92rem' }}>
                  Select your target Job and connected Repository above, then click <strong>"Run Full Assessment"</strong> to run deterministic citation extraction and gap analysis.
                </p>
                <button onClick={handleRunAssessment} className="btn btn-primary">
                  <Zap size={16} /> Run Assessment Now
                </button>
              </div>
            )}
          </div>
        )}

        {/* TAB: 15-DAY ROADMAP */}
        {page === 'roadmap' && (
          <div className="animate-fade-in">
            {assessmentResult && assessmentResult.roadmap ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                {/* Roadmap Header Card */}
                <div className="glass-panel" style={{
                  padding: '24px 28px',
                  background: 'linear-gradient(135deg, rgba(225, 29, 72, 0.04), rgba(99, 102, 241, 0.04))',
                  border: '1px solid rgba(225, 29, 72, 0.2)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-primary)', fontWeight: 700, fontSize: '0.85rem', textTransform: 'uppercase', marginBottom: 6 }}>
                        <Calendar size={18} /> 15-Day Targeted Implementation Plan
                      </div>
                      <h2 style={{ fontSize: '1.5rem', marginBottom: 6 }}>{assessmentResult.roadmap.title}</h2>
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', maxWidth: 800 }}>
                        {assessmentResult.roadmap.summary}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                      <button
                        onClick={() => navigate('/gap')}
                        className="btn btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                      >
                        <TrendingUp size={15} /> Back to Skill Gap
                      </button>
                      <button
                        onClick={() => {
                          const jsonStr = JSON.stringify(assessmentResult.roadmap, null, 2);
                          const blob = new Blob([jsonStr], { type: 'application/json' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `roadmap-15days-${assessmentResult.repo_full_name.replace('/', '-')}.json`;
                          a.click();
                          URL.revokeObjectURL(url);
                        }}
                        className="btn btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                      >
                        <Download size={15} /> Export Plan JSON
                      </button>
                      <button
                        onClick={() => downloadReportAsPdf({ assessmentResult })}
                        className="btn btn-primary"
                        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                      >
                        <FileText size={15} /> Download PDF
                      </button>
                    </div>
                  </div>

                  <div style={{
                    marginTop: 20,
                    padding: '12px 16px',
                    background: '#ffffff',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    fontSize: '0.88rem'
                  }}>
                    <Target size={18} color="var(--accent-primary)" style={{ flexShrink: 0 }} />
                    <span><strong>Expected Outcome:</strong> {assessmentResult.roadmap.expected_outcome}</span>
                  </div>
                </div>

                {/* Phases & Daily Tasks */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  {assessmentResult.roadmap.phases?.map(phase => (
                    <div key={phase.phase_number} className="glass-panel" style={{ padding: 24 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14 }}>
                        <div>
                          <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700 }}>
                            Phase {phase.phase_number} • {phase.day_range}
                          </div>
                          <h3 style={{ fontSize: '1.2rem', marginTop: 2 }}>{phase.title}</h3>
                        </div>
                        <div style={{ fontSize: '0.82rem', padding: '4px 12px', background: 'var(--bg-secondary)', borderRadius: 9999, border: '1px solid var(--border-subtle)' }}>
                          Milestone: <strong style={{ color: 'var(--text-main)' }}>{phase.milestone}</strong>
                        </div>
                      </div>

                      {/* Daily Tasks List */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16 }}>
                        {phase.tasks?.map(task => (
                          <div
                            key={task.day}
                            style={{
                              background: '#ffffff',
                              border: '1px solid var(--border-subtle)',
                              borderRadius: 'var(--radius-md)',
                              padding: 18,
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
                            }}
                          >
                            <div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                <span style={{
                                  background: 'var(--accent-primary)',
                                  color: '#fff',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  padding: '2px 8px',
                                  borderRadius: 4
                                }}>
                                  Day {task.day}
                                </span>
                                <span style={{
                                  fontSize: '0.78rem',
                                  color: '#4f46e5',
                                  background: '#eef2ff',
                                  padding: '2px 8px',
                                  borderRadius: 4,
                                  fontWeight: 600
                                }}>
                                  {task.target_skill}
                                </span>
                              </div>

                              <h4 style={{ fontSize: '0.98rem', marginBottom: 6 }}>{task.day_title}</h4>
                              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 12 }}>
                                {task.action_goal}
                              </p>

                              {/* Concrete Coding Task */}
                              <div style={{
                                background: 'var(--bg-secondary)',
                                padding: '10px 12px',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.82rem',
                                borderLeft: '3px solid #6366f1',
                                marginBottom: 10
                              }}>
                                <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: 3, display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <Code size={13} color="#6366f1" /> Coding Task:
                                </div>
                                <div style={{ color: 'var(--text-main)' }}>{task.code_task}</div>
                              </div>

                              {/* Verification Step */}
                              <div style={{
                                background: '#f0fdf4',
                                padding: '8px 12px',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.8rem',
                                borderLeft: '3px solid #16a34a',
                                marginBottom: 12
                              }}>
                                <div style={{ fontWeight: 600, color: '#16a34a', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <CheckSquare size={13} /> Verification:
                                </div>
                                <div style={{ color: '#14532d' }}>{task.verification_step}</div>
                              </div>
                            </div>

                            {/* Recommended Learning Videos & Docs */}
                            {task.recommended_resources && task.recommended_resources.length > 0 && (
                              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, marginTop: 4 }}>
                                <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
                                  <PlayCircle size={12} color="#dc2626" /> Reference Learning:
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  {task.recommended_resources.map((res, rIdx) => (
                                    <a
                                      key={rIdx}
                                      href={res.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        textDecoration: 'none',
                                        background: 'var(--bg-secondary)',
                                        padding: '5px 8px',
                                        borderRadius: 4,
                                        fontSize: '0.78rem',
                                        color: 'var(--text-main)'
                                      }}
                                    >
                                      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '85%' }}>
                                        {res.title}
                                      </span>
                                      <ArrowUpRight size={12} color="var(--accent-primary)" />
                                    </a>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="glass-panel" style={{ padding: 48, textAlign: 'center' }}>
                <Calendar size={44} color="var(--accent-primary)" style={{ margin: '0 auto 16px auto', display: 'block' }} />
                <h3 style={{ fontSize: '1.25rem', marginBottom: 8 }}>15-Day Roadmap Ready to Generate</h3>
                <p style={{ color: 'var(--text-muted)', maxWidth: 500, margin: '0 auto 20px auto', fontSize: '0.92rem' }}>
                  Run a full assessment on the Skill Gap tab first. The coach will analyze your repository, identify unmet competencies, and generate a customized 15-day daily implementation roadmap.
                </p>
                <button onClick={() => navigate('/gap')} className="btn btn-primary">
                  <TrendingUp size={16} /> Go to Skill Gap Assessment
                </button>
              </div>
            )}
          </div>
        )}

        {/* TAB: NAUKRI LIVE JOB FEED & MULTI-REPO ASSESSMENT */}
        {page === 'naukri' && (
          <NaukriPage
            repos={repos}
            jobs={jobs}
            selectedJobId={selectedJob?.id}
            selectedRepoId={selectedRepo?.id}
            apiBase={API_BASE}
            onRefreshData={loadInitialData}
            onJobImported={(importedJob) => {
              setJobs(prev => [importedJob, ...prev.filter(j => j.id !== importedJob.id)]);
              setSelectedJob(importedJob);
            }}
            onJobSelected={(importedJob) => {
              setSelectedJob(importedJob);
            }}
            onRepoConnected={(newRepo) => {
              setRepos(prev => [...prev.filter(r => r.id !== newRepo.id), newRepo]);
              setSelectedRepo(newRepo);
            }}
            onRepoSelected={(repo) => {
              setSelectedRepo(repo);
            }}
            onRepoUnlinked={(id) => {
              setRepos(prev => prev.filter(r => r.id !== id));
              if (selectedRepo?.id === id) {
                const remaining = repos.filter(r => r.id !== id);
                setSelectedRepo(remaining.length > 0 ? remaining[0] : null);
              }
            }}
            onAssessmentCompleted={(assessmentData) => {
              setAssessmentResult(assessmentData);
            }}
            setFeedback={setFeedback}
          />
        )}

        {/* TAB 2: IMPORT FORM */}
        {page === 'jobs' && (
          <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 24 }}>
            {/* Import Job */}
            <div className="glass-panel" style={{ padding: 24 }}>
              <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Briefcase size={20} color="var(--accent-primary)" /> Import New Job Description
              </h3>
              <form onSubmit={handleImportJob}>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <label htmlFor="job-source-url-input" style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      Job Source URL (External / Any Job Board)
                    </label>
                    <span style={{ fontSize: '0.74rem', color: 'var(--accent-primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Sparkles size={13} /> Groq AI Powered
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
                    <input
                      id="job-source-url-input"
                      type="url"
                      placeholder="e.g. https://boards.greenhouse.io/... or paste any job URL"
                      value={sourceUrl}
                      onChange={e => setSourceUrl(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '9px 12px',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        color: 'var(--text-main)',
                        fontSize: '0.9rem'
                      }}
                    />
                    <button
                      id="fetch-summarize-url-btn"
                      type="button"
                      onClick={handleFetchAndSummarizeUrl}
                      disabled={loading || loadingUrl || !sourceUrl.trim()}
                      className="btn btn-secondary"
                      style={{
                        whiteSpace: 'nowrap',
                        padding: '8px 14px',
                        fontSize: '0.84rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        background: 'rgba(225, 29, 72, 0.08)',
                        color: 'var(--accent-primary)',
                        borderColor: 'rgba(225, 29, 72, 0.35)',
                        fontWeight: 600,
                        cursor: (loading || loadingUrl || !sourceUrl.trim()) ? 'not-allowed' : 'pointer'
                      }}
                      title="Fetch external URL, summarize with Groq AI, and set as Target Job Profile"
                    >
                      {loadingUrl ? <RefreshCw size={14} className="pulse" /> : <Sparkles size={14} />}
                      {loadingUrl ? 'Summarizing...' : 'Summarize & Set Profile'}
                    </button>
                    {sourceUrl && (
                      <button
                        type="button"
                        onClick={() => setSourceUrl("")}
                        className="btn btn-secondary"
                        style={{ padding: '8px 10px', fontSize: '0.78rem' }}
                        title="Clear URL"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 5, marginBottom: 0 }}>
                    Enter any external URL. Groq AI summarizes it into essential job data, loads it below, and sets it in Target Job Profile above.
                  </p>
                </div>
                <div style={{ marginBottom: 18 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 6 }}>
                    <label htmlFor="job-raw-text-input" style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      Raw Job Description Text (Editable)
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {rawJobText && (
                        <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          {rawJobText.split(/\s+/).filter(Boolean).length} words
                        </span>
                      )}
                      <button
                        type="button"
                        id="summarize-text-btn"
                        onClick={handleSummarizeText}
                        disabled={loading || loadingUrl || !rawJobText || !rawJobText.trim()}
                        className="btn btn-secondary"
                        style={{
                          padding: '4px 10px',
                          fontSize: '0.78rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 5,
                          background: 'rgba(225, 29, 72, 0.08)',
                          color: 'var(--accent-primary)',
                          borderColor: 'rgba(225, 29, 72, 0.35)',
                          fontWeight: 600,
                          cursor: (loading || loadingUrl || !rawJobText || !rawJobText.trim()) ? 'not-allowed' : 'pointer'
                        }}
                        title="Summarize pasted description directly with Groq AI"
                      >
                        <Sparkles size={12} />
                        {loadingUrl ? 'Summarizing...' : 'Summarize Text with Groq AI'}
                      </button>
                    </div>
                  </div>
                  <textarea
                    id="job-raw-text-input"
                    rows={8}
                    value={rawJobText}
                    onChange={e => setRawJobText(e.target.value)}
                    placeholder="Job description will appear here after URL summarization, or you can paste text directly..."
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-main)',
                      fontSize: '0.9rem',
                      fontFamily: 'inherit',
                      resize: 'vertical'
                    }}
                  />
                </div>
                <button id="submit-import-job-btn" type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%' }}>
                  <Upload size={16} /> Parse & Extract Structured Requirements
                </button>
              </form>
            </div>

            {/* Connect Repository */}
            <div className="glass-panel" style={{ padding: 24 }}>
              <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <GitBranch size={20} color="var(--accent-primary)" /> Connect GitHub Repository
              </h3>
              <form onSubmit={handleConnectRepo}>
                <div style={{ marginBottom: 18 }}>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 6 }}>
                    Repository Full Name (owner/repo)
                  </label>
                  <input
                    id="repo-name-input"
                    type="text"
                    placeholder="octocat/Hello-World"
                    value={newRepoFullName}
                    onChange={e => setNewRepoFullName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-main)',
                      fontSize: '0.9rem'
                    }}
                  />
                </div>
                <button id="submit-connect-repo-btn" type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', marginBottom: 20 }}>
                  <ShieldCheck size={16} /> Connect & Scan Repository Tree
                </button>
              </form>

              <h4 style={{ fontSize: '0.9rem', marginBottom: 10, color: 'var(--text-muted)' }}>Connected Repositories ({repos.length})</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {repos.map(r => (
                  <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-secondary)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{r.full_name}</div>
                      <div className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                        SHA: {r.latest_commit_sha ? r.latest_commit_sha.slice(0, 10) : 'HEAD'}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedRepo(r);
                          setFeedback({ type: 'success', message: `Selected repository: ${r.full_name}` });
                        }}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                      >
                        Select
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDownloadRepo(r)}
                        className="btn btn-secondary"
                        title="Download ZIP"
                        style={{ padding: '4px 10px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 4 }}
                      >
                        <Download size={13} /> ZIP
                      </button>
                      <span className="badge badge-met">Active</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: REPOSITORIES / WEBHOOK EVENTS */}
        {page === 'repos' && (
          <div className="animate-fade-in">
            <div className="glass-panel" style={{ padding: 24, maxWidth: 720 }}>
              <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <GitBranch size={20} color="var(--accent-primary)" /> Connect GitHub Repository
              </h3>
              <form onSubmit={handleConnectRepo}>
                <input id="repo-name-input" type="text" placeholder="octocat/Hello-World" value={newRepoFullName} onChange={e => setNewRepoFullName(e.target.value)}
                  style={{ width: '100%', padding: '9px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', marginBottom: 14 }} />
                <button id="submit-connect-repo-btn" type="submit" disabled={loading} className="btn btn-primary"><ShieldCheck size={16} /> Connect & Scan</button>
              </form>
              <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {repos.map(r => (
                  <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 8 }}>
                    <div>
                      <strong>{r.full_name}</strong>
                      <div className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{r.latest_commit_sha ? r.latest_commit_sha.slice(0, 10) : 'HEAD'}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedRepo(r);
                          setFeedback({ type: 'success', message: `Selected repository: ${r.full_name}` });
                        }}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                      >
                        Select
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDownloadRepo(r)}
                        className="btn btn-secondary"
                        title="Download ZIP"
                        style={{ padding: '4px 10px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 4 }}
                      >
                        <Download size={13} /> ZIP
                      </button>
                      <span className="badge badge-met">Tracked</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {page === 'evidence' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h2 style={{ fontSize: '1.2rem' }}>Evidence Explorer</h2>
            {(assessmentResult?.skill_assessments || []).flatMap(skill => (skill.citations || []).map((c, i) => ({ skill, c, i }))).map(({ skill, c, i }) => (
              <div key={`${skill.requirement_id}-${i}`} className="glass-panel" style={{ padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
                  <strong>{skill.requirement_title}</strong>
                  <a href={c.github_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)', fontSize: '0.82rem' }}>{c.file_path}#L{c.start_line}-L{c.end_line}</a>
                </div>
                <pre className="mono" style={{ whiteSpace: 'pre-wrap', background: '#0f172a', color: '#e2e8f0', padding: 12, borderRadius: 8, fontSize: '0.8rem' }}>{c.snippet_text}</pre>
                <div style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--text-dim)' }}>Commit {c.commit_sha?.slice(0, 10)} · validated against file content</div>
              </div>
            ))}
            {!(assessmentResult?.skill_assessments || []).some(s => s.citations?.length) && (
              <div className="glass-panel" style={{ padding: 32, color: 'var(--text-muted)' }}>Run a skill-gap assessment to see cited excerpts.</div>
            )}
          </div>
        )}

        {page === 'history' && (
          <div className="animate-fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Terminal size={20} color="var(--accent-primary)" /> GitHub Webhook Deliveries & Audit Trail
              </h2>
              <button onClick={loadInitialData} className="btn btn-secondary" style={{ fontSize: '0.8rem' }}>
                <RefreshCw size={14} /> Refresh Log
              </button>
            </div>

            <div className="glass-panel" style={{ overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '12px 18px' }}>Delivery ID</th>
                    <th style={{ padding: '12px 18px' }}>Repository</th>
                    <th style={{ padding: '12px 18px' }}>Event</th>
                    <th style={{ padding: '12px 18px' }}>Commit SHA</th>
                    <th style={{ padding: '12px 18px' }}>Status</th>
                    <th style={{ padding: '12px 18px' }}>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev, i) => (
                    <tr key={ev.id || i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td className="mono" style={{ padding: '12px 18px', color: 'var(--accent-primary)', fontWeight: 600 }}>
                        {ev.delivery_id}
                      </td>
                      <td style={{ padding: '12px 18px', fontWeight: 600 }}>
                        {ev.repository_full_name}
                      </td>
                      <td style={{ padding: '12px 18px' }}>
                        <span className="badge badge-cyan">{ev.event_type}</span>
                      </td>
                      <td className="mono" style={{ padding: '12px 18px', color: 'var(--text-dim)' }}>
                        {ev.commit_sha ? ev.commit_sha.slice(0, 8) : '—'}
                      </td>
                      <td style={{ padding: '12px 18px' }}>
                        <span className={`badge ${ev.status === 'completed' ? 'badge-met' : ev.status === 'processing' ? 'badge-partial' : 'badge-unmet'}`}>
                          {ev.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 18px', color: 'var(--text-dim)', fontSize: '0.82rem' }}>
                        {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : 'Just now'}
                      </td>
                    </tr>
                  ))}
                  {events.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ padding: 32, textAlign: 'center', color: 'var(--text-dim)' }}>
                        No webhook delivery events recorded yet. Deliveries will appear here as commits are pushed.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <h3 style={{ margin: '22px 0 10px' }}>Skill status changes</h3>
            <div className="glass-panel" style={{ overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', color: 'var(--text-muted)' }}>
                    <th style={{ padding: 12, textAlign: 'left' }}>Requirement</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>From</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>To</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Trigger</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(h => (
                    <tr key={h.id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: 12 }}>#{h.requirement_id}</td>
                      <td style={{ padding: 12 }}>{h.previous_status || '—'}</td>
                      <td style={{ padding: 12 }}>{h.new_status}</td>
                      <td style={{ padding: 12 }}>{h.trigger_event}</td>
                    </tr>
                  ))}
                  {history.length === 0 && <tr><td colSpan={4} style={{ padding: 24, color: 'var(--text-dim)' }}>No status transitions yet.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: GEMINI AI CONFIGURATION */}
        {page === 'settings' && (
          <div className="animate-fade-in" style={{ maxWidth: 800, margin: '0 auto' }}>
            <div className="glass-panel" style={{ padding: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                <div style={{
                  width: 44,
                  height: 44,
                  borderRadius: 'var(--radius-md)',
                  background: 'linear-gradient(135deg, #e11d48, #be123c)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 4px 14px rgba(225, 29, 72, 0.3)'
                }}>
                  <Sparkles size={24} color="#fff" />
                </div>
                <div>
                  <h2 style={{ fontSize: '1.3rem' }}>Gemini LLM Assessment Engine</h2>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Skill verdicts come from a live Google model response. Gemini Flash is tried first; Gemma is used when Flash is over quota.
                  </p>
                </div>
              </div>

              {/* Status Indicator */}
              <div style={{
                background: geminiConfigured ? 'var(--status-met-bg)' : 'var(--status-partial-bg)',
                border: `1px solid ${geminiConfigured ? 'var(--status-met-border)' : 'var(--status-partial-border)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '16px 20px',
                marginBottom: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', color: geminiConfigured ? 'var(--status-met)' : 'var(--status-partial)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {geminiConfigured ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                    {geminiConfigured ? "Gemini LLM Active & Connected" : "Gemini API Key Required"}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    {geminiConfigured
                      ? `Key configured (${maskedKey}). All skill assessments will be decided by Gemini model.`
                      : "Currently falling back to deterministic line-range rules until key is supplied."
                    }
                  </div>
                </div>
                <span className={`badge ${geminiConfigured ? 'badge-met' : 'badge-partial'}`}>
                  {geminiConfigured ? "Live LLM Mode" : "Fallback Mode"}
                </span>
              </div>

              {/* API Key Form */}
              <form onSubmit={handleSaveGeminiKey}>
                <div style={{ marginBottom: 20 }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: 8 }}>
                    Enter Gemini API Key
                  </label>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <input
                        id="gemini-api-key-input"
                        type="password"
                        placeholder={geminiConfigured ? "Enter new key to update..." : "AIzaSy..."}
                        value={inputGeminiKey}
                        onChange={e => setInputGeminiKey(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '11px 14px',
                          background: 'var(--bg-secondary)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-sm)',
                          color: 'var(--text-main)',
                          fontSize: '0.95rem',
                          fontFamily: 'monospace'
                        }}
                      />
                    </div>
                    <button
                      id="save-gemini-key-btn"
                      type="submit"
                      disabled={loading || !inputGeminiKey.trim()}
                      className="btn btn-primary"
                    >
                      <Key size={16} /> Save & Activate Key
                    </button>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 8 }}>
                    You can obtain a free Gemini API key from <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>Google AI Studio</a>.
                  </p>
                  <button type="button" className="btn btn-secondary" disabled={loading} onClick={async () => {
                    setLoading(true);
                    setLlmTest(null);
                    try {
                      const res = await fetch(`${API_BASE}/config/test-llm`, { method: 'POST' });
                      setLlmTest(await res.json());
                    } catch (err) {
                      setLlmTest({ success: false, error: err.message });
                    } finally { setLoading(false); }
                  }}>
                    <Sparkles size={15} /> Send a live test prompt
                  </button>
                  {llmTest && (
                    <pre className="mono" style={{ marginTop: 12, whiteSpace: 'pre-wrap', background: '#0f172a', color: '#e2e8f0', padding: 12, borderRadius: 8, fontSize: '0.8rem' }}>
                      {JSON.stringify(llmTest, null, 2)}
                    </pre>
                  )}
                </div>
              </form>

              {/* Explanatory Cards */}
              <div style={{ marginTop: 28, borderTop: '1px solid var(--border-subtle)', paddingTop: 20 }}>
                <h4 style={{ fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-muted)' }}>How LLM-Based Evaluation Works:</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
                  <div style={{ background: 'var(--bg-secondary)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4 }}>1. Code Inspection</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                      Extracts exact line-range code snippets & manifest files from connected GitHub commit.
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4 }}>2. Gemini Reasoning</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                      Evaluates depth of real implementation vs shallow manifest mentions using structured schema.
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4 }}>3. Gap Next Steps</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                      Generates bespoke next steps, identifying exact architectural areas candidate needs to expand.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border-subtle)', padding: '18px 32px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.82rem' }}>
        TrueSkill — Deterministic Evidence-Based Verification Pipeline • SQLite/PostgreSQL • FastAPI • React
      </footer>
    </div>
  );
}
