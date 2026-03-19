const phraseEl = document.getElementById("phrase");

const EFFECT_DURATIONS = {
  fade: 1200,
  melt: 1400,
  glitch: 900,
};

const DEFAULTS = {
  hold_ms: 7000,
  pause_ms: 2500,
  color: "#e6e6e6",
  effect: "fade",
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchPayload() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch("/api/next", {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      return null;
    }
    return await res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

function clearPhraseClasses() {
  phraseEl.classList.remove("is-visible", "effect-fade", "effect-melt", "effect-glitch");
}

async function runLoop() {
  while (true) {
    const payload = await fetchPayload();
    if (!payload || !payload.text) {
      clearPhraseClasses();
      phraseEl.textContent = "";
      phraseEl.dataset.text = "";
      await sleep(2000);
      continue;
    }

    const effect = payload.effect || DEFAULTS.effect;
    const holdMs = payload.hold_ms || DEFAULTS.hold_ms;
    const pauseMs = payload.pause_ms || DEFAULTS.pause_ms;
    const color = payload.color || DEFAULTS.color;

    clearPhraseClasses();
    phraseEl.style.color = color;
    phraseEl.textContent = payload.text;
    phraseEl.dataset.text = payload.text;

    requestAnimationFrame(() => {
      phraseEl.classList.add("is-visible");
    });

    await sleep(holdMs);
    phraseEl.classList.add(`effect-${effect}`);

    const exitMs = EFFECT_DURATIONS[effect] || EFFECT_DURATIONS.fade;
    await sleep(exitMs);

    clearPhraseClasses();
    phraseEl.textContent = "";
    phraseEl.dataset.text = "";

    await sleep(pauseMs);
  }
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // no-op
    });
  });
}

runLoop();
