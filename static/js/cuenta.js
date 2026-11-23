/* SIFAT - Mi cuenta. Cambiar la contraseña propia */
(() => {
  'use strict';

  const { $, $$, api, mostrarError, recargarCon, reglasContrasena, pintarReglas } = window.SIFAT;

  const form = $('#form-cuenta');
  if (!form) return;
  const err = $('#cuenta-error');
  const btn = $('#cuenta-submit');

  const reglas = () => reglasContrasena($('#c-nueva').value, {
    nombre: form.dataset.nombre, email: form.dataset.email, confirmacion: $('#c-nueva2').value });
  ['#c-nueva', '#c-nueva2'].forEach((s) => $(s).addEventListener('input', () => pintarReglas($('#c-reglas'), reglas())));
  pintarReglas($('#c-reglas'), reglas());

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    const actual = $('#c-actual').value;
    const r = reglas();
    const malos = [];
    if (!actual) malos.push(['#c-actual', 'contraseña actual']);
    if (!r.largo || !r.letras || !r.personal) malos.push(['#c-nueva', 'contraseña nueva']);
    if (!r.igual) malos.push(['#c-nueva2', 'confirmación']);
    if (actual && actual === $('#c-nueva').value) malos.push(['#c-nueva', 'la nueva debe ser distinta a la actual']);
    if (malos.length) {
      malos.forEach(([sel]) => $(sel).setAttribute('aria-invalid', 'true'));
      mostrarError(err, 'Revisa: ' + [...new Set(malos.map(([, n]) => n))].join(', '));
      $(malos[0][0]).focus();
      return;
    }
    err.classList.add('hidden');
    btn.disabled = true; btn.textContent = 'Cambiando…';
    try {
      await api('POST', '/api/cuenta/contrasena',
        { actual, nueva: $('#c-nueva').value, confirmacion: $('#c-nueva2').value });
      recargarCon('Contraseña cambiada. Úsala la próxima vez que inicies sesión');
    } catch (ex) {
      mostrarError(err, ex.message);
      btn.disabled = false; btn.textContent = 'Cambiar contraseña';
    }
  });
})();
