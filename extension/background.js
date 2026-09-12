import { generateCodeVerifier, generateCodeChallenge } from './lib/pkce.js';

// ── Config ────────────────────────────────────────────────────────────────────
// Matches cdk/lib/applytic-stack.ts - same Hosted UI domain and public client
// (no client secret - authorizationCodeGrant + PKCE) used by the web app.
const COGNITO_DOMAIN = 'https://applytic-auth.auth.us-east-1.amazoncognito.com';
const CLIENT_ID = '1kf85rr01ra5c7s2vfirh8mt8s';
const SCOPES = 'email openid profile';

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

// Exported for Session 4 (API integration) to import getValidIdToken directly
// within the same service worker context.
export { getValidIdToken };
