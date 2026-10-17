import React from 'react';
import { ExternalLink, Zap, MapPin, Briefcase, IndianRupee, Clock, ChevronRight } from 'lucide-react';

export default function JobCard({
  job,
  onAssess,
  onViewDetails,
  isAssessing = false,
  isSelected = false,
}) {
  return (
    <div
      className="glass-panel"
      style={{
        padding: '20px 24px',
        marginBottom: 16,
        border: isSelected ? '1.5px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
        background: isSelected ? '#fffdfd' : 'var(--bg-card)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        transition: 'all 0.2s ease',
      }}
    >
      {/* Top Header: Title, Company & Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: 4 }}>
            {job.title}
          </h3>
          <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-muted)' }}>
            {job.company || 'Confidential Employer'}
          </div>
        </div>

        {/* View on Naukri link */}
        <a
          href={job.apply_url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary"
          style={{
            fontSize: '0.78rem',
            padding: '6px 12px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            textDecoration: 'none',
            whiteSpace: 'nowrap',
          }}
          title="Open original job posting on Naukri.com"
        >
          View on Naukri <ExternalLink size={13} />
        </a>
      </div>

      {/* Meta chips: Location, Exp, Salary, Posted */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-dim)' }}>
        {job.location && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <MapPin size={13} color="#64748b" /> {job.location}
          </span>
        )}
        {job.experience && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Briefcase size={13} color="#64748b" /> {job.experience}
          </span>
        )}
        {job.salary && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <IndianRupee size={13} color="#64748b" /> {job.salary}
          </span>
        )}
        {job.posted && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Clock size={13} color="#64748b" /> {job.posted}
          </span>
        )}
      </div>

      {/* Snippet preview */}
      {job.snippet && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
          {job.snippet}
        </p>
      )}

      {/* Tag skills */}
      {job.skills && job.skills.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
          {job.skills.slice(0, 7).map((skill, idx) => (
            <span
              key={idx}
              style={{
                fontSize: '0.74rem',
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-main)',
                fontWeight: 500,
              }}
            >
              {skill}
            </span>
          ))}
          {job.skills.length > 7 && (
            <span style={{ fontSize: '0.74rem', padding: '3px 6px', color: 'var(--text-dim)' }}>
              +{job.skills.length - 7} more
            </span>
          )}
        </div>
      )}

      {/* Bottom Action Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8, borderTop: '1px solid var(--border-subtle)', marginTop: 4 }}>
        <button
          onClick={() => onViewDetails && onViewDetails(job)}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            color: 'var(--text-dim)',
            fontSize: '0.82rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          Inspect JD Details <ChevronRight size={14} />
        </button>

        <button
          id={`assess-job-${job.external_id}`}
          onClick={() => onAssess(job)}
          disabled={isAssessing}
          className={isSelected ? 'btn btn-secondary' : 'btn btn-primary'}
          style={{
            fontSize: '0.82rem',
            padding: '7px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontWeight: 600,
          }}
        >
          {isAssessing ? (
            <>
              <Zap size={14} className="pulse" /> Selecting...
            </>
          ) : isSelected ? (
            <>
              <Zap size={14} /> Selected
            </>
          ) : (
            <>
              <Zap size={14} /> Select This
            </>
          )}
        </button>
      </div>
    </div>
  );
}
