// static/js/bundles.js

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('item-search');
  const resultsList = document.getElementById('search-results');
  const itemsBody   = document.getElementById('bundle-items');
  const bundleId    = itemsBody.dataset.bundleId;
  const updateBtn   = document.getElementById('update-bundle');

  let debounce;
  let abortCtrl;
  let page = 1;
  let draggedRow;

  function recalcTotals() {
    let totalCost = 0, totalRetail = 0;
    itemsBody.querySelectorAll('tr').forEach(row => {
      const q      = parseFloat(row.querySelector('input[name="quantity"]').value) || 0;
      const cost   = parseFloat(row.querySelector('input[name="cost"]').value)       || 0;
      const retail = parseFloat(row.querySelector('input[name="retail"]').value)     || 0;
      totalCost   += cost * q;
      totalRetail += retail * q;
    });

    const profit = totalRetail - totalCost;
    const markup = totalCost  > 0 ? (profit / totalCost  * 100) : 0;
    const margin = totalRetail> 0 ? (profit / totalRetail* 100) : 0;

    document.getElementById('total-cost').textContent    = totalCost.toFixed(2);
    document.getElementById('total-retail').textContent  = totalRetail.toFixed(2);
    document.getElementById('profit-amount').textContent = profit.toFixed(2);
    document.getElementById('markup-percent').textContent= markup.toFixed(2) + '%';
    document.getElementById('margin-percent').textContent= margin.toFixed(2) + '%';
  }

  // Initial calc on page load
  recalcTotals();

  // Live search
  function renderResults(products, reset = true) {
    if (reset) resultsList.innerHTML = '';
    resultsList.innerHTML += products.map(p => `
      <li class="list-group-item d-flex justify-content-between align-items-center"
          data-id="${p.id}"
          data-name="${p.name.replace(/"/g,'&quot;')}"
          data-description="${p.description.replace(/"/g,'&quot;')}"
          data-cost="${p.cost}"
          data-retail="${p.retail}"
          data-stock="${p.stock}">
        <div style="flex:1;">
          <strong>${p.name}</strong><br>
          ${p.description}<br>
          <small>Cost: $${p.cost.toFixed(2)}</small><br>
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
      resultsList.appendChild(li);
    }
  }

  function shouldSearch(q) {
    const isBarcode = /^\d{8,14}$/.test(q);
    const isSku = /^[\w-]+$/.test(q);
    return isBarcode || isSku || q.length >= 2;
  }

  searchInput.addEventListener('input', () => {
    clearTimeout(debounce);
    const q = searchInput.value.trim();
    if (!q || !shouldSearch(q)) {
      resultsList.innerHTML = '';
      return;
    }
    page = 1;
    debounce = setTimeout(async () => {
      try {
        if (abortCtrl) abortCtrl.abort();
        abortCtrl = new AbortController();
        const res = await fetch(`/bundles/search?q=${encodeURIComponent(q)}&page=${page}`, { signal: abortCtrl.signal });
        const { products } = await res.json();
        renderResults(products, true);
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.error('Search fetch error:', err);
          resultsList.innerHTML = `<li class="list-group-item text-danger">Error fetching results</li>`;
        }
      }
    }, 350);
  });

  // Add item
  resultsList.addEventListener('click', async e => {
    if (e.target.classList.contains('load-more')) {
      const q = searchInput.value.trim();
      e.target.remove();
      page += 1;
      const res = await fetch(`/bundles/search?q=${encodeURIComponent(q)}&page=${page}`);
      const { products } = await res.json();
      renderResults(products, false);
      return;
    }
    if (!e.target.classList.contains('add-btn')) return;
    const li      = e.target.closest('li');
    const id      = li.dataset.id;
    const name    = li.dataset.name;
    const desc    = li.dataset.description;
    const cost    = parseFloat(li.dataset.cost);
    const retail  = parseFloat(li.dataset.retail);
    const stock   = parseFloat(li.dataset.stock);
    const qtyInp  = li.querySelector('.qty-input');
    const quantity= parseInt(qtyInp.value, 10) || 1;

    try {
      const res = await fetch(`/bundles/${bundleId}/add-item`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ id, q: searchInput.value.trim(), type:'product', quantity })
      });
      if (!res.ok) throw new Error(await res.text());
      const { item_id } = await res.json();

      const row = document.createElement('tr');
      row.dataset.itemId = item_id;
      row.draggable = true;
      row.innerHTML = `
        <td><input type="text" name="product_name" class="form-control" value="${name}"></td>
        <td><input type="text" name="description" class="form-control" value="${desc}"></td>
        <td><div class="input-group"><span class="input-group-text">$</span><input type="text" name="cost" class="form-control" value="${cost.toFixed(2)}"></div></td>
        <td><div class="input-group"><span class="input-group-text">$</span><input type="text" name="retail" class="form-control" value="${retail.toFixed(2)}"></div></td>
        <td><input type="number" name="quantity" class="form-control" min="0" value="${quantity}"></td>
        <td class="stock-cell">${stock}</td>
        <td><button class="btn btn-sm btn-danger remove-item">&times;</button></td>
      `;
      row.classList.toggle('table-danger', stock === 0);
      itemsBody.appendChild(row);
      recalcTotals();
      resultsList.innerHTML = '';
      searchInput.value = '';
    } catch (err) {
      console.error('Add-item error:', err);
    }
  });

  // Remove item
  itemsBody.addEventListener('click', async e => {
    if (!e.target.classList.contains('remove-item')) return;
    if (!confirm('Remove this item?')) return;
    const row    = e.target.closest('tr');
    const itemId = row.dataset.itemId;
    try {
      const res = await fetch(`/bundles/${bundleId}/remove-item/${itemId}`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      row.remove();
      recalcTotals();
    } catch (err) {
      console.error('Remove-item error:', err);
    }
  });

  updateBtn.addEventListener('click', async () => {
    try {
      const res = await fetch(`/bundles/${bundleId}/refresh`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const { items } = await res.json();
      items.forEach(it => {
        const row = itemsBody.querySelector(`tr[data-item-id="${it.id}"]`);
        if (!row) return;
        row.querySelector('input[name="cost"]').value = parseFloat(it.cost).toFixed(2);
        const stockCell = row.querySelector('.stock-cell');
        stockCell.textContent = it.stock;
        row.classList.toggle('table-danger', it.stock === 0);
      });
      recalcTotals();
    } catch (err) {
      console.error('Refresh error:', err);
    }
  });

  // Inline update
  itemsBody.addEventListener('change', async e => {
    const input  = e.target;
    const row    = input.closest('tr');
    const itemId = row.dataset.itemId;
    const field  = input.name;
    const value  = input.value;
    try {
      const res = await fetch(`/bundles/${bundleId}/update-item/${itemId}`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ [field]: value })
      });
      if (!res.ok) throw new Error(await res.text());
      recalcTotals();
    } catch (err) {
      console.error('Update-item error:', err);
    }
  });

  itemsBody.addEventListener('dragstart', e => {
    draggedRow = e.target.closest('tr');
  });

  itemsBody.addEventListener('dragover', e => {
    e.preventDefault();
    const target = e.target.closest('tr');
    if (!target || target === draggedRow) return;
    const rect = target.getBoundingClientRect();
    const next = (e.clientY - rect.top) / (rect.height) > 0.5;
    itemsBody.insertBefore(draggedRow, next ? target.nextSibling : target);
  });

  itemsBody.addEventListener('dragend', () => {
    draggedRow = null;
  });
});
