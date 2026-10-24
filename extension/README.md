# Applytic Browser Extension

Add a job to your [Applytic](https://hardikjp7.github.io/applytic) tracker straight from the job posting - no copy and paste.

Open a job on LinkedIn, Indeed, or Glassdoor, click the Applytic icon in your toolbar, and hit **Add to Applytic**. The company, role, and link are filled in for you.

**Version:** 1.0.1 | **Works in:** Chrome, Edge, Brave and other Chromium browsers (tested in Brave) | **License:** Apache 2.0

---

## Supported sites

| Site | Where it works |
|---|---|
| LinkedIn | Job pages under `linkedin.com/jobs` - a job's own page, or search results with a job selected |
| Indeed | A job's own page (`/viewjob`), or search results with a job selected. All regional sites such as `in.indeed.com` |
| Glassdoor | Job listing pages and job panels on `glassdoor.com`, `.co.in`, `.co.uk`, `.ca`, `.com.au`, `.de`, `.fr`, `.ie`, `.sg` |

---

## Install

The extension isn't on the Chrome Web Store yet, so it installs through Developer mode. It takes about a minute.

1. Download `applytic-extension.zip` from the [latest release](https://github.com/hardikjp7/applytic/releases/latest).
2. Unzip it somewhere you won't delete, for example `Documents/applytic-extension`. The browser loads the extension from this folder, so keep it there.
3. Open your browser's extensions page:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
   - Brave: `brave://extensions`
4. Turn on **Developer mode** (top right).
5. Click **Load unpacked** and select the unzipped folder - the one that contains `manifest.json`.
6. Click the puzzle-piece icon in your toolbar and pin **Applytic**.

Your browser may show a "developer mode extensions" notice now and then. That is normal for extensions installed outside the store.

---

## Getting started

1. Click the Applytic icon and choose **Sign in**. A sign-in window opens - use the same account as the Applytic web app (email or Google).
2. Open any job posting on a supported site.
3. Click the Applytic icon. You will see the job's title and company.
4. Click **Add to Applytic**. The job lands on your board with the status **Applied**, the right source, and a link back to the posting.

The popup shows **Connected** at the top when you're signed in.

### Already tracked?

If the job is already on your board, the popup shows an amber note such as *Already tracked - status: Interview*. Add is never blocked - you can still add it again if you want to.

### Signed out or offline?

You can still click Add. The job shows **Queued** and is saved on your device. It syncs automatically the next time you sign in, or the next time you add a job while connected.

To check or manage queued jobs, click **Manage** in the popup (it appears when something is waiting), or right-click the extension icon and choose **Options**. There you can:
- see everything waiting to sync,
- remove an item you don't want,
- press **Sync now** to retry.

---

## Permissions

| Permission | Why it's needed |
|---|---|
| `identity` | Opens the browser's sign-in window for your Applytic account |
| `storage` | Keeps your sign-in session and the offline queue on your device |
| `activeTab` | Reads the job posting you are looking at when you open the popup |
| Access to LinkedIn, Indeed and Glassdoor job pages | The small script that reads the job title and company runs only on these sites |
| Access to the Applytic API and sign-in service | To add your jobs and check for duplicates |

---

## Privacy

- The extension reads the job title, company and link of the posting **only when you open the popup**.
- That information goes to your Applytic account and nowhere else. There is no analytics and no third-party service.
- To check for duplicates it fetches your own application list from Applytic.
- Your sign-in session and any queued jobs are stored locally in your browser. **Sign out** removes the session; queued jobs stay until they sync or you remove them in Options.
- To remove everything, remove the extension from your extensions page.

---

## Troubleshooting

**The popup says "Visit a job posting..."**
Make sure a job is actually open, not just a list. On search pages, click a job so its details appear, then open the popup again. If it still shows nothing, refresh the page once.

**It worked before but doesn't now**
LinkedIn, Indeed and Glassdoor change their pages from time to time, which can break reading the job details. Please [open an issue](https://github.com/hardikjp7/applytic/issues) with the site and the link to the posting.

**The sign-in window closes without signing me in**
Try again and finish the sign-in in the same window. If it keeps failing, check that the extension ID on your extensions page is `eghmfcibiaehpeaekkpnogbfbnelfakj`. A different ID means the folder was altered and sign-in will not work.

**It says Queued, not Added**
You are signed out or offline. Sign in and the job syncs by itself, or use **Sync now** in Options.

**My Glassdoor country isn't supported**
Only the domains listed above are included. Open an issue with your Glassdoor domain and it can be added.

---

## Updating

1. Download the new `applytic-extension.zip` from the [releases page](https://github.com/hardikjp7/applytic/releases).
2. Replace the contents of your existing extension folder with the new files.
3. Open your extensions page and click the reload icon on the Applytic card.

You stay signed in across updates.

---

## For developers and self-hosters

If you run your own Applytic backend, the extension needs three things changed:

1. In `background.js`, set `COGNITO_DOMAIN`, `CLIENT_ID` and `API_BASE` to your deployment, and update `host_permissions` in `manifest.json` to match.
2. The extension ID is fixed by the `key` field in `manifest.json` (`eghmfcibiaehpeaekkpnogbfbnelfakj`). Register `https://eghmfcibiaehpeaekkpnogbfbnelfakj.chromiumapp.org/` as a callback URL on your Cognito app client.
3. Add `chrome-extension://eghmfcibiaehpeaekkpnogbfbnelfakj` to your API's CORS allowed origins, then deploy.

Source and issues: [github.com/hardikjp7/applytic](https://github.com/hardikjp7/applytic)
