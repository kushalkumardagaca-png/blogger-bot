from social_identity import ensure_social_identity


def test_social_cleanup_never_corrupts_css_descendant_selectors():
    source = '<style>#root .card,#root .title{color:#241610}</style><p>Follow via <a href="https://twitter.com/closed">X</a>.</p>'
    out = ensure_social_identity(source)
    assert '#root .card,#root .title' in out
    assert '#root.card' not in out
    assert 'twitter.com' not in out


def test_social_cleanup_never_rewrites_executable_script_spacing():
    source = '<script>document.querySelector("#root .card"); var x = obj .value;</script>'
    assert ensure_social_identity(source) == source
