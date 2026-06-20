// ============================================
// Arabic AI Education Assistant - Dashboard JS
// ============================================

(function() {
    'use strict';

    if (!window.fetch || window.__INTELLI_ARABIC_AUTH_FETCH__) return;

    var nativeFetch = window.fetch.bind(window);
    window.__INTELLI_ARABIC_AUTH_FETCH__ = true;

    function authToken() {
        return window.AUTH_TOKEN || sessionStorage.getItem('authToken') || '';
    }

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
            options.headers = headers;
        }

        return nativeFetch(input, options);
    };
})();

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

    window.toggleProfileLanguage = function() {
        if (langSwitch) {
            langSwitch.click();
        }
        if (window.closeProfileMenu) {
            window.closeProfileMenu();
        }
    };

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
            captionFileTitle.textContent = file.name;
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

            console.log('[Dashboard] Sending caption request via AJAX...');

            fetch('/caption', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            })
            .then(function(res) {
                console.log('[Dashboard] Caption response status:', res.status);
                if (!res.ok) {
                    return res.text().then(function(text) {
                        // If server returned HTML (redirect), fall back to POST
                        if (text.indexOf('<!DOCTYPE') !== -1 || text.indexOf('<html') !== -1) {
                            console.log('[Dashboard] Got HTML response, falling back to POST');
                            captionForm.submit();
                            return null;
                        }
                        try { var data = JSON.parse(text); throw new Error(data.message || 'Server error'); }
                        catch(parseErr) { throw new Error('Server error: ' + res.status); }
                    });
                }
                return res.json();
            })
            .then(function(data) {
                if (!data) return; // Redirected to POST fallback
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
        var confidenceFill = document.getElementById('confidenceFill');
        var confidenceValue = document.getElementById('confidenceValue');

        if (resultImage) resultImage.src = data.image_url;
        if (resultArabic) resultArabic.textContent = data.arabic_caption;
        if (resultEnglish) resultEnglish.textContent = data.english_caption;

        var confidence = data.confidence || 75;
        if (confidenceFill) {
            confidenceFill.style.width = '0%';
            setTimeout(function() {
                confidenceFill.style.width = confidence + '%';
            }, 100);
        }
        if (confidenceValue) confidenceValue.textContent = confidence + '%';

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
            'Confidence: ' + (window._lastCaption.confidence || 75) + '%',
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
    });
    document.querySelector('.nav-item[data-module="' + moduleName + '"]').classList.add('active');

    // Update page title
    var pageTitle = document.getElementById('pageTitle');
    if (pageTitle) {
        pageTitle.textContent = config.title;
    }

    // Show loading state
    var contentArea = document.getElementById('contentArea');
    if (contentArea) {
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
                contentArea.innerHTML = '<div class="loading-spinner"><p style="color: var(--danger);">Failed to load module. Please try again.</p></div>';
            }
        });
};

window.logout = function() {
    sessionStorage.removeItem('authToken');
    window.AUTH_TOKEN = '';
    window.location.href = '/logout';
};

// Sidebar toggle for mobile
document.addEventListener('DOMContentLoaded', function() {
    var sidebar = document.querySelector('.sidebar');
    var sidebarToggles = document.querySelectorAll('.sidebar-toggle-mobile');

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
    var captionPreview = document.getElementById('captionPreview');
    var captionFileTitle = document.getElementById('captionFileTitle');
    var captionSubmit = document.getElementById('captionSubmit');

    if (captionDropZone && captionFileInput) {
        // Drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function(evt) {
            captionDropZone.addEventListener(evt, function(e) {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        captionDropZone.addEventListener('dragenter', function() {
            this.classList.add('drag-over');
        });

        captionDropZone.addEventListener('dragleave', function() {
            this.classList.remove('drag-over');
        });

        captionDropZone.addEventListener('drop', function(e) {
            this.classList.remove('drag-over');
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                captionFileInput.files = files;
                handleCaptionFileSelect(files[0]);
            }
        });

        captionFileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                handleCaptionFileSelect(this.files[0]);
            }
        });
    }

    if (captionForm) {
        captionForm.addEventListener('submit', function(e) {
            e.preventDefault();

            if (!captionFileInput || !captionFileInput.files.length) {
                showCaptionError('Please select an image first');
                return;
            }

            // Show loading state
            if (captionSubmit) {
                captionSubmit.disabled = true;
                captionSubmit.querySelector('.btn-text').style.display = 'none';
                captionSubmit.querySelector('.btn-loader').style.display = 'inline-flex';
            }

            var formData = new FormData(captionForm);
            fetch('/caption', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            })
                .then(function(res) {
                    if (!res.ok) throw new Error('Failed: ' + res.status);
                    return res.json();
                })
                .then(function(result) {
                    console.log('[Captioning] Result:', result);
                    displayCaptionResult(result);
                })
                .catch(function(err) {
                    console.error('[Captioning] Error:', err);
                    showCaptionError('Failed to generate caption. Please try again.');
                })
                .finally(function() {
                    if (captionSubmit) {
                        captionSubmit.disabled = false;
                        captionSubmit.querySelector('.btn-text').style.display = 'inline-flex';
                        captionSubmit.querySelector('.btn-loader').style.display = 'none';
                    }
                });
        });
    }
};

window.initializeEvaluationModule = function() {
    console.log('[Evaluation] Initializing module');

    var evaluationForm = document.getElementById('evaluationForm');
    if (!evaluationForm) return;

    var referenceTextarea = document.getElementById('reference');
    var studentTextarea = document.getElementById('student');
    var refCounter = document.getElementById('refCounter');
    var stuCounter = document.getElementById('stuCounter');

    // Character counters
    if (referenceTextarea && refCounter) {
        referenceTextarea.addEventListener('input', function() {
            refCounter.textContent = this.value.length;
        });
    }

    if (studentTextarea && stuCounter) {
        studentTextarea.addEventListener('input', function() {
            stuCounter.textContent = this.value.length;
        });
    }

    evaluationForm.addEventListener('submit', function(e) {
        e.preventDefault();

        var subject = document.getElementById('subject').value.trim();
        var reference = referenceTextarea.value.trim();
        var student = studentTextarea.value.trim();
        var evaluationSubmit = document.getElementById('evaluationSubmit');

        if (!subject || !reference || !student) {
            showEvaluationError('Please fill in all fields');
            return;
        }

        // Show loading state
        if (evaluationSubmit) {
            evaluationSubmit.disabled = true;
            evaluationSubmit.querySelector('.btn-text').style.display = 'none';
            evaluationSubmit.querySelector('.btn-loader').style.display = 'inline-flex';
        }

        fetch('/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                subject: subject,
                reference_answer: reference,
                student_answer: student
            }),
            credentials: 'same-origin'
        })
            .then(function(res) {
                if (!res.ok) throw new Error('Failed: ' + res.status);
                return res.json();
            })
            .then(function(result) {
                console.log('[Evaluation] Result:', result);
                displayEvaluationResult(result);
            })
            .catch(function(err) {
                console.error('[Evaluation] Error:', err);
                showEvaluationError('Failed to evaluate answers. Please try again.');
            })
            .finally(function() {
                if (evaluationSubmit) {
                    evaluationSubmit.disabled = false;
                    evaluationSubmit.querySelector('.btn-text').style.display = 'inline-flex';
                    evaluationSubmit.querySelector('.btn-loader').style.display = 'none';
                }
            });
    });
};

// Helper functions
function handleCaptionFileSelect(file) {
    var captionPreview = document.getElementById('captionPreview');
    var captionFileTitle = document.getElementById('captionFileTitle');

    if (file.type.startsWith('image/')) {
        var reader = new FileReader();
        reader.onload = function(e) {
            if (captionPreview) {
                captionPreview.src = e.target.result;
                captionPreview.style.display = 'block';
            }
            if (captionFileTitle) {
                captionFileTitle.textContent = file.name;
            }
        };
        reader.readAsDataURL(file);
    }
}

function displayCaptionResult(result) {
    var resultsPanel = document.getElementById('captionResults');
    if (!resultsPanel) return;

    document.getElementById('resultImage').src = result.image_url;
    document.getElementById('resultArabic').textContent = result.arabic_caption;
    document.getElementById('resultEnglish').textContent = result.english_caption;
    document.getElementById('confidenceFill').style.width = (result.confidence || 75) + '%';
    document.getElementById('confidenceValue').textContent = (result.confidence || 75) + '%';

    resultsPanel.style.display = 'block';
}

function showCaptionError(message) {
    var errorDiv = document.getElementById('captionError');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

function displayEvaluationResult(result) {
    var resultsPanel = document.getElementById('evaluationResults');
    if (!resultsPanel) return;

    var score = result.score || 0;
    document.getElementById('scoreValue').textContent = score;
    document.getElementById('similarityValue').textContent = Math.round((result.similarity || 0) * 100) + '%';
    document.getElementById('coverageValue').textContent = Math.round((result.coverage || 0) * 100) + '%';

    // Update feedback lists
    var feedback = result.feedback || {};
    var correctList = document.getElementById('correctList');
    var missingList = document.getElementById('missingList');
    var suggestionsList = document.getElementById('suggestionsList');

    if (correctList) {
        correctList.innerHTML = (feedback.correct_concepts || []).map(function(item) {
            return '<li>' + escapeHtml(item) + '</li>';
        }).join('');
    }

    if (missingList) {
        missingList.innerHTML = (feedback.missing_concepts || []).map(function(item) {
            return '<li>' + escapeHtml(item) + '</li>';
        }).join('');
    }

    if (suggestionsList) {
        suggestionsList.innerHTML = (feedback.suggestions || []).map(function(item) {
            return '<li>' + escapeHtml(item) + '</li>';
        }).join('');
    }

    // Update answer comparison
    document.getElementById('comparisonReference').textContent = result.reference_answer || '';
    document.getElementById('comparisonStudent').textContent = result.student_answer || '';

    resultsPanel.style.display = 'block';
}

function showEvaluationError(message) {
    var errorDiv = document.getElementById('evaluationError');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

window.copyCaption = function() {
    var arabicText = document.getElementById('resultArabic').textContent;
    var englishText = document.getElementById('resultEnglish').textContent;
    var text = 'Arabic: ' + arabicText + '\nEnglish: ' + englishText;

    navigator.clipboard.writeText(text).then(function() {
        alert('Caption copied to clipboard!');
    }).catch(function() {
        alert('Failed to copy to clipboard');
    });
};

window.downloadCaption = function() {
    var arabicText = document.getElementById('resultArabic').textContent;
    var englishText = document.getElementById('resultEnglish').textContent;
    var content = 'Image Caption\n\nArabic:\n' + arabicText + '\n\nEnglish:\n' + englishText;

    var blob = new Blob([content], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'caption.txt';
    a.click();
    URL.revokeObjectURL(url);
};

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ---- TOAST NOTIFICATIONS ----
function showToast(message) {
    var existing = document.querySelector('.toast');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:10px 20px;background:#0f172a;color:#fff;border-radius:8px;font-size:14px;font-weight:600;z-index:2000;animation:fadeIn 0.2s ease;box-shadow:0 4px 16px rgba(0,0,0,0.2)';
    document.body.appendChild(toast);

    setTimeout(function() {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(function() { if (toast.parentNode) toast.remove(); }, 300);
    }, 2000);
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
