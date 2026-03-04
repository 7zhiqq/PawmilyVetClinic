(function () {
  'use strict';
  var modal    = document.getElementById('addPetModal');
  var openBtn  = document.getElementById('openAddPet');
  var openBtn2 = document.getElementById('openAddPetEmpty');
  var closeBtn = document.getElementById('closeAddPet');
  if (!modal) return;

  function openModal()  { modal.classList.add('is-open');    document.body.style.overflow = 'hidden'; }
  function closeModal() { modal.classList.remove('is-open'); document.body.style.overflow = ''; }

  openBtn  && openBtn.addEventListener('click', openModal);
  openBtn2 && openBtn2.addEventListener('click', openModal);
  closeBtn && closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
  });
  if (modal.dataset.hasErrors === 'true') openModal();
})();