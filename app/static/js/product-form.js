// 상품 등록/수정 폼 보조 기능: 이미지 미리보기, 글자수 카운터, 드래그&드롭.
// 미리보기는 브라우저 안에서만 처리되며, 실제 파일 검증(확장자·용량)은
// 서버(save_uploaded_image)에서 다시 수행한다. 클라이언트 검증은 편의 기능일 뿐이다.
(function () {
  "use strict";

  var ALLOWED = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  var MAX_BYTES = 5 * 1024 * 1024;

  // ---------- 글자수 카운터 ----------
  function bindCounter(fieldId, counterId, max) {
    var el = document.getElementById(fieldId);
    var out = document.getElementById(counterId);
    if (!el || !out) return;
    function update() {
      var n = el.value.length;
      out.textContent = n + " / " + max;
      out.classList.toggle("over", n > max);
    }
    el.addEventListener("input", update);
    update();
  }
  bindCounter("title", "c-title", 100);
  bindCounter("description", "c-desc", 2000);

  // ---------- 이미지 미리보기 ----------
  var input = document.getElementById("image");
  var zone = document.getElementById("dropzone");
  var box = document.getElementById("dz-preview");
  var img = document.getElementById("dz-img");
  if (!input || !zone || !box || !img) return;

  function showPreview(file) {
    if (!file) return;
    if (ALLOWED.indexOf(file.type) === -1) {
      alert("PNG, JPG, GIF, WEBP 형식만 올릴 수 있어요.");
      input.value = "";
      return;
    }
    if (file.size > MAX_BYTES) {
      alert("이미지 용량은 5MB 이하여야 해요.");
      input.value = "";
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      img.src = e.target.result;   // data URI (CSP img-src 'self' data: 허용)
      box.classList.add("on");
    };
    reader.readAsDataURL(file);
  }

  input.addEventListener("change", function () {
    showPreview(input.files && input.files[0]);
  });

  // ---------- 드래그 & 드롭 ----------
  ["dragenter", "dragover"].forEach(function (ev) {
    zone.addEventListener(ev, function (e) {
      e.preventDefault();
      zone.classList.add("hover");
    });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    zone.addEventListener(ev, function (e) {
      e.preventDefault();
      zone.classList.remove("hover");
    });
  });
  zone.addEventListener("drop", function (e) {
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) {
      input.files = files;
      showPreview(files[0]);
    }
  });
})();
