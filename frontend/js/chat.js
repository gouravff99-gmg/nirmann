// =============================================
//  NIRMAN — Chat Widget
//  File: frontend/js/chat.js
// =============================================

let _chatOpen = false;

function toggleChat() {
  _chatOpen = !_chatOpen;
  document.getElementById('chat-panel').classList.toggle('hidden', !_chatOpen);
  document.getElementById('chat-toggle').textContent = _chatOpen ? '✕' : '💬';
}

async function sendChat() {
  const inp = document.getElementById('chat-input');
  const msg = (inp.value || '').trim();
  if (!msg) return;
  inp.value = '';
  appendChat(msg, 'user');
  try {
    const d = await api('POST', '/assistant/chat', { message: msg });
    appendChat(d.response, 'bot');
  } catch (e) {
    appendChat('Sorry, I encountered an error. Please try again.', 'bot');
  }
}

function sendQuickQ(text) {
  document.getElementById('chat-input').value = text;
  sendChat();
}

function appendChat(text, from) {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${from}`;
  div.innerHTML = `<div class="chat-bubble">${text}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}
