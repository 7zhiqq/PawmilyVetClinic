(function () {
  'use strict';
  var hamburger  = document.getElementById('hamburger');
  var mobileMenu = document.getElementById('mobileMenu');
  if (hamburger && mobileMenu) {
    var setExpanded = function (expanded) {
      hamburger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    };

    hamburger.addEventListener('click', function () {
      var isOpen = mobileMenu.classList.toggle('open');
      setExpanded(isOpen);
    });

    mobileMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        mobileMenu.classList.remove('open');
        setExpanded(false);
      });
    });

    setExpanded(false);
  }
})();