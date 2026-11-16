/** Bind this script to the private signup spreadsheet. Run setup once before deploying. */
const TAB_NAME = 'Signups';
const HEADERS = ['Joined at', 'Email', 'Interest', 'Source page', 'Consent'];
const INTERESTS = ['Six-week programme', 'Classes, workshops and programme'];

function setup() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  if (!book) throw new Error('Open Apps Script from Extensions in your signup spreadsheet.');
  PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', book.getId());
  const sheet = book.getSheetByName(TAB_NAME) || book.insertSheet(TAB_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#dbe6d7');
    sheet.setColumnWidth(1, 170);
    sheet.setColumnWidths(2, 4, 260);
  }
}

function json_(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}

function safeCell_(value) {
  return /^[=+@\-]/.test(value) ? "'" + value : value;
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  const email = String(p.email || '').trim().toLowerCase();
  const interest = String(p.list || '');
  const source = String(p.source || '');
  if (p._gotcha) return json_({ ok: false });
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ||
      !INTERESTS.includes(interest) || p.consent !== 'yes' ||
      !['index.html', 'practice.html', 'about.html', 'events.html'].includes(source)) {
    return json_({ ok: false, error: 'Please check your email and try again.' });
  }
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return json_({ ok: false, error: 'Please try again in a moment.' });
  let added = false;
  try {
    const id = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
    const sheet = SpreadsheetApp.openById(id).getSheetByName(TAB_NAME);
    if (!sheet) throw new Error('Run setup first.');
    const count = sheet.getLastRow() - 1;
    const rows = count > 0 ? sheet.getRange(2, 2, count, 2).getValues() : [];
    // Retrying after a network error must not add duplicate rows or send duplicate emails.
    const exists = rows.some(row => String(row[0]).replace(/^'/, '').toLowerCase() === email && row[1] === interest);
    if (!exists) {
      sheet.appendRow([new Date(), safeCell_(email), interest, source, 'Email updates about ' + interest.toLowerCase()]);
      SpreadsheetApp.flush();
      added = true;
    }
  } catch (error) {
    console.error('Signup could not be saved');
    return json_({ ok: false, error: 'We couldn’t save that. Please try again.' });
  } finally {
    lock.releaseLock();
  }
  // Optional owner notifications. Saving the signup succeeds even if mail quota is exhausted.
  if (added) {
    try {
      const recipient = PropertiesService.getScriptProperties().getProperty('NOTIFY_EMAIL');
      if (recipient && MailApp.getRemainingDailyQuota() > 0) {
        MailApp.sendEmail(recipient, 'New Breath Reset signup', email + '\nInterest: ' + interest + '\nSource: ' + source);
      }
    } catch (error) {
      console.warn('Signup saved; notification unavailable');
    }
  }
  return json_({ ok: true });
}

// Never expose subscriber data through the public endpoint.
function doGet() {
  return json_({ service: 'The Breath Reset signup' });
}
