// htmx 1.9 does not swap 4xx responses by default, so messages such as
// "already has a verification running" (429) would never reach the user.
// Swap the HTML body of these expected, user-facing errors into the target.
document.addEventListener("htmx:beforeSwap", function (evt) {
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

document.addEventListener("htmx:beforeRequest", function (evt) {
  var b = ghostBusyButton(evt.detail.elt);
  if (!b || b.getAttribute("aria-busy") === "true") return;
  b.setAttribute("aria-busy", "true");
  b.setAttribute("aria-disabled", "true");
  b.disabled = true;
  b.setAttribute("data-idle-label", b.textContent);
  b.textContent = b.getAttribute("data-busy-label") || (b.textContent.trim() + " (working…)");
});

document.addEventListener("htmx:afterRequest", function (evt) {
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

// Focus: after a user-initiated swap into #result, move focus to the first
// heading of the new content, else to #result (tabindex="-1"). The job panel
// polls every second; a poll swap moves focus only once, when the panel stops
// polling (job done, failed or timed out).
var ghostJobWasPolling = false;

document.addEventListener("htmx:afterSwap", function (evt) {
  var result = document.querySelector("#result");
  if (!result) return;
  var path = (evt.detail.pathInfo && evt.detail.pathInfo.requestPath) || "";
  var isPoll = /\/run\/[^/]+\/panel/.test(path);
  var job = result.querySelector(".job");
  var polling = !!(job && job.hasAttribute("hx-get"));
  if (isPoll) {
    var finished = ghostJobWasPolling && !polling;
    ghostJobWasPolling = polling;
    if (!finished) return;
  } else {
    var t = evt.detail.target;
    if (!t || !(t === result || result.contains(t))) return;
    ghostJobWasPolling = polling;
  }
  var h = result.querySelector("h1,h2,h3");
  if (h) {
    if (!h.hasAttribute("tabindex")) h.setAttribute("tabindex", "-1");
    h.focus();
  } else {
    result.focus();
  }
});
