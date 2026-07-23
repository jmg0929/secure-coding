// 거래 상세: 계좌번호 복사.
// 계좌번호는 data 속성에서만 읽고 DOM 조작은 textContent 로만 한다.
(function () {
  "use strict";

  var btn = document.getElementById("copy-acct");
  var box = document.getElementById("acct");
  if (!btn || !box) return;

  btn.addEventListener("click", function () {
    var account = box.dataset.account || "";
    var done = function () {
      btn.textContent = "복사됨 ✓";
      setTimeout(function () { btn.textContent = "계좌번호 복사"; }, 1500);
    };

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(account).then(done).catch(fallback);
    } else {
      fallback();
    }

    // http://localhost 등 클립보드 API 를 못 쓰는 환경 대비
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = account;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); done(); } catch (e) { /* 무시 */ }
      document.body.removeChild(ta);
    }
  });
})();
