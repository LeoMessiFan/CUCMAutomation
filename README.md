# UC Automation Portal

A secure internal web portal for provisioning Cisco CUCM phone and Jabber configurations via the AXL API. Replaces manual Jupyter notebook execution with a browser-based interface featuring real-time progress tracking, job history, and CSV batch upload.

---

## Features

- **Secure Login** — bcrypt-hashed passwords, session-based auth
- **Manual Provisioning Form** — 8-field form for single user provisioning
- **CSV Batch Upload** — provision multiple users from a single CSV file
- **CSV Template Download** — pre-formatted template with correct column headers
- **Real-Time Progress** — 5-step progress bar with live log output
- **Job History** — full audit log of all past jobs with status, duration, and expandable logs
- **Background Jobs** — automation runs async, UI stays responsive

## Automation Pipeline

For each user, the portal executes these steps against Cisco CUCM via AXL:

| Step | Action |
|------|--------|
| 1 | Resolve Mirror DN → SEP phone & CSF Jabber device names, get partition, line CSS, VM profile, phone config |
| 2 | Add or update the new DN (Directory Number) |
| 3 | Add or update the physical SEP phone |
| 4 | Add or update the Jabber soft client (CSF/TCT/BOT/TAB) |
| 5 | Update end user: associate device, enable IM&P, set primary extension |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.8+ / Flask |
| Database | SQLite via SQLAlchemy |
| Web Server | Gunicorn (production) |
| AXL Client | Python Zeep (SOAP) |
| Frontend | HTML + Tailwind CSS + Vanilla JS |
| Auth | Flask-Login + bcrypt |

---

## Prerequisites

- Linux server (Ubuntu 20.04+ or CentOS 8+)
- Python 3.8 or higher
- Network access to Cisco CUCM on port 8443
- AXL API enabled on CUCM and an AXL user account
- `axlsqltoolkit` schema files (`AXLAPI.wsdl`, `AXLEnums.xsd`, `AXLSoap.xsd`)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_ORG/uc-automation-portal.git
cd uc-automation-portal
```

### 2. Copy WSDL Schema Files

Copy the three required schema files from your `axlsqltoolkit` into the `schema/` directory:

```bash
cp /path/to/axlsqltoolkit/schema/current/AXLAPI.wsdl  schema/
cp /path/to/axlsqltoolkit/schema/current/AXLEnums.xsd  schema/
cp /path/to/axlsqltoolkit/schema/current/AXLSoap.xsd   schema/
```

> These files are not included in the repository. They come with the Cisco AXL SDK (DevNet download).

### 3. Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Fill in your values:

```env
FLASK_SECRET_KEY=your_long_random_secret_key_here
AXL_USERNAME=axl-test
AXL_PASSWORD=your_axl_password
AXL_FQDN=cucm-hostname.yourdomain.com
WSDL_PATH=schema/AXLAPI.wsdl
FLASK_ENV=production
HOST=0.0.0.0
PORT=5000
```

> **Never commit `.env` to Git.** It is listed in `.gitignore`.

### 5. Initialise the Database

```bash
flask init-db
```

### 6. Create Admin User

```bash
flask create-admin
```

You will be prompted for a username and password.

### 7. Start the Portal

```bash
chmod +x run.sh
./run.sh
```

The portal will be available at `http://<server-ip>:5000`.

---

## Running as a systemd Service (Recommended for Production)

Create a service file:

```bash
sudo nano /etc/systemd/system/uc-portal.service
```

Content:

```ini
[Unit]
Description=UC Automation Portal
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/uc-automation-portal
ExecStart=/opt/uc-automation-portal/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 app:app
EnvironmentFile=/opt/uc-automation-portal/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable uc-portal
sudo systemctl start uc-portal
sudo systemctl status uc-portal
```

---

## CSV Template

Download the template from the portal (`/api/download-template`) or create a CSV with these exact column headers:

| Column | Example | Notes |
|--------|---------|-------|
| `mirror_dn` | `19786007919` | Existing DN to mirror config from |
| `user_id` | `jsmith` | CUCM end user ID |
| `full_name` | `John Smith` | Used for DN description and display |
| `vm_enable` | `yes` | `yes` or `no` |
| `new_dn` | `60055` | New extension to provision |
| `phone_mac` | `AABBCC112233` | 12 hex characters, no separators |
| `phone_model` | `8851` | Cisco phone model number |
| `jabber_model` | `CSF` | `CSF`, `TCT`, `BOT`, or `TAB` |

---

## Project Structure

```
uc-automation-portal/
├── app.py                  # Flask entry point + CLI commands
├── config.py               # Configuration (reads from .env)
├── requirements.txt        # Python dependencies
├── run.sh                  # Production startup script
├── .env.example            # Environment variable template
├── .gitignore
├── README.md
│
├── database/
│   ├── models.py           # SQLAlchemy models: User, JobHistory
│   └── portal.db           # Auto-generated SQLite database (not in Git)
│
├── core/
│   ├── axl_client.py       # Zeep SOAP client initialisation
│   ├── automation.py       # All 9 AXL automation functions
│   └── runner.py           # Job orchestrator (background thread)
│
├── routes/
│   ├── auth.py             # /login, /logout
│   ├── dashboard.py        # /dashboard, /history
│   └── api.py              # /api/run-job, /api/job-status, /api/upload-csv, /api/download-template
│
├── schema/                 # WSDL files (not in Git — copy manually)
│   ├── AXLAPI.wsdl
│   ├── AXLEnums.xsd
│   └── AXLSoap.xsd
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── history.html
│
├── static/
│   ├── css/style.css
│   └── js/portal.js
│
└── uploads/                # Temporary CSV uploads (not in Git)
```

---

## Security Notes

- All passwords are stored as bcrypt hashes (cost factor 12)
- AXL credentials are loaded from environment variables only — never hardcoded
- `.env`, `portal.db`, and `uploads/` are excluded from Git
- All routes require authentication via `@login_required`
- CSV uploads are validated (extension, size, column headers) before processing
- AXL communication is server-side only — credentials never reach the browser
- SSL verification is disabled for internal CUCM (`session.verify = False`). To enable, set `session.verify = '/path/to/cert.pem'` in `core/axl_client.py`

---

## Troubleshooting

**`RuntimeError: AXL_FQDN is not configured`**
→ Check your `.env` file. Make sure `AXL_FQDN` is set and the file is in the project root.

**`FileNotFoundError: AXLAPI.wsdl not found`**
→ Copy the WSDL files into `schema/` as described in Step 2.

**`zeep.exceptions.Fault: The specified Line was not found`**
→ The Mirror DN entered does not exist in CUCM, or it is not in the `INTERNAL-PT` partition.

**`zeep.exceptions.Fault: ENUM for Cisco XXXX not found in TypeProduct`**
→ The phone model entered is not a valid product in this version of CUCM. Check the exact model string.

**Port 5000 already in use**
→ Change the `PORT` value in `.env` and restart.

---

## License

Internal use only. Not for distribution.
