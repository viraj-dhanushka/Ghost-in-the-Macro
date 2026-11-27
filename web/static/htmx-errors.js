// htmx 1.9 does not swap 4xx responses by default, so messages such as
// "already has a verification running" (429) would never reach the user.
// Swap the HTML body of these expected, user-facing errors into the target.
if (typeof document !== "undefined") document.addEventListener("htmx:beforeSwap", function (evt) {
  var s = evt.detail.xhr.status;
  if (s === 404 || s === 409 || s === 413 || s === 422 || s === 429 || s === 503) {
    evt.detail.shouldSwap = true;
    evt.detail.isError = false;
  }
});

// Busy state: the triggering button is disabled and relabelled (text cue, not
// colour only) while its request is in flight. Polls (elt is the job panel)
// have no button and are skipped.
function ghostBusyButton(elt) {
  if (!elt) return null;
  if (elt.tagName === "BUTTON") return elt;
  if (elt.tagName === "FORM") return elt.querySelector("button[type=submit], button:not([type])");
  return null;
}

if (typeof document !== "undefined") document.addEventListener("htmx:beforeRequest", function (evt) {
  var b = ghostBusyButton(evt.detail.elt);
  if (!b || b.getAttribute("aria-busy") === "true") return;
  b.setAttribute("aria-busy", "true");
  b.setAttribute("aria-disabled", "true");
  b.disabled = true;
  b.setAttribute("data-idle-label", b.textContent);
  b.textContent = b.getAttribute("data-busy-label") || (b.textContent.trim() + " (working…)");
});

if (typeof document !== "undefined") document.addEventListener("htmx:afterRequest", function (evt) {
  var b = ghostBusyButton(evt.detail.elt);
  if (!b || b.getAttribute("aria-busy") !== "true") return;
  b.removeAttribute("aria-busy");
  b.removeAttribute("aria-disabled");
  b.disabled = false;
  if (b.hasAttribute("data-idle-label")) {
    b.textContent = b.getAttribute("data-idle-label");
    b.removeAttribute("data-idle-label");
  }
});

// Focus: after a user-initiated swap into #result, move focus AND the view to the heading of the content that was
// swapped, not to the first heading on the page (that was always "Loaded ...", which scrolled the page back to the top
// when a run started and again when it ended):
//   POST /verify (a run starts)   -> the job panel heading (or the failure card's title when the run was refused)
//   the poll that ends a run      -> the verdict heading, else the job panel heading
//   a poll that is still running  -> nothing
//   POST /upload, POST /sample/x  -> the "Loaded ..." heading
//   POST /decision                -> nothing (the autopsy section is replaced in place; the page stays where it is)
//   GET /autopsy (a load trigger, not an action of the user) -> nothing
//   anything else                 -> the first heading in #result, else #result (the old rule)
// The decision is a pure function so that it can be tested without a browser.
function ghostFocusSelectors(path, finished) {
  if (/\/run\/[^/]+\/panel/.test(path)) return finished ? [".job .vc-headline", ".job h2"] : null;
  if (path === "/verify") return ["#job .job h2", ".job h2", "#job .failure-title", "#job [role=alert]"];
  if (path === "/upload" || /^\/sample\/[^/]+$/.test(path)) return ["#loaded-h"];
  if (path === "/decision") return null;
  if (path === "/autopsy") return null;
  return ["h1,h2,h3"];
}

// Earlier step rails stay on the page when a later one is swapped in. Only the newest may say "current step": earlier
// rails show that step as done (a text cue, not colour only), without the marker or aria-current.
function ghostSupersedeRails(doc) {
  var rails = doc.querySelectorAll(".stepper");
  for (var i = 0; i < rails.length - 1; i++) {
    var current = rails[i].querySelectorAll("li.current");
    for (var j = 0; j < current.length; j++) {
      var li = current[j];
      li.classList.remove("current");
      li.classList.add("done");
      li.removeAttribute("aria-current");
      var cue = li.querySelector(".step-cue");
      if (cue) cue.remove();
    }
  }
}

// The job panel polls every second; a poll swap moves focus only once, when the panel stops polling (job done, failed
// or timed out).
// While the panel polls, the heading that was focused is replaced every second and focus would fall back to the page.
// If (and only if) focus is lost like that, it is put back on the same heading without scrolling; focus that the user
// has moved elsewhere is never touched.
var ghostFocusState = { jobWasPolling: false, headingId: null };
function ghostAfterSwap(evt, doc, state) {
  var result = doc.querySelector("#result");
  if (!result) return;
  var path = (evt.detail.pathInfo && evt.detail.pathInfo.requestPath) || "";
  var isPoll = /\/run\/[^/]+\/panel/.test(path);
  var job = result.querySelector(".job");
  var polling = !!(job && job.hasAttribute("hx-get"));
  var finished = false;
  if (isPoll) {
    finished = state.jobWasPolling && !polling;
    state.jobWasPolling = polling;
    if (!finished) {
      var active = doc.activeElement;
      if (state.headingId && (!active || active.tagName === "BODY")) {
        var again = doc.getElementById(state.headingId);
        if (again) {
          if (!again.hasAttribute("tabindex")) again.setAttribute("tabindex", "-1");  // the new node has no tabindex yet
          again.focus({ preventScroll: true });
        }
      }
      return;
    }
  } else {
    var t = evt.detail.target;
    if (!t || !(t === result || result.contains(t))) return;
    state.jobWasPolling = polling;
  }
  var selectors = ghostFocusSelectors(path, finished);
  if (selectors === null) return;
  for (var i = 0; i < selectors.length; i++) {
    var h = result.querySelector(selectors[i]);
    if (h) {
      if (!h.hasAttribute("tabindex")) h.setAttribute("tabindex", "-1");
      h.focus({ preventScroll: true });
      h.scrollIntoView({ block: "start" });
      state.headingId = polling && h.id ? h.id : null;  // only a heading inside a panel that is still polling is replaced
      return;
    }
  }
  result.focus();
}

if (typeof document !== "undefined") {
  document.addEventListener("htmx:afterSwap", function (evt) {
    ghostSupersedeRails(document);
    ghostAfterSwap(evt, document, ghostFocusState);
  });
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { ghostFocusSelectors: ghostFocusSelectors, ghostSupersedeRails: ghostSupersedeRails, ghostAfterSwap: ghostAfterSwap };
}
