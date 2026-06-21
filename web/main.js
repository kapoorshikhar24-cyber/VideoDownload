/* --------------------------------------------------
   Antigravity Video Downloader Bridge Script (main.js)
   Integrates frontend DOM with exposed Python Eel methods
   -------------------------------------------------- */

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

let ffmpegAvailable = false;
let currentPlaylistInfo = null;
let isDownloadPaused = false;

// Application Initialization
function initApp() {
    setupTabNavigation();
    setupDropdownSync();
    setupEventHandlers();
    
    // Call Python to get initial application states
    loadAppStates();
}

// 1. Tab Navigation Routing
function setupTabNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    const panels = document.querySelectorAll('.tab-panel');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.getAttribute('data-tab');
            
            // Toggle tabs
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Toggle panels
            panels.forEach(p => p.classList.remove('active'));
            document.getElementById(`tab-${targetTab}`).classList.add('active');
            
            // Custom actions when switching tabs
            if (targetTab === 'history') {
                eel.get_history()(renderHistory);
            }
        });
    });
}

// 2. Dropdown Sync (Format Type Selector Options)
function setupDropdownSync() {
    // Single Format Options
    const singleFormatRadios = document.querySelectorAll('input[name="single-format"]');
    singleFormatRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            updateFormatSettings('single', radio.value);
        });
    });

    // Playlist Format Options
    const playlistFormatRadios = document.querySelectorAll('input[name="playlist-format"]');
    playlistFormatRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            updateFormatSettings('playlist', radio.value);
        });
    });
}

function updateFormatSettings(prefix, formatType) {
    const qualityLabel = document.getElementById(`lbl-${prefix}-quality`);
    const qualitySelect = document.getElementById(`${prefix}-quality`);
    const extSelect = document.getElementById(`${prefix}-ext`);

    // Reset dropdown values
    qualitySelect.innerHTML = '';
    extSelect.innerHTML = '';

    if (formatType === 'audio') {
        qualityLabel.textContent = 'Audio Quality';
        
        // Quality choices
        const qualities = [
            { text: 'Best (320kbps)', val: 'Best (320kbps)' },
            { text: 'Medium (192kbps)', val: 'Medium (192kbps)' },
            { text: 'Low (128kbps)', val: 'Low (128kbps)' }
        ];
        qualities.forEach(q => {
            const opt = document.createElement('option');
            opt.value = q.val;
            opt.textContent = q.text;
            qualitySelect.appendChild(opt);
        });
        qualitySelect.value = 'Medium (192kbps)';

        // Ext choices
        const extensions = ['mp3', 'm4a', 'wav', 'flac'];
        extensions.forEach(ext => {
            const opt = document.createElement('option');
            opt.value = ext;
            opt.textContent = ext;
            extSelect.appendChild(opt);
        });
        extSelect.value = 'mp3';
    } else {
        qualityLabel.textContent = 'Quality / Resolution';

        // Quality choices
        const qualities = ['Best Quality', '1080p', '720p', '480p', '360p'];
        qualities.forEach(q => {
            const opt = document.createElement('option');
            opt.value = q;
            opt.textContent = q;
            qualitySelect.appendChild(opt);
        });
        qualitySelect.value = 'Best Quality';

        // Ext choices
        const extensions = ['mp4', 'mkv', 'webm', 'avi', 'flv', 'mov'];
        extensions.forEach(ext => {
            const opt = document.createElement('option');
            opt.value = ext;
            opt.textContent = ext;
            extSelect.appendChild(opt);
        });
        extSelect.value = 'mp4';
    }
}

// 3. Application State Fetch
function loadAppStates() {
    updateStatus('Connecting to server...', 'blue');
    
    // Get FFmpeg status
    eel.check_ffmpeg_status()((available) => {
        ffmpegAvailable = available;
        const badge = document.getElementById('ffmpeg-badge');
        if (available) {
            badge.className = 'ffmpeg-status';
            badge.innerHTML = '<i class="fa-solid fa-circle-check"></i><span>FFmpeg Loaded</span>';
            
            // Enable advanced settings
            document.getElementById('single-embed-metadata').disabled = false;
            document.getElementById('single-embed-thumbnail').disabled = false;
            document.getElementById('playlist-embed-metadata').disabled = false;
            document.getElementById('playlist-embed-thumbnail').disabled = false;
        } else {
            badge.className = 'ffmpeg-status warning';
            badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i><span>FFmpeg Missing</span>';
            
            // Disable and uncheck settings requiring FFmpeg
            const chkMeta = document.getElementById('single-embed-metadata');
            const chkThumb = document.getElementById('single-embed-thumbnail');
            const chkMetaP = document.getElementById('playlist-embed-metadata');
            const chkThumbP = document.getElementById('playlist-embed-thumbnail');
            
            chkMeta.checked = false; chkMeta.disabled = true;
            chkThumb.checked = false; chkThumb.disabled = true;
            chkMetaP.checked = false; chkMetaP.disabled = true;
            chkThumbP.checked = false; chkThumbP.disabled = true;
        }
    });

    // Get default download directory path
    eel.get_default_dir()((dir) => {
        document.getElementById('single-dest').value = dir;
        document.getElementById('playlist-dest').value = dir;
    });

    // Load history
    eel.get_history()(renderHistory);
    
    updateStatus('System Ready', 'green');
}

// Helper: formats seconds to HH:MM:SS
function formatDuration(sec) {
    if (!sec) return '00:00';
    let hours = Math.floor(sec / 3600);
    let minutes = Math.floor((sec - (hours * 3600)) / 60);
    let seconds = sec - (hours * 3600) - (minutes * 60);
    
    let parts = [];
    if (hours > 0) parts.push(hours.toString().padStart(2, '0'));
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(seconds.toString().padStart(2, '0'));
    return parts.join(':');
}

// 4. UI Rendering Functions
function renderHistory(history) {
    const container = document.getElementById('history-list-container');
    const placeholder = document.getElementById('history-placeholder');
    
    container.innerHTML = '';
    
    if (!history || history.length === 0) {
        placeholder.classList.remove('hidden');
        container.classList.add('hidden');
        return;
    }

    placeholder.classList.add('hidden');
    container.classList.remove('hidden');

    history.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'card glass-card history-item-card';
        
        const isAudio = item.format.includes('Audio') || item.format.includes('MP3');
        const badgeClass = isAudio ? 'badge-audio' : 'badge-video';
        const badgeText = isAudio ? 'AUDIO' : 'VIDEO';
        
        card.innerHTML = `
            <div class="history-badge ${badgeClass}">${badgeText}</div>
            <div class="history-details">
                <h4 title="${item.title}">${item.title}</h4>
                <p>Format: ${item.format} | Size: ${item.size} | Downloaded: ${item.timestamp}</p>
            </div>
            <div class="history-actions">
                <button class="btn btn-primary btn-small btn-play" data-path="${item.path}">
                    <i class="fa-solid fa-play"></i> Play
                </button>
                <button class="btn btn-secondary btn-small btn-folder" data-path="${item.path}">
                    <i class="fa-solid fa-folder"></i> Folder
                </button>
                <button class="btn btn-secondary btn-small btn-remove" data-index="${index}">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `;
        container.appendChild(card);
    });

    // Attach listeners
    container.querySelectorAll('.btn-play').forEach(btn => {
        btn.addEventListener('click', () => {
            eel.play_file(btn.getAttribute('data-path'))((res) => {
                if (res !== true) showDialog('Error Playing File', res);
            });
        });
    });

    container.querySelectorAll('.btn-folder').forEach(btn => {
        btn.addEventListener('click', () => {
            eel.open_folder(btn.getAttribute('data-path'))((res) => {
                if (res !== true) showDialog('Error Opening Folder', res);
            });
        });
    });

    container.querySelectorAll('.btn-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.getAttribute('data-index'), 10);
            eel.remove_history_item(index)(renderHistory);
        });
    });
}

function renderPlaylist(info) {
    currentPlaylistInfo = info;
    
    document.getElementById('playlist-placeholder').classList.add('hidden');
    const container = document.getElementById('playlist-details-container');
    container.classList.remove('hidden');
    
    document.getElementById('playlist-title').textContent = info.title || 'Playlist';
    document.getElementById('playlist-count').textContent = `${info.entries.length} Videos Found`;
    
    const itemsList = document.getElementById('playlist-items-list');
    itemsList.innerHTML = '';

    info.entries.forEach((entry, idx) => {
        const row = document.createElement('div');
        row.className = 'playlist-item-row';
        
        const title = entry.title || 'Unknown Title';
        const duration = formatDuration(entry.duration);
        const channel = entry.uploader || entry.channel || 'Unknown Channel';
        
        row.innerHTML = `
            <label class="checkbox-label">
                <input type="checkbox" class="playlist-item-check" data-index="${idx}" checked>
                <span>${idx + 1}. ${title}</span>
            </label>
            <div class="item-meta">${channel} | ${duration}</div>
        `;
        itemsList.appendChild(row);
    });
}

function renderSearchResults(entries) {
    document.getElementById('search-loader').classList.add('hidden');
    const container = document.getElementById('search-results-container');
    const placeholder = document.getElementById('search-placeholder');
    
    container.innerHTML = '';
    
    if (!entries || entries.length === 0) {
        placeholder.classList.remove('hidden');
        placeholder.innerHTML = '<i class="fa-solid fa-circle-exclamation placeholder-icon"></i><p>No results found. Try a different query.</p>';
        container.classList.add('hidden');
        return;
    }

    placeholder.classList.add('hidden');
    container.classList.remove('hidden');

    entries.forEach(entry => {
        const item = document.createElement('div');
        item.className = 'card glass-card search-item-card';
        
        const thumbUrl = entry.thumbnail || 'https://via.placeholder.com/130x73?text=No+Thumb';
        const title = entry.title || 'Unknown Title';
        const channel = entry.uploader || entry.channel || 'Unknown Channel';
        const duration = formatDuration(entry.duration);
        const views = entry.view_count ? `${entry.view_count.toLocaleString()} views` : 'Views N/A';
        const loadUrl = `https://www.youtube.com/watch?v=${entry.id}`;

        item.innerHTML = `
            <div class="search-thumbnail">
                <img src="${thumbUrl}" alt="Thumbnail">
                <span class="duration-badge">${duration}</span>
            </div>
            <div class="search-meta">
                <h4 title="${title}">${title}</h4>
                <div class="channel-info">${channel}</div>
                <div class="meta-stats">${views}</div>
            </div>
            <button class="btn btn-primary btn-search-load" data-url="${loadUrl}">
                Load Video
            </button>
        `;
        container.appendChild(item);
    });

    // Attach listeners to search buttons
    container.querySelectorAll('.btn-search-load').forEach(btn => {
        btn.addEventListener('click', () => {
            const url = btn.getAttribute('data-url');
            loadVideoToSingleDownloader(url);
        });
    });
}

function loadVideoToSingleDownloader(url) {
    document.getElementById('single-url').value = url;
    // Switch to Single Tab
    const singleTabBtn = document.querySelector('.nav-tab[data-tab="single"]');
    singleTabBtn.click();
    // Start Analysis automatically
    triggerSingleAnalysis();
}

// 5. Event Listeners Setup
function setupEventHandlers() {
    // Paste buttons
    document.getElementById('btn-single-paste').addEventListener('click', () => {
        eel.get_clipboard_text()((text) => {
            if (text) document.getElementById('single-url').value = text;
        });
    });
    
    document.getElementById('btn-playlist-paste').addEventListener('click', () => {
        eel.get_clipboard_text()((text) => {
            if (text) document.getElementById('playlist-url').value = text;
        });
    });

    // Directory Browse Buttons
    document.getElementById('btn-single-browse').addEventListener('click', () => {
        const current = document.getElementById('single-dest').value;
        eel.browse_dir(current)((selected) => {
            if (selected) {
                document.getElementById('single-dest').value = selected;
                document.getElementById('playlist-dest').value = selected; // Sync
            }
        });
    });

    document.getElementById('btn-playlist-browse').addEventListener('click', () => {
        const current = document.getElementById('playlist-dest').value;
        eel.browse_dir(current)((selected) => {
            if (selected) {
                document.getElementById('single-dest').value = selected;
                document.getElementById('playlist-dest').value = selected; // Sync
            }
        });
    });

    // Single Analysis & Download
    document.getElementById('btn-single-analyze').addEventListener('click', triggerSingleAnalysis);
    document.getElementById('btn-single-download').addEventListener('click', startSingleDownload);
    document.getElementById('btn-single-cancel').addEventListener('click', cancelActiveDownload);
    document.getElementById('btn-single-pause').addEventListener('click', togglePauseDownload);

    // Playlist Analysis & Download
    document.getElementById('btn-playlist-analyze').addEventListener('click', triggerPlaylistAnalysis);
    document.getElementById('btn-playlist-download').addEventListener('click', startPlaylistDownload);
    document.getElementById('btn-playlist-cancel').addEventListener('click', cancelActiveDownload);
    document.getElementById('btn-playlist-pause').addEventListener('click', togglePauseDownload);
    
    // Select all/none in playlist checklist
    document.getElementById('btn-playlist-select-all').addEventListener('click', () => {
        document.querySelectorAll('.playlist-item-check').forEach(chk => chk.checked = true);
    });
    document.getElementById('btn-playlist-select-none').addEventListener('click', () => {
        document.querySelectorAll('.playlist-item-check').forEach(chk => chk.checked = false);
    });

    // YouTube Search
    document.getElementById('btn-search-trigger').addEventListener('click', triggerSearch);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') triggerSearch();
    });

    // Clear History Button
    document.getElementById('btn-clear-history').addEventListener('click', () => {
        if (confirm('Are you sure you want to clear your download library history? This won\'t delete physical files.')) {
            eel.clear_history()(renderHistory);
        }
    });

    // Dialog overlays close
    document.getElementById('dialog-close').addEventListener('click', hideDialog);
    document.getElementById('btn-dialog-ok').addEventListener('click', hideDialog);
}

// Trigger Single URL Metadata extraction
function triggerSingleAnalysis() {
    const url = document.getElementById('single-url').value.trim();
    if (!url) {
        showDialog('Input Required', 'Please enter or paste a valid video URL first.');
        return;
    }

    // Reset layout
    document.getElementById('single-details-container').classList.add('hidden');
    document.getElementById('single-progress-card').classList.add('hidden');
    document.getElementById('single-placeholder').innerHTML = '<i class="fa-solid fa-spinner fa-spin placeholder-icon spinner-accent"></i><p>Analyzing link details from YouTube...</p>';
    document.getElementById('single-placeholder').classList.remove('hidden');
    
    disableInputRow('single', true);
    updateStatus('Connecting to YouTube and extracting info...', 'blue');
    
    // Call Python background thread
    eel.analyze_url(url);
}

// Start Single Download process
function startSingleDownload() {
    const url = document.getElementById('single-url').value.trim();
    const dest = document.getElementById('single-dest').value.trim();
    const formatType = document.querySelector('input[name="single-format"]:checked').value;
    const quality = document.getElementById('single-quality').value;
    const ext = document.getElementById('single-ext').value;
    
    // Checkboxes
    const embedMetadata = document.getElementById('single-embed-metadata').checked;
    const embedThumbnail = document.getElementById('single-embed-thumbnail').checked;
    const downloadSubtitles = document.getElementById('single-download-subtitles').checked;
    const saveThumbnail = document.getElementById('single-save-thumbnail').checked;

    if (!dest) {
        showDialog('Invalid Path', 'Please select a valid folder save location.');
        return;
    }

    // Hide configurations, display progress bar
    document.getElementById('single-details-container').classList.add('hidden');
    const pCard = document.getElementById('single-progress-card');
    pCard.classList.remove('hidden');

    // Reset progress values
    document.getElementById('single-progress-bar').style.width = '0%';
    document.getElementById('single-progress-percent').textContent = '0%';
    document.getElementById('single-progress-speed').textContent = 'Starting...';
    document.getElementById('single-progress-eta').textContent = 'Calculating...';
    document.getElementById('single-progress-size').textContent = '-- / --';
    document.getElementById('single-progress-status').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Initializing Download...';
    
    isDownloadPaused = false;
    document.getElementById('btn-single-pause').innerHTML = '<i class="fa-solid fa-pause"></i> Pause Download';

    disableInputRow('single', true);
    updateStatus('Launching downloader...', 'blue');

    // Call Python
    eel.download_single(
        url, dest, formatType, quality, ext, 
        embedMetadata, embedThumbnail, saveThumbnail, downloadSubtitles
    );
}

// Trigger Playlist URL analysis
function triggerPlaylistAnalysis() {
    const url = document.getElementById('playlist-url').value.trim();
    if (!url) {
        showDialog('Input Required', 'Please enter a valid YouTube Playlist URL.');
        return;
    }

    // Reset layout
    document.getElementById('playlist-details-container').classList.add('hidden');
    document.getElementById('playlist-progress-card').classList.add('hidden');
    document.getElementById('playlist-placeholder').innerHTML = '<i class="fa-solid fa-spinner fa-spin placeholder-icon spinner-accent"></i><p>Parsing playlist entries...</p>';
    document.getElementById('playlist-placeholder').classList.remove('hidden');
    
    disableInputRow('playlist', true);
    updateStatus('Analyzing playlist database...', 'blue');
    
    // Call Python
    eel.analyze_playlist(url);
}

// Start Playlist Batch Download process
function startPlaylistDownload() {
    if (!currentPlaylistInfo) return;

    // Get checked indices
    const checkedBoxes = document.querySelectorAll('.playlist-item-check:checked');
    if (checkedBoxes.length === 0) {
        showDialog('Selection Required', 'Please check at least one video checkbox to download.');
        return;
    }

    const checkedEntries = [];
    checkedBoxes.forEach(chk => {
        const idx = parseInt(chk.getAttribute('data-index'), 10);
        checkedEntries.push(currentPlaylistInfo.entries[idx]);
    });

    const dest = document.getElementById('playlist-dest').value.trim();
    const formatType = document.querySelector('input[name="playlist-format"]:checked').value;
    const quality = document.getElementById('playlist-quality').value;
    const ext = document.getElementById('playlist-ext').value;
    
    // Checkboxes
    const embedMetadata = document.getElementById('playlist-embed-metadata').checked;
    const embedThumbnail = document.getElementById('playlist-embed-thumbnail').checked;
    const downloadSubtitles = document.getElementById('playlist-download-subtitles').checked;
    const saveThumbnail = document.getElementById('playlist-save-thumbnail').checked;

    if (!dest) {
        showDialog('Invalid Path', 'Please select a valid folder save location.');
        return;
    }

    // Hide playlist details and options
    document.getElementById('playlist-details-container').classList.add('hidden');
    const pCard = document.getElementById('playlist-progress-card');
    pCard.classList.remove('hidden');

    // Reset progress values
    document.getElementById('playlist-progress-overall').textContent = `Downloading video 1 of ${checkedEntries.length}...`;
    document.getElementById('playlist-progress-status').textContent = 'Loading...';
    document.getElementById('playlist-progress-bar').style.width = '0%';
    document.getElementById('playlist-progress-percent').textContent = '0%';
    document.getElementById('playlist-progress-speed').textContent = 'Starting...';
    document.getElementById('playlist-progress-eta').textContent = 'Calculating...';
    document.getElementById('playlist-progress-size').textContent = '-- / --';
    
    isDownloadPaused = false;
    document.getElementById('btn-playlist-pause').innerHTML = '<i class="fa-solid fa-pause"></i> Pause Batch Download';

    disableInputRow('playlist', true);
    updateStatus('Launching playlist downloader...', 'blue');

    // Call Python
    eel.download_playlist(
        checkedEntries, dest, formatType, quality, ext, 
        embedMetadata, embedThumbnail, saveThumbnail, downloadSubtitles
    );
}

// Cancel Active Download process
function cancelActiveDownload() {
    if (confirm('Are you sure you want to cancel the active download?')) {
        updateStatus('Cancelling download...', 'red');
        eel.cancel_download();
    }
}

// Toggle Pause/Resume for Active Download
function togglePauseDownload() {
    isDownloadPaused = !isDownloadPaused;
    const btnSinglePause = document.getElementById('btn-single-pause');
    const btnPlaylistPause = document.getElementById('btn-playlist-pause');
    
    if (isDownloadPaused) {
        updateStatus('Download paused...', 'orange');
        eel.pause_download();
        if (btnSinglePause) btnSinglePause.innerHTML = '<i class="fa-solid fa-play"></i> Resume Download';
        if (btnPlaylistPause) btnPlaylistPause.innerHTML = '<i class="fa-solid fa-play"></i> Resume Batch Download';
    } else {
        updateStatus('Resuming download...', 'blue');
        eel.resume_download();
        if (btnSinglePause) btnSinglePause.innerHTML = '<i class="fa-solid fa-pause"></i> Pause Download';
        if (btnPlaylistPause) btnPlaylistPause.innerHTML = '<i class="fa-solid fa-pause"></i> Pause Batch Download';
    }
}

// Trigger YouTube Search
function triggerSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    document.getElementById('search-placeholder').classList.add('hidden');
    document.getElementById('search-results-container').classList.add('hidden');
    document.getElementById('search-loader').classList.remove('hidden');

    document.getElementById('btn-search-trigger').disabled = true;
    updateStatus(`Searching YouTube for "${query}"...`, 'blue');

    // Call Python
    eel.search_youtube(query);
}

// Helper: disable/enable input controls
function disableInputRow(prefix, state) {
    document.getElementById(`${prefix}-url`).disabled = state;
    document.getElementById(`btn-${prefix}-paste`).disabled = state;
    document.getElementById(`btn-${prefix}-analyze`).disabled = state;
}

// Helper: Status Indicator update
function updateStatus(text, color) {
    document.getElementById('status-text').textContent = text;
    const dot = document.getElementById('status-dot');
    
    // Remove all color classes
    dot.className = 'status-dot';
    
    if (color === 'green') {
        dot.classList.add('green');
    } else if (color === 'blue') {
        dot.classList.add('blue');
    } else if (color === 'yellow') {
        dot.classList.add('yellow');
    } else if (color === 'red') {
        dot.classList.add('red');
    }
}

// Custom Dialog / Popup
function showDialog(title, message) {
    document.getElementById('dialog-title').textContent = title;
    document.getElementById('dialog-message').textContent = message;
    document.getElementById('dialog-overlay').classList.remove('hidden');
}

function hideDialog() {
    document.getElementById('dialog-overlay').classList.add('hidden');
}


/* --------------------------------------------------
   EEL PYTHON-EXPOSED CALLBACKS (Eel.expose)
   -------------------------------------------------- */

// Single Download - Meta analysis completed successfully
eel.expose(on_fetch_success);
function on_fetch_success(info) {
    disableInputRow('single', false);
    document.getElementById('single-placeholder').classList.add('hidden');
    
    const container = document.getElementById('single-details-container');
    container.classList.remove('hidden');
    
    // Fill video elements
    document.getElementById('single-title').textContent = info.title || 'Unknown Title';
    document.getElementById('single-thumbnail').src = info.thumbnail || 'https://via.placeholder.com/180x101?text=No+Thumbnail';
    document.getElementById('single-badge').textContent = formatDuration(info.duration);
    
    const channel = info.uploader || 'Unknown Channel';
    const views = info.view_count ? `${info.view_count.toLocaleString()} views` : 'Views N/A';
    document.getElementById('single-channel').innerHTML = `<i class="fa-solid fa-user"></i> ${channel}`;
    document.getElementById('single-views').innerHTML = `<i class="fa-solid fa-eye"></i> ${views}`;
    
    // Reset layout formats dropdown options
    const singleFormat = document.querySelector('input[name="single-format"]:checked').value;
    updateFormatSettings('single', singleFormat);

    updateStatus('Video metadata loaded successfully!', 'green');
}

// Single Download - Meta analysis failed
eel.expose(on_fetch_failed);
function on_fetch_failed(error_message) {
    disableInputRow('single', false);
    document.getElementById('single-details-container').classList.add('hidden');
    
    const placeholder = document.getElementById('single-placeholder');
    placeholder.classList.remove('hidden');
    placeholder.innerHTML = '<i class="fa-solid fa-triangle-exclamation placeholder-icon spinner-accent"></i><p>Metadata analysis failed. Check URL or internet connection.</p>';
    
    showDialog('Analysis Failed', error_message);
    updateStatus('Metadata fetching failed.', 'red');
}

// Single Download - Progress updates hook
eel.expose(update_download_progress);
function update_download_progress(data) {
    const percent = data.percent.toFixed(1);
    document.getElementById('single-progress-bar').style.width = `${percent}%`;
    document.getElementById('single-progress-percent').textContent = `${percent}%`;
    
    document.getElementById('single-progress-speed').textContent = data.speed ? data.speed : '--';
    document.getElementById('single-progress-eta').textContent = data.eta ? data.eta : '--';
    document.getElementById('single-progress-size').textContent = `${data.downloaded} / ${data.total}`;
    
    document.getElementById('single-progress-status').innerHTML = `<i class="fa-solid fa-arrow-down fa-bounce"></i> Downloading stream: ${data.filename.substring(0, 40)}...`;
    updateStatus(`Downloading: ${percent}%`, 'blue');
}

// Single Download - Post processing step
eel.expose(on_postprocess_start);
function on_postprocess_start() {
    document.getElementById('single-progress-status').innerHTML = `<i class="fa-solid fa-compact-disc fa-spin"></i> Post-processing and merging video/audio channels...`;
    updateStatus('Post-processing...', 'yellow');
}

// Single Download - Complete callback
eel.expose(on_download_complete);
function on_download_complete(success, message, final_path) {
    disableInputRow('single', false);
    
    document.getElementById('single-progress-card').classList.add('hidden');
    document.getElementById('single-details-container').classList.remove('hidden');
    
    if (success) {
        updateStatus('Download completed!', 'green');
        showDialog('Download Success', `Your file has been saved successfully.\n\nLocation: ${final_path}`);
        eel.get_history()(renderHistory);
    } else {
        if (message.includes('cancelled')) {
            updateStatus('Download cancelled.', 'yellow');
            showDialog('Cancelled', 'The download has been cancelled by the user.');
        } else {
            updateStatus('Download failed.', 'red');
            showDialog('Download Error', `${message}\n\nTip: 1080p+ merging requires FFmpeg installed on your path.`);
        }
    }
}

// Playlist - Fetch completed successfully
eel.expose(on_playlist_fetch_success);
function on_playlist_fetch_success(info) {
    disableInputRow('playlist', false);
    renderPlaylist(info);
    
    // Sync format choices
    const playlistFormat = document.querySelector('input[name="playlist-format"]:checked').value;
    updateFormatSettings('playlist', playlistFormat);
    
    updateStatus('Playlist entries extracted successfully!', 'green');
}

// Playlist - Fetch failed
eel.expose(on_playlist_fetch_failed);
function on_playlist_fetch_failed(error_message) {
    disableInputRow('playlist', false);
    document.getElementById('playlist-details-container').classList.add('hidden');
    
    const placeholder = document.getElementById('playlist-placeholder');
    placeholder.classList.remove('hidden');
    placeholder.innerHTML = '<i class="fa-solid fa-triangle-exclamation placeholder-icon spinner-accent"></i><p>Failed to parse playlist entries.</p>';
    
    showDialog('Playlist Load Failed', error_message);
    updateStatus('Playlist load failed.', 'red');
}

// Playlist - Start item callback
eel.expose(on_playlist_item_start);
function on_playlist_item_start(index, total, title) {
    document.getElementById('playlist-progress-overall').textContent = `Downloading video ${index} of ${total}...`;
    document.getElementById('playlist-progress-status').textContent = `Video: ${title}`;
    
    // Reset bar for the new item
    document.getElementById('playlist-progress-bar').style.width = '0%';
    document.getElementById('playlist-progress-percent').textContent = '0%';
}

// Playlist - Item progress updates hook
eel.expose(update_playlist_progress);
function update_playlist_progress(data) {
    const percent = data.percent.toFixed(1);
    document.getElementById('playlist-progress-bar').style.width = `${percent}%`;
    document.getElementById('playlist-progress-percent').textContent = `${percent}%`;
    
    document.getElementById('playlist-progress-speed').textContent = data.speed ? data.speed : '--';
    document.getElementById('playlist-progress-eta').textContent = data.eta ? data.eta : '--';
    document.getElementById('playlist-progress-size').textContent = `${data.downloaded} / ${data.total}`;
    
    updateStatus(`Playlist batch: item ${percent}%`, 'blue');
}

// Playlist - Item post processing
eel.expose(on_playlist_postprocess_start);
function on_playlist_postprocess_start() {
    document.getElementById('playlist-progress-status').textContent = `Post-processing/merging video and audio tracks...`;
}

// Playlist - Complete callback
eel.expose(on_playlist_download_complete);
function on_playlist_download_complete(success, message) {
    disableInputRow('playlist', false);
    
    document.getElementById('playlist-progress-card').classList.add('hidden');
    document.getElementById('playlist-details-container').classList.remove('hidden');
    
    if (success) {
        updateStatus('Batch completed!', 'green');
        showDialog('Batch Completed', message);
        eel.get_history()(renderHistory);
    } else {
        updateStatus('Batch finished with errors or cancelled.', 'yellow');
        showDialog('Batch Status', message);
    }
}

// YouTube Search - Success callback
eel.expose(on_search_success);
function on_search_success(entries) {
    document.getElementById('btn-search-trigger').disabled = false;
    renderSearchResults(entries);
    updateStatus(`Found ${entries.length} search results.`, 'green');
}

// YouTube Search - Failed callback
eel.expose(on_search_failed);
function on_search_failed(error_message) {
    document.getElementById('btn-search-trigger').disabled = false;
    document.getElementById('search-loader').classList.add('hidden');
    
    const placeholder = document.getElementById('search-placeholder');
    placeholder.classList.remove('hidden');
    placeholder.innerHTML = '<i class="fa-solid fa-triangle-exclamation placeholder-icon spinner-accent"></i><p>Search request failed.</p>';
    
    showDialog('Search Failed', error_message);
    updateStatus('YouTube search failed.', 'red');
}
