(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function playMeter() {
    var meter = document.querySelector(".results-meter[data-meter-from]");
    if (!meter || reduceMotion) return;
    var fill = meter.querySelector("span");
    if (!fill) return;
    var from = meter.getAttribute("data-meter-from");
    var to = fill.style.width;
    if (from === null || from + "%" === to) return;

    requestAnimationFrame(function () {
      fill.style.width = from + "%";
      requestAnimationFrame(function () {
        meter.classList.add("is-animating");
        fill.style.width = to;
      });
    });
  }

  function countUp() {
    var el = document.querySelector(".results-mastery-value[data-count-from]");
    if (!el || reduceMotion) return;
    var from = parseInt(el.getAttribute("data-count-from"), 10);
    var to = parseInt(el.getAttribute("data-count-to"), 10);
    if (isNaN(from) || isNaN(to) || from === to) return;

    var started = null;
    var duration = 1000;
    function frame(now) {
      if (started === null) started = now;
      var t = Math.min((now - started) / duration, 1);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(from + (to - from) * eased) + "%";
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    settle(el, to + "%");
  }

  function settle(el, finalText) {
    var done = false;
    function finish() {
      if (done) return;
      done = true;
      el.textContent = finalText;
      document.removeEventListener("visibilitychange", onHide);
    }
    function onHide() {
      if (document.hidden) finish();
    }
    document.addEventListener("visibilitychange", onHide);
    setTimeout(finish, 1200);
  }

  playMeter();
  countUp();
})();
