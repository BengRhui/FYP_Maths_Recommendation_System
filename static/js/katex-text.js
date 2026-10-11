(function () {
  "use strict";

  var DELIM = /\$\$(.+?)\$\$/g;

  // Authors write exponents two ways: as LaTeX inside $$..$$, and as bare
  // Unicode superscripts in otherwise plain prose ("4pq² × 3p²q"). The second
  // kind used to fall straight through to the page as literal text while the
  // rest of the same card was typeset, so a step could read in two different
  // notations at once. SUPERSCRIPTS is what lets the plain-text pass find and
  // convert them.
  var SUPERSCRIPTS = {
    "\u2070": "0", "\u00B9": "1", "\u00B2": "2", "\u00B3": "3", "\u2074": "4",
    "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
    "\u207B": "-"
  };
  var SUP_CLASS = "\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079\u207B";
  var SUP_RUN = new RegExp("[" + SUP_CLASS + "]+", "g");
  var HAS_SUP = new RegExp("[" + SUP_CLASS + "]");
  // One term, then any number of "operator + term" continuations. Terms stop at
  // punctuation, so a sentence's full stop is never swallowed into the math.
  var TERM = "[0-9A-Za-z(][0-9A-Za-z()" + SUP_CLASS + "]*";
  var MATH_RUN = new RegExp(TERM + "(?:\\s*[+\\-\u2212\u00D7\u00F7*/^=<>\u2264\u2265]\\s*" + TERM + ")*", "g");

  var OPERATOR_ONLY = /^[+\-−*×÷/^=<>≤≥().]+$/;
  var MATH_CHARSET = new RegExp("^[0-9a-zA-Z+\\-\u2212*/^=<>\u2264\u2265().\u00D7\u00F7\u03C0" + SUP_CLASS + "\\s]+$");
  var HAS_MATH_CHAR = /[0-9+\-−*/^=<>≤≥×÷]/;

  function toLatex(str) {
    return str
      .replace(SUP_RUN, function (run) {
        var digits = "";
        for (var i = 0; i < run.length; i++) digits += SUPERSCRIPTS[run.charAt(i)];
        return "^{" + digits + "}";
      })
      .replace(/×/g, "\\times ")
      .replace(/÷/g, "\\div ")
      .replace(/≤/g, "\\leq ")
      .replace(/≥/g, "\\geq ")
      .replace(/−/g, "-");
  }

  function structuralLatex(raw) {
    return window.mathNotation ? window.mathNotation.toLatex(raw) : raw;
  }

  function renderInto(el, latex) {
    try {
      // \displaystyle keeps fractions full-size while the math stays inline
      // with the surrounding text; plain inline mode shrinks them to script size.
      window.katex.render("\\displaystyle " + latex, el, { throwOnError: false, displayMode: false });
    } catch (e) {
    }
  }


  function renderTextNode(node) {
    var raw = node.nodeValue;
    if (raw.indexOf("$$") === -1 && !HAS_SUP.test(raw)) return;

    var frag = document.createDocumentFragment();
    var lastIndex = 0;
    var match;
    DELIM.lastIndex = 0;
    while ((match = DELIM.exec(raw)) !== null) {
      if (match.index > lastIndex) {
        appendPlain(frag, raw.slice(lastIndex, match.index));
      }
      var span = document.createElement("span");
      span.className = "math-inline";
      renderInto(span, toLatex(match[1].trim()));
      frag.appendChild(span);
      lastIndex = DELIM.lastIndex;
    }
    if (lastIndex < raw.length) appendPlain(frag, raw.slice(lastIndex));

    node.parentNode.replaceChild(frag, node);
  }

  /* Typeset the Unicode-superscript expressions inside an undelimited stretch of
     text and pass everything else through untouched. The superscript is the
     whole test on purpose: it is the one marker that says "this is math" without
     guessing, so ordinary prose that happens to contain an equals sign or a
     digit ("One box = x pencils") is left exactly as written. */
  function appendPlain(frag, text) {
    if (!HAS_SUP.test(text)) {
      frag.appendChild(document.createTextNode(text));
      return;
    }
    var last = 0;
    var m;
    MATH_RUN.lastIndex = 0;
    while ((m = MATH_RUN.exec(text)) !== null) {
      if (m[0] === "") { MATH_RUN.lastIndex++; continue; }
      if (!HAS_SUP.test(m[0])) continue;
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      var span = document.createElement("span");
      span.className = "math-inline";
      renderInto(span, toLatex(m[0]));
      frag.appendChild(span);
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
  }

  function renderTextEl(el) {
    Array.prototype.slice.call(el.childNodes).forEach(function (node) {
      if (node.nodeType === Node.TEXT_NODE) renderTextNode(node);
    });
  }


  function looksLikeMath(str) {
    if (!str || OPERATOR_ONLY.test(str)) return false;
    return MATH_CHARSET.test(str) && HAS_MATH_CHAR.test(str);
  }

  function renderValueEl(el) {
    var raw = el.textContent.trim();
    // Answer fields are authored both as plain algebra ("5p + 5q") and as
    // display-math text ("$$5p + 5q$$"). A value is already isolated in its
    // own element, so remove the delimiters before handing it to KaTeX.
    // The inner test matters: the outer match is greedy, so without it a value
    // holding two expressions ("$$a$$ and $$b$$") would be handed to KaTeX as
    // the single nonsense expression "a$$ and $$b".
    var delimited = raw.match(/^\$\$([\s\S]+)\$\$$/);
    if (delimited && delimited[1].indexOf("$$") === -1) {
      renderInto(el, toLatex(delimited[1].trim()));
      return;
    }
    // A third shape exists that neither branch caught: prose with delimited
    // math inside it ("Terms: $$7x, -4, 3y$$; coefficient of $$x$$: $$7$$.").
    // It is not one expression, and the punctuation keeps it out of
    // looksLikeMath, so it used to reach the page with its $$ still showing.
    // The text pass already knows how to typeset exactly this.
    if (raw.indexOf("$$") !== -1) {
      renderTextEl(el);
      return;
    }
    if (!looksLikeMath(raw)) return;
    // A bare value is a typed answer in the same notation the input box takes,
    // so it is converted the same way — otherwise "6^ab" reads back as
    // something the student did not see while typing it.
    renderInto(el, toLatex(structuralLatex(raw)));
  }

  function renderMathContent(root) {
    if (!window.katex) return;
    (root || document).querySelectorAll("[data-katex-text]").forEach(renderTextEl);
    (root || document).querySelectorAll("[data-katex-value]").forEach(renderValueEl);
  }

  document.addEventListener("DOMContentLoaded", function () { renderMathContent(document); });
  window.renderMathContent = renderMathContent;
})();
