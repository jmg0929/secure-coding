// 전체 채팅 클라이언트.
// 서버에서 메시지를 이미 이스케이프해 보내지만, 클라이언트에서도
// textContent 로만 DOM 에 삽입하여 XSS 를 이중으로 차단한다.
(function () {
  "use strict";

  var socket = io({ transports: ["websocket", "polling"] });

  var form = document.getElementById("chat-form");
  var input = document.getElementById("chat-input");
  var list = document.getElementById("messages");

  socket.on("receive_message", function (data) {
    var li = document.createElement("li");
    var who = document.createElement("strong");
    who.textContent = (data.username || "익명") + ": ";
    li.appendChild(who);
    // innerHTML 을 쓰지 않고 textContent 로만 삽입 (DOM XSS 방지)
    li.appendChild(document.createTextNode(data.message || ""));
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var msg = input.value.trim();
    if (!msg) return;
    socket.emit("send_message", { message: msg });
    input.value = "";
  });
})();
