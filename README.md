# The Breath Reset

A static website with a concise homepage and dedicated Programme, Breathe with me (`breathe-with-me.html`), Practice and About pages. The Breath Lab lives on Practice; older homepage anchors redirect to their new destinations.

Serve this folder with any static file server, for example `python3 -m http.server 8765`.

Signup forms share `script.js` and `signup-config.js`. Run the signup integration checks with `node --test integrations/google-apps-script/test.cjs`.

`events.html` redirects to `breathe-with-me.html`, preserving query strings and section anchors. The sessions signup retains `events.html` as its integration source for compatibility with the existing Apps Script endpoint.

The Practice page is temporarily hidden from site navigation and the homepage. Its content and direct URL remain available so it can be restored later.
