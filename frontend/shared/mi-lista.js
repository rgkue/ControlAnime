/**
 * mi-lista.js — Módulo autónomo para la sección /mi-lista del dashboard SPA
 *
 * Expone window.MiLista = { init, refresh }
 * El router (script.js) llama init() la primera vez y refresh() las siguientes.
 *
 * Sincronización en tiempo real con /anime/{id}:
 * Usa BroadcastChannel('ca_lista') para recibir eventos de invalidación
 * cuando el usuario modifica su lista desde la ficha de un anime.
 * Funciona sin redirects, sin sessionStorage, sin timing issues.
 */

;(function () {

// ── Guardia: no inicializar dos veces ────────────────────────────────────────
if (window.MiLista) { window.MiLista.refresh(); return }

// ── Estado ───────────────────────────────────────────────────────────────────
const s = {
    cache:     null,      // { vistos: [], pendientes: [], likes: [] }
    loading:   false,
    tab:       'vistos',  // 'vistos' | 'pendientes' | 'likes' | 'abandonados' | 'historial'
    vista:     'cards',   // 'cards' | 'filas'
    orden:     'fecha-desc',
    query:     '',
    pagina:    1,
    porPagina: 20,
    ctxMenu:   null,
    bound:     false,     // listeners ya bindeados
}

// ── BroadcastChannel — escucha eventos de /anime/{id} ────────────────────────
let bc = null
function initBroadcast() {
    try {
        bc = new BroadcastChannel('ca_lista')
        bc.onmessage = (e) => {
            if (e.data?.tipo === 'invalidar') {
                s.cache = null
                // Solo re-fetch si la sección está activa en pantalla
                if (document.getElementById('section-mi-lista')?.classList.contains('active')) {
                    _fetch()
                }
            }
        }
    } catch (e) {
        // BroadcastChannel no disponible (Firefox privado, etc.) — no pasa nada
    }
}

// ── Fetch ────────────────────────────────────────────────────────────────────
async function _fetch() {
    if (s.loading) return
    s.loading = true
    _renderLoading()
    try {
        const res  = await fetch('/lista')
        if (!res.ok) throw new Error(res.status)
        const data = await res.json()
        const lista = data.lista || []
        const likes = data.likes || []
        const abandonados = data.abandonados || lista.filter(a => a.tipo === 'abandonado')
        // Historial = todos ordenados por fecha desc (vistos + pendientes + abandonados + likes)
        const todos = [
            ...lista,
            ...likes.map(a => ({...a, tipo: 'like'}))
        ].sort((a, b) => new Date(b.agregado_en || 0) - new Date(a.agregado_en || 0))
        s.cache = {
            vistos:      lista.filter(a => a.tipo === 'visto'),
            pendientes:  lista.filter(a => a.tipo === 'pendiente'),
            likes,
            abandonados,
            historial:   todos,
        }
        // Sincronizar con state global del dashboard (contadores, inicio, stats)
        if (window._dashState) {
            window._dashState.lista.visto     = s.cache.vistos
            window._dashState.lista.pendiente = s.cache.pendientes
            if (typeof updateListCounters === 'function') updateListCounters()
        }
    } catch (err) {
        _el('tabContent').innerHTML =
            `<div class="empty-state"><div class="empty-icon">⚠️</div><p>Error al cargar la lista.</p><span>Intenta recargar la página.</span></div>`
        s.loading = false
        return
    }
    s.loading = false
    render()
}

// ── API pública ───────────────────────────────────────────────────────────────
async function init() {
    initBroadcast()
    _bindControls()
    if (s.cache) { render(); return }
    await _fetch()
}

async function refresh() {
    // Llamado por el router cada vez que se activa la sección.
    // Si el BroadcastChannel ya marcó el caché como null, re-fetch.
    // Si el caché sigue vivo, solo re-render (cambio de tab, etc.)
    if (!s.cache) {
        await _fetch()
    } else {
        render()
    }
}

window.MiLista = { init, refresh }

// ── Helpers DOM ───────────────────────────────────────────────────────────────
function _el(id) { return document.getElementById(id) }

function _escHtml(v = '') {
    return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}

function _fechaRel(str) {
    if (!str) return ''
    try {
        const d    = new Date(str)
        const diff = Date.now() - d.getTime()
        const mins = Math.floor(diff / 60000)
        if (mins < 1)   return 'ahora mismo'
        if (mins < 60)  return `hace ${mins} min`
        const hrs = Math.floor(mins / 60)
        if (hrs < 24)   return `hace ${hrs}h`
        const days = Math.floor(hrs / 24)
        if (days < 7)   return `hace ${days} días`
        return d.toLocaleDateString('es', { day: 'numeric', month: 'short' })
    } catch { return '' }
}

// ── Datos filtrados y ordenados ───────────────────────────────────────────────
function _datos() {
    if (!s.cache) return []
    const src = { vistos: s.cache.vistos, pendientes: s.cache.pendientes, likes: s.cache.likes, abandonados: s.cache.abandonados, historial: s.cache.historial }[s.tab] || []
    const q   = s.query.toLowerCase().trim()
    const filtrado = q
        ? src.filter(a => (a.titulo || '').toLowerCase().includes(q) || (a.titulo_alternativo || '').toLowerCase().includes(q))
        : src
    const copia = [...filtrado]
    switch (s.orden) {
        case 'fecha-asc':  copia.sort((a,b) => new Date(a.agregado_en||0) - new Date(b.agregado_en||0)); break
        case 'titulo-az':  copia.sort((a,b) => (a.titulo||'').localeCompare(b.titulo||'','es'));          break
        case 'titulo-za':  copia.sort((a,b) => (b.titulo||'').localeCompare(a.titulo||'','es'));          break
        case 'rating-desc':copia.sort((a,b) => (b.rating||0) - (a.rating||0));                           break
        default:           copia.sort((a,b) => new Date(b.agregado_en||0) - new Date(a.agregado_en||0))
    }
    return copia
}

// ── Render principal ──────────────────────────────────────────────────────────
function render() {
    _actualizarTabs()
    _actualizarOrden()
    const datos     = _datos()
    const total     = datos.length
    const pp        = s.porPagina
    const totalPags = Math.max(1, Math.ceil(total / pp))
    if (s.pagina > totalPags) s.pagina = totalPags

    const inicio = (s.pagina - 1) * pp
    const pagina = datos.slice(inicio, inicio + pp)
    const c = _el('tabContent')
    if (!c) return

    if (!total) { c.innerHTML = _htmlVacio(); return }

    let html = s.vista === 'cards'
        ? `<div class="lista-grid">${pagina.map(a => _htmlCard(a)).join('')}</div>`
        : `<div class="lista-rows">${pagina.map((a,i) => _htmlRow(a, inicio+i)).join('')}</div>`

    html += _htmlPaginacion(s.pagina, totalPags, total)
    c.innerHTML = html

    // Eventos cards/filas
    c.querySelectorAll('[data-ml-id]').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.closest('.ml-ctx-trigger')) return
            location.href = `/mi-lista/anime/${el.dataset.mlId}`
        })
        const trigger = el.querySelector('.ml-ctx-trigger')
        if (trigger) {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation()
                _abrirCtx(e, el.dataset.mlId, el.dataset.mlTipo)
            })
        }
        el.addEventListener('contextmenu', (e) => {
            e.preventDefault()
            _abrirCtx(e, el.dataset.mlId, el.dataset.mlTipo)
        })
    })

    // Eventos paginación
    c.querySelectorAll('[data-pag]').forEach(btn => {
        btn.addEventListener('click', () => {
            s.pagina = parseInt(btn.dataset.pag)
            render()
            document.querySelector('.content')?.scrollTo(0, 0)
        })
    })
}

function _renderLoading() {
    const c = _el('tabContent')
    if (!c) return
    c.innerHTML = `<div class="lista-grid">${Array.from({length: 8}, () => `
        <div class="lista-card">
            <div class="lista-card-cover skeleton" style="position:absolute;inset:0;filter:none;border-radius:10px"></div>
        </div>`).join('')}</div>`
}

// ── HTML helpers ──────────────────────────────────────────────────────────────
function _badge(tipo) {
    return tipo === 'visto'     ? '<span class="lista-badge-tipo visto">✓ Visto</span>'
         : tipo === 'pendiente' ? '<span class="lista-badge-tipo pendiente">⏳ Pendiente</span>'
         : '<span class="lista-badge-tipo like">❤ Me gusta</span>'
}

function _htmlCard(a) {
    const cover  = _escHtml(a.cover_url  || a.poster_url || '')
    const poster = _escHtml(a.poster_url || '')
    const titulo = _escHtml(a.titulo || 'Sin título')
    const fecha  = _fechaRel(a.agregado_en)
    return `
    <div class="lista-card" data-ml-id="${a.id}" data-ml-tipo="${a.tipo||''}" onclick="_irDetalle(event, '${a.id}')">
        <div class="lista-card-cover" style="background-image:url('${cover}')"></div>
        <button class="ml-ctx-trigger" title="Opciones">⋯</button>
        <img class="lista-card-poster" src="${poster}" alt="${titulo}" loading="lazy">
        <div class="lista-card-info">
            <div class="lista-card-title">${titulo}</div>
            <div class="lista-card-meta">
                ${_badge(a.tipo)}
                ${a.rating ? `<span class="lista-card-rating">★ ${a.rating}</span>` : ''}
                ${fecha    ? `<span class="lista-card-fecha">${fecha}</span>`        : ''}
            </div>
        </div>
    </div>`
}

function _htmlRow(a, idx) {
    const poster = _escHtml(a.poster_url || '')
    const titulo = _escHtml(a.titulo || 'Sin título')
    const fecha  = _fechaRel(a.agregado_en)
    const genres = a.genres ? ` · ${a.genres}` : ''
    return `
    <div class="lista-row" data-ml-id="${a.id}" data-ml-tipo="${a.tipo||''}" onclick="_irDetalle(event, '${a.id}')">
        <span class="lista-row-num">${idx + 1}</span>
        <img class="lista-row-poster" src="${poster}" alt="${titulo}" loading="lazy">
        <div class="lista-row-info">
            <span class="lista-row-titulo">${titulo}</span>
            <span class="lista-row-meta">${a.episodios ? a.episodios + ' eps' : ''}${genres}</span>
        </div>
        <div class="lista-row-right">
            ${_badge(a.tipo)}
            ${a.rating ? `<span class="lista-row-rating">★ ${a.rating}</span>` : ''}
            <span class="lista-row-fecha">${fecha}</span>
        </div>
        <button class="ml-ctx-trigger" title="Opciones">⋯</button>
    </div>`
}

function _htmlVacio() {
    if (s.query) return `<div class="empty-state"><div class="empty-icon">🔍</div><p>Sin resultados para "${_escHtml(s.query)}"</p><span>Prueba con otro título.</span></div>`
    const msgs = {
        abandonados: ['🚫', 'Sin abandonados', 'Los animes que dejes a medias aparecerán aquí.'],
        historial:   ['🕐', 'Sin actividad', 'Tu historial de animes agregados aparecerá aquí.'],
        vistos:     ['👁️', 'Aún no has marcado ningún anime como visto.',    'Explora tendencias y márcalos desde la ficha del anime.'],
        pendientes: ['⏳', 'No tienes animes pendientes.',                    'Agrega animes a tu lista de pendientes desde su ficha.'],
        likes:      ['❤️', 'No has dado me gusta a ningún anime todavía.',   'Pulsa el corazón en la ficha de cualquier anime.'],
    }
    const [icon, title, sub] = msgs[s.tab] || msgs.vistos
    return `<div class="empty-state"><div class="empty-icon">${icon}</div><p>${title}</p><span>${sub}</span></div>`
}

function _htmlPaginacion(actual, total, items) {
    if (total <= 1) return ''
    const pp  = s.porPagina
    const ini = (actual - 1) * pp + 1
    const fin = Math.min(actual * pp, items)
    const rango  = new Set([1, total, actual, actual-1, actual+1, actual-2, actual+2].filter(p => p >= 1 && p <= total))
    const sorted = [...rango].sort((a,b) => a-b)
    let prev = 0, btns = []
    for (const p of sorted) {
        if (p - prev > 1) btns.push(`<span class="pag-ellipsis">…</span>`)
        btns.push(`<button class="pag-btn${p === actual ? ' active' : ''}" data-pag="${p}">${p}</button>`)
        prev = p
    }
    return `
    <div class="ml-paginacion">
        <span class="pag-info">${ini}–${fin} de ${items}</span>
        <div class="pag-btns">
            <button class="pag-btn pag-arrow" data-pag="${actual-1}" ${actual<=1?'disabled':''}>‹</button>
            ${btns.join('')}
            <button class="pag-btn pag-arrow" data-pag="${actual+1}" ${actual>=total?'disabled':''}>›</button>
        </div>
    </div>`
}

// ── Tabs y controles ──────────────────────────────────────────────────────────
function _actualizarTabs() {
    if (!s.cache) return
    const counts = {
        vistos:      s.cache.vistos.length,
        pendientes:  s.cache.pendientes.length,
        likes:       s.cache.likes.length,
        abandonados: s.cache.abandonados.length,
        historial:   s.cache.historial.length,
    }
    ;['vistos','pendientes','likes','abandonados','historial'].forEach(key => {
        const el = _el(`mlTab${key.charAt(0).toUpperCase()+key.slice(1)}`)
        if (!el) return
        el.querySelector('.ml-tab-count')?.remove()
        if (counts[key] > 0) {
            const badge = document.createElement('span')
            badge.className = 'ml-tab-count'
            badge.textContent = counts[key]
            el.appendChild(badge)
        }
    })
    document.querySelectorAll('.ml-tab').forEach(t => t.classList.remove('active'))
    const tabKey = s.tab.charAt(0).toUpperCase() + s.tab.slice(1)
    _el(`mlTab${tabKey}`)?.classList.add('active')
}

function _actualizarOrden() {
    const sel = _el('mlOrdenSelect')
    if (sel) sel.value = s.orden
}

// ── Cache lookup ──────────────────────────────────────────────────────────────
function _findEnCache(id) {
    if (!s.cache) return null
    return [...s.cache.vistos, ...s.cache.pendientes, ...s.cache.likes]
        .find(a => String(a.id) === String(id)) || null
}

// ── Menú contextual ───────────────────────────────────────────────────────────
function _abrirCtx(e, animeId, tipoActual) {
    _cerrarCtx()
    const anime = _findEnCache(animeId)
    if (!anime) return
    const opciones = []
    if (tipoActual !== 'like') {
        if (tipoActual !== 'visto')     opciones.push({ label: '✓ Mover a Vistos',     fn: () => _mover(animeId, 'visto') })
        if (tipoActual !== 'pendiente') opciones.push({ label: '⏳ Mover a Pendientes', fn: () => _mover(animeId, 'pendiente') })
    }
    opciones.push({ label: '↗ Ver ficha',           fn: () => { location.href = `/dashboard/anime/${animeId}` } })
    opciones.push({ label: '🗑 Eliminar de lista',   fn: () => _eliminar(animeId), danger: true })

    const menu = document.createElement('div')
    menu.className = 'ml-ctx-menu'
    menu.innerHTML = opciones.map(o =>
        `<button class="ml-ctx-item${o.danger?' danger':''}">${o.label}</button>`
    ).join('')
    document.body.appendChild(menu)

    const vw = window.innerWidth, vh = window.innerHeight
    let x = e.pageX || e.clientX, y = e.pageY || e.clientY
    if (x + 190 > vw) x = vw - 196
    if (y + menu.offsetHeight + 20 > vh) y = y - menu.offsetHeight - 8
    menu.style.left = x + 'px'
    menu.style.top  = y + 'px'

    menu.querySelectorAll('.ml-ctx-item').forEach((btn, i) => {
        btn.addEventListener('click', (ev) => { ev.stopPropagation(); _cerrarCtx(); opciones[i].fn() })
    })
    s.ctxMenu = menu
    setTimeout(() => document.addEventListener('click', _cerrarCtx, { once: true }), 10)
}

function _cerrarCtx() {
    if (s.ctxMenu) { s.ctxMenu.remove(); s.ctxMenu = null }
}

// ── Acciones ──────────────────────────────────────────────────────────────────
async function _mover(animeId, nuevoTipo) {
    try {
        const res = await fetch('/lista/agregar', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json', ..._csrf() },
            body:    JSON.stringify({ anime_id: animeId, tipo: nuevoTipo })
        })
        if (!res.ok) return
        if (!s.cache) return
        const anime = _findEnCache(animeId)
        if (!anime) return
        s.cache.vistos     = s.cache.vistos.filter(a => String(a.id) !== String(animeId))
        s.cache.pendientes = s.cache.pendientes.filter(a => String(a.id) !== String(animeId))
        const actualizado  = { ...anime, tipo: nuevoTipo, agregado_en: new Date().toISOString() }
        if (nuevoTipo === 'visto')     s.cache.vistos.unshift(actualizado)
        if (nuevoTipo === 'pendiente') s.cache.pendientes.unshift(actualizado)
        _syncState()
        render()
    } catch {}
}

async function _eliminar(animeId) {
    try {
        const res = await fetch('/lista/eliminar', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json', ..._csrf() },
            body:    JSON.stringify({ anime_id: animeId })
        })
        if (!res.ok) return
        if (!s.cache) return
        s.cache.vistos     = s.cache.vistos.filter(a => String(a.id) !== String(animeId))
        s.cache.pendientes = s.cache.pendientes.filter(a => String(a.id) !== String(animeId))
        s.cache.likes      = s.cache.likes.filter(a => String(a.id) !== String(animeId))
        _syncState()
        const datos     = _datos()
        const totalPags = Math.max(1, Math.ceil(datos.length / s.porPagina))
        if (s.pagina > totalPags) s.pagina = totalPags
        render()
    } catch {}
}

function _syncState() {
    if (window._dashState) {
        window._dashState.lista.visto     = s.cache.vistos
        window._dashState.lista.pendiente = s.cache.pendientes
        if (typeof updateListCounters === 'function') updateListCounters()
    }
}

function _csrf() {
    const meta = document.querySelector('meta[name="csrf-token"]')
    return meta ? { 'X-CSRF-Token': meta.content } : {}
}

// ── Bind controles (una sola vez) ─────────────────────────────────────────────
function _irDetalle(e, animeId) {
    // No navegar si el clic fue en el botón de contexto o dentro del menú ctx
    if (e.target.closest('.ml-ctx-trigger') || e.target.closest('.ctx-menu')) return
    location.href = `/mi-lista/anime/${animeId}`
}

function _bindControls() {
    if (s.bound) return
    s.bound = true

    const on = (id, fn) => _el(id)?.addEventListener('click', fn)

    on('mlTabVistos',      () => { s.tab = 'vistos';      s.pagina = 1; render() })
    on('mlTabPendientes',  () => { s.tab = 'pendientes';  s.pagina = 1; render() })
    on('mlTabLikes',       () => { s.tab = 'likes';       s.pagina = 1; render() })
    on('mlTabAbandonados', () => { s.tab = 'abandonados'; s.pagina = 1; render() })
    on('mlTabHistorial',   () => { s.tab = 'historial';   s.pagina = 1; render() })

    on('mlBtnCards', () => {
        s.vista = 'cards'
        _el('mlBtnCards')?.classList.add('active')
        _el('mlBtnFilas')?.classList.remove('active')
        render()
    })
    on('mlBtnFilas', () => {
        s.vista = 'filas'
        _el('mlBtnFilas')?.classList.add('active')
        _el('mlBtnCards')?.classList.remove('active')
        render()
    })

    _el('mlOrdenSelect')?.addEventListener('change', (e) => {
        s.orden = e.target.value; s.pagina = 1; render()
    })

    let searchTimer = null
    _el('mlSearch')?.addEventListener('input', (e) => {
        clearTimeout(searchTimer)
        searchTimer = setTimeout(() => { s.query = e.target.value; s.pagina = 1; render() }, 200)
    })

    on('mlSearchClear', () => {
        const inp = _el('mlSearch')
        if (inp) inp.value = ''
        s.query = ''; s.pagina = 1; render()
        _el('mlSearch')?.focus()
    })
}

})() // fin IIFE
