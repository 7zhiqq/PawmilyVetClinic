(function () {
  'use strict';
  var realSelect = document.getElementById('id_species');
  var radios     = document.querySelectorAll('.species-option');
  if (!realSelect) return;

  var currentVal = realSelect.value;
  if (currentVal) {
    var match = document.querySelector('.species-option[value="' + currentVal + '"]');
    if (match) match.checked = true;
  }

  radios.forEach(function (radio) {
    radio.addEventListener('change', function () { realSelect.value = this.value; });
  });
})();