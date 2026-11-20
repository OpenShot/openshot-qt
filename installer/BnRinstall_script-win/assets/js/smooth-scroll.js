(function () {
  function qs(sel, ctx){ return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx){ return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  function smoothTo(hash) {
    if (!hash) return;
    var target = qs(hash);
    if (!target) return;
    var top = target.getBoundingClientRect().top + window.pageYOffset - 88;
    window.scrollTo({ top: top, behavior: 'smooth' });
  }
  function setActiveFilter(button) {
    qsa('[data-filter]').forEach(function (btn) { btn.classList.toggle('is-active', btn === button); });
  }
  function applyBucketFilter(tag) {
    qsa('.menu a').forEach(function (a) {
      var bucket = a.getAttribute('data-bucket') || '';
      var visible = (tag === 'all' || bucket.indexOf(tag) !== -1);
      a.parentElement.style.display = visible ? '' : 'none';
    });
  }
  function applySearchFilter(query) {
    var q = (query || '').trim().toLowerCase();
    qsa('.menu a').forEach(function (a) {
      var hay = (a.textContent + ' ' + (a.getAttribute('data-search') || '')).toLowerCase();
      var hit = !q || hay.indexOf(q) !== -1;
      if (a.parentElement.style.display !== 'none') a.parentElement.style.display = hit ? '' : 'none';
    });
  }
  function refreshActiveLink() {
    var sections = qsa('main .section[id]');
    var current = null;
    sections.forEach(function (section) {
      var rect = section.getBoundingClientRect();
      if (rect.top <= 140 && rect.bottom >= 140) current = section.id;
    });
    qsa('.menu a').forEach(function (a) { a.classList.toggle('is-active', current && a.getAttribute('href') === '#' + current); });
  }
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href^="#"]');
    if (link) {
      var href = link.getAttribute('href');
      if (href && href !== '#') {
        e.preventDefault();
        history.pushState(null, '', href);
        smoothTo(href);
      }
    }
    if (e.target && e.target.id === 'print-help') window.print();
    if (e.target && e.target.id === 'back-to-top') window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  window.addEventListener('load', function () {
    if (window.location.hash) smoothTo(window.location.hash);
    refreshActiveLink();
  });
  window.addEventListener('scroll', function () {
    refreshActiveLink();
    var btn = qs('#back-to-top');
    if (btn) btn.classList.toggle('is-visible', window.pageYOffset > 500);
  });
  qsa('[data-filter]').forEach(function (button) {
    button.addEventListener('click', function () {
      var tag = button.getAttribute('data-filter');
      setActiveFilter(button);
      applyBucketFilter(tag);
      applySearchFilter(qs('#menu-search') ? qs('#menu-search').value : '');
    });
  });
  var search = qs('#menu-search');
  if (search) {
    search.addEventListener('input', function () {
      var active = qs('[data-filter].is-active');
      applyBucketFilter(active ? active.getAttribute('data-filter') : 'all');
      applySearchFilter(search.value);
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && !/input|textarea/i.test((document.activeElement || {}).tagName || '')) {
      e.preventDefault();
      if (search) search.focus();
    }
  });
}());