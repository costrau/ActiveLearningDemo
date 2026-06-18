// === CONFIGURABLE BACKEND HOST ===
// When deploying, the hosting page can set `window.__BACKEND_HOST__` to override this.
// Default is localhost for local development.
// Default to same-origin (relative paths). Hosts can override via `window.__BACKEND_HOST__`.
const BACKEND_HOST = window.__BACKEND_HOST__
  ? new URL(window.__BACKEND_HOST__).origin
  : window.location.origin;

// Check if website uses subpath (e.g. example.com/app/) for image URLs
// Only add trailing slash if pathname is not empty and not just "/"
const SUBPATH = window.location.pathname && window.location.pathname !== "/"
  ? window.location.pathname.replace(/\/?$/, '/')
  : '';

const SELECT_REQUIRED = 5;
const MAX_SELECTION = 5;

const carsEl = document.getElementById('cars');
const intro = document.getElementById('intro');
const runBtn = document.getElementById('runBtn');
const statusEl = document.getElementById('status');
const gifArea = document.getElementById('gifArea');
const alArea = document.getElementById('alArea');
const leaderboardArea = document.getElementById('leaderboardArea');
// Enable leaderboard if URL contains ?leaderboard=on (accepts 'on', '1', 'true')
let lastLeaderboardScore = null;
const _lbq = (new URLSearchParams(window.location.search).get('leaderboard') || '').toLowerCase();
let leaderboardEnabled = ['on', '1', 'true'].includes(_lbq);
const gifView = document.getElementById('gifView');
const resultView = document.getElementById('resultView');
const intermediateResult = document.getElementById('intermediateResult');
const plotIntermediateUser = document.getElementById('plotIntermediateUser');
const intermediateUserControls = document.getElementById('intermediateUserControls');
const intermediateUserStepInfo = document.getElementById('intermediateUserStepInfo');
const intermediateSelectInfo = document.getElementById('intermediateSelectInfo');
const intermediateAlArea = document.getElementById('intermediateAlArea');
const continueToResult = document.getElementById('continueToResult');
const continueToAL = document.getElementById('continueToAL');
const controls = document.getElementById('controls');

let cars = [];
let selected = new Set();

function renderCars() {
  carsEl.innerHTML = '';
  cars.forEach(c => {
    const d = document.createElement('div');
    d.className = 'card' + (selected.has(c.id) ? ' selected' : '');
    d.style.width = '100px';

    const title = document.createElement('div');
    title.innerHTML = `<b></b>`;
    title.firstChild.textContent = c.name;

    const weight = document.createElement('div');
    weight.textContent = `${c.gewicht} kg`;

    const img = document.createElement('img');
    img.src = SUBPATH + c.icon_url;
    img.style.width = '60px';
    img.alt = c.name + ' icon';

    const speed = document.createElement('div');
    speed.innerHTML = `<b></b>`;
    speed.firstChild.textContent = `${c.geschwindigkeit} km/h`;

    d.appendChild(title);
    d.appendChild(weight);
    d.appendChild(img);
    d.appendChild(speed);

    d.onclick = () => {
      if (selected.has(c.id)) {
        selected.delete(c.id);
      } else {
        if (selected.size < MAX_SELECTION) selected.add(c.id);
      }
      renderCars();
    };
    carsEl.appendChild(d);
  });
}

async function loadCars() {
  try {
    const res = await fetch(`${BACKEND_HOST}/api/cars`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    cars = data.cars || [];
    renderCars();
  } catch (e) {
    console.error('Failed to load cars', e);
    statusEl.textContent = 'Fehler beim Laden der Autos.';
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function showGifs(gifUrls) {
  gifArea.innerHTML = '';
  for (const g of gifUrls) {
    const img = document.createElement('img');
    img.src = SUBPATH + g;
    img.alt = 'Experiment GIF';
    // preserve aspect ratio and limit height; CSS handles object-fit
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    img.style.maxHeight = '60vh';
    img.style.objectFit = 'contain';
    // caption: try to derive car info from gif filename and cars[]
    let captionHTML = '';
    let gifName = '';
    try {
      gifName = g.split('/').pop();
      const baseWithVel = gifName.replace(/\.gif$/i, '');
      const idx = baseWithVel.lastIndexOf('_');
      if (idx > 0) {
        const base = baseWithVel.substring(0, idx);
        const vel = baseWithVel.substring(idx + 1);
        const match = cars.find(c => {
          const p = (c.path || '').split('/').pop();
          const b = p ? p.replace(/\.[^.]+$/, '') : '';
          return b === base && String(c.geschwindigkeit) === String(vel);
        });
        if (match) captionHTML = `<b>${escapeHtml(match.name)}</b> — ${escapeHtml(match.geschwindigkeit)} km/h — ${escapeHtml(match.gewicht)} kg`;
      }
    } catch (e) { /* ignore parsing errors */ }
    if (!captionHTML) captionHTML = escapeHtml(gifName || '');

    const wrapper = document.createElement('div');
    wrapper.style.display = 'flex';
    wrapper.style.flexDirection = 'column';
    wrapper.style.alignItems = 'center';
    wrapper.appendChild(img);
    const cap = document.createElement('div');
    cap.className = 'gif-caption';
    cap.innerHTML = captionHTML;
    wrapper.appendChild(cap);
    gifArea.appendChild(wrapper);
    await sleep(2500);
    gifArea.removeChild(wrapper);
  }
}

function contourFromResponse(resp) {
  const V = resp.V; // 2d
  const M = resp.M; // 2d
  const Z = resp.y_pred; // 2d
  const x = V[0];
  const y = M.map(r => r[0]);
  return { x, y, z: Z };
}


// Helper to show only one main view
function showOnlyView(view) {
  [controls, gifView, intermediateResult, resultView].forEach(v => {
    if (v) v.style.display = 'none';
  });
  if (view) view.style.display = 'block';
  // Show car selection only with controls
  const carsEl = document.getElementById('cars');
  if (view === controls) {
    carsEl.style.display = '';
  } else {
    carsEl.style.display = 'none';
  }
  // After showing a view, schedule Plotly resize for any plots inside it
  if (view) {
    window.requestAnimationFrame(() => {
      try {
        const plots = view.querySelectorAll('.plot');
        plots.forEach(p => { try { Plotly.Plots.resize(p); } catch (e) { /* ignore */ } });
      } catch (e) { /* ignore if view has no querySelectorAll */ }
    });
  }
}

async function runExperiments({ intermediateOnly = false } = {}) {
  if (selected.size < SELECT_REQUIRED) { statusEl.textContent = `Bitte ${SELECT_REQUIRED} Autos auswählen.`; return }
  intro.style.display = 'none';
  statusEl.textContent = 'Starte Berechnung...';
  runBtn.disabled = true;
  // start compute job (returns job id and gifs immediately)
  const res = await fetch(`${BACKEND_HOST}/api/compute_start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selected: Array.from(selected) }) });
  let info;
  try {
    if (!res.ok) throw new Error(await res.text());
    info = await res.json();
  } catch (e) {
    statusEl.textContent = 'Fehler beim Starten der Berechnung.';
    console.error(e);
    runBtn.disabled = false;
    return;
  }

  // switch to gif view and show gifs only if not retraining in intermediate view
  const jobId = info.job_id;
  const gifs = info.gifs || [];

  // start polling in background (no overlapping requests)
  let result = null;
  const pollInterval = 800; // ms
  let pollCancelled = false;
  async function pollLoop() {
    while (!pollCancelled) {
      try {
        const r = await fetch(`${BACKEND_HOST}/api/compute_result?job_id=${jobId}`);
        if (r.ok) {
          const d = await r.json();
          if (d.ready) { result = d; break; }
        } else {
          console.warn('compute_result returned', r.status);
        }
      } catch (e) { console.error(e); }
      await sleep(pollInterval);
    }
  }

  // Show gifs for initial run (when not in intermediate view),
  // and also for the very first intermediate view (when retrainCount === 0)
  const pollPromise = pollLoop();
  if (!intermediateOnly || (intermediateOnly && retrainCount === 0)) {
    showOnlyView(gifView);
    await showGifs(gifs);
    shown = true;
  } else {
    shown = true;
  }

  // wait for poll to finish
  await pollPromise;
  pollCancelled = true;

  if (result) {
    if (intermediateOnly !== false) {
      showIntermediateResult(result);
    } else {
      showResult(result);
    }
  } else if (!intermediateOnly) {
    gifArea.textContent = 'Berechnung läuft, bitte warten...';
  }
}

function renderUserStepGraph(step, data, div, colorScale = 'Jet', titlePrefix = 'Dein Modell', ystd = false) {
  let cont, title, zlabel;
  if (ystd) {
    cont = contourFromResponse({ V: data.V, M: data.M, y_pred: step.y_std });
    title = `${titlePrefix} — Modell-Unsicherheit`;
    zlabel = 'Unsicherheit';
  } else {
    cont = contourFromResponse({ V: data.V, M: data.M, y_pred: step.y_pred });
    title = `${titlePrefix} — Fehler: ${step.rmse.toFixed(2)}`;
    zlabel = 'Bremsweg (m)';
  }
  const traces = [{ z: cont.z, x: cont.x, y: cont.y, type: 'contour', colorscale: colorScale, 'name': '', colorbar: { title: { text: zlabel } } }];
  // mark training points: initial red, additional green
  const train_ids = step.train_ids || [];
  const initial = train_ids.slice(0, 5).map(id => cars.find(c => c.id === id)).filter(Boolean);
  const additional = train_ids.slice(5).map(id => cars.find(c => c.id === id)).filter(Boolean);
  if (initial.length) traces.push({ x: initial.map(p => p.geschwindigkeit), y: initial.map(p => p.gewicht), mode: 'markers', name: '', marker: { color: 'red', size: 10, symbol: 'x' }, showlegend: false });
  if (additional.length) traces.push({ x: additional.map(p => p.geschwindigkeit), y: additional.map(p => p.gewicht), mode: 'markers', name: '', marker: { color: 'green', size: 12, symbol: 'x' }, showlegend: false });
  Plotly.newPlot(div, traces, {
    title: { text: title },
    autosize: true,
    width: null,
    height: null,
    margin: { t: 40, l: 60, r: 20, b: 40 },
    colorbar: { title: { text: 'Bremsweg (m)' } },
    xaxis: { title: { text: 'Geschwindigkeit (km/h)' } },
    yaxis: { title: { text: 'Gewicht (kg)' } },
  }, { responsive: true });
}

// --- INTERMEDIATE RESULT LOGIC ---
let retrainCount = 0;
// persistent suggestions array used by the plot click handler across intermediate rerenders
let intermediateSuggested = [];
function showIntermediateResult(data) {
  showOnlyView(intermediateResult);
  // Only show trained model
  if (data.error) {
    intermediateUserStepInfo.textContent = `Fehler: ${data.error}`;
    runBtn.disabled = false; controls.style.display = ''; document.getElementById('cars').style.display = '';
    return;
  }
  // user_steps: array of {y_pred, y_std, rmse, train_ids}
  const user_steps = data.user_steps || [];
  let user_step_idx = user_steps.length - 1;

  function renderUserStep(i) {
    const step = user_steps[i];
    renderUserStepGraph(step, data, 'plotIntermediateUser', 'Jet', 'Dein Modell');

    const train_ids = step.train_ids || [];
    let trainedCars = train_ids.map(id => cars.find(c => c.id === id)).filter(Boolean);

    // build DOM safely for trained cars
    const container = document.createElement('div');
    const h4 = document.createElement('h4');
    h4.textContent = 'Bisher trainierte Autos';
    container.appendChild(h4);
    const wrap = document.createElement('div');
    wrap.style.display = 'flex'; wrap.style.flexWrap = 'wrap'; wrap.style.gap = '8px';
    trainedCars.forEach(car => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.width = '110px';
      const name = document.createElement('div'); name.innerHTML = '<b></b>'; name.firstChild.textContent = car.name;
      const w = document.createElement('div'); w.textContent = `${car.gewicht} kg`;
      const img = document.createElement('img'); img.src = SUBPATH + car.icon_url; img.style.width = '60px'; img.alt = car.name + ' icon';
      const sp = document.createElement('div'); sp.innerHTML = '<b></b>'; sp.firstChild.textContent = `${car.geschwindigkeit} km/h`;
      card.appendChild(name); card.appendChild(w); card.appendChild(img); card.appendChild(sp);
      wrap.appendChild(card);
    });
    container.appendChild(wrap);
    intermediateAlArea.innerHTML = '';
    intermediateAlArea.appendChild(container);
  }
  if (user_steps.length) renderUserStep(user_step_idx);

  // click handler for retrain (attach only once)
  const gd = document.getElementById('plotIntermediateUser');
  // reset shared suggestions for this intermediate session
  intermediateSuggested.length = 0;
  // ensure the click handler is attached after each intermediate render
  if (gd) {
    // clear the attached flag so we reattach the handler; this avoids the
    // handler becoming stale after Plotly redraws the plot
    gd._clickAttached = false;
  }
  if (gd && gd.on && !gd._clickAttached) {
    gd._clickAttached = true;
    gd.on('plotly_click', async function (evt) {
      if (retrainCount >= 2) return;
      try {
        const pts = evt.points && evt.points[0];
        if (!pts) return;
        const x = pts.x;
        const y = pts.y;
        // request nearest car, include already selected and suggested ids to prefer non-duplicates
        const already = Array.from(new Set([...Array.from(selected), ...intermediateSuggested.map(s => s.id)]));
        const resp = await fetch(`${BACKEND_HOST}/api/nearest`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ x, y, selected: already }) });
        if (!resp.ok) throw new Error(await resp.text());
        const d = await resp.json();
        // show suggested car below the list using safe DOM ops
        const c = d.car; c.gif = d.gif;
        // compute current trained ids from the latest user step (if any)
        const latestStep = (user_steps && user_steps.length) ? user_steps[user_steps.length - 1] : null;
        const trainedIds = (latestStep && latestStep.train_ids) ? latestStep.train_ids : [];
        // if the returned car is already selected, already suggested, or already part of the training set,
        // show a hint and do not add it again
        if (selected.has(c.id) || intermediateSuggested.some(s => s.id === c.id) || trainedIds.includes(c.id)) {
          intermediateSelectInfo.textContent = 'Dieses Auto wurde bereits vorgeschlagen oder ist bereits trainiert.';
          return;
        }
        // otherwise add to suggestions
        intermediateSuggested.push(c);
        // remove any previous suggestion container to avoid accumulating rows
        const prev = document.getElementById('intermediateSuggestions');
        if (prev) prev.remove();
        const suggestionContainer = document.createElement('div');
        suggestionContainer.id = 'intermediateSuggestions';
        suggestionContainer.style.marginTop = '12px';
        const h4 = document.createElement('h4'); h4.textContent = 'Zum Training vorgeschlagene Autos'; suggestionContainer.appendChild(h4);
        const flex = document.createElement('div'); flex.style.display = 'flex'; flex.style.flexWrap = 'wrap'; flex.style.gap = '8px';
        intermediateSuggested.forEach((car, idx) => {
          const card = document.createElement('div'); card.className = 'card'; card.style.width = '110px';
          const name = document.createElement('div'); name.innerHTML = '<b></b>'; name.firstChild.textContent = car.name;
          const w = document.createElement('div'); w.textContent = `${car.gewicht} kg`;
          const img = document.createElement('img'); img.src = SUBPATH + car.icon_url; img.style.width = '60px'; img.alt = car.name + ' icon';
          const sp = document.createElement('div'); sp.innerHTML = '<b></b>'; sp.firstChild.textContent = `${car.geschwindigkeit} km/h`;
          const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'acceptIntermediateCarBtn chs-btn'; btn.textContent = 'Wähle dieses Auto';
          btn.dataset.carIdx = idx;
          btn.onclick = async () => {
            const idx2 = parseInt(btn.dataset.carIdx);
            const car2 = intermediateSuggested[idx2];
            if (!selected.has(car2.id) && selected.size < MAX_SELECTION + 2 && retrainCount < 2) {
              retrainCount++;
              intermediateSelectInfo.textContent = `Auto ${retrainCount}/2 gewählt. Du kannst noch ${2 - retrainCount} Auto(s) wählen.`;
              selected.add(car2.id);
              // remove the accepted car from pending suggestions
              intermediateSuggested = intermediateSuggested.filter(s => s.id !== car2.id);
              renderCars();
              // show only the gif of the newly added car
              showOnlyView(gifView);
              // show gif with caption preserving aspect ratio
              const wrapper = document.createElement('div');
              wrapper.style.display = 'flex'; wrapper.style.flexDirection = 'column'; wrapper.style.alignItems = 'center';
              const gimg = document.createElement('img'); gimg.src = SUBPATH + car2.gif; gimg.alt = car2.name + ' GIF'; gimg.style.maxWidth = '100%'; gimg.style.height = 'auto'; gimg.style.maxHeight = '60vh'; gimg.style.objectFit = 'contain';
              const cap = document.createElement('div'); cap.className = 'gif-caption'; cap.innerHTML = `<b>${escapeHtml(car2.name)}</b> — ${escapeHtml(car2.geschwindigkeit)} km/h — ${escapeHtml(car2.gewicht)} kg`;
              wrapper.appendChild(gimg); wrapper.appendChild(cap);
              gifArea.appendChild(wrapper);
              await sleep(2500);
              gifArea.removeChild(wrapper);
              // after showing gif, request new computation and update intermediate view
              await runExperiments({ intermediateOnly: true });
            }
            if (retrainCount >= 2) {
              continueToResult.style.display = '';
            }
          };
          card.appendChild(name); card.appendChild(w); card.appendChild(img); card.appendChild(sp); card.appendChild(btn);
          flex.appendChild(card);
        });
        suggestionContainer.appendChild(flex);
        // insert suggestion container at top of intermediateAlArea
        intermediateAlArea.insertBefore(suggestionContainer, intermediateAlArea.firstChild);
      } catch (e) { console.error(e); statusEl.textContent = 'Fehler bei Vorschlag'; }
    });
  }

  // reset info and button
  if (retrainCount === 0) {
    intermediateSelectInfo.textContent = 'Klicke in den Graphen, um ein Auto zum Nachtrainieren auszuwählen. Noch 2 Autos übrig.';
  } else if (retrainCount === 1) {
    intermediateSelectInfo.textContent = `Du kannst insgesamt noch ein weiteres Auto auswählen.`;
  } else {
    intermediateSelectInfo.textContent = 'Du hast die maximale Anzahl an Autos zum Nachtrainieren ausgewählt. Klicke auf den Button, um zum Gesamtergebnis zu gelangen.';
  }

  continueToResult.style.display = retrainCount >= 2 ? '' : 'none';
  continueToResult.onclick = () => {
    // Hide intermediate view and clear its content
    showOnlyView(null);
    plotIntermediateUser.innerHTML = '';
    intermediateUserStepInfo.textContent = '';
    intermediateSelectInfo.textContent = '';
    intermediateAlArea.innerHTML = '';
    // Show the final result view
    showResult(data);
  };
}


function showResult(data) {
  // hide gif view, show result view
  gifView.style.display = 'none';
  resultView.style.display = 'block';
  if (data.error) {
    statusEl.textContent = `Fehler: ${data.error}`;
    runBtn.disabled = false; controls.style.display = ''; document.getElementById('cars').style.display = '';
    return;
  }
  // user_steps: array of {y_pred, y_std, rmse, train_ids}
  const user_steps = data.user_steps || [];
  let user_step_idx = user_steps.length - 1;

  function renderUserStep(i) {
    const step = user_steps[i];
    renderUserStepGraph(step, data, 'plotUser', 'Jet', 'Dein Modell');
    document.getElementById('userStepInfo').textContent = `Schritt ${i + 1} / ${user_steps.length}`;
  }
  if (user_steps.length) {
    renderUserStep(user_step_idx);
  }

  // plot ground truth
  const groundCont = contourFromResponse({ V: data.V, M: data.M, y_pred: data.ground_truth });
  Plotly.newPlot('plotGround', [{ z: groundCont.z, x: groundCont.x, y: groundCont.y, type: 'contour', colorscale: 'Jet' }], {
    title: { text: 'Tatsächliches Ergebnis' },
    autosize: true,
    width: null,
    height: null,
    margin: { t: 40, l: 60, r: 20, b: 40 },
    colorbar: { title: { text: 'Bremsweg (m)' } },
    xaxis: { title: { text: 'Geschwindigkeit (km/h)' } },
    yaxis: { title: { text: 'Gewicht (kg)' } },
  }, { responsive: true });

  document.getElementById('userPrev').onclick = () => {
    if (user_step_idx > 0) {
      user_step_idx -= 1;
      renderUserStep(user_step_idx);
    }
  };
  document.getElementById('userNext').onclick = () => {
    if (user_step_idx < user_steps.length - 1) {
      user_step_idx += 1;
      renderUserStep(user_step_idx);
    }
  };

  document.getElementById('groundError').textContent = '';
  continueToAL.style.display = '';
  continueToAL.onclick = () => {
    showOnlyView(null);
    plotUser.innerHTML = '';
    document.getElementById('userStepInfo').textContent = '';
    document.getElementById('plotGround').innerHTML = '';
    document.getElementById('groundError').textContent = '';
    showActiveLearnerResult(data);
  };
}

function showActiveLearnerResult(data) {
  // plot active learner if available
  resultView.style.display = 'none';
  activeLearnerResult.style.display = 'block';
  const al_steps = data.al_steps || [];
  let al_step_idx = al_steps.length - 1;
  function renderAlStep(i) {
    const step = al_steps[i];
    renderUserStepGraph(step, data, 'plotAL', 'Jet', 'Aktiver Lerner');
    document.getElementById('alError').textContent = `Fehler AL: ${step.rmse.toFixed(2)}`;
    document.getElementById('alStepInfo').textContent = `Schritt ${i + 1} / ${al_steps.length}`;
  }

  function renderUncertaintyStep(i) {
    const step = al_steps[i];
    renderUserStepGraph(step, data, 'plotUncertainty', 'Greens', 'Aktiver-Lerner', true);
  }


  if (al_steps.length) {
    renderAlStep(al_step_idx);
    renderUncertaintyStep(al_step_idx);
  } else {
    const plotAL = document.getElementById('plotAL');
    plotAL.textContent = 'Aktiver Lerner nicht verfügbar.';
    document.getElementById('alError').textContent = '';
  }

  // navigation handlers
  document.getElementById('alPrev').onclick = () => { if (al_steps.length && al_step_idx > 0) { al_step_idx -= 1; renderAlStep(al_step_idx); renderUncertaintyStep(al_step_idx); } };
  document.getElementById('alNext').onclick = () => { if (al_steps.length && al_step_idx < al_steps.length - 1) { al_step_idx += 1; renderAlStep(al_step_idx); renderUncertaintyStep(al_step_idx); } };

  runBtn.disabled = false;

  // Compare numeric RMSE values (use numbers, not string comparisons)
  const user_steps = data.user_steps || [];
  const userFinal = Number(user_steps[user_steps.length - 1].rmse);
  const alFinal = al_steps.length ? Number(al_steps[al_steps.length - 1].rmse) : Infinity;
  if (userFinal > alFinal) {
    document.getElementById('Endsummary').textContent = `Das finale Modell hat einen Fehler von ${userFinal.toFixed(2)}, der aktive Lerner liegt bei ${alFinal !== Infinity ? alFinal.toFixed(2) : 'N/A'}. Der aktive Lerner hätte in diesem Fall besser abgeschnitten als dein Modell. Schau dir die Schritte des aktiven Lerners an, um zu verstehen, wie er trainiert wurde.`;
  } else if (userFinal === alFinal) {
    document.getElementById('Endsummary').textContent = `Das finale Modell hat einen Fehler von ${userFinal.toFixed(2)}, der aktive Lerner liegt bei ${alFinal !== Infinity ? alFinal.toFixed(2) : 'N/A'}. In diesem Fall haben dein Modell und der aktive Lerner die gleiche Leistung erbracht. Schau dir trotzdem die Schritte des aktiven Lerners an, um zu verstehen, wie er trainiert wurde.`;
  } else {
    document.getElementById('Endsummary').textContent = `Das finale Modell hat einen Fehler von ${userFinal.toFixed(2)}. Der aktive Lerner liegt bei ${alFinal !== Infinity ? alFinal.toFixed(2) : 'N/A'}. In diesem Fall hat dein Modell besser abgeschnitten als der aktive Lerner. Herzlichen Glückwunsch! Schau dir trotzdem die Schritte des aktiven Lerners an, um zu verstehen, wie er trainiert wurde.`;
  }
  renderLeaderboardForm(data.user_steps[data.user_steps.length - 1].rmse);
}

runBtn.onclick = () => { retrainCount = 0; runExperiments({ intermediateOnly: true }); };


function renderLeaderboardForm(lastScore) {
  // remember the last score so toggle can re-render later
  lastLeaderboardScore = lastScore;
  if (!leaderboardEnabled) {
    leaderboardArea.innerHTML = '';
    leaderboardArea.style.display = 'none';
    return;
  }
  leaderboardArea.style.display = '';
  leaderboardArea.innerHTML = '';
  const h2 = document.createElement('h2');
  h2.textContent = 'Leaderboard';
  leaderboardArea.appendChild(h2);
  const p = document.createElement('p');
  p.textContent = 'Wenn du möchtest, kannst du dich hier auf der Leaderboard-Seite eintragen. Trage dazu deinen Namen ein:';
  leaderboardArea.appendChild(p);
  const wrapper = document.createElement('div');
  const input = document.createElement('input');
  input.id = 'playerName'; input.className = 'form-control'; input.placeholder = 'Dein Name'; input.setAttribute('aria-label', 'Dein Name');
  const submit = document.createElement('button'); submit.type = 'button'; submit.id = 'submitScore'; submit.className = 'grn-btn'; submit.textContent = 'In Leaderboard eintragen'; submit.style.marginLeft = '8px';
  wrapper.appendChild(input); wrapper.appendChild(submit);
  leaderboardArea.appendChild(wrapper);
  submit.onclick = async () => {
    const name = input.value || 'anon';
    submit.disabled = true;
    try {
      const res = await fetch(`${BACKEND_HOST}/api/leaderboard`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, score: lastScore }) });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const el = document.createElement('div');
      const h = document.createElement('h3'); h.textContent = 'Leaderboard'; el.appendChild(h);
      (data.leaderboard || []).forEach((r, i) => {
        const row = document.createElement('div');
        // Print bold if name matches current player (case-insensitive)
        if (r.Name.toLowerCase() === name.toLowerCase()) {
          row.style.fontWeight = 'bold';
        }
        row.textContent = `${i + 1}. ${r.Name} — ${Number(r.Score).toFixed(2)}`;
        el.appendChild(row);
      });
      leaderboardArea.appendChild(el);
    } catch (e) {
      console.error('Failed to submit leaderboard', e);
      statusEl.textContent = 'Fehler beim Eintragen in das Leaderboard.';
    }
  };
}

loadCars();

// Initialize ResizeObserver to keep Plotly plots in sync with wrapper size
function initPlotResizeObserver() {
  if (typeof ResizeObserver === 'undefined') return;
  const ro = new ResizeObserver(entries => {
    for (const entry of entries) {
      const wrapper = entry.target;
      const gd = wrapper.querySelector && wrapper.querySelector('.plot');
      if (gd) {
        try { Plotly.Plots.resize(gd); } catch (e) { /* ignore */ }
      }
    }
  });
  document.querySelectorAll('.plot-wrapper').forEach(w => ro.observe(w));
}

// start observing plot wrappers
initPlotResizeObserver();

// Apply leaderboard setting from URL param at startup
if (leaderboardEnabled) {
  leaderboardArea.style.display = '';
} else {
  leaderboardArea.style.display = 'none';
}
