(function () {
  'use strict';
  var realSelect = document.getElementById('id_species');
  var radios     = document.querySelectorAll('.species-option');
  if (!realSelect) return;

  // ── Conditional "Other" species field ──────────────────────────────────
  var otherContainer = document.getElementById('speciesOtherContainer');
  var otherInput = document.getElementById('id_species_other');

  function updateOtherFieldVisibility() {
    if (realSelect.value === 'other') {
      if (otherContainer) otherContainer.style.display = '';
      if (otherInput) otherInput.setAttribute('required', '');
    } else {
      if (otherContainer) otherContainer.style.display = 'none';
      if (otherInput) {
        otherInput.removeAttribute('required');
        otherInput.value = '';
      }
    }
  }

  function syncFromCheckedRadio() {
    var checked = document.querySelector('.species-option:checked');
    if (checked) {
      realSelect.value = checked.value;
      updateOtherFieldVisibility();
    }
  }

  var currentVal = realSelect.value;
  if (currentVal) {
    var match = document.querySelector('.species-option[value="' + currentVal + '"]');
    if (match) match.checked = true;
  } else {
    syncFromCheckedRadio();
  }

  // Update visibility on page load
  updateOtherFieldVisibility();

  radios.forEach(function (radio) {
    radio.addEventListener('change', function () { 
      realSelect.value = this.value;
      updateOtherFieldVisibility();
    });
  });

  var form = realSelect.form;
  if (form) {
    form.addEventListener('submit', function(e) {
      syncFromCheckedRadio();
      // Validate that "Other" species field is filled when "other" is selected
      if (realSelect.value === 'other' && otherInput && !otherInput.value.trim()) {
        e.preventDefault();
        otherInput.focus();
        alert('Please specify what species of pet this is.');
        return false;
      }
    });
  }
})();