// 配置存储键
const CONFIG_KEY = 'photo_downloader_config';

// GitHub API 基础 URL
const GITHUB_API_BASE = 'https://api.github.com';

// DOM 元素
let elements = {};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initElements();
    loadConfig();
    setupEventListeners();
    fetchStatus();

    // 定时刷新状态（每30秒）
    setInterval(fetchStatus, 30000);
});

function initElements() {
    elements = {
        // 配置输入
        githubToken: document.getElementById('github-token'),
        githubRepo: document.getElementById('github-repo'),
        targetUrl: document.getElementById('target-url'),
        dropboxPath: document.getElementById('dropbox-path'),
        interval: document.getElementById('interval'),
        clearHistory: document.getElementById('clear-history'),

        // 按钮
        startBtn: document.getElementById('start-btn'),
        stopBtn: document.getElementById('stop-btn'),
        manualRunBtn: document.getElementById('manual-run-btn'),
        refreshLogsBtn: document.getElementById('refresh-logs-btn'),

        // 状态显示
        monitorStatus: document.getElementById('monitor-status'),
        lastRunTime: document.getElementById('last-run-time'),
        nextRunTime: document.getElementById('next-run-time'),
        lastResult: document.getElementById('last-result'),
        logContainer: document.getElementById('log-container'),

        // 帮助
        tokenHelp: document.getElementById('token-help'),
        helpSection: document.getElementById('help-section')
    };
}

function setupEventListeners() {
    elements.startBtn.addEventListener('click', startMonitoring);
    elements.stopBtn.addEventListener('click', stopMonitoring);
    elements.manualRunBtn.addEventListener('click', manualRun);
    elements.refreshLogsBtn.addEventListener('click', fetchLogs);
    elements.tokenHelp.addEventListener('click', (e) => {
        e.preventDefault();
        elements.helpSection.style.display = 'block';
    });
}

// 配置管理
function validateAndSaveConfig() {
    const config = {
        githubToken: elements.githubToken.value.trim(),
        githubRepo: elements.githubRepo.value.trim(),
        targetUrl: elements.targetUrl.value.trim(),
        dropboxPath: elements.dropboxPath.value.trim() || '/photos',
        interval: parseInt(elements.interval.value) || 60
    };

    // 验证必填字段
    if (!config.githubToken || !config.githubRepo || !config.targetUrl) {
        alert('❌ 请填写所有必填字段（标记 * 的字段）');
        return null;
    }

    // 验证仓库格式
    if (!config.githubRepo.match(/^[\w-]+\/[\w-]+$/)) {
        alert('❌ 仓库格式错误，应为: owner/repo');
        return null;
    }

    // 验证间隔
    if (config.interval < 10) {
        alert('❌ 检查间隔最小为 10 分钟');
        return null;
    }

    // 保存到 localStorage
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));

    return config;
}

function loadConfig() {
    const configStr = localStorage.getItem(CONFIG_KEY);
    if (!configStr) return;

    try {
        const config = JSON.parse(configStr);
        elements.githubToken.value = config.githubToken || '';
        elements.githubRepo.value = config.githubRepo || '';
        elements.targetUrl.value = config.targetUrl || '';
        elements.dropboxPath.value = config.dropboxPath || '/photos';
        elements.interval.value = config.interval || 60;
    } catch (e) {
        console.error('加载配置失败:', e);
    }
}

function getConfig() {
    const configStr = localStorage.getItem(CONFIG_KEY);
    if (!configStr) {
        // 静默返回 null，不弹窗提示
        return null;
    }
    return JSON.parse(configStr);
}

// GitHub API 调用
async function githubAPI(path, method = 'GET', body = null) {
    const config = getConfig();
    if (!config) return null;

    const url = `${GITHUB_API_BASE}${path}`;
    const options = {
        method,
        headers: {
            'Authorization': `token ${config.githubToken}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(url, options);

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || `HTTP ${response.status}`);
        }

        // 204 No Content 返回 null
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (e) {
        console.error('GitHub API 错误:', e);
        alert(`GitHub API 调用失败: ${e.message}\n\n请检查 Token 权限和网络连接`);
        return null;
    }
}

// 监控控制
async function startMonitoring() {
    // 验证并保存配置
    const config = validateAndSaveConfig();
    if (!config) return;

    const confirmMsg = elements.clearHistory.checked
        ? `确认开始监控？\n\n⚠️ 将清除历史记录并重新下载所有照片\n检查间隔: ${config.interval} 分钟`
        : `确认开始监控？\n\n检查间隔: ${config.interval} 分钟`;

    if (!confirm(confirmMsg)) {
        return;
    }

    // 1. 创建/更新 runtime-config.json（在 github_action 分支）
    const runtimeConfig = {
        enabled: true,
        interval: config.interval,
        clearHistory: elements.clearHistory.checked,  // 从 checkbox 读取
        lastRunTime: null,
        lastRunSuccess: null,
        taskConfig: {
            targetUrl: config.targetUrl,
            dropboxPath: config.dropboxPath
        }
    };

    const content = btoa(unescape(encodeURIComponent(JSON.stringify(runtimeConfig, null, 2))));

    // 检查文件是否存在（在 github_action 分支）
    const existing = await githubAPI(`/repos/${config.githubRepo}/contents/runtime-config.json?ref=github_action`);

    const result = await githubAPI(
        `/repos/${config.githubRepo}/contents/runtime-config.json`,
        'PUT',
        {
            message: 'Enable monitoring',
            content: content,
            branch: 'github_action',  // 指定提交到 github_action 分支
            sha: existing?.sha  // 如果文件存在，需要提供 SHA
        }
    );

    if (!result) return;

    // 2. 更新 UI
    updateUIAfterStart();

    alert('✅ 监控已启动！\n\nGitHub Actions 将在配置的间隔后开始执行。');

    // 清除 checkbox（首次运行标志仅生效一次）
    elements.clearHistory.checked = false;

    fetchStatus();
}

async function stopMonitoring() {
    const config = getConfig();
    if (!config) return;

    if (!confirm('确认停止监控？')) {
        return;
    }

    // 读取现有配置（从 github_action 分支）
    const existing = await githubAPI(`/repos/${config.githubRepo}/contents/runtime-config.json?ref=github_action`);
    if (!existing) {
        alert('❌ 配置文件不存在，请先启动监控');
        return;
    }

    // 解码并修改
    const currentConfig = JSON.parse(decodeURIComponent(escape(atob(existing.content))));
    currentConfig.enabled = false;

    const content = btoa(unescape(encodeURIComponent(JSON.stringify(currentConfig, null, 2))));

    const result = await githubAPI(
        `/repos/${config.githubRepo}/contents/runtime-config.json`,
        'PUT',
        {
            message: 'Disable monitoring',
            content: content,
            branch: 'github_action',  // 指定提交到 github_action 分支
            sha: existing.sha
        }
    );

    if (!result) return;

    updateUIAfterStop();
    alert('✅ 监控已停止');
    fetchStatus();
}

async function manualRun() {
    const config = getConfig();
    if (!config) return;

    if (!confirm('确认立即执行一次下载任务？')) {
        return;
    }

    const result = await githubAPI(
        `/repos/${config.githubRepo}/actions/workflows/photo-download.yml/dispatches`,
        'POST',
        {
            ref: 'github_action'  // 在 github_action 分支运行
        }
    );

    if (result === null) {  // 204 No Content 表示成功
        alert('✅ 任务已触发，请查看运行日志');
        setTimeout(fetchLogs, 3000);
    }
}

// 状态更新
async function fetchStatus() {
    const config = getConfig();
    if (!config) {
        // 没有配置时显示友好提示
        elements.monitorStatus.textContent = '未配置';
        elements.monitorStatus.className = 'status-badge status-inactive';
        elements.logContainer.innerHTML = '<p class="info">👈 请先填写左侧配置信息，然后点击"开始监控"</p>';
        return;
    }

    try {
        // 读取 runtime-config.json（从 github_action 分支）
        const configFile = await githubAPI(`/repos/${config.githubRepo}/contents/runtime-config.json?ref=github_action`);

        if (!configFile) {
            elements.monitorStatus.textContent = '未初始化';
            elements.monitorStatus.className = 'status-badge status-inactive';
            elements.logContainer.innerHTML = '<p class="info">请先点击"开始监控"初始化配置</p>';
            return;
        }

        const runtimeConfig = JSON.parse(decodeURIComponent(escape(atob(configFile.content))));

        // 更新状态
        if (runtimeConfig.enabled) {
            elements.monitorStatus.textContent = '运行中';
            elements.monitorStatus.className = 'status-badge status-active';
            elements.startBtn.disabled = true;
            elements.stopBtn.disabled = false;
        } else {
            elements.monitorStatus.textContent = '已停止';
            elements.monitorStatus.className = 'status-badge status-inactive';
            elements.startBtn.disabled = false;
            elements.stopBtn.disabled = true;
        }

        // 更新时间
        if (runtimeConfig.lastRunTime) {
            const lastRun = new Date(runtimeConfig.lastRunTime);
            elements.lastRunTime.textContent = lastRun.toLocaleString('zh-CN');

            // 计算下次运行时间
            const nextRun = new Date(lastRun.getTime() + runtimeConfig.interval * 60 * 1000);
            elements.nextRunTime.textContent = nextRun.toLocaleString('zh-CN');
        } else {
            elements.lastRunTime.textContent = '从未运行';
            elements.nextRunTime.textContent = '等待首次触发';
        }

        // 更新结果
        if (runtimeConfig.lastRunSuccess !== undefined && runtimeConfig.lastRunSuccess !== null) {
            elements.lastResult.textContent = runtimeConfig.lastRunSuccess ? '✅ 成功' : '❌ 失败';
        }

        // 自动加载日志
        fetchLogs();

    } catch (e) {
        console.error('获取状态失败:', e);
        elements.logContainer.innerHTML = '<p class="error">获取状态失败，请检查配置</p>';
    }
}

async function fetchLogs() {
    const config = getConfig();
    if (!config) return;

    try {
        const runs = await githubAPI(
            `/repos/${config.githubRepo}/actions/workflows/photo-download.yml/runs?per_page=5`
        );

        if (!runs || !runs.workflow_runs) {
            elements.logContainer.innerHTML = '<p class="info">暂无运行记录</p>';
            return;
        }

        const logHTML = runs.workflow_runs.map(run => {
            const startTime = new Date(run.created_at).toLocaleString('zh-CN');
            const duration = run.updated_at
                ? Math.round((new Date(run.updated_at) - new Date(run.created_at)) / 1000)
                : '--';

            let statusClass = '';
            let statusIcon = '';

            switch (run.status) {
                case 'completed':
                    statusClass = run.conclusion === 'success' ? 'log-success' : 'log-error';
                    statusIcon = run.conclusion === 'success' ? '✅' : '❌';
                    break;
                case 'in_progress':
                    statusClass = 'log-running';
                    statusIcon = '🔄';
                    break;
                default:
                    statusClass = 'log-pending';
                    statusIcon = '⏸️';
            }

            return `
                <div class="log-item ${statusClass}">
                    <div class="log-header">
                        <span class="log-status">${statusIcon} ${run.status}</span>
                        <span class="log-time">${startTime}</span>
                        <span class="log-duration">${duration}s</span>
                    </div>
                    <div class="log-message">
                        运行 #${run.run_number} - ${run.conclusion || '进行中'}
                        <a href="${run.html_url}" target="_blank">查看详情 →</a>
                    </div>
                </div>
            `;
        }).join('');

        elements.logContainer.innerHTML = logHTML || '<p class="info">暂无运行记录</p>';

    } catch (e) {
        console.error('获取日志失败:', e);
        elements.logContainer.innerHTML = '<p class="error">加载日志失败</p>';
    }
}

function updateUIAfterStart() {
    elements.startBtn.disabled = true;
    elements.stopBtn.disabled = false;
    elements.monitorStatus.textContent = '运行中';
    elements.monitorStatus.className = 'status-badge status-active';
}

function updateUIAfterStop() {
    elements.startBtn.disabled = false;
    elements.stopBtn.disabled = true;
    elements.monitorStatus.textContent = '已停止';
    elements.monitorStatus.className = 'status-badge status-inactive';
}
