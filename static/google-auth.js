(function () {
    "use strict";

    function showAlert(alertId, message) {
        var alertBox = document.getElementById(alertId);
        if (!alertBox) return;

        alertBox.textContent = message;
        alertBox.hidden = false;
        alertBox.style.display = "block";
    }

    function postCredential(credentialResponse, alertId) {
        if (!credentialResponse || !credentialResponse.credential) {
            showAlert(alertId, "Google did not return a sign-in credential. Please try again.");
            return;
        }

        fetch("/google-login", {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            credentials: "same-origin",
            body: JSON.stringify({ credential: credentialResponse.credential })
        })
            .then(function (response) {
                return response.json()
                    .catch(function () { return {}; })
                    .then(function (data) {
                        return { ok: response.ok, data: data };
                    });
            })
            .then(function (result) {
                if (result.ok && result.data.status === "success") {
                    window.location.href = "/dashboard";
                    return;
                }

                showAlert(
                    alertId,
                    result.data.message || "Could not sign in with Google. Please try again."
                );
            })
            .catch(function () {
                showAlert(alertId, "Could not reach the server. Please try again.");
            });
    }

    function render(config) {
        var buttonHost = document.getElementById(config.buttonId);
        if (!buttonHost) return;

        if (!config.clientId) {
            showAlert(config.alertId, "Google sign-in is not configured.");
            return;
        }

        var attempts = 0;
        function initGoogleButton() {
            attempts += 1;

            if (!window.google || !window.google.accounts || !window.google.accounts.id) {
                if (attempts < 80) {
                    window.setTimeout(initGoogleButton, 100);
                } else {
                    showAlert(config.alertId, "Could not load Google sign-in. Check your browser and try again.");
                }
                return;
            }

            window.google.accounts.id.initialize({
                client_id: config.clientId,
                callback: function (response) {
                    postCredential(response, config.alertId);
                },
                auto_select: false,
                cancel_on_tap_outside: true
            });

            window.google.accounts.id.renderButton(buttonHost, {
                theme: "outline",
                size: "large",
                type: "standard",
                shape: "rectangular",
                text: "continue_with",
                logo_alignment: "left",
                width: Math.max(240, Math.floor(buttonHost.getBoundingClientRect().width || 360))
            });
        }

        initGoogleButton();
    }

    window.IntelliArabicGoogleAuth = {
        render: render
    };
})();
