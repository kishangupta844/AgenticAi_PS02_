import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Briefcase, AlertCircle, RefreshCw, Zap, Sparkles, Database } from 'lucide-react';
import JobSearchBar from '../components/naukri/JobSearchBar';
import JobCard from '../components/naukri/JobCard';
import JobDetailDrawer from '../components/naukri/JobDetailDrawer';
import RepoLinker from '../components/naukri/RepoLinker';
import MultiRepoAssessment from '../components/naukri/MultiRepoAssessment';

export default function NaukriPage({
  repos = [],
  jobs = [],
  selectedJobId = null,
  selectedRepoId = null,
  apiBase = '/api/v1',
  onRefreshData,
  onJobImported,
  onJobSelected,
  onRepoConnected,
  onRepoSelected,
  onRepoUnlinked,
  onAssessmentCompleted,
  setFeedback,
}) {
  const base = apiBase.replace(/\/$/, '');
  const [searchParams, setSearchParams] = useSearchParams();

  // Search state synced with URL params
  const currentRole = searchParams.get('role') || 'Python Developer';
  const currentLocation = searchParams.get('location') || '';
  const currentExperience = searchParams.get('experience') || '';

  const [jobResults, setJobResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [searchProvider, setSearchProvider] = useState('naukri');
  const [isCached, setIsCached] = useState(false);

  // Selected repos for multi-repo assessment
  const [selectedRepoIds, setSelectedRepoIds] = useState([]);

  // Assessment execution state
  const [assessingJobId, setAssessingJobId] = useState(null);
  const [activeAssessment, setActiveAssessment] = useState(null);

  // Job Details Drawer state
  const [drawerJob, setDrawerJob] = useState(null);

  // Initialize selectedRepoIds from all repos if empty
  useEffect(() => {
    if (repos.length > 0 && selectedRepoIds.length === 0) {
      setSelectedRepoIds(repos.map((r) => r.id));
    }
  }, [repos, selectedRepoIds]);

  // Execute job search
  const performSearch = useCallback(
    async (role, location, experience) => {
      setSearchLoading(true);
      setSearchError(null);

      const params = new URLSearchParams();
      if (role) params.set('role', role);
      if (location) params.set('location', location);
      if (experience) params.set('experience', experience);

      try {
        const res = await fetch(`${base}/naukri/search?${params.toString()}`);
        if (!res.ok) {
          const text = await res.text();
          let errDetail = 'Failed to search Naukri jobs.';
          try {
            const errJson = JSON.parse(text);
            errDetail = errJson.detail?.detail || errJson.detail || errDetail;
          } catch {
            errDetail = `Server error (${res.status}): ${text.slice(0, 100)}`;
          }
          throw new Error(errDetail);
        }
        const data = await res.json();
        setJobResults(data.results || []);
        setSearchProvider(data.provider || 'naukri');
        setIsCached(Boolean(data.cached));
      } catch (err) {
        setSearchError(err.message);
      } finally {
        setSearchLoading(false);
      }
    },
    [base]
  );

  // Run search on initial mount or when query params change
  useEffect(() => {
    if (currentRole) {
      performSearch(currentRole, currentLocation, currentExperience);
    }
  }, [currentRole, currentLocation, currentExperience, performSearch]);

  const handleSearchSubmit = ({ role, location, experience }) => {
    const nextParams = new URLSearchParams();
    if (role) nextParams.set('role', role);
    if (location) nextParams.set('location', location);
    if (experience) nextParams.set('experience', experience);
    setSearchParams(nextParams);
  };

  const handleToggleRepoSelection = (repoId) => {
    setSelectedRepoIds((prev) =>
      prev.includes(repoId) ? prev.filter((id) => id !== repoId) : [...prev, repoId]
    );
  };

  // Main flow: "Select This" (import and select into Target Job Profile, run assessment if repos linked)
  const handleAssessJob = async (jobItem) => {
    setAssessingJobId(jobItem.external_id);
    setActiveAssessment(null);

    try {
      // 1. Import job into system (extract structured requirements, deduplicate)
      const importRes = await fetch(`${base}/naukri/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          external_id: jobItem.external_id,
          apply_url: jobItem.apply_url,
          title: jobItem.title,
          company: jobItem.company,
          snippet: jobItem.snippet,
          location: jobItem.location,
          experience: jobItem.experience,
          salary: jobItem.salary,
        }),
      });

      if (!importRes.ok) {
        const text = await importRes.text();
        let errDetail = 'Failed to import job description.';
        try {
          const errJson = JSON.parse(text);
          errDetail = errJson.detail?.detail || errJson.detail || errDetail;
        } catch {
          errDetail = `Import failed (${importRes.status}): ${text.slice(0, 100)}`;
        }
        throw new Error(errDetail);
      }

      const importedJob = await importRes.json();
      if (onJobImported) onJobImported(importedJob);
      if (onJobSelected) onJobSelected(importedJob);

      // If no repos linked yet, notify user that job is now selected and prompt to link repo
      if (repos.length === 0) {
        if (setFeedback) {
          setFeedback({
            type: 'success',
            message: `Selected "${importedJob.title}". Now link your GitHub repository on the right or top bar to assess skill gaps.`,
          });
        }
        const linkerEl = document.getElementById('repo-name-input');
        if (linkerEl) linkerEl.focus();
        return;
      }

      // 2. Repos are present: run assessment against selected repos
      const reposToAssess = selectedRepoIds.length > 0 ? selectedRepoIds : repos.map((r) => r.id);

      const assessRes = await fetch(`${base}/assessments/run-multi`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: importedJob.id,
          repo_ids: reposToAssess,
        }),
      });

      if (!assessRes.ok) {
        const text = await assessRes.text();
        let errDetail = 'Failed to run multi-repo assessment.';
        try {
          const errJson = JSON.parse(text);
          errDetail = errJson.detail?.detail || errJson.detail || errDetail;
        } catch {
          errDetail = `Assessment failed (${assessRes.status}): ${text.slice(0, 100)}`;
        }
        throw new Error(errDetail);
      }

      const assessmentData = await assessRes.json();
      setActiveAssessment(assessmentData);
      if (onAssessmentCompleted) onAssessmentCompleted(assessmentData);

      if (setFeedback) {
        setFeedback({
          type: 'success',
          message: `Selected "${importedJob.title}"! Assessment completed across ${reposToAssess.length} repositories with ${Math.round(
            assessmentData.summary?.overall_match_percentage || 0
          )}% score.`,
        });
      }

      // Refresh parent data lists
      if (onRefreshData) onRefreshData();
    } catch (err) {
      if (setFeedback) {
        setFeedback({ type: 'error', message: err.message });
      }
    } finally {
      setAssessingJobId(null);
    }
  };

  return (
    <div className="animate-fade-in" style={{ width: '100%' }}>
      {/* Page Title & Subtitle */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: '1.4rem', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Briefcase size={22} color="var(--accent-primary)" /> Naukri Job Feed & Multi-Repo Assessment
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Discover live job postings from Naukri.com, link multiple GitHub repositories, and deterministically assess your evidence in one click.
        </p>
      </div>

      {/* Two Column Layout on Desktop */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.8fr) minmax(320px, 1.2fr)',
          gap: 24,
          alignItems: 'start',
        }}
      >
        {/* Left Column: Search Bar & Live Job Feed */}
        <div>
          <JobSearchBar
            apiBase={base}
            initialRole={currentRole}
            initialLocation={currentLocation}
            initialExperience={currentExperience}
            onSearch={handleSearchSubmit}
            loading={searchLoading}
          />

          {/* Banner if Fallback or Cached Provider was used */}
          {searchProvider.includes('fallback') && (
            <div
              style={{
                padding: '10px 14px',
                marginBottom: 16,
                background: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.8rem',
                color: '#92400e',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Sparkles size={15} />
              Serving curated job feed with full compatibility (Naukri web anti-bot fallback enabled).
            </div>
          )}

          {isCached && !searchProvider.includes('fallback') && (
            <div
              style={{
                padding: '8px 12px',
                marginBottom: 14,
                background: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.78rem',
                color: 'var(--text-dim)',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Database size={13} /> Loaded fast from in-memory cache (polite rate limiting).
            </div>
          )}

          {/* Error Banner with Retry */}
          {searchError && (
            <div
              className="glass-panel"
              style={{
                padding: '20px',
                marginBottom: 16,
                background: 'var(--status-unmet-bg)',
                border: '1px solid var(--status-unmet-border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--status-unmet)' }}>
                <AlertCircle size={18} />
                <span style={{ fontSize: '0.88rem' }}>{searchError}</span>
              </div>
              <button
                onClick={() => performSearch(currentRole, currentLocation, currentExperience)}
                className="btn btn-secondary"
                style={{ fontSize: '0.8rem', padding: '6px 14px' }}
              >
                <RefreshCw size={13} /> Retry
              </button>
            </div>
          )}

          {/* Skeleton Loaders */}
          {searchLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[1, 2, 3].map((n) => (
                <div
                  key={n}
                  className="glass-panel pulse"
                  style={{ height: 160, borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)' }}
                />
              ))}
            </div>
          )}

          {/* Empty State */}
          {!searchLoading && !searchError && jobResults.length === 0 && (
            <div
              className="glass-panel"
              style={{
                padding: '40px 20px',
                textAlign: 'center',
                color: 'var(--text-muted)',
              }}
            >
              <Briefcase size={36} color="var(--text-dim)" style={{ margin: '0 auto 12px' }} />
              <h3 style={{ fontSize: '1.05rem', marginBottom: 4 }}>No jobs found for "{currentRole}"</h3>
              <p style={{ fontSize: '0.85rem' }}>
                Try searching for a different role keyword like "Python Developer", "Full Stack Engineer", or adjust filters.
              </p>
            </div>
          )}

          {/* Live Job Cards */}
          {!searchLoading &&
            jobResults.map((job) => {
              const isSelected =
                jobs.some((j) => j.id === selectedJobId && (j.external_id === job.external_id || j.apply_url === job.apply_url)) ||
                (selectedJobId && jobs.find((j) => j.id === selectedJobId)?.title === job.title);

              return (
                <JobCard
                  key={job.external_id}
                  job={job}
                  onAssess={handleAssessJob}
                  onViewDetails={(j) => setDrawerJob(j)}
                  isAssessing={assessingJobId === job.external_id}
                  isSelected={isSelected}
                />
              );
            })}
        </div>

        {/* Right Column: Multi-Repo Linker Sidebar */}
        <div style={{ position: 'sticky', top: 20 }}>
          <RepoLinker
            repos={repos}
            apiBase={base}
            selectedRepoIds={selectedRepoIds}
            activeConnectedRepoId={selectedRepoId}
            onToggleRepoSelection={handleToggleRepoSelection}
            onRepoConnected={(newRepo) => {
              if (onRepoConnected) onRepoConnected(newRepo);
              if (onRepoSelected) onRepoSelected(newRepo);
              setSelectedRepoIds((prev) => [...prev, newRepo.id]);
            }}
            onRepoSelected={onRepoSelected}
            onRepoUnlinked={(id) => {
              if (onRepoUnlinked) onRepoUnlinked(id);
              setSelectedRepoIds((prev) => prev.filter((rid) => rid !== id));
            }}
          />
        </div>
      </div>

      {/* Assessment Output Display */}
      {activeAssessment && (
        <div id="multi-repo-assessment-view" style={{ marginTop: 28 }}>
          <MultiRepoAssessment assessmentResult={activeAssessment} />
        </div>
      )}

      {/* Job Details Drawer */}
      <JobDetailDrawer
        job={drawerJob}
        onClose={() => setDrawerJob(null)}
        onAssess={handleAssessJob}
        isAssessing={assessingJobId === drawerJob?.external_id}
      />
    </div>
  );
}
