const STORAGE_KEY = 'photo_downloader_server_config';

let cfg = { apiBase: '', apiKey: '' };
let running = false;
let logBuffer = [];
const LOG_MAX_LINES = 500;

document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    document.getElementById('save-config').addEventListener('click', saveConfig);
    document.getElementById('refresh-btn').addEventListener('click', refreshAll);
    document.getElementById('refresh-history').addEventListener('click', fetchHistory);
    document.getElementById('refresh-logs').addEventListener('click', fetchLogs);
    document.getElementById('start-btn').addEventListener('click', startLoop);
    document.getElementById('stop-btn').addEventListener('click', stopLoop);
    document.getElementById('run-once-btn').addEventListener('click', runOnce);
    refreshAll();
    setInterval(refreshAll, 30000);
    setInterval(fetchLogs, 5000);
});

function loadConfig() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        cfg = { ...cfg, ...saved };
        document.getElementById('api-base').value = cfg.apiBase || '';
        document.getElementById('api-key').value = cfg.apiKey || '';
    } catch (e) {
        console.error('加载配置失败', e);
    }
}

function saveConfig() {
    cfg.apiBase = document.getElementById('api-base').value.trim();
    cfg.apiKey = document.getElementById('api-key').value.trim();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
    alert('已保存连接配置');
    refreshAll();
}

async function apiFetch(path, options = {}) {
    if (!cfg.apiBase) {
        throw new Error('请先填写 API 地址并保存');
    }
    const url = cfg.apiBase.replace(/\/$/, '') + path;
    const headers = options.headers || {};
    if (cfg.apiKey) {
        headers['x-api-key'] = cfg.apiKey;
    }
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
    }
    if (resp.status === 204) return null;
    return await resp.json();
}

async function refreshAll() {
    await Promise.allSettled([fetchStatus(), fetchHistory(), fetchLogs()]);
}

function setBadge(running) {
    const badge = document.getElementById('running-badge');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    if (running) {
        badge.textContent = '运行中';
        badge.className = 'badge active';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        badge.textContent = '已停止';
        badge.className = 'badge inactive';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

function formatTime(t) {
    if (!t) return '--';
    try {
        return new Date(t).toLocaleString('zh-CN');
    } catch (e) {
        return t;
    }
}

async function fetchStatus() {
    try {
        const data = await apiFetch('/api/status');
        running = !!data.running;
        setBadge(running);

        const cfgRuntime = data.config || {};
        const effectiveCfg = cfgRuntime;

        fillConfigInputs(effectiveCfg, !running);

        document.getElementById('target-url').textContent = effectiveCfg.target_url || '--';
        document.getElementById('interval').textContent = effectiveCfg.check_interval ? `${effectiveCfg.check_interval}s` : '--';
        document.getElementById('started-at').textContent = formatTime(data.started_at);
        document.getElementById('ended-at').textContent = formatTime(data.ended_at);
        document.getElementById('url-total').textContent = data.total_photos ?? '--';
        document.getElementById('download-summary').textContent = `${data.download_success ?? '--'} / ${data.download_failed ?? '--'}`;
        document.getElementById('dropbox-summary').textContent = data.dropbox_enabled
            ? `${data.dropbox_uploaded ?? 0} / ${data.dropbox_failed ?? 0}`
            : '未开启';
        document.getElementById('dropbox-total').textContent = data.history_size ?? '--';
        document.getElementById('duration').textContent = data.duration_sec ? `${data.duration_sec}s` : '--';
        document.getElementById('last-error').textContent = data.last_error || '--';
    } catch (e) {
        console.error(e);
    }
}

function fillConfigInputs(cfgData, editable) {
    document.getElementById('cfg-target-url').value = cfgData.target_url || '';
    document.getElementById('cfg-interval').value = cfgData.check_interval || '';
    document.getElementById('cfg-dropbox-path').value = cfgData.dropbox_save_path || '';
    document.getElementById('cfg-target-url').disabled = !editable;
    document.getElementById('cfg-interval').disabled = !editable;
    document.getElementById('cfg-dropbox-path').disabled = !editable;
}

function clearConfigInputs() {
    document.getElementById('cfg-target-url').value = '';
    document.getElementById('cfg-interval').value = '';
    document.getElementById('cfg-dropbox-path').value = '';
}

function collectConfigInputs() {
    const targetUrl = document.getElementById('cfg-target-url').value.trim();
    const interval = parseInt(document.getElementById('cfg-interval').value, 10);
    const dropboxPath = document.getElementById('cfg-dropbox-path').value.trim();

    if (!targetUrl) throw new Error('目标 URL 不能为空');
    if (!interval || interval <= 0) throw new Error('检查间隔必须大于 0');
    if (!dropboxPath) throw new Error('Dropbox 路径不能为空');

    return { target_url: targetUrl, check_interval: interval, dropbox_save_path: dropboxPath };
}

async function fetchHistory() {
    try {
        const res = await apiFetch('/api/history?limit=10');
        const list = res.items || [];
        const container = document.getElementById('history-list');
        if (!list.length) {
            container.textContent = '暂无数据';
            return;
        }
        container.innerHTML = list
            .map(item => {
                const cls = item.success ? 'history-item success' : 'history-item failed';
                return `
                    <div class="${cls}">
                        <div><strong>${formatTime(item.started_at)} → ${formatTime(item.ended_at)}</strong></div>
                        <div class="history-meta">
                            新照片 ${item.new_photos ?? 0}，下载成功 ${item.download_success ?? 0}，失败 ${item.download_failed ?? 0}，耗时 ${item.duration_sec ?? '--'}s
                        </div>
                        ${item.last_error ? `<div class="history-meta error">错误：${item.last_error}</div>` : ''}
                    </div>
                `;
            })
            .join('');
    } catch (e) {
        console.error(e);
    }
}

async function fetchLogs() {
    try {
        const tail = parseInt(document.getElementById('log-tail').value) || 200;
        const res = await apiFetch(`/api/logs?tail=${tail}`);
        const lines = res.lines || [];
        logBuffer = lines.map(line => line.replace(/\n$/, ''));
        renderLogBuffer();
    } catch (e) {
        document.getElementById('log-container').textContent = `加载日志失败：${e.message}`;
    }
}

async function startLoop() {
    try {
        const payload = collectConfigInputs();
        await apiFetch('/api/control/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        alert('已请求启动');
        await refreshAll();
    } catch (e) {
        alert(`启动失败: ${e.message}`);
    }
}

async function stopLoop() {
    try {
        await apiFetch('/api/control/stop', { method: 'POST' });
        alert('已请求停止');
        clearConfigInputs();
        await refreshAll();
    } catch (e) {
        alert(`停止失败: ${e.message}`);
    }
}

async function runOnce() {
    try {
        const payload = collectConfigInputs();
        await apiFetch('/api/control/run-once', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        alert('已触发手动运行');
        await refreshAll();
    } catch (e) {
        alert(`运行失败: ${e.message}`);
    }
}

function renderLogBuffer(autoScroll = false) {
    const container = document.getElementById('log-container');
    container.textContent = logBuffer.join('\n');
    if (autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}
