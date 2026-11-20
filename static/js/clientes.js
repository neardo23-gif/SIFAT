/* SIFAT - Clientes. Alta y edición */
(() => {
  'use strict';

  const { $, $$, api, mostrarError, recargarCon, leerJSON, openDialog, closeDialog } = window.SIFAT;

  (function clientes() {
    const dlg = $('#dlg-cliente');
    if (!dlg) return;
    const lista = leerJSON('clientes-data') || [];
    const porId = new Map(lista.map((c) => [String(c.id_cliente), c]));
    const form = $('#form-cliente');
    const err = $('#cli-error');
    const btn = $('#cli-submit');
    const activoWrap = $('#c-activo-wrap');
    let editando = null;

    const RFC_RE = /^([A-ZÑ&]{3,4})\d{6}([A-Z\d]{3})$/;
    const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,120}\.[A-Za-z]{2,24}$/;

    function abrir(c) {
      editando = c;
      form.reset();
      err.classList.add('hidden');
      $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
      $('#cli-titulo').textContent = c ? 'Editar cliente' : 'Nuevo cliente';
      btn.disabled = false; btn.textContent = 'Guardar cliente';
      const rfc = $('#c-rfc');
      rfc.readOnly = !!c;
      $('#c-rfc-hint').classList.toggle('hidden', !!c);
      if (c) {
        rfc.value = c.rfc;
        $('#c-razon').value = c.razon_social;
        $('#c-cp').value = c.cp;
        $('#c-regimen').value = c.clave_regimen;
        $('#c-uso').value = c.clave_uso;
        $('#c-email').value = c.email_crudo || '';
        $('#c-tel').value = c.telefono || '';
      }
      if (activoWrap) {
        activoWrap.classList.toggle('hidden', !c);
        activoWrap.classList.toggle('flex', !!c);
        $('#c-activo').checked = c ? !!c.activo : true;
      }
      openDialog(dlg);
      (c ? $('#c-razon') : rfc).focus();
    }

    function leer() {
      return {
        rfc: $('#c-rfc').value.trim().toUpperCase(),
        razon_social: $('#c-razon').value.trim(),
        cp_fiscal: $('#c-cp').value.trim(),
        clave_regimen: $('#c-regimen').value,
        clave_uso: $('#c-uso').value,
        email: $('#c-email').value.trim().toLowerCase(),
        telefono: $('#c-tel').value.replace(/[\s()-]/g, ''),
      };
    }

    function validar(d) {
      const malos = [];
      if (!editando && !RFC_RE.test(d.rfc)) malos.push(['#c-rfc', 'RFC']);
      if (!d.razon_social) malos.push(['#c-razon', 'razón social']);
      if (!/^\d{5}$/.test(d.cp_fiscal)) malos.push(['#c-cp', 'C.P. fiscal (5 dígitos)']);
      if (!d.clave_regimen) malos.push(['#c-regimen', 'régimen fiscal']);
      if (!d.clave_uso) malos.push(['#c-uso', 'uso de CFDI']);
      if (d.email && !EMAIL_RE.test(d.email)) malos.push(['#c-email', 'correo']);
      if (d.telefono && !/^\d{10,15}$/.test(d.telefono)) malos.push(['#c-tel', 'teléfono (10 a 15 dígitos)']);
      return malos;
    }

    /** En una edición solo se manda lo que cambió. */
    function cambios(d) {
      const antes = {
        razon_social: editando.razon_social, cp_fiscal: editando.cp,
        clave_regimen: editando.clave_regimen, clave_uso: editando.clave_uso,
        email: editando.email_crudo || '', telefono: editando.telefono || '',
      };
      const out = {};
      Object.keys(antes).forEach((k) => { if (d[k] !== antes[k]) out[k] = d[k]; });
      if (activoWrap && $('#c-activo').checked !== !!editando.activo) out.activo = $('#c-activo').checked;
      return out;
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const d = leer();
      $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
      const malos = validar(d);
      if (malos.length) {
        malos.forEach(([sel]) => $(sel).setAttribute('aria-invalid', 'true'));
        mostrarError(err, 'Revisa estos datos: ' + malos.map(([, n]) => n).join(', '));
        $(malos[0][0]).focus();
        return;
      }
      let cuerpo = d;
      if (editando) {
        cuerpo = cambios(d);
        if (!Object.keys(cuerpo).length) { closeDialog(dlg); return; }
      }
      err.classList.add('hidden');
      btn.disabled = true; btn.textContent = 'Guardando…';
      try {
        if (editando) await api('PATCH', `/api/clientes/${editando.id_cliente}`, cuerpo);
        else await api('POST', '/api/clientes', cuerpo);
        recargarCon(editando ? 'Cliente guardado' : 'Cliente dado de alta');
      } catch (ex) {
        mostrarError(err, ex.message);
        btn.disabled = false; btn.textContent = 'Guardar cliente';
      }
    });

    document.addEventListener('click', (e) => {
      const a = e.target.closest('[data-action]');
      if (!a) return;
      if (a.dataset.action === 'nuevo-cliente') abrir(null);
      if (a.dataset.action === 'editar-cliente') abrir(porId.get(a.dataset.id));
    });
  })();
})();
