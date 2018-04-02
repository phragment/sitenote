#!/usr/bin/env python3

# Copyright 2017-2018 Thomas Krug
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import configparser
import io
import os
import re
import shutil
import sys

import docutils
import docutils.core

from docutils.parsers.rst import Directive
import docutils.nodes
from docutils.parsers.rst import directives


# TODO
# - images
#  strip big image exif
#  create thumbnails
# - manipulate image links
#  image and external links should open in new tab (<a target= href= >)
# - create feed (atom)


class Overview(Directive):

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = False

    def run(self):
        # how to get current dir?
        d = self.arguments[0]

        art = crawl(d)

        # sort by date
        art = sorted(art, key=lambda k: k["date"], reverse=True)

        nodes = []
        for a in art:
            entry = docutils.nodes.section()

            title = docutils.nodes.title()
            link = docutils.nodes.reference()
            link += docutils.nodes.Text(a["title"])
            link["refuri"] = a["link"]
            title += link
            entry += title

            if a["desc"]:
                for (i, child) in enumerate(a["desc"].children):
                    if child.tagname == "title":
                        del a["desc"].children[i]
                entry += a["desc"]

            nodes.append(entry)

        return nodes


def crawl(d):
    infos = []

    for e in os.listdir(d):
        fp = os.path.join(d, e)
        if os.path.isdir(fp):
            fp = os.path.join(fp, "index.rst")
            rst_f = open(fp, "r")
            rst = rst_f.read()
            rst_f.close()
            dtree = get_dtree(rst)
            info = get_info(dtree)
            info["link"] = fp
            infos.append(info)

    # create feed
    # TODO

    return infos


def get_info(dtree):
    title = None
    date = ""
    desc = None

    for elem in dtree.traverse(siblings=True):
        if elem.tagname == "document":
            title = elem.get("title", "")
        if elem.tagname == "docinfo":
            if elem.children[0].tagname == "date":
                date = str( elem.children[0].children[0] )
        if elem.tagname == "topic":
            # save dtree elements
            desc = elem

    data = {"title": title, "date": date, "desc": desc}
    return data



head = '''<head>
<link rel="shortcut icon" href="/favicon.ico" type="image/ico">
<meta name="viewport" content="width=device-width, initial-scale=1">'''

def prep(conf):

    rst_fp = "header.rst"
    try:
        rst_f = open(rst_fp, "r")
    except FileNotFoundError:
        return None
    rst = rst_f.read()
    rst_f.close()
    header = render(rst, conf, "")
    header = re.search(r'<div class=\"document\">([\W\S]*)</div>', header, re.M).group(1)
    header = '<div class="header">' + header + "</div>"
    return header


def get_dtree(rst):

    try:
        with devnull():
            dtree = docutils.core.publish_doctree(rst)
    except docutils.utils.SystemMessage as e:
        print("error parsing rst")
        print(e)
        return None

    return dtree


def render(rst, conf, header):

    args = {
        "stylesheet_path": "",
        "stylesheet": "/default.css",
        "embed_stylesheet": False
    }

    # abs
    if args["stylesheet"].startswith("/"):
        args["stylesheet"] = conf["root"] + args["stylesheet"]

    dtree = get_dtree(rst)
    #print(dtree)
    dtree = dtree_prep(dtree, conf)

    try:
        with devnull():
            html = docutils.core.publish_from_doctree(dtree,
                       writer_name="html4css1",
                       settings=None,
                       settings_overrides=args)
    except docutils.utils.SystemMessage as e:
        print("error generating html")
        print(e)
        return None
    except AttributeError as e:
        print("error generating html")
        print(e)
        return None

    html = html.decode()
    html = re.sub(r'<head>', head, html)

    if header:
        html = re.sub(r'<body>', "<body>" + header, html)

    return html


def dtree_prep(dtree, conf):

    for elem in dtree.traverse(siblings=True):
        if elem.tagname == "reference":
            try:
                refuri = elem["refuri"]
            except KeyError:
                continue
            if refuri.endswith(".rst"):
                elem["refuri"] = refuri.replace(".rst", ".html")

            # abs
            if refuri.startswith("/"):
                elem["refuri"] = conf["root"] + elem["refuri"]


        if elem.tagname == "image":
            try:
                uri = elem["uri"]
            except KeyError:
                continue

            # abs
            if uri.startswith("/"):
                elem["uri"] = conf["root"] + uri

        if elem.tagname == "document":
            title = elem.get("title", "")
            if title:
                elem["title"] = conf["title"] + " - " + elem["title"]
            else:
                elem["title"] = conf["title"]

    return dtree


class devnull():
    def __init__(self):
        self.devnull = io.StringIO()

    def __enter__(self):
        sys.stdout = self.devnull
        sys.stderr = self.devnull

    def __exit__(self, type, value, traceback):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


def mkdir(fp):

    # behaves like "mkdir -p"
    try:
        os.makedirs(os.path.dirname(fp))
    except FileExistsError:
        pass


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("dirrst", help="input", nargs="?", default="rst")
    parser.add_argument("dirout", help="output", nargs="?", default="www")
    args = parser.parse_args()

    dirrst = os.path.abspath(args.dirrst)
    dirout = os.path.abspath(args.dirout)


    # read config
    parser = configparser.ConfigParser()
    parser.read("sitenote.conf")
    conf = dict(parser["site"])
    print(conf)

    # FIXME
    dirout = dirout + conf["root"]


    os.chdir(dirrst)

    #
    directives.register_directive("overview", Overview)

    header = prep(conf)

    for cd, subdirs, files in os.walk("./"):

        print(cd, subdirs, files)

        for f in files:

            if f.startswith("."):
                continue

            if f.endswith(".rst"):

                print("")

                # rel
                rst_fp = os.path.join(cd, f)
                print("convert", rst_fp)
                rst_f = open(rst_fp, "r")
                rst = rst_f.read()
                rst_f.close()

                html = render(rst, conf, header)

                # abs
                html_fp = os.path.join(dirout, rst_fp[:-4] + ".html")
                html_fp = os.path.normpath(html_fp)

                print(html_fp)

                mkdir(html_fp)

                html_f = open(html_fp, "w")
                html_f.write(html)
                html_f.close()

            else:

                src = os.path.join(cd, f)
                dst = os.path.join(dirout, src)
                dst = os.path.normpath(dst)

                mkdir(dst)
                shutil.copy(src, dst)

