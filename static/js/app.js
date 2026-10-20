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
    $('#det-borrar').classList.toggle('hidden', !s.activo);

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
