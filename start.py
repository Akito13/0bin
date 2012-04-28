# -*- coding: utf-8 -*-

"""
    Main script including controller, rooting, dependancy management, and
    server run.
"""

import os
import hashlib
import thread
import time
import tempfile
import glob

from datetime import datetime, timedelta

from src import settings, setup_path, Paste

setup_path()

from privilege import drop_privileges_permanently, coerce_user, coerce_group

from bottle import (Bottle, route, run, abort,
                    static_file, debug, view, request)


app = Bottle()


@app.route('/')
@view('home')
def index():
    return {}


@app.route('/paste/create', method='POST')
def create_paste():

    try:
        content = unicode(request.forms.get('content', ''), 'utf8')
    except UnicodeDecodeError:
        return {'status': 'error',
                'message': u"Encoding error: the paste couldn't be saved."}

    if content:
        expiration = request.forms.get('expiration', u'burn_after_reading')
        paste = Paste(expiration=expiration, content=content)
        paste.save()
        return {'status': 'ok',
                'paste': paste.uuid}

    return {'status': 'error',
            'message': u"Serveur error: the paste couldn't be saved. Please try later."}


@app.route('/paste/:paste_id')
@view('paste')
def display_paste(paste_id):

    now = datetime.now()
    keep_alive = False
    try:
        paste = Paste.load(paste_id)
        # Delete the paste if it expired:
        if 'burn_after_reading' in str(paste.expiration):
            # burn_after_reading contains the paste creation date
            # if this read appends 10 seconds after the creation date
            # we don't delete the paste because it means it's the redirection
            # to the paste that happens during the paste creation
            try:
                keep_alive = paste.expiration.split('#')[1]
                keep_alive = datetime.strptime(keep_alive,'%Y-%m-%d %H:%M:%S.%f')
                keep_alive = now < keep_alive + timedelta(seconds=10)
            except IndexError:
                keep_alive = False
            if not keep_alive:
                paste.delete()

        elif paste.expiration < now:
            paste.delete()
            raise ValueError()

    except (TypeError, ValueError):
        abort(404, u"This paste doesn't exist or has expired")

    return {'paste': paste, 'keep_alive': keep_alive}


@app.route('/static/<filename:path>')
def server_static(filename):
    return static_file(filename, root=settings.STATIC_FILES_ROOT)


if __name__ == "__main__":

    def drop_privileges():
        time.sleep(5)
        if settings.USER:
            settings.GROUP = settings.GROUP or settings.USER
            try:
                user = coerce_user(settings.USER)
                group = coerce_group(settings.GROUP)

                lock_files =  glob.glob(os.path.join(tempfile.gettempdir(),
                                                     'bottle.*.lock'))
                for lock_file in lock_files:
                    os.chown(lock_file, user, group)

                drop_privileges_permanently(settings.USER, settings.GROUP, ())
            except Exception:
                print "Failed to drop privileges. Running with current user."

    thread.start_new_thread(drop_privileges, ())

    if settings.DEBUG:
        debug(True)
        run(app, host=settings.DEV_HOST, port=settings.DEV_PORT,
                 reloader=True, server="cherrypy")
    else:
        run(app, host=settings.PROD_HOST,
            port=settings.PROD_PORT, server="cherrypy")


