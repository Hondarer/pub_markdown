#!/usr/bin/env python3
"""MkDocs の初回生成と再生成で、10 秒ごとに進捗を表示する。"""

import logging
import os
import sys

from mkdocs.plugins import CombinedEvent, event_priority
from mkdocs.structure.files import File, InclusionLevel
from mkdocs.structure.pages import Page

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import livedocs_progress as progress_state  # noqa: E402
from livedocs_progress import ProgressReporter  # noqa: E402

log = logging.getLogger("mkdocs.livedocs_progress")
_progress = None
_command = "build"
_total = 0
_validation_total = 0
_validation_started = False
_html_started = False
_html_completed = 0
_dirty = False
_patches = []


def _patch(owner, name, wrapper, group):
    """実行中の呼び出しだけ計測し、元の関数を復元用に保持する。"""
    original = getattr(owner, name)
    wrapped = wrapper(original)
    _patches.append((owner, name, original, wrapped, group))
    setattr(owner, name, wrapped)


def _restore(group=None):
    for entry in list(reversed(_patches)):
        owner, name, original, wrapped, category = entry
        if group is not None and group != category:
            continue
        if getattr(owner, name) is wrapped:
            setattr(owner, name, original)
        _patches.remove(entry)


def on_startup(command, dirty, **kwargs):
    global _command, _dirty
    _command = command
    _dirty = dirty


@event_priority(100)
def on_pre_build(**kwargs):
    global _progress
    _close()
    _progress = ProgressReporter(log.info, "Preparing site files")
    progress_state.build_progress = _progress
    _progress.__enter__()


@event_priority(100)
def on_files(files, **kwargs):
    _progress.set_phase("Preparing navigation")


@event_priority(150)
def _begin_nav(nav, config, **kwargs):
    if "awesome-nav" not in config.plugins:
        return
    from mkdocs_awesome_nav.nav.context import Directory, MkdocsFilesContext

    _progress.set_phase("Building navigation", unit="folders visited", count=True)
    visited = set()

    def measure(original):
        def visit(context, item):
            result = original(context, item)
            if isinstance(item, Directory):
                visited.add((id(context), item.path))
                _progress.update(len(visited))
            return result
        return visit

    # awesome-nav 3.3.0 の内部処理への依存を、この呼び出しに限定する。
    # see: https://github.com/lukasgeiter/mkdocs-awesome-nav/blob/v3.3.0/mkdocs_awesome_nav/nav/context.py
    _patch(MkdocsFilesContext, "visit", measure, "navigation")


@event_priority(-100)
def _finish_nav(nav, files, **kwargs):
    global _total, _validation_total
    _progress.report()
    _restore("navigation")
    inclusion = InclusionLevel.is_in_serve if _command == "serve" else InclusionLevel.is_included
    pages = files.documentation_pages(inclusion=inclusion)
    _validation_total = len(pages)
    _total = sum(1 for file in pages if not _dirty or file.is_modified())
    _progress.set_phase("Rendering Markdown", _total, unit="pages")

    def measure(original):
        def validate(page, **kwargs):
            _start_validation()
            result = original(page, **kwargs)
            _progress.advance()
            return result
        return validate

    _patch(Page, "validate_anchor_links", measure, "validation")


on_nav = CombinedEvent(_begin_nav, _finish_nav)


@event_priority(-100)
def on_page_content(html, **kwargs):
    _progress.advance()


@event_priority(100)
def on_env(env, files, config, **kwargs):
    _progress.report()
    inclusion = InclusionLevel.is_in_serve if _command == "serve" else InclusionLevel.is_included
    assets = [file for file in files if not file.is_documentation_page() and inclusion(file.inclusion)]
    _progress.set_phase("Copying assets", len(assets), unit="files")

    def measure(original):
        def copy(file, *args, **kwargs):
            result = original(file, *args, **kwargs)
            _progress.advance()
            return result
        return copy

    _patch(File, "copy_file", measure, "assets")

    from mkdocs.commands import build as build_module
    template_total = len(config.theme.static_templates) + len(config.extra_templates)
    templates_started = False

    def measure_template(original):
        def render(*args, **kwargs):
            nonlocal templates_started
            if not templates_started:
                _progress.report()
                _restore("assets")
                _progress.set_phase("Rendering shared templates", template_total, unit="templates")
                templates_started = True
            result = original(*args, **kwargs)
            _progress.advance()
            return result
        return render

    # see: https://github.com/mkdocs/mkdocs/blob/1.6.1/mkdocs/commands/build.py
    _patch(build_module, "_build_theme_template", measure_template, "templates")
    _patch(build_module, "_build_extra_template", measure_template, "templates")


@event_priority(100)
def on_page_context(context, page, **kwargs):
    global _html_started
    if page is not None and not _html_started:
        _progress.report()
        _restore("assets")
        _restore("templates")
        _progress.set_phase("Rendering HTML", _total, unit="pages")
        _html_started = True


@event_priority(-100)
def on_post_page(output, **kwargs):
    global _html_completed
    _progress.advance()
    _html_completed += 1
    if _html_completed == _total:
        _progress.report()
        _start_validation()


def _start_validation():
    global _validation_started
    if not _validation_started:
        _progress.set_phase("Validating links", _validation_total, unit="pages")
        _validation_started = True


@event_priority(100)
def _begin_post_build(config, **kwargs):
    _start_validation()
    _progress.report()
    _restore()
    search = config.plugins.get("material/search") or config.plugins.get("search")
    if search is None:
        return
    index = getattr(search, "search_index", None)
    entries = getattr(index, "entries", [])
    _progress.set_phase("Writing search index", completed=len(entries),
                        unit="indexed entries", count=True)


@event_priority(-100)
def _finish_post_build(**kwargs):
    _close()


on_post_build = CombinedEvent(_begin_post_build, _finish_post_build)


def _close():
    global _progress, _html_started, _html_completed, _validation_started
    _restore()
    if _progress is not None:
        _progress.close()
        _progress = None
    progress_state.build_progress = None
    _html_started = False
    _html_completed = 0
    _validation_started = False


def on_build_error(**kwargs):
    _close()


def on_shutdown(**kwargs):
    _close()
