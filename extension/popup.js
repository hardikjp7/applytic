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
  dupWarning: document.getElementById('dup-warning'),
  queueIndicator: document.getElementById('queue-indicator'),
  queueCountText: document.getElementById('queue-count-text'),
};

const STATUS_LABELS = {
  applied: 'Applied', screened: 'Screened', interview: 'Interview',
  offer: 'Offer', rejected: 'Rejected', withdrawn: 'Withdrawn',
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
    els.dupWarning.classList.add('hidden'); // cleared until checkDuplicate resolves
  }
}

function setQueueIndicator(queue) {
  const count = queue.length;
  els.queueIndicator.classList.toggle('hidden', count === 0);
  if (count > 0) {
    els.queueCountText.textContent = `${count} pending sync${count !== 1 ? 'es' : ''}`;
  }
}

// Runs after the job card is already showing - non-blocking, only ever
// upgrades the UI with a warning if one applies. Never gates the Add button.
async function checkDuplicate(jobData) {
  const res = await chrome.runtime.sendMessage({ type: 'CHECK_DUPLICATE', payload: jobData });
  if (res && res.ok && res.duplicate) {
    const label = STATUS_LABELS[res.duplicate.status] || res.duplicate.status;
    els.dupWarning.textContent = `Already tracked - status: ${label}`;
    els.dupWarning.classList.remove('hidden');
  } else {
    els.dupWarning.classList.add('hidden');
  }
}

function getCurrentJobFromActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab || !tab.id) { resolve(null); return; }
      chrome.tabs.sendMessage(tab.id, { type: 'GET_CURRENT_JOB' }, (res) => {
        if (chrome.runtime.lastError || !res || !res.ok) { resolve(null); return; }
        resolve(res.data || null);
      });
    });
  });
}

async function refreshState() {
  showTopLevel('loading');

  const [authRes, jobData, queueRes] = await Promise.all([
    chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' }),
    getCurrentJobFromActiveTab(),
    chrome.runtime.sendMessage({ type: 'GET_QUEUE' }),
  ]);

  if (!authRes || !authRes.ok) {
    showError((authRes && authRes.error) || 'Something went wrong.');
    return;
  }

  setAuthRow(authRes.signedIn);
  setJobSection(jobData);
  setQueueIndicator(queueRes && queueRes.ok ? queueRes.queue : []);
  showTopLevel('main');

  // Fire-and-forget - only ever upgrades the UI once it resolves, never
  // blocks showing the job card itself.
  if (jobData) checkDuplicate(jobData);
}

document.getElementById('manage-queue-btn').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

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

  chrome.runtime.sendMessage({ type: 'ADD_APPLICATION', payload: jobData }, async (res) => {
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

    const queueRes = await chrome.runtime.sendMessage({ type: 'GET_QUEUE' });
    if (queueRes && queueRes.ok) setQueueIndicator(queueRes.queue);
  });
});

document.getElementById('retry-btn').addEventListener('click', refreshState);

refreshState();