// ── ESTADO ────────────────────────────────────────────
const state = {
    user: { email: '', username: '', miembroDesde: '', foto: null, perfil_publico: false, instagram: '', discord: '', tiktok: '' },
    lista: { visto: [], pendiente: [], abandonado: [], like: [] },
    animes: [],
    activeSection: 'inicio',
    activeTab: 'visto',
    vistaLista: 'cards',   // 'cards' | 'lista'
    sidebarCollapsed: false,
    prefs: {
        tema: 'dark',
        idioma: 'es',
        densidad: 'normal',
        perfil: 'privado',
    },
}

// ── HELPER FECHA ──────────────────────────────────────
function parseFecha(str) {
    if (!str) return null
    // Normaliza "2026-03-05 22:42:45.050153" → "2026-03-05T22:42:45"
    const clean = str.replace(' ', 'T').split('.')[0]
    const d = new Date(clean)
    return isNaN(d.getTime()) ? null : d
}

function fechaRelativa(str) {
    const d = parseFecha(str)
    if (!d) return ''
    const ahora = new Date()
    const dias  = Math.floor((ahora - d) / 86400000)
    if (dias === 0) return 'Hoy'
    if (dias === 1) return 'Ayer'
    if (dias < 30)  return `Hace ${dias} días`
    if (dias < 365) return `Hace ${Math.floor(dias/30)} mes${Math.floor(dias/30)>1?'es':''}`
    return `Hace ${Math.floor(dias/365)} año${Math.floor(dias/365)>1?'s':''}`
}

function allListUnique() {
    const items = new Map()
    ;['visto', 'pendiente'].forEach(tipo => {
        ;(state.lista[tipo] || []).forEach(anime => {
            if (!anime?.id) return
            const key = String(anime.id)
            if (!items.has(key) || tipo === 'visto') {
                items.set(key, { ...anime, tipo_origen: tipo })
            }
        })
    })
    return Array.from(items.values())
}

function getSeenList() {
    return [...(state.lista.visto || [])]
}

function animeInList(animeId, tipo) {
    return (state.lista[tipo] || []).some(a => String(a.id) === String(animeId))
}

function animeIsSeen(animeId) {
    return animeInList(animeId, 'visto')
}

function updateListCounters() {
    const vistos      = (state.lista.visto      || []).length
    const pendientes  = (state.lista.pendiente  || []).length
    const abandonados = (state.lista.abandonado || []).length
    const likes       = (state.lista.like       || []).length
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val }
    setVal('statVistos',      vistos)
    setVal('statPendientes',  pendientes)
    setVal('statAbandonados', abandonados)
    setVal('statLikes',       likes)
    setVal('expStatTotal',    vistos + pendientes)
    setVal('expStatVistos',   vistos)
    setVal('expStatPend',     pendientes)
}

function syncModalButtons(animeId) {
    document.querySelectorAll('.modal-btn').forEach(btn => {
        const tipo = btn.dataset.tipo
        const active = tipo === 'visto' ? animeIsSeen(animeId) : animeInList(animeId, tipo)
        btn.classList.toggle('active', active)
    })
}

function socialIconSVG(tipo) {
    const icons = {
        instagram: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="2.5" width="19" height="19" rx="5"></rect><path d="M16.5 7.5h.01"></path><circle cx="12" cy="12" r="4"></circle></svg>',
        discord: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057c.002.022.015.043.03.056a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>',
        tiktok: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 3c.3 1.8 1.4 3.2 3 4.1 1 .6 2 .9 3 .9v3.2c-1.5 0-3-.4-4.3-1.1v5.5c0 3.3-2.7 6-6 6s-6-2.7-6-6 2.7-6 6-6c.3 0 .7 0 1 .1v3.3c-.3-.1-.6-.2-1-.2-1.5 0-2.8 1.3-2.8 2.8S8.2 18.2 9.8 18.2s2.8-1.3 2.8-2.8V3H14z"></path></svg>',
        link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.07 0l2.83-2.83a5 5 0 1 0-7.07-7.07L11.5 4.43"></path><path d="M14 11a5 5 0 0 0-7.07 0L4.1 13.83a5 5 0 0 0 7.07 7.07L12.5 19.57"></path></svg>'
    }
    return `<span class="perfil-red-icon">${icons[tipo] || icons.link}</span>`
}

// ── SIDEBAR ───────────────────────────────────────────
const sidebar     = document.getElementById('sidebar')
const collapseBtn = document.getElementById('collapseBtn')
const menuBtn     = document.getElementById('menuBtn')

collapseBtn.addEventListener('click', () => {
    state.sidebarCollapsed = !state.sidebarCollapsed
    sidebar.classList.toggle('collapsed', state.sidebarCollapsed)
})

menuBtn.addEventListener('click', () => sidebar.classList.toggle('mobile-open'))

document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && !sidebar.contains(e.target) && !menuBtn.contains(e.target)) {
        sidebar.classList.remove('mobile-open')
    }
})

// ── NAVEGACIÓN ────────────────────────────────────────
const sections   = document.querySelectorAll('.section')
const navItems   = document.querySelectorAll('.nav-item[data-section]')
const pageTitle  = document.getElementById('pageTitle')
const userChip   = document.getElementById('userChip')

const sectionTitles = {
    'inicio':        'Inicio',
    'mi-lista':      'Mi Lista',
    'populares':     'Tendencias',
    'emision':       'En emisión',
    'estadisticas':  'Estadísticas',
    'configuracion': 'Configuración',
    'exportar':      'Exportar lista',
}

// ── ROUTER — History API ──────────────────────────────
// Convierte pathname actual en sectionId.
// /dashboard            → 'inicio'
// /dashboard/mi-lista   → 'mi-lista'
// Rutas desconocidas    → 'inicio'
function resolvePathToSection() {
    const path = window.location.pathname
    if (path === '/dashboard' || path === '/dashboard/') return 'inicio'
    const match = path.match(/^\/dashboard\/([^\/]+)\/?$/)
    if (match) {
        const seg = match[1]
        const valid = ['mi-top','populares','emision','ranking',
                       'estadisticas','configuracion','exportar']
        return valid.includes(seg) ? seg : 'inicio'
    }
    return 'inicio'
}

// Devuelve la URL canónica de una sección.
function sectionToPath(sectionId) {
    return sectionId === 'inicio' ? '/dashboard' : `/dashboard/${sectionId}`
}

function navigateTo(sectionId, pushHistory = true) {
    state.activeSection = sectionId
    sections.forEach(s => s.classList.remove('active'))
    navItems.forEach(n => n.classList.remove('active'))

    const section = document.getElementById('section-' + sectionId)
    if (section) section.classList.add('active')

    const navItem = document.querySelector(`.nav-item[data-section="${sectionId}"]`)
    if (navItem) navItem.classList.add('active')

    pageTitle.textContent = sectionTitles[sectionId] || sectionId

    // Actualizar URL sin recargar
    if (pushHistory) {
        history.pushState({ section: sectionId }, '', sectionToPath(sectionId))
    }

    if (sectionId === 'estadisticas') renderStats()
    if (sectionId === 'configuracion') renderConfigForm()
    if (sectionId === 'mi-lista') { location.href = '/mi-lista'; return }
    if (sectionId === 'populares') {
        if (state.animes.length > 0) {
            renderAnimeGrid('popularGrid', state.animes)
            paginacion.popular = paginacion.popular || { offset: state.animes.length, limit: 28, agotado: state.animes.length < 28 }
            if (!paginacion.popular.agotado && !document.getElementById('wrap-popular')) {
                agregarCargarMas('popularGrid', 'popular', cargarMasPopular)
            }
        } else {
            renderSkeletons('popularGrid', 12)
            const interval = setInterval(() => {
                if (state.animes.length > 0) {
                    clearInterval(interval)
                    renderAnimeGrid('popularGrid', state.animes)
                    paginacion.popular = { offset: state.animes.length, limit: 28, agotado: state.animes.length < 28 }
                    if (!paginacion.popular.agotado) agregarCargarMas('popularGrid', 'popular', cargarMasPopular)
                }
            }, 200)
        }
    }
    if (sectionId === 'ranking')  loadRanking()
    if (sectionId === 'mi-top')   loadMiTop5()
    if (sectionId === 'exportar') loadExportar()
    if (sectionId === 'emision') {
        const grid = document.getElementById('emisionFullGrid')
        if (!grid) return
        // Solo cargar si está vacío
        if (grid.children.length === 0) {
            paginacion.emisionFull = { offset: 0, limit: 28, agotado: false }
            renderSkeletons('emisionFullGrid', 12)
            fetch('/animes/emision?limit=28&offset=0')
                .then(r => r.json())
                .then(data => {
                    const items = data.resultados || []
                    renderAnimeGrid('emisionFullGrid', items)
                    paginacion.emisionFull.offset = items.length
                    if (items.length >= 28) agregarCargarMas('emisionFullGrid', 'emisionFull', cargarMasEmisionFull)
                })
                .catch(() => {
                    grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><p>Error al cargar.</p></div>'
                })
        }
    }
    if (window.innerWidth <= 768) sidebar.classList.remove('mobile-open')
}

navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        const href = item.getAttribute('href')
        // Si el link tiene href que no es /dashboard/*, dejar navegar normalmente
        if (href && !href.startsWith('/dashboard')) return
        e.preventDefault()
        navigateTo(item.dataset.section)
    })
})

// Botón atrás/adelante del navegador
window.addEventListener('popstate', (e) => {
    const section = e.state?.section || resolvePathToSection()
    navigateTo(section, false)
})

document.querySelectorAll('.see-all[data-section]').forEach(link => {
    link.addEventListener('click', (e) => {
        const href = link.getAttribute('href')
        if (href && !href.startsWith('/dashboard')) return
        e.preventDefault()
        navigateTo(link.dataset.section)
    })
})

// ── VER TODO ─────────────────────────────────────────
const btnVerTodoTrending = document.getElementById('btnVerTodoTrending')
if (btnVerTodoTrending) {
    btnVerTodoTrending.addEventListener('click', () => navigateTo('populares'))
}

const btnVerTodoEmision = document.getElementById('btnVerTodoEmision')
if (btnVerTodoEmision) {
    btnVerTodoEmision.addEventListener('click', () => navigateTo('emision'))
}

userChip.addEventListener('click', () => navigateTo('configuracion'))
// ══════════════════════════════════════════════════════════════════

// ── MI LISTA — cargada como módulo externo ────────────────────────
// script.js solo orquesta; la lógica vive en sections/mi-lista.js
function _cargarMiLista() {
    if (window.MiLista) {
        // Módulo ya cargado — solo refrescar
        window.MiLista.refresh()
        return
    }
    // Primera vez — cargar el script dinámicamente
    const sc = document.createElement('script')
    sc.src = '/static/pages/dashboard/sections/mi-lista.js'
    sc.onerror = () => {
        const c = document.getElementById('tabContent')
        if (c) c.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><p>Error al cargar la sección.</p></div>'
    }
    document.head.appendChild(sc)
}

// Exponer _dashState para que mi-lista.js pueda sincronizar contadores
window._dashState = state


// ── ANIME CARD ────────────────────────────────────────
function animeCardHTML(anime) {
    // Soporta tanto formato Kitsu API como formato BD
    const poster = anime.poster_url || anime.attributes?.posterImage?.medium || ''
    const title  = anime.titulo || anime.attributes?.canonicalTitle || 'Sin título'
    const rating = anime.rating || (anime.attributes?.averageRating
        ? (parseFloat(anime.attributes.averageRating) / 10).toFixed(1)
        : null)
    return `
        <div class="anime-card">
            <img src="${poster}" alt="${title}" loading="lazy">
            <div class="card-info">
                <div class="card-title">${title}</div>
                ${rating ? `<div class="card-rating">★ ${rating}</div>` : ''}
            </div>
        </div>`
}

function animeCardListaHTML(anime, tipo) {
    const poster = anime.poster_url || ''
    const title  = anime.titulo || 'Sin título'
    const rating = anime.rating || null
    const fecha  = parseFecha(anime.agregado_en)
        ? parseFecha(anime.agregado_en).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
        : null
    return `
        <div class="anime-card" data-id="${anime.id}" style="cursor:pointer">
            <img src="${poster}" alt="${title}" loading="lazy">
            <div class="card-info">
                <div class="card-title">${title}</div>
                ${rating ? `<div class="card-rating">★ ${rating}</div>` : ''}
                ${fecha ? `<div class="card-fecha">${fecha}</div>` : ''}
            </div>
        </div>`
}

function openModalLista(anime, tipo) {
    const tipoLabel = tipo === 'visto' ? 'Vistos' : tipo === 'pendiente' ? 'Pendientes' : 'Favoritos'
    const fecha = parseFecha(anime.agregado_en)
        ? parseFecha(anime.agregado_en).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
        : 'Fecha desconocida'

    document.getElementById('modalListaTitulo').textContent    = anime.titulo || ''
    document.getElementById('modalListaAlt').textContent       = anime.titulo_alternativo || ''
    document.getElementById('modalListaPoster').src            = anime.poster_url || ''
    document.getElementById('modalListaFecha').textContent     = `Agregado el ${fecha}`
    document.getElementById('modalListaTipo').textContent      = `📂 ${tipoLabel}`
    const sinopsisListaEl = document.getElementById('modalListaSinopsis')
    sinopsisListaEl.textContent = anime.sinopsis_es || anime.sinopsis || 'Sin sinopsis disponible.'
    document.getElementById('modalListaFeedback').textContent  = ''
    document.getElementById('modalListaFeedback').className    = 'modal-feedback'

    const cover = document.getElementById('modalListaCover')
    cover.style.backgroundImage = anime.cover_url ? `url(${anime.cover_url})` : 'none'

    const meta = document.getElementById('modalListaMeta')
    meta.innerHTML = [
        anime.rating    ? `<span class="modal-badge rating">★ ${anime.rating}</span>` : '',
        anime.episodios ? `<span class="modal-badge eps">${anime.episodios} eps</span>` : '',
        anime.estado    ? `<span class="modal-badge estado">${anime.estado === 'finished' ? 'Finalizado' : 'En emisión'}</span>` : '',
    ].join('')

    // Guardar referencia para el botón eliminar
    document.getElementById('btnEliminarLista').dataset.animeId = anime.id
    document.getElementById('btnEliminarLista').dataset.tipo    = tipo

    document.getElementById('modalListaOverlay').style.display = 'flex'
    document.body.style.overflow = 'hidden'
}

document.getElementById('modalListaClose').addEventListener('click', closeModalLista)
document.getElementById('modalListaOverlay').addEventListener('click', (e) => {
    if (e.target === document.getElementById('modalListaOverlay')) closeModalLista()
})

function closeModalLista() {
    document.getElementById('modalListaOverlay').style.display = 'none'
    document.body.style.overflow = ''
}

document.getElementById('btnEliminarLista').addEventListener('click', async () => {
    const btn     = document.getElementById('btnEliminarLista')
    const animeId = btn.dataset.animeId
    const tipo    = btn.dataset.tipo
    const feedback = document.getElementById('modalListaFeedback')

    btn.disabled = true
    btn.textContent = 'Eliminando...'

    try {
        const res  = await fetch('/lista/eliminar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ anime_id: animeId })
        })
        const data = await res.json()
        if (!res.ok) {
            feedback.textContent = data.error || 'Error al eliminar.'
            feedback.className   = 'modal-feedback error'
            return
        }

        // Actualizar estado local
        state.lista[tipo] = state.lista[tipo].filter(a => a.id !== animeId)

        // Actualizar contadores
        updateListCounters()

        closeModalLista()
        renderTabContent(tipo)

    } catch(e) {
        feedback.textContent = 'Error de conexión.'
        feedback.className   = 'modal-feedback error'
    } finally {
        btn.disabled = false
        btn.textContent = '🗑️ Eliminar de mi lista'
    }
})

function renderAnimeGrid(containerId, animes) {
    const container = document.getElementById(containerId)
    if (!container) return
    container.innerHTML = animes.map(a => animeCardHTML(a)).join('')
    container.querySelectorAll('.anime-card').forEach((card, i) => {
        card.style.cursor = 'pointer'
        card.addEventListener('click', () => irAAnime(animes[i]))
    })
}

function renderSkeletons(containerId, count = 10) {
    const container = document.getElementById(containerId)
    if (!container) return
    container.innerHTML = Array.from({ length: count }, () => `
        <div class="anime-card">
            <div class="skeleton" style="height:200px;width:100%;border-radius:6px 6px 0 0;"></div>
            <div class="card-info">
                <div class="skeleton" style="height:12px;width:80%;margin-bottom:6px;border-radius:3px;"></div>
                <div class="skeleton" style="height:11px;width:40%;border-radius:3px;"></div>
            </div>
        </div>`).join('')
}

// ── ESTADÍSTICAS ──────────────────────────────────────
function setTextIfExists(id, value) {
    const el = document.getElementById(id)
    if (el) el.textContent = value
}

function escapeHTML(value = '') {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
}

function tiempoRelativo(fecha) {
    if (!fecha) return 'Fecha desconocida'
    const d = new Date(fecha)
    if (Number.isNaN(d.getTime())) return 'Fecha desconocida'
    const dias = Math.floor((Date.now() - d.getTime()) / 86400000)
    if (dias <= 0) return 'Hoy'
    if (dias === 1) return 'Ayer'
    if (dias < 30) return `Hace ${dias} días`
    if (dias < 365) return `Hace ${Math.floor(dias / 30)} meses`
    return `Hace ${Math.floor(dias / 365)} años`
}

function tipoListaLabel(tipo) {
    if (tipo === 'visto') return '✓ Visto'
    if (tipo === 'pendiente') return '⏳ Pendiente'
    return '❤️ Favorito'
}

function colorGenero(index) {
    const colores = ['var(--accent)', '#60a5fa', '#f472b6', '#34d399', '#fbbf24']
    return colores[index % colores.length]
}

function renderActividadChart(items) {
    const canvas = document.getElementById('canvasActividad')
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr        = window.devicePixelRatio || 1
    const cssWidth   = Math.max(canvas.parentElement?.clientWidth || 600, 300)
    const cssHeight  = 220

    canvas.width  = Math.floor(cssWidth  * dpr)
    canvas.height = Math.floor(cssHeight * dpr)
    canvas.style.width  = cssWidth  + 'px'
    canvas.style.height = cssHeight + 'px'
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, cssWidth, cssHeight)

    // Últimos 12 meses
    const ahora = new Date()
    const meses = []
    for (let i = 11; i >= 0; i--) {
        const d = new Date(ahora.getFullYear(), ahora.getMonth() - i, 1)
        meses.push({
            key:   `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`,
            label: d.toLocaleDateString('es-ES', { month:'short', year:'2-digit' }).replace(' ','\n'),
            value: 0,
        })
    }
    items.forEach(item => {
        if (!item.agregado_en) return
        const d = parseFecha(item.agregado_en)
        if (isNaN(d)) return
        const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`
        const m = meses.find(m => m.key === key)
        if (m) m.value++
    })

    const maxVal = Math.max(...meses.map(m => m.value), 1)
    const pad    = { top: 24, right: 20, bottom: 44, left: 40 }
    const W      = cssWidth  - pad.left - pad.right
    const H      = cssHeight - pad.top  - pad.bottom
    const N      = meses.length
    const stepX  = W / (N - 1)

    // ── Grid horizontal
    const yTicks = 4
    for (let i = 0; i <= yTicks; i++) {
        const y   = pad.top + (H / yTicks) * i
        const val = Math.round(maxVal - (maxVal / yTicks) * i)
        ctx.strokeStyle = 'rgba(255,255,255,0.07)'
        ctx.lineWidth   = 1
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + W, y); ctx.stroke()
        ctx.fillStyle  = 'rgba(255,255,255,0.28)'
        ctx.font       = `11px "DM Sans",sans-serif`
        ctx.textAlign  = 'right'
        ctx.textBaseline = 'middle'
        ctx.fillText(val, pad.left - 6, y)
    }

    // ── Grid vertical sutil
    meses.forEach((m, i) => {
        const x = pad.left + i * stepX
        ctx.strokeStyle = 'rgba(255,255,255,0.04)'
        ctx.lineWidth   = 1
        ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + H); ctx.stroke()
    })

    // ── Coordenadas de puntos
    const pts = meses.map((m, i) => ({
        x: pad.left + i * stepX,
        y: pad.top + H - (m.value / maxVal) * H,
        v: m.value,
    }))

    // ── Área rellena bajo la línea
    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + H)
    grad.addColorStop(0, 'rgba(249,115,22,0.30)')
    grad.addColorStop(1, 'rgba(249,115,22,0)')
    ctx.beginPath()
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y))
    ctx.lineTo(pts[N-1].x, pad.top + H)
    ctx.lineTo(pts[0].x,   pad.top + H)
    ctx.closePath()
    ctx.fillStyle = grad
    ctx.fill()

    // ── Línea principal naranja
    ctx.beginPath()
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y))
    ctx.strokeStyle = '#f97316'
    ctx.lineWidth   = 2.5
    ctx.lineJoin    = 'round'
    ctx.stroke()

    // ── Puntos + valor encima
    pts.forEach(p => {
        // punto blanco con borde naranja
        ctx.beginPath()
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2)
        ctx.fillStyle   = p.v > 0 ? '#fff' : 'rgba(255,255,255,0.2)'
        ctx.fill()
        ctx.strokeStyle = '#f97316'
        ctx.lineWidth   = 2
        ctx.stroke()

        // valor encima del punto solo si > 0
        if (p.v > 0) {
            ctx.fillStyle    = '#fff'
            ctx.font         = `bold 11px "DM Sans",sans-serif`
            ctx.textAlign    = 'center'
            ctx.textBaseline = 'bottom'
            ctx.fillText(p.v, p.x, p.y - 8)
        }
    })

    // ── Etiquetas eje X (cada 2 meses para no saturar)
    ctx.fillStyle    = 'rgba(255,255,255,0.35)'
    ctx.font         = `10px "DM Sans",sans-serif`
    ctx.textAlign    = 'center'
    ctx.textBaseline = 'top'
    meses.forEach((m, i) => {
        if (i % 2 !== 0) return
        const x = pad.left + i * stepX
        const parts = m.label.split('\n')
        ctx.fillText(parts[0], x, pad.top + H + 8)
        if (parts[1]) ctx.fillText(parts[1], x, pad.top + H + 20)
    })
}

function renderStats() {
    const v = state.lista.visto.length
    const p = state.lista.pendiente.length
    const total = new Set(allListUnique().map(a => String(a.id))).size

    setTextIfExists('statTotalCard', total)
    setTextIfExists('statVistosCard', v)
    setTextIfExists('statPendCard', p)
    setTextIfExists('statMiembro', state.user.miembroDesde || '—')

    const todos = [
        ...state.lista.visto.map(a => ({ ...a, _tipoLista: 'visto' })),
        ...state.lista.pendiente.map(a => ({ ...a, _tipoLista: 'pendiente' })),
    ]

    renderActividadChart(todos)

    const generosWrap = document.getElementById('statsGeneros')
    if (generosWrap) {
        const generosCount = {}
        todos.forEach(anime => {
            const raw = anime.generos || anime.genero || anime.genre || anime.categories || []
            const lista = Array.isArray(raw)
                ? raw
                : String(raw || '')
                    .split(',')
                    .map(g => g.trim())
                    .filter(Boolean)

            lista.forEach(genero => {
                const clave = genero.trim()
                if (!clave) return
                generosCount[clave] = (generosCount[clave] || 0) + 1
            })
        })

        const topGeneros = Object.entries(generosCount)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)

        if (!topGeneros.length) {
            generosWrap.innerHTML = '<div class="stats-empty">Todavía no hay géneros suficientes para mostrar.</div>'
        } else {
            const maxGenero = topGeneros[0][1]
            generosWrap.innerHTML = topGeneros.map(([genero, cantidad], index) => `
                <div class="stats-genero-row">
                    <span class="stats-genero-label">${escapeHTML(genero)}</span>
                    <div class="stats-genero-track">
                        <div class="stats-genero-bar" style="width:${(cantidad / maxGenero) * 100}%;background:${colorGenero(index)}"></div>
                    </div>
                    <span class="stats-genero-val">${cantidad}</span>
                </div>
            `).join('')
        }
    }

    const ultimosWrap = document.getElementById('statsUltimos')
    if (ultimosWrap) {
        const ultimos = [...todos]
            .filter(a => a.agregado_en)
            .sort((a, b) => (parseFecha(b.agregado_en)||0) - (parseFecha(a.agregado_en)||0))
            .slice(0, 5)

        if (!ultimos.length) {
            ultimosWrap.innerHTML = '<div class="stats-empty">Aún no hay animes agregados en tu lista.</div>'
        } else {
            ultimosWrap.innerHTML = ultimos.map(anime => `
                <div class="stats-reciente-row" data-id="${escapeHTML(anime.id)}" data-tipo="${escapeHTML(anime._tipoLista)}">
                    <img class="stats-reciente-poster" src="${escapeHTML(anime.poster_url || '')}" alt="${escapeHTML(anime.titulo || 'Anime')}" loading="lazy">
                    <div class="stats-reciente-info">
                        <div class="stats-reciente-titulo">${escapeHTML(anime.titulo || 'Sin título')}</div>
                        <div class="stats-reciente-meta">
                            ${anime.rating ? `<span>★ ${escapeHTML(anime.rating)}</span>` : ''}
                            ${anime.episodios ? `<span>${escapeHTML(anime.episodios)} eps</span>` : ''}
                        </div>
                    </div>
                    <div class="stats-reciente-right">
                        <span class="stats-reciente-tipo">${tipoListaLabel(anime._tipoLista)}</span>
                        <span class="stats-reciente-cuando">${tiempoRelativo(anime.agregado_en)}</span>
                    </div>
                </div>
            `).join('')

            ultimosWrap.querySelectorAll('.stats-reciente-row').forEach(row => {
                row.addEventListener('click', () => {
                    const anime = ultimos.find(a => String(a.id) === row.dataset.id && a._tipoLista === row.dataset.tipo)
                    if (anime) openModalLista(anime, anime._tipoLista)
                })
            })
        }
    }
}

// ── CONFIGURACIÓN ─────────────────────────────────────
function renderConfigForm() {
    document.getElementById('inputUsername').value = state.user.username || ''
    document.getElementById('inputEmail').value    = state.user.email || ''

    // Sincronizar toggles con estado actual
    // Sincronizar perfil_publico del usuario con el toggle
    state.prefs.perfil = state.user.perfil_publico ? 'publico' : 'privado'
    syncToggleGroup('temaToggle',     state.prefs.tema)
    syncToggleGroup('densidadToggle', state.prefs.densidad)
    syncToggleGroup('perfilToggle',   state.prefs.perfil)
    actualizarPerfilHint()

    // Redes sociales
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || '' }
    setVal('inputInstagram',     state.user.instagram)
    setVal('inputDiscord',        state.user.discord)
    setVal('inputTiktok',         state.user.tiktok)

    // Foto de perfil
    const letter = document.getElementById('avatarPreviewLetter')
    const img    = document.getElementById('avatarPreviewImg')
    if (state.user.foto) {
        img.src = state.user.foto
        img.style.display = 'block'
        letter.style.display = 'none'
        document.getElementById('btnEliminarFoto').style.display = 'inline-block'
    } else {
        img.style.display = 'none'
        letter.style.display = 'block'
        letter.textContent = (state.user.username || state.user.email || '?')[0].toUpperCase()
        document.getElementById('btnEliminarFoto').style.display = 'none'
    }
}

function setFeedback(id, msg, type) {
    const el = document.getElementById(id)
    el.textContent = msg
    el.className = 'config-feedback ' + type
    if (type === 'ok') setTimeout(() => { el.textContent = ''; el.className = 'config-feedback' }, 3000)
}

// Guardar username
document.getElementById('btnSaveUsername').addEventListener('click', async () => {
    const btn = document.getElementById('btnSaveUsername')
    const val = document.getElementById('inputUsername').value.trim()
    if (!val) { setFeedback('feedbackUsername', 'El nombre no puede estar vacío.', 'error'); return }
    if (val.length < 2) { setFeedback('feedbackUsername', 'Mínimo 2 caracteres.', 'error'); return }

    btn.disabled = true
    btn.textContent = 'Guardando...'
    try {
        const res  = await fetch('/update-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: val })
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackUsername', data.error || 'Error al guardar.', 'error'); return }
        state.user.username = val
        document.getElementById('welcomeName').textContent = val.toUpperCase()
        updateTopbarName()
        setFeedback('feedbackUsername', '✓ Nombre actualizado correctamente.', 'ok')
    } catch(e) {
        setFeedback('feedbackUsername', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false
        btn.textContent = 'Guardar'
    }
})

// Guardar email — flujo con verificacion por codigo
// Paso 1: solicitar cambio → envia codigo al nuevo correo
// Paso 2: confirmar con el codigo recibido
let _pendingEmail = ''

document.getElementById('btnSaveEmail').addEventListener('click', async () => {
    const btn = document.getElementById('btnSaveEmail')
    const val = document.getElementById('inputEmail').value.trim()
    if (!val) { setFeedback('feedbackEmail', 'El correo no puede estar vacío.', 'error'); return }
    if (val === state.user.email) { setFeedback('feedbackEmail', 'Es el mismo correo actual.', 'error'); return }

    btn.disabled = true
    btn.textContent = 'Enviando...'
    try {
        const res  = await fetch('/solicitar-cambio-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: val })
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackEmail', data.error || 'Error al enviar.', 'error'); return }

        _pendingEmail = val
        // Mostrar campo de codigo inline
        setFeedback('feedbackEmail', `Código enviado a ${val}. Revisa tu bandeja.`, 'ok')
        document.getElementById('emailVerificacionWrap').style.display = 'block'
        document.getElementById('inputEmailCodigo').value = ''
        document.getElementById('inputEmailCodigo').focus()
    } catch(e) {
        setFeedback('feedbackEmail', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false
        btn.textContent = 'Guardar'
    }
})

document.getElementById('btnConfirmarEmailCodigo')?.addEventListener('click', async () => {
    const btn    = document.getElementById('btnConfirmarEmailCodigo')
    const codigo = document.getElementById('inputEmailCodigo').value.trim()
    if (!codigo) { setFeedback('feedbackEmail', 'Ingresa el código.', 'error'); return }

    btn.disabled = true
    btn.textContent = 'Verificando...'
    try {
        const res  = await fetch('/confirmar-cambio-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ codigo })
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackEmail', data.error || 'Código incorrecto.', 'error'); return }

        // Actualizar estado local
        state.user.email = _pendingEmail
        document.getElementById('userEmail').textContent = _pendingEmail
        document.getElementById('emailVerificacionWrap').style.display = 'none'
        _pendingEmail = ''
        setFeedback('feedbackEmail', '✓ Correo actualizado correctamente.', 'ok')
    } catch(e) {
        setFeedback('feedbackEmail', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false
        btn.textContent = 'Confirmar'
    }
})

// Guardar contraseña
document.getElementById('btnSavePassword').addEventListener('click', async () => {
    const btn     = document.getElementById('btnSavePassword')
    const actual  = document.getElementById('inputPasswordActual').value
    const nueva   = document.getElementById('inputPasswordNueva').value
    const confirm = document.getElementById('inputPasswordConfirm').value

    if (!actual || !nueva || !confirm) { setFeedback('feedbackPassword', 'Completa todos los campos.', 'error'); return }
    if (nueva.length < 8) { setFeedback('feedbackPassword', 'La nueva contraseña debe tener al menos 8 caracteres.', 'error'); return }
    if (nueva !== confirm) { setFeedback('feedbackPassword', 'Las contraseñas no coinciden.', 'error'); return }

    btn.disabled = true
    btn.textContent = 'Guardando...'
    try {
        const res  = await fetch('/update-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password_actual: actual, password_nueva: nueva })
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackPassword', data.error || 'Error al cambiar contraseña.', 'error'); return }
        document.getElementById('inputPasswordActual').value = ''
        document.getElementById('inputPasswordNueva').value  = ''
        document.getElementById('inputPasswordConfirm').value = ''
        setFeedback('feedbackPassword', '✓ Contraseña actualizada correctamente.', 'ok')
    } catch(e) {
        setFeedback('feedbackPassword', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false
        btn.textContent = 'Guardar'
    }
})

// Foto de perfil
const fotoInput       = document.getElementById('fotoInput')
const avatarPreview   = document.getElementById('avatarPreview')
const btnSeleccionar  = document.getElementById('btnSeleccionarFoto')
const btnEliminar     = document.getElementById('btnEliminarFoto')

btnSeleccionar.addEventListener('click', () => fotoInput.click())
avatarPreview.addEventListener('click', () => fotoInput.click())

fotoInput.addEventListener('change', async () => {
    const file = fotoInput.files[0]
    if (!file) return
    if (file.size > 2 * 1024 * 1024) { setFeedback('feedbackFoto', 'La imagen no puede superar 2MB.', 'error'); return }

    const reader = new FileReader()
    reader.onload = async (e) => {
        const base64 = e.target.result

        try {
            const res  = await fetch('/update-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ foto_perfil: base64 })
            })
            const data = await res.json()
            if (!res.ok) { setFeedback('feedbackFoto', data.error || 'Error al subir imagen.', 'error'); return }

            state.user.foto = base64
            updateAvatarUI(base64)
            btnEliminar.style.display = 'inline-block'
            setFeedback('feedbackFoto', '✓ Foto actualizada.', 'ok')
        } catch(err) {
            setFeedback('feedbackFoto', 'Error de conexión.', 'error')
        }
    }
    reader.readAsDataURL(file)
})

btnEliminar.addEventListener('click', async () => {
    try {
        const res = await fetch('/update-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ foto_perfil: null })
        })
        if (!res.ok) return
        state.user.foto = null
        updateAvatarUI(null)
        btnEliminar.style.display = 'none'
        setFeedback('feedbackFoto', '✓ Foto eliminada.', 'ok')
    } catch(e) {
        setFeedback('feedbackFoto', 'Error de conexión.', 'error')
    }
})

function updateAvatarUI(fotoBase64) {
    // Topbar avatar
    const topbarAvatar = document.getElementById('userAvatar')
    // Config preview
    const previewLetter = document.getElementById('avatarPreviewLetter')
    const previewImg    = document.getElementById('avatarPreviewImg')

    if (fotoBase64) {
        // Topbar: poner imagen dentro del div
        topbarAvatar.innerHTML = `<img src="${fotoBase64}" alt="avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`
        // Config preview
        previewImg.src = fotoBase64
        previewImg.style.display = 'block'
        previewLetter.style.display = 'none'
    } else {
        const letra = (state.user.username || state.user.email || '?')[0].toUpperCase()
        topbarAvatar.innerHTML = letra
        previewImg.style.display = 'none'
        previewLetter.style.display = 'block'
        previewLetter.textContent = letra
    }
}

function updateTopbarName() {
    const nombre = state.user.username || state.user.email.split('@')[0]
    document.getElementById('userEmail').textContent = state.user.email
}

function renderInicioExtra() {
    // ÚLTIMOS AGREGADOS
    const todosAgregados = [
        ...state.lista.visto,
        ...state.lista.pendiente,
    ].sort((a, b) => (parseFecha(b.agregado_en)||0) - (parseFecha(a.agregado_en)||0)).slice(0, 4)

    const secUltimos = document.getElementById('ultimosAgregados')
    if (todosAgregados.length > 0) {
        document.getElementById('seccionUltimos').style.display = 'block'
        secUltimos.innerHTML = todosAgregados.map(a => `
            <div class="anime-card" data-id="${a.id}" style="cursor:pointer">
                <img src="${a.poster_url || ''}" alt="${a.titulo}" loading="lazy">
                <div class="card-info">
                    <div class="card-title">${a.titulo}</div>
                    ${a.rating ? `<div class="card-rating">★ ${a.rating}</div>` : ''}
                </div>
            </div>`).join('')
        secUltimos.querySelectorAll('.anime-card').forEach((card, i) => {
            card.addEventListener('click', () => irAAnime(todosAgregados[i]))
        })
    } else {
        document.getElementById('seccionUltimos').style.display = 'none'
    }

    // PENDIENTES
    const pendientes = state.lista.pendiente.slice(0, 4)
    const secPend = document.getElementById('pendientesGrid')
    if (pendientes.length > 0) {
        document.getElementById('seccionPendientes').style.display = 'block'
        secPend.innerHTML = pendientes.map(a => `
            <div class="anime-card" data-id="${a.id}" style="cursor:pointer">
                <img src="${a.poster_url || ''}" alt="${a.titulo}" loading="lazy">
                <div class="card-info">
                    <div class="card-title">${a.titulo}</div>
                    ${a.rating ? `<div class="card-rating">★ ${a.rating}</div>` : ''}
                    <div class="card-fecha" style="color:var(--accent)">⏳ Pendiente</div>
                </div>
            </div>`).join('')
        secPend.querySelectorAll('.anime-card').forEach((card, i) => {
            card.addEventListener('click', () => irAAnime(pendientes[i]))
        })
    } else {
        document.getElementById('seccionPendientes').style.display = 'none'
    }
}

// ── CARGAR USUARIO ────────────────────────────────────
async function loadUser() {
    try {
        const res  = await fetch('/me')
        if (!res.ok) { window.location.href = '/login'; return }
        const data = await res.json()

        state.user.email          = data.email
        state.user.username       = data.username || ''
        state.user.foto           = data.foto_perfil || null
        state.user.perfil_publico = data.perfil_publico || false
        state.user.instagram      = data.instagram      || ''
        state.user.discord        = data.discord        || ''
        state.user.tiktok         = data.tiktok         || ''
        state.user.miembroDesde = data.creado_en
            ? (parseFecha(data.creado_en) || new Date()).toLocaleDateString('es-ES', { year: 'numeric', month: 'long' })
            : '—'

        const displayName = data.username || data.email.split('@')[0]
        document.getElementById('userEmail').textContent  = data.email
        document.getElementById('welcomeName').textContent = displayName.toUpperCase()

        if (data.foto_perfil) {
            updateAvatarUI(data.foto_perfil)
        } else {
            document.getElementById('userAvatar').textContent = displayName[0].toUpperCase()
        }

        if (data.lista) {
            // /me devuelve visto, pendiente, abandonado (de lista_animes)
            // pero NO los likes (tabla separada). Los cargamos en background.
            state.lista.visto      = data.lista.visto      || []
            state.lista.pendiente  = data.lista.pendiente  || []
            state.lista.abandonado = data.lista.abandonado || []
            updateListCounters()
            renderInicioExtra()
            // Cargar likes en background sin bloquear el render inicial
            _cargarLikesBackground()
        }

    } catch(e) {
        window.location.href = '/login'
    }
}

// ── CARGAR ANIMES ─────────────────────────────────────
// Estado de paginación por sección
const paginacion = {
    trending: { offset: 0, limit: 28, agotado: false },
    emision:  { offset: 0, limit: 28, agotado: false },
    genero:   { offset: 0, limit: 28, agotado: false },
}

function btnCargarMas(seccionId) {
    return `<div class="cargar-mas-wrap" id="wrap-${seccionId}">
        <button class="btn-cargar-mas" id="btn-${seccionId}">Cargar más</button>
    </div>`
}

function agregarCargarMas(containerId, seccionId, callback) {
    const wrap = document.getElementById(`wrap-${seccionId}`)
    if (wrap) wrap.remove()
    const grid = document.getElementById(containerId)
    if (!grid) return
    grid.insertAdjacentHTML('afterend', btnCargarMas(seccionId))
    document.getElementById(`btn-${seccionId}`).addEventListener('click', callback)
}

function quitarCargarMas(seccionId) {
    const wrap = document.getElementById(`wrap-${seccionId}`)
    if (wrap) wrap.remove()
}

// ── PREFERENCIAS / PRIVACIDAD / ZONA DE PELIGRO ──────

function syncToggleGroup(groupId, activeValue) {
    const group = document.getElementById(groupId)
    if (!group) return
    group.querySelectorAll('.config-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === activeValue)
    })
}

function actualizarPerfilHint() {
    const hint = document.getElementById('perfilHint')
    if (!hint) return
    hint.textContent = state.prefs.perfil === 'privado'
        ? 'Solo tú puedes ver tu lista y estadísticas.'
        : 'Cualquier persona con tu enlace puede ver tu lista.'
}

function aplicarTema(tema) {
    if (tema === 'light') {
        document.documentElement.setAttribute('data-theme', 'light')
    } else {
        document.documentElement.removeAttribute('data-theme')
    }
}

function aplicarDensidad(densidad) {
    document.documentElement.setAttribute('data-densidad', densidad)
}

// Listeners toggles de preferencias
document.getElementById('temaToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        state.prefs.tema = btn.dataset.value
        syncToggleGroup('temaToggle', btn.dataset.value)
        aplicarTema(btn.dataset.value)
        localStorage.setItem('ca_tema', btn.dataset.value)
    })
})

// idioma toggle eliminado

document.getElementById('densidadToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        state.prefs.densidad = btn.dataset.value
        syncToggleGroup('densidadToggle', btn.dataset.value)
        aplicarDensidad(btn.dataset.value)
        localStorage.setItem('ca_densidad', btn.dataset.value)
    })
})

// Listener toggle privacidad
document.getElementById('perfilToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const esPublico = btn.dataset.value === 'publico'
        state.prefs.perfil = btn.dataset.value
        state.user.perfil_publico = esPublico
        syncToggleGroup('perfilToggle', btn.dataset.value)
        actualizarPerfilHint()
        try {
            await fetch('/update-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ perfil_publico: esPublico })
            })
            rankingCargado = false  // forzar recarga del ranking
        } catch(e) {}
    })
})

// Cargar preferencias guardadas en localStorage al inicio
;(function cargarPrefsLocales() {
    const tema     = localStorage.getItem('ca_tema')     || 'dark'
    const idioma   = localStorage.getItem('ca_idioma')   || 'es'
    const densidad = localStorage.getItem('ca_densidad') || 'normal'
    state.prefs.tema     = tema
    state.prefs.idioma   = idioma
    state.prefs.densidad = densidad
    aplicarTema(tema)
    aplicarDensidad(densidad)
})()

// ── ZONA DE PELIGRO ───────────────────────────────────

// Modal de confirmación reutilizable
function confirmarAccion(mensaje, onConfirm) {
    const overlay = document.createElement('div')
    overlay.className = 'confirm-overlay'
    overlay.innerHTML = `
        <div class="confirm-box">
            <p class="confirm-msg">${mensaje}</p>
            <div class="confirm-btns">
                <button class="confirm-cancel">Cancelar</button>
                <button class="confirm-ok btn-danger">Confirmar</button>
            </div>
        </div>`
    document.body.appendChild(overlay)
    overlay.querySelector('.confirm-cancel').addEventListener('click', () => overlay.remove())
    overlay.querySelector('.confirm-ok').addEventListener('click', () => { overlay.remove(); onConfirm() })
}

// Borrar toda la lista
document.getElementById('btnBorrarLista')?.addEventListener('click', () => {
    confirmarAccion('¿Seguro que quieres borrar toda tu lista? Esta acción no se puede deshacer.', async () => {
        const fb = document.getElementById('feedbackBorrarLista')
        try {
            const res  = await fetch('/lista/borrar-todo', { method: 'DELETE' })
            const data = await res.json()
            if (!res.ok) { setFeedback('feedbackBorrarLista', data.error || 'Error al borrar.', 'error'); return }
            // Limpiar estado local
            state.lista = { visto: [], pendiente: [], abandonado: [], like: [] }
            updateListCounters()
            setFeedback('feedbackBorrarLista', '✓ Lista borrada correctamente.', 'ok')
        } catch(e) {
            setFeedback('feedbackBorrarLista', 'Error de conexión.', 'error')
        }
    })
})

// Eliminar cuenta
document.getElementById('btnEliminarCuenta')?.addEventListener('click', () => {
    confirmarAccion('¿Seguro que quieres eliminar tu cuenta? Perderás todos tus datos permanentemente.', async () => {
        const fb = document.getElementById('feedbackEliminarCuenta')
        try {
            const res  = await fetch('/cuenta/eliminar', { method: 'DELETE' })
            const data = await res.json()
            if (!res.ok) { setFeedback('feedbackEliminarCuenta', data.error || 'Error.', 'error'); return }
            window.location.href = '/'
        } catch(e) {
            setFeedback('feedbackEliminarCuenta', 'Error de conexión.', 'error')
        }
    })
})

// ── GUARDAR CONFIGURACIÓN GENERAL ───────────────────
document.getElementById('btnGuardarConfig')?.addEventListener('click', async () => {
    const btn = document.getElementById('btnGuardarConfig')
    btn.disabled = true; btn.textContent = 'Guardando...'
    try {
        const res = await fetch('/update-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                perfil_publico: state.user.perfil_publico,
            })
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackConfig', data.error || 'Error.', 'error'); return }
        // Aplicar preferencias visuales
        aplicarTema(state.prefs.tema)
        aplicarDensidad(state.prefs.densidad)
        localStorage.setItem('ca_tema',     state.prefs.tema)
        localStorage.setItem('ca_densidad', state.prefs.densidad)
        rankingCargado = false  // forzar recarga del ranking
        setFeedback('feedbackConfig', '✓ Configuración guardada y aplicada.', 'ok')
    } catch(e) {
        setFeedback('feedbackConfig', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false; btn.textContent = '💾 Guardar configuración'
    }
})

// ── GUARDAR REDES SOCIALES ───────────────────────────
document.getElementById('btnSaveRedes')?.addEventListener('click', async () => {
    const btn = document.getElementById('btnSaveRedes')
    btn.disabled = true; btn.textContent = 'Guardando...'
    const datos = {
        instagram: document.getElementById('inputInstagram')?.value.trim() || '',
        discord:   document.getElementById('inputDiscord')?.value.trim()   || '',
        tiktok:    document.getElementById('inputTiktok')?.value.trim()    || '',
    }
    try {
        const res  = await fetch('/update-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackRedes', data.error || 'Error.', 'error'); return }
        Object.assign(state.user, datos)
        setFeedback('feedbackRedes', '✓ Redes guardadas correctamente.', 'ok')
    } catch(e) {
        setFeedback('feedbackRedes', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false; btn.textContent = 'Guardar redes'
    }
})

// ── RANKING ───────────────────────────────────────────
let rankingCargado = false

async function loadRanking() {
    if (rankingCargado) return
    const container = document.getElementById('rankingList')
    if (!container) return
    container.innerHTML = '<div class="ranking-loading">Cargando ranking...</div>'
    try {
        const res  = await fetch('/ranking')
        const data = await res.json()
        const lista = data.ranking || []
        if (!lista.length) {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">🏆</div><p>Aún no hay usuarios en el ranking.</p></div>'
            return
        }
        container.innerHTML = lista.map((u, i) => rankingRowHTML(u, i)).join('')
        container.querySelectorAll('.ranking-row[data-id]').forEach(row => {
            row.addEventListener('click', () => {
                const u = lista.find(x => String(x.id) === row.dataset.id)
                if (u?.perfil_publico) abrirPerfil(u.id)
            })
        })
        rankingCargado = true
    } catch(e) {
        container.innerHTML = '<div class="empty-state"><p>Error al cargar el ranking.</p></div>'
    }
}

function rankingRowHTML(u, i) {
    const pos     = i + 1
    const medalla = pos === 1 ? '🥇' : pos === 2 ? '🥈' : pos === 3 ? '🥉' : `#${pos}`
    const letra   = (u.username || '?')[0].toUpperCase()
    const avatar  = u.foto_perfil
        ? `<img src="${u.foto_perfil}" alt="${u.username}" class="ranking-avatar-img">`
        : `<div class="ranking-avatar-letter">${letra}</div>`
    const clickable = u.perfil_publico ? 'ranking-row--clickable' : ''
    const candado   = u.perfil_publico ? '' : '<span class="ranking-lock">🔒</span>'
    return `
        <div class="ranking-row ${clickable}" data-id="${u.id}">
            <span class="ranking-pos ${pos <= 3 ? 'top3' : ''}">${medalla}</span>
            <div class="ranking-avatar">${avatar}</div>
            <div class="ranking-user-info">
                <span class="ranking-username">${u.username || 'Usuario'}${candado}</span>
            </div>
            <div class="ranking-vistos">
                <span class="ranking-num">${u.vistos}</span>
                <span class="ranking-label">vistos</span>
            </div>
        </div>`
}

// ── PERFIL PÚBLICO ────────────────────────────────────
async function abrirPerfil(usuarioId) {
    const overlay = document.getElementById('perfilOverlay')
    overlay.style.display = 'flex'
    document.body.style.overflow = 'hidden'

    document.getElementById('perfilUsername').textContent = 'Cargando...'
    document.getElementById('perfilRedes').innerHTML = ''
    document.getElementById('perfilStatsRow').innerHTML = ''
    document.getElementById('perfilTop5').innerHTML = ''
    document.getElementById('perfilTop5Wrap').style.display = 'none'

    try {
        const res = await fetch(`/perfil/${usuarioId}`)
        if (res.status === 403) {
            overlay.style.display = 'none'
            document.body.style.overflow = ''
            return
        }
        const data = await res.json()
        const u = data.usuario || {}
        const stats = data.stats || {}
        const top5 = data.top5 || []

        const letra = (u.username || '?')[0].toUpperCase()
        document.getElementById('perfilAvatarLetter').textContent = letra
        const img = document.getElementById('perfilAvatarImg')
        if (u.foto_perfil) {
            img.src = u.foto_perfil
            img.style.display = 'block'
            document.getElementById('perfilAvatarLetter').style.display = 'none'
        } else {
            img.style.display = 'none'
            document.getElementById('perfilAvatarLetter').style.display = 'block'
        }

        document.getElementById('perfilUsername').textContent = u.username || 'Usuario'
        document.getElementById('perfilMiembro').textContent = u.creado_en
            ? `Miembro desde ${(parseFecha(u.creado_en) || new Date()).toLocaleDateString('es-ES', { year:'numeric', month:'long' })}`
            : ''

        const coverEl = document.getElementById('perfilCover')
        if (u.perfil_header_imagen) {
            coverEl.style.background = `linear-gradient(180deg, rgba(10,10,10,.08), rgba(10,10,10,.75)), url(${u.perfil_header_imagen}) center/cover no-repeat`
        } else if (u.perfil_header_color) {
            coverEl.style.background = `linear-gradient(135deg, ${u.perfil_header_color}, #101010)`
        } else {
            coverEl.style.background = 'linear-gradient(135deg, #f97316 0%, #1a1a1a 100%)'
        }

        const redes = []
        if (u.instagram) redes.push(`<a href="https://instagram.com/${u.instagram}" target="_blank" class="perfil-red instagram">${socialIconSVG('instagram')}<span>@${u.instagram}</span></a>`)
        if (u.discord) redes.push(`<a href="https://discord.com/${u.discord}" target="_blank" class="perfil-red discord">${socialIconSVG('discord')}<span>${u.discord}</span></a>`)
        if (u.tiktok) redes.push(`<a href="https://tiktok.com/@${u.tiktok}" target="_blank" class="perfil-red tiktok">${socialIconSVG('tiktok')}<span>@${u.tiktok}</span></a>`)

        document.getElementById('perfilRedes').innerHTML = redes.join('') || '<span class="stats-empty">Sin redes visibles.</span>'

        const topGenero = stats.top_generos?.[0]?.nombre || '—'
        document.getElementById('perfilStatsRow').innerHTML = `
            <div class="perfil-stat emphasis"><span class="perfil-stat-num">${stats.total_vistos || 0}</span><span class="perfil-stat-label">Vistos reales</span></div>
            <div class="perfil-stat"><span class="perfil-stat-num">${top5.length}</span><span class="perfil-stat-label">Top 5 activo</span></div>
            <div class="perfil-stat"><span class="perfil-stat-num perfil-stat-text">${escapeHTML(topGenero)}</span><span class="perfil-stat-label">Género destacado</span></div>`

        const top5Wrap = document.getElementById('perfilTop5Wrap')
        const top5El = document.getElementById('perfilTop5')
        top5Wrap.style.display = 'block'
        if (top5.length) {
            top5El.innerHTML = top5.map(item => `
                <div class="perfil-top5-item">
                    <span class="perfil-top5-pos p${item.posicion}">#${item.posicion}</span>
                    ${item.poster_url ? `<img class="perfil-top5-poster" src="${item.poster_url}" alt="${escapeHTML(item.titulo || '')}">` : '<div class="perfil-top5-poster"></div>'}
                    <div class="perfil-top5-info">
                        <div class="perfil-top5-titulo">${escapeHTML(item.titulo || 'Anime')}</div>
                        ${item.rating ? `<div class="perfil-top5-rating">★ ${Number(item.rating).toFixed(2)}</div>` : '<div class="perfil-top5-rating muted">Sin rating</div>'}
                    </div>
                </div>`).join('')
        } else {
            top5El.innerHTML = '<p class="stats-empty">Este usuario aún no ha configurado su Top 5.</p>'
        }
    } catch(e) {
        document.getElementById('perfilUsername').textContent = 'Error al cargar perfil'
    }
}

document.getElementById('perfilClose')?.addEventListener('click', () => {
    document.getElementById('perfilOverlay').style.display = 'none'
    document.body.style.overflow = ''
})
document.getElementById('perfilOverlay')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('perfilOverlay')) {
        document.getElementById('perfilOverlay').style.display = 'none'
        document.body.style.overflow = ''
    }
})

async function _cargarLikesBackground() {
    try {
        const res  = await fetch('/lista')
        if (!res.ok) return
        const data = await res.json()
        state.lista.like       = data.likes      || []
        state.lista.abandonado = data.abandonados || state.lista.abandonado
        updateListCounters()
    } catch(e) {}
}

loadAnimes()

async function loadAnimes() {
    paginacion.trending = { offset: 0, limit: 28, agotado: false }
    paginacion.emision  = { offset: 0, limit: 28, agotado: false }

    renderSkeletons('trendingGrid', 8)
    renderSkeletons('emisionGrid', 8)
    renderSkeletons('generoGrid', 8)

    // Tendencias
    try {
        const res  = await fetch(`/animes/top?limit=28&offset=0`)
        const data = await res.json()
        const items = data.resultados || []
        document.getElementById('trendingGrid').innerHTML = items.map(a => animeCardHTML(a)).join('')
        document.getElementById('trendingGrid').querySelectorAll('.anime-card').forEach((card, i) => {
            card.style.cursor = 'pointer'
            card.addEventListener('click', () => irAAnime(items[i]))
        })
        state.animes = items
        paginacion.trending.offset = items.length
    } catch(e) {
        document.getElementById('trendingGrid').innerHTML =
            `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">⚠️</div><p>No se pudieron cargar.</p></div>`
    }

    // En emisión
    try {
        const res  = await fetch(`/animes/emision?limit=28&offset=0`)
        const data = await res.json()
        const items = data.resultados || []
        renderAnimeGrid('emisionGrid', items)
        paginacion.emision.offset = items.length
    } catch(e) {
        document.getElementById('emisionGrid').innerHTML =
            `<div class="empty-state" style="grid-column:1/-1"><p>Error al cargar.</p></div>`
    }

    await loadGenero('Action')
}

async function cargarMasTrending() {
    const p = paginacion.trending
    if (p.agotado) return
    const btn = document.getElementById('btn-trending')
    if (btn) { btn.disabled = true; btn.textContent = 'Cargando...' }

    try {
        const res  = await fetch(`/animes/top?limit=${p.limit}&offset=${p.offset}`)
        const data = await res.json()
        const items = data.resultados || []
        const grid = document.getElementById('trendingGrid')
        const startIndex = grid.querySelectorAll('.anime-card').length
        grid.insertAdjacentHTML('beforeend', items.map(a => animeCardHTML(a)).join(''))
        grid.querySelectorAll('.anime-card:not([data-bound])').forEach((card, i) => {
            card.dataset.bound = '1'
            card.style.cursor = 'pointer'
            card.addEventListener('click', () => irAAnime(items[i]))
        })
        p.offset += items.length
        if (items.length < p.limit) {
            p.agotado = true
            quitarCargarMas('trending')
        } else if (btn) {
            btn.disabled = false
            btn.textContent = 'Cargar más'
        }
    } catch(e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Cargar más' }
    }
}

async function cargarMasEmision() {
    const p = paginacion.emision
    if (p.agotado) return
    const btn = document.getElementById('btn-emision')
    if (btn) { btn.disabled = true; btn.textContent = 'Cargando...' }

    try {
        const res  = await fetch(`/animes/emision?limit=${p.limit}&offset=${p.offset}`)
        const data = await res.json()
        const items = data.resultados || []
        const grid = document.getElementById('emisionGrid')
        grid.insertAdjacentHTML('beforeend', items.map(a => animeCardHTML(a)).join(''))
        grid.querySelectorAll('.anime-card:not([data-bound])').forEach((card, i) => {
            card.dataset.bound = '1'
            card.style.cursor = 'pointer'
            card.addEventListener('click', () => irAAnime(items[i]))
        })
        p.offset += items.length
        if (items.length < p.limit) {
            p.agotado = true
            quitarCargarMas('emision')
        } else if (btn) {
            btn.disabled = false
            btn.textContent = 'Cargar más'
        }
    } catch(e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Cargar más' }
    }
}

async function cargarMasPopular() {
    const p = paginacion.popular
    if (!p || p.agotado) return
    const btn = document.getElementById('btn-popular')
    if (btn) { btn.disabled = true; btn.textContent = 'Cargando...' }
    try {
        const res  = await fetch(`/animes/top?limit=${p.limit}&offset=${p.offset}`)
        const data = await res.json()
        const items = data.resultados || []
        const grid  = document.getElementById('popularGrid')
        grid.insertAdjacentHTML('beforeend', items.map(a => animeCardHTML(a)).join(''))
        grid.querySelectorAll('.anime-card:not([data-bound])').forEach((card, i) => {
            card.dataset.bound = '1'
            card.style.cursor = 'pointer'
            card.addEventListener('click', () => irAAnime(items[i]))
        })
        p.offset += items.length
        if (items.length < p.limit) {
            p.agotado = true
            quitarCargarMas('popular')
        } else if (btn) {
            btn.disabled = false
            btn.textContent = 'Cargar más'
        }
    } catch(e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Cargar más' }
    }
}

async function cargarMasEmisionFull() {
    const p = paginacion.emisionFull
    if (!p || p.agotado) return
    const btn = document.getElementById('btn-emisionFull')
    if (btn) { btn.disabled = true; btn.textContent = 'Cargando...' }
    try {
        const res  = await fetch(`/animes/emision?limit=${p.limit}&offset=${p.offset}`)
        const data = await res.json()
        const items = data.resultados || []
        const grid  = document.getElementById('emisionFullGrid')
        grid.insertAdjacentHTML('beforeend', items.map(a => animeCardHTML(a)).join(''))
        grid.querySelectorAll('.anime-card:not([data-bound])').forEach((card, i) => {
            card.dataset.bound = '1'
            card.style.cursor = 'pointer'
            card.addEventListener('click', () => irAAnime(items[i]))
        })
        p.offset += items.length
        if (items.length < p.limit) {
            p.agotado = true
            quitarCargarMas('emisionFull')
        } else if (btn) {
            btn.disabled = false
            btn.textContent = 'Cargar más'
        }
    } catch(e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Cargar más' }
    }
}

let generoActivo = 'accion'

async function loadGenero(g) {
    generoActivo = g
    paginacion.genero = { offset: 0, limit: 28, agotado: false }
    document.querySelectorAll('.genero-tab').forEach(t =>
        t.classList.toggle('active', t.dataset.genero === g)
    )
    quitarCargarMas('genero')
    renderSkeletons('generoGrid', 8)

    try {
        const res  = await fetch(`/animes/genero?g=${g}&limit=28&offset=0`)
        const data = await res.json()
        const items = data.resultados || []
        renderAnimeGrid('generoGrid', items)
        paginacion.genero.offset = items.length
        if (items.length >= 28) {
            agregarCargarMas('generoGrid', 'genero', cargarMasGenero)
        }
    } catch(e) {
        document.getElementById('generoGrid').innerHTML =
            `<div class="empty-state" style="grid-column:1/-1"><p>Error al cargar.</p></div>`
    }
}

async function cargarMasGenero() {
    const p = paginacion.genero
    if (p.agotado) return
    const btn = document.getElementById('btn-genero')
    if (btn) { btn.disabled = true; btn.textContent = 'Cargando...' }

    try {
        const res  = await fetch(`/animes/genero?g=${generoActivo}&limit=${p.limit}&offset=${p.offset}`)
        const data = await res.json()
        const items = data.resultados || []
        const grid = document.getElementById('generoGrid')
        grid.insertAdjacentHTML('beforeend', items.map(a => animeCardHTML(a)).join(''))
        grid.querySelectorAll('.anime-card:not([data-bound])').forEach((card, i) => {
            card.dataset.bound = '1'
            card.style.cursor = 'pointer'
            card.addEventListener('click', () => irAAnime(items[i]))
        })
        p.offset += items.length
        if (items.length < p.limit) {
            p.agotado = true
            quitarCargarMas('genero')
        } else if (btn) {
            btn.disabled = false
            btn.textContent = 'Cargar más'
        }
    } catch(e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Cargar más' }
    }
}

// ── LOGOUT ────────────────────────────────────────────
document.querySelector('.logout')?.addEventListener('click', async (e) => {
    e.preventDefault()
    try {
        await fetch('/logout', { method: 'POST' })
    } catch(e) {
        // Si falla el fetch igual redirigimos
    }
    window.location.href = '/'
})

// ── BÚSQUEDA ──────────────────────────────────────────
let searchTimeout = null
let currentAnime  = null

const searchInput   = document.getElementById('searchInput')
const searchResults = document.getElementById('searchResults')
const searchClear   = document.getElementById('searchClear')

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim()
    searchClear.style.display = q ? 'inline' : 'none'
    clearTimeout(searchTimeout)
    if (q.length < 2) { searchResults.style.display = 'none'; return }
    searchResults.style.display = 'block'
    searchResults.innerHTML = '<div class="search-loading">Buscando...</div>'
    searchTimeout = setTimeout(() => fetchSearch(q), 350)
})

searchClear.addEventListener('click', () => {
    searchInput.value = ''
    searchClear.style.display = 'none'
    searchResults.style.display = 'none'
    searchInput.focus()
})

document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrapper')) {
        searchResults.style.display = 'none'
    }
})

async function fetchSearch(q) {
    try {
        const res  = await fetch(`/animes/buscar?q=${encodeURIComponent(q)}`)
        const data = await res.json()
        renderSearchResults(data.resultados || [])
    } catch(e) {
        searchResults.innerHTML = '<div class="search-empty">Error al buscar.</div>'
    }
}

function renderSearchResults(items) {
    if (!items.length) {
        searchResults.innerHTML = '<div class="search-empty">Sin resultados.</div>'
        return
    }
    searchResults.innerHTML = items.map(a => `
        <div class="search-result-item" data-id="${a.id}">
            <img class="search-result-img" src="${a.poster_url || ''}" alt="${a.titulo}" loading="lazy">
            <div class="search-result-info">
                <div class="search-result-title">${a.titulo}</div>
                <div class="search-result-meta">
                    ${a.rating ? `★ ${a.rating}` : ''}
                    ${a.episodios ? ` · ${a.episodios} eps` : ''}
                    ${a.estado ? ` · ${a.estado === 'finished' ? 'Finalizado' : 'En emisión'}` : ''}
                </div>
            </div>
        </div>
    `).join('')

    searchResults.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const anime = items.find(a => a.id === item.dataset.id)
            if (anime) irAAnime(anime)
            searchResults.style.display = 'none'
            searchInput.value = ''
            searchClear.style.display = 'none'
        })
    })
}

// ── NAVEGACIÓN A FICHA DE ANIME ───────────────────────
function irAAnime(anime) {
    // Los animes ahora vienen siempre en formato interno desde la BD.
    try { sessionStorage.setItem('anime_prefetch', JSON.stringify(anime)) } catch(e) {}
    window.location.href = `/dashboard/anime/${anime.id}`
}

// Tabs de géneros
document.querySelectorAll('.genero-tab').forEach(tab => {
    tab.addEventListener('click', () => loadGenero(tab.dataset.genero))
})

// ── EXPORTAR XLSX ────────────────────────────────────
function todaLaLista() {
    return [
        ...state.lista.visto.map(a => ({...a, tipo: 'visto'})),
        ...state.lista.pendiente.map(a => ({...a, tipo: 'pendiente'})),
    ]
}




// ── INTERCEPTOR GLOBAL DE SESION Y CSRF ──────────────────
// Envuelve fetch para:
//   1. Inyectar X-CSRF-Token en todos los metodos mutantes (POST/PUT/PATCH/DELETE)
//   2. Detectar 401 y redirigir al login
//   3. Detectar 403 CSRF y avisar al usuario
//
// El csrf_token viene de la cookie 'csrf_token' (no HttpOnly)
// que el backend setea al hacer login.
;(function() {
    const _fetch = window.fetch
    const RUTAS_EXCLUIDAS = ['/login', '/logout', '/register', '/verify-email']
    const METODOS_MUTANTES = ['POST', 'PUT', 'PATCH', 'DELETE']

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)
        return match ? decodeURIComponent(match[1]) : null
    }

    window.fetch = async function(...args) {
        let [input, init = {}] = args

        // Inyectar CSRF en metodos mutantes
        const method = (init.method || 'GET').toUpperCase()
        if (METODOS_MUTANTES.includes(method)) {
            const csrf = getCsrfToken()
            if (csrf) {
                init = {
                    ...init,
                    headers: {
                        ...(init.headers || {}),
                        'X-CSRF-Token': csrf
                    }
                }
            }
        }

        const res = await _fetch(input, init)
        const url = typeof input === 'string' ? input : (input?.url || '')

        if (res.status === 401) {
            const esExcluida = RUTAS_EXCLUIDAS.some(r => url.includes(r))
            if (!esExcluida) {
                console.warn('[Auth] 401 en', url, '— redirigiendo al login')
                setTimeout(() => { window.location.href = '/login' }, 150)
            }
        }

        if (res.status === 403) {
            // Puede ser CSRF invalido — rara vez deberia ocurrir si la sesion es valida
            console.warn('[CSRF] 403 en', url, '— posible token CSRF invalido')
        }

        return res
    }
})()

// ── INICIO ────────────────────────────────────────────
loadUser()

// ── INICIO — resolver sección desde la URL actual ─────
// Si el usuario entró directamente a /dashboard/ranking,
// /dashboard/mi-lista, etc., navegamos a la sección correcta
// sin pushState (ya estamos en la URL correcta).
// history.replaceState registra el estado inicial para que
// popstate funcione también desde el primer historial.
;(function() {
    const section = resolvePathToSection()
    history.replaceState({ section }, '', sectionToPath(section))
    if (section !== 'inicio') {
        // Esperar a que loadUser termine antes de activar la sección
        // para que los datos ya estén disponibles (ej: estadísticas, mi-lista)
        const tryNavigate = setInterval(() => {
            if (state.user.email) {
                clearInterval(tryNavigate)
                navigateTo(section, false)
            }
        }, 80)
        // Fallback: si loadUser tarda más de 3s, navegamos igual
        setTimeout(() => {
            clearInterval(tryNavigate)
            navigateTo(section, false)
        }, 3000)
    }
})()
// ── PREFERENCIAS / PRIVACIDAD / ZONA DE PELIGRO ──────

function syncToggleGroup(groupId, activeValue) {
    const group = document.getElementById(groupId)
    if (!group) return
    group.querySelectorAll('.config-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === activeValue)
    })
}

function actualizarPerfilHint() {
    const hint = document.getElementById('perfilHint')
    if (!hint) return
    hint.textContent = state.prefs.perfil === 'privado'
        ? 'Solo tú puedes ver tu lista y estadísticas.'
        : 'Cualquier persona con tu enlace puede ver tu lista.'
}

function aplicarTema(tema) {
    if (tema === 'light') {
        document.documentElement.setAttribute('data-theme', 'light')
    } else {
        document.documentElement.removeAttribute('data-theme')
    }
}

function aplicarDensidad(densidad) {
    document.documentElement.setAttribute('data-densidad', densidad)
}

// Listeners toggles de preferencias
document.getElementById('temaToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        state.prefs.tema = btn.dataset.value
        syncToggleGroup('temaToggle', btn.dataset.value)
        aplicarTema(btn.dataset.value)
        localStorage.setItem('ca_tema', btn.dataset.value)
    })
})

// idioma toggle eliminado

document.getElementById('densidadToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        state.prefs.densidad = btn.dataset.value
        syncToggleGroup('densidadToggle', btn.dataset.value)
        aplicarDensidad(btn.dataset.value)
        localStorage.setItem('ca_densidad', btn.dataset.value)
    })
})

// Listener toggle privacidad
document.getElementById('perfilToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const esPublico = btn.dataset.value === 'publico'
        state.prefs.perfil = btn.dataset.value
        state.user.perfil_publico = esPublico
        syncToggleGroup('perfilToggle', btn.dataset.value)
        actualizarPerfilHint()
        try {
            await fetch('/update-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ perfil_publico: esPublico })
            })
            rankingCargado = false  // forzar recarga del ranking
        } catch(e) {}
    })
})

// Cargar preferencias guardadas en localStorage al inicio
;(function cargarPrefsLocales() {
    const tema     = localStorage.getItem('ca_tema')     || 'dark'
    const idioma   = localStorage.getItem('ca_idioma')   || 'es'
    const densidad = localStorage.getItem('ca_densidad') || 'normal'
    state.prefs.tema     = tema
    state.prefs.idioma   = idioma
    state.prefs.densidad = densidad
    aplicarTema(tema)
    aplicarDensidad(densidad)
})()

// ── ZONA DE PELIGRO ───────────────────────────────────

// Modal de confirmación reutilizable
function confirmarAccion(mensaje, onConfirm) {
    const overlay = document.createElement('div')
    overlay.className = 'confirm-overlay'
    overlay.innerHTML = `
        <div class="confirm-box">
            <p class="confirm-msg">${mensaje}</p>
            <div class="confirm-btns">
                <button class="confirm-cancel">Cancelar</button>
                <button class="confirm-ok btn-danger">Confirmar</button>
            </div>
        </div>`
    document.body.appendChild(overlay)
    overlay.querySelector('.confirm-cancel').addEventListener('click', () => overlay.remove())
    overlay.querySelector('.confirm-ok').addEventListener('click', () => { overlay.remove(); onConfirm() })
}

// Borrar toda la lista
document.getElementById('btnBorrarLista')?.addEventListener('click', () => {
    confirmarAccion('¿Seguro que quieres borrar toda tu lista? Esta acción no se puede deshacer.', async () => {
        const fb = document.getElementById('feedbackBorrarLista')
        try {
            const res  = await fetch('/lista/borrar-todo', { method: 'DELETE' })
            const data = await res.json()
            if (!res.ok) { setFeedback('feedbackBorrarLista', data.error || 'Error al borrar.', 'error'); return }
            // Limpiar estado local
            state.lista = { visto: [], pendiente: [], abandonado: [], like: [] }
            updateListCounters()
            setFeedback('feedbackBorrarLista', '✓ Lista borrada correctamente.', 'ok')
        } catch(e) {
            setFeedback('feedbackBorrarLista', 'Error de conexión.', 'error')
        }
    })
})

// Eliminar cuenta
document.getElementById('btnEliminarCuenta')?.addEventListener('click', () => {
    confirmarAccion('¿Seguro que quieres eliminar tu cuenta? Perderás todos tus datos permanentemente.', async () => {
        const fb = document.getElementById('feedbackEliminarCuenta')
        try {
            const res  = await fetch('/cuenta/eliminar', { method: 'DELETE' })
            const data = await res.json()
            if (!res.ok) { setFeedback('feedbackEliminarCuenta', data.error || 'Error.', 'error'); return }
            window.location.href = '/'
        } catch(e) {
            setFeedback('feedbackEliminarCuenta', 'Error de conexión.', 'error')
        }
    })
})


// ── MI TOP 5 ──────────────────────────────────────────────────────────────────
let top5State = []
let selectedTop5Pos = 1

async function loadMiTop5() {
    const slotsEl = document.getElementById('top5Slots')
    const wrap = document.getElementById('top5SearchWrap')
    if (!slotsEl) return
    slotsEl.innerHTML = '<div class="ranking-loading">Cargando...</div>'
    if (wrap) wrap.style.display = 'block'
    try {
        const res  = await fetch('/mi-top5')
        const data = await res.json()
        top5State  = data.top5 || []
        setupTop5SearchUI()
        renderTop5Slots()
        renderTop5SearchResults(document.getElementById('top5SearchInput')?.value || '')
    } catch(e) {
        slotsEl.innerHTML = '<p style="color:var(--muted)">Error al cargar tu top 5.</p>'
    }
}

function getTop5Candidates() {
    return allListUnique().sort((a, b) => (a.titulo || '').localeCompare(b.titulo || '', 'es', { sensitivity: 'base' }))
}

function setupTop5SearchUI() {
    const wrap  = document.getElementById('top5SearchWrap')
    const label = document.getElementById('top5PosLabel')
    const input = document.getElementById('top5SearchInput')
    const text  = document.querySelector('.top5-search-label')
    const cancel = document.getElementById('top5CancelSearch')
    if (!wrap || !input) return
    wrap.style.display = 'block'
    if (!selectedTop5Pos) selectedTop5Pos = 1
    if (label) label.textContent = `#${selectedTop5Pos}`
    if (text) text.innerHTML = 'Busca cualquier anime de tu lista y asígnalo a una posición de tu Top 5.'
    input.placeholder = 'Buscar en toda mi lista...'
    if (cancel) cancel.textContent = 'Limpiar búsqueda'
}

function renderTop5Slots() {
    const slotsEl = document.getElementById('top5Slots')
    const label   = document.getElementById('top5PosLabel')
    if (!slotsEl) return
    if (label) label.textContent = `#${selectedTop5Pos}`

    slotsEl.innerHTML = [1,2,3,4,5].map(pos => {
        const entrada = top5State.find(t => t.posicion === pos)
        const selected = pos === selectedTop5Pos ? ' searching' : ''
        if (!entrada) {
            return `
            <div class="top5-card empty${selected}" data-pos="${pos}">
                <div class="top5-card-inner top5-card-empty-inner">
                    <span class="top5-slot-pos pos-${pos}">#${pos}</span>
                    <div class="top5-empty-info">
                        <span class="top5-empty-label">Posición libre. Selecciónala y luego usa la búsqueda superior.</span>
                        <button class="top5-btn-add" data-pos="${pos}">Elegir anime</button>
                    </div>
                </div>
            </div>`
        }
        return `
        <div class="top5-card${selected}" data-pos="${pos}">
            <div class="top5-card-inner">
                <span class="top5-slot-pos pos-${pos}">#${pos}</span>
                <div class="top5-poster-wrap">
                    ${entrada.poster_url ? `<img class="top5-poster" src="${entrada.poster_url}" alt="${escapeHTML(entrada.titulo)}">` : '<div class="top5-poster-placeholder"></div>'}
                </div>
                <div class="top5-card-info">
                    <p class="top5-card-title">${escapeHTML(entrada.titulo)}</p>
                    ${entrada.rating ? `<div class="top5-card-rating">★ ${Number(entrada.rating).toFixed(2)}</div>` : ''}
                </div>
                <div class="top5-card-actions">
                    <button class="top5-btn-change" data-pos="${pos}" title="Editar">✎</button>
                    <button class="top5-btn-remove" data-pos="${pos}" title="Eliminar">✕</button>
                </div>
            </div>
        </div>`
    }).join('')

    slotsEl.querySelectorAll('.top5-card[data-pos], .top5-btn-add, .top5-btn-change').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation()
            selectedTop5Pos = parseInt(el.dataset.pos || el.closest('[data-pos]')?.dataset.pos || '1')
            renderTop5Slots()
            renderTop5SearchResults(document.getElementById('top5SearchInput')?.value || '')
            document.getElementById('top5SearchInput')?.focus()
        })
    })
    slotsEl.querySelectorAll('.top5-btn-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation()
            quitarTop5(parseInt(btn.dataset.pos))
        })
    })
}

function renderTop5SearchResults(query) {
    const resEl = document.getElementById('top5SearchResults')
    if (!resEl) return
    const q = (query || '').trim().toLowerCase()
    const filtrados = getTop5Candidates().filter(a => !q || (a.titulo || '').toLowerCase().includes(q)).slice(0, 20)
    if (!filtrados.length) {
        resEl.innerHTML = '<p class="top5-no-results">No hay resultados en tu lista.</p>'
        return
    }
    resEl.innerHTML = filtrados.map(a => {
        const yaEnTop = top5State.find(t => String(t.id) === String(a.id))
        return `
            <div class="top5-result-item" data-id="${a.id}">
                ${a.poster_url ? `<img class="top5-result-poster" src="${a.poster_url}" alt="${escapeHTML(a.titulo)}">` : '<div class="top5-result-poster"></div>'}
                <div class="top5-result-info">
                    <span class="top5-result-title">${escapeHTML(a.titulo)}</span>
                    <span class="top5-result-rating">${a.rating ? `★ ${Number(a.rating).toFixed(2)}` : (a.tipo_origen || 'lista')}</span>
                </div>
                ${yaEnTop ? `<span class="top5-result-rating">Ya en #${yaEnTop.posicion}</span>` : ''}
            </div>`
    }).join('')
    resEl.querySelectorAll('.top5-result-item').forEach(item => item.addEventListener('click', () => seleccionarTop5(item.dataset.id)))
}

const top5Input = document.getElementById('top5SearchInput')
if (top5Input) {
    let top5Timer = null
    top5Input.addEventListener('input', () => {
        clearTimeout(top5Timer)
        top5Timer = setTimeout(() => renderTop5SearchResults(top5Input.value), 120)
    })
}

document.getElementById('top5CancelSearch')?.addEventListener('click', () => {
    const input = document.getElementById('top5SearchInput')
    if (input) input.value = ''
    renderTop5SearchResults('')
})

async function seleccionarTop5(animeId) {
    try {
        const res  = await fetch('/mi-top5/guardar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ posicion: selectedTop5Pos, anime_id: animeId })
        })
        const data = await res.json()
        if (!res.ok) { alert(data.error || 'Error al guardar'); return }
        await loadMiTop5()
    } catch(e) { alert('Error de conexión') }
}

async function quitarTop5(pos) {
    try {
        const res = await fetch('/mi-top5/eliminar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ posicion: pos })
        })
        if (!res.ok) return
        top5State = top5State.filter(t => t.posicion !== pos)
        renderTop5Slots()
        renderTop5SearchResults(document.getElementById('top5SearchInput')?.value || '')
    } catch(e) {}
}


function getExportFiltroActivo() {
    const active = document.querySelector('#exportFiltroToggle .config-toggle-btn.active')
    return active?.dataset.value || 'todo'
}

function registrarExport(formato, cantidad, filtro) {
    const key = 'ca_export_historial'
    const historial = JSON.parse(localStorage.getItem(key) || '[]')
    historial.unshift({ formato, cantidad, filtro, fecha: new Date().toISOString() })
    localStorage.setItem(key, JSON.stringify(historial.slice(0, 8)))
    renderExportHistorial()
}

function renderExportHistorial() {
    const wrap = document.getElementById('exportHistorial')
    if (!wrap) return
    const historial = JSON.parse(localStorage.getItem('ca_export_historial') || '[]')
    if (!historial.length) {
        wrap.innerHTML = '<p class="stats-empty">Aún no has exportado ninguna lista.</p>'
        return
    }
    wrap.innerHTML = historial.map(item => {
        const fecha = new Date(item.fecha).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' })
        const icon = item.formato === 'xlsx' ? '📗' : '🧾'
        return `
            <div class="export-historial-item">
                <div class="export-historial-icon">${icon}</div>
                <div class="export-historial-info">
                    <div class="export-historial-titulo">Exportación ${item.formato.toUpperCase()}</div>
                    <div class="export-historial-meta">${item.cantidad} animes · filtro: ${item.filtro} · ${fecha}</div>
                </div>
                <span class="export-historial-formato ${item.formato}">${item.formato.toUpperCase()}</span>
            </div>`
    }).join('')
}

async function descargarArchivoExport(url, fallbackName) {
    const res = await fetch(url)
    const isJsonError = (res.headers.get('content-type') || '').includes('application/json')
    if (!res.ok) {
        const data = isJsonError ? await res.json().catch(() => ({})) : {}
        throw new Error(data.error || 'No se pudo generar la exportación')
    }
    const blob = await res.blob()
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const disp = res.headers.get('content-disposition') || ''
    const match = disp.match(/filename="?([^";]+)"?/) 
    a.href = href
    a.download = match?.[1] || fallbackName
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(href), 2000)
}

// ── EXPORTAR — cargar contadores y preview ────────────────────────────────────
function loadExportar() {
    updateListCounters()
    const active = document.querySelector('#exportFiltroToggle .config-toggle-btn.active')
    if (!active) document.querySelector('#exportFiltroToggle .config-toggle-btn')?.classList.add('active')
    renderExportPreview(getExportFiltroActivo())
    renderExportHistorial()
}

function renderExportPreview(filtro) {
    const tbody = document.getElementById('exportPreviewBody')
    if (!tbody) return
    const lista = filtro === 'todo'      ? todaLaLista()
                : filtro === 'visto'     ? state.lista.visto.map(a => ({...a, tipo:'visto'}))
                : filtro === 'pendiente' ? state.lista.pendiente.map(a => ({...a, tipo:'pendiente'}))
                : todaLaLista()
    const countEl = document.getElementById('exportPreviewCount')
    if (countEl) countEl.textContent = `(${lista.length})`
    tbody.innerHTML = lista.slice(0, 10).map((a, i) => `
        <tr>
            <td>${i+1}</td>
            <td>${escapeHTML(a.titulo||'-')}</td>
            <td style="text-transform:capitalize">${a.tipo||'-'}</td>
            <td>${a.rating ? parseFloat(a.rating).toFixed(2) : '-'}</td>
            <td>${a.episodios ? a.episodios+' ep.' : '-'}</td>
            <td>${a.agregado_en ? a.agregado_en.slice(0,10) : '-'}</td>
        </tr>
    `).join('')
}

document.querySelectorAll('#exportFiltroToggle .config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#exportFiltroToggle .config-toggle-btn').forEach(b => b.classList.remove('active'))
        btn.classList.add('active')
        renderExportPreview(btn.dataset.value || 'todo')
    })
})

document.getElementById('btnExportCSV')?.addEventListener('click', async () => {
    const filtro = getExportFiltroActivo()
    const lista = filtro === 'todo' ? todaLaLista() : todaLaLista().filter(a => a.tipo === filtro)
    const fb = document.getElementById('feedbackExport')
    if (!lista.length) {
        fb.textContent = 'No hay animes en la categoría seleccionada.'
        fb.className = 'config-feedback error'
        return
    }
    try {
        await descargarArchivoExport(`/export/xlsx?filtro=${encodeURIComponent(filtro)}`, `controlanime_${new Date().toISOString().slice(0,10)}.xlsx`)
        registrarExport('xlsx', lista.length, filtro)
        fb.textContent = `✓ ${lista.length} animes exportados.`
        fb.className = 'config-feedback ok'
    } catch (e) {
        fb.textContent = e.message || 'Error al exportar XLSX.'
        fb.className = 'config-feedback error'
    }
})

document.getElementById('btnExportJSON')?.addEventListener('click', async () => {
    const filtro = getExportFiltroActivo()
    const lista = filtro === 'todo' ? todaLaLista() : todaLaLista().filter(a => a.tipo === filtro)
    const fb = document.getElementById('feedbackExport')
    if (!lista.length) {
        fb.textContent = 'No hay animes en la categoría seleccionada.'
        fb.className = 'config-feedback error'
        return
    }
    try {
        await descargarArchivoExport(`/export/json?filtro=${encodeURIComponent(filtro)}`, `controlanime_${new Date().toISOString().slice(0,10)}.json`)
        registrarExport('json', lista.length, filtro)
        fb.textContent = `✓ ${lista.length} animes exportados en JSON.`
        fb.className = 'config-feedback ok'
    } catch (e) {
        fb.textContent = e.message || 'Error al exportar JSON.'
        fb.className = 'config-feedback error'
    }
})

// ── HEADER DEL PERFIL PÚBLICO ─────────────────────────────────────────────────
let headerState = { tipo: 'color', color: '#f97316', imagen: null }

async function loadMiHeader() {
    try {
        const res  = await fetch('/mi-perfil/header')
        const data = await res.json()
        if (res.ok) {
            headerState = data.header_imagen
                ? { tipo: 'imagen', color: '#f97316', imagen: data.header_imagen }
                : { tipo: 'color',  color: data.header_color || '#f97316', imagen: null }
            aplicarHeaderUI()
        }
    } catch(e) {}
}

function aplicarHeaderUI() {
    const colorField   = document.getElementById('headerColorField')
    const imagenField  = document.getElementById('headerImagenField')
    const colorInput   = document.getElementById('inputHeaderColor')
    const colorHex     = document.getElementById('headerColorHex')
    const imgPreview   = document.getElementById('headerImagenPreview')
    const imgPreviewEl = document.getElementById('headerImgPreviewEl')
    syncToggleGroup('headerTipoToggle', headerState.tipo)
    if (headerState.tipo === 'color') {
        if (colorField)  colorField.style.display  = 'block'
        if (imagenField) imagenField.style.display = 'none'
        if (colorInput)  colorInput.value           = headerState.color || '#f97316'
        if (colorHex)    colorHex.textContent       = headerState.color || '#f97316'
    } else {
        if (colorField)  colorField.style.display  = 'none'
        if (imagenField) imagenField.style.display = 'block'
        if (headerState.imagen && imgPreviewEl) {
            imgPreviewEl.src = headerState.imagen
            if (imgPreview) imgPreview.style.display = 'block'
        }
    }
}

document.getElementById('headerTipoToggle')?.querySelectorAll('.config-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        headerState.tipo = btn.dataset.value
        syncToggleGroup('headerTipoToggle', btn.dataset.value)
        aplicarHeaderUI()
    })
})

document.getElementById('inputHeaderColor')?.addEventListener('input', (e) => {
    const hex = document.getElementById('headerColorHex')
    if (hex) hex.textContent = e.target.value
    headerState.color = e.target.value
})

document.getElementById('btnSeleccionarHeaderImg')?.addEventListener('click', () => {
    document.getElementById('headerImagenInput')?.click()
})

document.getElementById('headerImagenInput')?.addEventListener('change', (e) => {
    const file = e.target.files[0]
    if (!file) return
    if (file.size > 3_000_000) { setFeedback('feedbackHeader', 'La imagen supera los 3MB.', 'error'); return }
    const reader = new FileReader()
    reader.onload = (ev) => {
        headerState.imagen = ev.target.result
        const imgPreview   = document.getElementById('headerImagenPreview')
        const imgPreviewEl = document.getElementById('headerImgPreviewEl')
        if (imgPreviewEl) imgPreviewEl.src = ev.target.result
        if (imgPreview)   imgPreview.style.display = 'block'
    }
    reader.readAsDataURL(file)
})

document.getElementById('btnGuardarHeader')?.addEventListener('click', async () => {
    const btn = document.getElementById('btnGuardarHeader')
    btn.disabled = true; btn.textContent = 'Guardando...'
    try {
        const body = headerState.tipo === 'color'
            ? { color: headerState.color }
            : { imagen: headerState.imagen }
        if (headerState.tipo === 'imagen' && !headerState.imagen) {
            setFeedback('feedbackHeader', 'Selecciona una imagen primero.', 'error'); return
        }
        const res  = await fetch('/perfil/header', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        const data = await res.json()
        if (!res.ok) { setFeedback('feedbackHeader', data.error || 'Error.', 'error'); return }
        // Sincronizar state.user para que el modal refleje el cambio inmediatamente
        if (headerState.tipo === 'imagen') {
            state.user.perfil_header_imagen = headerState.imagen
            state.user.perfil_header_color  = null
        } else {
            state.user.perfil_header_color  = headerState.color
            state.user.perfil_header_imagen = null
        }
        // Re-renderizar el cover del modal si está visible
        const coverEl = document.getElementById('perfilCover')
        if (coverEl) {
            if (state.user.perfil_header_imagen) {
                coverEl.style.background = `linear-gradient(180deg, rgba(10,10,10,.08), rgba(10,10,10,.75)), url(${state.user.perfil_header_imagen}) center/cover no-repeat`
            } else if (state.user.perfil_header_color) {
                coverEl.style.background = `linear-gradient(135deg, ${state.user.perfil_header_color}, #101010)`
            }
        }
        setFeedback('feedbackHeader', '✓ Header actualizado correctamente.', 'ok')
    } catch(e) {
        setFeedback('feedbackHeader', 'Error de conexión.', 'error')
    } finally {
        btn.disabled = false; btn.textContent = 'Guardar header'
    }
})

document.getElementById('btnResetHeader')?.addEventListener('click', async () => {
    const btn = document.getElementById('btnResetHeader')
    btn.disabled = true
    try {
        const res = await fetch('/perfil/header', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reset: true })
        })
        if (res.ok) {
            headerState = { tipo: 'color', color: '#f97316', imagen: null }
            state.user.perfil_header_imagen = null
            state.user.perfil_header_color  = null
            aplicarHeaderUI()
            const coverEl = document.getElementById('perfilCover')
            if (coverEl) coverEl.style.background = 'linear-gradient(135deg, #f97316 0%, #1a1a1a 100%)'
            setFeedback('feedbackHeader', '✓ Header restablecido.', 'ok')
        }
    } catch(e) {}
    finally { btn.disabled = false }
})

// Cargar header al abrir configuración
const _origRenderConfigForm = renderConfigForm
renderConfigForm = function() {
    _origRenderConfigForm()
    loadMiHeader()
}

loadAnimes()