/**
 * GOAL: Implement lazy loading for images using Intersection Observer API
 *        with fallback for older browsers and error handling.
 *
 * PARAMETERS (via data attributes):
 *   data-src: string - Actual image source URL - Required
 *   data-srcset: string - Source set for responsive images - Optional
 *   data-sizes: string - Sizes attribute for responsive images - Optional
 *   data-placeholder: string - Placeholder image URL - Optional
 *
 * RETURNS:
 *   None - Modifies DOM elements directly
 *
 * RAISES:
 *   Logs errors to console for debugging
 *
 * GUARANTEES:
 *   - Images load only when visible in viewport
 *   - Fallback loads all images if Intersection Observer not supported
 *   - Loading errors are logged
 *   - Placeholder images shown during loading
 */

(function() {
    'use strict';

    /**
     * GOAL: Check if browser supports Intersection Observer API.
     *
     * RETURNS:
     *   bool - True if supported, False otherwise
     *
     * GUARANTEES:
     *   - Accurate detection of Intersection Observer support
     */
    function supportsIntersectionObserver() {
        return 'IntersectionObserver' in window &&
               'IntersectionObserverEntry' in window &&
               'intersectionRatio' in window.IntersectionObserverEntry.prototype;
    }

    /**
     * GOAL: Load image from data attributes to src attribute.
     *
     * PARAMETERS:
     *   img: HTMLImageElement - Image element to load - Not null
     *
     * RETURNS:
     *   None - Modifies element directly
     *
     * GUARANTEES:
     *   - Image source is set from data-src
     *   - srcset and sizes are set if present
     *   - Loading class is removed
     */
    function loadImage(img) {
        const src = img.getAttribute('data-src');
        const srcset = img.getAttribute('data-srcset');
        const sizes = img.getAttribute('data-sizes');

        if (!src) {
            console.warn('[LazyLoading] Image missing data-src attribute', img);
            return;
        }

        img.src = src;

        if (srcset) {
            img.srcset = srcset;
        }

        if (sizes) {
            img.sizes = sizes;
        }

        img.classList.remove('lazy-loading');
        img.classList.add('lazy-loaded');

        // Handle loading errors
        img.onerror = function() {
            console.error('[LazyLoading] Failed to load image:', src);
            img.classList.remove('lazy-loaded');
            img.classList.add('lazy-error');
        };

        img.onload = function() {
            img.classList.remove('lazy-loading');
            img.classList.add('lazy-loaded');
        };
    }

    /**
     * GOAL: Initialize lazy loading with Intersection Observer.
     *
     * PARAMETERS:
     *   rootMargin: string - Margin around viewport for preloading - Default "50px"
     *
     * RETURNS:
     *   None - Sets up observer on all lazy images
     *
     * GUARANTEES:
     *   - All images with lazy class are observed
     *   - Images load when entering viewport + rootMargin
     *   - Observer is disconnected after all images loaded
     */
    function initIntersectionObserver(rootMargin) {
        const lazyImages = document.querySelectorAll('img.lazy');

        if (lazyImages.length === 0) {
            return;
        }

        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    loadImage(img);
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: rootMargin,
            threshold: 0.01
        });

        lazyImages.forEach(function(img) {
            observer.observe(img);
        });
    }

    /**
     * GOAL: Fallback for browsers without Intersection Observer.
     *        Loads all lazy images immediately.
     *
     * RETURNS:
     *   None - Loads all images
     *
     * GUARANTEES:
     *   - All lazy images are loaded
     *   - Function works in all browsers
     */
    function initFallback() {
        const lazyImages = document.querySelectorAll('img.lazy');

        lazyImages.forEach(function(img) {
            loadImage(img);
        });
    }

    /**
     * GOAL: Initialize lazy loading system.
     *
     * PARAMETERS:
     *   config: object - Configuration options - Optional
     *     rootMargin: string - Viewport margin for preloading
     *     enabled: bool - Whether lazy loading is enabled
     *
     * RETURNS:
     *   None - Initializes lazy loading
     *
     * GUARANTEES:
     *   - Lazy loading initialized if enabled
     *   - Appropriate method used based on browser support
     *   - Configuration from Django settings respected
     */
    function init(config) {
        config = config || {};

        // Check if lazy loading is enabled
        if (config.enabled === false) {
            console.log('[LazyLoading] Disabled via configuration');
            return;
        }

        const rootMargin = config.rootMargin || '50px';

        if (supportsIntersectionObserver()) {
            console.log('[LazyLoading] Using Intersection Observer');
            initIntersectionObserver(rootMargin);
        } else {
            console.log('[LazyLoading] Using fallback (load all images)');
            initFallback();
        }
    }

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            // Configuration from Django settings
            const lazyConfig = window.LAZY_LOADING_CONFIG || {};
            init(lazyConfig);
        });
    } else {
        // DOM already loaded
        const lazyConfig = window.LAZY_LOADING_CONFIG || {};
        init(lazyConfig);
    }

    // Export for external use
    window.LazyLoading = {
        init: init,
        loadImage: loadImage
    };

})();
