import React, { useState } from 'react';
import { Award, CheckCircle2, AlertCircle, XCircle, ChevronDown, ChevronUp, ExternalLink, BarChart3, Layers } from 'lucide-react';

export default function MultiRepoAssessment({ assessmentResult }) {
  const [showCompare, setShowCompare] = useState(false);
  const [expandedSkillId, setExpandedSkillId] = useState(null);

  if (!assessmentResult) return null;

  const { summary, skill_assessments = [], repos = [], repo_contributions = [] } = assessmentResult;

  const toggleExpand = (reqId) => {
    setExpandedSkillId(expandedSkillId === reqId ? null : reqId);
  };

  return (
    <div className="glass-panel" style={{ padding: '24px 28px', marginTop: 24 }}>
      {/* Assessment Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
            Multi-Repository Assessment Result
          </span>
          <h2 style={{ fontSize: '1.25rem', marginTop: 4 }}>
            {assessmentResult.job_title}
          </h2>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginTop: 2 }}>
            Evaluated against {repos.length} linked repos: <strong>{repos.join(', ')}</strong>
          </div>
        </div>

        {/* Aggregate Score Badge */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: summary.overall_match_percentage >= 70 ? 'var(--status-met)' : 'var(--status-partial)' }}>
            {Math.round(summary.overall_match_percentage)}%
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
            Weighted Match Score
          </div>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: 12,
          marginBottom: 20,
        }}
      >
        <div style={{ padding: '12px 14px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Skills Evaluated</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: 2 }}>{summary.total_skills}</div>
        </div>
        <div style={{ padding: '12px 14px', background: 'var(--status-met-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--status-met-border)' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--status-met)', textTransform: 'uppercase', fontWeight: 600 }}>Met</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--status-met)', marginTop: 2 }}>{summary.met}</div>
        </div>
        <div style={{ padding: '12px 14px', background: 'var(--status-partial-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--status-partial-border)' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--status-partial)', textTransform: 'uppercase', fontWeight: 600 }}>Partial</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--status-partial)', marginTop: 2 }}>{summary.partial}</div>
        </div>
        <div style={{ padding: '12px 14px', background: 'var(--status-unmet-bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--status-unmet-border)' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--status-unmet)', textTransform: 'uppercase', fontWeight: 600 }}>Unmet</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--status-unmet)', marginTop: 2 }}>{summary.unmet}</div>
        </div>
      </div>

      {/* Per-Repo Contribution Bar & Toggle */}
      {repo_contributions.length > 0 && (
        <div style={{ marginBottom: 24, padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h4 style={{ fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
              <BarChart3 size={15} color="var(--accent-primary)" /> Repository Contribution Breakdown
            </h4>
            <button
              type="button"
              onClick={() => setShowCompare(!showCompare)}
              className="btn btn-secondary"
              style={{ fontSize: '0.74rem', padding: '4px 10px' }}
            >
              {showCompare ? 'Hide Comparison' : 'Compare Repos'}
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {repo_contributions.map((c) => (
              <div key={c.repo_id} style={{ fontSize: '0.82rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <strong>{c.repo_full_name}</strong>
                  <span style={{ color: 'var(--text-muted)' }}>
                    {c.skills_met} Met · {c.skills_partial} Partial · {c.score_percentage}% Score
                  </span>
                </div>
                <div style={{ width: '100%', height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${c.score_percentage}%`,
                      height: '100%',
                      background: 'var(--accent-primary)',
                      borderRadius: 3,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-Skill Breakdown List */}
      <h3 style={{ fontSize: '1rem', marginBottom: 12 }}>
        Skill Verification Breakdown & Citations
      </h3>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {skill_assessments.map((skill) => {
          const isExpanded = expandedSkillId === skill.requirement_id;
          const statusClass =
            skill.status === 'met'
              ? 'badge-met'
              : skill.status === 'partial'
              ? 'badge-partial'
              : 'badge-unmet';

          return (
            <div
              key={skill.requirement_id}
              style={{
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                overflow: 'hidden',
                background: '#ffffff',
              }}
            >
              {/* Skill Row */}
              <div
                onClick={() => toggleExpand(skill.requirement_id)}
                style={{
                  padding: '12px 16px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  background: isExpanded ? 'var(--bg-secondary)' : '#ffffff',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className={`badge ${statusClass}`} style={{ textTransform: 'uppercase', fontSize: '0.72rem' }}>
                    {skill.status}
                  </span>
                  <div>
                    <strong style={{ fontSize: '0.88rem' }}>{skill.requirement_title}</strong>
                    <span style={{ marginLeft: 8, fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      Category: {skill.category}
                    </span>
                    {skill.winning_repo && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: '0.72rem',
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        Evidence in: {skill.winning_repo}
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    {skill.citations ? skill.citations.length : 0} citations
                  </span>
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </div>

              {/* Expanded details & Citations */}
              {isExpanded && (
                <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border-subtle)', background: '#fafafa' }}>
                  <div style={{ fontSize: '0.82rem', marginBottom: 8 }}>
                    <strong>Evaluation Reason: </strong>
                    <span style={{ color: 'var(--text-main)' }}>{skill.reason}</span>
                  </div>

                  {skill.evidence_repos && skill.evidence_repos.length > 0 && (
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginBottom: 10 }}>
                      Evidence found across repositories: <strong>{skill.evidence_repos.join(', ')}</strong>
                    </div>
                  )}

                  {/* Citations List */}
                  {skill.citations && skill.citations.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Source Code Permalinks & Excerpts
                      </div>
                      {skill.citations.map((c, cIdx) => (
                        <div
                          key={cIdx}
                          style={{
                            padding: 10,
                            borderRadius: 'var(--radius-sm)',
                            background: '#0f172a',
                            color: '#e2e8f0',
                            fontSize: '0.78rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span style={{ color: '#38bdf8' }}>
                              {c.repo_full_name ? `[${c.repo_full_name}] ` : ''}
                              {c.file_path}#L{c.start_line}-L{c.end_line}
                            </span>
                            {c.github_url && (
                              <a
                                href={c.github_url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: 'var(--accent-primary)', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                              >
                                Permalink <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                          <pre className="mono" style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: '0.75rem' }}>
                            {c.snippet_text}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      No direct source code snippets matched this requirement.
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
