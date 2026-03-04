(function () {
  'use strict';
  var backdrop  = document.getElementById('inviteModal');
  var emailEl   = document.getElementById('inviteModalEmail');
  var roleEl    = document.getElementById('inviteModalRole');
  var statusEl  = document.getElementById('inviteModalStatus');
  var linkInput = document.getElementById('inviteModalLink');
  var closeBtn  = document.getElementById('inviteModalClose');
  var copyBtn   = document.getElementById('inviteModalCopy');
  var openBtn   = document.getElementById('inviteModalOpenLink');
  if (!backdrop) return;

  function openModal(data) {
    emailEl.textContent  = data.email  || '';
    roleEl.textContent   = data.role   || '';
    statusEl.textContent = data.status || '';
    linkInput.value      = data.url    || '';
    backdrop.classList.add('is-open');
  }
  function closeModal() { backdrop.classList.remove('is-open'); }

  document.querySelectorAll('.invite-view-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openModal({ email: this.dataset.email, role: this.dataset.role,
                  status: this.dataset.status, url: this.dataset.url });
    });
  });

  backdrop.addEventListener('click', function (e) { if (e.target === backdrop) closeModal(); });
  closeBtn && closeBtn.addEventListener('click', closeModal);

  copyBtn && copyBtn.addEventListener('click', function () {
    if (!linkInput.value) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(linkInput.value);
    } else { linkInput.select(); document.execCommand('copy'); }
  });

  openBtn && openBtn.addEventListener('click', function () {
    if (linkInput.value) window.open(linkInput.value, '_blank');
  });
})();