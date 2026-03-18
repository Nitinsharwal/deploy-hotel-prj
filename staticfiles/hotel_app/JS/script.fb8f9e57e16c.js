function toggleMenu() {
    const navLinks = document.getElementById('nav-links');
    navLinks.classList.toggle('show');
}
const passwordField = document.getElementById("password");
const otp = document.getElementById("otp");
const togglePassword = document.getElementById("togglePassword");

togglePassword.addEventListener("click", function () {
  const type = passwordField.getAttribute("type") === "password" ? "text" : "password";
  passwordField.setAttribute("type", type);

  this.classList.toggle("fa-eye");
  this.classList.toggle("fa-eye-slash");
});