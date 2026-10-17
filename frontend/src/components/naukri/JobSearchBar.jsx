import React, { useState, useEffect, useRef } from 'react';
import { Search, MapPin, Briefcase, Filter } from 'lucide-react';

export default function JobSearchBar({
  initialRole = 'Python Developer',
  initialLocation = '',
  initialExperience = '',
  onSearch,
  loading = false,
  apiBase = '/api/v1',
}) {
  const base = apiBase.replace(/\/$/, '');
  const [role, setRole] = useState(initialRole);
  const [location, setLocation] = useState(initialLocation);
  const [experience, setExperience] = useState(initialExperience);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionBoxRef = useRef(null);

  // Sync state with incoming props (URL params)
  useEffect(() => {
    setRole(initialRole);
  }, [initialRole]);

  useEffect(() => {
    setLocation(initialLocation);
  }, [initialLocation]);

  useEffect(() => {
    setExperience(initialExperience);
  }, [initialExperience]);

  // Fetch typeahead suggestions when role input changes
  useEffect(() => {
    let active = true;
    const fetchSuggestions = async () => {
      try {
        const res = await fetch(`${base}/naukri/roles/suggest?q=${encodeURIComponent(role)}`);
        if (res.ok && active) {
          const list = await res.json();
          setSuggestions(list);
        }
      } catch {
        // silent fallback
      }
    };

    const timer = setTimeout(() => {
      if (role && role.trim().length >= 1) {
        fetchSuggestions();
      } else {
        setSuggestions([]);
      }
    }, 150);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [role]);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (suggestionBoxRef.current && !suggestionBoxRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    setShowSuggestions(false);
    if (!role.trim()) return;
    onSearch({ role: role.trim(), location: location.trim(), experience: experience.trim() });
  };

  const handleSelectSuggestion = (suggestedRole) => {
    setRole(suggestedRole);
    setShowSuggestions(false);
    onSearch({ role: suggestedRole, location: location.trim(), experience: experience.trim() });
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '16px 20px', marginBottom: 20 }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Role input with suggestions */}
        <div style={{ flex: '2 1 240px', position: 'relative' }} ref={suggestionBoxRef}>
          <label
            htmlFor="naukri-search-role"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}
          >
            <Briefcase size={13} color="var(--accent-primary)" /> TARGET ROLE / KEYWORD
          </label>
          <div style={{ position: 'relative' }}>
            <input
              id="naukri-search-role"
              type="text"
              value={role}
              onChange={(e) => {
                setRole(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              placeholder="e.g. Python Developer, Full Stack Engineer"
              autoComplete="off"
              style={{
                width: '100%',
                padding: '10px 12px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-main)',
                fontSize: '0.9rem',
                fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Typeahead Suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                marginTop: 4,
                background: '#ffffff',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                boxShadow: '0 10px 25px rgba(0,0,0,0.12)',
                zIndex: 50,
                maxHeight: 220,
                overflowY: 'auto',
              }}
            >
              {suggestions.map((item, idx) => (
                <div
                  key={idx}
                  onClick={() => handleSelectSuggestion(item)}
                  style={{
                    padding: '8px 12px',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    borderBottom: idx === suggestions.length - 1 ? 'none' : '1px solid var(--border-subtle)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-secondary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#ffffff')}
                >
                  {item}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Location input */}
        <div style={{ flex: '1.2 1 160px' }}>
          <label
            htmlFor="naukri-search-location"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}
          >
            <MapPin size={13} color="var(--text-dim)" /> LOCATION
          </label>
          <input
            id="naukri-search-location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Pune, Bengaluru, Remote"
            style={{
              width: '100%',
              padding: '10px 12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-main)',
              fontSize: '0.9rem',
              fontFamily: 'inherit',
            }}
          />
        </div>

        {/* Experience Select */}
        <div style={{ flex: '1 1 140px' }}>
          <label
            htmlFor="naukri-search-exp"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}
          >
            <Filter size={13} color="var(--text-dim)" /> EXPERIENCE
          </label>
          <select
            id="naukri-search-exp"
            value={experience}
            onChange={(e) => setExperience(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-main)',
              fontSize: '0.9rem',
              fontFamily: 'inherit',
            }}
          >
            <option value="">Any Experience</option>
            <option value="0-2 Yrs">0-2 Years (Entry/Junior)</option>
            <option value="3-5 Yrs">3-5 Years (Mid-level)</option>
            <option value="5-8 Yrs">5-8 Years (Senior)</option>
            <option value="8+ Yrs">8+ Years (Lead / Staff)</option>
          </select>
        </div>

        {/* Submit button */}
        <div style={{ alignSelf: 'flex-end', paddingTop: 20 }}>
          <button
            id="naukri-search-btn"
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ padding: '10px 20px', minWidth: 120, height: 42 }}
          >
            <Search size={16} /> {loading ? 'Searching...' : 'Find Jobs'}
          </button>
        </div>
      </div>
    </form>
  );
}
