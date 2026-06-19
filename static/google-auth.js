(function () {
    "use strict";

    var GOOGLE_SCRIPT_URL = "https://accounts.google.com/gsi/client";
    var scriptPromise = null;

    function googleIcon() {
        return [
            '<svg viewBox="0 0 24 24" aria-hidden="true">',
            '<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>',
            '<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>',
            '<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>',
            '<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>',
            '</svg>'
        ].join("");
    }

    function clearElement(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }

    function showAlert(alertId, message) {
        var alert = alertId ? document.getElementById(alertId) : null;
        if (!alert) return;

        alert.textContent = message;
        alert.hidden = false;
        alert.removeAttribute("hidden");
        alert.style.display = "block";
    }

    function fallbackButton(message, disabled) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "google-button google-fallback-button";
        button.disabled = Boolean(disabled);
        button.innerHTML = googleIcon() + "<span>" + message + "</span>";
        return button;
    }

    function loadGoogleScript() {
        if (window.google && window.google.accounts && window.google.accounts.id) {
            return Promise.resolve();
        }

        if (scriptPromise) {
            return scriptPromise;
        }

        scriptPromise = new Promise(function (resolve, reject) {
            var existing = document.querySelector('script[src="' + GOOGLE_SCRIPT_URL + '"]');
            var script = existing || document.createElement("script");

            script.addEventListener("load", resolve, { once: true });
            script.addEventListener("error", reject, { once: true });

            if (!existing) {
                script.src = GOOGLE_SCRIPT_URL;
                script.async = true;
                script.defer = true;
                document.head.appendChild(script);
            }
        });

        return scriptPromise;
    }

    function postCredential(config, response) {
        var credential = response && response.credential;
        var alertId = config.alertId;

        if (!credential) {
            showAlert(alertId, "Google did not return a sign-in credential. Please try again.");
            return;
        }

        fetch(config.loginUrl || "/google-login", {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            credentials: "same-origin",
            body: JSON.stringify({ credential: credential })
        })
            .then(function (res) {
                return res.json().catch(function () {
                    return {};
                }).then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                if (result.ok && result.data.status === "success") {
                    window.location.href = config.nextUrl || "/dashboard";
                    return;
                }

                throw new Error(result.data.message || "Could not sign in with Google.");
            })
            .catch(function (error) {
                showAlert(alertId, error.message || "Could not sign in with Google.");
            });
    }

    function renderOfficialButton(buttonHost, config) {
        var bounds = buttonHost.getBoundingClientRect();
        var width = Math.min(400, Math.max(240, Math.floor(bounds.width || 400)));
        var options = {
            client_id: config.clientId,
            callback: function (response) {
                postCredential(config, response);
            },
            ux_mode: "popup"
        };

        if (config.nonce) {
            options.nonce = config.nonce;
        }

        window.google.accounts.id.initialize(options);
        window.google.accounts.id.renderButton(buttonHost, {
            type: "standard",
            theme: "outline",
            size: "large",
            shape: "rectangular",
            text: "continue_with",
            logo_alignment: "left",
            width: width
        });
    }

    function render(config) {
        var buttonHost = document.getElementById(config.buttonId);
        if (!buttonHost) return;

        buttonHost.classList.add("google-auth-host");
        clearElement(buttonHost);

        if (!config.clientId) {
            buttonHost.appendChild(fallbackButton("Google sign-in is not configured", true));
            return;
        }

        buttonHost.appendChild(fallbackButton("Loading Google sign-in...", true));

        loadGoogleScript()
            .then(function () {
                if (!window.google || !window.google.accounts || !window.google.accounts.id) {
                    throw new Error("Google sign-in could not load.");
                }

                clearElement(buttonHost);
                renderOfficialButton(buttonHost, config);
            })
            .catch(function () {
                clearElement(buttonHost);
                buttonHost.appendChild(fallbackButton("Google sign-in is unavailable", true));
                showAlert(config.alertId, "Google sign-in could not load. Check your connection or browser settings.");
            });
    }

    window.IntelliArabicGoogleAuth = {
        render: render
    };
})();
