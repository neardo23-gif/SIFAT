/* SIFAT - utilidades compartidas por todas las pantallas. Sin dependencias.
   Se carga primero; cada pantalla usa lo que expone en window.SIFAT. */
(() => {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' });
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';

  /** Crea un elemento sin usar innerHTML (los datos vienen de la API). */
  function h(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
  }

  /* ---------------- toasts ---------------- */
  function toast(message, isError = false) {
    const host = $('#toasts');
    if (!host) return;
    const t = h('div', 'toast' + (isError ? ' is-error' : ''), message);
    host.appendChild(t);
    setTimeout(() => {
      t.classList.add('is-out');
      setTimeout(() => t.remove(), 200);
    }, 3600);
  }
  try {
    const pending = sessionStorage.getItem('sifat-toast');
    if (pending) { sessionStorage.removeItem('sifat-toast'); toast(pending); }
  } catch (_) { /* almacenamiento no disponible */ }

  /* ---------------- entradas al hacer scroll ---------------- */
  const revealEls = $$('[data-reveal]');
  if (revealEls.length) {
    if (reduceMotion || !('IntersectionObserver' in window)) {
      revealEls.forEach((el) => el.classList.add('is-in'));
    } else {
      revealEls.forEach((el) => {
        const siblings = $$('[data-reveal]', el.parentElement).filter((s) => s.parentElement === el.parentElement);
        const i = Math.max(0, siblings.indexOf(el));
        el.style.setProperty('--d', Math.min(i, 3) * 70 + 'ms');
      });
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target;
          el.classList.add('is-in');
          io.unobserve(el);
          if (el.classList.contains('lift')) {
            setTimeout(() => el.classList.add('settled'), 700);
          }
        });
      }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
      revealEls.forEach((el) => io.observe(el));
    }
  }

  /* ---------------- mostrar / ocultar contraseña ---------------- */
  $$('[data-toggle-pass]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.togglePass);
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(show));
      btn.setAttribute('aria-label', show ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  });

  /* ---------------- modales ---------------- */
  function openDialog(dlg) {
    if (!dlg.open) dlg.showModal();
  }
  function closeDialog(dlg) {
    if (dlg.open) dlg.close();
  }
  $$('dialog.modal').forEach((dlg) => {
    // clic en el fondo cierra
    dlg.addEventListener('click', (e) => { if (e.target === dlg) closeDialog(dlg); });
    $$('[data-close]', dlg).forEach((b) => b.addEventListener('click', () => closeDialog(dlg)));
  });

  /* ---------------- peticiones al servidor del front ---------------- */
  /** Llama a /api/... con el token CSRF. Devuelve el JSON o lanza Error con el mensaje. */
  async function api(method, url, body) {
    const opts = { method, headers: { 'X-CSRF-Token': csrf } };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(url, opts);
    } catch (_) {
      throw new Error('No hay conexión con el servidor. Revisa tu red e intenta de nuevo');
    }
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) throw new Error('Tu sesión terminó. Recarga la página e inicia sesión');
    if (!res.ok) throw new Error(data.mensaje || `Error ${res.status}`);
    return data;
  }

  function mostrarError(box, mensaje) {
    box.textContent = mensaje.endsWith('.') ? mensaje : mensaje + '.';
    box.classList.remove('hidden');
  }

  /** Recarga la página y muestra un aviso al volver. */
  function recargarCon(mensaje) {
    try { sessionStorage.setItem('sifat-toast', mensaje); } catch (_) {}
    location.reload();
  }

  function leerJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  /** Texto decimal con hasta 2 decimales ("12", "12.5", "12.50"). */
  const DECIMAL_RE = /^\d+(\.\d{1,2})?$/;

  /* ---------------- reglas de contraseña (las mismas que revisa el servidor) ---------------- */
  /** Devuelve {largo, letras, personal, igual}: true si se cumple cada regla. */
  // Minúsculas y sin acentos, para que "Pérez" y "perez" cuenten igual
  const plano = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

  function reglasContrasena(p, { nombre = '', email = '', confirmacion = '' } = {}) {
    const t = plano(p);
    const usuarioCorreo = plano(email).split('@')[0];
    const partes = plano(nombre).replace(/-/g, ' ').split(/\s+/).filter((x) => x.length >= 4);
    return {
      largo: p.length >= 12,
      letras: /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/.test(p) && /\d/.test(p),
      personal: p.length > 0 && !(usuarioCorreo.length >= 4 && t.includes(usuarioCorreo))
        && !partes.some((x) => t.includes(x)) && new Set(p).size >= 5,
      igual: p.length > 0 && p === confirmacion,
    };
  }

  /** Marca con ✓ u ○ cada <li data-regla="..."> de la lista según las reglas. */
  function pintarReglas(lista, reglas) {
    $$('[data-regla]', lista).forEach((li) => {
      const ok = reglas[li.dataset.regla];
      li.textContent = (ok ? '✓ ' : '○ ') + li.textContent.slice(2);
      li.classList.toggle('text-soft', ok);
      li.classList.toggle('text-mute', !ok);
    });
  }

  window.SIFAT = Object.freeze({
    $, $$, h, money, csrf, toast, api, mostrarError, recargarCon, leerJSON, DECIMAL_RE,
    openDialog, closeDialog, reglasContrasena, pintarReglas,
  });
})();
