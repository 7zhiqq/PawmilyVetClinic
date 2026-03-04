(function () {
  'use strict';

  function initModal(backdropId, openIds, closeId) {
    var backdrop = document.getElementById(backdropId);
    if (!backdrop) return;

    function openModal()  { backdrop.classList.add('is-open');    document.body.style.overflow = 'hidden'; }
    function closeModal() { backdrop.classList.remove('is-open'); document.body.style.overflow = ''; }

    openIds.forEach(function (id) {
      var btn = document.getElementById(id);
      btn && btn.addEventListener('click', openModal);
    });

    var closeBtn = document.getElementById(closeId);
    closeBtn && closeBtn.addEventListener('click', closeModal);

    backdrop.addEventListener('click', function (e) { if (e.target === backdrop) closeModal(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && backdrop.classList.contains('is-open')) closeModal();
    });

    if (backdrop.dataset.hasErrors === 'true') openModal();
  }

  initModal('bookModal',   ['openBookModal'],   'closeBookModal');
  initModal('addPetModal', ['openAddPetModal'], 'closeAddPetModal');

  var scheduleBackdrop = document.getElementById('scheduleModal');
  if (scheduleBackdrop) {
    initModal('scheduleModal', ['openScheduleModal'], 'closeScheduleModal');

    var ownerSelect = document.getElementById('id_owner');
    var petSelect   = document.getElementById('id_pet');

    function filterPetsByOwner() {
      if (!ownerSelect || !petSelect) return;
      var selectedOwnerId = ownerSelect.value;
      petSelect.querySelectorAll('option[data-owner-id]').forEach(function (opt) {
        if (selectedOwnerId === '' || opt.dataset.ownerId === selectedOwnerId) {
          opt.style.display = '';
        } else {
          opt.style.display = 'none';
          opt.selected = false;
        }
      });
      if (petSelect.selectedOptions[0] && petSelect.selectedOptions[0].style.display === 'none') {
        petSelect.value = '';
      }
    }

    ownerSelect && ownerSelect.addEventListener('change', filterPetsByOwner);
    if (scheduleBackdrop.dataset.hasErrors === 'true') filterPetsByOwner();
  }
})();