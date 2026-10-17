import React from 'react';
import { X, ExternalLink, Briefcase, MapPin, IndianRupee, Clock, CheckCircle2 } from 'lucide-react';

export default function JobDetailDrawer({ job, onClose, onAssess, isAssessing = false }) {
  if (!job) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '100%',
        maxWidth: 520,
        background: '#ffffff',
        boxShadow: '-8px 0 30px rgba(0,0,0,0.15)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        animation: 'slideInRight 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--accent-primary)', fontWeight: 700 }}>
            Job Description Details
          </span>
          <h2 style={{ fontSize: '1.15rem', marginTop: 4, lineHeight: 1.3 }}>{job.title}</h2>
          <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: 2 }}>
            {job.company || 'Confidential'}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 4,
            borderRadius: '50%',
            color: 'var(--text-muted)',
          }}
        >
          <X size={20} />
        </button>
      </div>

      {/* Body Content */}
      <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Meta summary */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 12,
            padding: 14,
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.82rem',
          }}
        >
          {job.location && (
            <div>
              <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>LOCATION</span>
              <strong style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                <MapPin size={13} /> {job.location}
              </strong>
            </div>
          )}
          {job.experience && (
            <div>
              <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>EXPERIENCE</span>
              <strong style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                <Briefcase size={13} /> {job.experience}
              </strong>
            </div>
          )}
          {job.salary && (
            <div>
              <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>SALARY</span>
              <strong style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                <IndianRupee size={13} /> {job.salary}
              </strong>
            </div>
          )}
          {job.posted && (
            <div>
              <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>POSTED</span>
              <strong style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                <Clock size={13} /> {job.posted}
              </strong>
            </div>
          )}
        </div>

        {/* Tagged Skills */}
        {job.skills && job.skills.length > 0 && (
          <div>
            <h4 style={{ fontSize: '0.85rem', marginBottom: 8, color: 'var(--text-muted)' }}>Key Skills & Requirements</h4>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {job.skills.map((s, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: '0.76rem',
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-main)',
                  }}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Snippet / Description */}
        <div>
          <h4 style={{ fontSize: '0.85rem', marginBottom: 8, color: 'var(--text-muted)' }}>Overview</h4>
          <p style={{ fontSize: '0.88rem', lineHeight: 1.6, color: 'var(--text-main)', whiteSpace: 'pre-wrap' }}>
            {job.snippet || 'No expanded overview text provided.'}
          </p>
        </div>

        {/* Link back */}
        <div style={{ marginTop: 'auto', paddingTop: 12 }}>
          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--accent-primary)',
              fontSize: '0.85rem',
              textDecoration: 'none',
              fontWeight: 600,
            }}
          >
            Open Original Naukri Job Posting <ExternalLink size={14} />
          </a>
        </div>
      </div>

      {/* Footer CTA */}
      <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border-subtle)', background: '#ffffff' }}>
        <button
          onClick={() => {
            onClose();
            onAssess(job);
          }}
          disabled={isAssessing}
          className="btn btn-primary"
          style={{ width: '100%', padding: '12px', fontSize: '0.9rem' }}
        >
          {isAssessing ? 'Selecting...' : 'Select This Job'}
        </button>
      </div>
    </div>
  );
}
