// Remembers the decision author's name in this browser only (localStorage). It never reads or fills
// any other field and sends nothing anywhere; storage errors (private mode, blocked) are ignored.
(function () {
  var KEY = "ghost-author";
  function read() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* not available */ } }
  function fill(root) {
    var fields = (root && root.querySelectorAll ? root : document).querySelectorAll("input[name=author]");
    for (var i = 0; i < fields.length; i++) {
      if (!fields[i].value) {
        var saved = read();
        if (saved) fields[i].value = saved;
      }
    }
  }
  document.addEventListener("input", function (ev) {
    var t = ev.target;
    if (t && t.matches && t.matches("input[name=author]")) write(t.value);
  });
  document.addEventListener("DOMContentLoaded", function () { fill(document); });
  document.addEventListener("htmx:afterSwap", function () { fill(document); });
  document.addEventListener("htmx:load", function (ev) { fill(ev.target); });
})();
