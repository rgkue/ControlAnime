const digits   = document.querySelectorAll('.code-digit')
const btnVer   = document.getElementById('btnVerificar')
const btnRenv  = document.getElementById('btnReenviar')
const errorDiv = document.getElementById('formError')
const exitoDiv = document.getElementById('formExito')

// ── NAVEGACIÓN ENTRE DÍGITOS ───────────────────────────
digits.forEach((input, i) => {
    input.addEventListener('input', () => {
        input.value = input.value.replace(/\D/g, '')
        input.classList.toggle('filled', input.value !== '')
        if (input.value && i < digits.length - 1) {
            digits[i + 1].focus()
        }
    })

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !input.value && i > 0) {
            digits[i - 1].focus()
            digits[i - 1].value = ''
            digits[i - 1].classList.remove('filled')
        }
    })

    // Pegar código completo
    input.addEventListener('paste', (e) => {
        e.preventDefault()
        const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
        pasted.split('').forEach((char, j) => {
            if (digits[j]) {
                digits[j].value = char
                digits[j].classList.add('filled')
            }
        })
        const lastFilled = Math.min(pasted.length, digits.length - 1)
        digits[lastFilled].focus()
    })
})

function getCodigo() {
    return Array.from(digits).map(d => d.value).join('')
}

function mostrarError(msg) {
    exitoDiv.style.display = 'none'
    errorDiv.textContent   = msg
    errorDiv.style.display = 'block'
}

function mostrarExito(msg) {
    errorDiv.style.display = 'none'
    exitoDiv.textContent   = msg
    exitoDiv.style.display = 'block'
}

// ── VERIFICAR ──────────────────────────────────────────
btnVer.addEventListener('click', async () => {
    const codigo = getCodigo()

    if (codigo.length < 6) {
        mostrarError('Ingresa los 6 dígitos del código')
        return
    }

    btnVer.disabled     = true
    btnVer.textContent  = 'Verificando...'
    errorDiv.style.display = 'none'

    try {
        const res  = await fetch('/verify-email', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ codigo })
        })

        const data = await res.json()

        if (res.ok) {
            mostrarExito('¡Cuenta verificada! Redirigiendo...')
            setTimeout(() => window.location.href = '/dashboard', 1800)
        } else {
            mostrarError(data.error || 'Código incorrecto')
            btnVer.disabled    = false
            btnVer.textContent = 'Verificar cuenta'
        }
    } catch(e) {
        mostrarError('Error de conexión, intenta de nuevo')
        btnVer.disabled    = false
        btnVer.textContent = 'Verificar cuenta'
    }
})

// ── REENVIAR ───────────────────────────────────────────
btnRenv.addEventListener('click', async (e) => {
    e.preventDefault()
    btnRenv.classList.add('disabled')
    btnRenv.textContent = 'Enviando...'

    try {
        const res  = await fetch('/resend-verification', { method: 'POST' })
        const data = await res.json()

        if (res.ok) {
            mostrarExito('Código reenviado a tu correo')
        } else {
            mostrarError(data.error || 'No se pudo reenviar')
        }
    } catch(e) {
        mostrarError('Error de conexión')
    }

    // Cooldown 60 segundos
    let segundos = 60
    const interval = setInterval(() => {
        btnRenv.textContent = `Reenviar (${segundos}s)`
        segundos--
        if (segundos < 0) {
            clearInterval(interval)
            btnRenv.textContent = 'Reenviar'
            btnRenv.classList.remove('disabled')
        }
    }, 1000)
})
