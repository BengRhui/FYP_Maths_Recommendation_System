(function () {
  "use strict";

  var canvas = document.querySelector(".path-canvas");
  if (!canvas) return;

  var links = canvas.querySelectorAll(".path-link");

  canvas.querySelectorAll(".path-node").forEach(function (node) {
    var skill = node.getAttribute("data-skill");

    function isolate() {
      canvas.classList.add("is-hovering-node");
      links.forEach(function (link) {
        link.classList.toggle("is-faded", link.getAttribute("data-target") !== skill);
      });
    }

    function reset() {
      canvas.classList.remove("is-hovering-node");
      links.forEach(function (link) { link.classList.remove("is-faded"); });
    }

    node.addEventListener("mouseenter", isolate);
    node.addEventListener("mouseleave", reset);
    node.addEventListener("focus", isolate);
    node.addEventListener("blur", reset);
  });

  var modalEl = document.getElementById("skillModal");
  var modalBody = document.getElementById("skillModalBody");
  if (!modalEl || !modalBody || !window.bootstrap) return;

  var modal = new window.bootstrap.Modal(modalEl);
  var loadingHtml = modalBody.innerHTML;

  canvas.querySelectorAll("a.path-node").forEach(function (node) {
    node.addEventListener("click", function (e) {
      e.preventDefault();
      var url = node.getAttribute("href");
      modalBody.innerHTML = loadingHtml;
      modal.show();
      fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (resp) { return resp.text(); })
        .then(function (html) { modalBody.innerHTML = html; })
        .catch(function () {
          modalBody.innerHTML = '<p class="text-center text-muted-2 py-5">Could not load this skill. Please try again.</p>';
        });
    });
  });
})();
