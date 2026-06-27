// ============================================
// Arabic AI Education Assistant - Dashboard JS
// ============================================

(function() {
    'use strict';

    if (!window.fetch || window.__INTELLI_ARABIC_AUTH_FETCH__) return;

    var nativeFetch = window.fetch.bind(window);
    window.__INTELLI_ARABIC_AUTH_FETCH__ = true;

    function storedAuthToken() {
        try {
            return sessionStorage.getItem('authToken') || '';
        } catch (err) {
            return '';
        }
    }

    function authToken() {
        return window.AUTH_TOKEN || storedAuthToken();
    }

    window.getAuthToken = authToken;

    function isSameOrigin(input) {
        var rawUrl = typeof input === 'string' ? input : input && input.url;
        if (!rawUrl) return true;

        try {
            return new URL(rawUrl, window.location.origin).origin === window.location.origin;
        } catch (err) {
            return true;
        }
    }

    window.fetch = function(input, init) {
        var token = authToken();
        var options = init ? Object.assign({}, init) : {};

        if (token && isSameOrigin(input)) {
            var headers = new Headers(options.headers || (input && input.headers) || {});
            if (!headers.has('Authorization')) {
                headers.set('Authorization', 'Bearer ' + token);
            }
            if (!headers.has('X-Auth-Token')) {
                headers.set('X-Auth-Token', token);
            }
            options.headers = headers;
        }

        return nativeFetch(input, options);
    };
})();

function addAuthTokenToFormData(formData) {
    var token = window.getAuthToken ? window.getAuthToken() : (window.AUTH_TOKEN || '');
    if (token) {
        formData.set('auth_token', token);
    }
    return formData;
}

function clearClientAuthToken() {
    try {
        sessionStorage.removeItem('authToken');
    } catch (err) {
        // Embedded browsers may block storage access.
    }
    window.AUTH_TOKEN = '';
}

window.clearClientAuthToken = clearClientAuthToken;

(function() {
    'use strict';

    console.log('[Dashboard] Script loaded');

    // ---- PROFILE DROPDOWN ----
    var profileTrigger = document.getElementById('profileTrigger');
    var profileWrapper = document.querySelector('.profile-dropdown-wrapper');
    var profileDropdown = document.getElementById('profileDropdown');

    if (profileTrigger && profileWrapper) {
        function setProfileMenuOpen(isOpen) {
            profileWrapper.classList.toggle('open', isOpen);
            profileTrigger.setAttribute('aria-expanded', String(isOpen));
            if (profileDropdown) {
                profileDropdown.setAttribute('aria-hidden', String(!isOpen));
            }
        }

        window.closeProfileMenu = function() {
            setProfileMenuOpen(false);
        };

        profileTrigger.addEventListener('click', function(e) {
            e.stopPropagation();
            setProfileMenuOpen(!profileWrapper.classList.contains('open'));
        });

        document.addEventListener('click', function(e) {
            if (!profileWrapper.contains(e.target)) {
                setProfileMenuOpen(false);
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                setProfileMenuOpen(false);
                profileTrigger.blur();
            }
        });
        console.log('[Dashboard] Profile dropdown initialized');
    }

    // ---- LANGUAGE SWITCH ----
    var langSwitch = document.getElementById('langSwitch');
    var langLabel = document.getElementById('langLabel');
    var isArabic = false;

    if (langSwitch) {
        langSwitch.addEventListener('click', function() {
            isArabic = !isArabic;
            langLabel.textContent = isArabic ? 'EN' : '\u0639\u0631\u0628\u064A';
            document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
            document.documentElement.lang = isArabic ? 'ar' : 'en';
        });
        console.log('[Dashboard] Language switch initialized');
    }

    // ---- STATISTICS ----
    function loadStats() {
        fetch('/api/stats')
            .then(function(res) {
                if (!res.ok) throw new Error('Stats fetch failed: ' + res.status);
                return res.json();
            })
            .then(function(stats) {
                console.log('[Dashboard] Stats loaded:', stats);
                animateCounter('statImages', stats.images_processed || 0);
                animateCounter('statEvaluations', stats.answers_evaluated || 0);
                var val = stats.ai_accuracy || 0;
                animateCounterText('statAccuracy', val, '%');
            })
            .catch(function(err) {
                console.warn('[Dashboard] Failed to load stats:', err);
            });
    }

    function animateCounter(elementId, target) {
        var el = document.getElementById(elementId);
        if (!el) return;
        var duration = 800;
        var startTime = performance.now();

        function update(currentTime) {
            var elapsed = currentTime - startTime;
            var progress = Math.min(elapsed / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(target * eased);
            if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    }

    function animateCounterText(elementId, target, suffix) {
        var el = document.getElementById(elementId);
        if (!el) return;
        var duration = 800;
        var startTime = performance.now();

        function update(currentTime) {
            var elapsed = currentTime - startTime;
            var progress = Math.min(elapsed / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = (target * eased).toFixed(1) + suffix;
            if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    }

    loadStats();

    // ---- IMAGE CAPTIONING: DRAG & DROP + PREVIEW ----
    var captionDropZone = document.getElementById('captionDropZone');
    var captionFileInput = document.getElementById('captionFileInput');
    var captionPreview = document.getElementById('captionPreview');
    var captionFileTitle = document.getElementById('captionFileTitle');
    var captionDropContent = document.getElementById('captionDropContent');

    if (captionDropZone && captionFileInput) {
        console.log('[Dashboard] Caption drop zone initialized');

        // Prevent default drag behaviors on the whole document
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function(evt) {
            document.body.addEventListener(evt, function(e) {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        captionDropZone.addEventListener('dragenter', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('drag-over');
        });

        captionDropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('drag-over');
        });

        captionDropZone.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');
        });

        captionDropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                // Set files on the input
                captionFileInput.files = e.dataTransfer.files;
                handleCaptionFile(files[0]);
            }
        });

        captionFileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                handleCaptionFile(this.files[0]);
            } else {
                resetCaptionPreview();
            }
        });
    }

    function handleCaptionFile(file) {
        if (!file || !file.type.startsWith('image/')) {
            showCaptionError('Please select a valid image file.');
            return;
        }

        hideCaptionError();
        if (captionFileTitle) {
            captionFileTitle.textContent = 'Image selected';
        }

        // Show preview
        if (captionPreview) {
            var reader = new FileReader();
            reader.onload = function(e) {
                captionPreview.src = e.target.result;
                captionPreview.style.display = 'block';
                if (captionDropContent) captionDropContent.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
    }

    function resetCaptionPreview() {
        if (captionPreview) {
            captionPreview.style.display = 'none';
            captionPreview.src = '';
        }
        if (captionFileTitle) {
            captionFileTitle.textContent = 'Drag & drop or click to upload';
        }
        if (captionDropContent) captionDropContent.style.display = '';
    }

    function showCaptionError(msg) {
        var el = document.getElementById('captionError');
        if (el) {
            el.textContent = msg;
            el.style.display = 'block';
        }
    }

    function hideCaptionError() {
        var el = document.getElementById('captionError');
        if (el) el.style.display = 'none';
    }

    // ---- IMAGE CAPTIONING: FORM SUBMIT (AJAX with POST fallback) ----
    var captionForm = document.getElementById('captionForm');
    if (captionForm) {
        console.log('[Dashboard] Caption form handler attached');

        captionForm.addEventListener('submit', function(e) {
            var fileInput = document.getElementById('captionFileInput');
            if (!fileInput || !fileInput.files.length) {
                e.preventDefault();
                showCaptionError('Please select an image first.');
                return;
            }

            // Try AJAX first, fall back to standard POST
            e.preventDefault();

            hideCaptionError();
            setCaptionLoading(true);

            var formData = new FormData();
            formData.append('image', fileInput.files[0]);
            addAuthTokenToFormData(formData);

            console.log('[Dashboard] Sending caption request via AJAX...');

            fetch('/caption', {
                method: 'POST',
                headers: { 'Accept': 'application/json' },
                body: formData,
                credentials: 'same-origin'
            })
            .then(function(res) {
                console.log('[Dashboard] Caption response status:', res.status);
                if (!res.ok) {
                    return res.text().then(function(text) {
                        if (text.indexOf('<!DOCTYPE') !== -1 || text.indexOf('<html') !== -1) {
                            throw new Error('Caption request returned an unexpected page. Please refresh and try again.');
                        }
                        var errorData = {};
                        try {
                            errorData = JSON.parse(text);
                        } catch(parseErr) {}
                        throw new Error(errorData.message || 'Server error: ' + res.status);
                    });
                }
                return res.json();
            })
            .then(function(data) {
                if (!data) return;
                console.log('[Dashboard] Caption result:', data);
                setCaptionLoading(false);
                if (data && data.image_url) {
                    showCaptionResults(data);
                } else {
                    showCaptionError(data.message || 'Failed to generate caption.');
                }
            })
            .catch(function(err) {
                console.error('[Dashboard] Caption AJAX error, falling back to POST:', err);
                // Fall back to standard form POST
                captionForm.submit();
            });
        });
    }

    function setCaptionLoading(loading) {
        var btn = document.getElementById('captionSubmit');
        if (!btn) return;
        var text = btn.querySelector('.btn-text');
        var loader = btn.querySelector('.btn-loader');
        btn.disabled = loading;
        if (text) text.style.display = loading ? 'none' : '';
        if (loader) loader.style.display = loading ? '' : 'none';
    }

    function showCaptionResults(data) {
        var panel = document.getElementById('captionResults');
        if (!panel) return;

        var resultImage = document.getElementById('resultImage');
        var resultArabic = document.getElementById('resultArabic');
        var resultEnglish = document.getElementById('resultEnglish');

        if (resultImage) resultImage.src = data.image_url;
        if (resultArabic) resultArabic.textContent = data.arabic_caption;
        if (resultEnglish) resultEnglish.textContent = data.english_caption;

        panel.style.display = 'grid';
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Store for copy/download
        window._lastCaption = data;

        // Refresh stats
        loadStats();
    }

    // ---- COPY CAPTION ----
    window.copyCaption = function() {
        if (!window._lastCaption) {
            showToast('No caption to copy.');
            return;
        }
        var text = 'Arabic: ' + window._lastCaption.arabic_caption + '\nEnglish: ' + window._lastCaption.english_caption;

        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(function() {
                showToast('Caption copied to clipboard!');
            }).catch(function() {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    };

    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            showToast('Caption copied to clipboard!');
        } catch (e) {
            showToast('Failed to copy.');
        }
        document.body.removeChild(ta);
    }

    // ---- DOWNLOAD CAPTION ----
    window.downloadCaption = function() {
        if (!window._lastCaption) {
            showToast('No caption to download.');
            return;
        }
        var content = [
            '=== Arabic AI Education Assistant - Caption Result ===',
            '',
            'Arabic Caption:',
            window._lastCaption.arabic_caption,
            '',
            'English Translation:',
            window._lastCaption.english_caption,
            '',
            'Generated: ' + new Date().toLocaleString()
        ].join('\n');

        var blob = new Blob([content], { type: 'text/plain' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'caption-result-' + Date.now() + '.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Result downloaded!');
    };

    // ---- ANSWER EVALUATION: CHARACTER COUNTER ----
    var evalReference = document.getElementById('evalReference');
    var evalStudent = document.getElementById('evalStudent');
    var refCharCount = document.getElementById('refCharCount');
    var stuCharCount = document.getElementById('stuCharCount');

    if (evalReference && refCharCount) {
        evalReference.addEventListener('input', function() {
            refCharCount.textContent = this.value.length;
        });
        refCharCount.textContent = (evalReference.value || '').length;
    }

    if (evalStudent && stuCharCount) {
        evalStudent.addEventListener('input', function() {
            stuCharCount.textContent = this.value.length;
        });
        stuCharCount.textContent = (evalStudent.value || '').length;
    }

    // ---- ANSWER EVALUATION: FORM SUBMIT (AJAX with POST fallback) ----
    var evaluateForm = document.getElementById('evaluateForm');
    if (evaluateForm) {
        console.log('[Dashboard] Evaluate form handler attached');

        evaluateForm.addEventListener('submit', function(e) {
            var reference = evalReference ? evalReference.value.trim() : '';
            var student = evalStudent ? evalStudent.value.trim() : '';

            if (!reference || !student) {
                e.preventDefault();
                showEvalError('Please fill in both reference and student answers.');
                return;
            }

            // Try AJAX first, fall back to standard POST
            e.preventDefault();

            var subjectEl = document.getElementById('evalSubject');
            var subject = subjectEl ? subjectEl.value : 'General';

            hideEvalError();
            setEvalLoading(true);

            console.log('[Dashboard] Sending evaluation request via AJAX...');

            fetch('/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reference_answer: reference,
                    student_answer: student,
                    subject: subject
                }),
                credentials: 'same-origin'
            })
            .then(function(res) {
                console.log('[Dashboard] Evaluate response status:', res.status);
                if (!res.ok) {
                    return res.text().then(function(text) {
                        if (text.indexOf('<!DOCTYPE') !== -1 || text.indexOf('<html') !== -1) {
                            console.log('[Dashboard] Got HTML response, falling back to POST');
                            evaluateForm.submit();
                            return null;
                        }
                        try { var data = JSON.parse(text); throw new Error(data.message || 'Server error'); }
                        catch(parseErr) { throw new Error('Server error: ' + res.status); }
                    });
                }
                return res.json();
            })
            .then(function(data) {
                if (!data) return;
                console.log('[Dashboard] Evaluate result:', data);
                setEvalLoading(false);
                if (data && data.score !== undefined) {
                    showEvalResults(data);
                } else {
                    showEvalError(data.message || 'Failed to evaluate answer.');
                }
            })
            .catch(function(err) {
                console.error('[Dashboard] Evaluate AJAX error, falling back to POST:', err);
                evaluateForm.submit();
            });
        });
    }

    function setEvalLoading(loading) {
        var btn = document.getElementById('evalSubmit');
        if (!btn) return;
        var text = btn.querySelector('.btn-text');
        var loader = btn.querySelector('.btn-loader');
        btn.disabled = loading;
        if (text) text.style.display = loading ? 'none' : '';
        if (loader) loader.style.display = loading ? '' : 'none';
    }

    function showEvalError(msg) {
        var el = document.getElementById('evalError');
        if (el) {
            el.textContent = msg;
            el.style.display = 'block';
        }
    }

    function hideEvalError() {
        var el = document.getElementById('evalError');
        if (el) el.style.display = 'none';
    }

    function showEvalResults(data) {
        var panel = document.getElementById('evalResults');
        if (!panel) return;

        var scorePercentage = data.score_percentage || (data.score * 10);
        var scoreNum = document.getElementById('scoreNumber');
        var scoreOutOf = document.getElementById('scoreOutOf');
        var scoreGrade = document.getElementById('scoreGrade');
        var scoreProgress = document.getElementById('scoreProgress');

        // Animate score number
        if (scoreNum) {
            scoreNum.textContent = '0';
            animateCounterText('scoreNumber', scorePercentage, '');
        }
        if (scoreOutOf) scoreOutOf.textContent = 'Score: ' + data.score + ' / 10';

        // Grade
        if (scoreGrade) {
            if (data.score >= 9) scoreGrade.textContent = 'Excellent';
            else if (data.score >= 7) scoreGrade.textContent = 'Good';
            else if (data.score >= 5) scoreGrade.textContent = 'Fair';
            else if (data.score >= 3) scoreGrade.textContent = 'Needs Work';
            else scoreGrade.textContent = 'Poor';
        }

        // Animate score circle
        if (scoreProgress) {
            var circumference = 326.73;
            var offset = circumference - (scorePercentage / 100) * circumference;
            scoreProgress.style.strokeDashoffset = circumference;
            scoreProgress.style.stroke = '#0d9488';
            setTimeout(function() {
                scoreProgress.style.strokeDashoffset = offset;
                if (data.score >= 7) scoreProgress.style.stroke = '#16a34a';
                else if (data.score >= 4) scoreProgress.style.stroke = '#f59e0b';
                else scoreProgress.style.stroke = '#dc2626';
            }, 100);
        }

        // Feedback lists
        var feedback = data.feedback || {};
        populateFeedbackList('correctList', feedback.correct_concepts || []);
        populateFeedbackList('missingList', feedback.missing_concepts || []);
        populateFeedbackList('suggestionsList', feedback.suggestions || []);

        panel.style.display = 'grid';
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Refresh stats
        loadStats();
    }

    function populateFeedbackList(listId, items) {
        var list = document.getElementById(listId);
        if (!list) return;
        list.innerHTML = '';
        items.forEach(function(item) {
            var li = document.createElement('li');
            li.textContent = item;
            list.appendChild(li);
        });
    }

    // ---- HISTORY MODAL ----
    window.showHistoryModal = function() {
        var modal = document.getElementById('historyModal');
        if (modal) {
            modal.style.display = 'grid';
            loadHistory();
        }
    };

    window.openHistoryModal = window.showHistoryModal;

    window.closeHistoryModal = function() {
        var modal = document.getElementById('historyModal');
        if (modal) modal.style.display = 'none';
    };

    // Close modal on overlay click
    document.addEventListener('click', function(e) {
        if (e.target.id === 'historyModal') {
            closeHistoryModal();
        }
    });

    // Close on Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeHistoryModal();
        }
    });

    function loadHistory() {
        var container = document.getElementById('historyList');
        if (!container) return;

        container.innerHTML = '<div class="empty-state"><span class="spinner" style="width:24px;height:24px;border-width:3px;border-color:var(--border);border-top-color:var(--accent);"></span><p>Loading history...</p></div>';

        fetch('/api/history', { credentials: 'same-origin' })
            .then(function(res) {
                if (!res.ok) throw new Error('Failed to load history');
                return res.json();
            })
            .then(function(history) {
                console.log('[Dashboard] History loaded:', history.length, 'items');

                if (!history || history.length === 0) {
                    container.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" width="48" height="48"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg><p>No activity yet. Start using the tools to see your history.</p></div>';
                    return;
                }

                var html = '';
                history.forEach(function(item) {
                    var isCaption = item.type === 'caption';
                    var iconClass = isCaption ? 'caption' : 'evaluation';
                    var typeLabel = isCaption ? 'Image Captioning' : 'Answer Evaluation';
                    var meta = isCaption ? (item.details || 'Caption generated') : (item.subject || 'General');
                    var scoreText = !isCaption && item.score != null ? item.score + '/10' : '';
                    var dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : '';

                    html += '<div class="history-item">' +
                        '<div class="history-icon ' + iconClass + '">' +
                        (isCaption
                            ? '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M4 7.5A2.5 2.5 0 016.5 5h11A2.5 2.5 0 0120 7.5v9A2.5 2.5 0 0117.5 19h-11A2.5 2.5 0 014 16.5v-9z" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'
                            : '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M7 3h7l4 4v14H7a2 2 0 01-2-2V5a2 2 0 012-2z" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'
                        ) +
                        '</div>' +
                        '<div class="history-details">' +
                        '<div class="history-type">' + typeLabel + '</div>' +
                        '<div class="history-meta">' + escapeHtml(meta) + (dateStr ? ' \u00B7 ' + dateStr : '') + '</div>' +
                        '</div>' +
                        (scoreText ? '<div class="history-score">' + scoreText + '</div>' : '') +
                        '</div>';
                });

                container.innerHTML = html;
            })
            .catch(function(err) {
                console.warn('[Dashboard] Failed to load history:', err);
                container.innerHTML = '<div class="empty-state"><p>Failed to load history. Please try again.</p></div>';
            });
    }

    console.log('[Dashboard] All scripts loaded successfully');
})();

// ============================================
// DASHBOARD MODULE SWITCHING
// ============================================

var currentModule = null;
var moduleConfig = {
    captioning: {
        title: 'Image Captioning',
        api: '/api/module/captioning'
    },
    evaluation: {
        title: 'Answer Evaluation',
        api: '/api/module/evaluation'
    }
};

window.switchModule = function(event, moduleName) {
    if (event) {
        event.preventDefault();
    }

    var config = moduleConfig[moduleName];
    if (!config) {
        console.error('[Dashboard] Unknown module:', moduleName);
        return;
    }

    if (currentModule === moduleName) return;

    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(function(item) {
        item.classList.remove('active');
        item.removeAttribute('aria-current');
    });
    var activeItem = document.querySelector('.nav-item[data-module="' + moduleName + '"]');
    if (activeItem) {
        activeItem.classList.add('active');
        activeItem.setAttribute('aria-current', 'page');
    }

    // Update page title
    var pageTitle = document.getElementById('pageTitle');
    if (pageTitle) {
        pageTitle.textContent = config.title;
    }

    // Show loading state
    var contentArea = document.getElementById('contentArea');
    if (contentArea) {
        contentArea.classList.remove('is-ready');
        contentArea.classList.add('is-loading');
        contentArea.innerHTML = '<div class="loading-spinner"><svg viewBox="0 0 24 24" width="48" height="48"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" opacity="0.2"/><path d="M12 3a9 9 0 019 9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="20" stroke-dashoffset="0" style="animation: spin 1s linear infinite"/></svg><p>Loading module...</p></div>';
    }

    // Fetch module content
    fetch(config.api, { credentials: 'same-origin' })
        .then(function(res) {
            if (!res.ok) throw new Error('Failed to load module: ' + res.status);
            return res.text();
        })
        .then(function(html) {
            console.log('[Dashboard] Module loaded:', moduleName);
            if (contentArea) {
                contentArea.innerHTML = html;
                contentArea.classList.remove('is-loading');
                requestAnimationFrame(function() {
                    contentArea.classList.add('is-ready');
                });
            }
            currentModule = moduleName;

            // Initialize module-specific handlers
            if (moduleName === 'captioning') {
                initializeCaptioningModule();
            } else if (moduleName === 'evaluation') {
                initializeEvaluationModule();
            }

            // Close sidebar on mobile after selecting module
            var sidebar = document.querySelector('.sidebar');
            if (sidebar && window.innerWidth <= 768) {
                sidebar.classList.remove('open');
                document.body.classList.remove('sidebar-open');
                document.querySelectorAll('.sidebar-toggle-mobile').forEach(function(toggle) {
                    toggle.setAttribute('aria-expanded', 'false');
                });
            }
        })
        .catch(function(err) {
            console.error('[Dashboard] Failed to load module:', err);
            if (contentArea) {
                contentArea.classList.remove('is-loading');
                contentArea.innerHTML = '<div class="loading-spinner"><p style="color: var(--danger);">Failed to load module. Please try again.</p></div>';
            }
        });
};

window.logout = function(event) {
    if (event && typeof event.preventDefault === 'function') {
        event.preventDefault();
    }

    clearClientAuthToken();

    if (!window.fetch) {
        window.location.assign('/logout');
        return false;
    }

    fetch('/logout', {
        method: 'POST',
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
    })
        .then(function(res) {
            if (!res.ok) throw new Error('Logout failed: ' + res.status);
            clearClientAuthToken();
            window.location.replace('/#home');
        })
        .catch(function() {
            clearClientAuthToken();
            window.location.assign('/logout');
        });

    return false;
};

document.addEventListener('click', function(event) {
    if (event.defaultPrevented) return;
    var target = event.target;
    var logoutLink = target && target.closest ? target.closest('[data-logout-link]') : null;
    if (!logoutLink) return;
    window.logout(event);
});

// Sidebar toggle for mobile
document.addEventListener('DOMContentLoaded', function() {
    var sidebar = document.querySelector('.sidebar');
    var sidebarToggles = document.querySelectorAll('.sidebar-toggle-mobile');
    var sidebarCollapseToggle = document.getElementById('sidebarCollapseToggle');

    function setSidebarCollapsed(isCollapsed) {
        document.body.classList.toggle('sidebar-collapsed', isCollapsed);
        if (sidebarCollapseToggle) {
            sidebarCollapseToggle.setAttribute('aria-expanded', String(!isCollapsed));
            sidebarCollapseToggle.setAttribute('aria-label', isCollapsed ? 'Expand sidebar' : 'Collapse sidebar');
            sidebarCollapseToggle.setAttribute('title', isCollapsed ? 'Expand sidebar' : 'Collapse sidebar');
        }
        try {
            localStorage.setItem('intelliArabicSidebarCollapsed', isCollapsed ? '1' : '0');
        } catch (err) {
            // Ignore storage restrictions in embedded browsers.
        }
    }

    if (sidebarCollapseToggle) {
        try {
            if (localStorage.getItem('intelliArabicSidebarCollapsed') === '1' && window.innerWidth > 768) {
                setSidebarCollapsed(true);
            }
        } catch (err) {
            // Ignore storage restrictions in embedded browsers.
        }

        sidebarCollapseToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'));
            if (window.closeProfileMenu) {
                window.closeProfileMenu();
            }
        });
    }

    if (sidebar && sidebarToggles.length) {
        function setSidebarOpen(isOpen) {
            sidebar.classList.toggle('open', isOpen);
            document.body.classList.toggle('sidebar-open', isOpen);
            sidebarToggles.forEach(function(toggle) {
                toggle.setAttribute('aria-expanded', String(isOpen));
            });
        }

        sidebarToggles.forEach(function(toggle) {
            toggle.addEventListener('click', function(e) {
                e.stopPropagation();
                setSidebarOpen(!sidebar.classList.contains('open'));
            });
        });

        // Close sidebar when clicking outside
        document.addEventListener('click', function(e) {
            var clickedToggle = Array.prototype.some.call(sidebarToggles, function(toggle) {
                return toggle.contains(e.target);
            });

            if (!sidebar.contains(e.target) && !clickedToggle) {
                setSidebarOpen(false);
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                setSidebarOpen(false);
            }
        });
    }
});

// ============================================
// MODULE INITIALIZATION FUNCTIONS
// ============================================

window.initializeCaptioningModule = function() {
    console.log('[Captioning] Initializing module');

    var captionForm = document.getElementById('captionForm');
    if (!captionForm) return;

    var captionDropZone = document.getElementById('captionDropZone');
    var captionFileInput = document.getElementById('captionFileInput');
    var captionFileTitle = document.getElementById('captionFileTitle');
    var captionSubmit = document.getElementById('captionSubmit');

    setCaptionButtonReady(Boolean(captionFileInput && captionFileInput.files && captionFileInput.files.length));

    if (captionDropZone && captionFileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function(evt) {
            captionDropZone.addEventListener(evt, function(e) {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        ['dragenter', 'dragover'].forEach(function(evt) {
            captionDropZone.addEventListener(evt, function() {
                captionDropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(function(evt) {
            captionDropZone.addEventListener(evt, function() {
                captionDropZone.classList.remove('drag-over');
            });
        });

        captionDropZone.addEventListener('drop', function(e) {
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                captionFileInput.files = files;
                handleCaptionFileSelect(files[0]);
            }
        });

        captionFileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                handleCaptionFileSelect(this.files[0]);
            } else {
                resetCaptionSelection();
            }
        });
    }

    captionForm.addEventListener('submit', function(e) {
        e.preventDefault();

        if (!captionFileInput || !captionFileInput.files.length) {
            showCaptionError('Please select an image first.');
            return;
        }

        setCaptionLoading(true);

        var captionFormData = addAuthTokenToFormData(new FormData(captionForm));

        fetch('/caption', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
            body: captionFormData,
            credentials: 'same-origin'
        })
            .then(function(res) {
                return res.text().then(function(text) {
                    var data = {};
                    if (text) {
                        try {
                            data = JSON.parse(text);
                        } catch (parseError) {
                            var isHtml = text.indexOf('<!DOCTYPE') !== -1 || text.indexOf('<html') !== -1;
                            var isLoginPage = isHtml && (text.indexOf('loginForm') !== -1 || text.indexOf('/login') !== -1);
                            if (res.redirected || res.status === 401 || isLoginPage) {
                                throw new Error('Your session expired. Please sign in again.');
                            }
                            throw new Error('Caption request returned an unexpected page. Please refresh and try again.');
                        }
                    }
                    if (!res.ok) {
                        throw new Error(data.message || 'Failed to generate caption.');
                    }
                    return data;
                });
            })
            .then(function(result) {
                console.log('[Captioning] Result:', result);
                displayCaptionResult(result);
                showToast('Caption generated successfully.', 'success');
            })
            .catch(function(err) {
                console.error('[Captioning] Error:', err);
                showCaptionError(err.message || 'Failed to generate caption. Please try again.');
            })
            .finally(function() {
                setCaptionLoading(false);
                setCaptionButtonReady(Boolean(captionFileInput && captionFileInput.files.length));
            });
    });

    function setCaptionButtonReady(isReady) {
        if (captionSubmit) captionSubmit.disabled = !isReady;
    }

    function resetCaptionSelection() {
        if (captionFileTitle) captionFileTitle.textContent = 'Drag & drop or click to upload';
        if (captionDropZone) captionDropZone.classList.remove('has-file');
        setCaptionButtonReady(false);
        updateSelectedImagePreview(null);
    }
};

window.initializeEvaluationModule = function() {
    console.log('[Evaluation] Initializing module');

    var evaluationForm = document.getElementById('evaluationForm');
    if (!evaluationForm) return;

    var referenceTextarea = document.getElementById('reference');
    var studentTextarea = document.getElementById('student');
    var questionInput = document.getElementById('subject');
    var refCounter = document.getElementById('refCounter');
    var stuCounter = document.getElementById('stuCounter');
    var questionCounter = document.getElementById('questionCounter');
    var refWordCounter = document.getElementById('refWordCounter');
    var stuWordCounter = document.getElementById('stuWordCounter');

    if (referenceTextarea) {
        updateEvaluationTextStats(referenceTextarea, refCounter, refWordCounter);
        referenceTextarea.addEventListener('input', function() {
            updateEvaluationTextStats(this, refCounter, refWordCounter);
        });
    }

    if (studentTextarea) {
        updateEvaluationTextStats(studentTextarea, stuCounter, stuWordCounter);
        studentTextarea.addEventListener('input', function() {
            updateEvaluationTextStats(this, stuCounter, stuWordCounter);
            autoExpandTextarea(this);
        });
        autoExpandTextarea(studentTextarea);
    }

    if (questionInput && questionCounter) {
        questionCounter.textContent = (questionInput.value || '').length;
        questionInput.addEventListener('input', function() {
            questionCounter.textContent = this.value.length;
        });
    }

    evaluationForm.addEventListener('submit', function(e) {
        e.preventDefault();

        var subjectEl = document.getElementById('subject');
        var subject = subjectEl ? subjectEl.value.trim() : '';
        var reference = referenceTextarea ? referenceTextarea.value.trim() : '';
        var student = studentTextarea ? studentTextarea.value.trim() : '';

        if (!subject || !reference || !student) {
            showEvaluationError('Please fill in all fields.');
            return;
        }

        hideEvaluationError();
        setEvaluationLoading(true);

        fetch('/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                subject: subject,
                reference_answer: reference,
                student_answer: student,
                auth_token: window.getAuthToken ? window.getAuthToken() : (window.AUTH_TOKEN || '')
            }),
            credentials: 'same-origin'
        })
            .then(function(res) {
                if (!res.ok) {
                    return res.json().catch(function() {
                        return {};
                    }).then(function(data) {
                        throw new Error(data.message || 'Failed to evaluate answers.');
                    });
                }
                return res.json();
            })
            .then(function(result) {
                console.log('[Evaluation] Result:', result);
                result.subject = subject;
                result.reference_answer = result.reference_answer || reference;
                result.student_answer = result.student_answer || student;
                displayEvaluationResult(result);
            })
            .catch(function(err) {
                console.error('[Evaluation] Error:', err);
                showEvaluationError(err.message || 'Failed to evaluate answers. Please try again.');
            })
            .finally(function() {
                setEvaluationLoading(false);
            });
    });
};

// Helper functions
function handleCaptionFileSelect(file) {
    var captionDropZone = document.getElementById('captionDropZone');
    var captionFileTitle = document.getElementById('captionFileTitle');
    var captionSubmit = document.getElementById('captionSubmit');

    if (!file || !file.type || !file.type.startsWith('image/')) {
        showCaptionError('Please select a valid image file.');
        if (captionSubmit) captionSubmit.disabled = true;
        return;
    }

    if (captionFileTitle) captionFileTitle.textContent = 'Image selected';
    if (captionDropZone) captionDropZone.classList.add('has-file');
    if (captionSubmit) captionSubmit.disabled = false;
    updateSelectedImagePreview(file);
}

function updateSelectedImagePreview(file) {
    var emptyState = document.getElementById('captionOutputEmpty');
    var resultsPanel = document.getElementById('captionResults');
    var skeleton = document.getElementById('captionSkeleton');
    var outputPanel = resultsPanel ? resultsPanel.closest('.output-panel') : null;

    if (outputPanel) outputPanel.classList.remove('has-results', 'is-loading');
    if (resultsPanel) {
        resultsPanel.hidden = true;
        resultsPanel.style.display = 'none';
    }
    if (skeleton) skeleton.hidden = true;
    if (emptyState) {
        emptyState.hidden = false;
        emptyState.style.display = 'grid';
    }
}

function setCaptionLoading(loading) {
    var btn = document.getElementById('captionSubmit');
    var text = btn ? btn.querySelector('.btn-text') : null;
    var loader = btn ? btn.querySelector('.btn-loader') : null;
    var emptyState = document.getElementById('captionOutputEmpty');
    var resultsPanel = document.getElementById('captionResults');
    var skeleton = document.getElementById('captionSkeleton');
    var outputPanel = resultsPanel ? resultsPanel.closest('.output-panel') : null;

    if (btn) btn.disabled = true;
    if (text) text.style.display = loading ? 'none' : '';
    if (loader) loader.style.display = loading ? 'inline-flex' : 'none';
    if (skeleton) skeleton.hidden = !loading;
    if (outputPanel) outputPanel.classList.toggle('is-loading', Boolean(loading));
    if (loading) {
        if (outputPanel) outputPanel.classList.remove('has-results');
        if (emptyState) {
            emptyState.hidden = true;
            emptyState.style.display = 'none';
        }
        if (resultsPanel) {
            resultsPanel.hidden = true;
            resultsPanel.style.display = 'none';
        }
    } else if (!window._lastCaption && (!resultsPanel || resultsPanel.hidden)) {
        if (outputPanel) outputPanel.classList.remove('has-results');
        if (emptyState) {
            emptyState.hidden = false;
            emptyState.style.display = 'grid';
        }
    }
}

function displayCaptionResult(result) {
    var resultsPanel = document.getElementById('captionResults');
    if (!resultsPanel) return;

    var emptyState = document.getElementById('captionOutputEmpty');
    var skeleton = document.getElementById('captionSkeleton');
    var resultImage = document.getElementById('resultImage');
    var resultArabic = document.getElementById('resultArabic');
    var resultEnglish = document.getElementById('resultEnglish');
    var outputPanel = resultsPanel.closest('.output-panel');

    if (outputPanel) outputPanel.classList.add('has-results');
    if (outputPanel) outputPanel.classList.remove('is-loading');
    if (emptyState) {
        emptyState.hidden = true;
        emptyState.style.display = 'none';
    }
    if (skeleton) skeleton.hidden = true;
    if (resultImage) resultImage.src = result.image_url || '';
    if (resultArabic) resultArabic.textContent = result.arabic_caption || '';
    if (resultEnglish) resultEnglish.textContent = result.english_caption || '';

    resultsPanel.hidden = false;
    resultsPanel.style.display = 'grid';
    window._lastCaption = result;
}

function showCaptionError(message) {
    var errorDiv = document.getElementById('captionError');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.hidden = false;
    }
    showToast(message, 'error');
}

function setEvaluationLoading(loading) {
    var btn = document.getElementById('evaluationSubmit');
    var text = btn ? btn.querySelector('.btn-text') : null;
    var loader = btn ? btn.querySelector('.btn-loader') : null;
    var emptyState = document.getElementById('evaluationOutputEmpty');
    var resultsPanel = document.getElementById('evaluationResults');
    var skeleton = document.getElementById('evaluationSkeleton');

    if (btn) btn.disabled = loading;
    if (text) text.style.display = loading ? 'none' : '';
    if (loader) loader.style.display = loading ? 'inline-flex' : 'none';
    if (skeleton) skeleton.hidden = !loading;
    if (loading) {
        if (emptyState) emptyState.style.display = 'none';
        if (resultsPanel) resultsPanel.style.display = 'none';
    }
}

function displayEvaluationResult(result) {
    var resultsPanel = document.getElementById('evaluationResults');
    if (!resultsPanel) return;

    var emptyState = document.getElementById('evaluationOutputEmpty');
    var skeleton = document.getElementById('evaluationSkeleton');
    var score = Number(result.score || 0);
    var finalPct = Math.max(0, Math.min(100, score * 10));
    var similarityPct = normalizePercent(result.similarity);

    if (emptyState) emptyState.style.display = 'none';
    if (skeleton) skeleton.hidden = true;

    setText('finalScoreValue', formatScore(score));
    setText('similarityValue', Math.round(similarityPct) + '%');
    setText('summarySimilarity', Math.round(similarityPct) + '%');
    setText('summaryFinalScore', formatScore(score));
    updateMetricCircle('finalScoreCircle', finalPct);
    updateMetricCircle('similarityCircle', similarityPct);
    renderEvaluationFeedback(result.feedback || {});

    resultsPanel.style.display = 'grid';
    window._lastEvaluation = result;
}

function renderEvaluationFeedback(feedback) {
    renderList('correctList', feedback.correct_concepts, 'The response was evaluated against the reference answer.');
    renderList('missingList', feedback.missing_concepts, 'No major missing concepts were detected.');
    renderList('suggestionsList', feedback.suggestions, 'Keep refining the answer with precise details.');
}

function showEvaluationError(message) {
    var errorDiv = document.getElementById('evaluationError');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.hidden = false;
    }
    showToast(message, 'error');
}

function hideEvaluationError() {
    var errorDiv = document.getElementById('evaluationError');
    if (errorDiv) {
        errorDiv.textContent = '';
        errorDiv.hidden = true;
    }
}

function normalizePercent(value) {
    var numeric = Number(value || 0);
    if (numeric <= 1) return Math.max(0, Math.min(100, numeric * 100));
    return Math.max(0, Math.min(100, numeric));
}

function updateMetricCircle(id, value) {
    var circle = document.getElementById(id);
    if (circle) circle.style.setProperty('--value', Math.round(value));
}

function updateProgressBar(id, value) {
    var bar = document.getElementById(id);
    if (bar) bar.style.width = Math.max(0, Math.min(100, Math.round(value))) + '%';
}

function updateEvaluationTextStats(textarea, charEl, wordEl) {
    var value = textarea ? textarea.value || '' : '';
    if (charEl) charEl.textContent = value.length;
    if (wordEl) wordEl.textContent = countWords(value);
}

function countWords(value) {
    return (value || '').trim().split(/\s+/).filter(Boolean).length;
}

function autoExpandTextarea(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(Math.max(textarea.scrollHeight, 142), 280) + 'px';
}

function formatScore(score) {
    return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

function renderList(id, items, fallback) {
    var list = document.getElementById(id);
    if (!list) return;
    var values = Array.isArray(items) && items.length ? items : [fallback];
    list.innerHTML = values.map(function(item) {
        return '<li>' + escapeHtml(item) + '</li>';
    }).join('');
}

function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function writeClipboard(text, successMessage) {
    if (!text) {
        showToast('Nothing to copy yet.', 'error');
        return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            showToast(successMessage || 'Copied to clipboard.', 'success');
        }).catch(function() {
            fallbackCopy(text, successMessage);
        });
    } else {
        fallbackCopy(text, successMessage);
    }
}

function fallbackCopy(text, successMessage) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();

    try {
        document.execCommand('copy');
        showToast(successMessage || 'Copied to clipboard.', 'success');
    } catch (err) {
        showToast('Copy failed. Please try again.', 'error');
    }

    document.body.removeChild(ta);
}

window.copyTextFromElement = function(elementId, successMessage) {
    var el = document.getElementById(elementId);
    writeClipboard(el ? el.textContent.trim() : '', successMessage);
};

window.copyCaption = function() {
    var englishText = (document.getElementById('resultEnglish') || {}).textContent || '';
    var arabicText = (document.getElementById('resultArabic') || {}).textContent || '';
    writeClipboard('English Caption:\n' + englishText.trim() + '\n\nArabic Caption:\n' + arabicText.trim(), 'Caption copied.');
};

window.downloadCaption = function() {
    var englishText = (document.getElementById('resultEnglish') || {}).textContent || '';
    var arabicText = (document.getElementById('resultArabic') || {}).textContent || '';
    if (!englishText && !arabicText) {
        showToast('No caption to download yet.', 'error');
        return;
    }

    downloadTextFile(
        'caption-result-' + Date.now() + '.txt',
        'Image Caption Result\n\nEnglish Caption:\n' + englishText.trim() + '\n\nArabic Caption:\n' + arabicText.trim()
    );
    showToast('Caption downloaded.', 'success');
};

window.downloadCaptionPdf = function() {
    var result = window._lastCaption;
    if (!result) {
        showToast('No caption result to download yet.', 'error');
        return;
    }

    downloadPdfDocument('caption-report-' + Date.now() + '.pdf', 'IntelliArabic Image Captioning Report', [
        'English Caption: ' + (result.english_caption || ''),
        'Arabic Caption: ' + (result.arabic_caption || '')
    ]);
    showToast('Caption PDF downloaded.', 'success');
};

window.regenerateCaption = function() {
    var form = document.getElementById('captionForm');
    var fileInput = document.getElementById('captionFileInput');
    if (!form || !fileInput || !fileInput.files.length) {
        showToast('Select an image before regenerating.', 'error');
        return;
    }
    form.requestSubmit();
};

window.removeCaptionImage = function() {
    var fileInput = document.getElementById('captionFileInput');
    var dropZone = document.getElementById('captionDropZone');
    var submit = document.getElementById('captionSubmit');
    var emptyState = document.getElementById('captionOutputEmpty');
    var resultsPanel = document.getElementById('captionResults');
    var skeleton = document.getElementById('captionSkeleton');
    var outputPanel = resultsPanel ? resultsPanel.closest('.output-panel') : null;

    if (fileInput) fileInput.value = '';
    if (dropZone) dropZone.classList.remove('has-file');
    if (submit) submit.disabled = true;
    setText('captionFileTitle', 'Drag & drop or click to upload');
    updateSelectedImagePreview(null);
    if (outputPanel) outputPanel.classList.remove('has-results', 'is-loading');
    if (resultsPanel) {
        resultsPanel.hidden = true;
        resultsPanel.style.display = 'none';
    }
    if (skeleton) skeleton.hidden = true;
    if (emptyState) {
        emptyState.hidden = false;
        emptyState.style.display = 'grid';
    }
    window._lastCaption = null;
    showToast('Image removed.', 'success');
};

window.clearCaptionModule = function() {
    removeCaptionImage();
};

window.copyEvaluation = function() {
    writeClipboard(buildEvaluationText(), 'Evaluation copied.');
};

window.downloadEvaluation = function() {
    var content = buildEvaluationText();
    if (!content) {
        showToast('No evaluation to download yet.', 'error');
        return;
    }
    downloadTextFile('evaluation-result-' + Date.now() + '.txt', content);
    showToast('Evaluation downloaded.', 'success');
};

window.downloadEvaluationPdf = function() {
    var content = buildEvaluationText();
    if (!content) {
        showToast('No evaluation report to download yet.', 'error');
        return;
    }

    downloadPdfDocument('evaluation-report-' + Date.now() + '.pdf', 'IntelliArabic Answer Evaluation Report', content.split('\n'));
    showToast('Evaluation PDF downloaded.', 'success');
};

window.exportEvaluationResults = function() {
    if (!window._lastEvaluation) {
        showToast('No evaluation result to export yet.', 'error');
        return;
    }

    downloadJsonFile('evaluation-results-' + Date.now() + '.json', window._lastEvaluation);
    showToast('Evaluation exported.', 'success');
};

window.reevaluateAnswer = function() {
    var form = document.getElementById('evaluationForm');
    if (!form) return;
    form.requestSubmit();
};

window.clearEvaluationModule = function() {
    var form = document.getElementById('evaluationForm');
    var resultsPanel = document.getElementById('evaluationResults');
    var emptyState = document.getElementById('evaluationOutputEmpty');
    var skeleton = document.getElementById('evaluationSkeleton');

    if (form) form.reset();
    ['questionCounter', 'refCounter', 'stuCounter', 'refWordCounter', 'stuWordCounter'].forEach(function(id) {
        setText(id, '0');
    });
    document.querySelectorAll('#evaluationForm textarea').forEach(function(textarea) {
        textarea.style.height = '';
    });
    if (resultsPanel) resultsPanel.style.display = 'none';
    if (emptyState) emptyState.style.display = 'grid';
    if (skeleton) skeleton.hidden = true;
    window._lastEvaluation = null;
    showToast('Evaluation form cleared.', 'success');
};

function buildEvaluationText() {
    var result = window._lastEvaluation;
    if (!result) return '';

    var feedback = result.feedback || {};
    return [
        'Answer Evaluation Result',
        '',
        'Question: ' + (result.subject || ''),
        'Final Score: ' + formatScore(Number(result.score || 0)) + '/10',
        'Similarity Score: ' + Math.round(normalizePercent(result.similarity)) + '%',
        'Question Relevance: ' + Math.round(normalizePercent(
            result.question_relevance !== undefined ? result.question_relevance : result.coverage
        )) + '%',
        '',
        'Strengths:',
        listToText(feedback.correct_concepts),
        '',
        'Areas for Improvement:',
        listToText(feedback.missing_concepts),
        '',
        'Suggestions:',
        listToText(feedback.suggestions)
    ].join('\n');
}

function listToText(items) {
    if (!Array.isArray(items) || !items.length) return '- None';
    return items.map(function(item) {
        return '- ' + item;
    }).join('\n');
}

function downloadTextFile(filename, content) {
    var blob = new Blob([content], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadJsonFile(filename, data) {
    var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadPdfDocument(filename, title, lines) {
    var safeLines = [title, '', 'Generated: ' + new Date().toLocaleString()].concat(lines || []);
    var contentLines = safeLines.map(function(line) {
        return escapePdfText(String(line || '').replace(/[^\x20-\x7E]/g, ' '));
    });
    var textCommands = ['BT', '/F1 12 Tf', '50 780 Td'];
    contentLines.forEach(function(line, index) {
        if (index > 0) textCommands.push('0 -18 Td');
        textCommands.push('(' + line + ') Tj');
    });
    textCommands.push('ET');

    var stream = textCommands.join('\n');
    var objects = [
        '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
        '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        '5 0 obj\n<< /Length ' + stream.length + ' >>\nstream\n' + stream + '\nendstream\nendobj\n'
    ];
    var pdf = '%PDF-1.4\n';
    var offsets = [0];
    objects.forEach(function(obj) {
        offsets.push(pdf.length);
        pdf += obj;
    });
    var xref = pdf.length;
    pdf += 'xref\n0 ' + (objects.length + 1) + '\n0000000000 65535 f \n';
    offsets.slice(1).forEach(function(offset) {
        pdf += String(offset).padStart(10, '0') + ' 00000 n \n';
    });
    pdf += 'trailer\n<< /Size ' + (objects.length + 1) + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF';

    var blob = new Blob([pdf], { type: 'application/pdf' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function escapePdfText(value) {
    return value.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
}

function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return '-';
    var units = ['B', 'KB', 'MB', 'GB'];
    var size = bytes;
    var unit = 0;
    while (size >= 1024 && unit < units.length - 1) {
        size /= 1024;
        unit += 1;
    }
    return (unit === 0 ? size : size.toFixed(1)) + ' ' + units[unit];
}

// ---- TOAST NOTIFICATIONS ----
function showToast(message, type) {
    var stack = document.querySelector('.toast-stack');
    if (!stack) {
        stack = document.createElement('div');
        stack.className = 'toast-stack';
        document.body.appendChild(stack);
    }

    var toast = document.createElement('div');
    toast.className = 'toast ' + (type || 'info');
    toast.setAttribute('role', 'status');
    toast.textContent = message;
    stack.appendChild(toast);

    requestAnimationFrame(function() {
        toast.classList.add('show');
    });

    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() {
            if (toast.parentNode) toast.remove();
            if (stack && !stack.children.length) stack.remove();
        }, 220);
    }, 2600);
}

// ---- AUTH FORM LOADING STATE ----
document.querySelectorAll('form[action="/login"], form[action="/register"], form[action="/reset-password"]').forEach(function(form) {
    var btn = form.querySelector('.button[type="submit"]');
    if (!btn) return;

    form.addEventListener('submit', function(e) {
        var password = this.querySelector('input[name="password"]');
        var confirm = this.querySelector('input[name="confirm_password"]');
        if (password && confirm && password.value !== confirm.value) {
            e.preventDefault();
            showErrorMsg(this, 'Passwords do not match.');
            return;
        }

        btn.disabled = true;
        var originalText = btn.textContent;
        btn.innerHTML = '<span class="spinner"></span>';
        btn.dataset.originalText = originalText;
    });
});

function showErrorMsg(form, message) {
    var existing = form.querySelector('.alert.error-msg');
    if (existing) existing.remove();

    var alert = document.createElement('p');
    alert.className = 'alert error-msg';
    alert.textContent = message;
    form.insertBefore(alert, form.querySelector('.button'));
}

// Re-enable buttons on page load
window.addEventListener('pageshow', function() {
    document.querySelectorAll('.button[disabled]').forEach(function(btn) {
        btn.disabled = false;
        var original = btn.dataset.originalText;
        if (original) btn.textContent = original;
    });
});

// ---- PASSWORD TOGGLE VISIBILITY ----
document.querySelectorAll('input[type="password"]').forEach(function(input) {
    var wrapper = input.closest('.field');
    if (!wrapper) return;
    wrapper.style.position = 'relative';
    input.style.paddingRight = '40px';

    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'password-toggle';
    toggle.setAttribute('aria-label', 'Toggle password visibility');
    toggle.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" role="img"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';
    wrapper.appendChild(toggle);

    toggle.addEventListener('click', function() {
        var isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        this.innerHTML = isPassword
            ? '<svg viewBox="0 0 24 24" width="18" height="18" role="img"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><line x1="1" y1="1" x2="23" y2="23" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'
            : '<svg viewBox="0 0 24 24" width="18" height="18" role="img"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';
    });
});

console.log('[Dashboard] Script initialization complete');
