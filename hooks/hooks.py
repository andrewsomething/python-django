#!/usr/bin/env python
# vim: et ai ts=4 sw=4:

import json
import os
import re
import subprocess
import sys
import time
from pwd import getpwnam
from grp import getgrnam
from random import choice

CHARM_PACKAGES = ["python-pip", "python-jinja2", "mercurial", "git-core", "subversion", "bzr"]

INJECTED_WARNING = """
#------------------------------------------------------------------------------
# The following is the import code for the settings directory injected by Juju
#------------------------------------------------------------------------------
"""


###############################################################################
# Supporting functions
###############################################################################
MSG_CRITICAL = "CRITICAL"
MSG_DEBUG = "DEBUG"
MSG_INFO = "INFO"
MSG_ERROR = "ERROR"
MSG_WARNING = "WARNING"


def juju_log(level, msg):
    subprocess.call(['juju-log', '-l', level, msg])

#------------------------------------------------------------------------------
# run: Run a command, return the output
#------------------------------------------------------------------------------
def run(command, exit_on_error=True, cwd=None):
    try:
        juju_log(MSG_DEBUG, command)
        return subprocess.check_output(
            command, stderr=subprocess.STDOUT, shell=True, cwd=cwd)
    except subprocess.CalledProcessError, e:
        juju_log(MSG_ERROR, "status=%d, output=%s" % (e.returncode, e.output))
        if exit_on_error:
            sys.exit(e.returncode)
        else:
            raise


#------------------------------------------------------------------------------
# install_file: install a file resource. overwites existing files.
#------------------------------------------------------------------------------
def install_file(contents, dest, owner="root", group="root", mode=0600):
    uid = getpwnam(owner)[2]
    gid = getgrnam(group)[2]
    dest_fd = os.open(dest, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, mode)
    os.fchown(dest_fd, uid, gid)
    with os.fdopen(dest_fd, 'w') as destfile:
        destfile.write(str(contents))


#------------------------------------------------------------------------------
# install_dir: create a directory
#------------------------------------------------------------------------------
def install_dir(dirname, owner="root", group="root", mode=0700):
    command = \
    '/usr/bin/install -o {} -g {} -m {} -d {}'.format(owner, group, oct(mode),
        dirname)
    return run(command)

#------------------------------------------------------------------------------
# config_get:  Returns a dictionary containing all of the config information
#              Optional parameter: scope
#              scope: limits the scope of the returned configuration to the
#                     desired config item.
#------------------------------------------------------------------------------
def config_get(scope=None):
    try:
        config_cmd_line = ['config-get']
        if scope is not None:
            config_cmd_line.append(scope)
        config_cmd_line.append('--format=json')
        config_data = json.loads(subprocess.check_output(config_cmd_line))
    except:
        config_data = None
    finally:
        return(config_data)


#------------------------------------------------------------------------------
# relation_json:  Returns json-formatted relation data
#                Optional parameters: scope, relation_id
#                scope:        limits the scope of the returned data to the
#                              desired item.
#                unit_name:    limits the data ( and optionally the scope )
#                              to the specified unit
#                relation_id:  specify relation id for out of context usage.
#------------------------------------------------------------------------------
def relation_json(scope=None, unit_name=None, relation_id=None):
    command = ['relation-get', '--format=json']
    if relation_id is not None:
        command.extend(('-r', relation_id))
    if scope is not None:
        command.append(scope)
    else:
        command.append('-')
    if unit_name is not None:
        command.append(unit_name)
    output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    return output or None


#------------------------------------------------------------------------------
# relation_get:  Returns a dictionary containing the relation information
#                Optional parameters: scope, relation_id
#                scope:        limits the scope of the returned data to the
#                              desired item.
#                unit_name:    limits the data ( and optionally the scope )
#                              to the specified unit
#------------------------------------------------------------------------------
def relation_get(scope=None, unit_name=None, relation_id=None):
    j = relation_json(scope, unit_name, relation_id)
    if j:
        return json.loads(j)
    else:
        return None


def relation_set(keyvalues, relation_id=None):
    args = []
    if relation_id:
        args.extend(['-r', relation_id])
    args.extend(["{}='{}'".format(k, v or '') for k, v in keyvalues.items()])
    run("relation-set {}".format(' '.join(args)))

    ## Posting json to relation-set doesn't seem to work as documented?
    ## Bug #1116179
    ##
    ## cmd = ['relation-set']
    ## if relation_id:
    ##     cmd.extend(['-r', relation_id])
    ## p = Popen(
    ##     cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    ##     stderr=subprocess.PIPE)
    ## (out, err) = p.communicate(json.dumps(keyvalues))
    ## if p.returncode:
    ##     juju_log(MSG_ERROR, err)
    ##     sys.exit(1)
    ## juju_log(MSG_DEBUG, "relation-set {}".format(repr(keyvalues)))


def relation_list(relation_id=None):
    """Return the list of units participating in the relation."""
    if relation_id is None:
        relation_id = os.environ['JUJU_RELATION_ID']
    cmd = ['relation-list', '--format=json', '-r', relation_id]
    json_units = subprocess.check_output(cmd).strip()
    if json_units:
        return json.loads(subprocess.check_output(cmd))
    return []


#------------------------------------------------------------------------------
# relation_ids:  Returns a list of relation ids
#                optional parameters: relation_type
#                relation_type: return relations only of this type
#------------------------------------------------------------------------------
def relation_ids(relation_types=('db',)):
    # accept strings or iterators
    if isinstance(relation_types, basestring):
        reltypes = [relation_types, ]
    else:
        reltypes = relation_types
    relids = []
    for reltype in reltypes:
        relid_cmd_line = ['relation-ids', '--format=json', reltype]
        json_relids = subprocess.check_output(relid_cmd_line).strip()
        if json_relids:
            relids.extend(json.loads(json_relids))
    return relids


#------------------------------------------------------------------------------
# relation_get_all:  Returns a dictionary containing the relation information
#                optional parameters: relation_type
#                relation_type: limits the scope of the returned data to the
#                               desired item.
#------------------------------------------------------------------------------
def relation_get_all(*args, **kwargs):
    relation_data = []
    relids = relation_ids(*args, **kwargs)
    for relid in relids:
        units_cmd_line = ['relation-list', '--format=json', '-r', relid]
        json_units = subprocess.check_output(units_cmd_line).strip()
        if json_units:
            for unit in json.loads(json_units):
                unit_data = \
                    json.loads(relation_json(relation_id=relid,
                        unit_name=unit))
                for key in unit_data:
                    if key.endswith('-list'):
                        unit_data[key] = unit_data[key].split()
                unit_data['relation-id'] = relid
                unit_data['unit'] = unit
                relation_data.append(unit_data)
    return relation_data

def apt_get_update():
    cmd_line = ['apt-get', 'update']
    return(subprocess.call(cmd_line))


#------------------------------------------------------------------------------
# apt_get_install( packages ):  Installs package(s)
#------------------------------------------------------------------------------
def apt_get_install(packages=None):
    if packages is None:
        return(False)
    cmd_line = ['apt-get', '-y', 'install', '-qq']
    if isinstance(packages, list):
        cmd_line.extend(packages)
    else:
        cmd_line.append(packages)
    return(subprocess.call(cmd_line))


#------------------------------------------------------------------------------
# pip_install( package ):  Installs a python package
#------------------------------------------------------------------------------
def pip_install(packages=None, upgrade=False):
    # Build in /tmp or Juju's internal git will be confused
    cmd_line = ['pip', 'install', '-b', '/tmp/']
    if packages is None:
        return(False)
    if upgrade:
        cmd_line.append('--upgrade')
    if packages.startswith('svn+') or packages.startswith('git+') or \
       packages.startswith('hg+') or packages.startswith('bzr+'):
        cmd_line.append('-e')
    cmd_line.append(packages)
    cmd_line.append('--use-mirrors')
    return(subprocess.call(cmd_line))

#------------------------------------------------------------------------------
# pip_install_req( path ):  Installs a requirements file
#------------------------------------------------------------------------------
def pip_install_req(path=None, upgrade=False):
    # Build in /tmp or Juju's internal git will be confused
    cmd_line = ['pip', 'install', '-b', '/tmp/']
    if path is None:
        return(False)
    if upgrade:
        cmd_line.append('--upgrade')
    cmd_line.append('-r')
    cmd_line.append(path)
    cwd = os.path.dirname(path)
    cmd_line.append('--use-mirrors')
    return(subprocess.call(cmd_line, cwd=cwd))

#------------------------------------------------------------------------------
# open_port:  Convenience function to open a port in juju to
#             expose a service
#------------------------------------------------------------------------------
def open_port(port=None, protocol="TCP"):
    if port is None:
        return(None)
    return(subprocess.call(['open-port', "%d/%s" %
        (int(port), protocol)]))


#------------------------------------------------------------------------------
# close_port:  Convenience function to close a port in juju to
#              unexpose a service
#------------------------------------------------------------------------------
def close_port(port=None, protocol="TCP"):
    if port is None:
        return(None)
    return(subprocess.call(['close-port', "%d/%s" %
        (int(port), protocol)]))


#------------------------------------------------------------------------------
# update_service_ports:  Convenience function that evaluate the old and new
#                        service ports to decide which ports need to be
#                        opened and which to close
#------------------------------------------------------------------------------
def update_service_port(old_service_port=None, new_service_port=None):
    if old_service_port is None or new_service_port is None:
        return(None)
    if new_service_port != old_service_port:
        close_port(old_service_port)
        open_port(new_service_port)

#
# Utils
#

def install_or_append(contents, dest, owner="root", group="root", mode=0600):
    if os.path.exists(dest):
        uid = getpwnam(owner)[2]
        gid = getgrnam(group)[2]
        dest_fd = os.open(dest, os.O_APPEND, mode)
        os.fchown(dest_fd, uid, gid)
        with os.fdopen(dest_fd, 'a') as destfile:
            destfile.write(str(contents))
    else:
        install_file(contents, dest, owner, group, mode)

def token_sql_safe(value):
    # Only allow alphanumeric + underscore in database identifiers
    if re.search('[^A-Za-z0-9_]', value):
        return False
    return True

def sanitize(s):
    s = s.replace(':', '_')
    s = s.replace('-', '_')
    s = s.replace('/', '_')
    s = s.replace('"', '_')
    s = s.replace("'", '_')
    return s

def user_name(relid, remote_unit, admin=False, schema=False):
    components = [sanitize(relid), sanitize(remote_unit)]
    if admin:
        components.append("admin")
    elif schema:
        components.append("schema")
    return "_".join(components)

def get_relation_host():
    remote_host = run("relation-get ip")
    if not remote_host:
        # remote unit $JUJU_REMOTE_UNIT uses deprecated 'ip=' component of
        # interface.
        remote_host = run("relation-get private-address")
    return remote_host


def get_unit_host():
    this_host = run("unit-get private-address")
    return this_host.strip()

def process_template(template_name, template_vars, destination):
    # --- exported service configuration file
    from jinja2 import Environment, FileSystemLoader
    template_env = Environment(
        loader=FileSystemLoader(os.path.join(os.environ['CHARM_DIR'],
        'templates')))

    template = \
        template_env.get_template(template_name).render(template_vars)

    with open(destination, 'w') as inject_file:
        inject_file.write(str(template))

def configure_and_install(rel):

    def _import_key(id):
        cmd = "apt-key adv --keyserver keyserver.ubuntu.com " \
              "--recv-keys %s" % id
        try:
            subprocess.check_call(cmd.split(' '))
        except:
            juju_log(MSG_ERROR, "Error importing repo key %s" % id)

    if rel == 'distro':
        return apt_get_install("python-django")
    elif rel[:4] == "ppa:":
        src = rel
        subprocess.check_call(["add-apt-repository", "-y", src])

        return apt_get_install("python-django")
    elif rel[:3] == "deb":
        l = len(rel.split('|'))
        if l ==  2:
            src, key = rel.split('|')
            juju_log("Importing PPA key from keyserver for %s" % src)
            _import_key(key)
        elif l == 1:
            src = rel
        else:
            juju_log(MSG_ERROR, "Invalid django-release: %s" % rel)

        with open('/etc/apt/sources.list.d/juju_python_django_deb.list', 'w') as f:
            f.write(src)

        return apt_get_install("python-django")
    elif rel == '':
        return pip_install('Django')
    else:
        return pip_install(rel)

#
# from:
#   http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
#
def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, program)
        if is_exe(exe_file):
            return exe_file

    return False

def find_django_admin_cmd():
    for cmd in ['django-admin.py', 'django-admin']:
        django_admin_cmd = which(cmd)
        if django_admin_cmd:
            return django_admin_cmd

    juju_log(MSG_ERROR, "No django-admin executable found.")

def append_template(template_name, template_vars, path, try_append=False):

    # --- exported service configuration file
    from jinja2 import Environment, FileSystemLoader
    template_env = Environment(
        loader=FileSystemLoader(os.path.join(os.environ['CHARM_DIR'],
        'templates')))

    template = \
        template_env.get_template(template_name).render(template_vars)

    append = False
    if os.path.exists(path):
        with open(path, 'r') as inject_file:
            if not str(template) in inject_file:
                append = True
    else:       
        append = True
        
    if append == True:
        with open(path, 'a') as inject_file:
            inject_file.write(INJECTED_WARNING)
            inject_file.write(str(template))



###############################################################################
# Hook functions
###############################################################################
def install():

    for retry in xrange(0,24):
        if apt_get_install(CHARM_PACKAGES):
            time.sleep(10)
        else:
            break

    configure_and_install(django_version)

    django_admin_cmd = find_django_admin_cmd()
            
    if extra_deb_pkgs:
        apt_get_install(extra_deb_pkgs.split(','))

    if extra_pip_pkgs:
        for package in extra_pip_pkgs.split(','):
            pip_install(package)

    if repos_username:
        m = re.match(".*://([^/]+)/.*", repos_url)
        if m is not None:
            repos_domain = m.group(1)
            template_vars = {
                'repos_domain': repos_domain,
                'repos_username': repos_username,
                'repos_password': repos_password
            }
            from os.path import expanduser
            process_template('netrc.tmpl', template_vars, expanduser('~/.netrc'))
        else:
            juju_log(MSG_ERROR, '''Failed to process repos_username and repos_password:\n
                                   cannot identify domain in URL {0}'''.format(repos_url))
        
    if vcs == 'hg' or vcs == 'mercurial':
        run('hg clone %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'git' or vcs == 'git-core':
        if repos_branch:
            run('git clone %s -b %s %s' % (repos_url, repos_branch, vcs_clone_dir))
        else:
            run('git clone %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'bzr' or vcs == 'bazaar':
        run('bzr branch %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'svn' or vcs == 'subversion':
        run('svn co %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == '' and repos_url == '':
        juju_log(MSG_INFO, "No version control using django-admin startproject")
        cmd = '%s startproject' % django_admin_cmd
        if project_template_url:
            cmd = " ".join([cmd, '--template', project_template_url])
        if project_template_extension:
            cmd = " ".join([cmd, '--extension', project_template_extension])
        try:
            run('%s %s %s' % (cmd, sanitized_unit_name, install_root), exit_on_error=False)
        except subprocess.CalledProcessError:
            run('%s %s' % (cmd, sanitized_unit_name), cwd=install_root)

    else:
        juju_log(MSG_ERROR, "Unknown version control")
        sys.exit(1)

    run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))

    install_dir(settings_dir_path, owner=wsgi_user, group=wsgi_group, mode=0755)
    install_dir(urls_dir_path, owner=wsgi_user, group=wsgi_group, mode=0755)

    #FIXME: Upgrades/pulls will mess those files

    for path, dir in ((settings_py_path, 'juju_settings'), (urls_py_path, 'juju_urls')):
        append_template('conf_injection.tmpl', {'dir': dir}, path)

    if requirements_pip_files:
       for req_file in requirements_pip_files.split(','):
            pip_install_req(os.path.join(working_dir,req_file))

    wsgi_py_path = os.path.join(working_dir, 'wsgi.py')
    if not os.path.exists(wsgi_py_path):
        process_template('wsgi.py.tmpl', {'project_name': sanitized_unit_name, \
                                          'django_settings': django_settings}, \
                                          wsgi_py_path)


def config_changed(config_data):
    os.environ['DJANGO_SETTINGS_MODULE'] = django_settings_modules
    django_admin_cmd = find_django_admin_cmd()

    site_secret_key = config_data['site_secret_key']
    if not site_secret_key:
        site_secret_key = ''.join([choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(50)])

    process_template('secret.tmpl', {'site_secret_key': site_secret_key}, settings_secret_path)

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def upgrade():
    if extra_pip_pkgs:
        for package in extra_pip_pkgs.split(','):
            pip_install(package, upgrade=True)

    apt_get_update()
    for retry in xrange(0,24):
        if apt_get_install(CHARM_PACKAGES):
            time.sleep(10)
        else:
            break

    if vcs == 'hg' or vcs == 'mercurial':
        run('hg pull %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'git' or vcs == 'git-core':
        if repos_branch:
            run('git pull %s -b %s %s' % (repos_url, repos_branch, vcs_clone_dir))
        else:
            run('git pull %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'bzr' or vcs == 'bazaar':
        run('bzr pull %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'svn' or vcs == 'subversion':
        run('svn up %s %s' % (repos_url, vcs_clone_dir))
    else:
        juju_log(MSG_ERROR, "Unknown version control")
        sys.exit(1)

    run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))

    if requirements_pip_files:
       for req_file in requirements_pip_files.split(','):
            pip_install_req(os.path.join(working_dir,req_file), upgrade=True)


    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
       relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

    for relid in relation_ids('django-settings'):
       relation_set({'django_settings_timestamp': time.time()}, relation_id=relid)
    

def django_settings_relation_joined_changed():
    os.environ['DJANGO_SETTINGS_MODULE'] = '.'.join([sanitized_unit_name, 'settings'])
    django_admin_cmd = find_django_admin_cmd()

    relation_set({'settings_dir_path': settings_dir_path,
                  'urls_dir_path': urls_dir_path,
                  'install_root': install_root,
                  'django_admin_cmd': django_admin_cmd,
                  'wsgi_user': wsgi_user,
                  'wsgi_group': wsgi_group,
                 })

    run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def django_settings_relation_broken():
    pass

def pgsql_relation_joined_changed():
    os.environ['DJANGO_SETTINGS_MODULE'] = '.'.join([sanitized_unit_name, 'settings'])
    django_admin_cmd = find_django_admin_cmd()

    packages = ["python-psycopg2", "postgresql-client"]
    apt_get_install(packages)

    database = relation_get("database")
    if not database:
        return

    templ_vars = {
       'db_engine': 'django.db.backends.postgresql_psycopg2',
       'db_database': database,
       'db_user': relation_get("user"),
       'db_password': relation_get("password"),
       'db_host': relation_get("host"),
    }

    process_template('engine.tmpl', templ_vars, settings_database_path % {'engine_name': 'pgsql'})

    run("%s syncdb --noinput --pythonpath=%s --settings=%s || true" % \
            (django_admin_cmd, install_root, django_settings_modules))


    run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def pgsql_relation_broken():
    run('rm %s' % settings_database_path % {'engine_name': 'pgsql'})

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def mongodb_relation_joined_changed():
    packages = ["python-mongoengine"]
    apt_get_install(packages)

    database = relation_get("database")
    if not database:
        return

    templ_vars = {
       'db_database': database,
       'db_host': relation_get("host"),
    }

    process_template('mongodb_engine.tmpl', templ_vars, settings_database_path % {'engine_name': 'mongodb'})

    run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def mongodb_relation_broken():
    run('rm %s' % settings_database_path % {'engine_name': 'mongodb'})

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def wsgi_relation_joined_changed():
    relation_set({'working_dir':working_dir})

    for var in config_data:
        if var.startswith('wsgi_') or var in ['listen_ip', 'port']:
            relation_set({var: config_data[var]})
    
    if not config_data['python_path']:
        relation_set({'python_path': install_root})

def wsgi_relation_broken():
    pass

def cache_relation_joined_changed():
    os.environ['DJANGO_SETTINGS_MODULE'] = django_settings_modules

    packages = ["python-memcache"]
    apt_get_install(packages)

    host = relation_get("host")
    if not host:
        return

    templ_vars = {
       'cache_engine': 'django.core.cache.backends.memcached.MemcachedCache',
       'cache_host': relation_get("host"),
       'cache_port': relation_get("port"),
    }

    process_template('cache.tmpl', templ_vars, settings_database_path % {'engine_name': 'memcache'})

    run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))


    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def cache_relation_broken():
    run('rm %s' % settings_database_path % {'engine_name': 'memcache'})

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def website_relation_joined_changed():
    relation_set({'port': config_data["port"], 'hostname': get_unit_host()})

def website_relation_broken():
    pass

###############################################################################
# Global variables
###############################################################################
config_data = config_get()
juju_log(MSG_DEBUG, "got config: %s" % str(config_data))

django_version = config_data['django_version']
vcs = config_data['vcs']
repos_url = config_data['repos_url']
repos_username = config_data['repos_username']
repos_password = config_data['repos_password']
repos_branch = config_data['repos_branch']

project_template_extension = config_data['project_template_extension']
project_template_url = config_data['project_template_url']

extra_deb_pkgs = config_data['additional_distro_packages']
extra_pip_pkgs = config_data['additional_pip_packages']
requirements_pip_files = config_data['requirements_pip_files']
wsgi_user = config_data['wsgi_user']
wsgi_group = config_data['wsgi_group']
install_root = config_data['install_root']
application_path = config_data['application_path']
django_settings = config_data['django_settings']

unit_name = os.environ['JUJU_UNIT_NAME'].split('/')[0]
sanitized_unit_name = sanitize(unit_name)
vcs_clone_dir = os.path.join(install_root, sanitized_unit_name)
if application_path:
    working_dir = os.path.join(vcs_clone_dir, application_path)
else:
    working_dir = vcs_clone_dir

django_settings_modules = '.'.join([sanitized_unit_name, django_settings])
django_run_dir = os.path.join(working_dir, "run/")
django_logs_dir = os.path.join(working_dir, "logs/")
settings_py_path = os.path.join(working_dir, 'settings.py')
urls_py_path = os.path.join(working_dir, 'urls.py')
settings_dir_path = os.path.join(working_dir, config_data["settings_dir_name"])
urls_dir_path = os.path.join(working_dir, config_data["urls_dir_name"])
settings_secret_path = os.path.join(working_dir, config_data["settings_secret_key_path"])
settings_database_path = os.path.join(working_dir, config_data["settings_database_path"])
hook_name = os.path.basename(sys.argv[0])

###############################################################################
# Main section
###############################################################################
def main():
    juju_log(MSG_INFO, "Running {} hook".format(hook_name))
    if hook_name == "install":
        install()

    elif hook_name == "config-changed":
       config_changed(config_data)

    elif hook_name == "upgrade-charm":
        upgrade()
        config_changed(config_data)

    elif hook_name in ["django-settings-relation-joined", "django-settings-relation-changed"]:
        django_settings_relation_joined_changed()
        config_changed(config_data)

    elif hook_name == "django-settings-relation-broken":
        django_settings_relation_broken()
        config_changed(config_data)

    elif hook_name in ["pgsql-relation-joined", "pgsql-relation-changed"]:
        pgsql_relation_joined_changed()
        config_changed(config_data)

    elif hook_name == "pgsql-relation-broken":
        pgsql_relation_broken()
        config_changed(config_data)

    elif hook_name in ["mongodb-relation-joined", "mongodb-relation-changed"]:
        mongodb_relation_joined_changed()
        config_changed(config_data)

    elif hook_name == "mongodb-relation-broken":
        mongodb_relation_broken()
        config_changed(config_data)

    elif hook_name in ["wsgi-relation-joined", "wsgi-relation-changed"]:
        wsgi_relation_joined_changed()

    elif hook_name == "wsgi-relation-broken":
        wsgi_relation_broken()

    elif hook_name in ["cache-relation-joined", "cache-relation-changed"]:
        cache_relation_joined_changed()

    elif hook_name == "cache-relation-broken":
        cache_relation_broken()

    elif hook_name in ["website-relation-joined", "website-relation-changed"]:
        website_relation_joined_changed()

    elif hook_name == "website-relation-broken":
        website_relation_broken()


    else:
        print "Unknown hook {}".format(hook_name)
        raise SystemExit(1)


if __name__ == '__main__':
    raise SystemExit(main())
