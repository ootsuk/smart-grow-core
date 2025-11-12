// AI Chat JavaScript

// グローバル変数
let currentSensorData = null;
let imageSelectModal = null; // 画像選択モーダル
let imagesByDate = {}; // 日付ごとの画像データ
let allChatImages = []; // 全画像データ
let selectedImageFilename = null; // 選択された画像のファイル名
let tempSelectedImage = null; // モーダル内で一時的に選択中の画像

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    // モーダル初期化
    imageSelectModal = new bootstrap.Modal(document.getElementById('imageSelectModal'));
    
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
    
    // 画像添付ボタン
    document.getElementById('attach-image-btn').addEventListener('click', function() {
        openImageSelectModal();
    });
    
    // 画像削除ボタン
    document.getElementById('remove-image-btn').addEventListener('click', function() {
        removeAttachedImage();
    });
    
    // モーダル内の選択確定ボタン
    document.getElementById('confirm-select-btn').addEventListener('click', function() {
        confirmImageSelection();
    });
    
    // サムネイルクリックで拡大表示
    document.getElementById('attached-image-thumb').addEventListener('click', function() {
        if (this.src) {
            window.open(this.src, '_blank');
        }
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
        
    } catch (error) {
        console.error('画像リスト読み込みエラー:', error);
    }
}

// 画像選択モーダルを開く
function openImageSelectModal() {
    // カレンダーを描画
    renderModalCalendar();
    
    // モーダルを表示
    imageSelectModal.show();
}

// モーダル用カレンダーの描画
function renderModalCalendar() {
    const container = document.getElementById('modal-calendar');
    
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
        
        html += `<div class="${className}" onclick="selectDateInModal('${dateStr}')">${day}</div>`;
    }
    
    html += `</div>`;
    container.innerHTML = html;
}

// モーダル内で日付選択
function selectDateInModal(dateStr) {
    const images = imagesByDate[dateStr];
    if (!images || images.length === 0) {
        return; // 画像がない日はクリックしても何もしない
    }
    
    // 最初の画像を一時選択
    tempSelectedImage = images[0];
    
    // プレビュー表示
    const preview = document.getElementById('modal-image-preview');
    const previewImg = document.getElementById('modal-preview-image');
    const dateDisplay = document.getElementById('modal-preview-date');
    
    previewImg.src = `/plant_images/layer_1/${tempSelectedImage.filename}`;
    dateDisplay.textContent = new Date(tempSelectedImage.timestamp).toLocaleDateString('ja-JP');
    preview.style.display = 'block';
    
    // 選択ボタンを有効化
    document.getElementById('confirm-select-btn').disabled = false;
    
    // カレンダーの選択状態を更新
    document.querySelectorAll('.mini-cal-day').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');
}

// 画像選択を確定
function confirmImageSelection() {
    if (!tempSelectedImage) return;
    
    // 選択を確定
    selectedImageFilename = tempSelectedImage.filename;
    
    // 添付画像プレビューを表示
    const preview = document.getElementById('attached-image-preview');
    const thumb = document.getElementById('attached-image-thumb');
    const dateDisplay = document.getElementById('attached-image-date');
    
    thumb.src = `/plant_images/layer_1/${selectedImageFilename}`;
    dateDisplay.textContent = new Date(tempSelectedImage.timestamp).toLocaleDateString('ja-JP');
    preview.style.display = 'block';
    
    // モーダルを閉じる
    imageSelectModal.hide();
    
    // 一時選択をクリア
    tempSelectedImage = null;
}

// 添付画像を削除
function removeAttachedImage() {
    selectedImageFilename = null;
    document.getElementById('attached-image-preview').style.display = 'none';
    document.getElementById('attached-image-thumb').src = '';
}

// センサーデータの読み込み
async function loadSensorData() {
    try {
        const response = await fetch('/api/dashboard-data?layer_id=1');
        const data = await response.json();
        
        // sensor_dataオブジェクトを取得
        const sensorData = data.sensor_data || {};
        currentSensorData = sensorData;
        
        // システム情報の表示を更新（null/undefinedチェックに変更して0を許容）
        const temp = (sensorData.temperature !== null && sensorData.temperature !== undefined) ? `${sensorData.temperature}℃` : 'N/A';
        const humid = (sensorData.humidity !== null && sensorData.humidity !== undefined) ? `${sensorData.humidity}%` : 'N/A';
        
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
                <img src="/plant_images/layer_1/${imagePath}" class="rounded mb-2" style="max-width: 120px; max-height: 80px; object-fit: cover; display: block;">
                <small class="text-muted">📷 ${imagePath}</small>
            </div>
        `;
    }
    
    // センサーデータ（null/undefinedチェックに変更して0を許容）
    // 注意: タンク圧力データは植物成長に直接関係ないため除外
    const temp = (sensorData.temperature !== null && sensorData.temperature !== undefined) ? `${sensorData.temperature}℃` : 'N/A';
    const humid = (sensorData.humidity !== null && sensorData.humidity !== undefined) ? `${sensorData.humidity}%` : 'N/A';
    
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
        
        // センサーデータからタンク圧力を除外
        const sensorDataWithoutTank = currentSensorData ? {
            temperature: currentSensorData.temperature,
            humidity: currentSensorData.humidity
        } : null;
        
        // システムメッセージ（送信データ）を表示（タンク圧力なし）
        addSystemMessage(sensorDataWithoutTank, selectedImageFilename);
        
        // タイピングインジケーター表示
        showTypingIndicator();
        
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
        
        // 添付画像プレビューを自動削除（送信成功後）
        removeAttachedImage();
        
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

