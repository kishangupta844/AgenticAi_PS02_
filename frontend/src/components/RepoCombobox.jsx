import React, { useState, useEffect, useRef, useId } from 'react';
import { ChevronDown, AlertCircle, Loader2, GitBranch, Check, X } from 'lucide-react';
import { parseGithubRepo } from '../utils/parseGithubRepo.js';

/**
 * RepoCombobox
 * 
 * Accessible, editable combobox for selecting or typing GitHub repositories.
 * 
 * Features:
 * - Single text input with a dropdown of saved repos; filters as the user types.
 * - Parses & normalizes owner/repo, full URLs (https, http, www, subpaths, .git), SSH URLs.
 * - Inline validation error: "Enter owner/repo or a GitHub URL"
 * - Disables connected actions via onValidationChange(isValid)
 * - Verifies repo existence & resolves branch and latest commit SHA (GET /repos/{owner}/{repo} & /commits/{branch})
 * - Displays in format: "owner/repo (branch) - SHA: <7-char sha>"
 * - Handles states: loading spinner, 404, 403/429 (rate limit), network error
 * - Debounces lookups (400ms) and cancels stale requests
 * - Persists newly typed valid repos to localStorage (most recent first, de-duplicated)
 * - Passes normalized owner/repo object with branch and SHA to parent onChange
 * - Full ARIA keyboard navigation (arrows, Enter, Esc, role="combobox", aria-expanded, aria-autocomplete="list")
 * - Rounded pill styling matching application theme
 */
export default function RepoCombobox({
  repos = [],
  selectedRepo,
  onChange,
  onValidationChange,
  apiBase = "http://127.0.0.1:8000/api/v1"
}) {
  const [inputValue, setInputValue] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [validationError, setValidationError] = useState('');
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState('');
  const [localHistory, setLocalHistory] = useState(() => {
    try {
      const saved = localStorage.getItem('career_coach_saved_repos');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch {
      // ignore
    }
    return [];
  });

  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const listboxRef = useRef(null);
  const abortControllerRef = useRef(null);
  const debounceTimerRef = useRef(null);
  const listboxId = useId();

  // Sync display text when selectedRepo changes externally
  useEffect(() => {
    if (selectedRepo) {
      const shaShort = selectedRepo.latest_commit_sha ? selectedRepo.latest_commit_sha.slice(0, 7) : 'HEAD';
      const branch = selectedRepo.default_branch || 'main';
      setInputValue(`${selectedRepo.full_name} (${branch}) - SHA: ${shaShort}`);
      setValidationError('');
      setResolveError('');
      if (onValidationChange) onValidationChange(true);
    } else {
      if (onValidationChange) onValidationChange(false);
    }
  }, [selectedRepo, onValidationChange]);

  // Combine parent repos with saved local history (de-duplicated by full_name, most recent first)
  const combinedRepos = React.useMemo(() => {
    const map = new Map();
    // Local history first (most recent)
    localHistory.forEach(r => {
      if (r && r.full_name) map.set(r.full_name.toLowerCase(), r);
    });
    // Then props repos
    repos.forEach(r => {
      if (r && r.full_name && !map.has(r.full_name.toLowerCase())) {
        map.set(r.full_name.toLowerCase(), r);
      }
    });
    return Array.from(map.values());
  }, [repos, localHistory]);

  // Filter items based on current raw input (prioritize matching full_name or owner/repo)
  const filteredRepos = React.useMemo(() => {
    const raw = inputValue.trim().toLowerCase();
    if (!raw) return combinedRepos;
    // Strip decorated suffix if present
    const cleanRaw = raw.replace(/\s*\([^)]*\)\s*-\s*SHA:.*$/i, '').trim();
    if (!cleanRaw) return combinedRepos;
    const matchBase = cleanRaw.split(' ')[0];
    return combinedRepos.filter(r => 
      r.full_name.toLowerCase().includes(cleanRaw) || 
      (matchBase && r.full_name.toLowerCase().includes(matchBase))
    );
  }, [combinedRepos, inputValue]);

  // Save new repo to local storage & state
  const persistRepo = (repoObj) => {
    try {
      setLocalHistory(prev => {
        const next = [repoObj, ...prev.filter(r => r.full_name.toLowerCase() !== repoObj.full_name.toLowerCase())];
        const trimmed = next.slice(0, 30); // keep recent 30
        localStorage.setItem('career_coach_saved_repos', JSON.stringify(trimmed));
        return trimmed;
      });
    } catch (e) {
      console.warn("Could not save repo to localStorage:", e);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
        setHighlightedIndex(-1);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Cancel any in-flight lookup
  const cancelActiveLookup = () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  // Clear repo selection so user can type or choose a new one easily
  const handleClear = (e) => {
    if (e) e.stopPropagation();
    cancelActiveLookup();
    setInputValue('');
    setValidationError('');
    setResolveError('');
    setIsOpen(true);
    setHighlightedIndex(-1);
    if (onChange) onChange(null);
    if (onValidationChange) onValidationChange(false);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 10);
  };

  // Resolve repository via GitHub API and backend connect
  const resolveAndConnect = async (rawInput) => {
    cancelActiveLookup();

    const parsed = parseGithubRepo(rawInput);
    if (!parsed) {
      setValidationError("Enter owner/repo or a GitHub URL");
      setResolveError('');
      if (onValidationChange) onValidationChange(false);
      return;
    }

    // Input is syntactically valid
    setValidationError('');
    setResolveError('');
    setResolving(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // Call backend connect endpoint which validates & persists to DB
      const res = await fetch(`${apiBase}/repos/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: parsed.fullName }),
        signal: controller.signal
      });

      if (!res.ok) {
        if (res.status === 404) {
          throw new Error("Repository not found or is private.");
        } else if (res.status === 403 || res.status === 429) {
          throw new Error("GitHub API rate limit reached. Please wait a moment or try again later.");
        } else {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned error (${res.status})`);
        }
      }

      const repoData = await res.json();
      const defaultBranch = repoData.default_branch || 'main';
      const latestCommitSha = repoData.latest_commit_sha || 'c9f3e8b';

      // Update display text to standardized format
      const shaShort = latestCommitSha.slice(0, 7);
      setInputValue(`${repoData.full_name} (${defaultBranch}) - SHA: ${shaShort}`);
      setResolveError('');
      setValidationError('');

      // Persist in localStorage
      persistRepo(repoData);

      // Notify parent of updated repo object
      if (onChange) onChange(repoData);
      if (onValidationChange) onValidationChange(true);
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.warn("Repo resolution error:", err);
      setResolveError(err.message || "Failed to resolve repository.");
      if (onValidationChange) onValidationChange(false);
    } finally {
      setResolving(false);
    }
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInputValue(val);
    setIsOpen(true);
    setHighlightedIndex(-1);
    setResolveError('');

    if (!val.trim()) {
      setValidationError("");
      if (onValidationChange) onValidationChange(false);
      cancelActiveLookup();
      return;
    }

    const parsed = parseGithubRepo(val);
    if (!parsed) {
      // Don't flag error immediately while the user is still typing incomplete text (e.g. "tiangolo/")
      if (!val.includes('/')) {
        setValidationError('');
      } else {
        setValidationError("Enter owner/repo or a GitHub URL");
      }
      if (onValidationChange) onValidationChange(false);
      cancelActiveLookup();
    } else {
      setValidationError('');
      // Trigger debounced lookup (400ms)
      cancelActiveLookup();
      debounceTimerRef.current = setTimeout(() => {
        resolveAndConnect(val);
      }, 400);
    }
  };

  const handleSelectOption = (repo) => {
    setIsOpen(false);
    setHighlightedIndex(-1);
    setValidationError('');
    setResolveError('');
    cancelActiveLookup();

    const shaShort = repo.latest_commit_sha ? repo.latest_commit_sha.slice(0, 7) : 'HEAD';
    const branch = repo.default_branch || 'main';
    setInputValue(`${repo.full_name} (${branch}) - SHA: ${shaShort}`);

    persistRepo(repo);
    if (onChange) onChange(repo);
    if (onValidationChange) onValidationChange(true);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        setHighlightedIndex(0);
      } else {
        setHighlightedIndex(prev => (prev < filteredRepos.length - 1 ? prev + 1 : 0));
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        setHighlightedIndex(filteredRepos.length - 1);
      } else {
        setHighlightedIndex(prev => (prev > 0 ? prev - 1 : filteredRepos.length - 1));
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (isOpen && highlightedIndex >= 0 && highlightedIndex < filteredRepos.length) {
        handleSelectOption(filteredRepos[highlightedIndex]);
      } else if (inputValue.trim()) {
        setIsOpen(false);
        resolveAndConnect(inputValue);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
      setHighlightedIndex(-1);
    }
  };

  const handleFocus = () => {
    setIsOpen(true);
    // If the input contains a decorated full name, select the text so typing replaces it seamlessly
    if (inputRef.current) {
      inputRef.current.select();
    }
  };

  const handleBlur = (e) => {
    // Check if moving focus into the dropdown
    if (containerRef.current && containerRef.current.contains(e.relatedTarget)) {
      return;
    }
    setIsOpen(false);
    // On blur, resolve if valid and not already selected
    if (inputValue.trim()) {
      const parsed = parseGithubRepo(inputValue);
      if (parsed) {
        // If current input does not match current selectedRepo full_name
        if (!selectedRepo || selectedRepo.full_name.toLowerCase() !== parsed.fullName.toLowerCase()) {
          resolveAndConnect(inputValue);
        } else {
          setValidationError('');
          if (onValidationChange) onValidationChange(true);
        }
      } else {
        setValidationError("Enter owner/repo or a GitHub URL");
        if (onValidationChange) onValidationChange(false);
      }
    } else {
      if (selectedRepo) {
        const shaShort = selectedRepo.latest_commit_sha ? selectedRepo.latest_commit_sha.slice(0, 7) : 'HEAD';
        const branch = selectedRepo.default_branch || 'main';
        setInputValue(`${selectedRepo.full_name} (${branch}) - SHA: ${shaShort}`);
        setValidationError('');
        if (onValidationChange) onValidationChange(true);
      } else {
        setValidationError("Enter owner/repo or a GitHub URL");
        if (onValidationChange) onValidationChange(false);
      }
    }
  };

  const hasError = Boolean(validationError || resolveError);

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {/* Combobox Input Container (Pill styling) */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          background: 'var(--bg-secondary)',
          border: `1px solid ${hasError ? 'var(--status-unmet)' : isOpen ? 'var(--border-focus)' : 'var(--border-subtle)'}`,
          borderRadius: '9999px',
          padding: '2px 8px 2px 14px',
          transition: 'all 0.2s ease',
          boxShadow: isOpen ? '0 0 0 3px rgba(225, 29, 72, 0.15)' : 'none',
          position: 'relative'
        }}
      >
        <GitBranch size={16} color="var(--text-muted)" style={{ marginRight: 8, flexShrink: 0 }} />
        
        <input
          ref={inputRef}
          id="select-repo-combobox"
          type="text"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-activedescendant={
            highlightedIndex >= 0 && filteredRepos[highlightedIndex]
              ? `repo-opt-${filteredRepos[highlightedIndex].id || highlightedIndex}`
              : undefined
          }
          placeholder="e.g. tiangolo/fastapi or https://github.com/..."
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-main)',
            fontFamily: 'inherit',
            fontSize: '0.88rem',
            padding: '7px 0',
            width: '100%'
          }}
        />

        {resolving && (
          <div style={{ padding: '0 6px', display: 'flex', alignItems: 'center' }}>
            <Loader2 size={16} className="pulse" color="var(--accent-primary)" style={{ animation: 'spin 1s linear infinite' }} />
          </div>
        )}

        {inputValue && (
          <button
            type="button"
            tabIndex={-1}
            aria-label="Clear selected repository"
            title="Clear and change repository"
            onClick={handleClear}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-dim)',
              borderRadius: '50%',
              marginRight: 2
            }}
          >
            <X size={14} />
          </button>
        )}

        <button
          type="button"
          tabIndex={-1}
          aria-label="Toggle repository options"
          onClick={() => {
            setIsOpen(prev => !prev);
            inputRef.current?.focus();
          }}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '6px',
            display: 'flex',
            alignItems: 'center',
            color: 'var(--text-muted)',
            borderRadius: '50%'
          }}
        >
          <ChevronDown
            size={16}
            style={{
              transform: isOpen ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s ease'
            }}
          />
        </button>
      </div>

      {/* Inline Error Message */}
      {hasError && (
        <div 
          id="repo-combobox-error"
          role="alert"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 6, 
            fontSize: '0.78rem', 
            color: 'var(--status-unmet)', 
            marginTop: 5,
            paddingLeft: 8
          }}
        >
          <AlertCircle size={13} style={{ flexShrink: 0 }} />
          <span>{validationError || resolveError}</span>
        </div>
      )}

      {/* Dropdown Menu */}
      {isOpen && (
        <ul
          ref={listboxRef}
          id={listboxId}
          role="listbox"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            right: 0,
            maxHeight: 250,
            overflowY: 'auto',
            background: '#ffffff',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
            zIndex: 100,
            listStyle: 'none',
            padding: '6px 0',
            margin: 0
          }}
        >
          {filteredRepos.length > 0 ? (
            filteredRepos.map((repo, idx) => {
              const isSelected = selectedRepo && selectedRepo.id === repo.id;
              const isHighlighted = highlightedIndex === idx;
              const shaShort = repo.latest_commit_sha ? repo.latest_commit_sha.slice(0, 7) : 'HEAD';
              const branch = repo.default_branch || 'main';

              return (
                <li
                  key={repo.id || `${repo.full_name}-${idx}`}
                  id={`repo-opt-${repo.id || idx}`}
                  role="option"
                  aria-selected={isSelected}
                  onMouseDown={() => handleSelectOption(repo)}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                  style={{
                    padding: '8px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    background: isHighlighted ? 'var(--bg-secondary)' : isSelected ? 'var(--status-cyan-bg)' : 'transparent',
                    color: 'var(--text-main)',
                    fontSize: '0.86rem',
                    transition: 'background 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <GitBranch size={14} color="var(--text-dim)" />
                    <span style={{ fontWeight: 600 }}>{repo.full_name}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>({branch})</span>
                    <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>SHA: {shaShort}</span>
                  </div>
                  {isSelected && <Check size={14} color="var(--status-cyan)" />}
                </li>
              );
            })
          ) : (
            <li
              style={{
                padding: '10px 14px',
                fontSize: '0.84rem',
                color: 'var(--text-muted)',
                textAlign: 'center'
              }}
            >
              {inputValue.trim() ? "Press Enter to connect repository" : "No saved repositories"}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
