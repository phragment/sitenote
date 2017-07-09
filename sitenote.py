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
import io
import os
import re
import shutil
import sys

import docutils
import docutils.core


head = '<head><meta name="viewport" content="width=device-width, initial-scale=1">'

css = '''<style type="text/css">
body {
  /* text color, very dark */
  color: #212526;
  /* background color, dark */
  background-color: #414A4C;
}
a {
  color: #6d7993;
}
div.document {
  /* text box background, light grey tone */
  background-color: #f5f5f5;
  padding: 18px;
  border-radius: 18px;
  max-width: 800px;
  margin: 0 auto;
}
h1.title {
  /* padding-top: 20px; */
  font-size: 220%;
  text-align: center;
  color: #59434B;
}
h2.subtitle {
  font-size: 180%;
  text-align: center;
  color: #59434B;
  padding-bottom: 20px;
}
div.section h1 {
  padding-top: 10px;
  font-size: 140%;
}
div.section h2 {
  padding-top: 10px;
  font-size: 120%;
}
img {
  display: block;
  margin: 0 auto;
  max-width: 100%;
  max-height: 100%;
}
.docutils {
  display: none;
}
</style>'''


def render(rst):

    args = {
        "embed_stylesheet": True,
        "output_encoding": "unicode"
    }

    with devnull():
        try:
            dtree = docutils.core.publish_doctree(rst)
        except docutils.utils.SystemMessage as e:
            print("error parsing rst")
            print(e)

    dtree = dtree_prep(dtree)

    with devnull():
        try:
            html = docutils.core.publish_from_doctree(dtree, writer_name="html4css1", settings=None, settings_overrides=args)
        except docutils.utils.SystemMessage as e:
            print("error generating html")
            print(e)
        except AttributeError as e:
            print("error generating html")
            print(e)

    html = re.sub(r'<head>', head, html)
    html = re.sub(r'<style\ type=\"text\/css\">[\W\S]*</style>', css, html, re.M)

    return html


def dtree_prep(dtree):

    for elem in dtree.traverse(siblings=True):
        if elem.tagname == "reference":
            try:
                refuri = elem["refuri"]
            except KeyError:
                continue
            if refuri.endswith(".rst"):
                elem["refuri"] = refuri.replace(".rst", ".html")

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
    parser.add_argument("dirrst", help="input", nargs="?", default="demo")
    parser.add_argument("dirout", help="output", nargs="?", default="out")
    args = parser.parse_args()

    dirrst = os.path.abspath(args.dirrst)
    dirout = os.path.abspath(args.dirout)


    os.chdir(dirrst)

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

                html = render(rst)

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


