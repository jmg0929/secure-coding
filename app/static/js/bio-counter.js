// 소개글 글자수 카운터. 실제 길이 제한은 서버(WTForms Length)에서 검증한다.
(function () {
  "use strict";
  var el = document.getElementById("bio");
  var out = document.getElementById("c-bio");
  if (!el || !out) return;
  function update() {
    var n = el.value.length;
    out.textContent = n + " / 500";
    out.classList.toggle("over", n > 500);
  }
  el.addEventListener("input", update);
  update();
})();
