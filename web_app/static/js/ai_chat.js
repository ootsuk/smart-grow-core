// AI Chat JavaScript

// グローバル変数
let currentSensorData = null;
let imagePreviewModal = null;
let imagesByDate = {}; // 日付ごとの画像データ
let allChatImages = []; // 全画像データ
let selectedImageFilename = null; // 選択された画像のファイル名

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
    
}

// 画像リストの読み込み（カレンダー用）
async function loadImageList() {
    try {
        // Layer 1の画像を取得
        const response = await fetch('/api/images?layer_id=1');
        const data = await response.json();
        
        allChatImages = data.images || [];
        imagesByDate = {};
        
        // 日付ごとにグループ化
        allChatImages.forEach(img => {
            const date = img.timestamp.split('T')[0]; // YYYY-MM-DD
            if (!imagesByDate[date]) {
                imagesByDate[date] = [];
            }
            imagesByDate[date].push(img);
        });
        
        // カレンダーを描画
        renderMiniCalendar();
        
    } catch (error) {
        console.error('画像リスト読み込みエラー:', error);
    }
}

// ミニカレンダーの描画
function renderMiniCalendar() {
    const container = document.getElementById('mini-calendar');
    
    // 最新の画像の日付を取得
    const latestDate = allChatImages.length > 0 ? new Date(allChatImages[0].timestamp) : new Date();
    const year = latestDate.getFullYear();
    const month = latestDate.getMonth();
    
    // カレンダーHTML
    let html = `
        <div class="text-center mb-2">
            <strong>${year}年${month + 1}月</strong>
        </div>
        <div class="mini-calendar-grid">
    `;
    
    // 曜日ヘッダー
    const weekDays = ['日', '月', '火', '水', '木', '金', '土'];
    weekDays.forEach(day => {
        html += `<div class="mini-cal-header">${day}</div>`;
    });
    
    // 月の最初の日と最後の日
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDayOfWeek = firstDay.getDay();
    const daysInMonth = lastDay.getDate();
    
    // 空白セル
    for (let i = 0; i < startDayOfWeek; i++) {
        html += `<div class="mini-cal-day"></div>`;
    }
    
    // 日付セル
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const hasImage = imagesByDate[dateStr] && imagesByDate[dateStr].length > 0;
        const isToday = dateStr === new Date().toISOString().split('T')[0];
        
        let className = 'mini-cal-day';
        if (hasImage) className += ' has-image';
        if (isToday) className += ' today';
        
        html += `<div class="${className}" onclick="selectDateForAI('${dateStr}')">${day}</div>`;
    }
    
    html += `</div>`;
    container.innerHTML = html;
}

// 日付選択（AI用）
function selectDateForAI(dateStr) {
    const images = imagesByDate[dateStr];
    if (!images || images.length === 0) {
        alert('この日の画像はありません');
        return;
    }
    
    // 最初の画像を選択
    const selectedImage = images[0];
    selectedImageFilename = selectedImage.filename;
    
    // プレビュー表示
    const preview = document.getElementById('selected-image-preview');
    const previewImg = preview.querySelector('img');
    const dateDisplay = document.getElementById('selected-image-date');
    
    previewImg.src = `/plant_images/layer_1/${selectedImage.filename}`;
    dateDisplay.textContent = new Date(selectedImage.timestamp).toLocaleDateString('ja-JP');
    preview.style.display = 'block';
    
    // カレンダーの選択状態を更新
    document.querySelectorAll('.mini-cal-day').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');
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
        
    } catch (error) {
        console.error('センサーデータ読み込みエラー:', error);
    }
}

// システムメッセージ（送信データ）を追加
function addSystemMessage(sensorData, imagePath) {
    const chatContainer = document.getElementById('chat-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'system-message';
    
    // 画像情報
    let imageHTML = '';
    if (imagePath) {
        imageHTML = `
            <div class="data-item">
                <i class="fas fa-image text-primary"></i>
                <span>${imagePath}</span>
            </div>
        `;
    }
    
    // センサーデータ
    const temp = sensorData.temperature ? `${sensorData.temperature}℃` : 'N/A';
    const humid = sensorData.humidity ? `${sensorData.humidity}%` : 'N/A';
    const supply = sensorData.supply_pressure ? `${sensorData.supply_pressure} kPa` : 'N/A';
    const drain = sensorData.drain_pressure ? `${sensorData.drain_pressure} kPa` : 'N/A';
    
    // 測定時刻
    let timeStr = 'N/A';
    if (sensorData.timestamp) {
        const dt = new Date(sensorData.timestamp);
        timeStr = dt.toLocaleString('ja-JP', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    messageDiv.innerHTML = `
        <div class="system-bubble">
            <div class="system-header">
                <i class="fas fa-chart-bar"></i>
                <span>以下のデータで分析中...</span>
            </div>
            <div class="system-content">
                ${imageHTML}
                <div class="data-row">
                    <div class="data-item">
                        <i class="fas fa-temperature-high text-danger"></i>
                        <span>${temp}</span>
                    </div>
                    <div class="data-item">
                        <i class="fas fa-tint text-info"></i>
                        <span>${humid}</span>
                    </div>
                    <div class="data-item">
                        <i class="fas fa-water text-primary"></i>
                        <span>給水: ${supply}</span>
                    </div>
                    <div class="data-item">
                        <i class="fas fa-faucet text-secondary"></i>
                        <span>排水: ${drain}</span>
                    </div>
                </div>
                <div class="data-row">
                    <div class="data-item">
                        <i class="fas fa-clock text-warning"></i>
                        <span>測定: ${timeStr}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

// 画像プレビューモーダルを表示
function showImagePreview() {
    if (selectedImageFilename) {
        const imagePath = `/plant_images/layer_1/${selectedImageFilename}`;
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
    
    // ユーザーメッセージを表示
    addUserMessage(message, selectedImageFilename);
    
    // 入力欄をクリア
    input.value = '';
    
    // 送信ボタンを無効化
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 送信中...';
    
    try {
        // 🔥 送信直前に最新のセンサーデータを取得
        await loadSensorData();
        
        // システムメッセージ（送信データ）を表示
        addSystemMessage(currentSensorData, selectedImage);
        
        // タイピングインジケーター表示
        showTypingIndicator();
        
        // センサーデータからタンク圧力を除外
        const sensorDataWithoutTank = currentSensorData ? {
            temperature: currentSensorData.temperature,
            humidity: currentSensorData.humidity
        } : null;
        
        // APIリクエスト
        const requestData = {
            message: message,
            image_filename: selectedImageFilename || null,
            sensor_data: sensorDataWithoutTank
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

