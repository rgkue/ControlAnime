// HEADER scroll
window.addEventListener('scroll', () => {
    document.getElementById('header').classList.toggle('scrolled', window.scrollY > 40)
})

// REVEAL on scroll
const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible') })
}, { threshold: 0.1 })

document.querySelectorAll('.reveal').forEach(el => observer.observe(el))

// CARRUSEL
const _cacheTrad = {};
const slidesEl = document.getElementById('slides');
const dotsEl = document.getElementById('dots');
let currentSlide = 0;
let slides = [];
let autoplay;

function buildSlide(anime) {
    const cover    = anime.cover_url || ''
    const title    = anime.titulo || 'Sin título'
    const synopsis = anime.sinopsis || ''
    const rating   = anime.rating ? anime.rating.toFixed(1) : null

    const div = document.createElement('div')
    div.className = 'slide'
    div.style.backgroundImage = `url(${cover})`
    div.innerHTML = `
        <div class="slide-overlay"></div>
        <div class="slide-overlay-bottom"></div>
        <div class="slide-content">
            <div class="slide-genre">Anime destacado</div>
            <div class="slide-title">${title}</div>
            <div class="slide-synopsis">${synopsis}</div>
            ${rating ? `<div class="slide-rating">★ ${rating} / 10</div>` : ''}
        </div>
    `
    return div
}

function goTo(n) {
    slides[currentSlide]?.classList.remove('active')
    document.querySelectorAll('.dot').forEach((d, i) => d.classList.toggle('active', i === n))
    currentSlide = n
    slidesEl.style.transform = `translateX(-${n * 100}%)`
    slides[currentSlide]?.classList.add('active')
}

function startAutoplay() {
    clearInterval(autoplay)
    autoplay = setInterval(() => goTo((currentSlide + 1) % slides.length), 6000)
}

async function loadHero() {
    try {
        const res = await fetch('/animes/hero');
        const data = await res.json();
        const animes = data.animes || [];

        slidesEl.innerHTML = '';
        dotsEl.innerHTML = '';
        slides = [];

        for (let i = 0; i < animes.length; i++) {
            const anime = animes[i];
            const slide = buildSlide(anime);
            slidesEl.appendChild(slide);
            slides.push(slide);

            const synopsisEl = slide.querySelector('.slide-synopsis');

            if (synopsisEl) {
                if (anime.sinopsis_es) {
                    // ✅ Ya traducida en BD — mostrar directamente, sin llamar MyMemory
                    synopsisEl.innerText = anime.sinopsis_es;
                } else if (anime.sinopsis) {
                    // ⚠️ Sin traducción cacheada — intentar MyMemory como fallback
                    traducirSinopsis(anime.sinopsis).then(traducido => {
                        if (traducido) synopsisEl.innerText = traducido;
                    });
                }
            }

            const dot = document.createElement('div');
            dot.className = 'dot' + (i === 0 ? ' active' : '');
            dot.addEventListener('click', () => { goTo(i); startAutoplay(); });
            dotsEl.appendChild(dot);
        }

        if (slides.length > 0) {
            slides[0].classList.add('active');
            startAutoplay();
        }

        // Imágenes del about
        animes.slice(0, 3).forEach((anime, i) => {
            const img = document.getElementById(`aboutImg${i + 1}`);
            if (img) { img.src = anime.poster_url || ''; img.alt = anime.titulo || ''; }
        });

        document.getElementById('statAnimes').textContent = animes.length > 0 ? '10K+' : '—';

    } catch (e) { console.error('Error:', e); }
}

// ── TRADUCCIÓN SINOPSIS (fallback — solo si backend no pudo cachear) ──────────
async function traducirSinopsis(texto) {
    if (!texto) return null;
    if (_cacheTrad[texto]) return _cacheTrad[texto];

    try {
        const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(texto.slice(0, 500))}&langpair=en|es`;
        const res  = await fetch(url);
        const data = await res.json();
        let trad = data?.responseData?.translatedText;

        // No cachear el warning de límite diario
        if (!trad || trad.toUpperCase().includes('MYMEMORY WARNING')) return null;

        if (trad !== texto) {
            // Limpiar HTML entities (e.g. &quot; &#39;)
            const aux = document.createElement('textarea');
            aux.innerHTML = trad;
            trad = aux.value;

            _cacheTrad[texto] = trad;
            return trad;
        }
    } catch (e) {
        console.error('Error en traducción:', e);
    }
    return null;
}

loadHero()

// MODALES LEGALES
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