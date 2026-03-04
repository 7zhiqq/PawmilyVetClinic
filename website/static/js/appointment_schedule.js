(function () {
  'use strict';

  var modal       = document.getElementById('scheduleModal');
  var openBtn     = document.getElementById('openScheduleModal');
  var openBtn2    = document.getElementById('openScheduleModalEmpty');
  var closeBtn    = document.getElementById('closeScheduleModal');
  var ownerSelect = document.getElementById('id_owner');
  var petSelect   = document.getElementById('id_pet');

  if (!modal) return;

  function openModal()  { modal.classList.add('is-open');    document.body.style.overflow = 'hidden'; }
  function closeModal() { modal.classList.remove('is-open'); document.body.style.overflow = ''; }

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

  openBtn  && openBtn.addEventListener('click', openModal);
  openBtn2 && openBtn2.addEventListener('click', openModal);
  closeBtn && closeBtn.addEventListener('click', closeModal);
  ownerSelect && ownerSelect.addEventListener('change', filterPetsByOwner);

  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
  });

  if (modal.dataset.hasErrors === 'true') { openModal(); filterPetsByOwner(); }
})();