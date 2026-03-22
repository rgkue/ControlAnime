// ── COLLAGE ────────────────────────────────────────────
async function loadCollage() {
    try {
        const res  = await fetch('/animes/collage')
        const json = await res.json()
        const grid = document.getElementById('animeGrid')
        if (!grid) return

        const animes = json.animes || []
        animes.forEach(anime => {
            if (!anime.poster_url) return
            const img = document.createElement('img')
            img.src     = anime.poster_url
            img.alt     = anime.titulo || 'Anime'
            img.loading = 'lazy'
            grid.appendChild(img)
        })
    } catch(e) {
        console.error('Error cargando collage:', e)
    }
}

// ── TOGGLE CONTRASEÑA ──────────────────────────────────
document.querySelectorAll('.toggle-password').forEach(btn => {
    btn.addEventListener('click', function() {
        const targetId = this.dataset.target
        const input    = document.getElementById(targetId)
        const isHidden = input.type === 'password'
        input.type = isHidden ? 'text' : 'password'
        this.innerHTML = isHidden
            ? `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
            : `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`
    })
})

// ── REGISTRO ───────────────────────────────────────────
const btnRegistro = document.getElementById('btnRegistro')
if (btnRegistro) {
    btnRegistro.addEventListener('click', async function() {
        const email    = document.getElementById('email').value.trim()
        const password = document.getElementById('password').value
        const confirm  = document.getElementById('confirm').value
        const errorDiv = document.getElementById('formError')
        const exitoDiv = document.getElementById('formExito')

        // Limpiar ambos mensajes SIEMPRE al inicio
        errorDiv.style.display = 'none'
        errorDiv.textContent   = ''
        exitoDiv.style.display = 'none'
        exitoDiv.textContent   = ''

        if (password !== confirm) {
            errorDiv.textContent   = 'Las contraseñas no coinciden'
            errorDiv.style.display = 'block'
            return
        }
        if (!password.trim()) {
            errorDiv.textContent   = 'La contraseña no puede estar vacía o contener solo espacios'
            errorDiv.style.display = 'block'
            return
        }
        
                // Validar fortaleza de contraseña
        const PASSWORDS_COMUNES = new Set([
            '12345678','123456789','1234567890','password','password1',
            'qwerty123','abc12345','iloveyou','admin123','welcome1',
            'monkey123','dragon12','master12','sunshine','princess',
            'letmein1','shadow12','michael1','football','baseball1'
        ])
        if (!/[A-Z]/.test(password)) {
            errorDiv.textContent   = 'La contraseña debe tener al menos una letra mayúscula'
            errorDiv.style.display = 'block'
            return
        }
        if (!/[0-9]/.test(password)) {
            errorDiv.textContent   = 'La contraseña debe tener al menos un número'
            errorDiv.style.display = 'block'
            return
        }
        if (!/[!@#$%^&*(),.?":{}|<>_\-+=\/\\`~\[\];']/.test(password)) {
            errorDiv.textContent   = 'La contraseña debe tener al menos un carácter especial (!@#$...)'
            errorDiv.style.display = 'block'
            return
        }
        if (PASSWORDS_COMUNES.has(password.toLowerCase())) {
            errorDiv.textContent   = 'La contraseña es demasiado común, elige una más segura'
            errorDiv.style.display = 'block'
            return
        }

        const chkTerminos = document.getElementById('chkTerminos')
        const termsError  = document.getElementById('termsError')
        if (!chkTerminos.checked) {
            termsError.style.display = 'block'
            chkTerminos.closest('.terms-check').style.color = '#fca5a5'
            return
        }
        termsError.style.display = 'none'

        // Deshabilitar botón para evitar doble envío
        this.disabled    = true
        this.style.opacity = '0.7'

        try {
            const res  = await fetch('/register', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ email, password })
            })
            const data = await res.json()

            if (res.ok) {
                exitoDiv.textContent   = '¡Cuenta creada correctamente! Redirigiendo...'
                exitoDiv.style.display = 'block'
                setTimeout(() => window.location.href = '/verify-email', 1500)
            } else {
                let msg = 'Error al crear la cuenta'
                if (data.error) {
                    msg = data.error
                } else if (data.detail) {
                    const d = Array.isArray(data.detail) ? data.detail[0] : data.detail
                    msg = d?.msg || d?.message || msg
                    msg = msg.replace(/^value error,\s*/i, '')
                }
                errorDiv.textContent   = msg
                errorDiv.style.display = 'block'
            }
        } catch(e) {
            errorDiv.textContent   = 'Error de conexión. Intenta de nuevo.'
            errorDiv.style.display = 'block'
        } finally {
            // Re-habilitar botón siempre
            this.disabled      = false
            this.style.opacity = '1'
        }
    })
}   

// ── INICIO ─────────────────────────────────────────────
loadCollage()

// ── MODALES LEGALES ────────────────────────────────────
function openModal(id) {
    const m = document.getElementById(id)
    if (!m) return
    m.classList.add('open')
    document.body.style.overflow = 'hidden'
}
function closeModal(id) {
    const m = document.getElementById(id)
    if (!m) return
    m.classList.remove('open')
    document.body.style.overflow = ''
}
function closeModalOutside(e, id) {
    if (e.target.id === id) closeModal(id)
}
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open').forEach(m => {
            m.classList.remove('open')
            document.body.style.overflow = ''
        })
    }
})
// Ocultar error de términos al marcar el checkbox
document.getElementById('chkTerminos')?.addEventListener('change', function() {
    if (this.checked) {
        document.getElementById('termsError').style.display = 'none'
        this.closest('.terms-check').style.color = ''
    }
})