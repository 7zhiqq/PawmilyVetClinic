(function () {
  'use strict';

  // ── Helpers ──────────────────────────────────────────────────────────────
  function showPreview(file, previewEl) {
    var reader = new FileReader();
    reader.onload = function (e) {
      previewEl.innerHTML = '';
      var img = document.createElement('img');
      img.src       = e.target.result;
      img.alt       = 'Preview';
      img.className = 'pet-photo-upload__img';
      previewEl.appendChild(img);
      previewEl.classList.add('has-image');
    };
    reader.readAsDataURL(file);
  }

  function truncateName(name, max) {
    return name.length > max ? name.substring(0, max - 3) + '\u2026' : name;
  }

  document.addEventListener('DOMContentLoaded', function () {

    // ── Add-pet modal ─────────────────────────────────────────────────────
    if (typeof initModal === 'function') {
      initModal('addPetModal', ['openAddPet', 'openAddPetEmpty'], 'closeAddPet');
    }
    // Add-pet preview is handled by shared add_pet_modal.js

    // ── Edit-pet modal open / close ───────────────────────────────────────
    document.querySelectorAll('[data-edit-pet]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var modal = document.getElementById('editPetModal_' + this.dataset.editPet);
        if (modal) { modal.classList.add('is-open'); document.body.style.overflow = 'hidden'; }
      });
    });

    document.querySelectorAll('[data-close-edit]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var modal = document.getElementById('editPetModal_' + this.dataset.closeEdit);
        if (modal) { modal.classList.remove('is-open'); document.body.style.overflow = ''; }
      });
    });

    document.querySelectorAll('[id^="editPetModal_"]').forEach(function (modal) {
      // Close on backdrop click
      modal.addEventListener('click', function (e) {
        if (e.target === modal) { modal.classList.remove('is-open'); document.body.style.overflow = ''; }
      });
      // Auto-open if the server sent back validation errors for this modal
      if (modal.dataset.hasErrors === 'true') {
        modal.classList.add('is-open'); document.body.style.overflow = 'hidden';
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        document.querySelectorAll('[id^="editPetModal_"].is-open').forEach(function (modal) {
          modal.classList.remove('is-open'); document.body.style.overflow = '';
        });
      }
    });

    // ── Edit-pet photo uploads (one per pet modal) ────────────────────────
    document.querySelectorAll('.edit-photo-input').forEach(function (input) {
      var pk           = input.dataset.pk;
      var hasExisting  = input.dataset.hasImage === 'true';

      var previewEl  = document.getElementById('editPhotoPreview_' + pk);
      var btnTextEl  = document.getElementById('editPhotoBtnText_' + pk);
      var clearBtn   = document.getElementById('editPhotoClear_' + pk);
      var clearCb    = document.getElementById('edit_' + pk + '-profile_picture-clear');
      var hintEl     = document.getElementById('editPhotoHint_' + pk);
      var filenameEl = document.getElementById('editPhotoFilename_' + pk);

      if (!previewEl) return;

      // Snapshot original preview markup so we can restore it on cancel
      var origPreviewHTML = previewEl.innerHTML;
      var fileStaged = false;

      function resetToOriginal() {
        input.value   = '';
        fileStaged    = false;
        previewEl.innerHTML = origPreviewHTML;
        previewEl.classList.toggle('has-image', hasExisting);

        if (btnTextEl)  btnTextEl.textContent = hasExisting ? 'Change photo' : 'Choose photo';
        if (hintEl)     hintEl.style.display  = '';
        if (filenameEl) { filenameEl.textContent = ''; filenameEl.style.display = 'none'; }
        if (clearCb)    clearCb.checked = false;

        if (clearBtn) {
          clearBtn.style.cssText = '';
          clearBtn.style.display = hasExisting ? 'inline-flex' : 'none';
        }
      }

      // Live preview on file select
      input.addEventListener('change', function () {
        var file = this.files && this.files[0];
        if (!file) return;

        fileStaged = true;
        showPreview(file, previewEl);

        if (btnTextEl)  btnTextEl.textContent = 'Change photo';
        if (hintEl)     hintEl.style.display  = 'none';
        if (filenameEl) {
          filenameEl.textContent  = '\u2713 ' + truncateName(file.name, 22);
          filenameEl.style.display = 'block';
        }
        // Uncheck clear flag — new file takes priority over removal
        if (clearCb) clearCb.checked = false;
        if (clearBtn) {
          clearBtn.style.display     = 'inline-flex';
          clearBtn.style.background  = '';
          clearBtn.style.color       = '';
          clearBtn.style.borderColor = '';
        }
      });

      if (clearBtn) {
        clearBtn.addEventListener('click', function () {
          if (fileStaged) {
            // Cancel staged file — revert to original photo state
            resetToOriginal();
          } else if (hasExisting && clearCb) {
            // Toggle server-side removal of the existing photo
            clearCb.checked = !clearCb.checked;
            if (clearCb.checked) {
              clearBtn.style.background  = '#ef4444';
              clearBtn.style.color       = '#fff';
              clearBtn.style.borderColor = '#ef4444';
            } else {
              clearBtn.style.cssText = '';
              clearBtn.style.display = 'inline-flex';
            }
          }
        });
      }
    });

  }); // end DOMContentLoaded
})();
