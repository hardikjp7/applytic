# Applytic Browser Extension (v3.2 - in progress)

## commit 1 scope (this drop)
- Manifest V3 scaffold with a pinned `key` so the extension ID is stable across dev reloads (`eghmfcibiaehpeaekkpnogbfbnelfakj`) - without this, `chrome.identity.launchWebAuthFlow`'s redirect URI would change every time the unpacked extension reloads, breaking the Cognito callback URL registration
- OAuth PKCE sign-in against the existing Cognito Hosted UI (same public client as the web app, no new Cognito resources)
- Token storage + silent refresh in `background.js`
- Popup UI: sign in / sign out / connection status

## Not yet included (later commits)
- Content scripts (LinkedIn first - commit 2, then Indeed/Glassdoor - commit 3)
- `POST /applications` API call + backend CORS update (commit 4)
- Options page, duplicate-detection nudge (commit 5)

## Local dev setup
1. `chrome://extensions` -> enable Developer mode
2. "Load unpacked" -> select this `extension/` directory
3. Note the extension ID Chrome shows - it should match `eghmfcibiaehpeaekkpnogbfbnelfakj` (the pinned key guarantees this). If it doesn't match, the `key` field in `manifest.json` was stripped or altered.
4. Click the toolbar icon -> Sign in. This opens a Chrome-managed auth window against the Hosted UI.

## Required CDK change before sign-in will work
The Cognito `UserPoolClient` needs this extension's redirect URI added to `callbackUrls`:
```
https://eghmfcibiaehpeaekkpnogbfbnelfakj.chromiumapp.org/
```
See the `str_replace` guide provided alongside this drop for the exact `cdk/lib/applytic-stack.ts` edit. Requires `cdk deploy` before testing sign-in end to end.

## Key management note
The private key (`key.pem`, generated locally, not included in this drop) should be stored securely outside the repo - it is only needed again if you want to re-derive the same extension ID on a different machine. It is never bundled with the extension or committed. If it's lost, a new key can be pinned, but the extension ID (and therefore the registered Cognito redirect URI) will change and need updating in CDK again.
