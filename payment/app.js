// app.js – Ask Botz Payment Gateway

// ── Config (edit these) ───────────────────────────────────────
const CONFIG = {
  upiId:       "Rajeshtg18x@ibl",
  upiName:     "Ask Botz",
  botUsername: "AskSubscriptionBot",
  support:     "Master_xkid",
};

// ── Read URL params ───────────────────────────────────────────
function getParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    order:    p.get("order")    || "ASK_0000000000",
    amount:   p.get("amount")  || "0",
    name:     p.get("name")    || "Subscription",
    duration: p.get("duration")|| "30",
    upi:      p.get("upi")     || CONFIG.upiId,
    upiname:  p.get("upiname") || CONFIG.upiName,
  };
}

// ── Build UPI deep links ──────────────────────────────────────
function makeLinks(params) {
  const { order, amount, upi, upiname } = params;
  const base = `pa=${upi}&pn=${encodeURIComponent(upiname)}&am=${amount}&tn=${encodeURIComponent(order)}&cu=INR`;
  return {
    gpay:    `gpay://upi/pay?${base}`,
    phonepe: `phonepe://pay?${base}`,
    paytm:   `paytmmp://pay?${base}`,
    amazon:  `amazonpay://pay?${base}`,
    bhim:    `upi://pay?${base}`,
    upi:     `upi://pay?${base}`,
  };
}

// ── Open UPI App ──────────────────────────────────────────────
let links = {};

function openApp(app) {
  const url = links[app];
  if (!url) return;

  // Try to open the app
  const start = Date.now();
  window.location.href = url;

  // If app not installed, show fallback after 2s
  setTimeout(() => {
    if (Date.now() - start < 2500) {
      showFallback(app);
    }
  }, 2000);
}

function showFallback(app) {
  const names = {
    gpay: "Google Pay", phonepe: "PhonePe",
    paytm: "Paytm", amazon: "Amazon Pay",
    bhim: "BHIM UPI", upi: "UPI App"
  };
  showToast(`${names[app] || "App"} not found. Try another app or use Manual UPI below.`, 3500);
}

// ── Populate page ─────────────────────────────────────────────
function init() {
  const params = getParams();
  links = makeLinks(params);

  // Order details
  document.getElementById("plan-name").textContent = decodeURIComponent(params.name);
  document.getElementById("duration").textContent  = params.duration + " days";
  document.getElementById("order-id").textContent  = params.order;
  document.getElementById("amount").textContent    = "₹" + params.amount;

  // Manual UPI
  document.getElementById("upi-id-display").textContent = params.upi;
  document.getElementById("pay-note").textContent        = params.order;

  // Telegram bot link
  const tgLink = `https://t.me/${CONFIG.botUsername}`;
  document.getElementById("tg-link").href = tgLink;

  // Support link
  const supportEl = document.getElementById("support-link");
  supportEl.href        = `https://t.me/${CONFIG.support}`;
  supportEl.textContent = `@${CONFIG.support}`;

  // Wire up UPI buttons
  const appMap = {
    "btn-gpay":    "gpay",
    "btn-phonepe": "phonepe",
    "btn-paytm":   "paytm",
    "btn-amazon":  "amazon",
    "btn-bhim":    "bhim",
    "btn-upi":     "upi",
  };
  Object.entries(appMap).forEach(([id, app]) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        openApp(app);
      });
    }
  });

  // Animate in
  document.querySelectorAll(".card").forEach((c, i) => {
    c.style.opacity = "0";
    c.style.transform = "translateY(20px)";
    c.style.transition = `opacity 0.4s ease ${i * 0.08}s, transform 0.4s ease ${i * 0.08}s`;
    requestAnimationFrame(() => {
      setTimeout(() => {
        c.style.opacity = "1";
        c.style.transform = "translateY(0)";
      }, 50);
    });
  });
}

// ── Copy to clipboard ─────────────────────────────────────────
function copyText(id, btn) {
  const text = document.getElementById(id).textContent.trim();
  const original = btn.textContent;

  const doSuccess = () => {
    btn.textContent = "Copied!";
    btn.classList.add("copied");
    showToast("Copied to clipboard!");
    setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove("copied");
    }, 2000);
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(doSuccess).catch(() => fallbackCopy(text, btn, original, doSuccess));
  } else {
    fallbackCopy(text, btn, original, doSuccess);
  }
}

function fallbackCopy(text, btn, original, doSuccess) {
  const el = document.createElement("textarea");
  el.value = text;
  el.style.position = "fixed";
  el.style.opacity  = "0";
  document.body.appendChild(el);
  el.focus();
  el.select();
  try {
    document.execCommand("copy");
    doSuccess();
  } catch (e) {
    showToast("Copy failed — please copy manually.");
  }
  document.body.removeChild(el);
}

// ── Toast notification ────────────────────────────────────────
let toastTimer = null;

function showToast(msg, duration = 2200) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.add("show");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), duration);
}

// ── Run ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", init);

