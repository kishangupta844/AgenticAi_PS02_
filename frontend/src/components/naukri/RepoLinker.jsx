import React, { useState } from 'react';
import { GitBranch, Plus, Search, Trash2, ExternalLink, Loader2, FolderGit2 } from 'lucide-react';
import { parseGithubRepo } from '../../utils/parseGithubRepo';

export default function RepoLinker({
  repos = [],
  selectedRepoIds = [],
  activeConnectedRepoId = null,
  onToggleRepoSelection,
  onRepoConnected,
  onRepoSelected,
  onRepoUnlinked,
  apiBase = '/api/v1',
}) {
  const base = apiBase.replace(/\/$/, '');
  const [tab, setTab] = useState('single'); // 'single' or 'github_user'
  const [singleRepoInput, setSingleRepoInput] = useState('');
  const [usernameInput, setUsernameInput] = useState('');
  const [userRepos, setUserRepos] = useState([]);
  const [fetchingUserRepos, setFetchingUserRepos] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // 1. Connect a single repo by URL or owner/repo
  const handleConnectSingle = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    const parsed = parseGithubRepo(singleRepoInput);
    if (!parsed) {
      setErrorMsg("Please enter a valid format: 'owner/repo' or a GitHub URL.");
      return;
    }

    setConnecting(true);
    try {
      const res = await fetch(`${base}/repos/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: parsed.fullName }),
      });
      if (!res.ok) {
        const text = await res.text();
        let errDetail = 'Failed to connect repository.';
        try {
          const errJson = JSON.parse(text);
          errDetail = errJson.detail || errDetail;
        } catch {
          errDetail = `Failed (${res.status}): ${text.slice(0, 100)}`;
        }
        throw new Error(errDetail);
      }
      const newRepo = await res.json();
      setSingleRepoInput('');
      setSuccessMsg(`Linked ${newRepo.full_name}`);
      if (onRepoConnected) onRepoConnected(newRepo);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setConnecting(false);
    }
  };

  // 2. Lookup public repos for a GitHub username
  const handleFetchUserRepos = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    const clean = usernameInput.trim().replace(/^@/, '');
    if (!clean) return;

    setFetchingUserRepos(true);
    try {
      const res = await fetch(`${base}/repos/by-user/${encodeURIComponent(clean)}`);
      if (!res.ok) {
        const text = await res.text();
        let errDetail = 'Could not fetch repositories for this username.';
        try {
          const errJson = JSON.parse(text);
          errDetail = errJson.detail || errDetail;
        } catch {
          errDetail = `Lookup failed (${res.status}): ${text.slice(0, 100)}`;
        }
        throw new Error(errDetail);
      }
      const list = await res.json();
      if (!list || list.length === 0) {
        setErrorMsg(`No public non-fork repositories found for @${clean}.`);
      }
      setUserRepos(list || []);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setFetchingUserRepos(false);
    }
  };

  // 3. Connect a repo chosen from user list
  const handleConnectFromList = async (repoItem) => {
    setConnecting(true);
    try {
      const res = await fetch(`${base}/repos/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: repoItem.full_name,
          default_branch: repoItem.default_branch,
          clone_url: repoItem.clone_url,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        let errDetail = 'Failed to connect repository.';
        try {
          const errJson = JSON.parse(text);
          errDetail = errJson.detail || errDetail;
        } catch {
          errDetail = `Failed (${res.status}): ${text.slice(0, 100)}`;
        }
        throw new Error(errDetail);
      }
      const newRepo = await res.json();
      setSuccessMsg(`Linked ${newRepo.full_name}`);
      if (onRepoConnected) onRepoConnected(newRepo);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setConnecting(false);
    }
  };

  // 4. Unlink / Delete a repo
  const handleUnlink = async (repoId, fullName, e) => {
    e.stopPropagation();
    if (!window.confirm(`Unlink repository '${fullName}'?`)) return;

    try {
      const res = await fetch(`${base}/repos/${repoId}`, { method: 'DELETE' });
      if (res.ok) {
        if (onRepoUnlinked) onRepoUnlinked(repoId);
      }
    } catch {
      // silent
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px 22px' }}>
      <h3 style={{ fontSize: '1.05rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <GitBranch size={18} color="var(--accent-primary)" /> Link Your GitHub Repositories
      </h3>
      <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 16 }}>
        Link multiple repositories. The assessment engine will scan and aggregate skill evidence across all linked projects.
      </p>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 8 }}>
        <button
          type="button"
          onClick={() => { setTab('single'); setErrorMsg(''); }}
          style={{
            background: tab === 'single' ? 'var(--bg-secondary)' : 'none',
            border: 'none',
            padding: '6px 12px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.82rem',
            fontWeight: tab === 'single' ? 700 : 500,
            color: tab === 'single' ? 'var(--text-main)' : 'var(--text-dim)',
            cursor: 'pointer',
          }}
        >
          Paste Repo / URL
        </button>
        <button
          type="button"
          onClick={() => { setTab('github_user'); setErrorMsg(''); }}
          style={{
            background: tab === 'github_user' ? 'var(--bg-secondary)' : 'none',
            border: 'none',
            padding: '6px 12px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.82rem',
            fontWeight: tab === 'github_user' ? 700 : 500,
            color: tab === 'github_user' ? 'var(--text-main)' : 'var(--text-dim)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <FolderGit2 size={13} /> Import by GitHub Username
        </button>
      </div>

      {/* Tab 1: Single repo paste */}
      {tab === 'single' && (
        <form onSubmit={handleConnectSingle} style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              id="repo-name-input"
              type="text"
              placeholder="e.g. tiangolo/fastapi or GitHub URL"
              value={singleRepoInput}
              onChange={(e) => setSingleRepoInput(e.target.value)}
              style={{
                flex: 1,
                padding: '9px 12px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-main)',
                fontSize: '0.88rem',
              }}
            />
            <button
              id="submit-connect-repo-btn"
              type="submit"
              disabled={connecting || !singleRepoInput.trim()}
              className="btn btn-primary"
              style={{ padding: '9px 16px', fontSize: '0.85rem' }}
            >
              <Plus size={15} /> Link
            </button>
          </div>
        </form>
      )}

      {/* Tab 2: Username import */}
      {tab === 'github_user' && (
        <div style={{ marginBottom: 16 }}>
          <form onSubmit={handleFetchUserRepos} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <input
              id="github-username-input"
              type="text"
              placeholder="GitHub username (e.g. torvalds)"
              value={usernameInput}
              onChange={(e) => setUsernameInput(e.target.value)}
              style={{
                flex: 1,
                padding: '9px 12px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-main)',
                fontSize: '0.88rem',
              }}
            />
            <button
              type="submit"
              disabled={fetchingUserRepos || !usernameInput.trim()}
              className="btn btn-secondary"
              style={{ padding: '9px 14px', fontSize: '0.85rem' }}
            >
              {fetchingUserRepos ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Find
            </button>
          </form>

          {/* User's repos list */}
          {userRepos.length > 0 && (
            <div
              style={{
                maxHeight: 180,
                overflowY: 'auto',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: 6,
                background: 'var(--bg-secondary)',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              {userRepos.map((r, idx) => {
                const isAlreadyLinked = repos.some((linked) => linked.full_name.toLowerCase() === r.full_name.toLowerCase());
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '6px 10px',
                      background: '#ffffff',
                      borderRadius: 4,
                      fontSize: '0.82rem',
                    }}
                  >
                    <div>
                      <strong>{r.name}</strong>
                      <span style={{ marginLeft: 8, fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                        {r.language} · ⭐ {r.stargazers_count}
                      </span>
                    </div>
                    {isAlreadyLinked ? (
                      <span className="badge badge-met" style={{ fontSize: '0.7rem' }}>Linked</span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleConnectFromList(r)}
                        disabled={connecting}
                        className="btn btn-secondary"
                        style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                      >
                        + Link
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      {errorMsg && (
        <div style={{ color: 'var(--status-unmet)', fontSize: '0.8rem', marginBottom: 12 }}>
          {errorMsg}
        </div>
      )}
      {successMsg && (
        <div style={{ color: 'var(--status-met)', fontSize: '0.8rem', marginBottom: 12 }}>
          {successMsg}
        </div>
      )}

      {/* Connected Repos Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Linked Repositories ({repos.length})
        </h4>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
          {selectedRepoIds.length} included in assessment
        </span>
      </div>

      {/* Connected Repos Chips / List */}
      {repos.length === 0 ? (
        <div
          style={{
            padding: 16,
            textAlign: 'center',
            fontSize: '0.82rem',
            color: 'var(--text-dim)',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          No repositories linked yet. Paste a repo above to get started.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {repos.map((r) => {
            const isChecked = selectedRepoIds.includes(r.id);
            const isActiveConnected = activeConnectedRepoId === r.id;

            return (
              <div
                key={r.id}
                onClick={() => {
                  if (onRepoSelected) onRepoSelected(r);
                  if (onToggleRepoSelection) onToggleRepoSelection(r.id);
                }}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  background: isActiveConnected
                    ? '#eff6ff'
                    : isChecked
                    ? 'var(--status-met-bg)'
                    : 'var(--bg-secondary)',
                  border: isActiveConnected
                    ? '1.5px solid #3b82f6'
                    : isChecked
                    ? '1px solid var(--status-met-border)'
                    : '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                title="Click to select this repo for the top Connected GitHub Repository bar"
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={(e) => {
                      e.stopPropagation();
                      if (onToggleRepoSelection) onToggleRepoSelection(r.id);
                    }}
                    style={{ cursor: 'pointer' }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.84rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                      {r.full_name}
                      {isActiveConnected && (
                        <span
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            padding: '1px 6px',
                            background: '#dbeafe',
                            color: '#1d4ed8',
                            borderRadius: 10,
                          }}
                        >
                          Connected in Top Bar
                        </span>
                      )}
                    </div>
                    <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                      SHA: {r.latest_commit_sha ? r.latest_commit_sha.slice(0, 8) : 'HEAD'} · {r.default_branch || 'main'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <a
                    href={`https://github.com/${r.full_name}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    style={{ color: 'var(--text-dim)', padding: 4 }}
                    title="View on GitHub"
                  >
                    <ExternalLink size={13} />
                  </a>
                  <button
                    type="button"
                    onClick={(e) => handleUnlink(r.id, r.full_name, e)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-dim)',
                      cursor: 'pointer',
                      padding: 4,
                    }}
                    title="Unlink Repository"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
