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
    var addInput = document.getElementById('id_profile_picture');
    var addPreview = document.getElementById('addPhotoPreview');
    var addClear = document.getElementById('addPhotoClear');
    var addBtnText = document.getElementById('addPhotoBtnText');
    var addHint = document.getElementById('addPhotoHint');
    var addFilename = document.getElementById('addPhotoFilename');

    if (!addInput || !addPreview) {
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
  });
})();