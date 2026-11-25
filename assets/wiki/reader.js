(() => {
  const tree = document.querySelector('#document-tree');
  const outline = document.querySelector('#page-outline');
  const article = document.querySelector('#page-content');
  const toc = document.querySelector('#toc');
  const backdrop = document.querySelector('#backdrop');
  const search = document.querySelector('#search');
  const panels = [tree, outline];
  const buttons = ['#tree-toggle', '#outline-toggle'].map(id => document.querySelector(id));
  const byPage = nodes => new Map([...nodes].map(node => [node.dataset.page, node]));
  const pages = byPage(document.querySelectorAll('template[data-page]'));
  const links = byPage(tree.querySelectorAll('a[data-page]'));
  let current, drawer, headings = [], choices = [];
  let landing = null;
  let updateScheduled = false;

  function showDrawer(index, restore = false) {
    const previous = drawer;
    drawer = index;
    panels.forEach((p, i) => {
      p.classList.toggle('open', index === i);
      buttons[i].setAttribute('aria-expanded', String(index === i));
    });
    backdrop.hidden = index === null;
    document.body.classList.toggle('panel-open', index !== null);
    if (index === 0) search.focus();
    if (index === 1) (toc.querySelector('[aria-current]') || document.querySelector('#raw')).focus();
    if (restore && previous != null) buttons[previous].focus();
  }
  buttons.forEach((button, i) => button.onclick = () => showDrawer(drawer === i ? null : i));
  backdrop.onclick = () => showDrawer(null, true);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && drawer != null) showDrawer(null, true);
  });
  for (const size of ['46rem', '64rem']) {
    matchMedia('(max-width: ' + size + ')').addEventListener('change', () => showDrawer(null));
  }

  const groups = [...tree.querySelectorAll('details')];
  let originalStates = null;
  search.addEventListener('input', () => {
    const text = search.value.trim().toLocaleLowerCase();
    if (text && !originalStates) originalStates = groups.map(group => group.open);
    for (const [key, a] of links) {
      a.hidden = !(a.textContent + ' ' + key).toLocaleLowerCase().includes(text);
    }
    groups.forEach((group, i) => {
      group.hidden = !group.querySelector('.page-link:not([hidden])');
      if (text) group.open = true;
      else if (originalStates) group.open = originalStates[i] || !!group.querySelector('[aria-current]');
    });
    if (!text) originalStates = null;
  });

  function highlight() {
    updateScheduled = false;
    let index = 0;
    const cutoff = document.querySelector('header').offsetHeight + 22;
    headings.forEach((h, i) => { if (h.getBoundingClientRect().top <= cutoff) index = i; });
    if (landing && Math.abs(scrollY - landing.top) < 2) index = landing.index;
    else {
      landing = null;
      if (scrollY > 0 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2) index = headings.length - 1;
    }
    choices.forEach((a, i) => {
      if (i === index) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    });
  }
  function scheduleHighlight() {
    if (!updateScheduled) {
      updateScheduled = true;
      requestAnimationFrame(highlight);
    }
  }
  window.addEventListener('scroll', scheduleHighlight, {passive:true});
  window.addEventListener('resize', scheduleHighlight);

  function render() {
    const route = new URLSearchParams(location.hash.slice(1));
    const id = pages.has(route.get('p')) ? route.get('p') : document.body.dataset.entry;
    const fromDrawer = drawer != null;
    showDrawer(null);
    if (current !== id) {
      current = id;
      const page = pages.get(id);
      article.replaceChildren(page.content.cloneNode(true));
      for (const [key, a] of links) {
        if (key === id) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
      }
      for (let group = links.get(id).closest('details'); group; group = group.parentElement.closest('details')) {
        group.open = true;
      }
      document.title = current === document.body.dataset.entry ? document.body.dataset.title :
        page.dataset.title + ' · ' + document.body.dataset.title;
      document.querySelector('#raw').href = page.dataset.raw;
      headings = [...article.querySelectorAll('h2,h3,h4,h5,h6')];
      choices = headings.map(h => {
        const a = document.createElement('a');
        a.href = '#' + new URLSearchParams({p:id, h:h.dataset.fragment});
        a.textContent = h.textContent;
        a.style.setProperty('--depth', Number(h.tagName.slice(1)) - 2);
        return a;
      });
      toc.replaceChildren(...choices);
    }
    const target = route.has('h') && [...article.querySelectorAll('[data-fragment]')].find(
      node => node.dataset.fragment === route.get('h'));
    if (target) {
      target.scrollIntoView({block:'start'});
      landing = {top:scrollY, index:Math.max(0, headings.indexOf(target))};
    } else {
      landing = null;
      window.scrollTo(0, 0);
    }
    if (fromDrawer) (target || article.parentElement).focus({preventScroll:true});
    highlight();
  }
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href^="#"]');
    if (a && a.hash === location.hash && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      render();
    }
  });
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  window.addEventListener('hashchange', render);
  render();
})();
