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
        const input    = document.getElementById(this.dataset.target)
        const isHidden = input.type === 'password'
        input.type = isHidden ? 'text' : 'password'
        this.innerHTML = isHidden
            ? `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
            : `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`
    })
})

// ── HELPERS ────────────────────────────────────────────
function mostrarPanel(id) {
    ['panelLogin', 'panelEmail', 'panelCodigo', 'panelExito'].forEach(p => {
        document.getElementById(p).classList.toggle('hidden', p !== id)
    })
}

function mostrarError(id, msg) {
    const el = document.getElementById(id)
    el.textContent = msg
    el.style.display = 'block'
}

function ocultarError(id) {
    const el = document.getElementById(id)
    el.style.display = 'none'
}

function setBtnLoading(btn, loading) {
    btn.disabled = loading
    btn.style.opacity = loading ? '0.7' : '1'
}

// ── LOGIN ──────────────────────────────────────────────
const btnLogin = document.getElementById('btnLogin')
if (btnLogin) {
    btnLogin.addEventListener('click', async function() {
        const email    = document.getElementById('email').value.trim()
        const password = document.getElementById('password').value
        ocultarError('formError')

        setBtnLoading(this, true)
        try {
            const res  = await fetch('/login', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ email, password })
            })
            const data = await res.json()

            if (res.ok) {
                window.location.href = '/dashboard'
            } else {
                mostrarError('formError', data.error || 'Error al iniciar sesión')
            }
        } catch(e) {
            mostrarError('formError', 'Error de conexión. Intenta de nuevo.')
        } finally {
            setBtnLoading(this, false)
        }
    })
}

// ── RECUPERAR: navegar entre paneles ──────────────────
let emailRecuperacion = ''

document.getElementById('linkOlvide').addEventListener('click', (e) => {
    e.preventDefault()
    ocultarError('emailError')
    document.getElementById('emailRecuperar').value = ''
    mostrarPanel('panelEmail')
})

document.getElementById('btnVolverLogin').addEventListener('click', () => {
    mostrarPanel('panelLogin')
})

document.getElementById('btnVolverEmail').addEventListener('click', () => {
    ocultarError('codigoError')
    mostrarPanel('panelEmail')
})

document.getElementById('btnIrLogin').addEventListener('click', () => {
    mostrarPanel('panelLogin')
})

// ── RECUPERAR: paso 1 — enviar código ─────────────────
document.getElementById('btnEnviarCodigo').addEventListener('click', async function() {
    const email = document.getElementById('emailRecuperar').value.trim()
    ocultarError('emailError')

    if (!email) {
        mostrarError('emailError', 'Ingresa tu correo electrónico')
        return
    }

    setBtnLoading(this, true)
    try {
        const res  = await fetch('/recuperar-contrasena', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ email })
        })
        const data = await res.json()

        if (res.ok) {
            emailRecuperacion = email
            // Mostrar el email en el subtítulo del panel de código
            document.getElementById('codigoDesc').textContent =
                `Ingresa el código que enviamos a ${email}`
            // Limpiar campos del panel 3
            document.getElementById('codigoReset').value = ''
            document.getElementById('passwordNueva').value = ''
            document.getElementById('passwordConfirmar').value = ''
            ocultarError('codigoError')
            mostrarPanel('panelCodigo')
        } else {
            mostrarError('emailError', data.error || 'Error al enviar el código')
        }
    } catch(e) {
        mostrarError('emailError', 'Error de conexión. Intenta de nuevo.')
    } finally {
        setBtnLoading(this, false)
    }
})

// ── RECUPERAR: paso 2 — cambiar contraseña ────────────
document.getElementById('btnCambiarPassword').addEventListener('click', async function() {
    const codigo           = document.getElementById('codigoReset').value.trim()
    const passwordNueva    = document.getElementById('passwordNueva').value
    const passwordConfirmar = document.getElementById('passwordConfirmar').value
    ocultarError('codigoError')

    if (!codigo) {
        mostrarError('codigoError', 'Ingresa el código de verificación')
        return
    }
    if (!passwordNueva || passwordNueva.length < 8) {
        mostrarError('codigoError', 'La contraseña debe tener al menos 8 caracteres')
        return
    }
    if (passwordNueva !== passwordConfirmar) {
        mostrarError('codigoError', 'Las contraseñas no coinciden')
        return
    }

    setBtnLoading(this, true)
    try {
        const res  = await fetch('/cambiar-contrasena-reset', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                email:          emailRecuperacion,
                codigo:         codigo,
                password_nueva: passwordNueva
            })
        })
        const data = await res.json()

        if (res.ok) {
            mostrarPanel('panelExito')
        } else {
            mostrarError('codigoError', data.error || 'Código incorrecto o expirado')
        }
    } catch(e) {
        mostrarError('codigoError', 'Error de conexión. Intenta de nuevo.')
    } finally {
        setBtnLoading(this, false)
    }
})

// ── INICIO ─────────────────────────────────────────────
loadCollage()
