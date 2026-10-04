from policy_hero_scale import BLOCK, START, TARGETS, ensure_policy_hero_scale


def broken_source():
    return '''<style>
.hero h1{font-size:clamp(44px,7.5vw,96px)}
.kvP-hero.kvP-in{display:grid;grid-template-columns:1fr 1fr}
#enhancedSite.kvP-in.kvP-h1,#enhancedSite.kc-htop h1{font-size:clamp(26px,4.5vw,54px)}
</style><h1 class="kvP-h1">Say <span class="kvP-flip"><i>hello</i></span>.</h1>'''


def test_all_four_policy_pages_receive_standard_rotating_word_scale():
    for path in TARGETS:
        out = ensure_policy_hero_scale(broken_source(), path)
        assert out.count(START) == 1
        assert '.kvP-hero .kvP-h1{font-size:clamp(30px,5vw,52px)!important' in out
        assert '.kvP-hero .kvP-flip i{font-size:.98em!important' in out
        assert 'font-size:clamp(21px,6vw,28px)!important' in out
        assert '.kvP-hero>.kvP-in{display:grid!important' in out
        assert 'grid-template-columns:minmax(0,1.04fr) minmax(280px,.96fr)!important' in out
        assert 'grid-template-columns:minmax(0,1fr) minmax(140px,.9fr)!important' in out


def test_corrupted_descendant_selectors_are_repaired():
    out = ensure_policy_hero_scale(broken_source(), '/p/privacy-policy.html')
    assert '#enhancedSite .kvP-in .kvP-h1' in out
    assert '#enhancedSite .kc-htop h1' in out
    assert '#enhancedSite.kvP-in.kvP-h1' not in out
    assert '.kvP-hero .kvP-in' in out
    assert '.kvP-hero.kvP-in' not in out


def test_non_target_page_gets_no_scale_override():
    out = ensure_policy_hero_scale(broken_source(), '/p/daily-news.html')
    assert START not in out
    assert BLOCK not in out


def test_scale_override_is_idempotent():
    once = ensure_policy_hero_scale(broken_source(), '/p/contact-us_01883938366.html')
    twice = ensure_policy_hero_scale(once, '/p/contact-us_01883938366.html')
    assert once == twice
    assert twice.count(START) == 1
