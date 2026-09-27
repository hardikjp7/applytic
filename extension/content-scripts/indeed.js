// Applytic - Indeed adapter (v3.2, confirmed against live data)
// Loaded after shared.js on https://*.indeed.com/*
//
// Confirmed live: Indeed's job view uses a heavily custom rendering layer
// (React Native Web - "css-146c3p1"-style hashed classes, no relation to
// Indeed's own marketing-site CSS), not a plain HTML document with normal
// semantic markup. The job title carries data-testid="vj-job-title" - an
// explicit test hook, about as durable as a selector gets.
// (An earlier attempt suspected this content lived inside an iframe and
// added all_frames/match_origin_as_fallback handling for that - turned out
// to be a red herring, the only real iframe present is a Google Tag
// Manager tracking pixel. The manifest changes are harmless to leave in
// place but weren't the actual fix.)
//
// Company name markup differs by page type - confirmed live, not assumed:
//   - On /jobs?...&vjk=... (search-embedded panel): no test id, just a
//     link whose href contains "/cmp/{CompanyName}".
//   - On /viewjob?jk=... (standalone page): data-testid="vj-company-name"
//     directly on a plain <div>, no <a> tag at all - so the href-based
//     approach alone can't find it here regardless of scoping.
// Tries the test id first (works on /viewjob, more stable where present),
// falls back to the href-scoped search (works on the search panel).
//
// Also confirmed live: Indeed injects its own self-promo ad ("Work at
// Indeed") elsewhere on some pages, which also links through /cmp/ - so
// the href-based fallback searches outward from the title element first
// (closest enclosing container, not the whole document) and filters out
// any candidate matching that known self-promo phrasing.

(function () {
  const TITLE_SELECTORS = ['[data-testid="vj-job-title"]'];
  const COMPANY_TESTID_SELECTORS = ['[data-testid="vj-company-name"]'];

  function queryFirst(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }

  function textOf(el) {
    return el ? el.textContent.trim().replace(/\s+/g, ' ') : '';
  }

  function isPromoText(text) {
    // Indeed's own "Work at Indeed" (and presumably similar) self-promo
    // links use this phrasing - not a real employer name.
    return /^work at\b/i.test(text.trim());
  }

  function getCompanyViaHrefNearTitle() {
    const titleEl = queryFirst(TITLE_SELECTORS);
    let node = titleEl ? titleEl.parentElement : null;
    let depth = 0;

    while (node && depth < 10) {
      const candidates = [...node.querySelectorAll('a[href*="/cmp/"]')]
        .map(textOf)
        .filter((text) => text && !isPromoText(text));
      if (candidates.length > 0) return candidates[0];
      node = node.parentElement;
      depth++;
    }

    const fallback = [...document.querySelectorAll('a[href*="/cmp/"]')]
      .map(textOf)
      .filter((text) => text && !isPromoText(text));
    return fallback[0] || '';
  }

  function getCompany() {
    const viaTestId = textOf(queryFirst(COMPANY_TESTID_SELECTORS));
    if (viaTestId && !isPromoText(viaTestId)) return viaTestId;
    return getCompanyViaHrefNearTitle();
  }

  // Indeed's canonical job identifier is the `jk` param, present as either
  // ?jk=... (direct /viewjob) or ?vjk=... (search-embedded panel).
  function canonicalUrl() {
    const params = new URLSearchParams(window.location.search);
    const jobKey = params.get('jk') || params.get('vjk');
    if (jobKey) {
      return `${window.location.origin}/viewjob?jk=${jobKey}`;
    }
    return window.location.href.split('#')[0];
  }

  function getJobData() {
    const role = textOf(queryFirst(TITLE_SELECTORS));
    const company = getCompany();
    if (!role || !company) return null;

    return {
      company,
      role,
      source: 'job-board',
      jobDescUrl: canonicalUrl(),
    };
  }

  window.ApplyticContent.registerJobDataProvider(getJobData, 'indeed');
})();
