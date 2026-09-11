"""The convenience CLI must not silently publish or run retired analyses."""
import sys

import pytest

import project


@pytest.mark.parametrize('arguments', [('build', 'cmo'), ('build', 'site'), ('build', 'forecast')])
def test_build_without_publication_intent_never_launches(monkeypatch, arguments):
    calls = []
    monkeypatch.setattr(sys, 'argv', ['project.py', *arguments])
    monkeypatch.setattr(project.subprocess, 'run', lambda *args, **kwargs: calls.append(args))
    with pytest.raises(SystemExit) as error:
        project.main()
    assert error.value.code == 2
    assert calls == []


@pytest.mark.parametrize('target,script', [('site', 'build_blue_oxblood_site.py'), ('forecast', 'build_2026_forecast_dashboard.py')])
def test_explicit_publication_preserves_existing_renderer(monkeypatch, target, script):
    calls = []
    monkeypatch.setattr(sys, 'argv', ['project.py', 'build', target, '--publish'])
    monkeypatch.setattr(project.subprocess, 'run', lambda *args, **kwargs: calls.append((args, kwargs)))
    project.main()
    assert calls == [(([sys.executable, str(project.ROOT / 'scripts' / script)],), {'cwd': project.ROOT, 'check': True})]
