"""Sculpt the village characters' heads in the shared rest skeleton."""
import math
from bisect import bisect_right

# Height, half width, distance from the center to the face and to the back of the skull.
PROFILE = (
    (1.153,.037,.067,.036), (1.173,.062,.110,.062), (1.195,.084,.126,.092),
    (1.222,.102,.132,.111), (1.252,.116,.132,.126), (1.284,.126,.130,.140),
    (1.312,.129,.132,.145), (1.341,.127,.139,.148), (1.369,.123,.129,.148),
    (1.399,.112,.110,.139), (1.429,.091,.087,.119), (1.454,.061,.056,.089),
    (1.469,.027,.022,.044), (1.474,.004,.003,.007),
)
HAIR = {
    "player": ("855a38", "b88351"),
    "boy": ("705139", "997449"),
    "girl": ("694631", "956844"),
    "man": ("4f453c", "776a58"),
    "woman": ("77665d", "aa9584"),
}


def build_head(style, head, eyes, oval, emit):
    adult = style in ("man", "woman")
    width = {"player":1., "boy":1.03, "girl":.96, "man":.95, "woman":.91}[style]
    eye_y = 1.307
    skin = {"player":(223,173,135), "boy":(224,176,137), "girl":(229,180,147),
            "man":(204,155,120), "woman":(222,170,138)}[style]
    heights = [row[0] for row in PROFILE]

    def profile(y):
        i = min(len(heights)-2, max(0,bisect_right(heights,y)-1))
        a,b=PROFILE[i:i+2]
        t=(y-a[0])/(b[0]-a[0])
        # Smooth tangents keep the face and the silhouette rounded between the profiles.
        p=PROFILE[max(0,i-1)]
        q=PROFILE[min(len(heights)-1,i+2)]
        dims=[]
        for j in (1,2,3):
            m0=(b[j]-p[j])*(b[0]-a[0])/(b[0]-p[0])
            m1=(q[j]-a[j])*(b[0]-a[0])/(q[0]-a[0])
            dims.append(a[j]+t*(m0+t*(3*(b[j]-a[j])-2*m0-m1+t*(2*(a[j]-b[j])+m0+m1))))
        w,front,back=dims
        jaw=math.exp(-((y-1.214)/.046)**2)
        return w*width*(1+.10*jaw if style=="man" else 1-.06*jaw if style=="woman" else 1),front,back

    def local(x,y,cx,cy,sx,sy):
        return math.exp(-((x-cx)/sx)**2-((y-cy)/sy)**2)

    def front_depth(x,y,forward,f):
        ax=abs(x)
        face = f*forward*(1.42-.42*forward)
        face -= .015*local(ax,y,.054,eye_y,.034,.018)
        face += (.011 if adult else .014)*local(ax,y,.086,1.267,.043,.029)
        face += .008*local(ax,y,.052,eye_y+.026,.038,.018)
        nose = (.040 if adult else .030)*local(x,y,0,1.273,.024,.019)
        nose += .021*local(x,y,0,1.302,.018,.038)
        nose += .016*local(ax,y,.017,1.267,.012,.012)
        face += nose + .008*local(x,y,0,1.222,.045,.020)
        return face

    def head_point(y,angle):
        w,f,b=profile(y)
        x=w*math.cos(angle)
        forward=math.sin(angle)
        z=front_depth(x,y,forward,f) if forward>0 else b*forward
        return x,y,z

    def face_depth(x,y):
        w,f,_=profile(y)
        return front_depth(x,y,math.sqrt(max(0,1-(x/w)**2)),f)

    def pack(point):
        return tuple(round(q*1000) for q in point)

    def paint(rgb, factor=1):
        return "".join(f"{min(255,max(0,round(q*factor))):02x}" for q in rgb)

    def head_paint(point):
        x,y,z=(p/1000 for p in point)
        warm=local(abs(x),y,.093,1.263,.038,.032) if z>.065 else 0
        jaw=math.exp(-((y-1.187)/.060)**2)
        upper=math.exp(-((y-1.374)/.061)**2)
        value=1-.035*jaw+.034*upper
        if style=="man":
            value-=.064*local(x,y,0,1.192,.102,.024)*float(z>0)
        return paint((skin[0]+7*warm,skin[1]-6*warm,skin[2]-4*warm),value)

    def rings(rows, pigment):
        quads=[]
        for bottom,top in zip(rows,rows[1:]):
            for i in range(len(bottom)):
                j=(i+1)%len(bottom)
                quads.extend(((bottom[i],top[i],top[j],pigment),(bottom[i],top[j],bottom[j],pigment)))
        for i in range(1,len(rows[-1])-1):
            quads.append((rows[-1][0],rows[-1][i+1],rows[-1][i],pigment))
        emit(quads,head)

    directions=[i*math.tau/56 for i in range(56)]
    levels=sorted(set(heights + [1.153+i*.008 for i in range(1,41)] + [1.260,1.273,1.307]))
    rings([[pack(head_point(y,a)) for a in directions] for y in levels],head_paint)

    dark_hair,lit_hair=([*bytes.fromhex(c)] for c in HAIR[style])
    colors={}
    scalp=[]
    for i in range(16):
        t=i/15
        band=[]
        for angle in directions:
            front=math.sin(angle)
            sweep=math.cos(angle)
            swept_lock=0
            if front>0:
                hairline=1.315+(.082 if adult else .072)*front**1.36
                hairline+=.012*front*math.sin(angle*2.9+(.7 if style=="boy" else -.2))
                if style in ("player","boy"):
                    swept_lock=math.exp(-((angle-(1.20 if style=="player" else 1.85))/.48)**2)
                    hairline-=.015*swept_lock
                hairline+=.0035*front*math.sin(angle*16)
            else:
                hairline=1.315+(.077 if style in ("girl","woman") else .055)*front
            y=hairline+(heights[-1]-hairline)*math.sin(t*math.pi/2)
            x,_,z=head_point(y,angle)
            curl=.0032*math.sin(angle*11+1.6*t)
            rise=min(1,t*6)
            bulk=.010+.005*math.sin(t*math.pi)+.010*swept_lock
            bump=(rise*bulk-.0015)*math.cos(t*math.pi/2)+curl*math.sin(math.pi*t)
            p=pack((x+math.cos(angle)*bump,y+.011*t+.009*swept_lock*math.sin(math.pi*t),z+front*bump))
            band.append(p)
            gleam=.32+.15*sweep+.12*math.sin(angle*13+4*t)+.18*t
            colors[p]=paint(tuple(a+(b-a)*gleam for a,b in zip(dark_hair,lit_hair)))
        scalp.append(band)
    rings(scalp,colors.__getitem__)

    def feature(x,y,w,up,down,offset,pigment,index,curve=0.,bulge=0.,spread=16):
        def vertex(dx,dy,crown=0):
            px,py=x+dx,y+dy+curve*(dx/w)**2
            return pack((px,py,face_depth(px,py)+offset+bulge*crown))

        center=vertex(0,0,1)
        rim=[]
        for i in range(spread):
            angle=i*math.tau/spread
            vertical=math.sin(angle)
            rim.append(vertex(w*math.cos(angle),(up if vertical>=0 else down)*vertical))
        emit([(center,p,rim[(i+1)%spread],pigment) for i,p in enumerate(rim)],index)

    for side in (-1,1):
        ear_x=profile(1.286)[0]
        oval(side*(ear_x+.003),1.283,.011,.021,.036,.024,paint(skin,.97),head,10)
        oval(side*(ear_x+.018),1.282,.019,.007,.020,.015,paint(skin,.88),head,8)
        x=side*(.052 if not adult else .050)
        eye_w=.023 if not adult else .021
        feature(x,eye_y,eye_w+.002,.012,.010,.006,paint(skin,.78),eyes,bulge=.005)
        feature(x,eye_y,eye_w,.0095,.0075,.009,"e7dbc7",eyes,bulge=.005)
        iris={"player":"60503c","boy":"4f3b2c","girl":"526347","man":"594838","woman":"62645a"}[style]
        feature(x,eye_y+.0008,.0073,.0071,.007,.016,iris,eyes,bulge=.002)
        feature(x,eye_y+.0008,.0037,.0038,.004,.020,"322b25",eyes)
        feature(x-.0018,eye_y+.0037,.0016,.0016,.0014,.022,"f7ecd7",eyes,spread=8)
        feature(x+side*.003,eye_y+.030,.026,.0036,.0027,.004,HAIR[style][0],head,curve=-.004)
        feature(side*.014,1.263,.005,.002,.0017,.005,paint(skin,.69),head,spread=10)
    mouth_width=.036 if adult else .029
    mouth_curve=.003 if style in ("player","girl","boy") else .001
    feature(0,1.223,mouth_width,.0055,.005,.003,paint((skin[0]+6,skin[1]-21,skin[2]-16)),head,curve=mouth_curve)
    feature(0,1.223,mouth_width*.94,.0015,.0015,.006,paint(skin,.65),head,curve=mouth_curve)
    if style=="girl":
        for side in (-1,1):
            for i in range(5):
                oval(side*(.120+.008*i),1.290-.041*i,-.078-.013*i,
                     .030-.003*i,.032,.028-.003*i,HAIR[style][i%2],head,10)
            oval(side*.150,1.115,-.130,.021,.012,.020,"cd846a",head,8)
    elif style=="woman":
        oval(0,1.337,-.142,.060,.049,.063,HAIR[style][0],head,14)
