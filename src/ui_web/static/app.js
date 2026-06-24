'use strict';

// ============================================================
// State
// ============================================================

const state = {
    ticker:      '',
    S:           null,     // current stock price
    divYield:    0,        // dividend yield as decimal
    expirations: [],       // all available expirations
    chains:      {},       // cached option chains: { exp: { calls, puts, T } }
    quickIVs:    [null, null, null],
};

// ============================================================
// Init
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    setupListeners();
});

function setupListeners() {
    $('fTicker').addEventListener('input', onTickerInput);
    $('fTicker').addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); loadStockData(); }
    });
    $('btnLoad').addEventListener('click', loadStockData);
    $('btnHistVol').addEventListener('click', calcHistVol);
    $('btnCalculate').addEventListener('click', calculateFull);
    $('btnSaveConfig').addEventListener('click', saveConfig);

    $('fPrice').addEventListener('input', debounceRecalc);
    $('fExpiration').addEventListener('change', onExpirationChange);
    $('fStrike').addEventListener('change', onStrikeChange);
    $('fStrikeCustom').addEventListener('input', debounceRecalc);
    $('fVolatility').addEventListener('input', debounceRecalc);
    $('fRiskFree').addEventListener('input', debounceRecalc);
    $('fDividend').addEventListener('input', debounceRecalc);

    document.querySelectorAll('input[name="optType"]').forEach(r =>
        r.addEventListener('change', onOptionTypeChange)
    );

    $('chkAllDates').addEventListener('change', () => {
        if (state.ticker) loadExpirations(state.ticker);
    });

    // Quick-view strike inputs
    for (let i = 0; i < 3; i++) {
        $(`qstrike${i}`).addEventListener('blur',    () => recalcQuickRow(i));
        $(`qstrike${i}`).addEventListener('keydown', e => { if (e.key === 'Enter') recalcQuickRow(i); });
    }

    // Close autocomplete on outside click
    document.addEventListener('click', e => {
        if (!e.target.closest('#tickerWrap')) hideSuggestions();
    });
}

// ============================================================
// Auth helper — redirect to login on session expiry
// ============================================================

async function apiFetch(url, opts) {
    const resp = await fetch(url, opts);
    if (resp.status === 401) {
        document.querySelectorAll('.oc-app input, .oc-app button, .oc-app select')
            .forEach(el => { el.disabled = true; });
        setStatus('Session expired — you have been logged out. Redirecting…');
        setTimeout(() => { window.location.href = '/login?expired=1'; }, SESSION_EXPIRED_REDIRECT_MS);
        return new Promise(() => {});  // never resolves — callers stop
    }
    return resp;
}

// ============================================================
// Config
// ============================================================

async function loadConfig() {
    try {
        const resp = await apiFetch('/api/config');
        if (!resp.ok) return;
        const cfg = await resp.json();
        $('fRiskFree').value = cfg.risk_free_rate ?? 0.045;
    } catch (_) { /* use default */ }
}

async function saveConfig() {
    const r = parseFloat($('fRiskFree').value);
    if (isNaN(r)) { alert('Enter a valid risk-free rate (decimal, e.g. 0.045).'); return; }
    const resp = await apiFetch('/api/config', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ risk_free_rate: r }),
    });
    if (resp.ok) {
        const msg = $('cfgSavedMsg');
        msg.style.display = 'inline';
        setTimeout(() => { msg.style.display = 'none'; }, SAVED_MSG_DISMISS_MS);
    }
}

// ============================================================
// Ticker autocomplete
// ============================================================

let _tickerTimer = null;

function onTickerInput() {
    // Force uppercase in place
    const pos = this.selectionStart;
    this.value = this.value.toUpperCase();
    this.setSelectionRange(pos, pos);

    const q = this.value.trim();
    if (_tickerTimer) clearTimeout(_tickerTimer);
    if (q.length < 1) { hideSuggestions(); return; }
    _tickerTimer = setTimeout(() => doTickerSearch(q), TICKER_SEARCH_DELAY_MS);
}

async function doTickerSearch(query) {
    try {
        const resp = await apiFetch(`/api/search/${encodeURIComponent(query)}`);
        if (!resp.ok) { hideSuggestions(); return; }
        const results = await resp.json();
        renderSuggestions(results);
    } catch (_) { hideSuggestions(); }
}

function renderSuggestions(results) {
    const box = $('suggestionsBox');
    if (!results || results.length === 0) { hideSuggestions(); return; }
    box.innerHTML = results.map(r =>
        `<div class="oc-suggest-item" onclick="selectTicker('${escAttr(r.symbol)}')">` +
        `<span class="oc-suggest-sym">${escHtml(r.symbol)}</span>` +
        `<span class="oc-suggest-name">${escHtml(r.name || '')}</span>` +
        `</div>`
    ).join('');
    box.style.display = 'block';
}

function hideSuggestions() {
    $('suggestionsBox').style.display = 'none';
}

function selectTicker(sym) {
    $('fTicker').value = sym;
    hideSuggestions();
    loadStockData();
}

// ============================================================
// Stock data
// ============================================================

async function loadStockData() {
    const ticker = $('fTicker').value.trim().toUpperCase();
    if (!ticker) { alert('Enter a ticker symbol first.'); return; }
    $('fTicker').value = ticker;
    hideSuggestions();

    setStatus(`Loading data for ${ticker}…`);
    clearResults();

    let data;
    try {
        const resp = await apiFetch(`/api/stock/${ticker}`);
        data = await resp.json();
        if (!resp.ok) { setStatus(`Error: ${data.error || 'Failed to load'}`); return; }
    } catch (e) { setStatus(`Network error: ${e.message}`); return; }

    state.ticker   = ticker;
    state.S        = data.current_price;
    state.divYield = data.dividend_yield || 0;
    state.chains   = {};  // clear cached chains for previous ticker

    $('fPrice').value   = data.current_price != null ? data.current_price.toFixed(2) : '';
    $('fDividend').value = ((data.dividend_yield || 0) * 100).toFixed(2);
    $('lblEarnings').textContent = data.earnings_date || 'N/A';
    $('lblCompany').textContent  = `${data.company_name || ''} (${ticker})`;

    appendResult(`Company:       ${data.company_name}\n`);
    appendResult(`Current Price: $${data.current_price?.toFixed(2)}\n`);
    if (data.previous_close) appendResult(`Prev Close:    $${data.previous_close}\n`);
    if (data.volume)         appendResult(`Volume:        ${Number(data.volume).toLocaleString()}\n`);
    appendResult(`Div Yield:     ${((data.dividend_yield || 0) * 100).toFixed(2)}%\n`);
    appendResult(`Next Earnings: ${data.earnings_date || 'unavailable'}\n`);

    // Show which data source served the request so provider failures are visible
    const src = data.data_source;
    if (src === 'massive') {
        appendResult(`Data source:   Massive.com\n`);
    } else if (src === 'yahoo_fallback') {
        appendResult(`Data source:   Yahoo Finance (Massive.com unavailable)\n`);
    }

    const srcNote = src === 'massive'        ? ' [Massive]'
                  : src === 'yahoo_fallback' ? ' [Yahoo — Massive unavailable]'
                  : '';
    setStatus(`Loaded ${data.company_name} (${ticker})${srcNote}`);

    await loadExpirations(ticker);
}

// ============================================================
// Expirations
// ============================================================

async function loadExpirations(ticker) {
    setStatus('Loading expiration dates…');

    const allDates = $('chkAllDates').checked;
    const url = `/api/expirations/${ticker}${allDates ? '?all=true' : ''}`;

    let data;
    try {
        const resp = await apiFetch(url);
        data = await resp.json();
        if (!resp.ok) { setStatus(`Error: ${data.error}`); return; }
    } catch (e) { setStatus(`Network error: ${e.message}`); return; }

    state.expirations = data.expirations || [];

    const sel = $('fExpiration');
    sel.innerHTML = state.expirations
        .map(e => `<option value="${e}">${e}</option>`)
        .join('');

    if (state.expirations.length > 0) {
        sel.value = state.expirations[0];
        await onExpirationChange();  // wait so strike/IV are set before quick view
    }

    loadQuickView();  // non-blocking; fetches ATM IV for each of the 3 rows
}

// ============================================================
// Expiration / strike / type changes
// ============================================================

async function onExpirationChange() {
    const exp     = $('fExpiration').value;
    const optType = getOptType();
    const S       = parseFloat($('fPrice').value);
    const r       = parseFloat($('fRiskFree').value);

    if (!exp || !state.ticker || !S) return;

    // Remember current strike before repopulating so we can try to preserve it
    const prevStrikeStr = $('fStrike').value;

    setStatus(`Loading options for ${exp}…`);

    const chain = await loadChain(state.ticker, exp);
    if (!chain) { setStatus('Failed to load options'); return; }

    const chainData = optType === 'call' ? chain.calls : chain.puts;
    if (!chainData || chainData.length === 0) {
        setStatus('No options found for this expiration'); return;
    }

    const strikes = chainData.map(o => o.strike).sort((a, b) => a - b);

    // Populate the dropdown with all listed strikes
    const strikeEl = $('fStrike');
    strikeEl.innerHTML = strikes
        .map(s => `<option value="${s}">${s.toFixed(2)}</option>`)
        .join('');

    // Try to keep the previous listed strike; fall back to nearest at or above ATM
    let selectedStrike;
    if (prevStrikeStr) {
        strikeEl.value = prevStrikeStr;
        if (strikeEl.value === prevStrikeStr) {
            selectedStrike = parseFloat(prevStrikeStr);
        }
    }
    if (!selectedStrike || isNaN(selectedStrike)) {
        selectedStrike = strikes.find(s => s >= S) ?? strikes[strikes.length - 1];
        strikeEl.value = selectedStrike;
    }

    // Compute IV for selected strike; fall back to ATM IV if the strike has no
    // usable bid/ask (e.g. deep OTM strikes with zero markets on low-price stocks).
    const opt = chainData.find(o => o.strike === selectedStrike);
    let iv = opt ? await computeIV(opt, selectedStrike, S, chain.T, r, optType) : null;
    if (!iv || iv <= 0) {
        try {
            const resp = await apiFetch(
                `/api/atm-iv/${state.ticker}/${exp}/${optType}?S=${S}&r=${r}`
            );
            if (resp.ok) {
                const d = await resp.json();
                if (d.atm_iv && d.atm_iv > 0) iv = d.atm_iv;
            }
        } catch (_) { /* leave iv null */ }
    }
    if (iv && iv > 0) {
        $('fVolatility').value = (iv * 100).toFixed(2);
    }

    setStatus(`${strikes.length} strikes for ${exp}`);
    debounceRecalc();
}

async function onStrikeChange() {
    const strike  = getStrike();
    const exp     = $('fExpiration').value;
    const optType = getOptType();
    const S       = parseFloat($('fPrice').value);
    const r       = parseFloat($('fRiskFree').value);

    if (isNaN(strike) || !exp) { debounceRecalc(); return; }

    const chain = state.chains[exp];
    if (chain) {
        const chainData = optType === 'call' ? chain.calls : chain.puts;
        const opt = chainData?.find(o => o.strike === strike);
        if (opt) {
            const iv = await computeIV(opt, strike, S, chain.T, r, optType);
            if (iv && iv > 0) {
                $('fVolatility').value = (iv * 100).toFixed(2);
            }
        }
    }

    // Sync quick-view strikes to match
    for (let i = 0; i < 3; i++) {
        $(`qstrike${i}`).value = strike.toFixed(2);
        const first3 = state.expirations.slice(0, 3);
        if (i < first3.length) calcQuickRowPrice(i, first3[i]);
    }

    debounceRecalc();
}

async function onOptionTypeChange() {
    const exp = $('fExpiration').value;
    if (exp && state.ticker) {
        $('fVolatility').value = '';   // stale IV from the previous type; force re-resolve
        await onExpirationChange();    // repopulate strikes + best IV for new type
    } else {
        debounceRecalc();
    }
    loadQuickView();  // refresh date labels (c↔p suffix) and ATM IVs
}

// Load chain from cache or fetch from API
async function loadChain(ticker, exp) {
    if (state.chains[exp]) return state.chains[exp];
    try {
        const resp = await apiFetch(`/api/options/${ticker}/${exp}`);
        if (!resp.ok) return null;
        const data = await resp.json();
        state.chains[exp] = data;
        return data;
    } catch (_) { return null; }
}

// Compute IV: bid/ask mid via API first, fall back to stored IV
async function computeIV(opt, K, S, T, r, optType) {
    if (opt.bid > 0 && opt.ask > 0 && T > 0) {
        const mid = (opt.bid + opt.ask) / 2;
        try {
            const resp = await apiFetch('/api/iv', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ market_price: mid, S, K, T, r, option_type: optType }),
            });
            if (resp.ok) {
                const d = await resp.json();
                if (d.iv && d.iv > 0) return d.iv;
            }
        } catch (_) { /* fall through */ }
    }
    return opt.implied_volatility || null;
}

// ============================================================
// Quick View
// ============================================================

async function loadQuickView() {
    if (!state.ticker || !state.S || state.expirations.length === 0) return;

    const optType    = getOptType();
    const S          = state.S;
    const r          = parseFloat($('fRiskFree').value);
    const mainStrike = getStrike() || null;
    const first3     = state.expirations.slice(0, 3);

    state.quickIVs = [null, null, null];

    for (let i = 0; i < 3; i++) {
        const row = $(`qrow${i}`);
        if (i < first3.length) {
            row.style.display = '';
            const exp = first3[i];
            $(`qdate${i}`).textContent  = fmtExpDate(exp, optType);
            $(`qstrike${i}`).value      = mainStrike ? mainStrike.toFixed(2) : '';
            $(`qiv${i}`).textContent    = '…';
            $(`qprice${i}`).textContent = '…';
            fetchQuickRowIV(i, exp, optType, S, r);  // non-blocking
        } else {
            row.style.display = 'none';
        }
    }
}

async function fetchQuickRowIV(rowIdx, exp, optType, S, r) {
    try {
        const params = new URLSearchParams({ S, r });
        const resp = await apiFetch(`/api/atm-iv/${state.ticker}/${exp}/${optType}?${params}`);
        if (!resp.ok) throw new Error('bad response');
        const data  = await resp.json();
        const iv    = data.atm_iv;

        if (iv && iv > 0) {
            state.quickIVs[rowIdx]          = iv;
            $(`qiv${rowIdx}`).textContent   = `${(iv * 100).toFixed(1)}%`;
            // If this row matches the currently selected expiry and fVolatility
            // is still empty (per-strike IV lookup failed), back-fill it now so
            // the fair-price display uses the same IV as the quick view.
            if (rowIdx === 0 && exp === $('fExpiration').value
                    && !parseFloat($('fVolatility').value)) {
                $('fVolatility').value = (iv * 100).toFixed(2);
                debounceRecalc();
            }
        } else {
            $(`qiv${rowIdx}`).textContent   = '--';
        }
    } catch (_) {
        $(`qiv${rowIdx}`).textContent = '--';
    }
    await calcQuickRowPrice(rowIdx, exp);
}

async function calcQuickRowPrice(rowIdx, exp) {
    const K       = parseFloat($(`qstrike${rowIdx}`).value);
    const S       = parseFloat($('fPrice').value);
    const sigma   = state.quickIVs[rowIdx] ?? (parseFloat($('fVolatility').value) / 100);
    const r       = parseFloat($('fRiskFree').value);
    const q       = parseFloat($('fDividend').value) / 100;
    const optType = getOptType();

    if (!K || !S || !sigma || isNaN(r) || !exp) {
        $(`qprice${rowIdx}`).textContent = '--'; return;
    }

    try {
        const resp = await apiFetch('/api/calculate', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ S, K, expiration: exp, sigma, r, q, option_type: optType }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            setStatus(`Error: ${err.error || 'calculation failed'}`);
            $(`qprice${rowIdx}`).textContent = '--';
            return;
        }
        const data = await resp.json();
        $(`qprice${rowIdx}`).textContent = `$${data.price.toFixed(2)}`;
    } catch (_) {
        $(`qprice${rowIdx}`).textContent = '--';
    }
}

async function recalcQuickRow(rowIdx) {
    const first3 = state.expirations.slice(0, 3);
    if (rowIdx < first3.length) await calcQuickRowPrice(rowIdx, first3[rowIdx]);
}

// ============================================================
// Live recalculation (Calculated Price display)
// ============================================================

let _calcTimer = null;

function debounceRecalc() {
    if (_calcTimer) clearTimeout(_calcTimer);
    _calcTimer = setTimeout(doRecalc, 300);
}

async function doRecalc() {
    const S       = parseFloat($('fPrice').value);
    const K       = getStrike();
    const exp     = $('fExpiration').value;
    const sigma   = parseFloat($('fVolatility').value) / 100;
    const r       = parseFloat($('fRiskFree').value);
    const q       = parseFloat($('fDividend').value) / 100;
    const optType = getOptType();

    if (!S || !K || !exp || !sigma || isNaN(r) || isNaN(q)) {
        $('lblCalcPrice').textContent = '--';
        $('lblDelta').textContent = '--';
        $('lblTheta').textContent = '--';
        return;
    }

    try {
        const resp = await apiFetch('/api/calculate', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ S, K, expiration: exp, sigma, r, q, option_type: optType }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            setStatus(`Error: ${err.error || 'calculation failed'}`);
            return;
        }
        const data = await resp.json();
        $('lblCalcPrice').textContent = `$${data.price.toFixed(2)}`;
        $('lblDelta').textContent = data.greeks?.delta != null
            ? data.greeks.delta.toFixed(4)
            : '--';
        $('lblTheta').textContent = data.greeks?.theta != null
            ? `$${data.greeks.theta.toFixed(4)} / day`
            : '--';
    } catch (_) { /* ignore */ }
}

// ============================================================
// Full Calculation (results panel)
// ============================================================

async function calculateFull() {
    const S       = parseFloat($('fPrice').value);
    const K       = getStrike();
    const exp     = $('fExpiration').value;
    const sigma   = parseFloat($('fVolatility').value) / 100;
    const r       = parseFloat($('fRiskFree').value);
    const q       = parseFloat($('fDividend').value) / 100;
    const optType = getOptType();
    const ticker  = $('fTicker').value.trim().toUpperCase();

    if (!S || !K || !exp || !sigma) {
        alert('Please load stock data and select an expiration / strike first.');
        return;
    }

    let data;
    try {
        const resp = await apiFetch('/api/calculate', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ S, K, expiration: exp, sigma, r, q, option_type: optType }),
        });
        data = await resp.json();
        if (!resp.ok) { setStatus(`Calculation error: ${data.error}`); return; }
    } catch (e) { setStatus(`Network error: ${e.message}`); return; }

    const g   = data.greeks;
    const p   = (label, val) => `  ${label.padEnd(22)}${val}`;
    const sep = '='.repeat(60);

    const lines = [
        sep,
        'AMERICAN OPTION VALUATION (Binomial Model)',
        sep,
        '',
        'INPUT PARAMETERS:',
        p('Ticker:',            ticker),
        p('Option Type:',       optType.toUpperCase()),
        p('Stock Price (S):',   `$${S.toFixed(2)}`),
        p('Strike Price (K):',  `$${K.toFixed(2)}`),
        p('Expiration Date:',   `${exp} (${data.days} days)`),
        p('Time to Expiry:',    `${data.T.toFixed(4)} years`),
        p('Volatility (σ):',    `${(sigma * 100).toFixed(2)}%`),
        p('Risk-Free Rate (r):', `${r.toFixed(4)} (${(r * 100).toFixed(2)}%)`),
        p('Dividend Yield (q):', `${(q * 100).toFixed(2)}%`),
        '',
        'VALUATION RESULTS:',
        p('Option Price:',       `$${data.price.toFixed(4)}`),
        '',
        'THE GREEKS:',
        p('Delta (Δ):',          g.delta.toFixed(4)),
        p('Gamma (Γ):',          g.gamma.toFixed(4)),
        p('Theta (Θ):',          `${g.theta.toFixed(4)} (per day)`),
        p('Vega (ν):',           `${g.vega.toFixed(4)} (per 1% change)`),
        p('Rho (ρ):',            `${g.rho.toFixed(4)} (per 1% change)`),
        '',
        sep,
    ];

    $('resultsText').textContent = lines.join('\n');
    $('lblCalcPrice').textContent = `$${data.price.toFixed(2)}`;
    $('lblDelta').textContent = g.delta != null ? g.delta.toFixed(4) : '--';
    $('lblTheta').textContent = g.theta != null
        ? `$${g.theta.toFixed(4)} / day`
        : '--';
}

// ============================================================
// Historical Volatility
// ============================================================

async function calcHistVol() {
    const ticker = $('fTicker').value.trim().toUpperCase();
    if (!ticker) { alert('Enter a ticker symbol first.'); return; }

    setStatus('Calculating historical volatility…');

    let data;
    try {
        const resp = await apiFetch(`/api/hist-vol/${ticker}`);
        data = await resp.json();
        if (!resp.ok) { setStatus(`Error: ${data.error}`); return; }
    } catch (e) { setStatus(`Network error: ${e.message}`); return; }

    const volPct = data.hist_vol * 100;
    $('fVolatility').value = volPct.toFixed(2);
    setStatus(`Historical Volatility (1y): ${volPct.toFixed(2)}%`);
    appendResult(`Historical Volatility (1 year): ${volPct.toFixed(2)}%\n`);
    debounceRecalc();
}

// ============================================================
// Utilities
// ============================================================

function getOptType() {
    return document.querySelector('input[name="optType"]:checked').value;
}

/** Return the effective strike: custom input if filled, else the dropdown. */
function getStrike() {
    const custom = parseFloat($('fStrikeCustom').value);
    if (!isNaN(custom) && custom > 0) return custom;
    return parseFloat($('fStrike').value);
}

function setStatus(msg) {
    $('statusLine').textContent = msg;
}

function clearResults() {
    $('resultsText').textContent = '';
}

function appendResult(text) {
    $('resultsText').textContent += text;
}

function fmtExpDate(exp, optType) {
    try {
        const [y, m, d] = exp.split('-');
        return `${m}/${d}/${y.slice(2)}${optType === 'call' ? 'c' : 'p'}`;
    } catch (_) { return exp; }
}

function escHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function escAttr(s) {
    return String(s).replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

function $(id) { return document.getElementById(id); }
