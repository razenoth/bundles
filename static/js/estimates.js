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

  // --- Update estimate (refresh costs from RepairShopr) ---
  const updateBtn = document.getElementById('update-estimate');
  if (updateBtn) {
    updateBtn.addEventListener('click', async () => {
      try {
        const res = await fetch(`/estimates/${estId}/refresh`, { method: 'POST' });
        if (!res.ok) throw new Error(await res.text());
        const { items } = await res.json();
        items.forEach(it => {
          const row = document.querySelector(`tr[data-item-id="${it.id}"]`);
          if (!row) return;
          const costInput = row.querySelector('.unit-price');
          if (costInput && it.unit_price !== undefined) {
            costInput.value = (+it.unit_price).toFixed(2);
          }
          const retailInput = row.querySelector('.retail');
          if (retailInput && it.retail !== undefined) {
            retailInput.value = (+it.retail).toFixed(2);
          }
        });
        recalc();
      } catch (err) {
        console.error('Refresh estimate error:', err);
      }
    });
  }

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
    bsSug.innerHTML = bundles.map(p => `
      <li class="list-group-item d-flex justify-content-between align-items-center"
          data-id="${p.id}"
          data-name="${p.name}"
          data-description="${p.description}"
          data-unit_price="${p.cost}"
          data-retail="${p.retail}">
        <div style="flex:1;">
          <strong>${p.name}</strong><br>
          ${p.description}<br>
          <small>Cost: $${p.cost.toFixed(2)}</small><br>
          <small>Retail: $${p.retail.toFixed(2)}</small>
        </div>
        <div class="d-flex align-items-center ms-3">
          <input type="number" class="form-control form-control-sm qty-input"
                 value="1" min="0" style="width:60px;">
          <button class="btn btn-sm btn-success ms-2 add-btn">Add</button>
        </div>
      </li>
    `).join('');
  }));

// Delegate clicks on the “Add” buttons in your bundle-suggestions <ul>:
bsSug.addEventListener('click', async e => {
  if (!e.target.classList.contains('add-btn')) return;
  const li  = e.target.closest('li');
  const qty = parseInt(li.querySelector('.qty-input').value, 10) || 1;
  const data = {
    id         : +li.dataset.id,
    name       : li.dataset.name,
    description: li.dataset.description,
    unit_price : parseFloat(li.dataset.unit_price),
    retail     : parseFloat(li.dataset.retail),
    type       : 'bundle',
    quantity   : qty
  };
  await addItem(data);
  bsSug.innerHTML = '';
  bsIn.value     = '';
});

  // --- Product search + delegated click ---
  const psIn  = document.getElementById('product-search');
  const psSug = document.getElementById('product-suggestions');
  let psPage = 1;
  let psAbort;

  function psShouldSearch(q) {
    const isBarcode = /^\d{8,14}$/.test(q);
    const isSku = /^[\w-]+$/.test(q);
    return isBarcode || isSku || q.length >= 2;
  }

  function renderProd(products, reset = true) {
    if (reset) psSug.innerHTML = '';
    psSug.innerHTML += products.map(p => `
      <li class="list-group-item d-flex justify-content-between align-items-center"
          data-id="${p.id}"
          data-name="${p.name}"
          data-description="${p.description.replace(/"/g,'&quot;')}"
          data-unit_price="${p.unit_price}"
          data-retail="${p.retail}"
          data-stock="${p.stock}">
        <div style="flex:1;">
          <strong>${p.name}</strong><br>
          ${p.description}<br>
          <small>Cost: $${p.unit_price.toFixed(2)}</small><br>
          <small>Retail: $${p.retail.toFixed(2)}</small><br>
          <small>Stock: ${p.stock}</small>
        </div>
        <div class="d-flex align-items-center ms-3">
          <input type="number" class="form-control form-control-sm qty-input"
                 value="1" min="0" style="width:60px;">
          <button class="btn btn-sm btn-success ms-2 add-btn">Add</button>
        </div>
      </li>
    `).join('');
    if (products.length === 25) {
      const li = document.createElement('li');
      li.className = 'list-group-item text-center load-more';
      li.textContent = 'Load more…';
      psSug.appendChild(li);
    }
  }

  psIn.addEventListener('input', debounce(async () => {
    const q = psIn.value.trim();
    if (!q || !psShouldSearch(q)) {
      psSug.innerHTML = '';
      return;
    }
    psPage = 1;
    try {
      if (psAbort) psAbort.abort();
      psAbort = new AbortController();
      const res = await fetch(`/estimates/search?q=${encodeURIComponent(q)}&page=${psPage}`, { signal: psAbort.signal });
      const { products } = await res.json();
      renderProd(products, true);
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Search fetch error:', err);
        psSug.innerHTML = `<li class="list-group-item text-danger">Error</li>`;
      }
    }
  }, 350));

  psSug.addEventListener('click', async e => {
    if (e.target.classList.contains('load-more')) {
      const q = psIn.value.trim();
      e.target.remove();
      psPage += 1;
      const res = await fetch(`/estimates/search?q=${encodeURIComponent(q)}&page=${psPage}`);
      const { products } = await res.json();
      renderProd(products, false);
      return;
    }
    if (!e.target.classList.contains('add-btn')) return;
    const li  = e.target.closest('li');
    const qty = parseInt(li.querySelector('.qty-input').value, 10) || 1;
    const data = {
      id         : +li.dataset.id,
      name       : li.dataset.name,
      description: li.dataset.description,
      unit_price : parseFloat(li.dataset.unit_price),
      retail     : parseFloat(li.dataset.retail),
      stock      : parseFloat(li.dataset.stock),
      type       : 'product',
      quantity   : qty
    };
    await addItem(data);
    psSug.innerHTML = '';
    psIn.value     = '';
    if (psAbort) psAbort.abort();
  });

  // --- Add line item via AJAX ---
  async function addItem(data) {
    if (!estId) return;
    const res = await fetch(`/estimates/${estId}/add-item`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) return;
    const payload = await res.json();
    const body = document.getElementById('items-body');

    if (data.type === 'bundle') {
      const parentData = { ...payload.parent, type: 'bundle', stock: null };
      const parentRow  = buildRow(parentData);
      body.appendChild(parentRow);
      payload.items.forEach(it => {
        const childData = { ...it, type: 'product', stock: it.stock };
        const childRow  = buildRow(childData, parentData.id);
        body.appendChild(childRow);
      });
    } else {
      const row = buildRow({ ...data, id: payload.item_id, type: data.type });
      body.appendChild(row);
    }
    recalc();
  }

  // --- Build a new table row for the added item ---
  function buildRow(data, parentId = null) {
    const tr = document.createElement('tr');
    tr.classList.add('draggable');
    tr.draggable = true;
    tr.dataset.itemId = data.id;
    tr.dataset.type = data.type;
    tr.dataset.qty = data.quantity ?? 1;
    if (parentId) {
      tr.dataset.parentId = parentId;
      tr.classList.add('bundle-item');
    }

    const dragTd = document.createElement('td');
    dragTd.className = 'drag-handle';
    dragTd.textContent = '☰';
    tr.appendChild(dragTd);

    const nameTd = document.createElement('td');
    if (parentId) nameTd.classList.add('ps-4');
    nameTd.textContent = data.name;
    tr.appendChild(nameTd);

    const descTd = document.createElement('td');
    descTd.textContent = data.description || '';
    tr.appendChild(descTd);

    for (let field of ['unit_price', 'retail', 'quantity']) {
      const td  = document.createElement('td');
      const inp = document.createElement('input');
      inp.type      = 'number';
      inp.step      = (field === 'quantity' ? '1' : '0.01');
      inp.className = 'form-control ' + (field === 'quantity' ? 'qty' : field.replace('_','-'));
      inp.value     = data[field] ?? (field === 'quantity' ? 1 : 0);
      td.appendChild(inp);
      tr.appendChild(td);
    }

    const stockTd = document.createElement('td');
    stockTd.className = 'stock-cell';
    stockTd.textContent = data.type === 'product' ? (data.stock ?? 0) : '--';
    tr.appendChild(stockTd);

    const lineTd = document.createElement('td');
    lineTd.className = 'line-total';
    lineTd.textContent = `$${((data.quantity || 1) * (data.unit_price || 0)).toFixed(2)}`;
    tr.appendChild(lineTd);

    const actTd = document.createElement('td');
    if (data.type === 'bundle') {
      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-sm btn-outline-primary toggle-bundle';
      toggleBtn.innerHTML = '&#128065;';
      toggleBtn.title = 'Show/Hide Items';
      actTd.appendChild(toggleBtn);
    }
    const remBtn = document.createElement('button');
    remBtn.className = 'btn btn-sm btn-danger remove-item';
    remBtn.textContent = '✕';
    actTd.appendChild(remBtn);
    tr.appendChild(actTd);

    const stockVal = data.type === 'product' ? (+data.stock || 0) : null;
    tr.classList.toggle('table-danger',
      (+data.quantity || 0) === 0 || (stockVal !== null && stockVal < (+data.quantity || 0))
    );
    return tr;
  }

  // --- Recalculate totals ---
  function recalc() {
    let totalCost   = 0;
    let totalRetail = 0;
    document.querySelectorAll('#items-body tr').forEach(row => {
      const q = +row.querySelector('.qty').value || 0;
      const c = +row.querySelector('.unit-price').value || 0;
      const r = +row.querySelector('.retail').value || 0;
      const lt = q * c;
      row.querySelector('.line-total').textContent = `$${lt.toFixed(2)}`;
      const stockCell = row.querySelector('.stock-cell');
      const stock = stockCell ? parseFloat(stockCell.textContent) : null;
      row.classList.toggle('table-danger', q === 0 || (stock !== null && stock < q));
      if (row.dataset.parentId) return; // child rows don't count toward totals
      totalCost   += lt;
      totalRetail += q * r;
    });
    const profit = totalRetail - totalCost;
    const markup = totalCost   > 0 ? (profit / totalCost   * 100) : 0;
    const margin = totalRetail > 0 ? (profit / totalRetail * 100) : 0;
    document.getElementById('total-cost').textContent    = totalCost.toFixed(2);
    document.getElementById('total-retail').textContent  = totalRetail.toFixed(2);
    document.getElementById('total-profit').textContent  = profit.toFixed(2);
    document.getElementById('markup-percent').textContent= markup.toFixed(2) + '%';
    document.getElementById('margin-percent').textContent= margin.toFixed(2) + '%';
  }

  // --- Inline edit, remove, toggle handlers ---
  const body = document.getElementById('items-body');
  body.addEventListener('click', async e => {
    if (e.target.matches('.remove-item')) {
      if (!confirm('Remove this item?')) return;
      const row = e.target.closest('tr');
      await fetch(`/estimates/${estId}/remove-item/${row.dataset.itemId}`, { method: 'POST' });
      const pid = row.dataset.itemId;
      row.remove();
      document.querySelectorAll(`tr[data-parent-id="${pid}"]`).forEach(r => r.remove());
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

    // If the bundle quantity changed, update child line quantities accordingly
    if (row.dataset.type === 'bundle' && e.target.classList.contains('qty')) {
      const oldQty = parseFloat(row.dataset.qty || '1');
      const newQty = parseFloat(row.querySelector('.qty').value) || 0;
      if (oldQty > 0) {
        const ratio = newQty / oldQty;
        row.dataset.qty = newQty;
        const children = document.querySelectorAll(`tr[data-parent-id="${id}"]`);
        for (const child of children) {
          const qInput = child.querySelector('.qty');
          const newChildQty = parseFloat(qInput.value) * ratio;
          qInput.value = newChildQty;
          await fetch(`/estimates/${estId}/update-item/${child.dataset.itemId}`, {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({ quantity: newChildQty })
          });
        }
      }
    }

    recalc();
  });

  // --- Drag & drop setup ---
  let draggedRow;
  let draggedRows = [];

  body.addEventListener('dragstart', e => {
    draggedRow = e.target.closest('tr');
    if (!draggedRow) return;
    if (!draggedRow.dataset.parentId) {
      const pid = draggedRow.dataset.itemId;
      draggedRows = [draggedRow, ...document.querySelectorAll(`tr[data-parent-id="${pid}"]`)];
    } else {
      draggedRows = [draggedRow];
    }
  });

  function getAfterNode(row) {
    let ref = row.nextSibling;
    while (ref && ref.dataset.parentId === row.dataset.itemId) {
      ref = ref.nextSibling;
    }
    return ref;
  }

  body.addEventListener('dragover', e => {
    e.preventDefault();
    const target = e.target.closest('tr');
    if (!target || draggedRows.includes(target)) return;
    const draggedParent = draggedRows[0].dataset.parentId || null;
    const targetParent  = target.dataset.parentId || null;
    if (draggedParent !== targetParent) return;

    const rect = target.getBoundingClientRect();
    const after = (e.clientY - rect.top) / rect.height > 0.5;
    let ref;
    if (!draggedRow.dataset.parentId) {
      ref = after ? getAfterNode(target) : target;
    } else {
      ref = after ? target.nextSibling : target;
    }
    draggedRows.forEach(r => body.insertBefore(r, ref));
  });

  body.addEventListener('dragend', () => {
    draggedRow = null;
    draggedRows = [];
  });

  // Initial calculation
  recalc();
}); // end DOMContentLoaded
