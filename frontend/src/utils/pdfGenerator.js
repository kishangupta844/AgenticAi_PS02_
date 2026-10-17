/**
 * Utility to generate and trigger download of a professional, print-ready PDF
 * for both Skill Gap Assessments and 15-Day Implementation Roadmaps.
 * 
 * Uses standard browser printable iframe document with clean CSS styling,
 * pagination headers, company/role headers, and auto-download/print triggers.
 */

export function downloadReportAsPdf({ type = 'all', assessmentResult }) {
  if (!assessmentResult) return;

  const {
    job_title,
    repo_full_name,
    evaluated_at,
    summary,
    readiness,
    roadmap,
    skill_assessments
  } = assessmentResult;

  const dateStr = evaluated_at ? new Date(evaluated_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }) : new Date().toLocaleDateString();

  const printWindow = window.open('', '_blank', 'width=900,height=1000');
  if (!printWindow) {
    alert("Please allow popups to download and print the PDF report.");
    return;
  }

  // Compile Skills HTML
  const skillsHtml = (skill_assessments || []).map(skill => {
    const isMet = skill.status === 'met';
    const isPartial = skill.status === 'partial';
    const statusLabel = isMet ? 'DEMONSTRATED (MET)' : isPartial ? 'PARTIAL' : 'GAP (UNMET)';
    const statusClass = isMet ? 'badge-met' : isPartial ? 'badge-partial' : 'badge-unmet';

    const citationsHtml = (skill.citations || []).map(c => `
      <div class="citation-row">
        <code>${c.file_path} (Lines ${c.start_line}-${c.end_line})</code>
        <pre class="snippet">${escapeHtml(c.snippet_text)}</pre>
      </div>
    `).join('');

    const resourcesHtml = (skill.resources || []).map(r => `
      <li class="resource-item">
        <strong>${escapeHtml(r.title)}</strong> (${r.type === 'youtube' ? 'Video' : 'Docs'}) - 
        <a href="${r.url}" target="_blank">${r.url}</a>
      </li>
    `).join('');

    return `
      <div class="skill-card ${skill.status}">
        <div class="skill-header">
          <div>
            <h3 class="skill-title">${escapeHtml(skill.requirement_title)}</h3>
            <div class="skill-sub">Category: ${escapeHtml(skill.category)} • Type: ${escapeHtml(skill.requirement_type)} • Weight: ${skill.weight}</div>
          </div>
          <span class="badge ${statusClass}">${statusLabel}</span>
        </div>
        <div class="skill-reason">${escapeHtml(skill.reason)}</div>

        ${citationsHtml ? `
          <div class="section-title">Deterministic Code Citations (${skill.citations.length})</div>
          ${citationsHtml}
        ` : ''}

        ${skill.practice_task ? `
          <div class="practice-box">
            <strong>Target Practice Task:</strong> ${escapeHtml(skill.practice_task)}
          </div>
        ` : ''}

        ${resourcesHtml ? `
          <div class="section-title">Verified Learning Resources</div>
          <ul class="resource-list">${resourcesHtml}</ul>
        ` : ''}
      </div>
    `;
  }).join('');

  // Compile Roadmap HTML
  let roadmapHtml = '';
  if (roadmap && roadmap.phases) {
    const phasesHtml = roadmap.phases.map(p => {
      const tasksHtml = (p.tasks || []).map(t => `
        <div class="roadmap-task">
          <div class="task-head">
            <span class="day-badge">Day ${t.day}</span>
            <span class="task-skill">${escapeHtml(t.target_skill)}</span>
            <strong class="task-title">${escapeHtml(t.day_title)}</strong>
          </div>
          <p class="task-goal">${escapeHtml(t.action_goal)}</p>
          <div class="code-box"><strong>Code Task:</strong> ${escapeHtml(t.code_task)}</div>
          <div class="verif-box"><strong>Verification:</strong> ${escapeHtml(t.verification_step)}</div>
          ${t.recommended_resources && t.recommended_resources.length > 0 ? `
            <div class="task-res">
              <strong>Learning Ref:</strong> ${t.recommended_resources.map(r => `<a href="${r.url}">${escapeHtml(r.title)}</a>`).join(', ')}
            </div>
          ` : ''}
        </div>
      `).join('');

      return `
        <div class="roadmap-phase">
          <div class="phase-header">
            <h3>Phase ${p.phase_number}: ${escapeHtml(p.title)} (${p.day_range})</h3>
            <div class="phase-milestone">Milestone: ${escapeHtml(p.milestone)}</div>
          </div>
          <div class="tasks-grid">
            ${tasksHtml}
          </div>
        </div>
      `;
    }).join('');

    roadmapHtml = `
      <div class="page-break"></div>
      <div class="roadmap-container">
        <h2 class="main-heading">15-Day Targeted Implementation Roadmap</h2>
        <p class="sub-heading">${escapeHtml(roadmap.summary)}</p>
        <div class="outcome-box"><strong>Target Outcome:</strong> ${escapeHtml(roadmap.expected_outcome)}</div>
        ${phasesHtml}
      </div>
    `;
  }

  const docHtml = `
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Assessment Report - ${escapeHtml(job_title)} - ${escapeHtml(repo_full_name)}</title>
        <style>
          @page {
            size: A4;
            margin: 15mm 15mm 15mm 15mm;
          }
          * { box-sizing: border-box; }
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #0f172a;
            background: #ffffff;
            margin: 0;
            padding: 20px;
            font-size: 13px;
            line-height: 1.5;
          }
          a { color: #e11d48; text-decoration: none; }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #e11d48;
            padding-bottom: 14px;
            margin-bottom: 20px;
          }
          .header-brand {
            font-size: 20px;
            font-weight: 800;
            color: #e11d48;
            letter-spacing: -0.5px;
          }
          .header-meta {
            text-align: right;
            font-size: 11px;
            color: #64748b;
          }
          .title-area {
            margin-bottom: 20px;
          }
          .job-title {
            font-size: 22px;
            font-weight: 800;
            margin: 0 0 4px 0;
            color: #0f172a;
          }
          .repo-subtitle {
            font-size: 13px;
            color: #475569;
          }
          .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 22px;
          }
          .metric-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 10px 14px;
            text-align: center;
          }
          .metric-label {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 2px;
          }
          .metric-val {
            font-size: 24px;
            font-weight: 800;
          }
          .badge {
            display: inline-block;
            font-size: 10px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
          }
          .badge-met { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
          .badge-partial { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
          .badge-unmet { background: #fff1f2; color: #e11d48; border: 1px solid #fecdd3; }
          
          .skill-card {
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 14px;
            margin-bottom: 14px;
            page-break-inside: avoid;
          }
          .skill-card.met { border-left: 4px solid #059669; }
          .skill-card.partial { border-left: 4px solid #d97706; }
          .skill-card.unmet { border-left: 4px solid #e11d48; }

          .skill-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
          }
          .skill-title {
            font-size: 14px;
            font-weight: 700;
            margin: 0 0 2px 0;
          }
          .skill-sub {
            font-size: 11px;
            color: #64748b;
          }
          .skill-reason {
            font-size: 12px;
            color: #1e293b;
            margin-bottom: 8px;
          }
          .section-title {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748b;
            margin: 8px 0 4px 0;
          }
          .citation-row {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 6px 10px;
            margin-bottom: 6px;
          }
          .citation-row code {
            font-size: 11px;
            font-weight: 700;
            color: #0284c7;
          }
          .snippet {
            font-family: monospace;
            font-size: 10px;
            background: #0f172a;
            color: #e2e8f0;
            padding: 6px;
            border-radius: 3px;
            margin: 4px 0 0 0;
            white-space: pre-wrap;
          }
          .practice-box {
            background: #eef2ff;
            border-left: 3px solid #6366f1;
            padding: 6px 10px;
            font-size: 11px;
            border-radius: 0 4px 4px 0;
            margin-top: 6px;
          }
          .resource-list {
            margin: 0;
            padding-left: 18px;
            font-size: 11px;
          }
          .resource-item {
            margin-bottom: 3px;
          }

          /* Roadmap Print Styles */
          .page-break {
            page-break-before: always;
          }
          .main-heading {
            font-size: 18px;
            font-weight: 800;
            margin: 0 0 4px 0;
            color: #0f172a;
          }
          .sub-heading {
            font-size: 12px;
            color: #64748b;
            margin-bottom: 12px;
          }
          .outcome-box {
            background: #f0fdf4;
            border-left: 3px solid #16a34a;
            padding: 8px 12px;
            font-size: 11px;
            margin-bottom: 16px;
          }
          .roadmap-phase {
            margin-bottom: 18px;
            page-break-inside: avoid;
          }
          .phase-header {
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 4px;
            margin-bottom: 10px;
          }
          .phase-header h3 {
            font-size: 13px;
            margin: 0;
            color: #e11d48;
          }
          .phase-milestone {
            font-size: 11px;
            color: #475569;
            font-style: italic;
          }
          .tasks-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
          }
          .roadmap-task {
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            padding: 10px;
            background: #ffffff;
            font-size: 11px;
            page-break-inside: avoid;
          }
          .task-head {
            margin-bottom: 4px;
          }
          .day-badge {
            background: #e11d48;
            color: #fff;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 5px;
            border-radius: 3px;
            margin-right: 5px;
          }
          .task-skill {
            background: #e0e7ff;
            color: #4338ca;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 5px;
            border-radius: 3px;
            margin-right: 5px;
          }
          .task-title {
            font-size: 11px;
          }
          .task-goal {
            margin: 4px 0;
            color: #475569;
          }
          .code-box {
            background: #f1f5f9;
            border-left: 2px solid #6366f1;
            padding: 4px 6px;
            font-size: 10px;
            margin-bottom: 4px;
          }
          .verif-box {
            background: #f0fdf4;
            border-left: 2px solid #16a34a;
            padding: 4px 6px;
            font-size: 10px;
            margin-bottom: 4px;
          }
          .task-res {
            font-size: 10px;
            color: #64748b;
          }

          .print-toolbar {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #0f172a;
            color: #fff;
            padding: 10px 16px;
            border-radius: 30px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            font-size: 12px;
            cursor: pointer;
            z-index: 1000;
          }
          @media print {
            .print-toolbar { display: none !important; }
            body { padding: 0; }
          }
        </style>
      </head>
      <body>
        <div class="print-toolbar" onclick="window.print()">
          <span>🖨️ Click to Print / Save as PDF</span>
        </div>

        <div class="header">
          <div>
            <div class="header-brand">TrueSkill</div>
            <div style="font-size: 11px; color: #64748b;">Deterministic Skill Verification & Gap Analysis Report</div>
          </div>
          <div class="header-meta">
            <div><strong>Generated:</strong> ${dateStr}</div>
            <div><strong>Status:</strong> Verified Code Evaluation</div>
          </div>
        </div>

        <div class="title-area">
          <h1 class="job-title">${escapeHtml(job_title)}</h1>
          <div class="repo-subtitle">Evaluated Repository: <strong>${escapeHtml(repo_full_name)}</strong></div>
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">Match Score</div>
            <div class="metric-val" style="color: #e11d48;">${summary?.overall_match_percentage || 0}%</div>
            <div style="font-size: 10px; color: #64748b;">Weighted: ${summary?.weighted_score || 0} pts</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Demonstrated (Met)</div>
            <div class="metric-val" style="color: #059669;">${summary?.met || 0}</div>
            <div style="font-size: 10px; color: #64748b;">Verified in Code</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Partial</div>
            <div class="metric-val" style="color: #d97706;">${summary?.partial || 0}</div>
            <div style="font-size: 10px; color: #64748b;">Manifest / Shallow</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Gaps (Unmet)</div>
            <div class="metric-val" style="color: #e11d48;">${summary?.unmet || 0}</div>
            <div style="font-size: 10px; color: #64748b;">Target Areas</div>
          </div>
        </div>

        ${readiness ? `
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; margin-bottom: 20px;">
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 2px;">
              Readiness Projection: <strong style="color: #0f172a;">${readiness.band} (${readiness.score}/100)</strong>
            </div>
            <div style="font-size: 12px; color: #334155;">${escapeHtml(readiness.rationale)}</div>
          </div>
        ` : ''}

        <h2 style="font-size: 15px; font-weight: 800; margin-bottom: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">
          Requirement Evaluation & Cited Evidence
        </h2>

        ${skillsHtml}

        ${roadmapHtml}
      </body>
    </html>
  `;

  printWindow.document.open();
  printWindow.document.write(docHtml);
  printWindow.document.close();

  // Automatically trigger print dialog once document loads
  printWindow.onload = () => {
    setTimeout(() => {
      printWindow.focus();
      printWindow.print();
    }, 250);
  };
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
