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


def find_isort(view):
    cmd = get_setting(view, "isort_command")
    cmd = os.path.expanduser(cmd)
    cmd = sublime.expand_variables(cmd, sublime.active_window().extract_variables())

    for maybe_cmd in ['isort', 'isort.exe']:
        if not cmd:
            cmd = which(maybe_cmd)

    return cmd


def get_config_file(path, name, default):
    editor_config_file = None
    for potential_settings_path in default:
        expanded = os.path.expanduser(potential_settings_path)
        if os.path.exists(expanded):
            editor_config_file = expanded
            break

    tries = 0
    current_directory = path
    while current_directory and tries < 25:
        potential_path = os.path.join(current_directory, name)
        if os.path.exists(potential_path):
            editor_config_file = potential_path
            break

        new_directory = os.path.split(current_directory)[0]
        if current_directory == new_directory:
            break
        current_directory = new_directory
        tries += 1

    return editor_config_file


class ISort:
    def __init__(self, view):
        self.view = view
        self.errors = []

    def __enter__(self):
        self.encoding = self.view.encoding()

        if self.encoding in ['Undefined', None]:
            self.encoding = get_setting(self.view, 'default_encoding')

        self.popen_args = shlex.split(find_isort(self.view), posix=False)

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
            msg = "You may need to re-open this file with a different encoding. Current encoding is {}.".format(self.encoding)
            self.error("UnicodeEncodeError: {}\n\n{}".format(err, msg))
            return

        # Encode text
        if get_setting(self.view, "use_stdin"):
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

        else:
            file_obj, temp_filename = tempfile.mkstemp(suffix=".py")

            try:
                temp_handle = os.fdopen(file_obj, 'wb')
                temp_handle.write(encoded_text)
                temp_handle.close()

                config_files = []
                config_files.append(get_config_file(self.popen_cwd, '.editorconfig', ['~/.editorconfig']))
                config_files.append(get_config_file(self.popen_cwd, 'pyproject.toml', []))
                config_files.append(get_config_file(
                    self.popen_cwd,
                    '.isort.cfg',
                    ['~/.isort.cfg'],
                ))
                config_files.append(get_config_file(self.popen_cwd, 'setup.cfg', []))
                config_files.append(get_config_file(self.popen_cwd, 'tox.ini', []))
                config_files = list(filter(None, config_files))

                if config_files:
                    self.popen_args += ["-sp", config_files[-1]]

                self.popen_args += [temp_filename]

                try:
                    popen = subprocess.Popen(self.popen_args,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE,
                                             cwd=self.popen_cwd,
                                             env=self.popen_env,
                                             startupinfo=self.popen_startupinfo)
                except OSError as err:
                    # always show error in popup
                    msg = "You may need to install iSort and/or configure 'isort_command' in the plugin's Settings."
                    sublime.error_message("OSError: %s\n\n%s" % (err, msg))
                    return

                encoded_stdout, encoded_stderr = popen.communicate()

                open_encoded = open

                with open_encoded(temp_filename, encoding=self.encoding) as fp:
                    text = fp.read()

            finally:
                os.unlink(temp_filename)

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
        if get_setting(self.view, 'popup_errors'):
            sublime.error_message(msg)


class SortImport(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_python(self.view)

    def run(self, edit):
        with ISort(self.view) as isort:
            isort.format(edit)


class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):  # pylint: disable=no-self-use
        if get_setting(view, 'on_save'):
            view.run_command('sort_import')


def get_setting(view, key, default_value=None):
    settings = view.settings()
    config = settings.get(SUBLIME_SETTINGS_KEY)
    if config is not None and key in config:
        return config[key]

    settings = sublime.load_settings(PLUGIN_SETTINGS_FILE)
    return settings.get(key, default_value)
