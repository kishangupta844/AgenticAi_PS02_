import assert from 'node:assert/strict';
import { parseGithubRepo } from './parseGithubRepo.js';

console.log('Running parseGithubRepo unit tests...');

// 1. Standard owner/repo
{
  const res = parseGithubRepo('tiangolo/fastapi');
  assert.deepEqual(res, { owner: 'tiangolo', repo: 'fastapi', fullName: 'tiangolo/fastapi' });
}

// 2. Whitespace trimming & casing preservation
{
  const res = parseGithubRepo('  facebook/React  ');
  assert.deepEqual(res, { owner: 'facebook', repo: 'React', fullName: 'facebook/React' });
}

// 3. Dots, underscores, hyphens in names
{
  const res = parseGithubRepo('my-org.co_de/cool-repo.v2');
  assert.deepEqual(res, { owner: 'my-org.co_de', repo: 'cool-repo.v2', fullName: 'my-org.co_de/cool-repo.v2' });
}

// 4. Trailing slashes
{
  const res = parseGithubRepo('tiangolo/fastapi///');
  assert.deepEqual(res, { owner: 'tiangolo', repo: 'fastapi', fullName: 'tiangolo/fastapi' });
}

// 5. Full https URL
{
  const res = parseGithubRepo('https://github.com/tiangolo/fastapi');
  assert.deepEqual(res, { owner: 'tiangolo', repo: 'fastapi', fullName: 'tiangolo/fastapi' });
}

// 6. http URL with www and trailing slash
{
  const res = parseGithubRepo('http://www.github.com/tiangolo/fastapi/');
  assert.deepEqual(res, { owner: 'tiangolo', repo: 'fastapi', fullName: 'tiangolo/fastapi' });
}

// 7. URL without scheme (www.github.com / github.com)
{
  const res1 = parseGithubRepo('github.com/pallets/flask');
  assert.deepEqual(res1, { owner: 'pallets', repo: 'flask', fullName: 'pallets/flask' });
  const res2 = parseGithubRepo('www.github.com/pallets/flask');
  assert.deepEqual(res2, { owner: 'pallets', repo: 'flask', fullName: 'pallets/flask' });
}

// 8. URL with .git suffix
{
  const res = parseGithubRepo('https://github.com/torvalds/linux.git');
  assert.deepEqual(res, { owner: 'torvalds', repo: 'linux', fullName: 'torvalds/linux' });
}

// 9. URL with /tree/<branch> or /blob/<branch> and query/hash
{
  const res1 = parseGithubRepo('https://github.com/tiangolo/fastapi/tree/master/docs');
  assert.deepEqual(res1, { owner: 'tiangolo', repo: 'fastapi', fullName: 'tiangolo/fastapi' });

  const res2 = parseGithubRepo('https://github.com/tiangolo/fastapi/blob/main/README.md?plain=1#L10');
  assert.deepEqual(res2, { owner: 'tiangolo', repo: 'fastapi', fullName: 'tiangolo/fastapi' });
}

// 10. SSH format
{
  const res = parseGithubRepo('git@github.com:octocat/Hello-World.git');
  assert.deepEqual(res, { owner: 'octocat', repo: 'Hello-World', fullName: 'octocat/Hello-World' });

  const res2 = parseGithubRepo('git@github.com:octocat/Hello-World');
  assert.deepEqual(res2, { owner: 'octocat', repo: 'Hello-World', fullName: 'octocat/Hello-World' });
}

// 11. Invalid cases (must return null)
{
  assert.equal(parseGithubRepo(''), null);
  assert.equal(parseGithubRepo('   '), null);
  assert.equal(parseGithubRepo(null), null);
  assert.equal(parseGithubRepo(undefined), null);
  assert.equal(parseGithubRepo('just-a-name'), null);
  assert.equal(parseGithubRepo('/only-repo'), null);
  assert.equal(parseGithubRepo('owner/'), null);
  assert.equal(parseGithubRepo('https://gitlab.com/owner/repo'), null); // not github
  assert.equal(parseGithubRepo('https://github.com/onlyone'), null);
  assert.equal(parseGithubRepo('owner/repo with spaces'), null);
  assert.equal(parseGithubRepo('owner/repo$badchar'), null);
  assert.equal(parseGithubRepo('owner//repo'), null);
}

console.log('All 11 test suites passed successfully! 🚀');
