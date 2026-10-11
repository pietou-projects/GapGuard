"""Offline fixtures. No network, GPIO, heater, or real G-code execution."""
import collections,contextlib,importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from gapguard import GapGuard,Machine,Native,Settings
P=Path(__file__).resolve().parent
SOURCE_ROOT=P.parent/'GapGuard_sources_20261002/snapshot/klipper/klippy'
def module(name):
    spec=importlib.util.spec_from_file_location('elegoo_'+name.replace('/','_'),str(SOURCE_ROOT/(name+'.py')))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def settings(**kw):return Settings(kw)
class Port:
    def __init__(self,m):
        self.m=m;self.time=.3;self.pos=0.;self.n=Native('printing',True,'/job.gcode');self.calls=[]
    def now(self):return self.time
    def tick(self):
        self.time+=.25;self.m.observe(self.time,self.n,self.pos)
        if self.m.claim_pause(self.n):
            self.calls.append(('native_pause',));self.n=Native('paused',False,self.n.path)
            self.m.observe(self.time,self.n,self.pos)
def session():
    m=Machine(settings());p=Port(m);m.start_ready(0.,12);m.gpio(.1,2,0.)
    m.reset(.2,pending_new=True);m.observe(p.now(),p.n,p.pos);return m,p
def paused():
    m,p=session();p.n=Native('paused',False,p.n.path);p.time+=1;m.observe(p.time,p.n,p.pos);return m,p
def adapter(m=None,p=None):
    if m is None:m,p=session()
    a=object.__new__(GapGuard);a.machine=m;a.s=m.s
    a.motion_trace=False;a._trace_previous_edge=None
    a._saved_fan1=a._fan_restore_pending=None
    a.fan1=NS(scale=255.,get_status=lambda t:{"value":0.})
    a._scheduled=a._busy=False;a._wake_id=0;a._wake_stamp=None;a._wake_time=float('inf')
    a._edges=collections.deque();a._boot_snapshot=None;a._dead=False
    a.extruder_name="extruder";a._monitor_timer=object();a.now=p.now;a.native=lambda:p.n;a.position=lambda t:p.pos
    a.printer=NS(is_shutdown=lambda:False)
    a.button_group=NS(mcu=NS(is_shutdown=lambda:False))
    callbacks=[];out=[];scripts=[]
    a.reactor=NS(register_callback=lambda cb,when:callbacks.append((cb,when)),update_timer=lambda *a:None,NEVER=1e30)
    def script(s):
        scripts.append(s)
        if s=='PAUSE':p.n=Native('paused',False,p.n.path)
    a.gcode=NS(get_mutex=contextlib.nullcontext,run_script_from_command=script,respond_info=out.append)
    a.gcmd=NS(respond_info=out.append,error=ValueError,get_int=lambda name,default,**kw:default)
    def drain(limit=30):
        count=0
        while callbacks:
            cb,when=callbacks.pop(0);p.time=max(p.time,when);cb(p.time);count+=1
            if count>limit:raise AssertionError('callback loop')
    return a,p,callbacks,scripts,out,drain
