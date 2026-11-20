/* SIFAT - comportamiento del front. Sin dependencias. */
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

  /* =========================================================
     Clientes
     ========================================================= */
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

  /* =========================================================
     Facturas
     ========================================================= */
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
      $('#fac-totales').replaceChildren(
        fila('Subtotal', money.format(f.subtotal)),
        fila('IVA', money.format(f.iva)),
        fila('Total', money.format(f.total), true),
      );
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
    const lista = $('#n-conceptos');

    // Misma regla que el servidor: se redondea cada importe a centavos (mitad hacia arriba)
    const centavos = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

    function recalcular() {
      let subtotal = 0; let iva = 0;
      $$('#n-conceptos > div').forEach((row) => {
        const s = servicios.get($('select', row).value);
        const cant = $('input', row).value.trim();
        const etiqueta = $('[data-importe]', row);
        if (!s || !DECIMAL_RE.test(cant)) { etiqueta.textContent = '-'; return; }
        const importe = centavos(Number(cant) * Number(s.precio_unitario));
        subtotal += importe;
        iva += centavos(importe * Number(s.tasa));
        etiqueta.textContent = money.format(importe);
      });
      $('#n-subtotal').textContent = money.format(subtotal);
      $('#n-iva').textContent = money.format(iva);
      $('#n-total').textContent = money.format(centavos(subtotal) + centavos(iva));
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

  /* =========================================================
     Pagos
     ========================================================= */
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

  /* =========================================================
     Catálogo
     ========================================================= */
  const dataEl = $('#servicios-data');
  if (!dataEl) return;

  const servicios = JSON.parse(dataEl.textContent);
  const categorias = JSON.parse($('#categorias-data').textContent);
  const byId = new Map(servicios.map((s) => [s.id_servicio, s]));

  const rows = $$('#tabla-servicios tbody tr');
  const state = { q: '', cat: '', page: 1, size: 10 };
  const els = {
    q: $('#q'), cat: $('#cat'), vacio: $('#vacio'), conteo: $('#conteo'),
    pagina: $('#pagina'), pag: $('#paginacion'), tabla: $('#tabla-servicios'),
    prev: $('[data-action="prev"]'), next: $('[data-action="next"]'),
    vTitulo: $('#vacio-titulo'), vTexto: $('#vacio-texto'),
  };

  const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

  function render() {
    const q = norm(state.q.trim());
    const matches = rows.filter((tr) => {
      const okQ = !q || norm(tr.dataset.search).includes(q);
      const okC = !state.cat || tr.dataset.cat === state.cat;
      return okQ && okC;
    });
    const pages = Math.max(1, Math.ceil(matches.length / state.size));
    state.page = Math.min(state.page, pages);
    const start = (state.page - 1) * state.size;
    const visible = new Set(matches.slice(start, start + state.size));
    rows.forEach((tr) => { tr.hidden = !visible.has(tr); });

    const total = servicios.length;
    const empty = matches.length === 0;
    els.tabla.parentElement.classList.toggle('hidden', empty);
    els.vacio.classList.toggle('hidden', !empty);
    if (empty && total === 0) {
      els.vTitulo.textContent = 'Aún no hay servicios';
      els.vTexto.textContent = 'Agrega el primero con “Nuevo servicio”.';
      $('[data-action="limpiar"]').classList.add('hidden');
    }
    els.pag.classList.toggle('hidden', empty);
    if (!empty) {
      els.conteo.textContent = `Mostrando ${start + 1}–${start + visible.size} de ${matches.length}` +
        (matches.length !== total ? ` (${total} en total)` : '');
      els.pagina.textContent = `Página ${state.page} de ${pages}`;
      els.prev.disabled = state.page <= 1;
      els.next.disabled = state.page >= pages;
    }
  }

  let debounce;
  els.q.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { state.q = els.q.value; state.page = 1; render(); }, 120);
  });
  els.cat.addEventListener('change', () => { state.cat = els.cat.value; state.page = 1; render(); });
  render();

  /* ---------------- detalle ---------------- */
  const dlgDetalle = $('#dlg-detalle');
  let actual = null;

  function dato(label, value) {
    const wrap = h('div');
    wrap.append(h('dt', 'text-[13px] text-mute', label), h('dd', 'mt-0.5 font-medium', value));
    return wrap;
  }

  function abrirDetalle(id) {
    const s = byId.get(id);
    if (!s) return;
    actual = s;
    $('#det-clave').textContent = `${s.id_servicio} · ${s.clave}`;
    $('#det-titulo').textContent = s.nombre;
    $('#det-desc').textContent = s.descripcion || 'Sin descripción.';

    const datos = $('#det-datos');
    datos.replaceChildren(
      dato('Precio', `${money.format(s.precio_unitario)} / ${(s.unidad_medida || '').toLowerCase()}`),
      dato('Categoría', s.categoria || '-'),
      dato('Estado', s.activo ? 'Activo' : 'Inactivo'),
      dato('Impuesto', s.impuesto ? `${s.impuesto.nombre} ${Math.round(s.impuesto.tasa * 100)}% (${s.impuesto.tipo})` : '-'),
    );
    // atributos que no todos los servicios tienen (esquema flexible)
    if (s.duracion_estimada_dias) datos.append(dato('Duración estimada', `${s.duracion_estimada_dias} días`));
    if (s.requiere_contrato_confidencialidad) datos.append(dato('Confidencialidad', 'Requiere contrato'));
    // un servicio inactivo ya está dado de baja
    $('#det-borrar')?.classList.toggle('hidden', !s.activo);

    const lista = $('#det-caract');
    lista.replaceChildren();
    const cs = s.caracteristicas || [];
    if (!cs.length) {
      lista.append(h('li', 'px-4 py-3 text-[15px] text-mute', 'Este servicio no tiene características registradas.'));
    }
    cs.forEach((c) => {
      const li = h('li', 'flex items-baseline justify-between gap-4 px-4 py-2.5 text-[15px]');
      const left = h('span', '', c.nombre);
      left.append(h('span', 'ml-2 text-[13px] text-mute', c.tipo));
      li.append(left, h('span', 'text-right text-mute', c.valor));
      lista.append(li);
    });
    openDialog(dlgDetalle);
  }

  $('#tabla-servicios tbody').addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-id]');
    if (tr) abrirDetalle(tr.dataset.id);
  });

  /* ---------------- formulario alta / edición ---------------- */
  const dlgForm = $('#dlg-form');
  const form = $('#form-servicio');
  const cList = $('#f-caract');
  const formError = $('#form-error');
  let modo = 'crear';

  $('#lista-cats').replaceChildren(...categorias.map((c) => Object.assign(document.createElement('option'), { value: c })));

  function filaCaract(c = { nombre: '', tipo: 'tecnica', valor: '' }) {
    const row = h('div', 'grid grid-cols-[1fr_auto] gap-2 sm:grid-cols-[1.2fr_120px_1fr_auto]');
    const nombre = h('input', 'field'); nombre.placeholder = 'Nombre'; nombre.value = c.nombre; nombre.setAttribute('aria-label', 'Nombre de la característica');
    const tipo = h('select', 'field'); tipo.setAttribute('aria-label', 'Tipo de característica');
    ['tecnica', 'comercial'].forEach((t) => { const o = h('option', '', t); o.value = t; tipo.append(o); });
    tipo.value = c.tipo;
    const valor = h('input', 'field'); valor.placeholder = 'Valor'; valor.value = c.valor; valor.setAttribute('aria-label', 'Valor de la característica');
    const del = h('button', 'icon-btn'); del.type = 'button'; del.setAttribute('aria-label', 'Quitar característica');
    del.innerHTML = '<svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
    del.addEventListener('click', () => row.remove());
    row.append(nombre, tipo, valor, del);
    return row;
  }

  function siguienteId() {
    const max = servicios.reduce((m, s) => Math.max(m, parseInt((s.id_servicio.split('-')[1] || '0'), 10) || 0), 0);
    return 'SRV-' + String(max + 1).padStart(3, '0');
  }

  function abrirForm(s) {
    modo = s ? 'editar' : 'crear';
    form.reset();
    cList.replaceChildren();
    formError.classList.add('hidden');
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    $('#form-titulo').textContent = s ? 'Editar servicio' : 'Nuevo servicio';
    $('#form-submit').textContent = 'Guardar servicio';
    const id = $('#f-id');
    id.readOnly = !!s;
    if (s) {
      id.value = s.id_servicio;
      $('#f-clave').value = s.clave || '';
      $('#f-nombre').value = s.nombre || '';
      $('#f-desc').value = s.descripcion || '';
      $('#f-cat').value = s.categoria || '';
      $('#f-precio').value = s.precio_unitario;
      $('#f-unidad').value = s.unidad_medida || 'Servicio';
      $('#f-activo').checked = !!s.activo;
      // preselecciona el impuesto actual del servicio, si existe en el catálogo
      if (s.impuesto) {
        const clave = `${s.impuesto.nombre}|${Number(s.impuesto.tasa).toFixed(4)}|${s.impuesto.tipo}`;
        if ($(`#f-impuesto option[value="${CSS.escape(clave)}"]`)) $('#f-impuesto').value = clave;
      }
      (s.caracteristicas || []).forEach((c) => cList.append(filaCaract(c)));
    } else {
      id.value = siguienteId();
    }
    openDialog(dlgForm);
    $('#f-clave').focus();
  }

  function leerForm() {
    const caracteristicas = $$('#f-caract > div').map((row) => {
      const [nombre, valor] = $$('input', row);
      const tipo = $('select', row);
      return { nombre: nombre.value.trim(), tipo: tipo.value, valor: valor.value.trim() };
    }).filter((c) => c.nombre);
    return {
      id_servicio: $('#f-id').value.trim(),
      clave: $('#f-clave').value.trim().toUpperCase(),
      nombre: $('#f-nombre').value.trim(),
      descripcion: $('#f-desc').value.trim(),
      categoria: $('#f-cat').value.trim(),
      precio_unitario: parseFloat($('#f-precio').value),
      unidad_medida: $('#f-unidad').value,
      activo: $('#f-activo').checked,
      // solo se manda cuál impuesto; la tasa la pone el servidor
      impuesto_clave: $('#f-impuesto').value,
      caracteristicas,
    };
  }

  function validar(d) {
    const malos = [];
    if (!/^SRV-\d{3,6}$/.test(d.id_servicio)) malos.push('#f-id');
    if (!/^[A-Z0-9-]{1,20}$/.test(d.clave)) malos.push('#f-clave');
    if (!d.nombre) malos.push('#f-nombre');
    if (!d.categoria) malos.push('#f-cat');
    if (!d.impuesto_clave) malos.push('#f-impuesto');
    // mismo rango y máximo 2 decimales que valida la Lambda
    if (!(d.precio_unitario >= 0 && d.precio_unitario <= 10000000) ||
        !/^\d+(\.\d{1,2})?$/.test($('#f-precio').value.trim())) malos.push('#f-precio');
    return malos;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const d = leerForm();
    $$('.field', form).forEach((f) => f.removeAttribute('aria-invalid'));
    const malos = validar(d);
    if (malos.length) {
      malos.forEach((sel) => $(sel).setAttribute('aria-invalid', 'true'));
      formError.textContent = 'Revisa los campos marcados: identificador (SRV-000), clave (letras, números y guiones), nombre, categoría y precio (máximo 2 decimales) son obligatorios.';
      formError.classList.remove('hidden');
      $(malos[0]).focus();
      return;
    }
    formError.classList.add('hidden');
    const btn = $('#form-submit');
    btn.disabled = true; btn.textContent = 'Guardando…';
    try {
      const res = await fetch('/api/servicios', {
        method: modo === 'crear' ? 'POST' : 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify(d),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.mensaje || `Error ${res.status}`);
      try { sessionStorage.setItem('sifat-toast', modo === 'crear' ? 'Servicio agregado' : 'Servicio guardado'); } catch (_) {}
      location.reload();
    } catch (err) {
      formError.textContent = err.message + '.';
      formError.classList.remove('hidden');
      btn.disabled = false; btn.textContent = 'Guardar servicio';
    }
  });

  /* ---------------- confirmar borrado ---------------- */
  const dlgBorrar = $('#dlg-borrar');
  const formBorrar = $('#form-borrar');
  const inputConfirma = $('#borrar-confirma');
  const btnBorrar = $('#borrar-submit');

  function abrirBorrar(s) {
    $('#borrar-nombre').textContent = s.nombre;
    $('#borrar-id').textContent = s.id_servicio;
    inputConfirma.value = '';
    btnBorrar.disabled = true;
    $('#borrar-error').classList.add('hidden');
    openDialog(dlgBorrar);
    inputConfirma.focus();
  }
  inputConfirma.addEventListener('input', () => {
    btnBorrar.disabled = inputConfirma.value.trim() !== actual.id_servicio;
  });
  formBorrar.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (inputConfirma.value.trim() !== actual.id_servicio) return;
    btnBorrar.disabled = true; btnBorrar.textContent = 'Dando de baja…';
    try {
      const res = await fetch('/api/servicios?id_servicio=' + encodeURIComponent(actual.id_servicio), {
        method: 'DELETE', headers: { 'X-CSRF-Token': csrf },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.mensaje || `Error ${res.status}`);
      try { sessionStorage.setItem('sifat-toast', 'Servicio dado de baja'); } catch (_) {}
      location.reload();
    } catch (err) {
      const box = $('#borrar-error');
      box.textContent = err.message + '.';
      box.classList.remove('hidden');
      btnBorrar.disabled = false; btnBorrar.textContent = 'Dar de baja';
    }
  });

  /* ---------------- acciones por delegación ---------------- */
  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-action]');
    if (!a) return;
    switch (a.dataset.action) {
      case 'nuevo': abrirForm(null); break;
      case 'editar': closeDialog(dlgDetalle); abrirForm(actual); break;
      case 'pedir-borrar': closeDialog(dlgDetalle); abrirBorrar(actual); break;
      case 'add-caract': { const r = filaCaract(); cList.append(r); $('input', r).focus(); break; }
      case 'prev': state.page--; render(); break;
      case 'next': state.page++; render(); break;
      case 'limpiar':
        state.q = ''; state.cat = ''; state.page = 1;
        els.q.value = ''; els.cat.value = ''; render(); break;
      default: break;
    }
  });
})();
