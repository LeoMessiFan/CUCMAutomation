/**
 * portal.js
 * Frontend logic for UC Automation Portal dashboard.
 */

// ── DOM refs ─────────────────────────────────────────────────────────────────
const provisionForm  = document.getElementById('provisionForm');
const submitBtn      = document.getElementById('submitBtn');
const submitText     = document.getElementById('submitText');
const formErrors     = document.getElementById('formErrors');
const progressPanel  = document.getElementById('progressPanel');
const statusBadge    = document.getElementById('statusBadge');
const logOutput      = document.getElementById('logOutput');

const dropZone       = document.getElementById('dropZone');
const csvFile        = document.getElementById('csvFile');
const csvFileName    = document.getElementById('csvFileName');
const csvFileNameText = document.getElementById('csvFileNameText');
const clearCsvBtn    = document.getElementById('clearCsvBtn');
const csvUploadBtn   = document.getElementById('csvUploadBtn');
const csvErrors      = document.getElementById('csvErrors');
const csvSuccess     = document.getElementById('csvSuccess');

let pollInterval = null;

// ── Voicemail toggle ─────────────────────────────────────────────────────────
document.querySelectorAll('.toggle-option input[type="radio"]').forEach(radio => {
  radio.addEventListener('change', () => {
    document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
    if (radio.checked) radio.nextElementSibling.classList.add('active');
  });
});

// ── MAC address auto-uppercase ───────────────────────────────────────────────
const macInput = document.getElementById('phone_mac');
if (macInput) {
  macInput.addEventListener('input', () => {
    macInput.value = macInput.value.replace(/[^0-9a-fA-F]/g, '').toUpperCase();
  });
}

// ── Manual Form Submit ───────────────────────────────────────────────────────
if (provisionForm) {
  provisionForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    const data = getFormData();
    setSubmitting(true);

    try {
      const res = await fetch('/api/run-job', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(data),
      });
      const json = await res.json();

      if (!res.ok || !json.success) {
        showErrors(json.errors || ['An unknown error occurred.']);
        setSubmitting(false);
        return;
      }

      showProgress();
      startPolling(json.job_id);

    } catch (err) {
      showErrors(['Network error. Please try again.']);
      setSubmitting(false);
    }
  });
}

// ── Form Data Helper ─────────────────────────────────────────────────────────
function getFormData() {
  const fd = new FormData(provisionForm);
  const data = {};
  for (const [k, v] of fd.entries()) data[k] = v;
  return data;
}

// ── Submit State ─────────────────────────────────────────────────────────────
function setSubmitting(loading) {
  submitBtn.disabled = loading;
  submitText.textContent = loading ? 'Running...' : 'Run Provisioning';
}

// ── Error Display ─────────────────────────────────────────────────────────────
function clearErrors() {
  formErrors.classList.add('hidden');
  formErrors.innerHTML = '';
}

function showErrors(errors) {
  formErrors.innerHTML = errors.map(e => `<div>⚠ ${e}</div>`).join('');
  formErrors.classList.remove('hidden');
}

// ── Progress Panel ────────────────────────────────────────────────────────────
function showProgress() {
  progressPanel.classList.remove('hidden');
  setStatusBadge('running');
  logOutput.textContent = '';
  for (let i = 1; i <= 5; i++) resetStep(i);
  progressPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setStatusBadge(status) {
  statusBadge.className = `status-badge status-${status}`;
  statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

function resetStep(n) {
  const row  = document.getElementById(`step-${n}`);
  const icon = document.getElementById(`step-icon-${n}`);
  if (!row || !icon) return;
  row.classList.remove('active', 'done', 'failed');
  icon.classList.remove('active', 'done', 'failed');
  icon.querySelector('.step-num').classList.remove('hidden');
  icon.querySelector('.step-check').classList.add('hidden');
}

function activateStep(n) {
  for (let i = 1; i < n; i++) markStepDone(i);
  const row  = document.getElementById(`step-${n}`);
  const icon = document.getElementById(`step-icon-${n}`);
  if (!row || !icon) return;
  row.classList.add('active');
  icon.classList.add('active');
}

function markStepDone(n) {
  const row  = document.getElementById(`step-${n}`);
  const icon = document.getElementById(`step-icon-${n}`);
  if (!row || !icon) return;
  row.classList.remove('active');
  row.classList.add('done');
  icon.classList.remove('active');
  icon.classList.add('done');
  icon.querySelector('.step-num').classList.add('hidden');
  icon.querySelector('.step-check').classList.remove('hidden');
}

function markStepFailed(n) {
  const row  = document.getElementById(`step-${n}`);
  const icon = document.getElementById(`step-icon-${n}`);
  if (!row || !icon) return;
  row.classList.add('failed');
  icon.classList.add('failed');
}

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling(jobId) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => pollJob(jobId), 2000);
  pollJob(jobId); // immediate first call
}

async function pollJob(jobId) {
  try {
    const res  = await fetch(`/api/job-status/${jobId}`);
    const job  = await res.json();

    // Update log
    logOutput.textContent = job.log_output || '';
    logOutput.scrollTop   = logOutput.scrollHeight;

    // Update steps
    if (job.current_step > 0) activateStep(job.current_step);

    // Terminal states
    if (job.status === 'success') {
      clearInterval(pollInterval);
      setStatusBadge('success');
      setSubmitting(false);
      for (let i = 1; i <= 5; i++) markStepDone(i);

    } else if (job.status === 'failed') {
      clearInterval(pollInterval);
      setStatusBadge('failed');
      setSubmitting(false);
      if (job.current_step > 0) markStepFailed(job.current_step);
    }

  } catch (err) {
    console.error('Polling error:', err);
  }
}

// ── CSV Drop Zone ─────────────────────────────────────────────────────────────
if (dropZone) {
  dropZone.addEventListener('click', () => csvFile.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-brand-500');
  });
  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-brand-500');
  });
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-brand-500');
    const file = e.dataTransfer.files[0];
    if (file) setCSVFile(file);
  });

  csvFile.addEventListener('change', () => {
    if (csvFile.files[0]) setCSVFile(csvFile.files[0]);
  });

  clearCsvBtn.addEventListener('click', () => {
    csvFile.value = '';
    csvFileName.classList.add('hidden');
    csvUploadBtn.disabled = true;
    csvErrors.classList.add('hidden');
    csvSuccess.classList.add('hidden');
  });
}

function setCSVFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    csvErrors.textContent = '⚠ File must be a .csv file.';
    csvErrors.classList.remove('hidden');
    return;
  }
  csvErrors.classList.add('hidden');
  csvFileNameText.textContent = file.name;
  csvFileName.classList.remove('hidden');
  csvUploadBtn.disabled = false;

  // Put file back into input for FormData
  const dt = new DataTransfer();
  dt.items.add(file);
  csvFile.files = dt.files;
}

// ── CSV Upload ────────────────────────────────────────────────────────────────
if (csvUploadBtn) {
  csvUploadBtn.addEventListener('click', async () => {
    if (!csvFile.files[0]) return;
    csvErrors.classList.add('hidden');
    csvSuccess.classList.add('hidden');
    csvUploadBtn.disabled = true;
    csvUploadBtn.textContent = 'Uploading...';

    const fd = new FormData();
    fd.append('csv_file', csvFile.files[0]);

    try {
      const res  = await fetch('/api/upload-csv', { method: 'POST', body: fd });
      const json = await res.json();

      if (!res.ok || !json.success) {
        csvErrors.innerHTML = (json.errors || ['Upload failed.']).map(e => `<div>⚠ ${e}</div>`).join('');
        csvErrors.classList.remove('hidden');
      } else {
        let msg = `✓ ${json.jobs_queued} job(s) queued successfully.`;
        if (json.row_errors && json.row_errors.length > 0) {
          msg += ` ${json.row_errors.length} row(s) skipped due to errors.`;
        }
        csvSuccess.textContent = msg;
        csvSuccess.classList.remove('hidden');

        // Show progress for first job if any
        if (json.jobs && json.jobs.length > 0) {
          showProgress();
          startPolling(json.jobs[0].job_id);
        }
      }

    } catch (err) {
      csvErrors.textContent = '⚠ Network error. Please try again.';
      csvErrors.classList.remove('hidden');
    }

    csvUploadBtn.disabled = false;
    csvUploadBtn.innerHTML = `<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
      Upload & Run Batch`;
  });
}
