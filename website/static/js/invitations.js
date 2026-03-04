// Modal functionality for invitations
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('inviteModal');
  const modalClose = document.getElementById('inviteModalClose');
  const modalEmail = document.getElementById('inviteModalEmail');
  const modalRole = document.getElementById('inviteModalRole');
  const modalStatus = document.getElementById('inviteModalStatus');
  const modalLink = document.getElementById('inviteModalLink');
  const modalCopy = document.getElementById('inviteModalCopy');
  const modalOpenLink = document.getElementById('inviteModalOpenLink');
  const viewButtons = document.querySelectorAll('.invite-view-btn');

  // Open modal when clicking view button
  viewButtons.forEach(button => {
    button.addEventListener('click', function() {
      const email = this.getAttribute('data-email');
      const role = this.getAttribute('data-role');
      const status = this.getAttribute('data-status');
      const url = this.getAttribute('data-url');

      modalEmail.textContent = email;
      modalRole.textContent = role;
      modalStatus.textContent = status;
      modalLink.value = url;

      modal.style.display = 'flex';
    });
  });

  // Close modal
  modalClose.addEventListener('click', function() {
    modal.style.display = 'none';
  });

  // Close modal when clicking backdrop
  modal.addEventListener('click', function(e) {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });

  // Copy link to clipboard
  modalCopy.addEventListener('click', function() {
    modalLink.select();
    modalLink.setSelectionRange(0, 99999); // For mobile devices
    
    navigator.clipboard.writeText(modalLink.value).then(function() {
      const originalText = modalCopy.innerHTML;
      modalCopy.innerHTML = '<i class="fa-solid fa-check" style="font-size:0.7rem;"></i> Copied!';
      
      setTimeout(function() {
        modalCopy.innerHTML = originalText;
      }, 2000);
    }).catch(function(err) {
      alert('Failed to copy link: ' + err);
    });
  });

  // Open link in new tab
  modalOpenLink.addEventListener('click', function() {
    window.open(modalLink.value, '_blank');
  });

  // Close modal with Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && modal.style.display === 'flex') {
      modal.style.display = 'none';
    }
  });
});
