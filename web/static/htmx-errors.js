// htmx 1.9 does not swap 4xx responses by default, so messages such as
// "already has a verification running" (429) would never reach the user.
// Swap the HTML body of these expected, user-facing errors into the target.
document.addEventListener("htmx:beforeSwap", function (evt) {
  var s = evt.detail.xhr.status;
  if (s === 409 || s === 422 || s === 429) {
    evt.detail.shouldSwap = true;
    evt.detail.isError = false;
  }
});
