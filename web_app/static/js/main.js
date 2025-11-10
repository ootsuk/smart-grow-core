// ===== Smart Grow System 共通JavaScript =====

// 現在時刻の表示（フッター）
function updateCurrentTime() {
    const now = new Date();
    const timeString = now.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = timeString;
    }
}

// 初回実行と1秒ごとの更新
updateCurrentTime();
setInterval(updateCurrentTime, 1000);

// ===== ユーティリティ関数 =====

/**
 * 日時フォーマット関数
 * @param {string} isoString - ISO形式の日時文字列
 * @param {boolean} withSeconds - 秒を含めるか
 * @returns {string} フォーマットされた日時文字列
 */
function formatDateTime(isoString, withSeconds = true) {
    if (!isoString) return 'N/A';
    
    const date = new Date(isoString);
    const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    };
    
    if (withSeconds) {
        options.second = '2-digit';
    }
    
    return date.toLocaleString('ja-JP', options);
}

/**
 * 相対時間表示（例: "3分前"）
 * @param {string} isoString - ISO形式の日時文字列
 * @returns {string} 相対時間の文字列
 */
function getRelativeTime(isoString) {
    if (!isoString) return 'N/A';
    
    const now = new Date();
    const past = new Date(isoString);
    const diffMs = now - past;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) {
        return `${diffSec}秒前`;
    } else if (diffMin < 60) {
        return `${diffMin}分前`;
    } else if (diffHour < 24) {
        return `${diffHour}時間前`;
    } else {
        return `${diffDay}日前`;
    }
}

/**
 * エラーメッセージの表示
 * @param {string} message - エラーメッセージ
 * @param {string} containerId - 表示先のコンテナID
 */
function showError(message, containerId = 'error-container') {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <i class="fas fa-exclamation-circle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
}

/**
 * 成功メッセージの表示
 * @param {string} message - 成功メッセージ
 * @param {string} containerId - 表示先のコンテナID
 */
function showSuccess(message, containerId = 'success-container') {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <i class="fas fa-check-circle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
}

/**
 * ローディングスピナーの表示
 * @param {string} containerId - 表示先のコンテナID
 */
function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status">
                <span class="visually-hidden">読み込み中...</span>
            </div>
            <p class="text-muted mt-2">データを読み込んでいます...</p>
        </div>
    `;
}

/**
 * データなしメッセージの表示
 * @param {string} containerId - 表示先のコンテナID
 * @param {string} message - 表示メッセージ
 */
function showNoData(containerId, message = 'データがありません') {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="text-center py-5 text-muted">
            <i class="fas fa-inbox fa-3x mb-3"></i>
            <p>${message}</p>
        </div>
    `;
}

/**
 * ログレベルに応じたバッジクラスを取得
 * @param {string} logLevel - ログレベル（CRITICAL, ERROR, WARNING, INFO）
 * @returns {string} Bootstrapバッジクラス
 */
function getLogLevelBadge(logLevel) {
    const badges = {
        'CRITICAL': 'bg-danger',
        'ERROR': 'bg-danger',
        'WARNING': 'bg-warning text-dark',
        'INFO': 'bg-info text-dark',
        'DEBUG': 'bg-secondary'
    };
    return badges[logLevel] || 'bg-secondary';
}

/**
 * ログレベルに応じたアイコンを取得
 * @param {string} logLevel - ログレベル
 * @returns {string} Font Awesomeアイコンクラス
 */
function getLogLevelIcon(logLevel) {
    const icons = {
        'CRITICAL': 'fas fa-exclamation-circle text-danger',
        'ERROR': 'fas fa-times-circle text-danger',
        'WARNING': 'fas fa-exclamation-triangle text-warning',
        'INFO': 'fas fa-info-circle text-info',
        'DEBUG': 'fas fa-bug text-secondary'
    };
    return icons[logLevel] || 'fas fa-circle text-secondary';
}

/**
 * ジョブタイプに応じたアイコンを取得
 * @param {string} jobType - ジョブタイプ（camera, sensor, water）
 * @returns {string} Font Awesomeアイコンクラス
 */
function getJobIcon(jobType) {
    const icons = {
        'camera': 'fas fa-camera text-primary',
        'sensor': 'fas fa-thermometer-half text-danger',
        'water': 'fas fa-tint text-info'
    };
    return icons[jobType] || 'fas fa-cog';
}

/**
 * ジョブタイプの日本語ラベルを取得
 * @param {string} jobType - ジョブタイプ
 * @returns {string} 日本語ラベル
 */
function getJobLabel(jobType) {
    const labels = {
        'camera': '写真撮影',
        'sensor': 'センサー測定',
        'water': '水やり'
    };
    return labels[jobType] || jobType;
}

/**
 * 数値を指定した小数点以下の桁数で丸める
 * @param {number} value - 数値
 * @param {number} decimals - 小数点以下の桁数
 * @returns {number} 丸めた数値
 */
function roundTo(value, decimals = 2) {
    return Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals);
}

/**
 * Chart.jsの共通設定
 */
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            display: true,
            position: 'top'
        }
    },
    scales: {
        x: {
            grid: {
                display: false
            }
        },
        y: {
            beginAtZero: false,
            grid: {
                color: 'rgba(0, 0, 0, 0.05)'
            }
        }
    }
};

/**
 * Chart.jsのカラーパレット
 */
const chartColors = {
    temperature: {
        border: 'rgb(255, 99, 132)',
        background: 'rgba(255, 99, 132, 0.2)'
    },
    humidity: {
        border: 'rgb(54, 162, 235)',
        background: 'rgba(54, 162, 235, 0.2)'
    },
    supply_pressure: {
        border: 'rgb(75, 192, 192)',
        background: 'rgba(75, 192, 192, 0.2)'
    },
    drain_pressure: {
        border: 'rgb(255, 206, 86)',
        background: 'rgba(255, 206, 86, 0.2)'
    }
};

// ===== ページロード時の初期化 =====
document.addEventListener('DOMContentLoaded', function() {
    // ツールチップの有効化（Bootstrap 5）
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // ポップオーバーの有効化（Bootstrap 5）
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    console.log('Smart Grow System initialized');
});

// ===== エクスポート（モジュール使用時） =====
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatDateTime,
        getRelativeTime,
        showError,
        showSuccess,
        showLoading,
        showNoData,
        getLogLevelBadge,
        getLogLevelIcon,
        getJobIcon,
        getJobLabel,
        roundTo,
        chartDefaults,
        chartColors
    };
}

