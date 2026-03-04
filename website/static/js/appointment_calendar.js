(function () {
  'use strict';

  /* Book modal – pet owner */
  var bookModal = document.getElementById('bookModal');
  var openBook  = document.getElementById('openBookModal');
  var closeBook = document.getElementById('closeBookModal');

  if (bookModal) {
    function openBookModal()  { bookModal.classList.add('is-open');    document.body.style.overflow = 'hidden'; }
    function closeBookModal() { bookModal.classList.remove('is-open'); document.body.style.overflow = ''; }

    openBook  && openBook.addEventListener('click', openBookModal);
    closeBook && closeBook.addEventListener('click', closeBookModal);
    bookModal.addEventListener('click', function (e) { if (e.target === bookModal) closeBookModal(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && bookModal.classList.contains('is-open')) closeBookModal();
    });
    if (bookModal.dataset.hasErrors === 'true') openBookModal();
  }

  /* Schedule / Walk-in modal – staff */
  var scheduleModal = document.getElementById('scheduleModal');
  var openSchedule  = document.getElementById('openScheduleModal');
  var closeSchedule = document.getElementById('closeScheduleModal');

  if (scheduleModal) {
    var ownerSelect = document.getElementById('id_owner');
    var petSelect   = document.getElementById('id_pet');

    function openScheduleModal()  { scheduleModal.classList.add('is-open');    document.body.style.overflow = 'hidden'; }
    function closeScheduleModal() { scheduleModal.classList.remove('is-open'); document.body.style.overflow = ''; }

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

    openSchedule  && openSchedule.addEventListener('click', openScheduleModal);
    closeSchedule && closeSchedule.addEventListener('click', closeScheduleModal);
    ownerSelect   && ownerSelect.addEventListener('change', filterPetsByOwner);
    scheduleModal.addEventListener('click', function (e) { if (e.target === scheduleModal) closeScheduleModal(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && scheduleModal.classList.contains('is-open')) closeScheduleModal();
    });
    if (scheduleModal.dataset.hasErrors === 'true') { openScheduleModal(); filterPetsByOwner(); }
  }
})();