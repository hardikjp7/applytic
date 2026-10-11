import { generateCodeVerifier, generateCodeChallenge } from './lib/pkce.js';

// ── Config ────────────────────────────────────────────────────────────────────
// Matches cdk/lib/applytic-stack.ts - same Hosted UI domain and public client
// (no client secret - authorizationCodeGrant + PKCE) used by the web app.
const COGNITO_DOMAIN = 'https://applytic-auth.auth.us-east-1.amazoncognito.com';
const CLIENT_ID = '1kf85rr01ra5c7s2vfirh8mt8s';
const SCOPES = 'email openid profile';

// API Gateway's Cognito authorizer reads the ID token directly from the
// Authorization header - no "Bearer " prefix, same convention as
// frontend/src/lib/amplify.ts's axios interceptor.
const API_BASE = 'https://mbjyu0w1k5.execute-api.us-east-1.amazonaws.com/v1';

// chrome.identity.launchWebAuthFlow requires this exact redirect URI to be
// registered in Cognito's UserPoolClient callbackUrls (CDK change - see
// cdk/lib/applytic-stack.ts str_replace guide). Stable across reloads only
// because manifest.json pins a "key", which fixes the extension ID.
const REDIRECT_URI = chrome.identity.getRedirectURL();

const STORAGE_KEY = 'applytic_auth';

// ── Token storage ─────────────────────────────────────────────────────────────

async function getStoredAuth() {
  const result = await chrome.storage.local.get(STORAGE_KEY);
  return result[STORAGE_KEY] || null;
}

async function setStoredAuth(auth) {
  await chrome.storage.local.set({ [STORAGE_KEY]: auth });
}

async function clearStoredAuth() {
  await chrome.storage.local.remove(STORAGE_KEY);
}

// ── OAuth flow ────────────────────────────────────────────────────────────────

async function signIn() {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);

  const authUrl = new URL(`${COGNITO_DOMAIN}/oauth2/authorize`);
  authUrl.searchParams.set('client_id', CLIENT_ID);
  authUrl.searchParams.set('response_type', 'code');
  authUrl.searchParams.set('scope', SCOPES);
  authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
  authUrl.searchParams.set('code_challenge', codeChallenge);
  authUrl.searchParams.set('code_challenge_method', 'S256');

  const redirectResponse = await chrome.identity.launchWebAuthFlow({
    url: authUrl.toString(),
    interactive: true,
  });

  const code = new URL(redirectResponse).searchParams.get('code');
  if (!code) {
    throw new Error('No authorization code returned from Cognito Hosted UI');
  }

  const tokens = await exchangeCodeForTokens(code, codeVerifier);
  await setStoredAuth(tokens);
  await flushQueue();
  return tokens;
}

async function exchangeCodeForTokens(code, codeVerifier) {
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: codeVerifier,
  });

  const res = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Token exchange failed: ${res.status} ${text}`);
  }

  const data = await res.json();
  return {
    idToken: data.id_token,
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    // expires_in is seconds from issuance - store an absolute expiry instead
    // so callers don't need to track when the token was fetched.
    expiresAt: Date.now() + data.expires_in * 1000,
  };
}

async function refreshTokens(refreshToken) {
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: CLIENT_ID,
    refresh_token: refreshToken,
  });

  const res = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) {
    // Refresh token itself expired or was revoked - caller should treat
    // this as a full sign-out, not retry.
    throw new Error(`Token refresh failed: ${res.status}`);
  }

  const data = await res.json();
  return {
    idToken: data.id_token,
    accessToken: data.access_token,
    // Cognito does not rotate the refresh token on refresh by default.
    refreshToken,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
}

async function signOut() {
  await clearStoredAuth();
}

const QUEUE_KEY = 'applytic_pending_queue';

async function queueApplication(payload) {
  const result = await chrome.storage.local.get(QUEUE_KEY);
  const queue = result[QUEUE_KEY] || [];
  queue.push({ ...payload, queuedAt: Date.now() });
  await chrome.storage.local.set({ [QUEUE_KEY]: queue });
  return true;
}

async function getQueue() {
  const result = await chrome.storage.local.get(QUEUE_KEY);
  return result[QUEUE_KEY] || [];
}

async function setQueue(queue) {
  await chrome.storage.local.set({ [QUEUE_KEY]: queue });
}

// ── Live API call ──────────────────────────────────────────────────────────

function toCreateApplicationRequest(payload) {
  // Maps the content script's extracted shape to CreateApplicationRequest
  // (lambdas/applications/handler.py). jobDescText isn't part of the API
  // schema - it's dropped here, kept only for a possible future
  // pre-filled-notes feature.
  return {
    company: payload.company,
    role: payload.role,
    status: 'applied',
    source: payload.source,
    jobDescUrl: payload.jobDescUrl,
  };
}

// Returns { ok: true } on success, { ok: false, retryable } on failure.
// retryable=true means "queue it and try again later" (network error, 5xx,
// 401 after a failed refresh); retryable=false means the request itself was
// bad (4xx other than 401) and re-queueing it would just fail again.
async function postApplication(idToken, payload) {
  try {
    const res = await fetch(`${API_BASE}/applications`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: idToken,
      },
      body: JSON.stringify(toCreateApplicationRequest(payload)),
    });

    if (res.ok) return { ok: true };

    if (res.status === 401) {
      return { ok: false, retryable: true, error: 'Session expired.' };
    }
    if (res.status >= 500) {
      return { ok: false, retryable: true, error: 'Applytic is temporarily unavailable.' };
    }

    const body = await res.json().catch(() => ({}));
    return { ok: false, retryable: false, error: body.error || `Request failed (${res.status})` };
  } catch {
    // Network error - offline, DNS failure, etc.
    return { ok: false, retryable: true, error: 'Network error.' };
  }
}

// Short in-memory cache only - lost on service worker restart, which just
// means one extra fetch next time. Not worth persisting for a 60s TTL.
let applicationsCache = null;
let applicationsCacheAt = 0;
const APPLICATIONS_CACHE_TTL_MS = 60_000;

async function fetchApplicationsCached(idToken) {
  if (applicationsCache && Date.now() - applicationsCacheAt < APPLICATIONS_CACHE_TTL_MS) {
    return applicationsCache;
  }
  const res = await fetch(`${API_BASE}/applications`, { headers: { Authorization: idToken } });
  if (!res.ok) throw new Error(`Failed to fetch applications (${res.status})`);
  const data = await res.json();
  applicationsCache = data.applications || [];
  applicationsCacheAt = Date.now();
  return applicationsCache;
}

function norm(s) {
  return (s || '').trim().toLowerCase();
}

// URL match first (strongest signal - same canonical posting), falling
// back to company+role (case-insensitive) since a user might have added
// the same job from a different source/URL than the one being viewed now.
function findDuplicate(applications, jobData) {
  const urlMatch = applications.find(
    (a) => a.jobDescUrl && jobData.jobDescUrl && a.jobDescUrl === jobData.jobDescUrl
  );
  if (urlMatch) return urlMatch;

  const company = norm(jobData.company);
  const role = norm(jobData.role);
  return applications.find((a) => norm(a.company) === company && norm(a.role) === role) || null;
}

// Attempts to sync one item: live POST if signed in, queue otherwise.
async function syncApplication(payload) {
  const idToken = await getValidIdToken();
  if (!idToken) {
    await queueApplication(payload);
    return { ok: true, queued: true };
  }

  const result = await postApplication(idToken, payload);
  if (result.ok) {
    applicationsCache = null; // invalidate - a new record just landed
    return { ok: true, queued: false };
  }
  if (result.retryable) {
    await queueApplication(payload);
    return { ok: true, queued: true };
  }
  // Non-retryable - surface the real error rather than silently queueing
  // something that will never succeed (e.g. a validation error).
  return { ok: false, error: result.error };
}

// Drains the pending queue against a live token. Best-effort - stops at the
// first retryable failure (network/auth still down) and leaves the rest
// queued for next time; non-retryable items are dropped with a console
// warning rather than stuck retrying forever.
async function flushQueue() {
  const idToken = await getValidIdToken();
  if (!idToken) return;

  const queue = await getQueue();
  if (queue.length === 0) return;

  let stoppedAt = queue.length; // default: everything processed
  for (let i = 0; i < queue.length; i++) {
    const result = await postApplication(idToken, queue[i]);
    if (!result.ok && result.retryable) {
      // Still can't reach the API - stop here and keep this item plus
      // everything after it queued for next time.
      stoppedAt = i;
      break;
    }
    if (!result.ok) {
      console.warn('Applytic: dropping un-syncable queued item', queue[i], result.error);
    }
  }
  await setQueue(queue.slice(stoppedAt));
}

// Returns a valid idToken, refreshing first if the stored one is expired
// (or about to expire within 60s). Returns null if the user isn't signed in
// or the refresh token itself has expired.
async function getValidIdToken() {
  const auth = await getStoredAuth();
  if (!auth) return null;

  if (Date.now() < auth.expiresAt - 60_000) {
    return auth.idToken;
  }

  try {
    const refreshed = await refreshTokens(auth.refreshToken);
    await setStoredAuth(refreshed);
    return refreshed.idToken;
  } catch {
    await clearStoredAuth();
    return null;
  }
}

// ── Message handling (popup + content scripts talk to the worker via this) ────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      switch (message.type) {
        case 'SIGN_IN': {
          const tokens = await signIn();
          sendResponse({ ok: true, signedIn: true, hasToken: !!tokens.idToken });
          break;
        }
        case 'SIGN_OUT': {
          await signOut();
          sendResponse({ ok: true, signedIn: false });
          break;
        }
        case 'GET_AUTH_STATE': {
          const idToken = await getValidIdToken();
          sendResponse({ ok: true, signedIn: !!idToken });
          break;
        }
        case 'CHECK_DUPLICATE': {
          const idToken = await getValidIdToken();
          if (!idToken) {
            sendResponse({ ok: true, duplicate: null }); // nothing to check against
            break;
          }
          try {
            const apps = await fetchApplicationsCached(idToken);
            const dup = findDuplicate(apps, message.payload);
            sendResponse({
              ok: true,
              duplicate: dup ? { appId: dup.appId, status: dup.status, company: dup.company, role: dup.role } : null,
            });
          } catch {
            sendResponse({ ok: true, duplicate: null }); // fail quiet - never blocks the Add flow
          }
          break;
        }
        case 'GET_QUEUE': {
          sendResponse({ ok: true, queue: await getQueue() });
          break;
        }
        case 'REMOVE_QUEUE_ITEM': {
          const queue = await getQueue();
          const updated = queue.filter((_, i) => i !== message.index);
          await setQueue(updated);
          sendResponse({ ok: true, queue: updated });
          break;
        }
        case 'FLUSH_QUEUE_NOW': {
          await flushQueue();
          sendResponse({ ok: true, queue: await getQueue() });
          break;
        }
        case 'ADD_APPLICATION': {
          // Opportunistic flush first - if the queue built up while signed
          // out or offline and connectivity/auth is back, clear it before
          // adding the new item on top.
          await flushQueue();
          const result = await syncApplication(message.payload);
          sendResponse(result);
          break;
        }
        default:
          sendResponse({ ok: false, error: `Unknown message type: ${message.type}` });
      }
    } catch (err) {
      sendResponse({ ok: false, error: err.message || String(err) });
    }
  })();
  // Keep the message channel open for the async response above.
  return true;
});

// Exported in case a later session (e.g. an options page) needs direct
// access from within the same service worker module graph.
export { getValidIdToken };
