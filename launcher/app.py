# -*- coding: utf-8 -*-

import os
from datetime import datetime
from functools import partial
import traceback

from kivy.lang import Builder
from kivy.app import App
from kivy.utils import platform
from kivy.properties import ListProperty, BooleanProperty, StringProperty
from glob import glob
from os.path import dirname, join, exists

KIVYLAUNCHER_PATHS = os.environ.get("KIVYLAUNCHER_PATHS")


class Launcher(App):
    external_path_file = 'external_path.txt'
    external_path = StringProperty('')
    paths = ListProperty()
    logs = ListProperty()
    display_logs = BooleanProperty(False)

    def log(self, log):
        print(log)
        self.logs.append(f"{datetime.now().strftime('%X.%f')}: {log}")

    def on_enter_path(self, instance, value):
        path = self.root.ids.path.text
        if path not in self.paths:
            with open(self.external_path_file, "w") as f:
                f.write(path)
            self.paths.append(path)
        self.refresh_entries()

    def build(self):
        self.log('start of log')

        if KIVYLAUNCHER_PATHS:
            self.paths.extend(KIVYLAUNCHER_PATHS.split(","))

        if platform == 'android':
            from jnius import autoclass
            from android.permissions import request_permissions, Permission, check_permission
            from plyer import accelerometer
            self.log(accelerometer)
            accelerometer.enable()
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            Environment = autoclass('android.os.Environment')
            sdcard_path = Environment.getExternalStorageDirectory().getAbsolutePath()
            self.paths = [sdcard_path + "/kivy"]
        else:
            self.paths = [os.path.expanduser("~/kivy")]

        self.root = Builder.load_file("launcher/app.kv")
        self.root.ids.path.bind(on_text_validate=partial(self.on_enter_path, self))

        # load external path
        if os.path.exists(self.external_path_file):
            with open(self.external_path_file, "r") as f:
                external_path = f.read()
                self.root.ids.path.txt = external_path
                self.paths.append(external_path)
        self.refresh_entries()

    def refresh_entries(self):
        data = []
        self.log('starting refresh')
        for entry in self.find_entries(paths=self.paths):
            self.log(f'found entry {entry}')
            data.append({
                "data_title": entry.get("title", "- no title -"),
                "data_path": entry.get("path"),
                "data_logo": entry.get("logo", "data/logo/kivy-icon-64.png"),
                "data_orientation": entry.get("orientation", ""),
                "data_author": entry.get("author", ""),
                "data_entry": entry
            })
        self.root.ids.rv.data = data

    def find_entries(self, path=None, paths=None):
        self.log(f'looking for entries in {paths} or {path}')
        if paths is not None:
            for path in paths:
                for entry in self.find_entries(path=path):
                    yield entry

        elif path is not None:
            if not exists(path):
                self.log(f'{path} does not exist')
                return

            for folder in os.listdir(path):
                project_folder = os.path.join(path, folder)
                if os.path.isdir(project_folder):
                    contents = os.listdir(project_folder)
                    filename = None
                    if 'android.txt' in contents:
                        filename = os.path.join(project_folder, 'android.txt')
                    elif 'main.py' in contents:
                        filename = os.path.join(project_folder, 'main.py')
                    else:
                        continue
                    self.log(f'{filename} exist')
                    entry = self.read_entry(filename)
                    if entry:
                        yield entry

    def read_entry(self, filename):
        self.log(f'reading entry {filename}')
        data = {}
        try:
            if filename.endswith('android.txt'):
                with open(filename, "r") as fd:
                    lines = fd.readlines()
                    for line in lines:
                        k, v = line.strip().split("=", 1)
                        data[k] = v
                data["entrypoint"] = join(dirname(filename), "main.py")
            else:
                data['title'] = os.path.split(dirname(filename))[-1]
                data['author'] = 'Unknown'
                data['orientation'] = 'sensor'
                data["entrypoint"] = filename
        except Exception:
            traceback.print_exc()
            return None
        data["path"] = dirname(filename)
        icon = join(data["path"], "icon.png")
        if exists(icon):
            data["icon"] = icon
        return data

    def start_activity(self, entry):
        if platform == "android":
            self.start_android_activity(entry)
        else:
            self.start_desktop_activity(entry)

    def start_desktop_activity(self, entry):
        import sys
        from subprocess import Popen
        entrypoint = entry["entrypoint"]
        env = os.environ.copy()
        env["KIVYLAUNCHER_ENTRYPOINT"] = entrypoint
        main_py = os.path.realpath(os.path.join(
            os.path.dirname(__file__), "..", "main.py"))
        cmd = Popen([sys.executable, main_py], env=env)
        cmd.communicate()

    def start_android_activity(self, entry):
        self.log('starting activity')
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        System = autoclass("java.lang.System")
        activity = PythonActivity.mActivity
        Intent = autoclass("android.content.Intent")
        String = autoclass("java.lang.String")

        j_entrypoint = String(entry.get("entrypoint"))
        j_orientation = String(entry.get("orientation"))

        self.log('creating intent')
        intent = Intent(
            activity.getApplicationContext(),
            PythonActivity
        )
        intent.putExtra("entrypoint", j_entrypoint)
        intent.putExtra("orientation", j_orientation)
        self.log(f'ready to start intent {j_entrypoint} {j_orientation}')
        activity.startActivity(intent)
        self.log('activity started')
        System.exit(0)
