(function () {
  // Apply theme as early as possible to reduce flashing
  const stored = localStorage.getItem("theme");

  // If user never chose a theme, use system preference
  const systemPrefersDark =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  const theme = stored || (systemPrefersDark ? "dark" : "light");

  if (theme === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }

  window.toggleTheme = function () {
    document.documentElement.classList.toggle("dark");
    const isDark = document.documentElement.classList.contains("dark");
    localStorage.setItem("theme", isDark ? "dark" : "light");

    //  NEW: tell charts to redraw instantly (no refresh)
    window.dispatchEvent(new Event("preventab:theme-changed"));
  };
})();