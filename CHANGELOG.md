# Changelog

All notable changes to the UC Automation Portal are documented here.

---

## [v1.1] — 2026-04-01

### New Features

**Role-Based Access Control**
- Added `admin` and `user` roles to the user model
- Admin users have full access to all features including CSV batch upload and user management
- Regular users can access Provision and History pages only

**Admin User Management Page**
- New `/admin/users` page accessible only to admin accounts
- Admins can create new user accounts with username, password, and role assignment
- Admins can reset passwords for any user
- Admins can delete user accounts (cannot delete own account)
- Admin link visible in navigation bar for admin users only

**CSV Upload Restriction**
- CSV batch upload is now restricted to admin users only
- Regular users see a locked state with a message explaining the restriction
- CSV template download remains available to all users
- `/api/upload-csv` endpoint returns 403 if accessed by non-admin

### Bug Fixes

**AXL DN Search Pattern**
- Fixed Mirror DN search failing for E.164 numbers (`\+19786007919`)
- Search pattern corrected from `\+%{digits}` to `%{digits}` to match CUCM route plan lookup behavior
- DNs with or without `\+` prefix are now handled correctly on input

**Device Pool Missing (Step 4)**
- Fixed Jabber provisioning failing with "A Device Pool is required" error
- When no physical SEP phone is associated with the Mirror DN, the portal now falls back to using the CSF (Jabber) device to retrieve Device Pool, CSS, Location, and MRGL

**Primary DN Error (Step 5)**
- Fixed "Primary Extension DN should be associated with the associated devices" error
- Primary DN is now only set if a User DN is provided in the form
- If User DN is left blank (new user), Step 5 skips setting primary DN instead of failing
- Internal extension numbers (e.g. `60012`) no longer incorrectly get `\+` prefix applied

**Timezone Display**
- Fixed portal log timestamps showing UTC time instead of local time
- Log timestamps now correctly display Eastern Time (EDT/EST)
- History page job times converted from UTC to local time on display

**Datetime Subtraction Error**
- Fixed `TypeError: can't subtract offset-naive and offset-aware datetimes` when calculating job duration
- Both `started_at` and `finished_at` are now normalized before subtraction

### Optional Fields

- **Phone MAC Address** and **Phone Model** are now optional — leave blank for Jabber-only provisioning (Step 3 skipped)
- **User DN** is now optional — leave blank for brand new users with no existing DN (Step 2 skipped)
- Form labels updated: "Mirror DN" → "Template DN", "New DN" → "User DN" for clarity

---

## [v1.0] — 2026-03-30

### Initial Release

- Flask web portal wrapping Cisco CUCM AXL automation script
- Secure login with bcrypt password hashing and Flask-Login session management
- Manual provisioning form with 8 input fields
- 5-step automation pipeline via Cisco AXL SOAP API (Zeep):
  - Step 1: Resolve Mirror DN to device names and copy configuration
  - Step 2: Add or update Directory Number (DN)
  - Step 3: Add or update physical SEP phone
  - Step 4: Add or update Jabber soft client (CSF/TCT/BOT/TAB)
  - Step 5: Update end user, associate device, set primary extension
- Real-time progress panel with 5-step indicator and live log output
- CSV batch upload for provisioning multiple users at once
- CSV template download
- Job history page with status badges, duration, and expandable logs
- SQLite database with SQLAlchemy ORM
- Gunicorn production server on Linux
- Background threading for async job execution
