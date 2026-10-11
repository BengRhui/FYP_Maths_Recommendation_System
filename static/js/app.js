(function () {
  "use strict";

  document.querySelectorAll("[data-autoopen]").forEach(function (modal) {
    if (window.bootstrap && window.bootstrap.Modal) {
      window.bootstrap.Modal.getOrCreateInstance(modal).show();
    }
  });

  var createClassForm = document.querySelector("#createClassModal form");
  if (createClassForm) {
    var createClassName = createClassForm.querySelector("[name=name]");
    var showNameError = function () {
      var field = createClassName.closest(".mb-3");
      var errors = field.querySelector(".errorlist");
      if (!errors) {
        errors = document.createElement("ul");
        errors.className = "errorlist";
        field.appendChild(errors);
      }
      errors.innerHTML = "<li>This field is required.</li>";
    };
    var clearNameError = function () {
      var errors = createClassName.closest(".mb-3").querySelector(".errorlist");
      if (errors) errors.remove();
    };
    createClassForm.addEventListener("submit", function (e) {
      if (!createClassName.value.trim()) {
        e.preventDefault();
        showNameError();
        createClassName.focus();
      }
    });
    createClassName.addEventListener("input", function () {
      if (createClassName.value.trim()) clearNameError();
    });
    createClassForm.closest(".modal").addEventListener("hidden.bs.modal", function () {
      createClassForm.reset();
      clearNameError();
    });
  }

  document.querySelectorAll(".toast-mp").forEach(function (t) {
    setTimeout(function () {
      t.style.transition = "opacity .4s";
      t.style.opacity = "0";
      setTimeout(function () { t.remove(); }, 400);
    }, 5000);
  });

  document.querySelectorAll("[data-answer-form]").forEach(function (form) {
    var submitBtn = form.querySelector("[data-continue]");
    var timerField = form.querySelector("[name=response_time_sec]");
    var started = Date.now();

    function refresh() {
      var hasAnswer = false;
      var radios = form.querySelectorAll('input[type=radio]');
      if (radios.length) {
        radios.forEach(function (r) { if (r.checked) hasAnswer = true; });
      }
      var textInput = form.querySelector('[data-text-answer]');
      if (textInput && textInput.value.trim() !== "") hasAnswer = true;
      if (submitBtn) submitBtn.disabled = !hasAnswer;
    }

    form.querySelectorAll(".answer-row").forEach(function (row) {
      row.addEventListener("click", function () {
        var radio = row.querySelector('input[type=radio]');
        if (radio) radio.checked = true;
        form.querySelectorAll(".answer-row").forEach(function (r) { r.classList.remove("selected"); });
        row.classList.add("selected");
        refresh();
      });
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); row.click(); }
      });
    });

    var textInput = form.querySelector('[data-text-answer]');
    if (textInput) textInput.addEventListener("input", refresh);

    form.addEventListener("submit", function () {
      if (timerField) timerField.value = ((Date.now() - started) / 1000).toFixed(1);
    });

    refresh();
  });

  // Review questions use the same collapsing wrapper as the other disclosures
  // (discPrepare and friends are declared further down and hoisted), so a
  // question opens and folds on the app's curve instead of snapping.
  // Content fetched after load (the review modal on the activity page) has to
  // prepare its own panels, so the collapse helpers are shared rather than
  // reimplemented there.
  window.mpCollapse = {
    prepare: discPrepare,
    setOpen: discSetOpen,
    isOpen: discIsOpen,
    openExclusive: reviewOpenExclusive,
    bindAriaToggles: bindAriaToggles
  };

  // Reviewing is a one-at-a-time job: opening a question folds whichever one
  // was already open, so the list never grows into a wall of stacked answers.
  // Scoped to the list the question belongs to, so the modal and the results
  // page each behave as their own accordion.
  function reviewOpenExclusive(head) {
    if (discIsOpen(head)) { discSetOpen(head, false); return; }
    var scope = head.closest(".review-scroll, .results-review") || document;
    scope.querySelectorAll("[data-review-toggle]").forEach(function (other) {
      if (other !== head && discIsOpen(other)) discSetOpen(other, false);
    });
    discSetOpen(head, true);
  }

  document.querySelectorAll("[data-review-toggle]").forEach(discPrepare);

  document.querySelectorAll("[data-review-toggle]").forEach(function (head) {
    head.addEventListener("click", function () { reviewOpenExclusive(head); });
  });

  // These panels collapse purely in CSS off aria-expanded, so the handler only
  // has to flip the attribute. Takes a root because fetched markup (the review
  // modal) has to bind its own.
  function bindAriaToggles(root) {
    (root || document)
      .querySelectorAll("[data-band-toggle], [data-steps-toggle]")
      .forEach(function (head) {
        if (head.dataset.ariaToggleBound) return;
        head.dataset.ariaToggleBound = "1";
        head.addEventListener("click", function () {
          head.setAttribute(
            "aria-expanded",
            head.getAttribute("aria-expanded") === "true" ? "false" : "true"
          );
        });
      });
  }
  bindAriaToggles(document);

  document.addEventListener("click", function (e) {
    var row = e.target.closest("[data-row-href]");
    if (!row) return;
    if (e.target.closest("a, button, input, label, select, form")) return;
    if (window.getSelection && String(window.getSelection()).trim() !== "") return;
    var url = row.getAttribute("data-row-href");
    if (e.metaKey || e.ctrlKey || e.shiftKey) window.open(url, "_blank");
    else window.location.href = url;
  });

  (function () {
    var head = document.querySelector(".sd-attempts thead");
    var scroller = head && head.closest(".sd-panel-scroll");
    if (!scroller) return;
    var publish = function () {
      scroller.style.setProperty("--sd-thead-h", head.offsetHeight + "px");
    };
    publish();
    window.addEventListener("resize", publish);
  })();

  // The solution lives in its own table row that was simply un-hidden. A <tr>
  // cannot carry the collapsing grid itself, so the wrapper goes around the
  // panel inside its cell and the row's height follows it. The cell's padding
  // moves onto the panel (see app.css) or the closed row would never reach
  // zero height.
  function attemptPanelWrap(head) {
    var body = document.getElementById(head.getAttribute("aria-controls"));
    var panel = body && body.querySelector(".sd-solution");
    if (!panel) return null;
    var track = panel.parentNode;
    if (track.classList && track.classList.contains("collapse-fx-track")) return track.parentNode;
    return null;
  }

  function attemptPrepare(head) {
    var body = document.getElementById(head.getAttribute("aria-controls"));
    var panel = body && body.querySelector(".sd-solution");
    if (!panel || attemptPanelWrap(head)) return;
    var wrap = document.createElement("div");
    wrap.className = "collapse-fx";
    var track = document.createElement("div");
    track.className = "collapse-fx-track";
    panel.parentNode.insertBefore(wrap, panel);
    wrap.appendChild(track);
    track.appendChild(panel);
    // A row left in the flow can never measure zero in a collapsed-border
    // table: the cell always absorbs half of each neighbour's border, so an
    // "empty" row still shows a ~1px sliver between every attempt and makes
    // the rule above an open row look thicker than the one below it. Hide the
    // row again once it has finished collapsing.
    wrap.addEventListener("transitionend", function (e) {
      if (e.target !== wrap || e.propertyName !== "grid-template-rows") return;
      if (!wrap.classList.contains("is-open")) body.setAttribute("hidden", "");
    });
    // The summary row collapses to nothing while open, so the panel itself
    // carries the close. Clicks on a control inside it, or a click that ends a
    // text selection, are left alone.
    body.addEventListener("click", function (e) {
      if (e.target.closest("a, button, input, label, select, form")) return;
      if (window.getSelection && String(window.getSelection()).trim() !== "") return;
      attemptSetOpen(head, false);
    });
  }

  function attemptSetOpen(head, open) {
    var body = document.getElementById(head.getAttribute("aria-controls"));
    if (!body) return;
    head.setAttribute("aria-expanded", open ? "true" : "false");
    var wrap = attemptPanelWrap(head);
    if (!wrap) {
      if (open) body.removeAttribute("hidden");
      else body.setAttribute("hidden", "");
      return;
    }
    if (open) {
      // Put the row back in the flow, let that land, then run the collapse.
      body.removeAttribute("hidden");
      void wrap.offsetHeight;
      wrap.classList.add("is-open");
    } else {
      wrap.classList.remove("is-open");
    }
  }

  document.querySelectorAll("[data-attempt-toggle]").forEach(attemptPrepare);

  document.querySelectorAll("[data-attempt-toggle]").forEach(function (head) {
    var row = head.closest("tr");
    if (!row) return;
    row.addEventListener("click", function () {
      if (window.getSelection && String(window.getSelection()).length) return;
      if (head.getAttribute("aria-expanded") === "true") { attemptSetOpen(head, false); return; }
      var tbody = head.closest("tbody");
      if (tbody) {
        tbody.querySelectorAll("[data-attempt-toggle]").forEach(function (other) {
          if (other !== head && other.getAttribute("aria-expanded") === "true") attemptSetOpen(other, false);
        });
      }
      attemptSetOpen(head, true);
    });
  });

  // Disclosure sections open on an animated height so the rows below are
  // pushed down rather than jumping. The collapsing wrapper is built here
  // instead of in each of the templates that owns one of these panels, and
  // the markup keeps its `hidden` attribute so a page without JS still
  // renders the panels closed.
  function discBody(head) {
    return document.getElementById(head.getAttribute("aria-controls"));
  }

  function discWrap(head) {
    var body = discBody(head);
    if (!body) return null;
    var track = body.parentNode;
    if (!track || !track.classList || !track.classList.contains("collapse-fx-track")) return null;
    return track.parentNode;
  }

  function discPrepare(head) {
    var body = discBody(head);
    // "instant" opts a panel out: the mastery distribution opens sideways,
    // not downward, so a height animation would describe the wrong motion.
    if (!body || head.getAttribute("data-skillset-toggle") === "instant") return;
    if (discWrap(head)) return;
    var wrap = document.createElement("div");
    // "sideways" panels sit beside their head rather than under it, so they
    // reveal by the head narrowing instead of by a height change.
    wrap.className = head.getAttribute("data-skillset-toggle") === "sideways"
      ? "collapse-fx-x"
      : "collapse-fx";
    // The grid item has to be a bare box: a panel's own padding and border
    // still count toward the row's minimum size, so putting them one level
    // in is what lets the closed state actually reach zero height.
    var track = document.createElement("div");
    track.className = "collapse-fx-track";
    body.parentNode.insertBefore(wrap, body);
    wrap.appendChild(track);
    track.appendChild(body);
    body.removeAttribute("hidden");
    if (head.getAttribute("aria-expanded") === "true") wrap.classList.add("is-open");

    // A review card hides its summary row while open, so the panel carries the
    // close. Scoped to that panel: the results page keeps its header visible
    // and must not close when someone clicks the working.
    if (body.classList.contains("review-body")) {
      body.addEventListener("click", function (e) {
        if (e.target.closest("a, button, input, label, select, form")) return;
        if (window.getSelection && String(window.getSelection()).trim() !== "") return;
        discSetOpen(head, false);
      });
    }
  }

  function discIsOpen(head) {
    var wrap = discWrap(head);
    if (wrap) return wrap.classList.contains("is-open");
    var body = discBody(head);
    return !!body && !body.hasAttribute("hidden");
  }

  function discSetOpen(head, open) {
    var body = discBody(head);
    if (!body) return;
    var wrap = discWrap(head);
    if (wrap) wrap.classList.toggle("is-open", open);
    else if (open) body.removeAttribute("hidden");
    else body.setAttribute("hidden", "");
    head.setAttribute("aria-expanded", open ? "true" : "false");
  }

  document.querySelectorAll("[data-skillset-toggle], [data-example-toggle]").forEach(discPrepare);

  // A sideways panel's card is only as tall as the taller of its head and its
  // panel. Starting the panel from zero means the card's height sits pinned at
  // the head's height for the first third of the animation and then lurches --
  // and during an accordion switch the closing card shrinks while the opening
  // one is still pinned, so the modal dips and rebounds. Starting the panel at
  // the head's own height makes card height and panel height the same number
  // throughout, so both cards move on the curve from the first frame.
  function syncSidewaysHeads(scope) {
    (scope || document).querySelectorAll('[data-skillset-toggle="sideways"]').forEach(function (h) {
      var card = h.closest(".pskill-card");
      if (card) card.style.setProperty("--sw-head-h", h.getBoundingClientRect().height + "px");
    });
  }
  window.addEventListener("resize", function () { syncSidewaysHeads(); });

  document.querySelectorAll("[data-skillset-toggle]").forEach(function (head) {
    head.addEventListener("click", function () {
      syncSidewaysHeads(head.closest(".modal-body") || document);
      if (discIsOpen(head)) { discSetOpen(head, false); return; }
      var container = head.closest(".modal-body");
      if (container) {
        container.querySelectorAll("[data-skillset-toggle]").forEach(function (otherHead) {
          if (otherHead !== head && discIsOpen(otherHead)) discSetOpen(otherHead, false);
        });
      }
      discSetOpen(head, true);
    });
  });

  document.querySelectorAll("[data-example-toggle]").forEach(function (head) {
    head.addEventListener("click", function () { discSetOpen(head, !discIsOpen(head)); });
  });

  document.querySelectorAll("[data-solution-toggle]").forEach(discPrepare);

  document.querySelectorAll("[data-solution-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var show = !discIsOpen(btn);
      discSetOpen(btn, show);
      btn.textContent = show
        ? btn.getAttribute("data-hide-label") || "Hide Solution"
        : btn.getAttribute("data-show-label") || "Show Solution";
    });
  });

  (function () {
    var modalEl = document.getElementById("confirmModal");
    var modal = modalEl && window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : null;
    var messageEl = modalEl && modalEl.querySelector("[data-confirm-message]");
    var acceptBtn = modalEl && modalEl.querySelector("[data-confirm-accept]");
    var pendingForm = null;

    document.querySelectorAll("[data-confirm]").forEach(function (el) {
      el.addEventListener("submit", function (e) {
        if (el.dataset.confirmSkip) { delete el.dataset.confirmSkip; return; }
        e.preventDefault();
        if (!modal) {
          if (window.confirm(el.getAttribute("data-confirm"))) el.submit();
          return;
        }
        pendingForm = el;
        if (messageEl) messageEl.textContent = el.getAttribute("data-confirm");

        var parentModalEl = el.closest(".modal");
        var parentModal = parentModalEl && parentModalEl !== modalEl && window.bootstrap
          ? window.bootstrap.Modal.getInstance(parentModalEl)
          : null;
        if (parentModal) {
          parentModalEl.addEventListener("hidden.bs.modal", function onHidden() {
            parentModalEl.removeEventListener("hidden.bs.modal", onHidden);
            modal.show();
          });
          parentModal.hide();
        } else {
          modal.show();
        }
      });
    });

    if (acceptBtn) {
      acceptBtn.addEventListener("click", function () {
        modal.hide();
        if (!pendingForm) return;
        pendingForm.dataset.confirmSkip = "true";
        if (pendingForm.requestSubmit) pendingForm.requestSubmit();
        else pendingForm.submit();
        pendingForm = null;
      });
    }
  })();

  (function () {
    var scroller = document.querySelector(".class-activity-scroll");
    var cardHead = scroller && scroller.querySelector(".activity-card-head");
    if (scroller && cardHead) {
      var publishHeadHeight = function () {
        scroller.style.setProperty(
          "--activity-head-h",
          cardHead.offsetHeight + "px"
        );
      };
      publishHeadHeight();
      window.addEventListener("resize", publishHeadHeight);
    }

    var tableScroll = scroller && scroller.querySelector(".activity-table-scroll");
    var wholeRows = function () {
      if (!tableScroll) return;
      if (!window.matchMedia("(min-width: 992px)").matches) {
        tableScroll.style.maxHeight = "";
        return;
      }
      var head = tableScroll.querySelector("thead");
      var rows = tableScroll.querySelectorAll("tbody tr");
      if (!head || !rows.length) return;
      tableScroll.style.maxHeight = "";
      var headH = head.getBoundingClientRect().height;
      var top = rows[0].getBoundingClientRect().top;
      var room = tableScroll.clientHeight - headH + 0.5;
      var count = 0;
      for (var i = 0; i < rows.length; i++) {
        if (rows[i].getBoundingClientRect().bottom - top > room) break;
        count = i + 1;
      }
      if (
        tableScroll.closest(".class-activity-overview") &&
        !document.body.classList.contains("is-activity-expanded")
      ) {
        count = Math.min(count, 3);
      }
      count = Math.min(Math.max(count, 1), rows.length);
      if (count === rows.length) return;
      var bodyH = rows[count - 1].getBoundingClientRect().bottom - top;
      tableScroll.style.maxHeight = (headH + bodyH).toFixed(2) + "px";
    };
    wholeRows();
    window.addEventListener("resize", wholeRows);

    var btn = document.querySelector("[data-activity-expand]");
    var cards = document.getElementById("overviewCards");
    if (!btn || !cards) return;

    // Enlarging the activity panel used to drop the stat cards with
    // display:none, so the table jumped up the page. Route it through the
    // same collapsing wrapper the disclosure panels use, starting open.
    var cardsWrap = document.createElement("div");
    cardsWrap.className = "collapse-fx activity-cards-fx is-open";
    var cardsTrack = document.createElement("div");
    cardsTrack.className = "collapse-fx-track";
    cards.parentNode.insertBefore(cardsWrap, cards);
    cardsWrap.appendChild(cardsTrack);
    cardsTrack.appendChild(cards);

    btn.addEventListener("click", function () {
      var expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
      cards.classList.toggle("is-collapsed", !expanded);
      cardsWrap.classList.toggle("is-open", expanded);
      document.body.classList.toggle("is-activity-expanded", !expanded);
      var label = expanded ? "Expand" : "Collapse";
      btn.setAttribute("title", label);
      btn.setAttribute("aria-label", label + " recent activity");
      wholeRows();
    });

    // The table's whole-row clamp is measured from available height, which
    // is only final once the cards have finished collapsing.
    cardsWrap.addEventListener("transitionend", function (e) {
      if (e.target === cardsWrap && e.propertyName === "grid-template-rows") wholeRows();
    });
  })();

  document.querySelectorAll("table[data-column-filters]").forEach(function (table) {
    var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr")).filter(function (row) {
      return row.cells.length > 1;
    });
    var menus = Array.prototype.slice.call(table.querySelectorAll(".th-filter"));
    if (!rows.length || !menus.length) return;

    // col -> { value, test(row) }
    var selected = {};

    function cellText(row, col) {
      var cell = row.cells[col];
      return cell ? cell.textContent.trim() : "";
    }

    function rowDate(row, col) {
      var cell = row.cells[col];
      var raw = cell && cell.getAttribute("data-when");
      if (!raw) return null;
      var d = new Date(raw);
      return isNaN(d.getTime()) ? null : d;
    }

    function startOfDay(d) { var x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
    function startOfWeek(d) {
      var x = startOfDay(d);
      x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); // weeks run Monday to Sunday
      return x;
    }
    function startOfMonth(d) { var x = startOfDay(d); x.setDate(1); return x; }

    function applyFilters() {
      rows.forEach(function (row) {
        var visible = Object.keys(selected).every(function (col) {
          return selected[col].test(row);
        });
        row.hidden = !visible;
      });
      menus.forEach(function (menu) {
        var col = menu.getAttribute("data-filter-col");
        menu.classList.toggle("has-active-filter", col in selected);
        menu.querySelectorAll("button").forEach(function (btn) {
          btn.classList.toggle("active", btn.dataset.value === (selected[col] ? selected[col].value : ""));
        });
      });
    }

    function addOption(menu, panel, col, value, label, test) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.value = value;
      btn.textContent = label;
      btn.addEventListener("click", function () {
        if (value) selected[col] = { value: value, test: test };
        else delete selected[col];
        menu.removeAttribute("open");
        applyFilters();
      });
      panel.appendChild(btn);
    }

    menus.forEach(function (menu) {
      var col = menu.getAttribute("data-filter-col");
      var panel = menu.querySelector(".activity-filter-panel");
      if (!panel) return;

      addOption(menu, panel, col, "", "All", function () { return true; });

      // A date column filters by period. Listing every distinct "2 days, 6
      // hours ago" is not a filter anyone can use -- the labels are unique per
      // row, so each one matches exactly one attempt.
      if (menu.getAttribute("data-filter-mode") === "date") {
        var now = new Date();
        var periods = [
          { value: "today", label: "Today", from: startOfDay(now) },
          { value: "week", label: "This week", from: startOfWeek(now) },
          { value: "month", label: "This month", from: startOfMonth(now) }
        ];
        var previousCount = -1;
        periods.forEach(function (period) {
          var test = function (row) {
            var d = rowDate(row, col);
            return !!d && d >= period.from;
          };
          var count = rows.filter(test).length;
          // Skip a period nothing falls into, and skip one that would select
          // exactly what the period above it already selects.
          if (!count || count === previousCount) return;
          previousCount = count;
          addOption(menu, panel, col, period.value, period.label, test);
        });
        return;
      }

      var values = [];
      rows.forEach(function (row) {
        var text = cellText(row, col);
        if (text && values.indexOf(text) === -1) values.push(text);
      });
      values.sort();

      values.forEach(function (value) {
        addOption(menu, panel, col, value, value, function (row) {
          return cellText(row, col) === value;
        });
      });
    });

    applyFilters();
  });

  document.addEventListener("click", function (e) {
    document.querySelectorAll(".th-filter[open]").forEach(function (menu) {
      if (!menu.contains(e.target)) menu.removeAttribute("open");
    });
  });

  // A filter panel is absolutely positioned inside a table that sits in three
  // nested clipping boxes (the scroll region, the flush card, and the column
  // wrapper), so anything taller than the remaining card was being cut off.
  // Fixed positioning escapes all three; the coordinates come from the summary
  // it belongs to and are refreshed whenever anything moves under it.
  function placeFilterPanel(menu) {
    var panel = menu.querySelector(".activity-filter-panel");
    var summary = menu.querySelector("summary");
    if (!panel || !summary) return;
    var r = summary.getBoundingClientRect();
    var margin = 8;
    panel.style.top = r.bottom + margin + "px";
    panel.style.left = r.left + "px";
    panel.style.maxHeight = Math.max(120, window.innerHeight - r.bottom - margin * 3) + "px";
    var pr = panel.getBoundingClientRect();
    if (pr.right > window.innerWidth - margin) {
      panel.style.left = Math.max(margin, window.innerWidth - pr.width - margin) + "px";
    }
  }

  function placeOpenFilterPanels() {
    document.querySelectorAll(".activity-filter-menu[open]").forEach(placeFilterPanel);
  }

  document.querySelectorAll(".activity-filter-menu").forEach(function (menu) {
    menu.addEventListener("toggle", function () {
      if (menu.open) placeFilterPanel(menu);
    });
  });
  window.addEventListener("resize", placeOpenFilterPanels);
  // Capture phase so scrolling of the inner table region counts too.
  document.addEventListener("scroll", placeOpenFilterPanels, true);

  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      navigator.clipboard.writeText(text).then(function () {
        var original = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(function () { btn.textContent = original; }, 1500);
      });
    });
  });

  (function () {
    var tooltipEls = document.querySelectorAll("[data-tooltip]");
    if (!tooltipEls.length) return;

    var tip = document.createElement("div");
    tip.className = "mp-tooltip";
    document.body.appendChild(tip);

    function showAt(x, y, text) {
      tip.textContent = text;
      tip.style.left = x + "px";
      tip.style.top = y + "px";
      tip.classList.add("is-visible");
    }
    function hide() {
      tip.classList.remove("is-visible");
    }

    tooltipEls.forEach(function (el) {
      var text = el.getAttribute("data-tooltip");
      el.addEventListener("mouseenter", function (e) { showAt(e.clientX, e.clientY, text); });
      el.addEventListener("mousemove", function (e) { showAt(e.clientX, e.clientY, text); });
      el.addEventListener("mouseleave", hide);
      el.addEventListener("focus", function () {
        var r = el.getBoundingClientRect();
        showAt(r.left + r.width / 2, r.top, text);
      });
      el.addEventListener("blur", hide);
    });
  })();

  document.querySelectorAll(".spark-card-body").forEach(function (body) {
    var svg = body.querySelector(".spark-svg");
    var labels = body.querySelectorAll(".spark-labels span");
    var dots = body.querySelectorAll(".spark-dot");
    var line = body.querySelector(".spark-line");
    if (!svg || !labels.length || labels.length !== dots.length) return;

    function align() {
      var svgRect = svg.getBoundingClientRect();
      var viewBoxWidth = svg.viewBox.baseVal.width;
      if (!svgRect.width || !viewBoxWidth) return;
      labels.forEach(function (label, i) {
        var labelRect = label.getBoundingClientRect();
        var centerFraction = (labelRect.left + labelRect.width / 2 - svgRect.left) / svgRect.width;
        dots[i].setAttribute("cx", (centerFraction * viewBoxWidth).toFixed(1));
      });
      if (line) {
        var points = [];
        dots.forEach(function (dot) { points.push(dot.getAttribute("cx") + "," + dot.getAttribute("cy")); });
        line.setAttribute("points", points.join(" "));
      }
    }

    align();
    window.addEventListener("resize", align);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(align);
  });

  (function () {
    var bars = document.querySelectorAll('.sd-skill-bar > span[data-pct]');
    if (!bars.length) return;

    bars.forEach(function (bar) {
      var pct = bar.getAttribute('data-pct');
      if (!pct) return;

      var label = document.createElement('strong');
      label.className = 'sd-skill-level';
      label.textContent = pct + '%';
      bar.appendChild(label);

      var finalWidth = bar.style.width || (pct + '%');
      try { bar.style.width = '0%'; } catch (e) {}
      void bar.offsetWidth;
      bar.style.width = finalWidth;

      var onEnd = function (e) {
        if (e.propertyName !== 'width') return;
        label.classList.add('is-visible');
        bar.removeEventListener('transitionend', onEnd);
      };
      bar.addEventListener('transitionend', onEnd);

      setTimeout(function () {
        if (!label.classList.contains('is-visible')) label.classList.add('is-visible');
      }, 1100);
    });
  })();

})();
