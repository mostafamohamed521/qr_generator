def language_toggle(request):
    """Compute the exact URL to send the language-switch form to, instead
    of relying on Django's set_language view to correctly strip/rebuild
    the language prefix via translate_url() (which requires the current
    path to successfully resolve() *and* reverse() under the new
    language -- if that fails for any reason, e.g. an app namespace with
    no matching URL in the target language, translate_url() silently
    returns the URL unchanged and the redirect lands back on the same
    prefix, on the same language, no matter which button was clicked).

    This only has two languages to handle and only one ('ar') is ever
    prefixed (settings.py sets prefix_default_language=False for 'en'),
    so a plain string strip/prepend is both correct and impossible to
    get subtly wrong the way relying on URL resolution can be.
    """
    path = request.path
    is_ar_prefixed = path == '/ar' or path.startswith('/ar/')
    unprefixed = path[3:] if is_ar_prefixed else path
    if not unprefixed.startswith('/'):
        unprefixed = '/' + unprefixed

    if is_ar_prefixed:
        # currently Arabic -> toggle goes to English, which has no prefix
        toggle_next = unprefixed
    else:
        # currently English -> toggle goes to Arabic, which is prefixed
        toggle_next = '/ar' + unprefixed

    return {'lang_toggle_next': toggle_next}
