// 1:1 채팅 클라이언트.
// 서버가 메시지를 이미 이스케이프해 보내지만, 클라이언트에서도
// textContent 로만 DOM 에 삽입하여 XSS 를 이중으로 차단한다.
(function () {
  "use strict";

  var box = document.getElementById("dm");
  if (!box) return;

  var peerId = box.dataset.peerId;
  var myId = box.dataset.myId;

  var socket = io({ transports: ["websocket", "polling"] });
  var form = document.getElementById("dm-form");
  var input = document.getElementById("dm-input");
  var list = document.getElementById("dm-messages");

  function scrollToBottom() {
    list.scrollTop = list.scrollHeight;
  }

  function nowHHMM() {
    var d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  function addMessage(senderId, text) {
    var li = document.createElement("li");
    li.className = "bubble-row " + (senderId === myId ? "mine" : "theirs");

    var wrap = document.createElement("div");
    wrap.className = "bubble-wrap";

    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text; // innerHTML 미사용 (DOM XSS 방지)

    var time = document.createElement("span");
    time.className = "bubble-time";
    time.textContent = nowHHMM();

    wrap.appendChild(bubble);
    wrap.appendChild(time);
    li.appendChild(wrap);
    list.appendChild(li);
    scrollToBottom();
  }

  socket.on("connect", function () {
    socket.emit("join_dm", { peer_id: peerId });
  });

  socket.on("dm_receive", function (data) {
    addMessage(data.sender_id, data.message || "");
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var msg = input.value.trim();
    if (!msg) return;
    socket.emit("dm_message", { peer_id: peerId, message: msg });
    input.value = "";
    input.focus();
  });

  scrollToBottom();
})();
