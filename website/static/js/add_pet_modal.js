(function () {
  'use strict';

  function showPreview(file, previewEl) {
    var reader = new FileReader();
    reader.onload = function (e) {
      previewEl.innerHTML = '';
      var img = document.createElement('img');
      img.src = e.target.result;
      img.alt = 'Preview';
      img.className = 'pet-photo-upload__img';
      previewEl.appendChild(img);
      previewEl.classList.add('has-image');
    };
    reader.readAsDataURL(file);
  }

  function truncateName(name, max) {
    return name.length > max ? name.substring(0, max - 3) + '...' : name;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var addForm = document.querySelector('#addPetModal form, #addPetModalEmpty form');
    var speciesRadios = document.querySelectorAll('#addPetModal input[name="species"], #addPetModalEmpty input[name="species"]');
    var speciesOtherGroup = document.getElementById('speciesOtherGroupModal');
    var speciesOtherInput = document.getElementById('id_species_other_modal');

    var addInput = document.getElementById('id_profile_picture');
    var addPreview = document.getElementById('addPhotoPreview');
    var addClear = document.getElementById('addPhotoClear');
    var addBtnText = document.getElementById('addPhotoBtnText');
    var addHint = document.getElementById('addPhotoHint');
    var addFilename = document.getElementById('addPhotoFilename');

    function toggleSpeciesOtherInput() {
      if (!speciesOtherGroup || !speciesOtherInput) return;

      var selectedSpecies = '';
      speciesRadios.forEach(function (radio) {
        if (radio.checked) selectedSpecies = radio.value;
      });

      var showOtherInput = selectedSpecies === 'other';
      speciesOtherGroup.style.display = showOtherInput ? '' : 'none';
      speciesOtherInput.required = showOtherInput;

      if (!showOtherInput) {
        speciesOtherInput.value = '';
      }
    }

    if (!addInput || !addPreview) {
      if (speciesRadios.length) {
        speciesRadios.forEach(function (radio) {
          radio.addEventListener('change', toggleSpeciesOtherInput);
        });
        toggleSpeciesOtherInput();
      }
      return;
    }

    function resetAddPhoto() {
      addInput.value = '';
      addPreview.innerHTML = '<span class="pet-photo-upload__placeholder">🐾</span>';
      addPreview.classList.remove('has-image');

      if (addClear) {
        addClear.style.display = 'none';
      }
      if (addBtnText) {
        addBtnText.textContent = 'Choose photo';
      }
      if (addHint) {
        addHint.style.display = '';
      }
      if (addFilename) {
        addFilename.textContent = '';
        addFilename.style.display = 'none';
      }
    }

    addInput.addEventListener('change', function () {
      var file = this.files && this.files[0];
      if (!file) {
        return;
      }

      showPreview(file, addPreview);

      if (addClear) {
        addClear.style.display = 'inline-flex';
      }
      if (addBtnText) {
        addBtnText.textContent = 'Change photo';
      }
      if (addHint) {
        addHint.style.display = 'none';
      }
      if (addFilename) {
        addFilename.textContent = '✓ ' + truncateName(file.name, 22);
        addFilename.style.display = 'block';
      }
    });

    if (addClear) {
      addClear.addEventListener('click', resetAddPhoto);
    }

    if (speciesRadios.length) {
      speciesRadios.forEach(function (radio) {
        radio.addEventListener('change', toggleSpeciesOtherInput);
      });
      toggleSpeciesOtherInput();
    }

    if (addForm) {
      addForm.addEventListener('submit', function (e) {
        toggleSpeciesOtherInput();
        if (speciesOtherInput && speciesOtherInput.required && !speciesOtherInput.value.trim()) {
          e.preventDefault();
          speciesOtherInput.focus();
        }
      });
    }
  });
})();