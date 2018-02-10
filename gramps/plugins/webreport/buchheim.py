# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2007       Johan Gonqvist <johan.gronqvist@gmail.com>
# Copyright (C) 2007-2009  Gary Burton <gary.burton@zen.co.uk>
# Copyright (C) 2007-2009  Stephane Charette <stephanecharette@gmail.com>
# Copyright (C) 2008-2009  Brian G. Matherly
# Copyright (C) 2008       Jason M. Simanek <jason@bohemianalps.com>
# Copyright (C) 2008-2011  Rob G. Healey <robhealey1@gmail.com>
# Copyright (C) 2010       Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2010,2015  Serge Noiraud
# Copyright (C) 2011       Tim G L Lyons
# Copyright (C) 2013       Benny Malengier
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

#------------------------------------------------
# GRAMPS module
#------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#------------------------------------------------
# Set up logging
#------------------------------------------------
import logging
log = logging.getLogger(".NarrativeWeb.BuchheimTree")


#------------------------------------------------------------
#
# DrawTree - a Buchheim draw tree which implements the
#   tree drawing algorithm of:
#
#   Improving Walker's algorithm to Run in Linear Time
#   Christoph Buchheim, Michael Juenger, and Sebastian Leipert
#
#   Also see:
#
#   Positioning Nodes for General Trees
#   John Q. Walker II
#
# The following modifications are noted:
#
# - The root node is 'west' according to the later nomenclature
#   employed by Walker with the nodes stretching 'east'
# - This reverses the X & Y co-originates of the Buchheim paper
# - The algorithm has been tweaked to track the maximum X and Y
#   as 'width' and 'height' to aid later layout
# - The Buchheim examples track a string identifying the actual
#   node but this implementation tracks the handle of the
#   DB node identifying the person in the Grams DB.  This is done
#   to minimize occupancy at any one time.
#------------------------------------------------------------
class DrawTree(object):
    def __init__(self, tree, parent=None, depth=0, number=1):
        self.x = -1.
        self.y = depth
        self.width = self.x
        self.height = self.y
        self.tree = tree
        self.children = [DrawTree(c, self, depth+1, i+1)
                         for i, c
                         in enumerate(tree.children)]
        self.parent = parent
        self.thread = None
        self.mod = 0
        self.ancestor = self
        self.change = self.shift = 0
        self._lmost_sibling = None
        #this is the number of the node in its group of siblings 1..n
        self.number = number

    def left(self):
        return self.thread or len(self.children) and self.children[0]

    def right(self):
        return self.thread or len(self.children) and self.children[-1]

    def lbrother(self):
        n = None
        if self.parent:
            for node in self.parent.children:
                if node == self:
                    return n
                else:
                    n = node
        return n

    def get_lmost_sibling(self):
        if not self._lmost_sibling and self.parent and self != \
                self.parent.children[0]:
            self._lmost_sibling = self.parent.children[0]
        return self._lmost_sibling
    lmost_sibling = property(get_lmost_sibling)

    def __str__(self):
        return ("%s: x=%s mod=%s" % (self.tree, self.x, self.mod))

    def __repr__(self):
        return self.__str__()


def buchheim(tree, node_width, h_separation, node_height, v_separation):
    """
    Calculate the position of elements of the graph given a minimum
    generation width separation and minimum generation height separation.
    """
    dt = firstwalk(DrawTree(tree), node_height, v_separation)
    min = second_walk(dt, 0, node_width+h_separation, 0)
    if min < 0:
        third_walk(dt, -min)

    return dt


def third_walk(tree, n):
    tree.x += n
    tree.width = max(tree.width, tree.x)
    for c in tree.children:
        third_walk(c, n)


def firstwalk(v, node_height=1., v_separation=1.):
    """
    Determine horizontal positions.
    """
    if len(v.children) == 0:
        if v.lmost_sibling:
            v.y = v.lbrother().y + v_separation
        else:
            v.y = 0.
    else:
        default_ancestor = v.children[0]
        for w in v.children:
            firstwalk(w, node_height, v_separation)
            default_ancestor = apportion(w, default_ancestor, v_separation)
            v.height = max(v.height, w.height)
            assert v.width >= w.width
        # print "finished v =", v.tree, "children"
        execute_shifts(v)

        midpoint = (v.children[0].y + v.children[-1].y) / 2

        w = v.lbrother()
        if w:
            v.y = w.y + v_separation
            v.mod = v.y - midpoint
        else:
            v.y = midpoint

    assert v.width >= v.x
    v.height = max(v.height, v.y)
    return v


def apportion(v, default_ancestor, v_separation):
    w = v.lbrother()
    if w is not None:
        #in buchheim notation:
        #i == inner; o == outer; r == right; l == left; r = +; l = -
        vir = vor = v
        vil = w
        vol = v.lmost_sibling
        sir = sor = v.mod
        sil = vil.mod
        sol = vol.mod
        while vil.right() and vir.left():
            vil = vil.right()
            vir = vir.left()
            vol = vol.left()
            vor = vor.right()
            vor.ancestor = v
            shift = (vil.y + sil) - (vir.y + sir) + v_separation
            if shift > 0:
                move_subtree(ancestor(vil, v, default_ancestor), v, shift)
                sir = sir + shift
                sor = sor + shift
            sil += vil.mod
            sir += vir.mod
            sol += vol.mod
            sor += vor.mod
        if vil.right() and not vor.right():
            vor.thread = vil.right()
            vor.mod += sil - sor
        else:
            if vir.left() and not vol.left():
                vol.thread = vir.left()
                vol.mod += sir - sol
            default_ancestor = v
    return default_ancestor


def move_subtree(wl, wr, shift):
    subtrees = wr.number - wl.number
    # print wl.tree, "is conflicted with", wr.tree, 'moving',
    # subtrees, 'shift', shift
    # print wl, wr, wr.number, wl.number, shift, subtrees, shift/subtrees
    wr.change -= shift / subtrees
    wr.shift += shift
    wl.change += shift / subtrees
    wr.y += shift
    wr.mod += shift
    wr.height = max(wr.height, wr.y)


def execute_shifts(v):
    shift = change = 0
    for w in v.children[::-1]:
        # print "shift:", w, shift, w.change
        w.y += shift
        w.mod += shift
        change += w.change
        shift += w.shift + change
        w.height = max(w.height, w.y)
        v.height = max(v.height, w.height)


def ancestor(vil, v, default_ancestor):
    """
    The relevant text is at the bottom of page 7 of
    Improving Walker's Algorithm to Run in Linear Time" by Buchheim et al
    """
    if vil.ancestor in v.parent.children:
        return vil.ancestor
    else:
        return default_ancestor


def second_walk(v, modifier=0, h_separation=0, width=0, min=None):
    """
    Note that some of this code is modified to orientate the root node 'west'
    instead of 'north' in the Bushheim algorithms.
    """
    v.y -= modifier
    v.x -= width

    if min is None or v.x < min:
        min = v.x

    for w in v.children:
        min = second_walk(
            w, modifier + v.mod, h_separation, width + h_separation, min)
        v.width = max(v.width, w.width)
        v.height = max(v.height, w.height)

    v.width = max(v.width, v.x)
    v.height = max(v.height, v.y)
    return min
