"""TradingView's axis gestures, added to the plotly charts in the browser.

Dragging the price scale to stretch the candles vertically, and the time scale
to squeeze them horizontally, is half of how a TradingView chart is read.
Plotly has no equivalent and no figure attribute that would turn one on:

- its own axis bands *pan* across the middle 80% and only scale from the outer
  10%, so the gesture a TradingView user makes does the wrong thing;
- those bands are 20px wide (`DRAGGERSIZE`, a plotly constant), while the
  price scale they sit in is as wide as its tick labels — about sixty. Two
  thirds of the visible scale is not grabbable at all.

So the gesture has to be added on the page. Three things keep that from being
as fragile as injected JavaScript usually is:

- **It never computes a range.** It hit-tests the pointer against the panes
  plotly already drew, then hands the work straight back to plotly by
  dispatching a `wheel` event at the axis band it wants scaled — the same
  event a scroll over that band would produce. Plotly does the arithmetic, the
  redraw and the `plotly_relayout`. The anchor is the wheel's own position,
  which is how the newest bar can be pinned in place the way TradingView pins
  it, and why none of plotly's zoom maths is restated here.
- **It names three plotly classes and nothing else:** `nsewdrag` (a pane's
  body), `ewdrag` and `nsdrag` (its time and price bands). Those have been the
  same across plotly 1.x and 2.x.
- **It fails closed.** No parent document, no chart under the pointer, no band
  to dispatch into: it returns, and the chart behaves exactly as before.

`st.markdown` strips `<script>`, so this goes through `components.html`, whose
iframe Streamlit grants `allow-same-origin allow-scripts` — same origin as the
page holding the charts, so `window.parent` is reachable. The iframe hides
itself once it has run, and the listeners install once per session however
many times Streamlit reruns the script.
"""

from __future__ import annotations

import streamlit.components.v1 as components

# Feel of the gesture. Plotly clamps one wheel notch to 20 and scales the
# range by exp(-notch / 200), so 1.5 notches per pixel puts a 200px drag at
# e^-1.5 — a little over four times in or out, which is about TradingView's.
NOTCHES_PER_PIXEL = 1.5

_SCRIPT = """
<script>
(function () {
  "use strict";

  var win, doc;
  try {
    win = window.parent;
    doc = win.document;
  } catch (err) {
    return;                       // not same-origin: leave the page alone
  }
  if (!doc) return;

  // Streamlit renders this component again on every rerun, so each new iframe
  // has to take itself out of the layout. The listeners below are delegated
  // on the document and only ever want installing once.
  try {
    var frame = window.frameElement;
    if (frame) {
      // Hiding the block Streamlit wrapped the iframe in takes the row gap
      // with it; the iframe alone would leave a stripe of dead space above
      // the toolbar. Display:none does not unload a frame that has already run.
      var host = frame.closest(".stElementContainer, .element-container") || frame;
      host.style.display = "none";
    }
  } catch (err) {}

  if (win.__tvAxisDrag) return;
  win.__tvAxisDrag = true;

  var NOTCHES_PER_PIXEL = %(notches)s;
  var NOTCH_LIMIT = 20;            // plotly clamps a single wheel notch here
  var CLICK_SLOP = 3;              // a press that moves less than this is a click
  var CACHE_MS = 200;              // how long measured pane boxes stay good for

  var live = null;
  var cache = {gd: null, at: 0, panes: null};

  // The chart under a pointer, unless the pointer is on the modebar — which
  // floats over the top of the price scale, and whose buttons would otherwise
  // be swallowed by a gesture aimed at the axis behind them.
  function chartOf(node) {
    if (!node || !node.closest) return null;
    return node.closest(".modebar") ? null : node.closest(".js-plotly-plot");
  }

  function panes(gd) {
    var now = Date.now();
    if (cache.gd === gd && now - cache.at < CACHE_MS) return cache.panes;
    var bodies = gd.querySelectorAll(".nsewdrag");
    var out = [];
    for (var i = 0; i < bodies.length; i++) {
      out.push({group: bodies[i].parentNode,
                box: bodies[i].getBoundingClientRect()});
    }
    cache = {gd: gd, at: now, panes: out};
    return out;
  }

  // Which scale, if any, the pointer is over. The test is against the pane's
  // own box rather than against plotly's 20px band, because TradingView lets
  // you grab anywhere in a scale and the tick labels are most of one. Inside
  // a pane belongs to plotly: that is where dragging pans the chart.
  function scaleUnder(gd, x, y) {
    var found = panes(gd), i, box, band, best = null;
    for (i = 0; i < found.length; i++) {
      box = found[i].box;
      if (x >= box.left && x <= box.right && y >= box.top && y <= box.bottom) {
        return null;
      }
    }
    for (i = 0; i < found.length; i++) {
      box = found[i].box;
      if (x > box.right && y >= box.top && y <= box.bottom) {
        band = found[i].group.querySelector(".nsdrag");
        if (band) return {axis: "y", band: band, box: box};
      }
      // The time scale belongs to the lowest pane the pointer is under: with
      // a volume strip below the candles, that is the strip, not the candles.
      if (y > box.bottom && x >= box.left && x <= box.right) {
        band = found[i].group.querySelector(".ewdrag");
        if (band && (!best || box.bottom > best.box.bottom)) {
          best = {axis: "x", band: band, box: box};
        }
      }
    }
    return best;
  }

  function scaleBy(hit, pixels) {
    // Plotly reads a wheel's anchor off the pane box it was dispatched into.
    // Pinning the time scale to the right edge holds the newest bar still
    // while the history stretches past it; the price scale pins to the middle.
    var box = hit.box;
    var options = {
      clientX: hit.axis === "x" ? box.right : (box.left + box.right) / 2,
      clientY: (box.top + box.bottom) / 2,
      deltaMode: 0, bubbles: false, cancelable: true
    };
    var total = -pixels * NOTCHES_PER_PIXEL;
    var steps = Math.min(24, Math.ceil(Math.abs(total) / NOTCH_LIMIT));
    for (var i = 0; i < steps; i++) {
      options.deltaY = total / steps;
      hit.band.dispatchEvent(new win.WheelEvent("wheel", options));
    }
  }

  function onDown(event) {
    if (live || !event.isTrusted || event.button !== 0) return;
    var gd = chartOf(event.target);
    if (!gd) return;
    cache.gd = null;                       // measure the panes where they are now
    var hit = scaleUnder(gd, event.clientX, event.clientY);
    if (!hit) return;
    live = {hit: hit, x: event.clientX, y: event.clientY,
            fromX: event.clientX, fromY: event.clientY};
    event.preventDefault();
    event.stopPropagation();               // plotly's own axis pan never starts
  }

  function onMove(event) {
    if (!live) {
      var gd = chartOf(event.target);
      if (gd) {
        var over = scaleUnder(gd, event.clientX, event.clientY);
        gd.style.cursor = over ? (over.axis === "x" ? "ew-resize" : "ns-resize") : "";
      }
      return;
    }
    // Right and up read as "stretch", so the drag agrees with the wheel:
    // scrolling up over a scale already zooms into it.
    var pixels = live.hit.axis === "x" ? event.clientX - live.x
                                       : live.y - event.clientY;
    live.x = event.clientX;
    live.y = event.clientY;
    if (pixels) scaleBy(live.hit, pixels);
    event.preventDefault();
    event.stopPropagation();
  }

  function onUp(event) {
    if (!live) return;
    var hit = live.hit;
    var still = Math.abs(event.clientX - live.fromX)
              + Math.abs(event.clientY - live.fromY) <= CLICK_SLOP;
    live = null;
    event.stopPropagation();
    // A press that went nowhere was a click, and two of those are plotly's
    // "reset this axis". Hand the gesture back rather than swallowing it.
    if (still) {
      var options = {bubbles: true, cancelable: true, view: win, button: 0,
                     clientX: event.clientX, clientY: event.clientY};
      hit.band.dispatchEvent(new win.MouseEvent("mousedown", options));
      hit.band.dispatchEvent(new win.MouseEvent("mouseup", options));
    }
  }

  doc.addEventListener("mousedown", onDown, true);
  doc.addEventListener("mousemove", onMove, true);
  doc.addEventListener("mouseup", onUp, true);
  win.addEventListener("blur", function () { live = null; });
})();
</script>
""" % {"notches": NOTCHES_PER_PIXEL}


def script() -> str:
    """The installed markup, so a test can read it without a browser."""
    return _SCRIPT


def enable() -> None:
    """Wire the axis gestures onto every plotly chart on the page.

    Call once, next to `theme.inject()`. Zero height: the component only
    exists to run its script, and hides its own iframe as soon as it has.
    """
    components.html(_SCRIPT, height=0)
