from gi.repository import Gst
import asyncio


def create_capsfilter(caps_string):
    capsfilter = Gst.ElementFactory.make('capsfilter')
    caps = Gst.Caps.from_string(caps_string)
    capsfilter.set_property('caps', caps)
    return capsfilter


def link_many(*args):
    for i, x in enumerate(args[0:-1]):
        ret = Gst.Element.link(args[i], args[i+1])
        if not ret:
            print('ERROR LINKING: {} with {}'.format(args[i], args[i+1]))


def add_many(pipeline, *args):
    for a in args:
        pipeline.add(a)


def remove_many(pipeline, *args):
    for a in args:
        pipeline.remove(a)


def set_many_to_state(state, *args):
    for a in args:
        a.set_state(state)


async def send_eos_and_wait(element):
    try:
        element.set_state(Gst.State.PLAYING)
        sink_pad = element.get_static_pad('sink')
        src_pad = element.get_static_pad('src')

        spin_lock = {'done': False}

        def eos_callback(pad, info):

            if not (info.type & Gst.PadProbeType.EVENT_DOWNSTREAM):
                return Gst.PadProbeReturn.PASS

            event = info.get_event()

            if not event:
                return Gst.PadProbeReturn.PASS

            if event.type != Gst.EventType.EOS:
                return Gst.PadProbeReturn.PASS

            spin_lock['done'] = True

            return Gst.PadProbeReturn.DROP

        src_pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM | Gst.PadProbeType.BLOCK, eos_callback)
        sink_pad.send_event(Gst.Event.new_eos())

        while spin_lock['done'] is not True:
            await asyncio.sleep(0.1)
    except Exception:
        pass


async def wait_for_pending_state_none(element):
    (_, state, pending_state) = element.get_state(1)
    while pending_state != Gst.State.VOID_PENDING:
        (_, state, pending_state) = element.get_state(1)
        await asyncio.sleep(0.1)
