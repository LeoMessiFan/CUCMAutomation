module.exports = {
  apps: [{
    name: 'uc-portal',
    script: '/home/yhan/monitoring2026/uc-portal/venv/bin/gunicorn',
    args: '-w 2 -b 0.0.0.0:5000 --timeout 120 app:app',
    cwd: '/home/yhan/monitoring2026/uc-portal',
    env: {
      TZ: 'America/New_York',
      FLASK_ENV: 'production'
    },
    autorestart: true,
    watch: false,
    max_memory_restart: '512M',
  }]
}
