// AI Chat JavaScript

// グローバル変数
let currentSensorData = null;
let imagePreviewModal = null;

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    // モーダル初期化
    imagePreviewModal = new bootstrap.Modal(document.getElementById('imagePreviewModal'));
    
    // イベントリスナー設定
    setupEventListeners();
    
    // 画像リストを読み込み
    loadImageList();
    
    // センサーデータを読み込み（初回）
    loadSensorData();
    
    // センサーデータを定期的に更新（30秒ごと）
    setInterval(loadSensorData, 30000);
    
    // Marked.jsの設定
    marked.setOptions({
        breaks: true,
        gfm: true,
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        }
    });
});

// イベントリスナーの設定
function setupEventListeners() {
    // チャットフォーム送信
    document.getElementById('chat-form').addEventListener('submit', function(e) {
        e.preventDefault();
        sendMessage();
    });
    
    // クイックアクションボタン
    document.querySelectorAll('.quick-action-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            document.getElementById('user-input').value = question;
            sendMessage();
        });
    });
    
    // 画像選択
    document.getElementById('image-selector').addEventListener('change', function() {
        updateImagePreview();
    });
}

// 画像リストの読み込み
async function loadImageList() {
    try {
        // Layer 1の画像を取得（必要に応じて変更可能）
        const response = await fetch('/api/images?layer_id=1');
        const data = await response.json();
        
        const selector = document.getElementById('image-selector');
        selector.innerHTML = '<option value="">選択なし</option>';
        
        if (data.images && data.images.length > 0) {
            data.images.forEach(img => {
                const option = document.createElement('option');
                option.value = img.filename;
                // timestampから日付を抽出（YYYY-MM-DD HH:MM:SS形式）
                const date = img.timestamp ? img.timestamp.split('T')[0] : 'N/A';
                option.textContent = `${date} - ${img.filename}`;
                selector.appendChild(option);
            });
        }
    } catch (error) {
        console.error('画像リスト読み込みエラー:', error);
    }
}

// センサーデータの読み込み
async function loadSensorData() {
    try {
        const response = await fetch('/api/dashboard-data?layer_id=1');
        const data = await response.json();
        
        // sensor_dataオブジェクトを取得
        const sensorData = data.sensor_data || {};
        currentSensorData = sensorData;
        
        // システム情報の表示を更新（スペースを追加してN/A kPaのように表示）
        const temp = sensorData.temperature ? `${sensorData.temperature}℃` : 'N/A';
        const humid = sensorData.humidity ? `${sensorData.humidity}%` : 'N/A';
        const supply = sensorData.supply_pressure ? `${sensorData.supply_pressure} kPa` : 'N/A';
        const drain = sensorData.drain_pressure ? `${sensorData.drain_pressure} kPa` : 'N/A';
        
        // タイムスタンプを表示形式に変換
        let timeStr = '';
        if (sensorData.timestamp) {
            const dt = new Date(sensorData.timestamp);
            timeStr = ` (${dt.toLocaleString('ja-JP', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})})`;
        }
        
        const infoText = `温度: ${temp}, 湿度: ${humid}, 給水タンク: ${supply}, 排水タンク: ${drain}${timeStr}`;
        document.getElementById('system-info-display').textContent = infoText;
        
    } catch (error) {
        console.error('センサーデータ読み込みエラー:', error);
        document.getElementById('system-info-display').textContent = 'センサーデータの取得に失敗しました';
    }
}

// 画像プレビューの更新
function updateImagePreview() {
    const selector = document.getElementById('image-selector');
    const preview = document.getElementById('selected-image-preview');
    const previewImg = preview.querySelector('img');
    
    if (selector.value) {
        // Layer 1を想定（必要に応じて動的に変更）
        const imagePath = `/plant_images/layer_1/${selector.value}`;
        previewImg.src = imagePath;
        preview.style.display = 'block';
    } else {
        preview.style.display = 'none';
    }
}

// 画像プレビューモーダルを表示
function showImagePreview() {
    const selector = document.getElementById('image-selector');
    if (selector.value) {
        const imagePath = `/plant_images/layer_1/${selector.value}`;
        document.getElementById('modal-preview-image').src = imagePath;
        imagePreviewModal.show();
    }
}

// メッセージ送信
async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    
    if (!message) {
        return;
    }
    
    const sendBtn = document.getElementById('send-btn');
    const imageSelector = document.getElementById('image-selector');
    const selectedImage = imageSelector.value;
    
    // ユーザーメッセージを表示
    addUserMessage(message, selectedImage);
    
    // 入力欄をクリア
    input.value = '';
    
    // 送信ボタンを無効化
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 送信中...';
    
    // タイピングインジケーター表示
    showTypingIndicator();
    
    try {
        // 🔥 送信直前に最新のセンサーデータを取得
        await loadSensorData();
        
        // APIリクエスト
        const requestData = {
            message: message,
            image_filename: selectedImage || null,
            sensor_data: currentSensorData
        };
        
        const response = await fetch('/api/ai-chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // タイピングインジケーターを削除
        removeTypingIndicator();
        
        // エラーレスポンスの場合
        if (data.error) {
            addAIMessage(`⚠️ **エラー**\n\n${data.error}`);
        } else {
            // AIメッセージを表示
            addAIMessage(data.response);
        }
        
    } catch (error) {
        console.error('メッセージ送信エラー:', error);
        removeTypingIndicator();
        addAIMessage('⚠️ **エラー**\n\n申し訳ございません。予期しないエラーが発生しました。もう一度お試しください。');
    } finally {
        // 送信ボタンを有効化
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 送信';
    }
}

// ユーザーメッセージを追加
function addUserMessage(message, imagePath) {
    const chatContainer = document.getElementById('chat-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    
    let imageHTML = '';
    if (imagePath) {
        const fullPath = `/plant_images/layer_1/${imagePath}`;
        imageHTML = `<img src="${fullPath}" class="attached-image" alt="添付画像" onclick="showAttachedImage('${fullPath}')">`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-user"></i>
        </div>
        <div class="message-bubble user-bubble">
            <div class="message-content">
                <p class="mb-0">${escapeHtml(message)}</p>
                ${imageHTML}
            </div>
        </div>
    `;
    
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

// AIメッセージを追加
function addAIMessage(message) {
    const chatContainer = document.getElementById('chat-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    
    // MarkdownをHTMLに変換
    const htmlContent = marked.parse(message);
    
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-bubble ai-bubble">
            <div class="message-content markdown-body">
                ${htmlContent}
            </div>
        </div>
    `;
    
    chatContainer.appendChild(messageDiv);
    
    // コードブロックのハイライトを適用
    messageDiv.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
    
    scrollToBottom();
}

// タイピングインジケーターを表示
function showTypingIndicator() {
    const chatContainer = document.getElementById('chat-container');
    
    const indicatorDiv = document.createElement('div');
    indicatorDiv.className = 'message ai-message';
    indicatorDiv.id = 'typing-indicator';
    
    indicatorDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-bubble ai-bubble">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    
    chatContainer.appendChild(indicatorDiv);
    scrollToBottom();
}

// タイピングインジケーターを削除
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// チャットを最下部にスクロール
function scrollToBottom() {
    const chatContainer = document.getElementById('chat-container');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 添付画像をモーダルで表示
function showAttachedImage(imagePath) {
    document.getElementById('modal-preview-image').src = imagePath;
    imagePreviewModal.show();
}

// HTMLエスケープ
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

