// Global variables
let updateInterval;
let selectedFile = null;
let printStartTime = null;
let consoleLines = [];
let currentConfigTab = 'general';
let configData = {};

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupUpload();
    updateStatus();
    updateFiles();
    checkUSB();
    loadPluginStatusItems();
    addConsoleMessage('System initialized with plugin support', 'info');
    addConsoleMessage('Waiting for printer connection...');
    
    updateInterval = setInterval(() => {
        updateStatus();
        checkUSB();
        loadPluginStatusItems();
    }, 3000);
});

// Plugin Status Items
async function loadPluginStatusItems() {
    try {
        const response = await fetch('/api/config/ui/status_bar_items');
        const result = await response.json();
        
        if (result.success && result.items) {
            updatePluginStatusItems(result.items);
        }
    } catch (error) {
        console.error('Error loading plugin status items:', error);
    }
}

function updatePluginStatusItems(items) {
    const container = document.getElementById('pluginStatusItems');
    const additionalContainer = document.getElementById('additionalStatusItems');
    
    // Sort items by priority
    items.sort((a, b) => (a.priority || 100) - (b.priority || 100));
    
    container.innerHTML = '';
    additionalContainer.innerHTML = '';
    
    items.forEach(item => {
        const element = createPluginStatusElement(item);
        
        // Add to appropriate container based on priority
        if (item.priority && item.priority < 50) {
            container.appendChild(element);
        } else {
            additionalContainer.appendChild(element);
        }
    });
}

function createPluginStatusElement(item) {
    const element = document.createElement('div');
    element.className = 'plugin-status-item';
    element.innerHTML = item.content;
    
    if (item.style) {
        Object.assign(element.style, item.style);
    }
    
    if (item.tooltip) {
        element.title = item.tooltip;
    }
    
    return element;
}

// Config Modal Functions
function openConfigModal() {
    document.getElementById('configModal').classList.add('active');
    loadConfigTab(currentConfigTab);
}

function closeConfigModal() {
    document.getElementById('configModal').classList.remove('active');
}

function switchConfigTab(tabName) {
    currentConfigTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.modal-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    loadConfigTab(tabName);
}

async function loadConfigTab(tabName) {
    const content = document.getElementById('configContent');
    
    switch (tabName) {
        case 'general':
            content.innerHTML = await generateGeneralConfig();
            break;
        case 'printer':
            content.innerHTML = await generatePrinterConfig();
            break;
        case 'interface':
            content.innerHTML = await generateInterfaceConfig();
            break;
        case 'plugins':
            content.innerHTML = await generatePluginsConfig();
            break;
        default:
            // Check if it's a plugin tab
            await loadPluginConfigTab(tabName);
            break;
    }
}

async function generateGeneralConfig() {
    try {
        const response = await fetch('/api/config/app');
        const result = await response.json();
        const config = result.config;

        return `
            <div class="config-section">
                <div class="config-section-title">Application Settings</div>
                
                <div class="form-group">
                    <label class="form-label">Theme</label>
                    <select class="form-input" id="theme" onchange="updateConfigValue('interface', 'theme', this.value)">
                        <option value="dark" ${config.interface?.theme === 'dark' ? 'selected' : ''}>Dark</option>
                        <option value="light" ${config.interface?.theme === 'light' ? 'selected' : ''}>Light</option>
                    </select>
                    <div class="form-help">Choose the interface theme</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Update Interval (ms)</label>
                    <input type="number" class="form-input" id="updateInterval" 
                           value="${config.interface?.update_interval || 3000}" min="1000" max="10000"
                           onchange="updateConfigValue('interface', 'update_interval', parseInt(this.value))">
                    <div class="form-help">How often to update status information</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Console Max Lines</label>
                    <input type="number" class="form-input" id="consoleMaxLines" 
                           value="${config.interface?.console_max_lines || 50}" min="10" max="200"
                           onchange="updateConfigValue('interface', 'console_max_lines', parseInt(this.value))">
                    <div class="form-help">Maximum number of lines to keep in console</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">
                        <input type="checkbox" class="form-checkbox" id="webcamEnabled" 
                               ${config.interface?.webcam_enabled ? 'checked' : ''}
                               onchange="updateConfigValue('interface', 'webcam_enabled', this.checked)">
                        Enable Webcam
                    </label>
                    <div class="form-help">Show webcam feed if available</div>
                </div>
            </div>
        `;
    } catch (error) {
        return '<div class="alert alert-error">Failed to load general configuration</div>';
    }
}

async function generatePrinterConfig() {
    try {
        const response = await fetch('/api/config/app');
        const result = await response.json();
        const config = result.config;

        return `
            <div class="config-section">
                <div class="config-section-title">Printer Communication</div>
                
                <div class="form-group">
                    <label class="form-label">Serial Port</label>
                    <input type="text" class="form-input" id="serialPort" 
                           value="${config.printer?.serial_port || '/dev/serial0'}"
                           onchange="updateConfigValue('printer', 'serial_port', this.value)">
                    <div class="form-help">Serial port for printer communication</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Baud Rate</label>
                    <select class="form-input" id="baudrate" onchange="updateConfigValue('printer', 'baudrate', parseInt(this.value))">
                        <option value="9600" ${config.printer?.baudrate === 9600 ? 'selected' : ''}>9600</option>
                        <option value="19200" ${config.printer?.baudrate === 19200 ? 'selected' : ''}>19200</option>
                        <option value="38400" ${config.printer?.baudrate === 38400 ? 'selected' : ''}>38400</option>
                        <option value="57600" ${config.printer?.baudrate === 57600 ? 'selected' : ''}>57600</option>
                        <option value="115200" ${config.printer?.baudrate === 115200 ? 'selected' : ''}>115200</option>
                    </select>
                    <div class="form-help">Serial communication speed</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Timeout (seconds)</label>
                    <input type="number" class="form-input" id="timeout" 
                           value="${config.printer?.timeout || 5.0}" min="1" max="30" step="0.1"
                           onchange="updateConfigValue('printer', 'timeout', parseFloat(this.value))">
                    <div class="form-help">Communication timeout</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Firmware Version</label>
                    <input type="text" class="form-input" id="firmwareVersion" 
                           value="${config.printer?.firmware_version || 'V4.13'}"
                           onchange="updateConfigValue('printer', 'firmware_version', this.value)">
                    <div class="form-help">Expected firmware version</div>
                </div>
            </div>
            
            <div class="config-section">
                <div class="config-section-title">USB Gadget Settings</div>
                
                <div class="form-group">
                    <label class="form-label">Mount Point</label>
                    <input type="text" class="form-input" id="mountPoint" 
                           value="${config.usb?.mount_point || '/mnt/usb_share'}"
                           onchange="updateConfigValue('usb', 'mount_point', this.value)">
                    <div class="form-help">USB drive mount point</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Image File</label>
                    <input type="text" class="form-input" id="imageFile" 
                           value="${config.usb?.image_file || '/piusb.bin'}"
                           onchange="updateConfigValue('usb', 'image_file', this.value)">
                    <div class="form-help">USB gadget image file path</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">
                        <input type="checkbox" class="form-checkbox" id="autoStart" 
                               ${config.usb?.auto_start ? 'checked' : ''}
                               onchange="updateConfigValue('usb', 'auto_start', this.checked)">
                        Auto-start USB Gadget
                    </label>
                    <div class="form-help">Automatically start USB gadget on boot</div>
                </div>
            </div>
        `;
    } catch (error) {
        return '<div class="alert alert-error">Failed to load printer configuration</div>';
    }
}

async function generateInterfaceConfig() {
    try {
        const response = await fetch('/api/config/app');
        const result = await response.json();
        const config = result.config;

        return `
            <div class="config-section">
                <div class="config-section-title">File Management</div>
                
                <div class="form-group">
                    <label class="form-label">Maximum Files</label>
                    <input type="number" class="form-input" id="maxFiles" 
                           value="${config.file_management?.max_files || 50}" min="10" max="1000"
                           onchange="updateConfigValue('file_management', 'max_files', parseInt(this.value))">
                    <div class="form-help">Maximum number of files to keep</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Maximum Age (days)</label>
                    <input type="number" class="form-input" id="maxAgeDays" 
                           value="${config.file_management?.max_age_days || 30}" min="1" max="365"
                           onchange="updateConfigValue('file_management', 'max_age_days', parseInt(this.value))">
                    <div class="form-help">Automatically remove files older than this</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">
                        <input type="checkbox" class="form-checkbox" id="autoCleanup" 
                               ${config.file_management?.auto_cleanup ? 'checked' : ''}
                               onchange="updateConfigValue('file_management', 'auto_cleanup', this.checked)">
                        Enable Auto-cleanup
                    </label>
                    <div class="form-help">Automatically remove old files</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Allowed Extensions</label>
                    <input type="text" class="form-input" id="allowedExtensions" 
                           value="${(config.file_management?.allowed_extensions || []).join(', ')}"
                           onchange="updateConfigValue('file_management', 'allowed_extensions', this.value.split(',').map(s => s.trim()))">
                    <div class="form-help">Comma-separated list of allowed file extensions</div>
                </div>
            </div>
        `;
    } catch (error) {
        return '<div class="alert alert-error">Failed to load interface configuration</div>';
    }
}

async function generatePluginsConfig() {
    try {
        const response = await fetch('/api/config/plugins/list');
        const result = await response.json();
        
        if (!result.success) {
            return '<div class="alert alert-error">Failed to load plugins</div>';
        }

        const plugins = result.plugins || [];
        
        let html = `
            <div class="config-section">
                <div class="config-section-title">Available Plugins</div>
                <div class="plugin-list">
        `;

        if (plugins.length === 0) {
            html += '<div class="empty-state">No plugins found</div>';
        } else {
            plugins.forEach(plugin => {
                html += `
                    <div class="plugin-item">
                        <div class="plugin-header">
                            <div>
                                <span class="plugin-name">${plugin.name}</span>
                                <span class="plugin-version">v${plugin.version}</span>
                            </div>
                            <span class="plugin-status ${plugin.enabled ? 'enabled' : 'disabled'}">
                                ${plugin.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                        </div>
                        <div class="plugin-description">${plugin.description}</div>
                        <div class="plugin-author">by ${plugin.author}</div>
                        <div class="plugin-actions">
                            ${plugin.enabled ? 
                                `<button class="plugin-btn plugin-btn-disable" onclick="togglePlugin('${plugin.name}', false)">Disable</button>` :
                                `<button class="plugin-btn plugin-btn-enable" onclick="togglePlugin('${plugin.name}', true)">Enable</button>`
                            }
                            <button class="plugin-btn plugin-btn-reload" onclick="reloadPlugin('${plugin.name}')">Reload</button>
                        </div>
                    </div>
                `;
            });
        }

        html += '</div></div>';

        // Add plugin-specific config tabs
        const pluginTabsResponse = await fetch('/api/config/ui/config_tabs');
        const pluginTabsResult = await pluginTabsResponse.json();
        
        if (pluginTabsResult.success && pluginTabsResult.tabs.length > 0) {
            // Add plugin tabs to the modal tabs
            const tabsContainer = document.getElementById('configTabs');
            
            // Remove existing plugin tabs
            tabsContainer.querySelectorAll('[data-plugin-tab]').forEach(tab => tab.remove());
            
            // Add new plugin tabs
            pluginTabsResult.tabs.forEach(tab => {
                const tabButton = document.createElement('button');
                tabButton.className = 'modal-tab';
                tabButton.setAttribute('data-plugin-tab', 'true');
                tabButton.onclick = () => switchConfigTab(tab.id);
                tabButton.innerHTML = `
                    <span class="modal-tab-icon">${tab.icon || '🔌'}</span>
                    ${tab.title}
                `;
                tabsContainer.appendChild(tabButton);
            });
        }

        return html;
        
    } catch (error) {
        return '<div class="alert alert-error">Failed to load plugins configuration</div>';
    }
}

async function loadPluginConfigTab(tabId) {
    try {
        const response = await fetch('/api/config/ui/config_tabs');
        const result = await response.json();
        
        if (result.success) {
            const tab = result.tabs.find(t => t.id === tabId);
            if (tab && tab.content) {
                const content = document.getElementById('configContent');
                content.innerHTML = generatePluginTabContent(tab);
            }
        }
    } catch (error) {
        console.error('Error loading plugin config tab:', error);
    }
}

function generatePluginTabContent(tab) {
    if (tab.content.type === 'form') {
        let html = `<div class="config-section">
            <div class="config-section-title">${tab.title} Configuration</div>`;
        
        tab.content.fields.forEach(field => {
            html += generateFormField(field, tab.plugin);
        });
        
        html += '</div>';
        return html;
    }
    
    return '<div class="alert alert-warning">Unsupported plugin configuration format</div>';
}

function generateFormField(field, pluginName) {
    let inputHtml = '';
    const fieldId = `plugin_${pluginName}_${field.name}`;
    
    switch (field.type) {
        case 'text':
            inputHtml = `<input type="text" class="form-input" id="${fieldId}" 
                        value="${field.value || ''}" placeholder="${field.placeholder || ''}"
                        ${field.required ? 'required' : ''}
                        onchange="updatePluginConfigValue('${pluginName}', '${field.name}', this.value)">`;
            break;
        case 'checkbox':
            inputHtml = `<label class="form-label">
                        <input type="checkbox" class="form-checkbox" id="${fieldId}" 
                        ${field.value ? 'checked' : ''}
                        onchange="updatePluginConfigValue('${pluginName}', '${field.name}', this.checked)">
                        ${field.label}
                        </label>`;
            break;
        case 'color':
            inputHtml = `<input type="color" class="form-color" id="${fieldId}" 
                        value="${field.value || '#000000'}"
                        onchange="updatePluginConfigValue('${pluginName}', '${field.name}', this.value)">`;
            break;
        case 'number':
            inputHtml = `<input type="number" class="form-input" id="${fieldId}" 
                        value="${field.value || ''}" 
                        ${field.min !== undefined ? `min="${field.min}"` : ''}
                        ${field.max !== undefined ? `max="${field.max}"` : ''}
                        ${field.step !== undefined ? `step="${field.step}"` : ''}
                        onchange="updatePluginConfigValue('${pluginName}', '${field.name}', parseFloat(this.value))">`;
            break;
        default:
            inputHtml = `<input type="text" class="form-input" id="${fieldId}" 
                        value="${field.value || ''}"
                        onchange="updatePluginConfigValue('${pluginName}', '${field.name}', this.value)">`;
            break;
    }
    
    if (field.type === 'checkbox') {
        return `<div class="form-group">
            ${inputHtml}
            ${field.help ? `<div class="form-help">${field.help}</div>` : ''}
        </div>`;
    } else {
        return `<div class="form-group">
            <label class="form-label">${field.label}</label>
            ${inputHtml}
            ${field.help ? `<div class="form-help">${field.help}</div>` : ''}
        </div>`;
    }
}

function updateConfigValue(section, key, value) {
    if (!configData[section]) {
        configData[section] = {};
    }
    configData[section][key] = value;
}

function updatePluginConfigValue(pluginName, key, value) {
    if (!configData.plugins) {
        configData.plugins = {};
    }
    if (!configData.plugins[pluginName]) {
        configData.plugins[pluginName] = {};
    }
    configData.plugins[pluginName][key] = value;
}

async function togglePlugin(pluginName, enable) {
    try {
        const action = enable ? 'enable' : 'disable';
        const response = await fetch(`/api/config/plugins/${pluginName}/${action}`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.success) {
            showAlert(result.message, 'success');
            // Reload plugins tab
            if (currentConfigTab === 'plugins') {
                loadConfigTab('plugins');
            }
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert(`Error ${enable ? 'enabling' : 'disabling'} plugin: ${error.message}`, 'error');
    }
}

async function reloadPlugin(pluginName) {
    try {
        const response = await fetch(`/api/config/plugins/${pluginName}/reload`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.success) {
            showAlert(result.message, 'success');
            // Reload plugins tab
            if (currentConfigTab === 'plugins') {
                loadConfigTab('plugins');
            }
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert(`Error reloading plugin: ${error.message}`, 'error');
    }
}

async function saveConfig() {
    try {
        const promises = [];
        
        // Save app config
        for (const [section, sectionData] of Object.entries(configData)) {
            if (section === 'plugins') continue;
            
            for (const [key, value] of Object.entries(sectionData)) {
                promises.push(
                    fetch('/api/config/app', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ section, key, value })
                    })
                );
            }
        }
        
        // Save plugin configs
        if (configData.plugins) {
            for (const [pluginName, pluginConfig] of Object.entries(configData.plugins)) {
                promises.push(
                    fetch(`/api/config/plugins/${pluginName}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ config: pluginConfig })
                    })
                );
            }
        }
        
        await Promise.all(promises);
        
        showAlert('Configuration saved successfully', 'success');
        configData = {}; // Clear pending changes
        closeConfigModal();
        
    } catch (error) {
        showAlert(`Error saving configuration: ${error.message}`, 'error');
    }
}

async function resetConfig() {
    if (!confirm('Reset all settings to defaults? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/config/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ section: null })
        });
        const result = await response.json();
        
        if (result.success) {
            showAlert('Configuration reset to defaults', 'success');
            configData = {};
            loadConfigTab(currentConfigTab);
        } else {
            showAlert('Failed to reset configuration', 'error');
        }
    } catch (error) {
        showAlert(`Error resetting configuration: ${error.message}`, 'error');
    }
}

// Console functions
function addConsoleMessage(message, type = '') {
    const timestamp = new Date().toLocaleTimeString();
    const line = `[${timestamp}] ${message}`;
    consoleLines.push({text: line, type: type});
    
    // Keep only last 50 messages
    if (consoleLines.length > 50) {
        consoleLines.shift();
    }
    
    updateConsole();
}

function updateConsole() {
    const consoleArea = document.getElementById('consoleArea');
    consoleArea.innerHTML = consoleLines.map(line => 
        `<div class="console-line ${line.type}">${line.text}</div>`
    ).join('');
    consoleArea.scrollTop = consoleArea.scrollHeight;
}

// File upload setup
function setupUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    uploadArea.onclick = () => fileInput.click();
    
    uploadArea.ondragover = (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    };
    
    uploadArea.ondragleave = () => {
        uploadArea.classList.remove('dragover');
    };
    
    uploadArea.ondrop = (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        uploadFiles(e.dataTransfer.files);
    };
    
    fileInput.onchange = (e) => uploadFiles(e.target.files);
}

// Upload files
async function uploadFiles(files) {
    const formData = new FormData();
    for (let file of files) {
        formData.append('files', file);
    }

    try {
        showAlert('Uploading...', 'warning');
        addConsoleMessage(`Uploading ${files.length} file(s)...`);
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (result.success) {
            showAlert(`Uploaded ${result.total_uploaded} files successfully`, 'success');
            addConsoleMessage(`Successfully uploaded ${result.total_uploaded} file(s)`, 'success');
            
            if (result.total_errors > 0) {
                addConsoleMessage(`${result.total_errors} file(s) failed to upload`, 'warning');
            }
            
            updateFiles();
        } else {
            showAlert('Upload failed', 'error');
            addConsoleMessage('Upload failed', 'error');
        }
    } catch (error) {
        showAlert(`Upload error: ${error.message}`, 'error');
        addConsoleMessage(`Upload error: ${error.message}`, 'error');
    }
}

// Update status
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();

        // Connection
        const connEl = document.getElementById('connectionStatus');
        if (status.connected) {
            connEl.textContent = 'Connected';
            connEl.className = 'status-value status-connected';
        } else {
            connEl.textContent = 'Disconnected';
            connEl.className = 'status-value status-disconnected';
        }

        // Print status
        const printEl = document.getElementById('printStatus');
        printEl.textContent = status.print_status.state;
        if (status.print_status.state === 'PRINTING') {
            printEl.className = 'status-value status-printing';
            showPrintingView(status);
        } else if (status.print_status.state === 'PAUSED') {
            printEl.className = 'status-value status-warning';
            showPrintingView(status);
        } else {
            printEl.className = 'status-value';
            if (status.print_status.state === 'IDLE') {
                hidePrintingView();
            }
        }

        // Progress
        const progress = status.print_status.progress_percent;
        document.getElementById('progressStatus').textContent = `${progress.toFixed(1)}%`;
        document.getElementById('progressBar').style.width = `${progress}%`;

        // Z position
        document.getElementById('zPosition').textContent = `${status.z_position.toFixed(2)} mm`;

        // Update buttons
        updateButtons(status);

        // Update printing overlay if visible
        updatePrintingOverlay(status);

    } catch (error) {
        console.error('Status error:', error);
    }
}

// Update button states
function updateButtons(status) {
    const connected = status.connected;
    const printing = status.print_status.state === 'PRINTING';
    const paused = status.print_status.state === 'PAUSED';

    document.getElementById('connectBtn').disabled = connected;
    document.getElementById('disconnectBtn').disabled = !connected;
    document.getElementById('startBtn').disabled = !connected || printing || paused || !selectedFile;
    document.getElementById('pauseBtn').disabled = !connected || !printing;
    document.getElementById('resumeBtn').disabled = !connected || !paused;
    document.getElementById('stopBtn').disabled = !connected || (!printing && !paused);
}

// Update file list
async function updateFiles() {
    try {
        const response = await fetch('/api/files');
        const files = await response.json();
        const fileList = document.getElementById('fileList');
        
        if (files.length === 0) {
            fileList.innerHTML = '<div class="empty-state">No files found</div>';
            return;
        }

        fileList.innerHTML = files.map(file => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name">${file.name}</div>
                    <div class="file-meta">${formatSize(file.size)} • ${file.modified}</div>
                </div>
                <div class="file-actions">
                    <button class="btn file-btn" onclick="selectFile('${file.name}')">📋 Select</button>
                    <button class="btn btn-success file-btn" onclick="printFile('${file.name}')">🖨 Print</button>
                    <button class="btn btn-danger file-btn" onclick="deleteFile('${file.name}')">🗑 Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        document.getElementById('fileList').innerHTML = '<div class="empty-state">Error loading files</div>';
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Storage statistics
async function showStorageStats() {
    try {
        const response = await fetch('/api/storage_stats');
        const stats = await response.json();
        
        if (stats.total_files !== undefined) {
            document.getElementById('totalFiles').textContent = stats.total_files;
            document.getElementById('totalSize').textContent = formatSize(stats.total_file_size);
            
            const storageStats = document.getElementById('storageStats');
            storageStats.style.display = storageStats.style.display === 'none' ? 'block' : 'none';
            
            addConsoleMessage(`Storage: ${stats.total_files} files, ${formatSize(stats.total_file_size)}`, 'info');
        }
    } catch (error) {
        addConsoleMessage(`Failed to get storage stats: ${error.message}`, 'error');
    }
}

// Cleanup files
async function cleanupFiles() {
    if (!confirm('Clean up old files? This will remove files older than 30 days or excess files beyond 50.')) {
        return;
    }

    try {
        addConsoleMessage('Starting file cleanup...');
        const response = await fetch('/api/cleanup_files', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_files: 50, max_age_days: 30 })
        });
        const result = await response.json();
        
        if (result.success) {
            showAlert(`Cleanup completed: ${result.deleted_count} files removed`, 'success');
            addConsoleMessage(result.message, 'success');
            updateFiles();
        } else {
            showAlert('Cleanup failed', 'error');
            addConsoleMessage(`Cleanup failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showAlert(`Cleanup error: ${error.message}`, 'error');
        addConsoleMessage(`Cleanup error: ${error.message}`, 'error');
    }
}

// Printer actions
async function connectPrinter() {
    addConsoleMessage('Attempting to connect to printer...');
    const response = await fetch('/api/connect', { method: 'POST' });
    const result = await response.json();
    const message = result.message || (result.success ? 'Connected' : result.error);
    showAlert(message, result.success ? 'success' : 'error');
    addConsoleMessage(message, result.success ? 'success' : 'error');
}

async function disconnectPrinter() {
    addConsoleMessage('Disconnecting from printer...');
    const response = await fetch('/api/disconnect', { method: 'POST' });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function selectFile(filename) {
    addConsoleMessage(`Selecting file: ${filename}`);
    const response = await fetch('/api/select_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
    });
    const result = await response.json();
    if (result.success) {
        selectedFile = filename;
        showAlert(`Selected: ${filename}`, 'success');
        addConsoleMessage(`File selected: ${filename}`, 'success');
    } else {
        showAlert(result.error, 'error');
        addConsoleMessage(`Failed to select file: ${result.error}`, 'error');
    }
}

async function printFile(filename) {
    addConsoleMessage(`Starting print: ${filename}`);
    const response = await fetch('/api/print_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
    });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function startPrint() {
    if (!selectedFile) {
        showAlert('No file selected', 'warning');
        addConsoleMessage('Cannot start print - no file selected', 'warning');
        return;
    }
    await printFile(selectedFile);
}

async function pausePrint() {
    addConsoleMessage('Pausing print...');
    const response = await fetch('/api/pause', { method: 'POST' });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function resumePrint() {
    addConsoleMessage('Resuming print...');
    const response = await fetch('/api/resume', { method: 'POST' });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function stopPrint() {
    if (!confirm('Stop current print?')) return;
    addConsoleMessage('Stopping print...');
    const response = await fetch('/api/stop', { method: 'POST' });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function homeZ() {
    addConsoleMessage('Homing Z axis...');
    const response = await fetch('/api/home_z', { method: 'POST' });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function moveZ(distance) {
    addConsoleMessage(`Moving Z axis ${distance}mm...`);
    const response = await fetch('/api/move_z', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ distance })
    });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function recoverUSB() {
    addConsoleMessage('Starting USB error recovery...');
    const response = await fetch('/api/recover_usb_error', { method: 'POST' });
    const result = await response.json();
    showAlert(result.message, result.success ? 'success' : 'error');
    addConsoleMessage(result.message, result.success ? 'success' : 'error');
}

async function deleteFile(filename) {
    if (!confirm(`Delete ${filename}?`)) return;
    addConsoleMessage(`Deleting file: ${filename}`);
    const response = await fetch('/api/delete_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
    });
    const result = await response.json();
    if (result.success) {
        updateFiles();
        showAlert('File deleted', 'success');
        addConsoleMessage(`File deleted: ${filename}`, 'success');
    } else {
        showAlert(result.error, 'error');
        addConsoleMessage(`Failed to delete file: ${result.error}`, 'error');
    }
}

function refreshFiles() {
    addConsoleMessage('Refreshing file list...');
    updateFiles();
}

// USB functions
async function checkUSB() {
    try {
        const response = await fetch('/api/usb_status');
        const status = await response.json();

        const serviceEl = document.getElementById('usbService');
        const mountEl = document.getElementById('usbMount');
        const spaceEl = document.getElementById('usbSpace');

        // Service status with color
        if (status.service_running) {
            serviceEl.textContent = 'Running';
            serviceEl.className = 'usb-value status-connected';
        } else {
            serviceEl.textContent = 'Stopped';
            serviceEl.className = 'usb-value status-disconnected';
        }

        // Mount status with color
        if (status.mounted) {
            mountEl.textContent = 'Mounted';
            mountEl.className = 'usb-value status-connected';
        } else {
            mountEl.textContent = 'Not Mounted';
            mountEl.className = 'usb-value status-disconnected';
        }
        
        // Free space
        if (status.usb_space && status.usb_space.free) {
            const freeGB = (status.usb_space.free / (1024 * 1024 * 1024)).toFixed(1);
            spaceEl.textContent = `${freeGB} GB`;
            spaceEl.className = 'usb-value';
        } else {
            spaceEl.textContent = 'Unknown';
            spaceEl.className = 'usb-value';
        }
    } catch (error) {
        console.error('USB status error:', error);
    }
}

// Printing view functions
function showPrintingView(status) {
    const overlay = document.getElementById('printingOverlay');
    if (!overlay.classList.contains('active')) {
        overlay.classList.add('active');
        if (status.print_status.state === 'PRINTING' && !printStartTime) {
            printStartTime = Date.now();
        }
    }
}

function hidePrintingView() {
    const overlay = document.getElementById('printingOverlay');
    overlay.classList.remove('active');
    printStartTime = null;
}

function closePrintingView() {
    hidePrintingView();
}

function updatePrintingOverlay(status) {
    if (!document.getElementById('printingOverlay').classList.contains('active')) return;

    // File name
    const fileName = status.selected_file || selectedFile || 'Unknown File';
    document.getElementById('printingFileName').textContent = fileName;

    // Layer info
    const progress = status.print_status.progress_percent;
    const estimatedLayers = Math.max(1, Math.round(status.print_status.total_bytes / 10000));
    const currentLayer = Math.round((progress / 100) * estimatedLayers);
    document.getElementById('printingLayerInfo').textContent = `Layer ${currentLayer} of ${estimatedLayers}`;

    // Progress
    document.getElementById('printingProgress').textContent = `${progress.toFixed(0)}%`;

    // Z Position
    document.getElementById('printingZPos').textContent = `${status.z_position.toFixed(2)}`;

    // Time left (estimated)
    if (printStartTime && progress > 1) {
        const elapsed = (Date.now() - printStartTime) / 1000;
        const totalEstimated = (elapsed / progress) * 100;
        const remaining = Math.max(0, totalEstimated - elapsed);
        document.getElementById('printingTimeLeft').textContent = formatTime(remaining);
    } else {
        document.getElementById('printingTimeLeft').textContent = '--';
    }

    // Data progress
    document.getElementById('printingBytes').textContent = `${progress.toFixed(0)}%`;
}

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes}m`;
    }
}

// Show alerts
function showAlert(message, type) {
    const alertArea = document.getElementById('alertArea');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alertArea.appendChild(alert);
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 4000);
}

// Cleanup
window.addEventListener('beforeunload', () => {
    if (updateInterval) clearInterval(updateInterval);
});