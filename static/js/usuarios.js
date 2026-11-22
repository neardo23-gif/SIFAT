/* SIFAT - Usuarios. Alta de personas con validación en vivo (las mismas reglas que el servidor) */
(() => {
  'use strict';

  const { $, $$, api, mostrarError, recargarCon, openDialog } = window.SIFAT;

  const dlg = $('#dlg-usuario');
  if (!dlg) return;
  const form = $('#form-usuario');
  const err = $('#usr-error');
  const btn = $('#usr-submit');

  // Letras (con acentos, ñ y ü) separadas por un espacio, guion o apóstrofo
  const NOMBRE_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:[ '-][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*$/;
  const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,120}\.[A-Za-z]{2,24}$/;
  const espacios = (s) => s.replace(/\s+/g, ' ').trim();

  function leer() {
    return {
      nombre: espacios($('#u-nombre').value),
      apellidos: espacios($('#u-apellidos').value),
      email: $('#u-email').value.trim().toLowerCase(),
      rol: $('#u-rol').value,
      password: $('#u-pass').value,
      confirmacion: $('#u-pass2').value,
    };
  }

  /** Reglas de la contraseña. Devuelve {regla: cumple}. */
  function reglas(d) {
    const p = d.password; const t = p.toLowerCase();
    const usuarioCorreo = d.email.split('@')[0];
    const nombre = d.nombre.toLowerCase();
    return {
      largo: p.length >= 12,
      letras: /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/.test(p) && /\d/.test(p),
      personal: p.length > 0 && !(usuarioCorreo.length >= 4 && t.includes(usuarioCorreo))
        && !(nombre.length >= 4 && t.includes(nombre)) && new Set(p).size >= 5,
      igual: p.length > 0 && p === d.confirmacion,
    };
  }

  function pintarReglas() {
    const r = reglas(leer());
    $$('#u-reglas [data-regla]').forEach((li) => {
      const ok = r[li.dataset.regla];
      li.textContent = (ok ? '✓ ' : '○ ') + li.textContent.slice(2);
      li.classList.toggle('text-soft', ok);
      li.classList.toggle('text-mute', !ok);
    });
  }
  ['#u-pass', '#u-pass2', '#u-nombre', '#u-email'].forEach((s) => $(s).addEventListener('input', pintarReglas));

  function validar(d) {
    const malos = [];
    if (d.nombre.length < 2 || !NOMBRE_RE.test(d.nombre)) malos.push(['#u-nombre', 'nombre']);
    if (d.apellidos.length < 2 || !NOMBRE_RE.test(d.apellidos)) malos.push(['#u-apellidos', 'apellidos']);
    if (`${d.nombre} ${d.apellidos}`.length > 100) malos.push(['#u-apellidos', 'nombre completo (máximo 100)']);
    if (!EMAIL_RE.test(d.email)) malos.push(['#u-email', 'correo']);
    const r = reglas(d);
    if (!r.largo || !r.letras || !r.personal) malos.push(['#u-pass', 'contraseña']);
    if (!r.igual) malos.push(['#u-pass2', 'confirmación de la contraseña']);
    return malos;
  }

  function abrir() {
    form.reset();
    err.classList.add('hidden');
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    $$('[data-toggle-pass]', form).forEach((b) => {
      $('#' + b.dataset.togglePass).type = 'password';
      b.setAttribute('aria-pressed', 'false');
    });
    btn.disabled = false; btn.textContent = 'Registrar usuario';
    pintarReglas();
    openDialog(dlg);
    $('#u-nombre').focus();
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const d = leer();
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    const malos = validar(d);
    if (malos.length) {
      malos.forEach(([sel]) => $(sel).setAttribute('aria-invalid', 'true'));
      mostrarError(err, 'Revisa estos datos: ' + [...new Set(malos.map(([, n]) => n))].join(', '));
      $(malos[0][0]).focus();
      return;
    }
    err.classList.add('hidden');
    btn.disabled = true; btn.textContent = 'Registrando…';
    try {
      const u = await api('POST', '/api/usuarios', d);
      recargarCon(`${u.nombre} ya puede iniciar sesión con ${u.email}`);
    } catch (ex) {
      mostrarError(err, ex.message);
      btn.disabled = false; btn.textContent = 'Registrar usuario';
    }
  });

  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-action="nuevo-usuario"]')) abrir();
  });
})();
