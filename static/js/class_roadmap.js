(function () {
  "use strict";

  var canvas = document.querySelector(".roadmap-canvas");
  if (!canvas || canvas.classList.contains("is-preview")) return;

  var prereqs;
  try {
    prereqs = JSON.parse(canvas.getAttribute("data-roadmap-prereqs") || "{}");
  } catch (e) {
    prereqs = {};
  }

  var url = canvas.getAttribute("data-toggle-url");
  var csrf = canvas.getAttribute("data-csrf");
  var nodes = Array.prototype.slice.call(canvas.querySelectorAll(".roadmap-node"));
  var links = Array.prototype.slice.call(canvas.querySelectorAll(".path-link"));
  var includedOut = document.querySelector("[data-roadmap-included]");
  var unreachableOut = document.querySelector("[data-roadmap-unreachable]");
  var warn = document.querySelector("[data-roadmap-warn]");
  var tally = document.querySelector("[data-roadmap-tally]");

  var included = {};
  var byslug = {};
  nodes.forEach(function (node) {
    var slug = node.getAttribute("data-skill");
    byslug[slug] = node;
    included[slug] = node.getAttribute("aria-pressed") === "true";
  });

  var order = (function () {
    var seen = {};
    var out = [];
    function visit(slug) {
      if (seen[slug] === 1 || !byslug[slug]) return;
      seen[slug] = 1;
      (prereqs[slug] || []).forEach(visit);
      out.push(slug);
    }
    Object.keys(byslug).forEach(visit);
    return out;
  })();

  var STATES = ["is-included", "is-excluded", "is-unreachable"];
  var LABELS = {
    "is-included": "Included in the roadmap",
    "is-excluded": "Excluded from the roadmap",
    "is-unreachable": "Included, but unreachable — a prerequisite is excluded"
  };

  function render() {
    var reachable = {};
    var unreachableCount = 0;
    var includedCount = 0;

    order.forEach(function (slug) {
      var ok = included[slug];
      if (ok) {
        includedCount++;
        (prereqs[slug] || []).forEach(function (p) {
          if (!reachable[p]) ok = false;
        });
      }
      reachable[slug] = ok;

      var state = !included[slug] ? "is-excluded" : ok ? "is-included" : "is-unreachable";
      if (state === "is-unreachable") unreachableCount++;

      var node = byslug[slug];
      if (!node.classList.contains(state)) {
        STATES.forEach(function (s) { node.classList.toggle(s, s === state); });
        node.classList.remove("is-just-changed");
        void node.offsetWidth;
        node.classList.add("is-just-changed");
      }
      node.setAttribute("aria-pressed", included[slug] ? "true" : "false");
      var say = node.querySelector("[data-roadmap-state]");
      if (say) say.textContent = LABELS[state];
    });

    links.forEach(function (link) {
      var source = link.getAttribute("data-source");
      var target = link.getAttribute("data-target");
      var severed = included[target] && !reachable[source];
      link.classList.toggle("is-severed", severed);
      link.classList.toggle("is-dimmed", !severed && (!included[source] || !included[target]));
      link.classList.toggle("is-live", !!(reachable[source] && reachable[target]));
    });

    if (includedOut) includedOut.textContent = includedCount;
    if (unreachableOut) unreachableOut.textContent = unreachableCount;
    if (warn) warn.hidden = unreachableCount === 0;
    if (tally) tally.classList.toggle("has-warning", unreachableCount > 0);
  }

  function save(node, slug, next) {
    var body = new FormData();
    body.append("skill_id", node.getAttribute("data-skill-id"));
    body.append("available", next ? "true" : "false");
    body.append("csrfmiddlewaretoken", csrf);
    node.classList.add("is-saving");
    return fetch(url, {
      method: "POST",
      body: body,
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (data) {
        node.classList.remove("is-saving");
        if (data.available !== next) {
          included[slug] = data.available;
          render();
        }
      })
      .catch(function () {
        node.classList.remove("is-saving");
        included[slug] = !next;
        render();
        node.classList.add("is-save-failed");
        window.setTimeout(function () {
          node.classList.remove("is-save-failed");
        }, 2400);
      });
  }

  nodes.forEach(function (node) {
    var slug = node.getAttribute("data-skill");

    node.addEventListener("click", function () {
      if (node.classList.contains("is-saving")) return;
      included[slug] = !included[slug];
      render();
      save(node, slug, included[slug]);
    });

    function isolate() {
      canvas.classList.add("is-hovering-node");
      links.forEach(function (link) {
        link.classList.toggle("is-faded", link.getAttribute("data-target") !== slug);
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

  render();
})();
