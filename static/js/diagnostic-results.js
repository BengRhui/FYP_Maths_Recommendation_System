(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var page = document.querySelector(".dr-page");
  if (!page || reduceMotion) return;

  requestAnimationFrame(function () {
    page.classList.add("is-cued");
    requestAnimationFrame(function () {
      page.classList.add("is-playing");
      page.classList.remove("is-cued");

      var cols = Array.prototype.slice.call(page.querySelectorAll('.dr-col-fill'));
      cols.forEach(function (col) {
        var label = col.querySelector('.dr-col-fill-level');
        if (!label) return;
        var onEnd = function (e) {
          if (e.propertyName !== 'height') return;
          label.classList.add('is-visible');
          col.removeEventListener('transitionend', onEnd);
        };
        col.addEventListener('transitionend', onEnd);
        var delay = 900 + (parseInt(getComputedStyle(col).getPropertyValue('--i') || 0) * 90);
        setTimeout(function () { if (!label.classList.contains('is-visible')) label.classList.add('is-visible'); }, delay);
      });

    });
  });
})();
