// Applytic - shared content-script helper (v3.2, popup-triggered flow)
//
// Earlier versions of this file ran a continuous MutationObserver + interval
// loop to keep an in-page "Add to Applytic" button injected and positioned
// correctly at all times. That meant fighting each site's DOM for a stable
// injection anchor - LinkedIn's hashed classes alone took two rounds of
// live debugging just for placement, before Indeed/Glassdoor were even
// tested. None of that placement problem exists if there's no in-page UI at
// all: the popup now asks "is there a job here?" only once, at the moment
// the user clicks the toolbar icon while looking at a job posting. So this
// file's only job is answering that question - extraction logic still lives
// per-adapter (LinkedIn's document.title trick, etc.), but there is nothing
// left here about watching for DOM changes or finding somewhere to inject.

window.ApplyticContent = (function () {
  // getJobData: () => jobData object, or null if this isn't a ready job
  // posting page right now.
  function registerJobDataProvider(getJobData, source) {
    console.log(`[Applytic] ${source} content script loaded on`, window.location.href);

    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message.type !== 'GET_CURRENT_JOB') return false;

      let data = null;
      try {
        data = getJobData();
      } catch (err) {
        console.warn('[Applytic] extraction failed', err);
      }

      console.log('[Applytic] extraction result:', data);
      sendResponse({ ok: true, data });
      return true;
    });
  }

  return { registerJobDataProvider };
})();
