__author__ = 'katharine'

import calendar
import dateutil.parser
import logging
import struct
import urlparse
from colours import PEBBLE_COLOURS

logger = logging.getLogger('pypkjs.timeline.attributes')


class TimelineAttributeSet(object):
    def __init__(self, attributes, fw_mapping):
        self.attributes = attributes
        self.fw_mapping = fw_mapping

    def serialise(self):
        serialised = ''
        count = 0

        for key, value in self.attributes.iteritems():
            if key == 'type':
                continue
            try:
                attribute_info = self.fw_mapping['attributes'][key]
            except KeyError:
                logger.warning("skipping unknown attribute '%s'", key)
                continue
            print key
            converted = self.convert_type(attribute_info, value)
            if converted is None:
                logger.warning("Couldn't convert '%s' value '%s'", key, value)
                continue
            logger.debug("attribute (%s, %s) -> (%s, %s, %s)", key, value, attribute_info['id'], len(converted), converted.encode('hex'))
            serialised += struct.pack("<BH", attribute_info['id'], len(converted)) + converted
            count += 1

        return count, serialised

    def convert_type(self, attribute_info, value):
        conversion_methods = {
            'string-string': lambda x, y: x.encode('utf-8')[:y.get('max_length', 64)-1] + '\x00',
            'uri-resource_id': self._uri_lookup,
            'number-uint32': lambda x, y: struct.pack('<I', x),
            'number-uint16': lambda x, y: struct.pack('<H', x),
            'number-uint8':  lambda x, y: struct.pack('<B', x),
            'number-int32':  lambda x, y: struct.pack('<i', x),
            'number-int16':  lambda x, y: struct.pack('<h', x),
            'number-int8':   lambda x, y: struct.pack('<b', x),
            'enum-uint8':    self._enum_lookup,
            'string_array-string_array': self._serialise_string_array,
            'isodate-unixtime': lambda x, y: struct.pack('<I', calendar.timegm(dateutil.parser.parse(x).utctimetuple())),
            'color-uint8':   self._colour_lookup,
        }
        return conversion_methods[attribute_info['type']](value, attribute_info)

    def _uri_lookup(self, value, attribute_info):
        url = urlparse.urlparse(value)
        if url.scheme == 'system':
            if value in self.fw_mapping['resources']:
                res_id = self.fw_mapping['resources'][value]
                logger.debug("got res_id %s (%s)", res_id, res_id | (1 << 31))
                return struct.pack("<I", res_id | (1 << 31))
        # We'll need to handle app resources here, when we know what they look like.
        return None

    @staticmethod
    def _enum_lookup(value, attribute_info):
        try:
            return struct.pack('<B', attribute_info['enum'][value])
        except KeyError:
            return None

    @staticmethod
    def _serialise_string_array(value, attribute_info):
        try:
            parts = '\x00'.join(value)
            return struct.pack('<%ss' % len(parts), parts.encode('utf-8'))
        except TypeError:
            return None

    @staticmethod
    def _colour_lookup(value, attribute_info):
        if not isinstance(value, basestring) or len(value) == 0:
            return None

        # Try a hex colour value
        if value[0] == '#' and len(value) == 7:
            try:
                r8, g8, b8 = int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
            except ValueError:
                logger.warning("Couldn't parse %s to a colour value.", value)
                return None
            r, g, b = r8 >> 6, g8 >> 6, b8 >> 6
            colour = 0b11000000 | (r << 4) | (g << 2) | b
        else:
        # Try a colour name
            colour = PEBBLE_COLOURS.get(value.lower(), None)

        return struct.pack('<B', colour)
