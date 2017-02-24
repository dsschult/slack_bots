"""
Load/store data from a json file.
"""

from __future__ import absolute_import, division, print_function

import os
import json
from datetime import date,datetime,time

import logging

logger = logging.getLogger('json_store')


class datetime_converter:
    @staticmethod
    def dumps(obj):
        return obj.isoformat()
    @staticmethod
    def loads(obj,name=None):
        if ':' in obj:
            if 'T' in obj or ' ' in obj:
                center = ' '
                if 'T' in obj:
                    center = 'T'
                # must be datetime
                if '.' in obj:
                    return datetime.strptime( obj, "%Y-%m-%d"+center+"%H:%M:%S.%f")
                else:
                    return datetime.strptime( obj, "%Y-%m-%d"+center+"%H:%M:%S")
            else:
                # must be time
                if '.' in obj:
                    return datetime.strptime( obj, "%H:%M:%S.%f")
                else:
                    return datetime.strptime( obj, "%H:%M:%S")
        else:
            # must be date
            return datetime.strptime( obj, "%Y-%m-%d")

class date_converter(datetime_converter):
    @staticmethod
    def loads(obj,name=None):
        d = datetime_converter.loads(obj)
        return date(d.year,d.month,d.day)

class time_converter(datetime_converter):
    @staticmethod
    def loads(obj,name=None):
        d = datetime_converter.loads(obj)
        return time(d.hour,d.minute,d.second,d.microsecond)

class set_converter:
    @staticmethod
    def dumps(obj):
        return list(obj)
    @staticmethod
    def loads(obj,name=None):
        return set(obj)

JSONConverters = {
    'datetime':datetime_converter,
    'date':date_converter,
    'time':time_converter,
    'set':set_converter,
}

def objToJSON(obj):
    if isinstance(obj,(dict,list,tuple,str,int,float,bool)) or obj is None:
        return obj
    else:
        name = obj.__class__.__name__
        if name in JSONConverters:
            return {'__jsonclass__':[name,JSONConverters[name].dumps(obj)]}
        else:
            raise Exception('Cannot encode %s class to JSON'%name)

def JSONToObj(obj):
    ret = obj
    if isinstance(obj,dict) and '__jsonclass__' in obj:
        logging.info('try unpacking class')
        try:
            name = obj['__jsonclass__'][0]
            if name not in JSONConverters:
                raise Exception('class %r not found in converters'%name)
            obj_repr = obj['__jsonclass__'][1]
            ret = JSONConverters[name].loads(obj_repr,name=name)
        except Exception as e:
            logging.warn('error making json class: %r',e,exc_info=True)
    return ret

# copied from tornado.escape so we don't have to include that project
def recursive_unicode(obj):
    """Walks a simple data structure, converting byte strings to unicode.

    Supports lists, tuples, sets, and dictionaries.
    """
    if isinstance(obj, dict):
        return {recursive_unicode(k): recursive_unicode(obj[k]) for k in obj}
    elif isinstance(obj, set):
        return {recursive_unicode(i) for i in obj}
    elif isinstance(obj, list):
        return [recursive_unicode(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(recursive_unicode(i) for i in obj)
    elif isinstance(obj, bytes):
        return obj.decode("utf-8")
    else:
        return obj

def load(filename):
    try:
        with open(filename, 'r') as f:
            sites = json.load(f, object_hook=JSONToObj)
    except:
        sites = {}
    if not isinstance(sites,dict):
        sites = {}
    return sites

def store(data, filename):
    try:
        with open(filename+'_','w') as f:
            json.dump(recursive_unicode(data), f, default=objToJSON,
                      separators=(',',':'))
        os.rename(filename+'_',filename)
    except:
        logger.info('cannot save', exc_info=True)
    finally:
        if os.path.exists(filename+'_'):
            os.remove(filename+'_')

