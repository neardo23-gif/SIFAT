/* SIFAT - Facturas. Detalle, cancelación y emisión */
(() => {
  'use strict';

  const { $, $$, h, money, api, mostrarError, recargarCon, leerJSON, DECIMAL_RE, openDialog, closeDialog } = window.SIFAT;

  (function facturas() {
    const cfg = leerJSON('facturas-config');
    if (!cfg) return;
    const dlgDet = $('#dlg-factura');
    const dlgCan = $('#dlg-cancelar');
    const dlgNueva = $('#dlg-nueva');
    let actual = null;
    const ESTATUS = { vigente: 'Por cobrar', pagada: 'Pagada', cancelada: 'Cancelada' };

    function fecha(valor) {
      const d = new Date(valor);
      return isNaN(d) ? '-' : d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
    }
    function dato(label, value) {
      const wrap = h('div');
      wrap.append(h('dt', 'text-[13px] text-mute', label), h('dd', 'mt-0.5 font-medium', value));
      return wrap;
    }
    function fila(label, value, fuerte) {
      const wrap = h('div', 'flex justify-between' + (fuerte ? ' border-t border-line pt-1.5 font-semibold' : ''));
      wrap.append(h('dt', fuerte ? '' : 'text-mute', label), h('dd', '', value));
      return wrap;
    }

    /* ---- detalle ---- */
    async function verFactura(folio) {
      actual = null;
      $('#fac-titulo').textContent = folio;
      $('#fac-sub').textContent = 'Factura';
      $('#fac-cargando').classList.remove('hidden');
      $('#fac-error').classList.add('hidden');
      $('#fac-cuerpo').classList.add('hidden');
      $('#fac-cancelar').classList.add('hidden');
      $('#fac-pagar').classList.add('hidden');
      openDialog(dlgDet);
      try {
        const f = await api('GET', '/api/facturas/' + encodeURIComponent(folio));
        actual = f;
        pintarDetalle(f);
      } catch (ex) {
        mostrarError($('#fac-error'), ex.message);
      } finally {
        $('#fac-cargando').classList.add('hidden');
      }
    }

    function pintarDetalle(f) {
      $('#fac-sub').textContent = `${f.cliente} · ${f.rfc}`;
      $('#fac-datos').replaceChildren(
        dato('Estatus', ESTATUS[f.estatus] || f.estatus),
        dato('Emisión', fecha(f.fecha_emision)),
        dato('Emitió', f.usuario || '-'),
        dato('Forma de pago', `${f.clave_forma_pago} ${f.forma_pago}`),
        dato('Método de pago', `${f.clave_metodo_pago} ${f.metodo_pago}`),
        dato('Saldo', money.format(f.saldo)),
      );
      const motivo = $('#fac-motivo');
      motivo.classList.toggle('hidden', f.estatus !== 'cancelada');
      if (f.estatus === 'cancelada') {
        motivo.textContent = `Cancelada el ${fecha(f.fecha_cancelacion)}. Motivo: ${f.motivo_cancelacion || '-'}`;
      }

      $('#fac-conceptos').replaceChildren(...f.conceptos.map((c) => {
        const tr = h('tr');
        const nombre = h('td', 'px-3 py-2', c.nombre_servicio);
        nombre.append(h('span', 'ml-2 font-mono text-[12px] text-mute', c.clave_servicio));
        tr.append(
          nombre,
          h('td', 'px-3 py-2 text-right tabular-nums', Number(c.cantidad).toLocaleString('es-MX')),
          h('td', 'px-3 py-2 text-right tabular-nums text-mute', money.format(c.precio_unitario)),
          h('td', 'px-3 py-2 text-right tabular-nums', money.format(c.importe)),
          h('td', 'px-3 py-2 text-right tabular-nums text-mute', money.format(c.iva_importe)),
        );
        return tr;
      }));
      const totales = [fila('Subtotal', money.format(f.subtotal)), fila('IVA', money.format(f.iva))];
      if (Number(f.isr) > 0) totales.push(fila('ISR retenido', '-' + money.format(f.isr)));
      totales.push(fila('Total', money.format(f.total), true));
      $('#fac-totales').replaceChildren(...totales);
      const pagos = $('#fac-pagos');
      pagos.replaceChildren();
      if (!f.pagos.length) {
        pagos.append(h('li', 'px-4 py-3 text-[15px] text-mute', 'Esta factura no tiene pagos registrados.'));
      }
      f.pagos.forEach((p) => {
        const li = h('li', 'flex items-baseline justify-between gap-4 px-4 py-2.5 text-[15px]');
        const izq = h('span', '', fecha(p.fecha_pago));
        izq.append(h('span', 'ml-2 text-[13px] text-mute', [p.clave_forma_pago, p.referencia].filter(Boolean).join(' · ')));
        li.append(izq, h('span', 'tabular-nums font-medium', money.format(p.monto)));
        pagos.append(li);
      });
      $('#fac-cuerpo').classList.remove('hidden');

      const vigente = f.estatus === 'vigente';
      $('#fac-cancelar').classList.toggle('hidden', !(cfg.puede_cancelar && vigente && !f.pagos.length));
      const pagar = $('#fac-pagar');
      pagar.classList.toggle('hidden', !(cfg.puede_pagar && vigente && Number(f.saldo) > 0));
      pagar.href = `${cfg.url_pagos}?folio=${encodeURIComponent(f.folio)}`;
    }

    /* ---- cancelar ---- */
    const formCan = $('#form-cancelar');
    formCan.addEventListener('submit', async (e) => {
      e.preventDefault();
      const motivo = $('#can-motivo').value.trim();
      const box = $('#can-error');
      if (motivo.length < 5) { mostrarError(box, 'Escribe un motivo de al menos 5 caracteres'); return; }
      const btn = $('#can-submit');
      btn.disabled = true; btn.textContent = 'Cancelando…';
      try {
        await api('POST', `/api/facturas/${encodeURIComponent(actual.folio)}/cancelar`, { motivo });
        recargarCon(`Factura ${actual.folio} cancelada`);
      } catch (ex) {
        mostrarError(box, ex.message);
        btn.disabled = false; btn.textContent = 'Cancelar factura';
      }
    });

    /* ---- nueva factura ---- */
    const servicios = new Map(cfg.servicios.map((s) => [s.id_servicio, s]));
    const retieneIsr = new Set(cfg.retiene_isr || []);
    const lista = $('#n-conceptos');

    // Misma regla que el servidor: se redondea cada importe a centavos (mitad hacia arriba)
    const centavos = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

    function recalcular() {
      let subtotal = 0; let iva = 0; let isr = 0;
      const cliente = $('#n-cliente');
      const tasaIsr = cliente && retieneIsr.has(parseInt(cliente.value, 10)) ? Number(cfg.tasa_isr) : 0;
      $$('#n-conceptos > div').forEach((row) => {
        const s = servicios.get($('select', row).value);
        const cant = $('input', row).value.trim();
        const etiqueta = $('[data-importe]', row);
        if (!s || !DECIMAL_RE.test(cant)) { etiqueta.textContent = '-'; return; }
        const importe = centavos(Number(cant) * Number(s.precio_unitario));
        subtotal += importe;
        iva += centavos(importe * Number(s.tasa));
        isr += centavos(importe * tasaIsr);
        etiqueta.textContent = money.format(importe);
      });
      $('#n-subtotal').textContent = money.format(subtotal);
      $('#n-iva').textContent = money.format(iva);
      $('#n-isr-fila').hidden = !tasaIsr;
      $('#n-isr').textContent = '-' + money.format(centavos(isr));
      $('#n-total').textContent = money.format(centavos(centavos(subtotal) + centavos(iva) - centavos(isr)));
    }

    function filaConcepto() {
      const row = h('div', 'grid grid-cols-[1fr_auto] items-center gap-2 sm:grid-cols-[1fr_110px_120px_auto]');
      const sel = h('select', 'field'); sel.setAttribute('aria-label', 'Servicio');
      const vacio = h('option', '', 'Elige un servicio…'); vacio.value = '';
      sel.append(vacio);
      cfg.servicios.forEach((s) => {
        const o = h('option', '', `${s.nombre} · ${money.format(s.precio_unitario)} / ${(s.unidad_medida || '').toLowerCase()}`);
        o.value = s.id_servicio;
        sel.append(o);
      });
      const cant = h('input', 'field tabular-nums');
      Object.assign(cant, { type: 'number', min: '0.01', step: '0.01', value: '1', inputMode: 'decimal' });
      cant.setAttribute('aria-label', 'Cantidad');
      const importe = h('span', 'hidden text-right tabular-nums text-mute sm:block', '-');
      importe.dataset.importe = '';
      const del = h('button', 'icon-btn'); del.type = 'button'; del.setAttribute('aria-label', 'Quitar concepto');
      del.innerHTML = '<svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      del.addEventListener('click', () => { row.remove(); recalcular(); });
      sel.addEventListener('change', recalcular);
      cant.addEventListener('input', recalcular);
      row.append(sel, cant, importe, del);
      return row;
    }

    function abrirNueva() {
      $('#form-factura').reset();
      lista.replaceChildren(filaConcepto());
      $('#n-error').classList.add('hidden');
      const btn = $('#n-submit');
      btn.disabled = false; btn.textContent = 'Emitir factura';
      recalcular();
      openDialog(dlgNueva);
      $('#n-cliente').focus();
    }

    if (dlgNueva) {
      $('#n-cliente').addEventListener('change', recalcular);
      $('#form-factura').addEventListener('submit', async (e) => {
        e.preventDefault();
        const box = $('#n-error');
        const idCliente = parseInt($('#n-cliente').value, 10);
        const conceptos = $$('#n-conceptos > div').map((row) => ({
          id_servicio: $('select', row).value,
          cantidad: $('input', row).value.trim(),
        }));
        if (!idCliente) { mostrarError(box, 'Elige el cliente'); $('#n-cliente').focus(); return; }
        if (!conceptos.length) { mostrarError(box, 'Agrega al menos un concepto'); return; }
        if (conceptos.some((c) => !c.id_servicio)) { mostrarError(box, 'Elige el servicio de cada concepto'); return; }
        if (conceptos.some((c) => !DECIMAL_RE.test(c.cantidad) || Number(c.cantidad) <= 0)) {
          mostrarError(box, 'Cada cantidad debe ser mayor que 0 y tener máximo 2 decimales'); return;
        }
        box.classList.add('hidden');
        const btn = $('#n-submit');
        btn.disabled = true; btn.textContent = 'Emitiendo…';
        try {
          const f = await api('POST', '/api/facturas', {
            id_cliente: idCliente,
            clave_forma_pago: $('#n-forma').value,
            clave_metodo_pago: $('#n-metodo').value,
            conceptos,
          });
          recargarCon(`Factura ${f.folio} emitida por ${money.format(f.total)}`);
        } catch (ex) {
          mostrarError(box, ex.message);
          btn.disabled = false; btn.textContent = 'Emitir factura';
        }
      });
    }

    document.addEventListener('click', (e) => {
      const a = e.target.closest('[data-action]');
      const tr = e.target.closest('#tabla-facturas tr[data-folio]');
      if (!a && tr) { verFactura(tr.dataset.folio); return; }
      if (!a) return;
      switch (a.dataset.action) {
        case 'ver-factura': verFactura(a.dataset.folio); break;
        case 'pedir-cancelar':
          if (!actual) break;
          closeDialog(dlgDet);
          $('#can-folio').textContent = actual.folio;
          $('#can-motivo').value = '';
          $('#can-error').classList.add('hidden');
          $('#can-submit').disabled = false; $('#can-submit').textContent = 'Cancelar factura';
          openDialog(dlgCan);
          $('#can-motivo').focus();
          break;
        case 'nueva-factura': if (dlgNueva) abrirNueva(); break;
        case 'add-concepto': { const r = filaConcepto(); lista.append(r); $('select', r).focus(); break; }
        default: break;
      }
    });
  })();
})();
