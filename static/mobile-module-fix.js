```javascript
(function () {
    'use strict';

    if (window.__INTELLIARABIC_MOBILE_FIX__) {
        return;
    }

    window.__INTELLIARABIC_MOBILE_FIX__ = true;

    const MOBILE_BREAKPOINT = 980;

    let sidebar;
    let contentArea;
    let toggleButtons = [];

    let savedWindowScroll = 0;
    let savedContentScroll = 0;
    let previousContentOverflow = '';
    let scrollLocked = false;

    function findElements() {
        sidebar = document.querySelector('.sidebar');

        contentArea =
            document.querySelector('.content-area') ||
            document.getElementById('contentArea');

        toggleButtons = Array.from(
            document.querySelectorAll(
                '.sidebar-toggle-mobile, [data-sidebar-toggle]'
            )
        );
    }

    function isMobile() {
        return window.innerWidth <= MOBILE_BREAKPOINT;
    }

    function isSidebarOpen() {
        return Boolean(
            sidebar &&
            sidebar.classList.contains('open')
        );
    }

    function updateToggleButtons(open) {
        toggleButtons.forEach(function (button) {
            button.setAttribute(
                'aria-expanded',
                String(open)
            );

            button.setAttribute(
                'aria-label',
                open
                    ? 'Close navigation menu'
                    : 'Open navigation menu'
            );
        });
    }

    function lockScroll() {
        if (scrollLocked) {
            return;
        }

        scrollLocked = true;

        /*
         * The dashboard normally scrolls inside .content-area.
         * Lock that element so the visible module does not jump.
         */
        if (contentArea) {
            savedContentScroll = contentArea.scrollTop;
            previousContentOverflow =
                contentArea.style.overflowY;

            contentArea.style.overflowY = 'hidden';
            contentArea.style.overscrollBehavior = 'none';

            return;
        }

        /*
         * Fallback for pages that use normal window scrolling.
         */
        savedWindowScroll =
            window.scrollY ||
            document.documentElement.scrollTop ||
            0;

        document.body.style.position = 'fixed';
        document.body.style.top =
            '-' + savedWindowScroll + 'px';
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockScroll() {
        if (!scrollLocked) {
            return;
        }

        scrollLocked = false;

        if (contentArea) {
            contentArea.style.overflowY =
                previousContentOverflow;

            contentArea.style.removeProperty(
                'overscroll-behavior'
            );

            requestAnimationFrame(function () {
                contentArea.scrollTop =
                    savedContentScroll;
            });

            return;
        }

        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';

        requestAnimationFrame(function () {
            window.scrollTo(0, savedWindowScroll);
        });
    }

    function openSidebar() {
        findElements();

        if (!sidebar || !isMobile()) {
            return;
        }

        sidebar.classList.add('open');
        document.body.classList.add('sidebar-open');

        sidebar.setAttribute('aria-hidden', 'false');

        updateToggleButtons(true);
        lockScroll();
    }

    function closeSidebar() {
        findElements();

        if (!sidebar) {
            return;
        }

        sidebar.classList.remove('open');
        document.body.classList.remove('sidebar-open');

        sidebar.setAttribute('aria-hidden', 'true');

        updateToggleButtons(false);
        unlockScroll();
    }

    function toggleSidebar() {
        if (isSidebarOpen()) {
            closeSidebar();
        } else {
            openSidebar();
        }
    }

    /*
     * Capture hamburger clicks before older scripts can move
     * the page or toggle the sidebar twice.
     */
    document.addEventListener(
        'click',
        function (event) {
            const target = event.target;

            if (!target || !target.closest) {
                return;
            }

            const toggleButton = target.closest(
                '.sidebar-toggle-mobile, [data-sidebar-toggle]'
            );

            if (toggleButton && isMobile()) {
                event.preventDefault();
                event.stopImmediatePropagation();

                toggleSidebar();
                return;
            }

            if (!isSidebarOpen()) {
                return;
            }

            const sidebarItem = target.closest(
                '.sidebar .nav-item, .sidebar a'
            );

            if (sidebarItem) {
                /*
                 * Keep the existing module-selection logic,
                 * then close the mobile sidebar.
                 */
                setTimeout(function () {
                    closeSidebar();
                }, 0);

                return;
            }

            /*
             * The CSS backdrop is generated through
             * body.sidebar-open::before. A click outside the
             * sidebar closes it.
             */
            if (
                sidebar &&
                !sidebar.contains(target)
            ) {
                closeSidebar();
            }
        },
        true
    );

    document.addEventListener(
        'keydown',
        function (event) {
            if (
                event.key === 'Escape' &&
                isSidebarOpen()
            ) {
                event.preventDefault();
                closeSidebar();
            }
        }
    );

    window.addEventListener(
        'resize',
        function () {
            if (
                window.innerWidth > MOBILE_BREAKPOINT &&
                isSidebarOpen()
            ) {
                closeSidebar();
            }
        }
    );

    window.addEventListener(
        'pageshow',
        function () {
            findElements();

            if (isSidebarOpen()) {
                closeSidebar();
            }
        }
    );

    document.addEventListener(
        'DOMContentLoaded',
        function () {
            findElements();

            if (!sidebar) {
                return;
            }

            sidebar.setAttribute(
                'aria-hidden',
                String(!isSidebarOpen())
            );

            updateToggleButtons(isSidebarOpen());

            /*
             * Restore scrolling if another existing script
             * removes the sidebar's open class.
             */
            const sidebarObserver =
                new MutationObserver(function () {
                    if (
                        !isSidebarOpen() &&
                        scrollLocked
                    ) {
                        document.body.classList.remove(
                            'sidebar-open'
                        );

                        updateToggleButtons(false);
                        unlockScroll();
                    }
                });

            sidebarObserver.observe(sidebar, {
                attributes: true,
                attributeFilter: ['class']
            });
        }
    );
})();
```
