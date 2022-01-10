import sys

import gi

gi.require_version('Gst', '1.0')
# from gi.repository import Gst, GObject, GLib

from gi.repository import GObject, Gst
from gi.repository import GLib
from common.bus_call import bus_call
from common.is_aarch_64 import is_aarch64
from common.FPS import GETFPS
import pyds

fps_streams = {}


# tiler_sink_pad_buffer_probe将提取OSD接收到的元数据，并更新绘制矩形的参数，对象信息等.
def tiler_src_pad_buffer_probe(pad, info, u_data):
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("无法获取GstBuffer")
        return

    # 从gst_buffer U缓冲区检索批处理元数据
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C gst_缓冲区的地址作为输入，通过哈希（gst_缓冲区）获得
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list

    while l_frame is not None:
        try:
            # 请注意，l_frame.data需要转换为pyds.NvDsFrameMeta
            # 演员由pyds完成。glist_get_nvds_frame_meta（）
            # 强制转换还保留底层内存的所有权
            # 在C代码中，因此Python垃圾收集器将离开
            # 只有它。
            # frame_meta = pyds.glist_get_nvds_frame_meta(l_frame.data)
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration as ex:
            print('异常')
            print(ex)
            break

        '''
        print("Frame Number is ", frame_meta.frame_num)
        print("Source id is ", frame_meta.source_id)
        print("Batch id is ", frame_meta.batch_id)
        print("Source Frame Width ", frame_meta.source_frame_width)
        print("Source Frame Height ", frame_meta.source_frame_height)
        print("Num object meta ", frame_meta.num_obj_meta)
        '''
        source_id = frame_meta.source_id
        batch_id = frame_meta.batch_id
        frame_number = frame_meta.frame_num  # 帧序号

        l_obj = frame_meta.obj_meta_list  # 检测结果
        num_rects = frame_meta.num_obj_meta  # 检测数量
        # print('源ID='+str(source_id)+' ，批次ID='+str(batch_id)+' ，帧序号='+str(frame_number)+' ,检测数量='+str(num_rects))

        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration as ex:
                print('异常')
                print(ex)
                break
            if obj_meta.class_id < 0:
                print('类ID错误：' + str(obj_meta.class_id) + ' ,不能小于0！')
                break
            cls_name = obj_meta.obj_label
            org_bbox_coords = obj_meta.detector_bbox_info.org_bbox_coords  # 检测信息 height , left, top, width
            tracker_bbox_coords = obj_meta.tracker_bbox_info.org_bbox_coords
            clas_conf = round(obj_meta.confidence, 3)  # 检测置信度
            tracker_conf = round(obj_meta.tracker_confidence, 3)  # 跟踪置信度，dcf 跟踪才有置信度
            tracker_id_src = obj_meta.object_id  # 跟踪ID
            print('obj_meta.object_id=', obj_meta.object_id)

            conf = clas_conf
            if clas_conf <= 0 and tracker_conf > 0:
                conf = tracker_conf
            box_x = round(org_bbox_coords.left, 0)
            box_y = round(org_bbox_coords.top, 0)
            box_w = round(org_bbox_coords.width, 0)
            box_h = round(org_bbox_coords.height, 0)
            if box_w <= 0 and tracker_bbox_coords.width > 0:
                box_x = round(tracker_bbox_coords.left, 0)
                box_y = round(tracker_bbox_coords.top, 0)
                box_w = round(tracker_bbox_coords.width, 0)
                box_h = round(tracker_bbox_coords.height, 0)

            msg = '源ID={}，批次ID={}，帧序号={} , 类id={},  类名称={} , 置信度={},x={}，y={}，w={}，h={}'.format(source_id,
                                                                                                batch_id,
                                                                                                frame_number,
                                                                                                obj_meta.class_id,
                                                                                                cls_name,
                                                                                                conf, box_x, box_y,
                                                                                                box_w, box_h)
            print(msg)

            rect_params = obj_meta.rect_params  # 对象的位置参数
            box_color = [255, 255, 255, 255]
            rect_params.border_color.set(box_color[0], box_color[1], box_color[2],
                                         box_color[3])  # 指定检测边界框的边框颜色，{ r: 1.0 g: 0.0 b: 0.0 a: 1.0 }

            # mask_params= obj_meta.rect_params #保存对象的遮罩参数，此蒙版覆盖在对象上
            text_params = obj_meta.text_params  # 保存描述对象的文本，该文本可以覆盖在标识对象的标准文本上
            display_text = ''
            display_text = cls_name + ' ' + str(conf)

            text_params.display_text = display_text

            # text_params.y_offset = text_params.y_offset -4 #12

            text_params.font_params.font_color.set(0.0, 0.0, 0.0, 1.0)  # 设置字体颜色，{ r: 1.0 g: 0.0 b: 0.0 a: 1.0 }
            text_params.set_bg_clr = 1  # 设置背景填充
            bg_color = [255, 255, 255, 255]
            text_params.text_bg_clr.set(bg_color[0], bg_color[1], bg_color[2],
                                        bg_color[3])  # 设置背景颜色，{ r: 1.0 g: 0.0 b: 0.0 a: 1.0 }

            # 偏移一下 y轴
            if text_params.y_offset < 0:
                text_params.y_offset = 0

            try:
                l_obj = l_obj.next
            except StopIteration as ex:
                print('异常')
                print(ex)
                break

        """display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]
        py_nvosd_text_params.display_text = "Frame Number={} Number of Objects={} Vehicle_count={} Person_count={}".format(frame_number, num_rects, vehicle_count, person)
        py_nvosd_text_params.x_offset = 10;
        py_nvosd_text_params.y_offset = 12;
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 10
        py_nvosd_text_params.font_params.font_color.red = 1.0
        py_nvosd_text_params.font_params.font_color.green = 1.0
        py_nvosd_text_params.font_params.font_color.blue = 1.0
        py_nvosd_text_params.font_params.font_color.alpha = 1.0
        py_nvosd_text_params.set_bg_clr = 1
        py_nvosd_text_params.text_bg_clr.red = 0.0
        py_nvosd_text_params.text_bg_clr.green = 0.0
        py_nvosd_text_params.text_bg_clr.blue = 0.0
        py_nvosd_text_params.text_bg_clr.alpha = 1.0
        #print("Frame Number=", frame_number, "Number of Objects=",num_rects,"Vehicle_count=",vehicle_count,"Person_count=",person)
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)"""

        # msg = "帧序号={} , 检测数量={} , 未佩戴口罩计数={} , 正常佩戴口罩计数={} , 错误佩戴口罩={} ".format(
        #     frame_number, num_rects, obj_counter[PGIE_CLASS_ID_1], obj_counter[PGIE_CLASS_ID_2], obj_counter[PGIE_CLASS_ID_3])
        # print(msg)

        # Get frame rate through this probe
        fps_streams["stream{0}".format(frame_meta.pad_index)].get_fps()
        try:
            l_frame = l_frame.next
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK


def on_pad_added(element, element_src_pad, data):
    print("In cb_newpad\n");
    caps = element_src_pad.get_current_caps()
    str = caps.get_structure(0)
    name = str.get_name()
    depay_elem = data

    media = str.get_string("media")
    is_video = media == 'video'
    if 'x-rtp' in name and is_video is True:
        print('开始绑定RTSP')
        sinkpad = depay_elem.get_static_pad("sink")
        state = element_src_pad.link(sinkpad)
        if state != Gst.PadLinkReturn.OK:
            print('无法将depay加载程序链接到rtsp src')
        else:
            print('绑定RTSP成功')
    else:
        print('不符合不能绑定,get_name=', name, ' , media=', media)


def main(rtsp):
    print(rstp)
    # Standard GStreamer initialization
    Gst.init(None)

    fps_streams['stream0'] = GETFPS(0)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Source element for reading from the file
    print("Creating Source \n ")
    source = Gst.ElementFactory.make("rtspsrc", "rtsp-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")
    source.set_property("short-header", "true")
    source.set_property("latency", 0)  # 缓存时间毫秒
    depay = Gst.ElementFactory.make('rtph264depay', "depay")
    if not depay:
        sys.stderr.write(" Unable to create depayer \n")

    source.connect('pad-added', on_pad_added, depay)

    # Since the data format in the input file is elementary h264 stream,
    # we need a h264parser
    print("Creating H264Parser \n")
    h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
    if not h264parser:
        sys.stderr.write(" Unable to create h264 parser \n")

    # Use nvdec_h264 for hardware accelerated decode on GPU
    print("Creating Decoder \n")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
    if not decoder:
        sys.stderr.write(" Unable to create Nvv4l2 Decoder \n")

    # decoder.set_property('mjpeg',1)

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    # Use nvinfer to run inferencing on decoder's output,
    # behaviour of inferencing is set through config file
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")

    # Create OSD to draw on the converted RGBA buffer
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")

    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    # Finally render the osd output
    if is_aarch64():
        transform = Gst.ElementFactory.make("nvegltransform", "nvegl-transform")

    print("Creating EGLSink \n")
    sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
    if not sink:
        sys.stderr.write(" Unable to create egl sink \n")

    source.set_property('location', rtsp)
    streammux.set_property('width', 1280)
    streammux.set_property('height', 720)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', 4000000)
    pgie.set_property('config-file-path', "dstest3_pgie_config.txt")

    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(depay)
    pipeline.add(h264parser)
    pipeline.add(decoder)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(sink)
    if is_aarch64():
        pipeline.add(transform)

    # we link the elements together
    # file-source -> h264-parser -> nvh264-decoder ->
    # nvinfer -> nvvidconv -> nvosd -> video-renderer
    print("Linking elements in the Pipeline \n")
    source.link(depay)
    depay.link(h264parser)
    h264parser.link(decoder)

    sinkpad = streammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")
    srcpad = decoder.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of decoder \n")
    srcpad.link(sinkpad)

    streammux.link(pgie)
    pgie.link(nvvidconv)
    nvvidconv.link(nvosd)
    if is_aarch64():
        nvosd.link(transform)
        transform.link(sink)
    else:
        nvosd.link(sink)

    # 开始运行
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    tiler_src_pad = pgie.get_static_pad("src")
    if not tiler_src_pad:
        sys.stderr.write(" 无法获取src pad \n")
    else:
        tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, 0)

    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)


if __name__ == '__main__':
    # rstp = 'rtsp://admin:123456789a@192.168.2.66:554/cam/realmonitor?channel=1&subtype=0'
    # rstp = 'rtsp://admin:123456789a@192.168.2.3:554/h264/ch1/sub/av_stream'
    rstp = 'rtsp://admin:123456789a@192.168.2.3:554/h264/ch1/main/av_stream'
    main(rstp)
    sys.exit()
