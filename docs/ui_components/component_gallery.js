const buttons = document.querySelectorAll("[data-theme-class]");
buttons.forEach((button) => {
  button.addEventListener("click", () => {
    document.body.className = button.dataset.themeClass;
  });
});
