const states = {
  loading: document.getElementById('loading'),
  signedOut: document.getElementById('signed-out'),
  signedIn: document.getElementById('signed-in'),
  error: document.getElementById('error'),
};

function show(name) {
  Object.values(states).forEach((el) => el.classList.add('hidden'));
  states[name].classList.remove('hidden');
}

function showError(message) {
  states.error.querySelector('.error-msg').textContent = message;
  show('error');
}

async function refreshState() {
  show('loading');
  const res = await chrome.runtime.sendMessage({ type: 'GET_AUTH_STATE' });
  if (!res.ok) {
    showError(res.error || 'Something went wrong.');
    return;
  }
  show(res.signedIn ? 'signedIn' : 'signedOut');
}

document.getElementById('sign-in-btn').addEventListener('click', async () => {
  show('loading');
  const res = await chrome.runtime.sendMessage({ type: 'SIGN_IN' });
  if (!res.ok) {
    showError(res.error || 'Sign-in failed. Please try again.');
    return;
  }
  await refreshState();
});

document.getElementById('sign-out-btn').addEventListener('click', async () => {
  show('loading');
  await chrome.runtime.sendMessage({ type: 'SIGN_OUT' });
  await refreshState();
});

document.getElementById('retry-btn').addEventListener('click', refreshState);

refreshState();
