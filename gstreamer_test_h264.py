import sys

import gi
gi.require_version('Gst', '1.0')
# from gi.repository import Gst, GObject, GLib

from gi.repository import GObject, Gst
from gi.repository import GLib
from common.bus_call import bus_call


# rtspsrc的srcpad是随机衬垫，这里使用回调函数来连接衬垫。
def on_pad_added(src, pad, des):
    vpad = des.get_static_pad("sink")
    pad.link(vpad)


def main(rtsp):
    print(rstp)
    Gst.init(None)

    pipe = Gst.Pipeline()

    queue1 = Gst.ElementFactory.make("queue", "queue1")

    source = Gst.ElementFactory.make("rtspsrc", "src")
    source.set_property("short-header", "true")
    source.set_property("location", rstp)

    source.connect("pad-added", on_pad_added, queue1)

    depay = Gst.ElementFactory.make("rtph264depay", "depay")

    decodebin = Gst.ElementFactory.make("avdec_h264", "decodea")

    sink = Gst.ElementFactory.make("xvimagesink", "sink")

    #添加元素
    pipe.add(source)
    pipe.add(depay)
    pipe.add(queue1)
    pipe.add(sink)
    pipe.add(decodebin)

    #拼接
    queue1.link(depay)
    depay.link(decodebin)
    decodebin.link(sink)


    #开始运行
    loop = GLib.MainLoop()
    bus = pipe.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    pipe.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipe.set_state(Gst.State.NULL)

if __name__ == '__main__':
    rstp = 'rtsp://admin:123456789a@192.168.2.71:554/cam/realmonitor?channel=1&subtype=0'
    rstp = 'rtsp://admin:123456789a@192.168.2.3:554/h264/ch1/main/av_stream'
    main(rstp)
    sys.exit()