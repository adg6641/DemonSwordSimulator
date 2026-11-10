"""Fixed-length joints for the hero's ground movement, crouch and jump."""
import json
from math import acos, atan2, cos, exp, hypot, pi, sin, sqrt

from pico2d import SDL_SetTextureColorMod


GROUND = {
    'idle_breathe', 'idle_to_walk', 'walk', 'walk_to_run', 'run_start', 'run',
    'run_to_walk', 'walk_to_idle', 'run_stop',
    'crouch_down', 'crouch_up', 'crouch_idle', 'crouch_walk',
}
AIR = {'jump_takeoff', 'jump_rise', 'jump_apex', 'fall', 'land_soft', 'land_hard'}
# Idle and walking use whole-body sprites. Keep their names in GROUND for stride tracking.
RIG_CLIPS = (GROUND | AIR) - {'idle_breathe', 'idle_to_walk', 'walk', 'walk_to_idle'}

THIGH = 40.3
SHIN = 36.5
ANKLE = 14.4


def lerp(a, b, t):
    return a + (b-a)*t


def unit(value):
    return max(0.0, min(1.0, value))


def ease(value):
    t=unit(value)
    return t*t*(3-2*t)


def rotated(point, angle):
    x,y=point
    c,s=cos(angle),sin(angle)
    return x*c+y*s, y*c-x*s


def add(p, q):
    return p[0]+q[0],p[1]+q[1]


def leg(hip, foot):
    """Keep both bones the same length. The knee bends towards the toes."""
    dx,dy=foot[0]-hip[0],foot[1]-hip[1]
    raw=hypot(dx,dy)
    length=max(8,min(THIGH+SHIN-.8,raw))
    angle=atan2(dy,dx)
    bend=acos(max(-1,min(1,(THIGH*THIGH+length*length-SHIN*SHIN)/(2*THIGH*length))))
    knee=add(hip,(THIGH*cos(angle+bend),THIGH*sin(angle+bend)))
    ankle=add(hip,(length*cos(angle),length*sin(angle))) if raw!=length else foot
    return hip,knee,ankle


def foot_at(phase, stride, contact, lift):
    """During contact the boot stays at one world position."""
    p=phase%1
    reach=stride*contact/2
    if p<contact:
        return reach-stride*p, ANKLE, 0.0
    t=(p-contact)/(1-contact)
    # Match the backwards ground speed on both sides of the swing.
    tangent=-stride*(1-contact)
    travel=lerp(-reach,reach,ease(t))+tangent*(2*t**3-3*t*t+t)
    arc=sin(pi*t)
    return travel,ANKLE+lift*arc*arc,.48*sin(2*pi*t)*arc


def sole_height(angle):
    # The toe and heel may roll, but neither corner may dip below the surface.
    return max(-rotated((x,-14.2),angle)[1] for x in (-8.7,21.3))+.2


class HeroRig:
    def __init__(self, folder):
        self.folder=folder
        data=json.loads((folder/'locomotion_parts.json').read_text(encoding='utf8'))
        self.filename=data['image']
        self.density=data['density']
        self.parts=data['parts']
        self.image=None
        self.reset()

    def preload(self):
        if self.image is None:
            from animation import load_pixel_image
            self.image=load_pixel_image(self.folder/self.filename,smooth=True)

    def reset(self):
        self.phase=.22
        self.motion=self.pace=self.duck=self.air=self.compress=self.time=0.0
        self.tuck=0.0
        self.rise=0.0
        self.last_facing=1
        self.grounded=True
        self.air_time=0.0
        self.land_time=1.0
        self._pose()

    def update(self, dt, distance, facing, grounded, vy, name):
        if dt<=0:
            return
        self.time+=dt
        speed=min(340,abs(distance)/dt)
        if grounded and not self.grounded:
            self.land_time=0
        elif grounded:
            self.land_time+=dt
        self.air_time=0 if grounded else self.air_time+dt
        self.grounded=grounded
        ground_speed=speed if grounded and name in GROUND else 0.0
        self.motion=lerp(self.motion,unit(ground_speed/135),1-exp(-17*dt))
        self.pace=lerp(self.pace,unit((ground_speed-158)/162),1-exp(-13*dt))
        self.duck=lerp(self.duck,float(name in {'crouch_down','crouch_idle','crouch_walk'}),1-exp(-16*dt))
        self.air=lerp(self.air,float(not grounded),1-exp(-20*dt))
        self.rise=lerp(self.rise,max(-1,min(1,vy/750)),1-exp(-19*dt))
        self.tuck=lerp(self.tuck,(1-abs(self.rise)) if not grounded else 0,1-exp(-13*dt))
        squat=.45 if name=='jump_takeoff' and grounded else 0.0
        if grounded and self.land_time<.24:
            squat=max(squat,.78*sin(pi*self.land_time/.24)**1.2)
        self.compress=lerp(self.compress,squat,1-exp(-22*dt))
        stride=lerp(lerp(116,188,self.pace),73,self.duck)
        contact=lerp(lerp(.62,.42,self.pace),.69,self.duck)
        if facing!=self.last_facing:
            self.phase=(contact-self.phase)%1
        self.last_facing=facing
        if ground_speed:
            self.phase=(self.phase+abs(distance)/stride)%1
        self._pose()

    def _pose(self):
        weight,pace,low,air=self.motion,self.pace,self.duck,self.air
        stride=lerp(lerp(116,188,pace),73,low)
        contact=lerp(lerp(.62,.42,pace),.69,low)
        lift=lerp(lerp(10,24,pace),8,low)
        step=4*pi*self.phase
        breath=.65*sin(self.time*2.7)*(1-weight)
        y=lerp(84,46,low)-lerp(2.2,3.7,pace)*cos(step)*weight-12*self.compress+breath
        y=lerp(y,81+3*self.tuck,air)
        hip_x=lerp(0,4,low)+1.9*sin(step)*weight
        descent=ease(-self.rise)
        feet=[]
        for near in (False,True):
            shift=0 if near else .5
            phase=self.phase+shift
            foot=foot_at(phase,stride,contact,lift)
            stance=lerp(17,13,low) if near else lerp(-26,-15,low)
            x=lerp(stance,foot[0],weight)
            fy=lerp(ANKLE,foot[1],weight)
            boot_turn=foot[2]*weight
            # One leg leads in the air, the other trails. They fold and extend continuously.
            tuck=self.tuck
            ax=(15+8*tuck+11*descent) if near else (-17+10*tuck-4*descent)
            ay=ANKLE+(7+20*tuck if near else 4+11*tuck)*(1-.55*descent)
            x=lerp(x,ax,air)
            fy=lerp(fy,ay,air)
            boot_turn=lerp(boot_turn,(-.12 if near else .32)*tuck,air)
            fy=max(fy,sole_height(boot_turn))
            feet.append((x,fy,boot_turn,phase))
            # Let the pelvis follow an extended support leg before the ankle leaves the floor.
            dx=x-hip_x-(-3 if near else 4)
            reach=THIGH+SHIN-1.1
            y=min(y,fy+sqrt(max(0,reach*reach-dx*dx))+3)
        hip=(hip_x,y)
        lean=.055+weight*lerp(.075,.36,pace)+.60*low+.12*self.compress
        lean=lerp(lean,.19+.10*self.rise,air)
        neck=add(hip,rotated((0,42),lean))
        # Keep the gaze steady while the pelvis rises, lands and runs.
        head=add(neck,(1,5))
        cape=add(neck,rotated((-10,-4),lean))
        cape_turn=-.34+(.21+.29*pace)*weight+.16*air+.06*sin(2*pi*self.phase-.8)*weight
        limbs=[]
        for near,(x,fy,boot_turn,phase) in enumerate(feet):
            center=add(hip,(-3 if near else 4,-3))
            thigh,knee,ankle=leg(center,(x,fy))
            shoulder=add(hip,rotated((-13 if near else 11,33),lean))
            opposite=-cos(2*pi*phase)
            swing=opposite*weight*lerp(.22,.43,pace)*(.70 if near else 1)
            upper=(-.12 if near else .02)+swing+.23*low
            upper=lerp(upper,-.15+(.24 if near else .47)*self.tuck+(-.20 if near else .35)*descent,air)
            lower=upper+(.53 if near else .30)+pace*weight*(.64 if near else 1.02)
            lower=lerp(lower,.82+.39*self.tuck,air)
            elbow=add(shoulder,(26*sin(upper),-26*cos(upper)))
            hand=add(elbow,(25*sin(lower),-25*cos(lower)))
            limbs.append((thigh,knee,ankle,boot_turn,shoulder,elbow,hand,lower))
        self.pose=hip,lean,head,cape,cape_turn,limbs
        self.hand=limbs[-1][6]
        self.blade_angle=.43-.14*pace*weight-.12*low+.031*sin(2*pi*self.phase)*weight-.09*air

    def _piece(self, name, at, angle, x, y, facing, scale):
        from animation import draw_region
        part=self.parts[name]
        w,h=part['size']
        u,v=part['pivot']
        cx,cy=rotated(((.5-u)*w,(v-.5)*h),angle)
        draw_region(self.image,part['rect'],x+facing*(at[0]+cx)*scale,y+(at[1]+cy)*scale,
                    scale/self.density,facing,angle*facing)

    def _bone(self, name, start, end, x, y, facing, scale):
        part=self.parts[name]
        w,h=part['size']
        u,v=part['pivot']
        ex,ey=part['tip']
        source=atan2((ey-v)*h,(ex-u)*w)
        angle=atan2(start[1]-end[1],end[0]-start[0])-source
        self._piece(name,start,angle,x,y,facing,scale)

    def draw(self, x, y, facing, scale):
        self.preload()
        hip,lean,head,cape,cape_turn,limbs=self.pose
        self._piece('cape',cape,cape_turn,x,y,facing,scale)
        for near,(thigh,knee,ankle,foot,shoulder,elbow,hand,wrist) in enumerate(limbs):
            if not near:
                SDL_SetTextureColorMod(self.image.texture,170,175,191)
            self._bone('shin',knee,ankle,x,y,facing,scale)
            self._piece('boot',ankle,foot,x,y,facing,scale)
            self._bone('thigh',thigh,knee,x,y,facing,scale)
            self._bone('forearm',elbow,hand,x,y,facing,scale)
            if not near:
                self._piece('free_hand',hand,-wrist,x,y,facing,scale)
            self._bone('upper_arm',shoulder,elbow,x,y,facing,scale)
            if not near:
                SDL_SetTextureColorMod(self.image.texture,255,255,255)
                self._piece('head',head,-.04-.14*lean,x,y,facing,scale)
                self._piece('torso',hip,lean,x,y,facing,scale)

    def draw_grip(self, x, y, facing, scale):
        self._piece('grip',self.hand,-.08,x,y,facing,scale)
