/**
 * Shared modal open/close handler.
 *
 * @param {string}   backdropId  – id of the `.modal-backdrop` element
 * @param {string[]} openIds     – ids of buttons that open the modal
 * @param {string}   closeId     – id of the close button inside the modal
 */
function initModal(backdropId, openIds, closeId) {
  'use strict';
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
