const els = {
  loading: document.getElementById('loading'),
  main: document.getElementById('main'),
  error: document.getElementById('error'),
  authDot: document.getElementById('auth-dot'),
  authLabel: document.getElementById('auth-label'),
  authActionBtn: document.getElementById('auth-action-btn'),
  jobFound: document.getElementById('job-found'),
  jobNotFound: document.getElementById('job-not-found'),
  jobRole: document.querySelector('#job-found .job-role'),
  jobCompany: document.querySelector('#job-found .job-company'),
  addBtn: document.getElementById('add-btn'),
  addFeedback: document.getElementById('add-feedback'),
};

const topLevelStates = { loading: els.loading, main: els.main, error: els.error };

function showTopLevel(name) {
  Object.values(topLevelStates).forEach((el) => el.classList.add('hidden'));
  topLevelStates[name].classList.remove('hidden');
}

function showError(message) {
  els.error.querySelector('.error-msg').textContent = message;
  showTopLevel('error');
}

async function handleSignIn() {
  showTopLevel('loading');
  const res = await chrome.runtime.sendMessage({ type: 'SIGN_IN' });
  if (!res.ok) {
    showError(res.error || 'Sign-in failed. Please try again.');
    return;
  }
  await refreshState();
}

async function handleSignOut() {
  showTopLevel('loading');
  await chrome.runtime.sendMessage({ type: 'SIGN_OUT' });
  await refreshState();
}

function setAuthRow(signedIn) {
  els.authDot.classList.toggle('status-dot-off', !signedIn);
  els.authLabel.textContent = signedIn ? 'Connected' : 'Not signed in';
  els.authActionBtn.textContent = signedIn ? 'Sign out' : 'Sign in';
  // Reassigned each render rather than two permanently-bound listeners on
  // separate buttons - one button, whose behavior follows current state.
  els.authActionBtn.onclick = signedIn ? handleSignOut : handleSignIn;
}

function setJobSection(jobData) {
  els.jobFound.classList.toggle('hidden', !jobData);
  els.jobNotFound.classList.toggle('hidden', !!jobData);
  if (jobData) {
    els.jobRole.textContent = jobData.role;
    els.jobCompany.textContent = jobData.company;
    els.addFeedback.classList.add('hidden');
    els.addBtn.disabled = false;
    els.addBtn.textContent = 'Add to Applytic';
  }
}

// Queries the active tab's content script directly, rather than trusting
// any cached/background state - this is the freshest possible read of
// "what's on screen right now," and it's only ever asked once per popup
// open, so there's no cost to always going straight to the source.
function queryFrame(tabId, frameId) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { type: 'GET_CURRENT_JOB' }, { frameId }, (res) => {
      // chrome.runtime.lastError fires when this particular frame has no
      // content script loaded - expected for most frames on most pages,
      // not an error worth surfacing.
      if (chrome.runtime.lastError || !res || !res.ok) {
        resolve(null);
        return;
      }
      resolve(res.data || null);
    });
  });
}

// Most pages only have one relevant frame (frameId 0, the main document),
// but some sites (Indeed's job view, confirmed live) render the actual job
// content inside an embedded iframe instead. chrome.tabs.sendMessage
// without an explicit frameId sends to every frame but only surfaces one
// reply, and which one isn't reliable - so frames are enumerated and
// queried individually here, taking the first one that actually has data.
async function getCurrentJobFromActiveTab() {
  const tabs = await new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, resolve);
  });
  const tab = tabs[0];
  if (!tab || !tab.id) return null;

  let frames;
  try {
    frames = await chrome.webNavigation.getAllFrames({ tabId: tab.id });
  } catch {
    frames = null;
  }
  // Fallback to just the main frame if webNavigation is unavailable for
  // any reason - still correct for every site except Indeed's iframe case.
  if (!frames || frames.length === 0) {
    frames = [{ frameId: 0 }];
  }

  for (const frame of frames) {
    const data = await queryFrame(tab.id, frame.frameId);
    if (data) return data;
  }
  return null;
}

async function refreshState() {
  showTopLevel('loading');

  const [authRes, jobData] = await Promise.all([
    chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' }),
    getCurrentJobFromActiveTab(),
  ]);

  if (!authRes || !authRes.ok) {
    showError((authRes && authRes.error) || 'Something went wrong.');
    return;
  }

  setAuthRow(authRes.signedIn);
  setJobSection(jobData);
  showTopLevel('main');
}

els.addBtn.addEventListener('click', async () => {
  const jobData = await getCurrentJobFromActiveTab();
  if (!jobData) {
    // Rare - the page changed between popup open and click. Re-check
    // instead of sending stale data.
    await refreshState();
    return;
  }

  els.addBtn.disabled = true;
  els.addBtn.textContent = 'Adding...';
  els.addFeedback.classList.add('hidden');

  chrome.runtime.sendMessage({ type: 'ADD_APPLICATION', payload: jobData }, (res) => {
    els.addBtn.disabled = false;

    if (chrome.runtime.lastError || !res || !res.ok) {
      els.addBtn.textContent = 'Add to Applytic';
      els.addFeedback.textContent = (res && res.error) || 'Could not add this application.';
      els.addFeedback.className = 'feedback feedback-error';
      return;
    }

    els.addBtn.textContent = res.queued ? 'Queued' : 'Added';
    els.addFeedback.textContent = res.queued
      ? 'Saved - will sync once signed in.'
      : 'Added to Applytic.';
    els.addFeedback.className = 'feedback feedback-success';
  });
});

document.getElementById('retry-btn').addEventListener('click', refreshState);

refreshState();
