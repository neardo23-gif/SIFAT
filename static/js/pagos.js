/* SIFAT - Pagos. Registro de pagos con saldo precargado */
(() => {
  'use strict';

  const { $, money, api, mostrarError, recargarCon, leerJSON, DECIMAL_RE, openDialog } = window.SIFAT;

  (function pagos() {
    const cfg = leerJSON('pagos-config');
    if (!cfg) return;
    const dlg = $('#dlg-pago');
    const sel = $('#p-folio');
    const saldoEl = $('#p-saldo');
    const monto = $('#p-monto');
    let saldo = null;
    let consulta = 0;

    async function elegir(folio) {
      saldo = null;
      saldoEl.textContent = folio ? 'Consultando saldo…' : '';
      if (!folio) return;
      const mia = ++consulta; // si el usuario cambia rápido, solo cuenta la última respuesta
      try {
        const f = await api('GET', '/api/facturas/' + encodeURIComponent(folio));
        if (mia !== consulta) return;
        saldo = Number(f.saldo);
        saldoEl.textContent = `Saldo pendiente: ${money.format(saldo)} de ${money.format(f.total)}`;
        monto.value = saldo.toFixed(2);
        monto.max = saldo.toFixed(2);
      } catch (ex) {
        if (mia === consulta) saldoEl.textContent = 'No se pudo consultar el saldo: ' + ex.message;
      }
    }

    function abrir(folio) {
      $('#form-pago').reset();
      $('#p-error').classList.add('hidden');
      const btn = $('#p-submit');
      btn.disabled = false; btn.textContent = 'Registrar pago';
      if (folio && $(`#p-folio option[value="${CSS.escape(folio)}"]`)) sel.value = folio;
      elegir(sel.value);
      openDialog(dlg);
      (sel.value ? monto : sel).focus();
    }

    sel.addEventListener('change', () => elegir(sel.value));

    $('#form-pago').addEventListener('submit', async (e) => {
      e.preventDefault();
      const box = $('#p-error');
      const valor = monto.value.trim();
      if (!sel.value) { mostrarError(box, 'Elige la factura'); sel.focus(); return; }
      if (!DECIMAL_RE.test(valor) || Number(valor) <= 0) {
        mostrarError(box, 'El monto debe ser mayor que 0 y tener máximo 2 decimales'); monto.focus(); return;
      }
      if (saldo !== null && Number(valor) > saldo + 1e-9) {
        mostrarError(box, `El monto no puede superar el saldo pendiente (${money.format(saldo)})`); monto.focus(); return;
      }
      box.classList.add('hidden');
      const btn = $('#p-submit');
      btn.disabled = true; btn.textContent = 'Registrando…';
      try {
        const p = await api('POST', '/api/pagos', {
          folio: sel.value,
          clave_forma_pago: $('#p-forma').value,
          monto: valor,
          referencia: $('#p-ref').value.trim(),
        });
        recargarCon(p.factura_pagada ? `Pago registrado: la factura ${p.folio} quedó pagada`
          : `Pago registrado. Saldo restante: ${money.format(p.saldo_restante)}`);
      } catch (ex) {
        mostrarError(box, ex.message);
        btn.disabled = false; btn.textContent = 'Registrar pago';
      }
    });

    document.addEventListener('click', (e) => {
      const a = e.target.closest('[data-action="nuevo-pago"]');
      if (a) abrir('');
    });
    // Viene del detalle de una factura: /pagos?folio=FAC-0001
    if (cfg.folio_inicial) abrir(cfg.folio_inicial);
  })();
})();
