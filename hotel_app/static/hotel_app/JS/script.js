// Site-wide JS.
// NOTE: `toggleMenu` is intentionally NOT defined here — the modern drawer
// version is defined inline in navbar.html / ven_base.html so it can use
// the body-scroll lock + backdrop + ARIA state. Defining it here too would
// overwrite that newer version (load order: this file runs after the inline
// script in the included nav partial).

(function () {
  // Optional: legacy password-eye toggle for older pages that used a single
  // #togglePassword + #password element pair. Guarded so missing nodes don't
  // throw and kill subsequent JS on the page.
  document.addEventListener('DOMContentLoaded', function () {
    const passwordField = document.getElementById('password');
    const togglePassword = document.getElementById('togglePassword');
    if (!passwordField || !togglePassword) return;
    togglePassword.addEventListener('click', function () {
      const isHidden = passwordField.getAttribute('type') === 'password';
      passwordField.setAttribute('type', isHidden ? 'text' : 'password');
      this.classList.toggle('fa-eye');
      this.classList.toggle('fa-eye-slash');
    });
  });
})();
