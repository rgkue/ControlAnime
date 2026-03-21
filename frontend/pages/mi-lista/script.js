;(function () {

// ── Estado ────────────────────────────────────────────────────────────────────
const s = {
    cache:     null,   // { vistos, pendientes, likes }
    loading:   false,
    tab:       'vistos',
    vista:     'cards',
    orden:     'fecha-desc',
    query:     '',
    genero:    '',
    anio:      '',
    pagina:    1,
    porPagina: 20,
    ctxMenu:   null,
}

// ── Shell ─────────────────────────────────────────────────────────────────────
const sidebar     = document.getElementById('sidebar')
const collapseBtn = document.getElementById('collapseBtn')
const menuBtn     = document.getElementById('menuBtn')

collapseBtn?.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed')
    localStorage.setItem('sidebar_collapsed', sidebar.classList.contains('collapsed') ? '1' : '0')
})
menuBtn?.addEventListener('click', () => sidebar.classList.toggle('mobile-open'))
document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && sidebar &&
        !sidebar.contains(e.target) && !menuBtn?.contains(e.target))
        sidebar.classList.remove('mobile-open')
})
if (localStorage.getItem('sidebar_collapsed') === '1') sidebar?.classList.add('collapsed')

// ── User ──────────────────────────────────────────────────────────────────────
async function loadUser() {
    try {
        const res = await fetch('/me')
        if (!res.ok) { location.href = '/login'; return }
        const data = await res.json()
        const name = data.username || data.email.split('@')[0]
        document.getElementById('userEmail').textContent = data.email
        const av = document.getElementById('userAvatar')
        if (data.foto_perfil) {
            av.style.backgroundImage = `url('${data.foto_perfil}')`
            av.style.backgroundSize  = 'cover'
            av.textContent = ''
        } else {
            av.textContent = name[0].toUpperCase()
        }
    } catch { location.href = '/login' }
}

// ── BroadcastChannel ──────────────────────────────────────────────────────────
try {
    const bc = new BroadcastChannel('ca_lista')
    bc.onmessage = (e) => { if (e.data?.tipo === 'invalidar') { s.cache = null; _fetch() } }
} catch {}

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function _fetch() {
    if (s.loading) return
    s.loading = true
    _renderLoading()
    try {
        const res  = await fetch('/lista')
        if (!res.ok) throw new Error()
        const data = await res.json()
        const lista = data.lista || []
        const likes = data.likes || []
        s.cache = {
            vistos:      lista.filter(a => a.tipo === 'visto'),
            pendientes:  lista.filter(a => a.tipo === 'pendiente'),
            likes,
            abandonados: data.abandonados || [],
        }
        _poblarFiltros()
    } catch {
        _el('tabContent').innerHTML =
            `<div class="empty-state"><div class="empty-icon">⚠️</div><p>Error al cargar la lista.</p></div>`
        s.loading = false; return
    }
    s.loading = false
    render()
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const _el  = id => document.getElementById(id)
const _esc = v  => String(v||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')

function _fechaRel(str) {
    if (!str) return ''
    try {
        const d = new Date(str), diff = Date.now() - d.getTime()
        const m = Math.floor(diff/60000)
        if (m < 1)  return 'ahora mismo'
        if (m < 60) return `hace ${m} min`
        const h = Math.floor(m/60)
        if (h < 24) return `hace ${h}h`
        const dy = Math.floor(h/24)
        if (dy < 7) return `hace ${dy} días`
        return d.toLocaleDateString('es', { day:'numeric', month:'short', year:'numeric' })
    } catch { return '' }
}

function _fechaCorta(str) {
    if (!str) return ''
    try { return new Date(str).toLocaleDateString('es', { day:'numeric', month:'short', year:'numeric' }) }
    catch { return '' }
}

function csrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
    return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

// ── Poblar filtros género y año ───────────────────────────────────────────────
function _poblarFiltros() {
    if (!s.cache) return
    const todos = [...s.cache.vistos, ...s.cache.pendientes, ...s.cache.likes]

    // Géneros únicos
    const generos = new Set()
    todos.forEach(a => {
        if (a.genres) a.genres.split(',').forEach(g => { const t = g.trim(); if (t) generos.add(t) })
    })
    const gSel = _el('mlGeneroSelect')
    if (gSel) {
        gSel.innerHTML = '<option value="">Género</option>' +
            [...generos].sort().map(g => `<option value="${_esc(g)}">${_esc(g)}</option>`).join('')
    }

    // Años únicos (de agregado_en o start_date)
    const anios = new Set()
    todos.forEach(a => {
        const d = a.agregado_en || a.start_date
        if (d) { try { anios.add(new Date(d).getFullYear()) } catch {} }
    })
    const aSel = _el('mlAnioSelect')
    if (aSel) {
        aSel.innerHTML = '<option value="">Año</option>' +
            [...anios].sort((a,b) => b-a).map(y => `<option value="${y}">${y}</option>`).join('')
    }
}

// ── Datos filtrados ───────────────────────────────────────────────────────────
function _datos() {
    if (!s.cache) return []
    const src = { vistos: s.cache.vistos, pendientes: s.cache.pendientes, likes: s.cache.likes, abandonados: s.cache.abandonados }[s.tab] || []
    let datos = [...src]

    // Búsqueda
    if (s.query) {
        const q = s.query.toLowerCase()
        datos = datos.filter(a => (a.titulo||'').toLowerCase().includes(q))
    }

    // Filtro género
    if (s.genero) {
        datos = datos.filter(a => (a.genres||'').split(',').map(g=>g.trim()).includes(s.genero))
    }

    // Filtro año
    if (s.anio) {
        datos = datos.filter(a => {
            const d = a.agregado_en || a.start_date
            if (!d) return false
            try { return new Date(d).getFullYear() === parseInt(s.anio) } catch { return false }
        })
    }

    // Orden
    switch (s.orden) {
        case 'fecha-asc':   datos.sort((a,b) => new Date(a.agregado_en||0) - new Date(b.agregado_en||0)); break
        case 'titulo-az':   datos.sort((a,b) => (a.titulo||'').localeCompare(b.titulo||'','es'));          break
        case 'titulo-za':   datos.sort((a,b) => (b.titulo||'').localeCompare(a.titulo||'','es'));          break
        case 'rating-desc': datos.sort((a,b) => (b.rating||0) - (a.rating||0));                           break
        default:            datos.sort((a,b) => new Date(b.agregado_en||0) - new Date(a.agregado_en||0))
    }
    return datos
}

// ── Render principal ──────────────────────────────────────────────────────────
function render() {
    _actualizarTabs()

    if (s.tab === 'historial') {
        _el('mlFiltros')?.style.setProperty('display', 'none')
        _el('mlVistaBtns')?.style.setProperty('display', 'none')
        _renderHistorial()
        return
    }

    _el('mlFiltros')?.style.removeProperty('display')
    _el('mlVistaBtns')?.style.removeProperty('display')

    const datos     = _datos()
    const total     = datos.length
    const totalPags = Math.max(1, Math.ceil(total / s.porPagina))
    if (s.pagina > totalPags) s.pagina = totalPags
    const pagina = datos.slice((s.pagina-1)*s.porPagina, s.pagina*s.porPagina)
    const c = _el('tabContent')
    if (!c) return

    if (!total) { c.innerHTML = _htmlVacio(); return }

    let html = s.vista === 'cards'
        ? `<div class="lista-grid">${pagina.map(a => _htmlCard(a)).join('')}</div>`
        : `<div class="lista-rows">${pagina.map((a,i) => _htmlRow(a, (s.pagina-1)*s.porPagina+i)).join('')}</div>`

    html += _htmlPaginacion(s.pagina, totalPags, total)
    c.innerHTML = html
    _bindCards(c)
}

// ── Historial ─────────────────────────────────────────────────────────────────
// Estado historial (paginación por mes + filtro)
const hs = { mesFiltro: '', pags: {} }  // pags: { [mesKey]: pagina }
const HIST_POR_PAG = 20

function _renderHistorial() {
    const c = _el('tabContent')
    if (!c) return
    if (!s.cache) { c.innerHTML = ''; return }

    const todos = [...s.cache.vistos]
        .filter(a => a.agregado_en)
        .sort((a,b) => new Date(b.agregado_en) - new Date(a.agregado_en))

    if (!todos.length) {
        c.innerHTML = `<div class="empty-state"><div class="empty-icon">📅</div><p>No hay historial todavía.</p><span>Marca animes como vistos para verlos aquí.</span></div>`
        return
    }

    // Agrupar por mes/año
    const grupos = {}
    todos.forEach(a => {
        try {
            const d   = new Date(a.agregado_en)
            const key = d.toLocaleDateString('es', { month:'long', year:'numeric' })
            if (!grupos[key]) grupos[key] = []
            grupos[key].push(a)
        } catch {}
    })
    const meses = Object.keys(grupos)

    // Stats globales
    const totalEps  = s.cache.vistos.reduce((sum, a) => sum + (parseInt(a.episodios_vistos)||0), 0)
    const totalMins = totalEps * 24
    const horas     = Math.floor(totalMins / 60)
    const mins      = totalMins % 60

    // Filtro de mes
    const mesFiltroOpts = meses.map(m =>
        `<option value="${m}" ${hs.mesFiltro===m?'selected':''}>${m.charAt(0).toUpperCase()+m.slice(1)}</option>`
    ).join('')

    let html = `
    <div class="hist-summary">
        <div class="hist-stat"><span class="hist-stat-num">${s.cache.vistos.length}</span><span class="hist-stat-label">Animes vistos</span></div>
        <div class="hist-stat"><span class="hist-stat-num">${totalEps}</span><span class="hist-stat-label">Episodios</span></div>
        <div class="hist-stat"><span class="hist-stat-num">${horas}h${mins > 0 ? ` ${mins}m` : ''}</span><span class="hist-stat-label">Tiempo viendo</span></div>
    </div>
    <div class="hist-filtro-mes">
        <select id="histMesFiltro" class="hist-mes-select">
            <option value="">Todos los meses</option>
            ${mesFiltroOpts}
        </select>
    </div>
    <div class="hist-timeline">`

    const gruposFiltrados = hs.mesFiltro ? { [hs.mesFiltro]: grupos[hs.mesFiltro] || [] } : grupos

    for (const [mes, animes] of Object.entries(gruposFiltrados)) {
        const pag     = hs.pags[mes] || 1
        const total   = animes.length
        const totalPags = Math.ceil(total / HIST_POR_PAG)
        const slice   = animes.slice((pag-1)*HIST_POR_PAG, pag*HIST_POR_PAG)

        html += `
        <div class="hist-grupo" data-mes="${mes}">
            <div class="hist-mes-header">
                <span class="hist-mes-label">${mes.charAt(0).toUpperCase()+mes.slice(1)}</span>
                <span class="hist-mes-count">${total} anime${total !== 1 ? 's' : ''}</span>
            </div>
            <div class="hist-items">`

        slice.forEach(a => {
            const epsV = parseInt(a.episodios_vistos)||0
            const epsTxt = epsV ? `${epsV} eps · ` : ''
            const hTxt   = epsV ? `~${Math.round(epsV*24/60*10)/10}h` : ''
            html += `
            <div class="hist-item" data-ml-id="${a.id}" style="cursor:pointer">
                <img class="hist-poster" src="${_esc(a.poster_url||'')}" alt="${_esc(a.titulo)}" loading="lazy">
                <div class="hist-info">
                    <span class="hist-titulo">${_esc(a.titulo||'Sin título')}</span>
                    <span class="hist-meta">${epsTxt}${hTxt}</span>
                </div>
                <div class="hist-right">
                    ${a.rating ? `<span class="hist-rating">★ ${a.rating}</span>` : ''}
                    <span class="hist-fecha">${_fechaCorta(a.agregado_en)}</span>
                </div>
            </div>`
        })

        html += `</div>`

        // Paginación numérica del mes
        if (totalPags > 1) {
            html += `<div class="hist-paginacion" data-mes="${mes}">`
            // Prev
            html += `<button class="hist-pag-btn ${pag===1?'disabled':''}" data-mes="${mes}" data-pag="${pag-1}" ${pag===1?'disabled':''}>‹</button>`
            // Números
            for (let i=1; i<=totalPags; i++) {
                if (totalPags > 7 && Math.abs(i-pag) > 2 && i !== 1 && i !== totalPags) {
                    if (i === 2 || i === totalPags-1) { html += `<span class="hist-pag-ellipsis">…</span>`; continue }
                    continue
                }
                html += `<button class="hist-pag-btn ${i===pag?'active':''}" data-mes="${mes}" data-pag="${i}">${i}</button>`
            }
            // Next
            html += `<button class="hist-pag-btn ${pag===totalPags?'disabled':''}" data-mes="${mes}" data-pag="${pag+1}" ${pag===totalPags?'disabled':''}>›</button>`
            html += `</div>`
        }

        html += `</div>`
    }
    html += `</div>`
    c.innerHTML = html

    // Listeners
    c.querySelectorAll('.hist-item[data-ml-id]').forEach(el => {
        el.addEventListener('click', () => location.href = `/mi-lista/anime/${el.dataset.mlId}`)
    })
    const selMes = document.getElementById('histMesFiltro')
    if (selMes) selMes.addEventListener('change', () => { hs.mesFiltro = selMes.value; hs.pags = {}; _renderHistorial() })
    c.querySelectorAll('.hist-pag-btn:not(.disabled)').forEach(btn => {
        btn.addEventListener('click', () => {
            hs.pags[btn.dataset.mes] = parseInt(btn.dataset.pag)
            _renderHistorial()
        })
    })
}

function _renderLoading() {
    const c = _el('tabContent')
    if (c) c.innerHTML = `<div class="lista-grid">${Array.from({length:8},()=>
        `<div class="lista-card"><div class="lista-card-cover skeleton" style="position:absolute;inset:0;filter:none;border-radius:10px"></div></div>`
    ).join('')}</div>`
}

// ── HTML cards / rows ─────────────────────────────────────────────────────────
function _badge(tipo) {
    return tipo === 'visto'      ? '<span class="lista-badge-tipo visto">✓ Visto</span>'
         : tipo === 'pendiente'  ? '<span class="lista-badge-tipo pendiente">⏳ Pendiente</span>'
         : tipo === 'abandonado' ? '<span class="lista-badge-tipo abandonado">🚫 Abandonado</span>'
         : '<span class="lista-badge-tipo like">❤ Me gusta</span>'
}

function _htmlCard(a) {
    return `
    <div class="lista-card" data-ml-id="${a.id}" data-ml-tipo="${a.tipo||''}">
        <div class="lista-card-cover" style="background-image:url('${_esc(a.cover_url||a.poster_url||'')}')"></div>
        <button class="ml-ctx-trigger" title="Opciones">⋯</button>
        <img class="lista-card-poster" src="${_esc(a.poster_url||'')}" alt="${_esc(a.titulo)}" loading="lazy">
        <div class="lista-card-info">
            <div class="lista-card-title">${_esc(a.titulo||'Sin título')}</div>
            <div class="lista-card-meta">
                ${_badge(a.tipo)}
                ${a.rating ? `<span class="lista-card-rating">★ ${a.rating}</span>` : ''}
                ${a.agregado_en ? `<span class="lista-card-fecha">${_fechaRel(a.agregado_en)}</span>` : ''}
            </div>
        </div>
    </div>`
}

function _htmlRow(a, idx) {
    return `
    <div class="lista-row" data-ml-id="${a.id}" data-ml-tipo="${a.tipo||''}">
        <span class="lista-row-num">${idx+1}</span>
        <img class="lista-row-poster" src="${_esc(a.poster_url||'')}" alt="${_esc(a.titulo)}" loading="lazy">
        <div class="lista-row-info">
            <span class="lista-row-titulo">${_esc(a.titulo||'Sin título')}</span>
            <span class="lista-row-meta">${a.episodios ? a.episodios+' eps' : ''}${a.genres ? ' · '+a.genres : ''}</span>
        </div>
        <div class="lista-row-right">
            ${_badge(a.tipo)}
            ${a.rating ? `<span class="lista-row-rating">★ ${a.rating}</span>` : ''}
            <span class="lista-row-fecha">${_fechaRel(a.agregado_en)}</span>
        </div>
        <button class="ml-ctx-trigger" title="Opciones">⋯</button>
    </div>`
}

function _htmlVacio() {
    if (s.query || s.genero || s.anio)
        return `<div class="empty-state"><div class="empty-icon">🔍</div><p>Sin resultados para los filtros aplicados.</p><span>Prueba cambiando la búsqueda o los filtros.</span></div>`
    const m = {
        vistos:      ['👁️','Aún no has marcado ningún anime como visto.','Explora tendencias y márcalos desde la ficha del anime.'],
        pendientes:  ['⏳','No tienes animes pendientes.','Agrega animes a tu lista de pendientes desde su ficha.'],
        likes:       ['❤️','No has dado me gusta a ningún anime todavía.','Pulsa el corazón en la ficha de cualquier anime.'],
        abandonados: ['🚫','No has abandonado ningún anime.','Puedes marcar un anime como abandonado desde su ficha cuando está en pendientes.'],
    }
    const [icon,title,sub] = m[s.tab]||m.vistos
    return `<div class="empty-state"><div class="empty-icon">${icon}</div><p>${title}</p><span>${sub}</span></div>`
}

function _htmlPaginacion(actual, total, items) {
    if (total <= 1) return ''
    const pp = s.porPagina, ini = (actual-1)*pp+1, fin = Math.min(actual*pp, items)
    const rango = new Set([1,total,actual,actual-1,actual+1].filter(p=>p>=1&&p<=total))
    const sorted = [...rango].sort((a,b)=>a-b)
    let prev=0, btns=[]
    for (const p of sorted) {
        if (p-prev>1) btns.push(`<span class="pag-ellipsis">…</span>`)
        btns.push(`<button class="pag-btn${p===actual?' active':''}" data-pag="${p}">${p}</button>`)
        prev=p
    }
    return `<div class="ml-paginacion">
        <span class="pag-info">${ini}–${fin} de ${items}</span>
        <div class="pag-btns">
            <button class="pag-btn pag-arrow" data-pag="${actual-1}" ${actual<=1?'disabled':''}>‹</button>
            ${btns.join('')}
            <button class="pag-btn pag-arrow" data-pag="${actual+1}" ${actual>=total?'disabled':''}>›</button>
        </div>
    </div>`
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function _actualizarTabs() {
    if (!s.cache) return
    const counts = { vistos: s.cache.vistos.length, pendientes: s.cache.pendientes.length, likes: s.cache.likes.length, abandonados: s.cache.abandonados.length }
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
        el.classList.toggle('active', key === s.tab)
    })
}

// ── Bind cards ────────────────────────────────────────────────────────────────
function _bindCards(c) {
    c.querySelectorAll('[data-ml-id]').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.closest('.ml-ctx-trigger')) return
            location.href = `/mi-lista/anime/${el.dataset.mlId}`
        })
        el.querySelector('.ml-ctx-trigger')?.addEventListener('click', (e) => {
            e.stopPropagation()
            _abrirCtx(e, el.dataset.mlId, el.dataset.mlTipo)
        })
        el.addEventListener('contextmenu', (e) => { e.preventDefault(); _abrirCtx(e, el.dataset.mlId, el.dataset.mlTipo) })
    })
    c.querySelectorAll('[data-pag]').forEach(btn => {
        btn.addEventListener('click', () => {
            s.pagina = parseInt(btn.dataset.pag)
            render()
            document.querySelector('.content')?.scrollTo(0,0)
        })
    })
}

// ── Ctx menú ──────────────────────────────────────────────────────────────────
function _findEnCache(id) {
    if (!s.cache) return null
    return [...s.cache.vistos,...s.cache.pendientes,...s.cache.likes].find(a=>String(a.id)===String(id))||null
}

function _abrirCtx(e, animeId, tipoActual) {
    _cerrarCtx()
    const opciones = []
    if (tipoActual !== 'visto')     opciones.push({ label:'✓ Mover a Vistos',     fn:()=>_mover(animeId,'visto') })
    if (tipoActual !== 'pendiente') opciones.push({ label:'⏳ Mover a Pendientes', fn:()=>_mover(animeId,'pendiente') })
    opciones.push({ label:'✏️ Editar entrada',    fn:()=>location.href=`/mi-lista/anime/${animeId}` })
    opciones.push({ label:'↗ Ver ficha',          fn:()=>location.href=`/dashboard/anime/${animeId}` })
    opciones.push({ label:'🗑 Eliminar de lista', fn:()=>_eliminar(animeId), danger:true })

    const menu = document.createElement('div')
    menu.className = 'ml-ctx-menu'
    menu.innerHTML = opciones.map(o=>`<button class="ml-ctx-item${o.danger?' danger':''}">${o.label}</button>`).join('')
    document.body.appendChild(menu)

    let x = e.pageX||e.clientX, y = e.pageY||e.clientY
    if (x+200 > window.innerWidth) x = window.innerWidth-206
    menu.style.left = x+'px'; menu.style.top = y+'px'
    requestAnimationFrame(()=>{
        if (y+menu.offsetHeight+20 > window.innerHeight) menu.style.top=(y-menu.offsetHeight-8)+'px'
    })
    menu.querySelectorAll('.ml-ctx-item').forEach((btn,i)=>{
        btn.addEventListener('click', (ev)=>{ ev.stopPropagation(); _cerrarCtx(); opciones[i].fn() })
    })
    s.ctxMenu = menu
    setTimeout(()=>document.addEventListener('click',_cerrarCtx,{once:true}),10)
}

function _cerrarCtx() { if (s.ctxMenu) { s.ctxMenu.remove(); s.ctxMenu=null } }

// ── Acciones ──────────────────────────────────────────────────────────────────
async function _mover(animeId, nuevoTipo) {
    try {
        const res = await fetch('/lista/agregar', {
            method:'POST', headers:{'Content-Type':'application/json',...csrf()},
            body: JSON.stringify({anime_id:animeId, tipo:nuevoTipo})
        })
        if (!res.ok) return
        const anime = _findEnCache(animeId)
        if (!anime || !s.cache) return
        s.cache.vistos     = s.cache.vistos.filter(a=>String(a.id)!==String(animeId))
        s.cache.pendientes = s.cache.pendientes.filter(a=>String(a.id)!==String(animeId))
        const upd = {...anime, tipo:nuevoTipo, agregado_en:new Date().toISOString()}
        if (nuevoTipo==='visto')     s.cache.vistos.unshift(upd)
        if (nuevoTipo==='pendiente') s.cache.pendientes.unshift(upd)
        render()
    } catch {}
}

async function _eliminar(animeId) {
    try {
        const res = await fetch('/lista/eliminar', {
            method:'POST', headers:{'Content-Type':'application/json',...csrf()},
            body: JSON.stringify({anime_id:animeId})
        })
        if (!res.ok || !s.cache) return
        s.cache.vistos     = s.cache.vistos.filter(a=>String(a.id)!==String(animeId))
        s.cache.pendientes = s.cache.pendientes.filter(a=>String(a.id)!==String(animeId))
        s.cache.likes      = s.cache.likes.filter(a=>String(a.id)!==String(animeId))
        render()
    } catch {}
}

// ── Controles ─────────────────────────────────────────────────────────────────
function _bindControls() {
    const on = (id,fn) => _el(id)?.addEventListener('click', fn)

    on('mlTabVistos',      ()=>{ s.tab='vistos';      s.pagina=1; render() })
    on('mlTabPendientes',  ()=>{ s.tab='pendientes';  s.pagina=1; render() })
    on('mlTabLikes',       ()=>{ s.tab='likes';       s.pagina=1; render() })
    on('mlTabAbandonados', ()=>{ s.tab='abandonados'; s.pagina=1; render() })
    on('mlTabHistorial',   ()=>{ s.tab='historial';   s.pagina=1; render() })

    on('mlBtnCards', ()=>{ s.vista='cards'; _el('mlBtnCards')?.classList.add('active'); _el('mlBtnFilas')?.classList.remove('active'); render() })
    on('mlBtnFilas', ()=>{ s.vista='filas'; _el('mlBtnFilas')?.classList.add('active'); _el('mlBtnCards')?.classList.remove('active'); render() })

    _el('mlOrdenSelect')?.addEventListener('change', e=>{ s.orden=e.target.value; s.pagina=1; render() })
    _el('mlGeneroSelect')?.addEventListener('change', e=>{ s.genero=e.target.value; s.pagina=1; render() })
    _el('mlAnioSelect')?.addEventListener('change',   e=>{ s.anio=e.target.value;   s.pagina=1; render() })

    let timer=null
    _el('mlSearch')?.addEventListener('input', e=>{
        clearTimeout(timer)
        timer = setTimeout(()=>{ s.query=e.target.value; s.pagina=1; render() }, 200)
    })
    on('mlSearchClear', ()=>{ const inp=_el('mlSearch'); if(inp)inp.value=''; s.query=''; s.pagina=1; render(); _el('mlSearch')?.focus() })
}

// ── CSS historial (inyectado dinámicamente) ───────────────────────────────────
function _injectStyles() {
    const style = document.createElement('style')
    style.textContent = `
    .hist-summary {
        display: flex; gap: 24px; padding: 20px 0 24px;
        border-bottom: 1px solid var(--border); margin-bottom: 24px; flex-wrap: wrap;
    }
    .hist-stat { display: flex; flex-direction: column; gap: 2px; }
    .hist-stat-num   { font-size: 1.6rem; font-weight: 700; color: var(--accent); line-height:1; }
    .hist-stat-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing:.05em; }

    .hist-timeline { display: flex; flex-direction: column; gap: 32px; }
    .hist-grupo {}
    .hist-mes-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border);
    }
    .hist-mes-label { font-weight: 600; font-size: 0.9rem; text-transform: capitalize; color: var(--text); }
    .hist-mes-count { font-size: 0.75rem; color: var(--muted); }

    .hist-items { display: flex; flex-direction: column; gap: 8px; }
    .hist-item {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 12px; border-radius: 8px; background: var(--surface2);
        transition: background var(--transition);
    }
    .hist-item:hover { background: var(--surface3); }
    .hist-poster { width: 36px; height: 52px; object-fit: cover; border-radius: 4px; flex-shrink:0; }
    .hist-info   { flex: 1; display: flex; flex-direction: column; gap: 3px; min-width:0; }
    .hist-titulo { font-weight: 500; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .hist-meta   { font-size: 0.75rem; color: var(--muted); }
    .hist-right  { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink:0; }
    .hist-rating { font-size: 0.8rem; color: #f59e0b; font-weight: 600; }
    .hist-fecha  { font-size: 0.75rem; color: var(--muted); white-space: nowrap; }

    /* Filtro mes */
    .hist-filtro-mes { margin-bottom: 20px; }
    .hist-mes-select {
        background: var(--surface2); border: 1px solid var(--border); color: var(--text);
        padding: 7px 14px; border-radius: 8px; font-size: 0.85rem; cursor: pointer;
        outline: none; transition: border-color var(--transition);
    }
    .hist-mes-select:hover, .hist-mes-select:focus { border-color: var(--accent); }

    /* Paginación por mes */
    .hist-paginacion {
        display: flex; align-items: center; justify-content: center;
        gap: 4px; margin-top: 16px; flex-wrap: wrap;
    }
    .hist-pag-btn {
        min-width: 34px; height: 34px; border-radius: 6px; border: 1px solid var(--border);
        background: var(--surface2); color: var(--text); font-size: 0.85rem;
        cursor: pointer; transition: all var(--transition); padding: 0 8px;
    }
    .hist-pag-btn:hover:not(.disabled):not(.active) { border-color: var(--accent); color: var(--accent); }
    .hist-pag-btn.active { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 700; }
    .hist-pag-btn.disabled { opacity: 0.3; cursor: default; }
    .hist-pag-ellipsis { color: var(--muted); padding: 0 4px; line-height: 34px; }
    `
    document.head.appendChild(style)
}

// ── Init ──────────────────────────────────────────────────────────────────────
_injectStyles()
_bindControls()
loadUser()
_fetch()

})()
