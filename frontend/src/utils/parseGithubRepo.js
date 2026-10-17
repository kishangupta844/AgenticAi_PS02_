/**
 * Reusable utility to parse and normalize user-provided GitHub repository input.
 * 
 * Supports:
 * - "owner/repo"
 * - "https://github.com/owner/repo"
 * - "http://github.com/owner/repo"
 * - "www.github.com/owner/repo"
 * - "github.com/owner/repo"
 * - Trailing slashes, .git suffix
 * - URL paths like "/tree/main", "/blob/master/path/to/file", query params, hashes
 * - SSH URLs: "git@github.com:owner/repo.git"
 * 
 * Validation rule:
 * Owner and Repo names must match: ^[A-Za-z0-9_.-]+$
 * 
 * Preserves original casing for display while providing canonical lower-cased fields if needed.
 */

const REPO_NAME_REGEX = /^[A-Za-z0-9_.-]+$/;

export function parseGithubRepo(input) {
  if (typeof input !== 'string') return null;
  let raw = input.trim();
  if (!raw) return null;

  // Strip decorator suffix if present (e.g. " (main) - SHA: 1234567")
  raw = raw.replace(/\s*\([^)]*\)\s*-\s*SHA:.*$/i, '').trim();
  if (!raw) return null;

  // Case 1: SSH format "git@github.com:owner/repo(.git)?"
  const sshMatch = raw.match(/^git@github\.com:([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?$/i);
  if (sshMatch) {
    const owner = sshMatch[1];
    const repo = sshMatch[2].replace(/\.git$/i, '');
    if (REPO_NAME_REGEX.test(owner) && REPO_NAME_REGEX.test(repo)) {
      return { owner, repo, fullName: `${owner}/${repo}` };
    }
    return null;
  }

  // Case 2: URL format (https://, http://, //, www., github.com/...)
  let normalized = raw;
  if (/^(https?:)?\/\//i.test(normalized) || /^www\.github\.com/i.test(normalized) || /^github\.com/i.test(normalized)) {
    if (!/^[a-zA-Z]+:\/\//i.test(normalized)) {
      normalized = 'https://' + normalized.replace(/^\/\//, '');
    }
    try {
      const url = new URL(normalized);
      const hostname = url.hostname.toLowerCase();
      if (hostname !== 'github.com' && hostname !== 'www.github.com') {
        return null;
      }
      // Pathname like "/owner/repo/tree/main" -> parts: ["owner", "repo", ...]
      const parts = url.pathname.split('/').filter(Boolean);
      if (parts.length < 2) return null;
      const owner = parts[0];
      const repo = parts[1].replace(/\.git$/i, '');
      if (REPO_NAME_REGEX.test(owner) && REPO_NAME_REGEX.test(repo)) {
        return { owner, repo, fullName: `${owner}/${repo}` };
      }
      return null;
    } catch {
      return null;
    }
  }

  // Case 3: "owner/repo" with optional .git or trailing slash or subpath
  // Strip trailing slashes first
  const cleaned = raw.replace(/\/+$/, '');
  const slashParts = cleaned.split('/');
  if (slashParts.length >= 2) {
    const owner = slashParts[0];
    const repo = slashParts[1].replace(/\.git$/i, '');
    // If user typed owner/repo or owner/repo/tree/branch, extract owner and repo
    if (REPO_NAME_REGEX.test(owner) && REPO_NAME_REGEX.test(repo)) {
      return { owner, repo, fullName: `${owner}/${repo}` };
    }
  }

  return null;
}
