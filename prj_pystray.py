#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2023 Hannes Haberl <hannes.haberl@student.tugraz.at>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pystray

from PIL import Image

from pathlib import Path
from collections import OrderedDict
from datetime import datetime


def get_image_path(project_name) -> Path|None:
	prefix = 'myIcon_'
	icon_ext = '.ico'
	f = Path(prefix+project_name)
	f = f.with_suffix(icon_ext)

	if f.exists(): return f

	return None

class PrjTray:
	def __init__(self, logfile, projects, default) -> None:
		self.project = default

		self.logfile = logfile

		self.projects = projects

		self.menu = self.make_menu()

		p, wp = self.get_project(default)
		image = Image.open(p.get_wp_icon(wp))
		self.fallback_icon = image

		self.tray = pystray.Icon('PRJTRX', image, menu = self.menu)

		self.change_project(default)

	def make_menu(self) -> pystray.Menu:
		menu_items = []

		for id, p in self.projects.items():
			key = id
			if len(p.workpackages) > 1:
				submenu_items = []
				for wp_id, wp in p.workpackages.items():
					wp_key = (id, wp_id)
					submenu_items.append(
						pystray.MenuItem(
							wp[0],
							self.on_click(wp_key),
							self.is_selected(wp_key),
							radio=True
						)
					)

				menu_items.append(
					pystray.MenuItem(
						p.name,
						pystray.Menu(*submenu_items)
					)
				)
			else:
				menu_items.append(
					pystray.MenuItem(
						p.name,
						self.on_click(key),
						self.is_selected(key),
						radio=True
					)
				)

		menu_items.append(
			pystray.Menu.SEPARATOR
		)

		menu_items.append(
			pystray.MenuItem('Quit', self.quit('Menu Exit'))
		)

		return pystray.Menu(*menu_items)

	def get_project(self, key):
		project = None
		wp = None
		if isinstance(key, tuple):
			project = key[0]
			wp = key[1]
		else:
			project = key

		return self.projects[project], wp


	def is_selected(self, key):
		def inner(item):
			return key == self.project

		return inner

	def on_click(self, key):
		def inner(icon, item):

			if self.project == key:
				print('No change')
				return

			self.change_project(key)

		return inner

	def change_project(self, new_key):

		# print(f'{self.project} -> {new_key}')
		self.project = new_key

		p, wp = self.get_project(new_key)

		icon_path = p.get_wp_icon(wp)

		icon = self.fallback_icon
		if icon_path is not None:
			icon = Image.open(icon_path)
		else:
			print('Icon fallback')

		self.tray.icon = icon

		info = p.get_id(wp)
		self.log_change(info)


	def log_change(self, info):
		time = datetime.now()
		time_fmt = time.strftime('%Y-%m-%d %H:%M:%S')

		log_text = f'{time_fmt} -- changed <{info}>'

		print(log_text)

		with open(self.logfile, 'at') as f:
			f.write(log_text + '\n')


	def quit(self, trigger = ''):
		def inner(icon, item):
			self.log_change(f'QUIT ({trigger})')
			self.tray.stop()

		return inner

class Project:
	def __init__(self, identifier, workpackages):
		self.id, self.name = get_id_name(identifier)
		self.icon = get_image_path(self.name)

		self.workpackages = OrderedDict()
		for wp in workpackages:
			wp_id, wp_name = get_id_name(wp)

			wp_icon = get_image_path(wp_name)

			# print(f'{wp_id}: {wp_name}, {wp_icon=}')

			self.workpackages[wp_id]= (wp_name, wp_icon)

	def get_wp_icon(self, key=None):
		if key in self.workpackages:
			icon = self.workpackages[key][1]
			return self.icon if icon is None else icon

		return self.icon

	def get_id(self, wp=None):
		if wp is None:
			if not self.workpackages:
				return self.id
			default_wp = next(iter(self.workpackages))
			return f'{self.id}:{default_wp}'

		return f'{self.id}:{wp}'

g_tray = None
def term_handler(signal, frame):
	if g_tray is None:
		return

	tray.quit('SIGTERM')(None, None)

if __name__ == '__main__':
	import argparse
	import signal
	import threading
	import json

	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('--logfile', default='prjtrx_events.log',
		type=Path, help='Path of logfile')
	parser.add_argument('config_file', type=Path, help='Path of config.json')

	args = parser.parse_args()

	conf_path = args.config_file
	if not conf_path.exists():
		print('Unable to load', conf_path)
		exit(1)

	with open(conf_path) as f:
		conf = json.load(f)

	def get_id_name(prj: str) -> tuple[str, str]:
		# splits project into id and name
		parts = prj.split('-')

		return (parts[0], parts[-1])


	projects = OrderedDict()
	for k, v in conf.items():
		p = Project(k, v)
		projects[p.id] = p

	#
	first_prj = next(iter(projects.values()))
	if len(first_prj.workpackages) > 1:
		first_wp = next(iter(first_prj.workpackages))
		default = (first_prj.id, first_wp)
	else:
		default = first_prj.name

	logfile = args.logfile
	# print(projects)
	tray = PrjTray(logfile, projects, default)

	g_tray = tray

	signal.signal(signal.SIGTERM, term_handler)


	try:
		th = threading.Thread(target=tray.tray.run)
		th.start()

		th.join()
	except KeyboardInterrupt:
		tray.quit('SIGINT')(None, None)
