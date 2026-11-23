/* SIFAT - Usuarios. Alta, restablecer contraseña y activar/desactivar (mismas reglas que el servidor) */
(() => {
  'use strict';

  const { $, $$, api, mostrarError, recargarCon, openDialog, reglasContrasena, pintarReglas } = window.SIFAT;

  const dlg = $('#dlg-usuario');
  if (!dlg) return;

  // Letras (con acentos, ñ y ü) separadas por un espacio, guion o apóstrofo
  const NOMBRE_RE = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:[ '-][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*$/;
  const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,120}\.[A-Za-z]{2,24}$/;
  const espacios = (s) => s.replace(/\s+/g, ' ').trim();

  /** Deja un formulario como nuevo: sin errores y con las contraseñas ocultas. */
  function limpiar(form, err) {
    form.reset();
    err.classList.add('hidden');
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    $$('[data-toggle-pass]', form).forEach((b) => {
      $('#' + b.dataset.togglePass).type = 'password';
      b.setAttribute('aria-pressed', 'false');
    });
  }

  function marcar(malos, err) {
    malos.forEach(([sel]) => $(sel).setAttribute('aria-invalid', 'true'));
    mostrarError(err, 'Revisa estos datos: ' + [...new Set(malos.map(([, n]) => n))].join(', '));
    $(malos[0][0]).focus();
  }

  /* ---------------- alta ---------------- */
  const form = $('#form-usuario');
  const err = $('#usr-error');
  const btn = $('#usr-submit');

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
  const reglasAlta = (d) => reglasContrasena(d.password, {
    nombre: `${d.nombre} ${d.apellidos}`, email: d.email, confirmacion: d.confirmacion });
  const repintarAlta = () => pintarReglas($('#u-reglas'), reglasAlta(leer()));
  ['#u-pass', '#u-pass2', '#u-nombre', '#u-apellidos', '#u-email'].forEach((s) => $(s).addEventListener('input', repintarAlta));

  function validar(d) {
    const malos = [];
    if (d.nombre.length < 2 || !NOMBRE_RE.test(d.nombre)) malos.push(['#u-nombre', 'nombre']);
    if (d.apellidos.length < 2 || !NOMBRE_RE.test(d.apellidos)) malos.push(['#u-apellidos', 'apellidos']);
    if (`${d.nombre} ${d.apellidos}`.length > 100) malos.push(['#u-apellidos', 'nombre completo (máximo 100)']);
    if (!EMAIL_RE.test(d.email)) malos.push(['#u-email', 'correo']);
    const r = reglasAlta(d);
    if (!r.largo || !r.letras || !r.personal) malos.push(['#u-pass', 'contraseña']);
    if (!r.igual) malos.push(['#u-pass2', 'confirmación de la contraseña']);
    return malos;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const d = leer();
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    const malos = validar(d);
    if (malos.length) { marcar(malos, err); return; }
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

  /* ---------------- restablecer contraseña ---------------- */
  const dlgRes = $('#dlg-restablecer');
  const formRes = $('#form-restablecer');
  const errRes = $('#res-error');
  const btnRes = $('#res-submit');
  let elegido = null;

  const reglasRes = () => reglasContrasena($('#r-pass').value, {
    nombre: elegido?.nombre || '', email: elegido?.email || '', confirmacion: $('#r-pass2').value });
  ['#r-pass', '#r-pass2'].forEach((s) => $(s).addEventListener('input', () => pintarReglas($('#r-reglas'), reglasRes())));

  formRes.addEventListener('submit', async (e) => {
    e.preventDefault();
    const r = reglasRes();
    $$('.field', formRes).forEach((f) => f.removeAttribute('aria-invalid'));
    const malos = [];
    if (!r.largo || !r.letras || !r.personal) malos.push(['#r-pass', 'contraseña']);
    if (!r.igual) malos.push(['#r-pass2', 'confirmación de la contraseña']);
    if (malos.length) { marcar(malos, errRes); return; }
    btnRes.disabled = true; btnRes.textContent = 'Guardando…';
    try {
      await api('POST', `/api/usuarios/${elegido.id}/contrasena`,
        { password: $('#r-pass').value, confirmacion: $('#r-pass2').value });
      recargarCon(`Contraseña de ${elegido.nombre} actualizada`);
    } catch (ex) {
      mostrarError(errRes, ex.message);
      btnRes.disabled = false; btnRes.textContent = 'Guardar contraseña';
    }
  });

  /* ---------------- activar / desactivar ---------------- */
  const dlgEst = $('#dlg-estado');
  const errEst = $('#est-error');
  const btnEst = $('#est-submit');

  $('#form-estado').addEventListener('submit', async (e) => {
    e.preventDefault();
    const activar = !elegido.activo;
    btnEst.disabled = true; btnEst.textContent = activar ? 'Activando…' : 'Desactivando…';
    try {
      await api('PATCH', `/api/usuarios/${elegido.id}`, { activo: activar });
      recargarCon(activar ? `${elegido.nombre} puede volver a entrar` : `${elegido.nombre} ya no puede entrar`);
    } catch (ex) {
      mostrarError(errEst, ex.message);
      btnEst.disabled = false; btnEst.textContent = activar ? 'Activar' : 'Desactivar';
    }
  });

  /* ---------------- acciones ---------------- */
  function desdeBoton(b) {
    return { id: b.dataset.id, nombre: b.dataset.nombre, email: b.dataset.email, activo: b.dataset.activo === 'true' };
  }

  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-action]');
    if (!a) return;
    switch (a.dataset.action) {
      case 'nuevo-usuario':
        limpiar(form, err);
        btn.disabled = false; btn.textContent = 'Registrar usuario';
        repintarAlta();
        openDialog(dlg);
        $('#u-nombre').focus();
        break;
      case 'restablecer':
        elegido = desdeBoton(a);
        limpiar(formRes, errRes);
        $('#res-nombre').textContent = elegido.nombre;
        btnRes.disabled = false; btnRes.textContent = 'Guardar contraseña';
        pintarReglas($('#r-reglas'), reglasRes());
        openDialog(dlgRes);
        $('#r-pass').focus();
        break;
      case 'cambiar-estado': {
        elegido = desdeBoton(a);
        const activar = !elegido.activo;
        errEst.classList.add('hidden');
        $('#est-titulo').textContent = activar ? `¿Activar a ${elegido.nombre}?` : `¿Desactivar a ${elegido.nombre}?`;
        $('#est-texto').textContent = activar
          ? 'Podrá volver a iniciar sesión con su correo y contraseña.'
          : 'Ya no podrá iniciar sesión, y si está dentro de la app perderá el acceso en unos minutos. Sus facturas se conservan.';
        btnEst.className = 'btn ' + (activar ? 'btn-primary' : 'btn-danger');
        btnEst.disabled = false; btnEst.textContent = activar ? 'Activar' : 'Desactivar';
        openDialog(dlgEst);
        break;
      }
      default: break;
    }
  });

})();
