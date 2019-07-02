# -*- coding: utf-8 -*-
"""
Sublime Text 3 Plugin to invoke iSort on a Python file.
"""
from __future__ import print_function

import os
import shlex
import subprocess
import sys
import tempfile
from shutil import which

import sublime
import sublime_plugin

KEY = "isort"

PLUGIN_SETTINGS_FILE = "isort.sublime-settings"
SUBLIME_SETTINGS_KEY = "isort"


def is_python(view):
    return view.score_selector(0, 'source.python') > 0


def find_isort():
    cmd = get_setting("isort_command")
    cmd = os.path.expanduser(cmd)
    cmd = sublime.expand_variables(cmd, sublime.active_window().extract_variables())

    save_settings = not cmd

    for maybe_cmd in ['isort', 'isort.exe']:
        if not cmd:
            cmd = which(maybe_cmd)

    return cmd


class ISort:
    def __init__(self, view):
        self.view = view
        self.errors = []

    def __enter__(self):
        self.encoding = self.view.encoding()

        if self.encoding in ['Undefined', None]:
            self.encoding = get_setting('default_encoding')

        self.popen_args = shlex.split(find_isort(), posix=False)

        fname = self.view.file_name()

        self.popen_cwd = os.path.dirname(fname) if fname else None
        self.popen_env = os.environ.copy()
        self.popen_env['LANG'] = str(self.encoding)

        # win32: hide console window
        if sys.platform in ('win32', 'cygwin'):
            self.popen_startupinfo = subprocess.STARTUPINFO()
            self.popen_startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
            self.popen_startupinfo.wShowWindow = subprocess.SW_HIDE
        else:
            self.popen_startupinfo = None

        self.view.erase_regions(KEY)
        self.view.erase_status(KEY)

        return self

    def __exit__(self, exc_type, value, traceback):
        """Exit the runtime context related to this object.
        """

    # R0914 Too many local variables
    # R1710 Either all return statements in a function should return an expression, or none of them should.
    def format(self, edit):  # pylint: disable=R0914, R1710
        selection = sublime.Region(0, self.view.size())

        text = self.view.substr(selection)

        try:
            encoded_text = text.encode(self.encoding)
        except UnicodeEncodeError as err:
            msg = "You may need to re-open this file with a different encoding. Current encoding is {}.".format(
                self.encoding)
            self.error("UnicodeEncodeError: {}\n\n{}".format(err, msg))

        self.popen_args += ["-"]

        try:
            popen = subprocess.Popen(self.popen_args,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     stdin=subprocess.PIPE,
                                     cwd=self.popen_cwd,
                                     env=self.popen_env,
                                     startupinfo=self.popen_startupinfo)
        except OSError as err:
            # always show error in popup
            msg = "You may need to install iSort and/or configure 'isort_command' in the plugin's Settings."
            sublime.error_message("OSError: %s\n\n%s" % (err, msg))
            return

        encoded_stdout, encoded_stderr = popen.communicate(encoded_text)
        text = encoded_stdout.decode(self.encoding)

        if popen.returncode not in (0, 2):
            stderr = encoded_stderr.decode(self.encoding)
            stderr = stderr.replace(os.linesep, '\n')

            # report error
            err_lines = stderr.splitlines()
            msg = err_lines[-1]
            self.error('%s', msg)

            return

        text = text.replace(os.linesep, '\n')
        self.view.replace(edit, selection, text)

        if selection.a <= selection.b:
            return sublime.Region(selection.a, selection.a + len(text))

        return sublime.Region(selection.b + len(text), selection.b)

    def error(self, msg, *args):
        msg = msg % args
        self.errors.append(msg)
        self.view.set_status(KEY, 'iSort: %s' % ', '.join(self.errors))
        if get_setting('popup_errors'):
            sublime.error_message(msg)


class SortImport(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_python(self.view)

    def run(self, edit):
        with ISort(self.view) as isort:
            isort.format(edit)


class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):  # pylint: disable=no-self-use
        if get_setting('on_save'):
            view.run_command('sort_import')


def get_setting(key, default_value=None):
    settings = sublime.active_window().active_view().settings()
    config = settings.get(SUBLIME_SETTINGS_KEY)
    if config is not None and key in config:
        return config[key]

    settings = sublime.load_settings(PLUGIN_SETTINGS_FILE)
    return settings.get(key, default_value)
