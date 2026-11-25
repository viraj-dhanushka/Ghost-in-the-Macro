// "Start over": after DELETE /session succeeds, reload to a fresh landing page.
document.addEventListener("htmx:afterRequest", function (evt) {
  var el = evt.detail && evt.detail.elt;
  if (el && el.id === "start-over" && evt.detail.successful) {
    window.location.assign("/");
  }
});
