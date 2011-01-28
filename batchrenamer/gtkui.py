#
# gtkui.py
#
# Copyright (C) 2011 Nathan Hoad <nathan@getoffmalawn.com>
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
# Copyright (C) 2010 Pedro Algarvio <pedro@algarvio.me>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#

import gtk
import re
import os

from deluge.log import LOG as log
from deluge.ui.client import client
from deluge.plugins.pluginbase import GtkPluginBase
import deluge.component as component
import deluge.common
from deluge.core.torrent import Torrent

from common import get_resource


class RenameFiles():
    """Class to wrap up the GUI and all filename processing functions"""
    def __init__(self, tor_id, files):
        self.tor_id = tor_id
        self.files = files

    def run(self):
        """Build the GUI and display it."""
        self.glade = gtk.glade.XML(get_resource("rename.glade"))
        self.window = self.glade.get_widget("RenameDialog")
        self.window.set_transient_for(component.get("MainWindow").window)
        self.template_field = self.glade.get_widget("filename_field")
        self.default_season_field = self.glade.get_widget("default_season")

        dic = {"on_ok_clicked": self.ok,
                "on_cancel_clicked": self.cancel}

        self.glade.signal_autoconnect(dic)

        self.build_tree_store()
        self.load_tree()
        treeview = self.glade.get_widget("treeview")
        treeview.expand_all()
        self.window.show()

    def enable_row(self, cell, path, model):
        """Enable a row and display the new name"""
        model[path][0] = not model[path][0]

        i = 0

        for child in model[path].iterchildren():
            i += 1
            child[0] = model[path][0]
            self.rename(child)

        if i > 0:
            if model[path][0]:
                model[path][3] = "Can't rename folders. Click to edit me manually!"
            else:
                model[path][3] = ""
        else:
            self.rename(model[path])

    def rename(self, row):
        """Clean the name, and try to add the season and episode info."""
        # pre-emptively try and find the season and episode numbers
        if row[0] and row[1]:
            default_season = self.default_season_field.get_value_as_int()
            season = None
            episode = None
            new_name = None

            old_name = row[2]

            # clean up the name
            new_name = self.clean(old_name)

            # try and extract season + episode numbering
            season, episode, new_name = self.parse_season_episode(new_name)

            # last resort, guess the episode number and use the default season
            if season is None:
                episode, name = self.guess(new_name)

                if episode:
                    new_name = name
                    season = default_season

            if len(self.template_field.get_text()) > 0:
                file_extension = os.path.splitext(old_name)[1]
                new_name = self.template_field.get_text() + file_extension

            new_name = new_name.replace('^s', 'S' + str(season).zfill(2))
            new_name = new_name.replace('^e', 'E' + str(episode).zfill(2))
            # annoying v2 tags still stick around, so get rid of them
            new_name = re.sub('\s?v\d\s?', '', new_name)

            row[3] = new_name
        elif row[0] and not row[1]:
            row[3] = "Can't rename folders. Click to edit me manually!"
        else:
            row[3] = ""

        for child in row.iterchildren():
            child[0] = row[0]
            self.rename(child)

    def clean(self, s):
        """Replace underscores with spaces, capitalise words and remove
        brackets and anything inbetween them.
        """
        opening_brackets = ['(', '[', '<', '{']
        closing_brackets = [')', ']', '>', '}']
        for i in range(len(opening_brackets)):
            b = opening_brackets[i]
            c = closing_brackets[i]

            while b in s:
                start = s.find(b)
                end = s.find(c) + 1

                s = re.sub(re.escape(s[start:end]), '', s)

        results = os.path.splitext(s)
        extension = results[1]
        s = results[0]

        s = s.replace('_', ' ')
        s = s.replace('.', ' ')
        s = s.strip()
        words = s.split(' ')
        s = ' '.join([w.capitalize() for w in words[:-1]])

        #results = os.path.splitext(words[-1])
        #words[-1] = results[0].upper()

        s += ' %s%s' % (words[-1], extension)

        #s += ' %s%s' % (words[-1], extension)

        return s

    def parse_season_episode(self, s):
        """Try and parse the season and episode numbers from the filename.

        Searches for both the SxxExx and SEE season/episode structures."""
        season = None
        episode = None

        results = re.search('S(\d+)E(\d+)', s)
        if results:
            s = re.sub('S(\d+)E(\d+)', '^s^e', s)
        else:
            results = re.search('(\d)(\d\d)', s)
            if results:
                s = re.sub('\d\d\d', '^s^e', s)

        if results:
            season = int(results.groups()[0])
            episode = int(results.groups()[1])

        return (season, episode, s)

    def guess(self, s):
        """This is called if nothing else has been found. Takes one last swoop.

        It assumes that the first number it finds is the episode number, and
        uses the default season number set by the user to set the season."""
        # plain old HOPE that's an episode number, not a TV show number.
        results = re.findall(r'\d+', s)
        words = s.split(' ')

        extension = os.path.splitext(s)[1]

        for w in words:
            r = re.search(r'(\d+)', w)

            if r:
                episode = r.groups()[0]
                i = words.index(w)
                s = ' '.join(words[:i] + ['^s^e'] + words[i + 1:])

                if i == len(words) - 1:
                    s += extension

                return episode, s

        return None, None

    def edit_row(self, cell, path, new_text):
        """Set the new name of folders to what was typed."""
        model = self.tree_store
        # this way you can only edit folders, not files.
        if not model[path][1]:
            self.tree_store[path][3] = new_text
            model[path][0] = True

    def build_tree_store(self):
        """Build the tree store to store data."""
        tree_store = gtk.TreeStore(bool, str, str, str)

        treeview = self.glade.get_widget("treeview")
        treeview.set_model(tree_store)

        enable_column = gtk.TreeViewColumn('Rename?')
        index = gtk.TreeViewColumn('Index')
        old_name = gtk.TreeViewColumn('Old Name')
        new_name = gtk.TreeViewColumn('New Name')

        cell = gtk.CellRendererText()
        cell.set_property('editable', True)
        cell.connect('edited', self.edit_row)

        bool_cell = gtk.CellRendererToggle()
        bool_cell.set_property('activatable', True)
        bool_cell.connect('toggled', self.enable_row, tree_store)

        enable_column.pack_start(bool_cell, False)
        index.pack_start(cell, False)
        old_name.pack_start(cell, False)
        new_name.pack_start(cell, False)

        enable_column.add_attribute(bool_cell, 'active', 0)
        index.add_attribute(cell, 'text', 1)
        old_name.add_attribute(cell, 'text', 2)
        new_name.add_attribute(cell, 'text', 3)

        treeview.append_column(enable_column)
        treeview.append_column(index)
        treeview.append_column(old_name)
        treeview.append_column(new_name)

        self.tree_store = tree_store

    def load_tree(self):
        """Load the tree store up with the file data."""
        structure = {0: []}
        parents = {}

        files = [(p['path'], p['index']) for p in self.files]

        real_parent = None
        for p, index in files:
            if os.path.basename(p) == p:
                structure[0].append(p)
                tree_store.append(None, [False, index, p, ''])

            else:
                parts = p.split('/')
                for i in range(len(parts)):
                    # make sure the depth exists
                    try:
                        structure[i]
                    except KeyError:
                        structure[i] = []

                    # prevents doubles of folders
                    if parts[i] not in structure[i]:
                        structure[i].append(parts[i])

                        try:
                            parent = parents[parts[i - 1]]
                        except KeyError:
                            parent = real_parent

                        # if this, we're adding the actual files, no folders
                        if os.path.basename(p) == parts[i]:
                            self.tree_store.append(parent, [False, index, parts[i], ''])
                        # still adding folders -_-
                        else:
                            result = self.tree_store.append(parent, [False, "", parts[i], ''])
                            parents[parts[i]] = result

    def ok(self, arg):
        """Process renaming, as the dialog was closed with OK"""
        self.window.hide()
        self.window.destroy()

        i = 0
        model = self.tree_store

        new_files = []
        try:
            base_name = ""
            while True:
                # only rename selected files
                result = self.get_new_name(model[i], base_name)

                if result:
                    new_files.extend(result)

                i += 1
        except IndexError:
            pass

        log.debug("New file names and indexes:")
        for index, f in new_files:
            log.debug("%d : %s" % (index, f))

        client.batchrenamer.rename_torrent_files(self.tor_id, new_files)

    def get_new_name(self, item, base_name):
        """Get the new name from model, and all it's children.

        Keyword arguments:
        item -- The item to retrieve new name info from.
        base_name -- the basename to prepend to new filenames.

        """
        new_files = []
        bad_name = "Can't rename folders. Click to edit me manually!"

        if item[0] and item[1]:
            name = os.path.join(base_name, item[3])
            index = item[1]
            t = [int(index), name]
            new_files.append(t)
        elif not item[1]:
            tmp_base_name = os.path.join(base_name, item[2])
            # if the folder has been renamed to a good name
            if item[3] != bad_name and item[3] != "":
                name = item[3]
                tmp_base_name = os.path.join(base_name, name)

            new_files.extend(self.get_child_names(tmp_base_name, item, bad_name))

        return new_files

    def cancel(self, arg=None):
        """Do nothing, the user doesn't want to rename :("""
        self.window.hide()
        self.window.destroy()

    def get_child_names(self, base_name, parent, bad_name):
        """Get all the new filenames of child elements of the treestore.

        Keyword arguments:
        base_name -- the basename (folder path) to prepend to each filename.
        parent -- the parent to get the children from.
        bad_name -- if this string is found, this item won't be renamed (for folders).

        """
        new_files = []
        for child in parent.iterchildren():
            result = self.get_new_name(child, base_name)

            if result:
                new_files.extend(result)

        return new_files


class GtkUI(GtkPluginBase):
    def enable(self):
        self.glade = gtk.glade.XML(get_resource("config.glade"))

        component.get("Preferences").add_page("BatchRenamer", self.glade.get_widget("batch_prefs"))

        # add the MenuItem to the context menu.
        torrentmenu = component.get("MenuBar").torrentmenu
        self.menu_item = gtk.ImageMenuItem("Rename Torrent")

        img = gtk.image_new_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_MENU)
        self.menu_item.set_image(img)
        self.menu_item.connect("activate", self.rename_selected_torrent)
        torrentmenu.append(self.menu_item)
        torrentmenu.show_all()

    def disable(self):
        component.get("Preferences").remove_page("BatchRenamer")
        component.get("MenuBar").torrentmenu.remove(self.menu_item)

    def rename_selected_torrent(self, arg):
        torrent_id = component.get("TorrentView").get_selected_torrent()
        client.batchrenamer.get_torrent_files(torrent_id).addCallback(self.build_dialog)

    def build_dialog(self, result):
        """Display the dialog using the torrent ID and files."""
        tor_id = result[0]
        files = result[1]
        r = RenameFiles(tor_id, files)
        r.run()
