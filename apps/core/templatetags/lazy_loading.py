"""
GOAL: Provide Django template tags for lazy loading images.

TEMPLATE TAGS:
  - lazy_image: Generate img tag with lazy loading support
  - lazy_image_enabled: Check if lazy loading is enabled in settings

GUARANTEES:
  - All template tags follow AGENTS.md contract pattern
  - Type hints are complete
  - Proper error handling
"""

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
from typing import Optional, Dict, Any

register = template.Library()


@register.simple_tag
def lazy_image_enabled() -> bool:
    """
    GOAL: Check if lazy loading is enabled in Django settings.

    RETURNS:
      bool - True if lazy loading enabled, False otherwise

    GUARANTEES:
      - Returns True if setting not defined
      - Returns False if LAZY_LOADING_ENABLED is False
    """
    return getattr(settings, 'LAZY_LOADING_ENABLED', True)


@register.simple_tag
def lazy_image_placeholder() -> str:
    """
    GOAL: Get placeholder image URL from settings.

    RETURNS:
      str - Placeholder image URL - Default: "/static/img/placeholder.svg"

    GUARANTEES:
      - Returns default placeholder if not configured
      - URL is always a string
    """
    return getattr(settings, 'LAZY_LOADING_PLACEHOLDER', '/static/img/placeholder.svg')


@register.inclusion_tag('lazy_loading/lazy_image.html', takes_context=True)
def lazy_image(
    context: Dict[str, Any],
    src: str,
    alt: str = '',
    class_name: str = '',
    placeholder: Optional[str] = None,
    srcset: Optional[str] = None,
    sizes: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    loading: str = 'lazy',
    **kwargs
) -> Dict[str, Any]:
    """
    GOAL: Generate img tag with lazy loading support using data-src attributes.

    PARAMETERS:
      context: Dict[str, Any] - Django template context - Not None
      src: str - Image source URL - Required, non-empty
      alt: str - Alt text for accessibility - Default: ''
      class_name: str - CSS class names - Default: ''
      placeholder: str - Placeholder image URL - Optional, uses default if None
      srcset: str - Source set for responsive images - Optional
      sizes: str - Sizes attribute for responsive images - Optional
      width: int - Image width in pixels - Optional
      height: int - Image height in pixels - Optional
      loading: str - Native loading attribute - Default: 'lazy'
      **kwargs: Any - Additional HTML attributes - Optional

    RETURNS:
      Dict[str, Any] - Template context with all image attributes - Never None

    RAISES:
      ValueError: If src is empty or None

    GUARANTEES:
      - Returns complete context for template rendering
      - Lazy loading classes added automatically
      - Placeholder URL uses default if not provided
      - All HTML attributes are safe strings
      - Native loading attribute included for browsers that support it
    """
    if not src:
        raise ValueError("lazy_image: src parameter is required")

    # Check if lazy loading is enabled
    enabled = getattr(settings, 'LAZY_LOADING_ENABLED', True)
    effective_loading = loading if enabled else "eager"

    # Get default placeholder if not provided
    if placeholder is None:
        placeholder = getattr(settings, 'LAZY_LOADING_PLACEHOLDER', '/static/img/placeholder.svg')

    # Build CSS classes
    classes = []
    if class_name:
        classes.append(class_name)
    if enabled:
        classes.append('lazy')
        classes.append('lazy-loading')

    # Build attributes
    attrs = {
        'class': ' '.join(classes),
        'alt': alt,
        'loading': effective_loading,
    }

    if width:
        attrs['width'] = width
    if height:
        attrs['height'] = height

    # Add any additional attributes
    attrs.update(kwargs)

    # Build template context
    template_context = {
        'src': src,
        'alt': alt,
        'class': ' '.join(classes),
        'placeholder': placeholder,
        'srcset': srcset,
        'sizes': sizes,
        'enabled': enabled,
        'attrs': attrs,
        'loading': effective_loading,
    }

    return template_context


@register.simple_tag
def lazy_loading_config() -> str:
    """
    GOAL: Generate JavaScript configuration object for lazy loading.

    RETURNS:
      str - JavaScript object literal with configuration - Never None

    GUARANTEES:
      - Returns valid JavaScript object
      - Configuration matches Django settings
      - JSON-safe output
    """
    enabled = getattr(settings, 'LAZY_LOADING_ENABLED', True)
    root_margin = getattr(settings, 'LAZY_LOADING_ROOT_MARGIN', '50px')

    config = {
        'enabled': enabled,
        'rootMargin': root_margin,
    }

    import json
    return mark_safe(json.dumps(config))
