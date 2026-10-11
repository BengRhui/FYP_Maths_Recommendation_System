(function () {
  "use strict";

  document.addEventListener("click", function (e) {
    document.querySelectorAll(".activity-filter-menu[open]").forEach(function (menu) {
      if (!menu.contains(e.target)) menu.removeAttribute("open");
    });
  });

  var loadMoreLink = document.getElementById("activityLoadMoreLink");
  var rowsBox = document.getElementById("activityRows");
  var loadMoreWrap = document.getElementById("activityLoadMore");
  if (loadMoreLink && rowsBox && loadMoreWrap) {
    loadMoreLink.addEventListener("click", function (e) {
      e.preventDefault();
      var url = loadMoreLink.getAttribute("href");
      fetch(url)
        .then(function (resp) { return resp.text(); })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, "text/html");
          var fetchedRows = doc.querySelectorAll("#activityRows .activity-row");
          var currentCount = rowsBox.querySelectorAll(".activity-row").length;
          fetchedRows.forEach(function (row, i) {
            if (i >= currentCount) rowsBox.appendChild(row.cloneNode(true));
          });

          var nextLink = doc.getElementById("activityLoadMoreLink");
          if (nextLink) {
            loadMoreLink.setAttribute("href", nextLink.getAttribute("href"));
          } else {
            loadMoreWrap.remove();
          }

          if (window.history && window.history.replaceState) {
            window.history.replaceState(null, "", url);
          }
        });
    });
  }

  var reviewModalEl = document.getElementById("reviewModal");
  var reviewModalBody = document.getElementById("reviewModalBody");
  if (!reviewModalEl || !reviewModalBody || !window.bootstrap) return;

  var reviewModal = new window.bootstrap.Modal(reviewModalEl);
  var loadingHtml = reviewModalBody.innerHTML;

  // This markup arrives by fetch, long after app.js has prepared the panels
  // that were in the document at load, so each new one is prepared here and
  // driven through the same collapse helpers.
  function bindReviewToggles(container) {
    var collapse = window.mpCollapse;
    // The "show step-by-step explanation" controls inside each card arrive with
    // this markup too, so they need binding alongside the cards themselves.
    if (collapse && collapse.bindAriaToggles) collapse.bindAriaToggles(container);
    container.querySelectorAll("[data-review-toggle]").forEach(function (head) {
      if (collapse) collapse.prepare(head);
      head.addEventListener("click", function () {
        if (collapse) { collapse.openExclusive(head); return; }
        var body = document.getElementById(head.getAttribute("aria-controls"));
        if (!body) return;
        var open = body.hasAttribute("hidden");
        if (open) { body.removeAttribute("hidden"); head.setAttribute("aria-expanded", "true"); }
        else { body.setAttribute("hidden", ""); head.setAttribute("aria-expanded", "false"); }
      });
    });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-review-url]");
    if (!btn) return;
    if (!e.target.closest("button, a") &&
        window.getSelection && String(window.getSelection()).trim() !== "") return;
    reviewModalBody.innerHTML = loadingHtml;
    reviewModal.show();
    fetch(btn.getAttribute("data-review-url"), { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (resp) { return resp.text(); })
      .then(function (html) {
        reviewModalBody.innerHTML = html;
        bindReviewToggles(reviewModalBody);
        if (window.renderMathContent) window.renderMathContent(reviewModalBody);
      })
      .catch(function () {
        reviewModalBody.innerHTML = '<p class="text-center text-muted-2 py-5">Could not load this attempt. Please try again.</p>';
      });
  });
})();
