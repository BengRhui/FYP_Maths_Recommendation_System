(function () {
  "use strict";

  function initPasswordUI(root) {
    root.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var input = document.getElementById(btn.getAttribute("data-toggle-password"));
        if (!input) return;
        var showing = input.type === "text";
        input.type = showing ? "password" : "text";
        btn.classList.toggle("is-visible", !showing);
        btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      });
    });

    root.querySelectorAll("[data-password-requirements]").forEach(function (box) {
      var input = document.getElementById(box.getAttribute("data-password-requirements"));
      if (!input) return;
      var items = box.querySelectorAll("[data-req]");

      function refresh() {
        var value = input.value;
        var allMet = true;
        items.forEach(function (item) {
          var rule = item.getAttribute("data-req");
          var met = false;
          if (rule === "length") met = value.length >= 8;
          else if (rule === "letter") met = /[a-zA-Z]/.test(value);
          else if (rule === "number") met = /[0-9]/.test(value);
          else if (rule === "special") met = /[^a-zA-Z0-9]/.test(value);
          if (!met) allMet = false;
          var dot = item.querySelector(".req-dot");
          if (dot) dot.classList.toggle("met", met);
        });
        box.classList.toggle("all-met", allMet);
      }

      input.addEventListener("input", refresh);
      refresh();
    });
  }

  initPasswordUI(document);

  function fitAuthShell() {
    var shell = document.querySelector(".auth-shell, .auth-shell-wide");
    if (!shell) return;
    shell.style.marginTop = "";
    var doc = document.documentElement;
    var overflow = doc.scrollHeight - doc.clientHeight;
    if (overflow <= 0) return;
    var minGapUnderNav = 4;
    var maxShift = parseFloat(getComputedStyle(shell).paddingTop) - minGapUnderNav;
    var shift = Math.min(overflow, Math.max(maxShift, 0));
    if (shift > 0) shell.style.marginTop = "-" + shift + "px";
  }
  if (document.querySelector(".auth-shell, .auth-shell-wide")) {
    fitAuthShell();
    window.addEventListener("load", fitAuthShell);
    window.addEventListener("resize", fitAuthShell);
  }

  document.querySelectorAll("[data-password-modal-body]").forEach(function (modalBody) {
    var pristineHtml = modalBody.innerHTML;
    var modalEl = modalBody.closest(".modal");
    if (!modalEl) return;
    modalEl.addEventListener("hidden.bs.modal", function () {
      modalBody.innerHTML = pristineHtml;
      initPasswordUI(modalBody);
    });
  });

  document.addEventListener("submit", function (e) {
    var form = e.target.closest("[data-password-form]");
    if (!form) return;
    var modalBody = form.closest("[data-password-modal-body]");
    if (!modalBody) return;
    e.preventDefault();

    var submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    fetch(window.location.href, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          window.location.reload();
          return;
        }
        modalBody.innerHTML = data.html;
        initPasswordUI(modalBody);
      })
      .catch(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  });
})();
