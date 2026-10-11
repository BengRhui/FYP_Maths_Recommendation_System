(function () {
  "use strict";

  /* The one place that turns what a student types into LaTeX.
   *
   * It has to agree with two things it cannot see: curriculum/answer_math.py,
   * which decides whether the answer is right, and the results pages, which
   * show the answer back afterwards. When the preview under the input box had
   * its own copy of this, the three drifted — "6^ab" previewed as $$6^{ab}$$
   * while the grader read it as $$(6^a)b$$ and the results page printed it
   * that way too, so a student watched their answer change meaning between
   * typing it and reading it back. Both callers now go through here. */

  var FUNCS = [
    { name: "sqrt", latex: "\\sqrt", wrap: "{}" },
    { name: "ln", latex: "\\ln", wrap: "()" },
    { name: "sin", latex: "\\sin", wrap: "()" },
    { name: "cos", latex: "\\cos", wrap: "()" },
    { name: "tan", latex: "\\tan", wrap: "()" }
  ];

  // How far a bare exponent reaches. This mirrors answer_math's tokeniser,
  // which reads a run of digits as one number but each letter as its own
  // variable: "x^12" is the twelfth power, while "6^ab" is 6 to the a, times
  // b. Anything wider belongs in brackets — "6^(ab)" — and is handled above.
  var BARE_EXPONENT = /^-?(?:\d+(?:\.\d+)?|[a-zA-Z])/;

  function findMatchingParen(str, openIdx) {
    var depth = 0;
    for (var i = openIdx; i < str.length; i++) {
      if (str[i] === "(") depth++;
      else if (str[i] === ")") {
        depth--;
        if (depth === 0) return i;
      }
    }
    return -1;
  }

  function convertCore(str) {
    var out = "";
    var i = 0;
    var n = str.length;

    function isWordBoundary(idx) {
      if (idx <= 0) return true;
      return !/[a-zA-Z]/.test(str[idx - 1]);
    }

    while (i < n) {
      if (str.startsWith("log_(", i) && isWordBoundary(i)) {
        var baseOpen = i + 4;
        var baseClose = findMatchingParen(str, baseOpen);
        if (baseClose !== -1 && str[baseClose + 1] === "(") {
          var exprClose = findMatchingParen(str, baseClose + 1);
          if (exprClose !== -1) {
            var base = str.slice(baseOpen + 1, baseClose);
            var expr = str.slice(baseClose + 2, exprClose);
            out += "\\log_{" + convertCore(base) + "}(" + convertCore(expr) + ")";
            i = exprClose + 1;
            continue;
          }
        }
      }
      if (str.startsWith("log(", i) && isWordBoundary(i)) {
        var lOpen = i + 3;
        var lClose = findMatchingParen(str, lOpen);
        if (lClose !== -1) {
          out += "\\log(" + convertCore(str.slice(lOpen + 1, lClose)) + ")";
          i = lClose + 1;
          continue;
        }
      }
      var matchedFunc = null;
      for (var f = 0; f < FUNCS.length; f++) {
        var fn = FUNCS[f];
        if (str.startsWith(fn.name + "(", i) && isWordBoundary(i)) { matchedFunc = fn; break; }
      }
      if (matchedFunc) {
        var fOpen = i + matchedFunc.name.length;
        var fClose = findMatchingParen(str, fOpen);
        if (fClose !== -1) {
          var inner = convertCore(str.slice(fOpen + 1, fClose));
          out += matchedFunc.wrap === "{}" ? matchedFunc.latex + "{" + inner + "}" : matchedFunc.latex + "(" + inner + ")";
          i = fClose + 1;
          continue;
        }
      }
      if (str.startsWith("pi", i) && isWordBoundary(i) && (i + 2 >= n || !/[a-zA-Z]/.test(str[i + 2]))) {
        out += "\\pi ";
        i += 2;
        continue;
      }
      if (str[i] === "^") {
        if (str[i + 1] === "(") {
          var eClose = findMatchingParen(str, i + 1);
          if (eClose !== -1) {
            out += "^{" + convertCore(str.slice(i + 2, eClose)) + "}";
            i = eClose + 1;
            continue;
          }
        }
        var m = BARE_EXPONENT.exec(str.slice(i + 1));
        if (m) {
          out += "^{" + m[0] + "}";
          i += 1 + m[0].length;
          continue;
        }
      }
      if (str.startsWith("<=", i)) { out += "\\leq "; i += 2; continue; }
      if (str.startsWith(">=", i)) { out += "\\geq "; i += 2; continue; }
      if (str.startsWith("!=", i)) { out += "\\neq "; i += 2; continue; }
      if (str[i] === "*") { out += "\\times "; i += 1; continue; }

      out += str[i];
      i += 1;
    }
    return out;
  }

  // Index of the bracket that opens the group closing at closeIdx, or -1.
  function findMatchingOpen(str, closeIdx) {
    var close = str[closeIdx];
    var open = close === ")" ? "(" : "{";
    var depth = 0;
    for (var i = closeIdx; i >= 0; i--) {
      if (str[i] === close) depth++;
      else if (str[i] === open) {
        depth--;
        if (depth === 0) return i;
      }
    }
    return -1;
  }

  // "(a+b)" -> "a+b" when one bracket pair wraps the whole thing.
  function unwrap(str) {
    return str[0] === "(" && findMatchingParen(str, 0) === str.length - 1 ? str.slice(1, -1) : str;
  }

  // Where the numerator of a "/" at the end of `out` starts. Multiplication and
  // division share a precedence and run left to right, so everything multiplied
  // together before the slash is on top: "Tq/p" is (Tq)/p, "a(R-1)/(R+1)" is
  // a(R-1) over R+1. The run stops at +, -, =, a comma, an unmatched bracket
  // or a space, so "2 + x/3" only puts x on top.
  function numeratorStart(out) {
    var i = out.length;
    while (i > 0) {
      var ch = out[i - 1];
      if (ch === ")" || ch === "}") {
        var open = findMatchingOpen(out, i - 1);
        if (open === -1) break;
        i = open;
      } else if (/[a-zA-Z0-9.\\^_]/.test(ch)) {
        i--;
      } else {
        break;
      }
    }
    return i;
  }

  // The denominator starting at idx: a bracketed group, or one number or letter
  // with its power ("y^{2}"). A bare term followed straight on by another
  // ("p/3b") stays a slash: the grader reads that as (p/3)·b, and drawing b
  // under the bar would show a different answer from the one being marked.
  function readDenominator(str, idx) {
    while (str[idx] === " ") idx++;
    if (str[idx] === "(") {
      var close = findMatchingParen(str, idx);
      return close === -1 ? null : { text: str.slice(idx + 1, close), end: close + 1 };
    }
    var m = /^(?:\d+(?:\.\d+)?|[a-zA-Z])(?:\^\{[^{}]*\})?(?![a-zA-Z0-9(])/.exec(str.slice(idx));
    return m ? { text: m[0], end: idx + m[0].length } : null;
  }

  function convertFractions(str) {
    var out = "";
    var i = 0;
    while (i < str.length) {
      if (str[i] === "/") {
        var trimmed = out.replace(/ +$/, "");
        var start = numeratorStart(trimmed);
        var den = start < trimmed.length ? readDenominator(str, i + 1) : null;
        if (den) {
          var num = trimmed.slice(start);
          // A fraction just built is itself a term, so "a/b/c" nests.
          out = trimmed.slice(0, start) + "\\frac{" + unwrap(num) + "}{" + convertFractions(den.text) + "}";
          i = den.end;
          continue;
        }
      }
      out += str[i];
      i += 1;
    }
    return out;
  }

  // Symbols a student can reach from the palette or their own keyboard. The
  // unicode minus is normalised first, so the exponent rule above sees a plain
  // "-"; the rest are operators that convertCore passes straight through.
  function toLatex(raw) {
    var text = (raw || "").replace(/\u2212/g, "-");
    text = convertFractions(convertCore(text));
    return text
      .replace(/\u00D7/g, "\\times ")
      .replace(/\u00F7/g, "\\div ")
      .replace(/\u2264/g, "\\leq ")
      .replace(/\u2265/g, "\\geq ");
  }

  window.mathNotation = { toLatex: toLatex };
})();
