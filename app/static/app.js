const tickerPrice = document.getElementById('tickerPrice');
const tickerMeta = document.getElementById('tickerMeta');
const tickerDot = document.getElementById('tickerDot');

const form = document.getElementById('alertForm');
const createBtn = document.getElementById('createBtn');
const formStatus = document.getElementById('formStatus');
const alertsList = document.getElementById('alertsList');
const tabs = document.getElementById('tabs');

let currentStatus = 'active';
let lastPrice = null;

// ── Price ticker ─────────────────────────────────────────────────
async function refreshPrice() {
  try {
    const res = await fetch('/api/price');
    const data = await res.json();
    if (data.error) {
      tickerMeta.innerText = 'price unavailable';
      return;
    }
    const price = data.price;
    tickerPrice.innerText = `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    tickerDot.classList.add('live');

    if (lastPrice !== null) {
      tickerPrice.classList.remove('flash-up', 'flash-down');
      if (price > lastPrice) tickerPrice.classList.add('flash-up');
      else if (price < lastPrice) tickerPrice.classList.add('flash-down');
      setTimeout(() => tickerPrice.classList.remove('flash-up', 'flash-down'), 1500);
    }
    lastPrice = price;

    const computedAt = data.computed_at ? new Date(data.computed_at) : null;
    const staleTag = data.is_stale ? ' · stale' : '';
    tickerMeta.innerText = computedAt
      ? `updated ${computedAt.toLocaleTimeString()}${staleTag}`
      : `live${staleTag}`;
  } catch (e) {
    tickerMeta.innerText = 'price unavailable';
  }
}

// ── Alerts list ──────────────────────────────────────────────────
function fmtMoney(n) {
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function renderAlert(alert) {
  const card = document.createElement('div');
  card.className = 'alert-card';

  const dirClass = alert.condition === 'above' ? 'dir-up' : 'dir-down';
  const dirWord = alert.condition === 'above' ? 'above' : 'below';
  const dirArrow = alert.condition === 'above' ? '▲' : '▼';

  const info = document.createElement('div');
  info.className = 'alert-info';

  const conditionLine = document.createElement('div');
  conditionLine.className = 'alert-condition';
  conditionLine.innerHTML = `<span class="${dirClass}">${dirArrow} ${dirWord}</span> ${fmtMoney(alert.target_price)}`;

  const metaLine = document.createElement('div');
  metaLine.className = 'alert-meta';
  const bits = [alert.email];
  if (alert.note) bits.push(alert.note);
  if (alert.status === 'triggered' && alert.triggered_at) {
    bits.push(`fired ${fmtDate(alert.triggered_at)} @ ${fmtMoney(alert.triggered_price)}`);
  } else {
    bits.push(`created ${fmtDate(alert.created_at)}`);
  }
  metaLine.innerText = bits.filter(Boolean).join(' · ');

  info.appendChild(conditionLine);
  info.appendChild(metaLine);

  const right = document.createElement('div');
  right.style.display = 'flex';
  right.style.alignItems = 'center';
  right.style.gap = '10px';

  const statusTag = document.createElement('span');
  statusTag.className = `alert-status ${alert.status}`;
  statusTag.innerText = alert.status;
  right.appendChild(statusTag);

  const delBtn = document.createElement('button');
  delBtn.className = 'delete-btn';
  delBtn.innerHTML = '✕';
  delBtn.title = 'Delete alert';
  delBtn.addEventListener('click', () => deleteAlert(alert.id));
  right.appendChild(delBtn);

  card.appendChild(info);
  card.appendChild(right);
  return card;
}

async function loadAlerts() {
  alertsList.innerHTML = '<p class="empty">Loading…</p>';
  try {
    const res = await fetch(`/api/alerts?status=${currentStatus}`);
    const data = await res.json();
    if (data.error) {
      alertsList.innerHTML = `<p class="empty">Couldn't load alerts: ${data.error}</p>`;
      return;
    }
    if (!data.length) {
      alertsList.innerHTML = `<p class="empty">No ${currentStatus === 'all' ? '' : currentStatus + ' '}alerts yet.</p>`;
      return;
    }
    alertsList.innerHTML = '';
    data.forEach((alert) => alertsList.appendChild(renderAlert(alert)));
  } catch (e) {
    alertsList.innerHTML = '<p class="empty">Connection error — is the server running?</p>';
  }
}

async function deleteAlert(id) {
  try {
    await fetch(`/api/alerts/${id}`, { method: 'DELETE' });
    loadAlerts();
  } catch (e) {
    // no-op, list stays as-is; user can retry
  }
}

tabs.addEventListener('click', (e) => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  tabs.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
  btn.classList.add('active');
  currentStatus = btn.dataset.status;
  loadAlerts();
});

// ── Create alert form ────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  createBtn.disabled = true;
  formStatus.className = 'form-status';
  formStatus.innerText = '';

  const payload = {
    condition: document.getElementById('condition').value,
    target_price: document.getElementById('targetPrice').value,
    email: document.getElementById('email').value,
    note: document.getElementById('note').value,
  };

  try {
    const res = await fetch('/api/alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      formStatus.className = 'form-status err';
      formStatus.innerText = data.error || 'Something went wrong.';
    } else {
      formStatus.className = 'form-status ok';
      formStatus.innerText = `Alert created — you'll be emailed when it fires.`;
      form.reset();
      if (currentStatus === 'active' || currentStatus === 'all') loadAlerts();
    }
  } catch (err) {
    formStatus.className = 'form-status err';
    formStatus.innerText = 'Connection error — is the server running?';
  } finally {
    createBtn.disabled = false;
  }
});

refreshPrice();
setInterval(refreshPrice, 45000);
loadAlerts();
