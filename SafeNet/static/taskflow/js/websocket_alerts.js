const alertSocket = new WebSocket('ws://' + window.location.host + '/ws/alerts/');

alertSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    const alertMessage = data['alert'];
    const alertBox = document.getElementById('alert-box');
    alertBox.innerHTML += `<div class="alert alert-warning">${alertMessage}</div>`;
};

alertSocket.onclose = function(e) {
    console.error('WebSocket closed unexpectedly');
};
