// static/js/bundles.js

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('item-search');
  const resultsList = document.getElementById('search-results');
  const itemsBody   = document.getElementById('bundle-items');
  const bundleId    = itemsBody.dataset.bundleId;

  let debounce;

  function recalcTotals() {
    let totalCost = 0, totalRetail = 0;
    itemsBody.querySelectorAll('tr').forEach(row => {
      const q     = parseFloat(row.querySelector('input[name="quantity"]').value) || 0;
      const cost  = parseFloat(row.querySelector('input[name="cost"]').value)       || 0;
      const retail= parseFloat(row.querySelector('input[name="retail"]').value)     || 0;
      totalCost  += cost * q;
      totalRetail+= retail * q;
    });
    document.getElementById('total-cost').textContent   = totalCost.toFixed(2);
    document.getElementById('total-retail').textContent = totalRetail.toFixed(2);
    const markup = totalCost > 0
      ? ((totalRetail - totalCost) / totalCost * 100).toFixed(2) + '%'
      : '0.00%';
    document.getElementById('markup-percent').textContent = markup;
    document.getElementById('profit-amount').textContent = (totalRetail - totalCost).toFixed(2);
  }

  // Initial calc on page load
  recalcTotals();

  // Live search
  searchInput.addEventListener('input', () => {
    clearTimeout(debounce);
    const q = searchInput.value.trim();
    if (!q) {
      resultsList.innerHTML = '';
      return;
    }
    debounce = setTimeout(async () => {
      try {
        const res = await fetch(`/bundles/search?q=${encodeURIComponent(q)}`);
        const { products } = await res.json();
        resultsList.innerHTML = products.map(p => `
          <li class="list-group-item d-flex justify-content-between align-items-center" data-id="${p.id}">
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
      } catch (err) {
        console.error('Search fetch error:', err);
        resultsList.innerHTML = `<li class="list-group-item text-danger">Error fetching results</li>`;
      }
    }, 300);
  });

  // Add item
  resultsList.addEventListener('click', async e => {
    if (!e.target.classList.contains('add-btn')) return;
    const li      = e.target.closest('li');
    const id      = li.dataset.id;
    const qtyInp  = li.querySelector('.qty-input');
    const quantity= parseInt(qtyInp.value, 10) || 1;

    try {
      const res = await fetch(`/bundles/${bundleId}/add-item`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ id, q: searchInput.value.trim(), type:'product', quantity })
      });
      if (!res.ok) throw new Error(await res.text());

      // Fetch the new item HTML from server or append manually.
      // Simplest: reload only the table and summary via AJAX,
      // but for now: manual row append is left as an exercise.
      window.location.reload();  // fallback ensures totals correct
    } catch (err) {
      console.error('Add-item error:', err);
    }
  });

  // Remove item
  itemsBody.addEventListener('click', async e => {
    if (!e.target.classList.contains('remove-item')) return;
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
});
