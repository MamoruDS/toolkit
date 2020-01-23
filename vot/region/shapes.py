import os, sys

from copy import copy
from functools import reduce
from abc import abstractmethod, ABC
from typing import Tuple
from enum import Enum

import numpy as np
import cv2

from vot import VOTException
from vot.utilities.draw import DrawHandle

class ConversionException(VOTException):
    """Region conversion exception, the conversion cannot be performed
    """
    pass

class RegionType(Enum):
    """Enumeration of region types
    """
    SPECIAL = 0
    RECTANGLE = 1
    POLYGON = 2
    MASK = 3

class Region(ABC):
    """
    Base class for all region containers

    :var type: type of the region
    """
    def __init__(self):
        pass

    @abstractmethod
    def type(self):
        pass

    @abstractmethod
    def copy(self):
        """Copy region to another object
        """

    @abstractmethod
    def convert(self, rtype: RegionType):
        """Convert region to another type. Note that some conversions
        degrade information.
        Arguments:
            rtype {RegionType} -- Desired type.
        """

class Special(Region):
    """
    Special region

    :var code: Code value
    """

    UNKNOWN = 0
    INITIALIZATION = 1
    FAILURE = 2

    def __init__(self, code):
        """ Constructor

        :param code: Special code
        """
        super().__init__()
        self._code = int(code)

    def __str__(self):
        """ Create string from class """
        return '{}'.format(self._code)

    def type(self):
        return RegionType.SPECIAL

    def copy(self):
        return Special(self._code)

    def convert(self, rtype: RegionType):
        if rtype == RegionType.SPECIAL:
            return self.copy()
        else:
            raise ConversionException("Unable to convert special region to {}".format(rtype))

    def code(self):
        """Retiurns special code for this region
        Returns:
            int -- Type code
        """
        return self._code

    def draw(self, handle: DrawHandle, color, width):
        pass

class Rectangle(Region):
    """
    Rectangle region

    :var x: top left x coord of the rectangle region
    :var float y: top left y coord of the rectangle region
    :var float w: width of the rectangle region
    :var float h: height of the rectangle region
    """
    def __init__(self, x=0, y=0, width=0, height=0):
        """ Constructor

            :param float x: top left x coord of the rectangle region
            :param float y: top left y coord of the rectangle region
            :param float w: width of the rectangle region
            :param float h: height of the rectangle region
        """
        super().__init__()
        self.x, self.y, self.width, self.height = x, y, width, height

    def __str__(self):
        """ Create string from class """
        return '{},{},{},{}'.format(self.x, self.y, self.width, self.height)

    def type(self):
        return RegionType.RECTANGLE

    def copy(self):
        return copy(self)

    def convert(self, rtype: RegionType):
        if rtype == RegionType.RECTANGLE:
            return self.copy()
        elif rtype == RegionType.POLYGON:
            points = []
            points.append((self.x, self.y))
            points.append((self.x + self.width, self.y))
            points.append((self.x + self.width, self.y + self.height))
            points.append((self.x, self.y + self.height))
            return Polygon(points)
        elif rtype == RegionType.MASK:
            return Mask(np.ones((int(round(self.height)), int(round(self.width))), np.uint8), (int(round(self.x)), int(round(self.y))))
        else:
            raise ConversionException("Unable to convert rectangle region to {}".format(rtype))

    def draw(self, handle: DrawHandle, color=(1, 0, 0, 0.7), width=1):
        polygon = [(self.x, self.y), (self.x + self.width, self.y), \
            (self.x + self.width, self.y + self.height), \
            (self.x, self.y + self.height)]
        handle.polygon(polygon, width, color)

    def resize(self, factor=1):
        return Rectangle(self.x * factor, self.y * factor,
                         self.width * factor, self.height * factor)

    def center(self):
        return (self.x + self.width / 2, self.y + self.height / 2)

class Polygon(Region):
    """
    Polygon region

    :var list points: List of points as tuples [(x1,y1), (x2,y2),...,(xN,yN)]
    :var int count: number of points
    """
    def __init__(self, points):
        """
        Constructor

        :param list points: List of points as tuples [(x1,y1), (x2,y2),...,(xN,yN)]
        """
        super().__init__()
        assert isinstance(points, list)
        # do not allow empty list
        assert points
        assert reduce(lambda x, y: x and y, [isinstance(p, tuple) for p in points])
        self.count = len(points)
        self.points = points

    def __str__(self):
        """ Create string from class """
        return ','.join(['{},{}'.format(p[0], p[1]) for p in self.points])

    def type(self):
        return RegionType.POLYGON

    def copy(self):
        return copy(self)

    def convert(self, rtype: RegionType):
        if rtype == RegionType.POLYGON:
            return self.copy()
        elif rtype == RegionType.RECTANGLE:
            top = sys.float_info.max
            bottom = -sys.float_info.max
            left = sys.float_info.max
            right = -sys.float_info.max

            for point in self.points:
                top = min(top, point[1])
                bottom = max(bottom, point[1])
                left = min(left, point[0])
                right = max(right, point[0])

            return Rectangle(left, top, right - left, bottom - top)
        elif rtype == RegionType.MASK:
            x_ = np.round(np.array([p[0] for p in self.points])).astype(np.int32)
            y_ = np.round(np.array([p[1] for p in self.points])).astype(np.int32)
            tl_ = (max(0, np.min(x_)), max(0, np.min(y_)))  # there is no need to consider negative coordinates since fill poly function can work with negative coordinates
            w_ = np.max(x_) - tl_[0] + 1
            h_ = np.max(y_) - tl_[1] + 1
            # normalize points by x_min and y_min (so that the smallest element is 0)
            points_norm = [(px - tl_[0], py - tl_[1]) for px, py in zip(x_, y_)]
            m = np.zeros((h_, w_), dtype=np.uint8)
            cv2.fillConvexPoly(m, np.round(np.array(points_norm)).astype(np.int32), 1)

            return Mask(m, offset=tl_)
        else:
            raise ConversionException("Unable to convert polygon region to {}".format(rtype))

    def draw(self, handle: DrawHandle, color=(1, 0, 0, 0.7), width=1):
        handle.polygon(self.points, width, color)

    def resize(self, factor=1):
        return Polygon([(p[0] * factor, p[1] * factor) for p in self.points])

from vot.region.utils import mask2bbox, mask_to_rle

class Mask(Region):
    """Mask region
    """

    def __init__(self, mask: np.array, offset: Tuple[int, int] = (0, 0), optimize=False):
        super().__init__()
        self.mask = mask.astype(np.uint8)
        self.mask[self.mask > 0] = 1
        self.offset = offset
        if optimize:  # optimize is used when mask without an offset is given (e.g. full-image mask)
            self._optimize()

    def __str__(self):
        offset_str = '%d,%d' % self.offset
        region_sz_str = '%d,%d' % (self.mask.shape[1], self.mask.shape[0])
        rle_str = ','.join([str(el) for el in mask_to_rle(self.mask)])
        return 'm%s,%s,%s' % (offset_str, region_sz_str, rle_str)

    def _optimize(self):
        bounds = mask2bbox(self.mask)
        self.mask = np.copy(self.mask[bounds[1]:bounds[3], bounds[0]:bounds[2]])
        self.offset = (bounds[0], bounds[1])

    def type(self):
        return RegionType.MASK

    def copy(self):
        return copy(self)

    def convert(self, rtype: RegionType):
        if rtype == RegionType.MASK:
            return self.copy()
        elif rtype == RegionType.RECTANGLE:
            bounds = mask2bbox(self.mask)
            return Rectangle(bounds[0] + self.offset[0], bounds[1] + self.offset[1],
                            bounds[2] - bounds[0], bounds[3] - bounds[1])
        elif rtype == RegionType.POLYGON:
            bounds = mask2bbox(self.mask)
            return Polygon([(bounds[0], bounds[1]), (bounds[2], bounds[1]), (bounds[2], bounds[3]), (bounds[0], bounds[3])])
        else:
            raise ConversionException("Unable to convert mask region to {}".format(rtype))

    def draw(self, handle: DrawHandle, color=(1, 0, 0, 0.7)):
        handle.mask(self.mask, self.offset, color)

    def get_array(self, output_sz=None):
        """
        return an array of 2-D binary mask
        output_sz is in the format: [width, height]
        """
        tl_x, tl_y = self.offset[0], self.offset[1]
        region_w, region_h = self.mask.shape[1], self.mask.shape[0]
        mask_ = np.zeros((region_h + tl_y, region_w + tl_x), dtype=np.uint8)
        # mask bounds - needed if mask is outside of image
        # TODO: this part of code needs to be tested more with edge cases
        src_x0, src_y0 = 0, 0
        src_x1, src_y1 = self.mask.shape[1], self.mask.shape[0]
        dst_x0, dst_y0 = tl_x, tl_y
        dst_x1, dst_y1 = tl_x + region_w, tl_y + region_h
        if dst_x1 > 0 and dst_y1 > 0 and dst_x0 < mask_.shape[1] and dst_y0 < mask_.shape[0]:
            if dst_x0 < 0:
                src_x0 = -dst_x0
                dst_x0 = 0
            if dst_y0 < 0:
                src_y0 = -dst_y0
                dst_y0 = 0
            if dst_x1 > mask_.shape[1]:
                src_x1 -= dst_x1 - mask_.shape[1]# + 1
                dst_x1 = mask_.shape[1]
            if dst_y1 > mask_.shape[0]:
                src_y1 -= dst_y1 - mask_.shape[0]# + 1
                dst_y1 = mask_.shape[0]
            mask_[dst_y0:dst_y1, dst_x0:dst_x1] = self.mask[src_y0:src_y1, src_x0:src_x1]

        # pad with zeros right and down if output size is larger than current mask
        if output_sz is not None:
            pad_x = output_sz[0] - mask_.shape[1]
            if pad_x < 0:
                mask_ = mask_[:, :mask_.shape[1] + pad_x]
                # padding has to be set to zero, otherwise pad function fails
                pad_x = 0
            pad_y = output_sz[1] - mask_.shape[0]
            if pad_y < 0:
                mask_ = mask_[:mask_.shape[0] + pad_y, :]
                # padding has to be set to zero, otherwise pad function fails
                pad_y = 0
            mask_ = np.pad(mask_, ((0, pad_y), (0, pad_x)), 'constant', constant_values=0)

        return mask_
