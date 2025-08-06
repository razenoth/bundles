document.addEventListener('DOMContentLoaded', ()=>{
  const searchInput = document.querySelector('#item-search');
  const resultsList = document.querySelector('#search-results');
  const itemsTable  = document.querySelector('#line-items tbody');

  searchInput.addEventListener('input', async e => {
    const q = e.target.value;
    if (!q) { resultsList.innerHTML=''; return; }
    const res = await fetch(`/estimates/search?q=${encodeURIComponent(q)}`);
    const {products, bundles} = await res.json();
    resultsList.innerHTML = '';
    for(let item of [...products, ...bundles]){
      let li = document.createElement('li');
      li.className = 'list-group-item';
      li.textContent = item.name;
      li.dataset.id   = item.id;
      li.dataset.type = item.type;
      resultsList.append(li);
    }
  });

  resultsList.addEventListener('click', async e => {
    if(e.target.tagName!=='LI') return;
    await fetch(`/estimates/${estimateId}/add-item`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id:e.target.dataset.id, type:e.target.dataset.type, name:e.target.textContent})
    });
    location.reload();
  });

  itemsTable.addEventListener('click', async e=>{
    if(!e.target.classList.contains('remove-item')) return;
    const row = e.target.closest('tr'), id=row.dataset.itemId;
    await fetch(`/estimates/${estimateId}/remove-item/${id}`,{method:'POST'});
    row.remove();
  });

  itemsTable.addEventListener('change', async e=>{
    const field = e.target.dataset.field, value=e.target.value;
    const row = e.target.closest('tr'), id=row.dataset.itemId;
    await fetch(`/estimates/${estimateId}/update-item/${id}`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({[field]:value})
    });
  });
});
