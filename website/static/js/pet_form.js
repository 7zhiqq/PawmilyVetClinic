(function () {
  'use strict';
  var realSelect = document.getElementById('id_species');
  var radios     = document.querySelectorAll('.species-option');
  if (!realSelect) return;

  function syncFromCheckedRadio() {
    var checked = document.querySelector('.species-option:checked');
    if (checked) {
      realSelect.value = checked.value;
    }
  }

  var currentVal = realSelect.value;
  if (currentVal) {
    var match = document.querySelector('.species-option[value="' + currentVal + '"]');
    if (match) match.checked = true;
  } else {
    syncFromCheckedRadio();
  }

  radios.forEach(function (radio) {
    radio.addEventListener('change', function () { realSelect.value = this.value; });
  });

  var form = realSelect.form;
  if (form) {
    form.addEventListener('submit', syncFromCheckedRadio);
  }
})();