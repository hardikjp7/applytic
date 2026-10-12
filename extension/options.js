const els = {
  authDot: document.getElementById('auth-dot'),
  authLabel: document.getElementById('auth-label'),
  authActionBtn: document.getElementById('auth-action-btn'),
  queueList: document.getElementById('queue-list'),
  queueEmpty: document.getElementById('queue-empty'),
  syncNowBtn: document.getElementById('sync-now-btn'),
};

async function handleSignIn() {
  const res = await chrome.runtime.sendMessage({ type: 'SIGN_IN' });
  if (!res.ok) {
    alert(res.error || 'Sign-in failed. Please try again.');
  }
  await refresh();
}

async function handleSignOut() {
  await chrome.runtime.sendMessage({ type: 'SIGN_OUT' });
  await refresh();
}

function setAuthRow(signedIn) {
  els.authDot.classList.toggle('status-dot-off', !signedIn);
  els.authLabel.textContent = signedIn ? 'Connected' : 'Not signed in';
  els.authActionBtn.textContent = signedIn ? 'Sign out' : 'Sign in';
  els.authActionBtn.onclick = signedIn ? handleSignOut : handleSignIn;
}

function renderQueue(queue) {
  els.queueList.innerHTML = '';
  els.queueEmpty.classList.toggle('hidden', queue.length > 0);

  queue.forEach((item, index) => {
    const row = document.createElement('div');
    row.className = 'queue-item';

    const info = document.createElement('div');
    info.className = 'queue-item-info';
    const when = item.queuedAt ? new Date(item.queuedAt).toLocaleString() : '';
    info.innerHTML = `<strong>${escapeHtml(item.role || '(unknown role)')}</strong><br>` +
      `${escapeHtml(item.company || '(unknown company)')}<br>` +
      `<span class="queue-item-meta">Queued ${when}</span>`;

    const removeBtn = document.createElement('button');
    removeBtn.className = 'link-btn';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', async () => {
      const res = await chrome.runtime.sendMessage({ type: 'REMOVE_QUEUE_ITEM', index });
      if (res && res.ok) renderQueue(res.queue);
    });

    row.appendChild(info);
    row.appendChild(removeBtn);
    els.queueList.appendChild(row);
  });
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

els.syncNowBtn.addEventListener('click', async () => {
  els.syncNowBtn.disabled = true;
  els.syncNowBtn.textContent = 'Syncing...';
  const res = await chrome.runtime.sendMessage({ type: 'FLUSH_QUEUE_NOW' });
  els.syncNowBtn.disabled = false;
  els.syncNowBtn.textContent = 'Sync now';
  if (res && res.ok) renderQueue(res.queue);
});

async function refresh() {
  const [authRes, queueRes] = await Promise.all([
    chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' }),
    chrome.runtime.sendMessage({ type: 'GET_QUEUE' }),
  ]);
  if (authRes && authRes.ok) setAuthRow(authRes.signedIn);
  if (queueRes && queueRes.ok) renderQueue(queueRes.queue);
}

refresh();
