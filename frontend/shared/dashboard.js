// ═══════════════════════════════════════════════════════════════════
// frontend/shared/dashboard.js
// Módulo compartido — ControlAnime Dashboard
// Incluir en todas las páginas del dashboard ANTES del script propio.
// ═══════════════════════════════════════════════════════════════════

// ── ESTADO COMPARTIDO ────────────────────────────────────────────
const state = {
    user: {
        email: '', username: '', miembroDesde: '', foto: null,
        perfil_publico: false, instagram: '', discord: '', tiktok: '',
        perfil_header_color: null, perfil_header_imagen: null,
    },
    lista: { visto: [], pendiente: [] },
}

// ── INTERCEPTOR GLOBAL DE SESIÓN Y CSRF ─────────────────────────
;(function() {
    const _fetch = window.fetch
    const RUTAS_EXCLUIDAS  = ['/login', '/logout', '/register', '/verify-email']
    const METODOS_MUTANTES = ['POST', 'PUT', 'PATCH', 'DELETE']

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)
        return match ? decodeURIComponent(match[1]) : null
    }

    window.fetch = async function(...args) {
        let [input, init = {}] = args
        const method = (init.method || 'GET').toUpperCase()
        if (METODOS_MUTANTES.includes(method)) {
            const csrf = getCsrfToken()
            if (csrf) init = { ...init, headers: { ...(init.headers || {}), 'X-CSRF-Token': csrf } }
        }
        const res = await _fetch(input, init)
        const url = typeof input === 'string' ? input : (input?.url || '')
        if (res.status === 401) {
            const esExcluida = RUTAS_EXCLUIDAS.some(r => url.includes(r))
            if (!esExcluida) setTimeout(() => { window.location.href = '/login' }, 150)
        }
        if (res.status === 403) console.warn('[CSRF] 403 en', url)
        return res
    }
})()

// ── HELPERS FECHA ────────────────────────────────────────────────
function parseFecha(str) {
    if (!str) return null
    const clean = str.replace(' ', 'T').split('.')[0]
    const d = new Date(clean)
    return isNaN(d.getTime()) ? null : d
}

function fechaRelativa(str) {
    const d = parseFecha(str)
    if (!d) return ''
    const dias = Math.floor((new Date() - d) / 86400000)
    if (dias === 0) return 'Hoy'
    if (dias === 1) return 'Ayer'
    if (dias < 30)  return `Hace ${dias} días`
    if (dias < 365) return `Hace ${Math.floor(dias/30)} mes${Math.floor(dias/30)>1?'es':''}`
    return `Hace ${Math.floor(dias/365)} año${Math.floor(dias/365)>1?'s':''}`
}

// ── UTILIDADES DOM ───────────────────────────────────────────────
function setTextIfExists(id, val) { const el=document.getElementById(id); if(el) el.textContent=val }
function escapeHTML(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}
function tipoListaLabel(tipo) { return tipo==='visto'?'✓ Visto':'⏳ Pendiente' }
function colorGenero(i) { return ['var(--accent)','#60a5fa','#f472b6','#34d399','#fbbf24'][i%5] }

// ── SIDEBAR ──────────────────────────────────────────────────────
function initSidebar() {
    const sidebar     = document.getElementById('sidebar')
    const collapseBtn = document.getElementById('collapseBtn')
    if (!sidebar || !collapseBtn) return

    // Restaurar estado colapsado
    if (localStorage.getItem('sidebarCollapsed') === 'true') sidebar.classList.add('collapsed')

    collapseBtn.addEventListener('click', () => {
        const c = sidebar.classList.toggle('collapsed')
        localStorage.setItem('sidebarCollapsed', c)
    })

    // Marcar activo según pathname actual (rutas reales SPA)
    const path = window.location.pathname
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
        const sec = item.dataset.section
        const itemPath = sec === 'inicio' ? '/dashboard' : `/dashboard/${sec}`
        item.classList.toggle('active', path === itemPath || path.startsWith(itemPath + '/'))
    })
}

// ── CARGAR USUARIO (topbar) ──────────────────────────────────────
async function loadUserChip() {
    try {
        const res = await fetch('/me')
        if (!res.ok) { window.location.href = '/login'; return null }
        const data = await res.json()

        state.user.email                = data.email
        state.user.username             = data.username || ''
        state.user.foto                 = data.foto_perfil || null
        state.user.perfil_publico       = data.perfil_publico || false
        state.user.instagram            = data.instagram || ''
        state.user.discord              = data.discord   || ''
        state.user.tiktok               = data.tiktok    || ''
        state.user.perfil_header_color  = data.perfil_header_color  || null
        state.user.perfil_header_imagen = data.perfil_header_imagen || null
        state.user.miembroDesde = data.creado_en
            ? (parseFecha(data.creado_en)||new Date()).toLocaleDateString('es-ES',{year:'numeric',month:'long'})
            : '—'

        const displayName = data.username || data.email.split('@')[0]

        const emailEl  = document.getElementById('userEmail')
        const avatarEl = document.getElementById('userAvatar')
        if (emailEl)  emailEl.textContent = data.email
        if (avatarEl) {
            avatarEl.innerHTML = data.foto_perfil
                ? `<img src="${data.foto_perfil}" alt="avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`
                : displayName[0].toUpperCase()
        }

        if (data.lista) state.lista = data.lista
        return data
    } catch(e) {
        window.location.href = '/login'
        return null
    }
}

// ── LOGOUT ───────────────────────────────────────────────────────
async function logout() {
    try { await fetch('/logout', { method: 'POST' }) } catch(e) {}
    window.location.href = '/login'
}

// ── NAVEGACIÓN A FICHA DE ANIME ──────────────────────────────────
function irAAnime(anime) {
    if (!anime?.id) return
    const normalized = {
        id:        String(anime.id),
        titulo:    anime.titulo    || anime.attributes?.canonicalTitle || anime.canonicalTitle || 'Sin título',
        cover_url: anime.cover_url || anime.attributes?.coverImage?.original || anime.attributes?.coverImage?.large || '',
        poster_url:anime.poster_url|| anime.attributes?.posterImage?.medium  || anime.attributes?.posterImage?.small || '',
        rating:    anime.rating    || anime.attributes?.averageRating || '',
        episodios: anime.episodios || anime.attributes?.episodeCount  || null,
        sinopsis:  anime.sinopsis  || anime.attributes?.synopsis || '',
        genres:    anime.genres    || '', genres:    anime.genres    || '',
        genres_es: anime.genres_es || '',
        sinopsis_es: anime.sinopsis_es || '',
        estado:    anime.estado    || anime.attributes?.status   || '',
        año:       anime.año       || (anime.attributes?.startDate || '').slice(0,4) || '',
        tipo:      anime.tipo      || anime.attributes?.subtype  || '',
    }
    sessionStorage.setItem('animeData', JSON.stringify(normalized))
    window.location.href = `/dashboard/anime/${normalized.id}`
}

// ── TOPBAR HTML ──────────────────────────────────────────────────
// Inyecta el contenido del topbar si el elemento #pageTopbar existe.
// Las páginas que usan su propio topbar no necesitan llamar esto.
function initTopbar(title) {
    const topbar = document.getElementById('pageTopbar')
    if (!topbar) return
    topbar.innerHTML = `
        <div class="page-topbar-left">
            <span class="page-topbar-title">${escapeHTML(title)}</span>
        </div>
        <div class="user-chip" id="userChip"
             onclick="window.location.href='/dashboard/configuracion'"
             style="cursor:pointer;display:flex;align-items:center;gap:10px;
                    background:var(--surface2);border:1px solid var(--border);
                    border-radius:40px;padding:6px 14px 6px 6px;">
            <div class="user-avatar" id="userAvatar"
                 style="width:30px;height:30px;border-radius:50%;background:var(--accent);
                        color:#000;font-weight:600;font-size:13px;display:flex;
                        align-items:center;justify-content:center;overflow:hidden;flex-shrink:0;">
            </div>
            <span class="user-email" id="userEmail"
                  style="font-size:13px;color:var(--muted);max-width:180px;
                         overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                Cargando...
            </span>
        </div>
    `
}

// ── INIT AUTOMÁTICO ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => { initSidebar() })
