#!/usr/bin/env python3

import binascii
from construct import *
import cv2
import fcntl
import logging
import numpy
import time
import sys

from filters import *

V4L2_FIELD_NONE = 1
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_COLORSPACE_SRGB = 8
VIDIOC_S_FMT = 0xc0d05605

v4l2_pix_format = Struct(
    "wtf" / Default(Int32ul, 0x0),
    "width" / Int32ul,
    "height" / Int32ul,
    "pixelformat" / Int32ul,
    "field" / Int32ul,
    "bytesperline" / Int32ul,
    "sizeimage" / Int32ul,
    "colorspace" / Int32ul,
    "priv" / Default(Int32ul, 0),
    "flags" / Default(Int32ul, 0),
    "hsv_enc" / Default(Int32ul, 0),
    "quantization" / Default(Int32ul, 0),
    "xfer_func" / Default(Int32ul, 0),
    "padding" / Padding(200 - 48),
)

v4l2_format = Struct(
    "type" / Int32ul,
    "pix"  / v4l2_pix_format,
)

def open_capture(camera_in):
    capture = cv2.VideoCapture(camera_in)
    if not capture.isOpened():
        logging.error("failed to open camera")
        sys.exit(1)

    fps = capture.get(cv2.CAP_PROP_FPS)
    logging.debug(f"Frames per second: {fps}")
    capture.set(cv2.CAP_PROP_FPS, 10)

    return capture

def open_video_out(camera_out):
    width = 640
    height = 480
    pix_format = dict(
        width        = width,
        height       = height,
        pixelformat  = cv2.VideoWriter_fourcc(*"YU12"),
        sizeimage    = int(width * height * 1.5),
        field        = V4L2_FIELD_NONE,
        bytesperline = width ,
        colorspace   = V4L2_COLORSPACE_SRGB,
    )
    vid_format = dict(
        type = V4L2_BUF_TYPE_VIDEO_OUTPUT,
        pix  = pix_format,
    )

    video_out = open(f"/dev/video{camera_out}", "wb")

    request = v4l2_format.build(vid_format)
    ret = fcntl.ioctl(video_out.fileno(), VIDIOC_S_FMT, request)
    if ret != request:
        logging.warning("unexpected ioctl output (happens with different sizeimage...)")
        logging.warning(v4l2_format.parse(ret))

    return video_out

def main(camera_in=0, camera_out=1, do_flip=False):
    current_filter = None
    keys = {
        " ": (FilterColor,    [ (255, 0, 211) ]),
        ")": (FilterAddImage, [ "img/smile.png" ]),
        "a": (FilterAddImage, [ "img/applause.png" ]),
        "t": (FilterAddText,  [ "(be right back)" ]),
        "v": (FilterVideo,    [ "img/rick-astley-never-gonna-give-you-up-video.mp4" ]),
        "b": (FilterBlur ,    [ "{LASTFRAME}" ]),
    }

    capture = open_capture(camera_in)
    video_out = open_video_out(camera_out)
    while True :
        ret, frame = capture.read()
        if not ret:
            break

        if do_flip:
            frame = cv2.flip(frame, 1)

        # apply filter before converting to out camera format
        if current_filter:
            frame = current_filter.draw(frame)
            if current_filter.done():
                current_filter = None

        xframe = cv2.cvtColor(frame, cv2.COLOR_RGBA2YUV_YV12)
        raw = numpy.fromstring(xframe, dtype=numpy.uint8)

        if False:
            print(len(raw), raw)
            with open('/tmp/w', 'wb') as fp:
                fp.write(raw)
        if False:
            cv2.imwrite("/tmp/frame.jpg", frame)

        ret = video_out.write(raw)

        cv2.imshow("Augmented reality - Webcam", frame)
        c = chr(cv2.waitKey(1) & 0xFF)
        if c == 'q':
            break
        elif c in keys:
            klass, args = keys[c]
            args = [ frame if arg == "{LASTFRAME}" else arg for arg in args ]
            if current_filter is None:
                current_filter = klass(*args)
            elif isinstance(current_filter, klass):
                current_filter.stop()

    capture.release()
    video_out.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=int, help="Video input", default=0)
    parser.add_argument("--output", type=int, help="Video output", default=1)
    parser.add_argument("--flip", action="store_true", help="Flip image horizontally")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    main(args.input, args.output, args.flip)
