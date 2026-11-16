# Connect the waitlist to Google Sheets

1. Create a **private** Google spreadsheet called **The Breath Reset — Signups**.
2. In that spreadsheet, open **Extensions → Apps Script**. Paste `Code.gs` into the editor and save.
3. Run `setup` once and authorise access. This creates a formatted `Signups` tab and stores the spreadsheet ID in script properties.
4. Optional: in **Project Settings → Script properties**, add `NOTIFY_EMAIL` with your notification address. Leave it absent for spreadsheet-only collection. No visitor confirmation email is sent.
5. Choose **Deploy → New deployment → Web app**. Execute as **Me**, access **Anyone**. The write endpoint is public; the spreadsheet stays private. Authorise the deployment from your Google account.
6. Copy the deployment URL ending in `/exec` into `window.BREATH_RESET_SIGNUP_URL` in the site's `signup-config.js`. Never copy a password, token or Google credential.
7. Test from the served site with an address you control. Confirm a row appears and, if enabled, the owner notification arrives. Submit again to verify the same email/interest pair does not create another row. Confirm both programme and closing forms record their distinct interests.

The browser uses a standard URL-encoded POST and follows the Google response redirect. It only shows success after reading `{ "ok": true }`; an opaque response or blocked redirect is never treated as success. Test on the real site origin before launch. If Google returns a login page, verify access is **Anyone**, not “Anyone with a Google account”, and use `/exec`, not `/dev`.

After changes to Apps Script, use **Deploy → Manage deployments → Edit → New version** to update the existing URL.

The script validates inputs, escapes spreadsheet formulas, uses a write lock, ignores honeypot entries, and deduplicates email/interest pairs. A public endpoint can still receive spam; it is not a newsletter platform. Honour removal requests before sending updates. Google service quotas apply; notification failures never undo saved signups. See [Apps Script web apps](https://developers.google.com/apps-script/guides/web) and [quotas](https://developers.google.com/apps-script/guides/services/quotas).

## Local checks

Run `node integrations/google-apps-script/test.cjs` from the repository. These use mocked Google services to check saving, deduplication, validation and failure handling; they do not establish live Google delivery.
