// static/js/estimates.js
document.addEventListener('DOMContentLoaded', () => {
  const estId = document.querySelector('[data-estimate-id]').dataset.estimateId;

  // Debounce helper
  function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  // --- Save button (PATCH existing estimate) ---
  document.getElementById('save-estimate').addEventListener('click', async () => {
    const payload = {
      customer_id:      document.getElementById('customer-id').value,
      customer_name:    document.getElementById('customer-search').value,
      customer_address: document.getElementById('customer-address').textContent,
      status:           document.getElementById('status').value
    };
    const res = await fetch(`/estimates/${estId}/edit`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload)
    });
    if (res.ok) {
      alert('Estimate saved successfully');
    } else {
      alert('Error saving estimate');
      console.error(await res.text());
    }
  });

  // --- Bundle search + delegated click ---
  const bsIn  = document.getElementById('bundle-search');
  const bsSug = document.getElementById('bundle-suggestions');
  bsIn.addEventListener('input', debounce(async () => {
    const q = bsIn.value.trim();
    if (!q) {
      bsSug.innerHTML = '';
      return;
    }
    const res = await fetch(`/bundles/search-bundles?q=${encodeURIComponent(q)}`);
    const { bundles } = await res.json();
    bsSug.innerHTML = bundles.map(b => `
      <a href="#" class="list-group-item list-group-item-action"
         data-id="${b.id}" data-name="${b.name}">
        ${b.name}
      </a>
    `).join('');
  }));
  bsSug.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a) return;
    e.preventDefault();
    const data = { id: +a.dataset.id, name: a.dataset.name, type: 'bundle' };
    addItem(data);
    bsSug.innerHTML = '';
    bsIn.value = '';
  });

  // --- Product search + delegated click ---
  const psIn  = document.getElementById('product-search');
  const psSug = document.getElementById('product-suggestions');
  psIn.addEventListener('input', debounce(async () => {
    const q = psIn.value.trim();
    if (!q) {
      psSug.innerHTML = '';
      return;
    }
    const res = await fetch(`/estimates/search?q=${encodeURIComponent(q)}`);
    const { products } = await res.json();
    psSug.innerHTML = products.map(p => `
      <a href="#" class="list-group-item list-group-item-action"
         data-id="${p.id}" data-name="${p.name}"
         data-unit_price="${p.unit_price}">
        ${p.name}
      </a>
    `).join('');
  }));
  psSug.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a) return;
    e.preventDefault();
    const data = {
      id: +a.dataset.id,
      name: a.dataset.name,
      type: 'product',
      unit_price: +a.dataset.unit_price,
      retail: +a.dataset.unit_price
    };
    addItem(data);
    psSug.innerHTML = '';
    psIn.value = '';
  });

  // --- Add line item via AJAX ---
  async function addItem(data) {
    console.log('addItem called, estId=', estId, 'data=', data);
    if (!estId) return; 
    const res = await fetch(`/estimates/${estId}/add-item`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(data)
    });
    if (!res.ok) return;
    const payload = await res.json();
    const row = await buildRow(payload, data);
    document.getElementById('items-body').appendChild(row);
    recalc();
    attachDragHandlers(row);
  }

  // --- Build a new table row for the added item ---
  async function buildRow({ item_id }, data) {
    const tr = document.createElement('tr');
    tr.classList.add('draggable');
    tr.draggable = true;
    tr.dataset.itemId = item_id;

    // Drag handle
    const dragTd = document.createElement('td');
    dragTd.className = 'drag-handle';
    dragTd.textContent = '☰';
    tr.appendChild(dragTd);

    // Name & type
    for (let key of ['name', 'type']) {
      const td = document.createElement('td');
      td.textContent = data[key];
      tr.appendChild(td);
    }

    // Qty, cost, retail inputs
    for (let field of ['quantity', 'unit_price', 'retail']) {
      const td  = document.createElement('td');
      const inp = document.createElement('input');
      inp.type      = 'number';
      inp.step      = (field==='quantity' ? '1' : '0.01');
      inp.className = 'form-control ' +
        (field==='quantity' ? 'qty' : field.replace('_','-'));
      inp.value     = data[field] ?? (field==='quantity' ? 1 : 0);
      td.appendChild(inp);
      tr.appendChild(td);
    }

    // Line total
    const lineTd = document.createElement('td');
    lineTd.className = 'line-total';
    lineTd.textContent = `$${(
      (data.quantity||1) * (data.unit_price||0)
    ).toFixed(2)}`;
    tr.appendChild(lineTd);

    // Actions (toggle bundle / remove)
    const actTd = document.createElement('td');
    if (data.type === 'bundle') {
      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-sm btn-link toggle-bundle';
      toggleBtn.textContent = 'Show/Hide Items';
      actTd.appendChild(toggleBtn);
    }
    const remBtn = document.createElement('button');
    remBtn.className = 'btn btn-sm btn-danger remove-item';
    remBtn.textContent = '✕';
    actTd.appendChild(remBtn);
    tr.appendChild(actTd);

    return tr;
  }

  // --- Recalculate totals ---
  function recalc() {
    let totalCost   = 0;
    let totalRetail = 0;
    document.querySelectorAll('#items-body tr').forEach(row => {
      const q   = +row.querySelector('.qty').value || 0;
      const c   = +row.querySelector('.unit-price').value || 0;
      const r   = +row.querySelector('.retail').value || 0;
      const lt  = q * c;
      totalCost   += lt;
      totalRetail += q * r;
      row.querySelector('.line-total')
         .textContent = `$${lt.toFixed(2)}`;
    });
    document.getElementById('total-cost').textContent   = `$${totalCost.toFixed(2)}`;
    document.getElementById('total-retail').textContent = `$${totalRetail.toFixed(2)}`;
    document.getElementById('total-profit').textContent = `$${(totalRetail - totalCost).toFixed(2)}`;
  }

  // --- Inline edit, remove, toggle handlers ---
  const body = document.getElementById('items-body');
  body.addEventListener('click', async e => {
    if (e.target.matches('.remove-item')) {
      const row = e.target.closest('tr');
      await fetch(`/estimates/${estId}/remove-item/${row.dataset.itemId}`, { method: 'POST' });
      row.remove();
      recalc();
    }
    if (e.target.matches('.toggle-bundle')) {
      const parentId = e.target.closest('tr').dataset.itemId;
      document.querySelectorAll(`tr[data-parent-id="${parentId}"]`)
        .forEach(r => r.style.display = r.style.display === 'none' ? '' : 'none');
    }
  });
  body.addEventListener('change', async e => {
    if (!e.target.matches('.qty, .unit-price, .retail')) return;
    const row = e.target.closest('tr');
    const id  = row.dataset.itemId;
    const payload = {
      quantity:   +row.querySelector('.qty').value,
      unit_price: +row.querySelector('.unit-price').value,
      retail:     +row.querySelector('.retail').value
    };
    await fetch(`/estimates/${estId}/update-item/${id}`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    recalc();
  });

  // --- Drag & drop setup ---
  function attachDragHandlers(row) {
    row.addEventListener('dragstart', e => {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', null);
      window.dragSrc = row;
    });
    row.addEventListener('dragover', e => {
      e.preventDefault();
    });
    row.addEventListener('drop', e => {
      e.stopPropagation();
      const src = window.dragSrc;
      if (src && src !== row) {
        row.parentNode.insertBefore(src, row.nextSibling);
      }
    });
  }
  document.querySelectorAll('#items-body .draggable')
    .forEach(r => attachDragHandlers(r));

  // Initial calculation
  recalc();
}); // end DOMContentLoaded
