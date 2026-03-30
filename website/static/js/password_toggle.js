document.addEventListener("DOMContentLoaded", function () {
  var passwordInputs = document.querySelectorAll(".login-form input[type='password']");

  passwordInputs.forEach(function (input, index) {
    if (input.dataset.passwordToggleReady === "true") {
      return;
    }

    var wrapper = document.createElement("div");
    wrapper.className = "password-toggle-wrap";

    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    var toggleButton = document.createElement("button");
    toggleButton.type = "button";
    toggleButton.className = "password-toggle-btn";
    toggleButton.setAttribute("aria-controls", input.id || "password-input-" + index);
    toggleButton.setAttribute("aria-label", "Show password");
    toggleButton.setAttribute("aria-pressed", "false");

    if (!input.id) {
      input.id = "password-input-" + index;
    }

    var icon = document.createElement("i");
    icon.className = "fa-regular fa-eye";
    icon.setAttribute("aria-hidden", "true");
    toggleButton.appendChild(icon);

    toggleButton.addEventListener("click", function () {
      var isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";

      icon.className = isHidden ? "fa-regular fa-eye-slash" : "fa-regular fa-eye";
      toggleButton.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
      toggleButton.setAttribute("aria-pressed", isHidden ? "true" : "false");
    });

    wrapper.appendChild(toggleButton);
    input.dataset.passwordToggleReady = "true";
  });
});
