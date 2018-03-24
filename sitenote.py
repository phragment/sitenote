#!/usr/bin/env python3

# Copyright 2017 Thomas Krug
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
import docutils.nodes


# TODO
# - images
#  strip big image exif
#  create thumbnails
# - manipulate image links
#  image and external links should open in new tab (<a target= href= >)
# - add directive
#  overview page for articles
# - create rss feed

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


def render(rst, conf, header):

    args = {
        "stylesheet_path": "",
        "stylesheet": "/default.css",
        "embed_stylesheet": False
    }

    # abs
    if args["stylesheet"].startswith("/"):
        args["stylesheet"] = conf["root"] + args["stylesheet"]

    with devnull():
        try:
            dtree = docutils.core.publish_doctree(rst)
        except docutils.utils.SystemMessage as e:
            print("error parsing rst")
            print(e)
            return None

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

    header = prep(conf)

    for cd, subdirs, files in os.walk("./"):

        print(cd, subdirs, files)

        for f in files:

            if f.startswith("."):
                continue

            if f.endswith(".rst"):

                print("convert", f)

                # rel
                rst_fp = os.path.join(cd, f)
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


