(function () {
  "use strict";


  // The typed-answer → LaTeX conversion lives in math-notation.js, shared
  // with the results pages so the preview and the record cannot disagree.
  function toLatex(raw) {
    return window.mathNotation.toLatex(raw);
  }


  function setupMathInput(wrap) {
    var input = wrap.querySelector("[data-math-input]");
    var preview = wrap.querySelector("[data-math-preview]");
    if (!input || !preview) return;

    function renderPreview() {
      var raw = input.value.trim();
      if (!raw) {
        preview.setAttribute("data-empty", "true");
        preview.innerHTML = "";
        return;
      }
      preview.removeAttribute("data-empty");
      try {
        window.katex.render(toLatex(raw), preview, { throwOnError: false, displayMode: true });
      } catch (e) {
        preview.textContent = raw;
      }
    }

    input.addEventListener("input", renderPreview);
    renderPreview();

    setupPalette(wrap, input);
  }


  function setupPalette(wrap, input) {
    var toggle = wrap.querySelector("[data-math-palette-toggle]");
    var panel = wrap.querySelector("[data-math-palette-panel]");
    if (!toggle || !panel) return;

    if (window.katex) {
      panel.querySelectorAll("[data-latex]").forEach(function (btn) {
        try {
          window.katex.render(btn.getAttribute("data-latex"), btn, { throwOnError: true });
        } catch (e) {  }
      });
    }

    toggle.addEventListener("click", function () {
      var open = panel.hasAttribute("hidden");
      if (open) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
      wrap.classList.toggle("is-palette-open", open);
      toggle.classList.toggle("is-active", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    var tabs = panel.querySelectorAll("[data-palette-tab]");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var group = tab.getAttribute("data-palette-tab");
        tabs.forEach(function (t) {
          var on = t === tab;
          t.classList.toggle("is-active", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
        panel.querySelectorAll("[data-palette-group]").forEach(function (g) {
          if (g.getAttribute("data-palette-group") === group) g.removeAttribute("hidden");
          else g.setAttribute("hidden", "");
        });
      });
    });

    panel.querySelectorAll("[data-insert]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var token = btn.getAttribute("data-insert");
        var offset = parseInt(btn.getAttribute("data-cursor-offset"), 10) || token.length;
        var start = input.selectionStart != null ? input.selectionStart : input.value.length;
        var end = input.selectionEnd != null ? input.selectionEnd : input.value.length;
        input.value = input.value.slice(0, start) + token + input.value.slice(end);
        input.focus();
        input.selectionStart = input.selectionEnd = start + offset;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-math-input-wrap]").forEach(setupMathInput);
  });
})();
