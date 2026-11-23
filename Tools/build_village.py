"""Build the original low-poly village meshes and the walkable layout. Python 3 only."""
import gzip
import json
import math
import random
import struct
from pathlib import Path

from build_car_panels import GRILLE, PLATE, SIZE, STRIP, build_atlas
from build_house_atlas import atlas_uv, build_house_atlas
from build_child import ADULTS, CHILDREN, PLAYER, child_assets, is_skinned

ROOT = Path(__file__).resolve().parents[1] / "Assets" / "Resources"
rng = random.Random(73)
meshes = {}
solids = []
vault_fences = set()
gates = []
trees = []
doors = []
residents = []
vegetable_patches = []
YARDS = ((-14.6,2.4),(14.7,2.4),(-14.8,20.4),(14.9,20.4),
         (-14.9,38.7),(16.4,38.7),(16.6,56.4))
ROAD_HEIGHT = .04
BOUNDS = (-48.0, 48.0, -17.15, 87.71)
TRACK = [(-10.65,.15,3.15),(-8,.30,2.82),(-3,.18,2.65),(3,-.28,2.58),
         (7,-.20,2.55),(12,0,2.62),(17,.14,2.69),(22,.35,2.42),(26,.31,2.0),
         (31,.05,1.80),(36,.16,1.52),(44,1.1,1.12),(52,3.2,1.08),
         (61,1.8,.96),(68,-.55,.94),(77,-1.8,.86),(86.8,-1.2,.57)]
group = "01 Ground"
origin = (0, 0, 0)
angle = 0


def color(hex_value):
    return tuple(bytes.fromhex(hex_value)) if isinstance(hex_value, str) else hex_value


def tint(hex_value, factor):
    return tuple(max(0, min(255, round(v * factor))) for v in color(hex_value))


def transform(point):
    x, y, z = point
    ox, oy, oz = origin
    return (ox + x * math.cos(angle) + z * math.sin(angle),
            oy + y,
            oz - x * math.sin(angle) + z * math.cos(angle))


def triangle(a, b, c, paint, vertex_paint=None):
    if isinstance(paint, str):
        paint = color(paint)
    colors = vertex_paint or (paint, paint, paint)
    mesh = meshes.setdefault(group, bytearray())
    for point, vertex_color in zip((a, b, c), colors):
        coords = [round(value * 100) for value in transform(point)]
        mesh.extend(struct.pack("<hhhBBB", *coords, *vertex_color))


def quad(a, b, c, d, paint):
    triangle(a, b, c, paint)
    triangle(a, c, d, paint)


def box(x, y, z, w, h, d, paint, roll=0):
    points = []
    for a, b, c in (
        (-1,-1,-1), (1,-1,-1), (1,1,-1), (-1,1,-1),
        (-1,-1,1), (1,-1,1), (1,1,1), (-1,1,1),
    ):
        px, py = a*w/2, b*h/2
        points.append((x + px*math.cos(roll) - py*math.sin(roll),
                       y + px*math.sin(roll) + py*math.cos(roll), z+c*d/2))
    faces = ((0,3,2,1), (4,5,6,7), (0,4,7,3), (1,2,6,5), (3,7,6,2), (0,1,5,4))
    for face, light in zip(faces, (.97, 1, .91, 1, 1.04, .84)):
        quad(*(points[i] for i in face), tint(paint, light))


def prism(rings, paint, vary=.1):
    for lower, upper in zip(rings, rings[1:]):
        for i in range(len(lower)):
            j = (i + 1) % len(lower)
            quad(lower[i], upper[i], upper[j], lower[j], tint(paint, rng.uniform(1-vary, 1+vary)))
    for i in range(1, len(rings[0])-1):
        triangle(rings[0][0], rings[0][i], rings[0][i+1], tint(paint, .88))
        triangle(rings[-1][0], rings[-1][i+1], rings[-1][i], tint(paint, 1.03))


def ring(x, y, z, rx, rz, sides, rotation=0):
    return [(x + rx*math.cos(rotation + i*math.tau/sides), y,
             z + rz*math.sin(rotation + i*math.tau/sides)) for i in range(sides)]


def cylinder(x, y, z, r, height, paint, sides=7, r_top=None, lean=(0, 0)):
    prism([ring(x, y-height/2, z, r, r, sides),
           ring(x+lean[0], y+height/2, z+lean[1],
                r if r_top is None else r_top, r if r_top is None else r_top, sides)], paint)


def boulder(x, y, z, w, h, d, paint, sides=7):
    rotation = rng.uniform(0, .9)
    prism([ring(x, y-h*.47, z, w*.25, d*.28, sides, rotation),
           ring(x, y-h*.18, z, w*.50, d*.50, sides, rotation),
           ring(x+w*.08, y+h*.26, z-d*.06, w*.43, d*.39, sides, rotation),
           ring(x+w*.08, y+h*.50, z-d*.10, w*.13, d*.15, sides, rotation)], paint, .13)


def solid(x, y, z, w, h, d, vault=False):
    cx, cy, cz = transform((x, y, z))
    cosine, sine = abs(math.cos(angle)), abs(math.sin(angle))
    if vault:
        vault_fences.add(len(solids))
    solids.append([round(v, 3) for v in (cx, cy, cz, w*cosine + d*sine, h, w*sine + d*cosine)])


def set_piece(name, position=(0,0,0), rotation=0):
    global group, origin, angle
    group, origin, angle = name, position, math.radians(rotation)


def ground():
    for ix in range(-34, 34):
        for iz in range(-20, 43):
            x, z = ix*3, iz*3
            tones = ("8c9c52","85974d","889747","91a058","87984f","929e55")
            tone = color(rng.choice(tones))
            quad((x,0,z),(x,0,z+3),(x+3,0,z+3),(x+3,0,z),tone)


def strip_mesh(rows):
    """The shoulders, wheel tracks and road bed are adjacent triangles on one surface."""
    for left, right in zip(rows, rows[1:]):
        for a, b, c, d in zip(left, right, right[1:], left[1:]):
            triangle(a[0], b[0], c[0], None, (a[1], b[1], c[1]))
            triangle(a[0], c[0], d[0], None, (a[1], c[1], d[1]))


def lane_cross_section(z):
    for (z0, x0, w0), (z1, x1, w1) in zip(TRACK, TRACK[1:]):
        if z <= z1:
            t = max(0, (z-z0)/(z1-z0))
            return x0+(x1-x0)*t, w0+(w1-w0)*t
    return TRACK[-1][1:]


def roads():
    set_piece("02 Roads")
    bands = [(-1,"8e9253"),(-.88,"aa996f"),(-.56,"caba90"),(-.43,"b79f79"),
             (-.33,"b29b73"),(-.22,"c4b087"),(0,"c2ab80"),(.22,"c4b087"),
             (.33,"b29b73"),(.43,"b79f79"),(.56,"caba90"),(.88,"aa996f"),(1,"8e9253")]
    sections = []
    for (start, *_), (end, *_) in zip(TRACK, TRACK[1:]):
        n = math.ceil((end-start)/.71)
        sections.extend(start+(end-start)*i/n for i in range(n))
    sections.append(TRACK[-1][0])
    rows = []
    for z in sections:
        x, w = lane_cross_section(z)
        broad_noise = 1 + .038*math.sin(z*1.66) + .026*math.sin(z*.41)
        rows.append([((x+w*f, ROAD_HEIGHT, z), tint(paint, broad_noise*rng.uniform(.94,1.06)))
                     for f,paint in bands])
    strip_mesh(rows)

    # Asphalt and its markings are tiled side by side, with no decal at the same depth.
    for x in range(-90,90,3):
        for z0,z1,paint in ((-17.1,-16.6,"aa9c76"),(-16.6,-13.90,"797c76"),
                            (-13.90,-13.82,"b8b5a0" if abs(x)>5 and x%9==0 else "797c76"),
                            (-13.82,-11.13,"797c76"),(-11.13,-10.65,"aa9c76")):
            y = ROAD_HEIGHT
            quad((x,y,z0),(x,y,z1),(x+3,y,z1),(x+3,y,z0),tint(paint,rng.uniform(.98,1.02)))
    for x in range(-58,59,4):
        box(x,.42,-17.65,.12,.84,.12,"a9a88f")
        box(x,.73,-17.55,.11,.24,.07,"bb5d42")
    solid(0,1.0,-17.4,116,2,.24)


def house_surface(vertices, paint, material, uvs):
    mesh = meshes.setdefault(group.replace("House ", "House skin ", 1), bytearray())
    indices = (0,1,2,0,2,3) if len(vertices) == 4 else (0,1,2)
    rgb = color(paint) if isinstance(paint, str) else paint
    for i in indices:
        point = [round(value*100) for value in transform(vertices[i])]
        uv = atlas_uv(material, *uvs[i])
        mesh.extend(struct.pack("<hhhBBBHH", *point, *rgb, *(round(value*65535) for value in uv)))


def wall_patch(x0, x1, y0, y1, z, paint, material, mirror=False):
    u0, u1 = (1,0) if mirror else (0,1)
    house_surface(((x0,y0,z),(x0,y1,z),(x1,y1,z),(x1,y0,z)), paint, material,
                  ((u0,0),(u0,1),(u1,1),(u1,0)))


def wall_courses(length, base, z, paint, old, doorway, vertical, variations, random):
    if vertical:
        count = math.ceil(length/.225)
        for i in range(count):
            left = -length/2 + i*length/count
            right = left + length/count
            bottom = 2.32 if doorway and left < .52 and right > -.52 else .47
            for y0,y1 in ((bottom,(bottom+base)/2),((bottom+base)/2,base)):
                house_surface(((left,y0,z),(left,y1,z),(right-.013,y1,z),(right-.013,y0,z)),
                              tint(paint, random.uniform(.84,1.08)), "boards",
                              ((0,0),(1,0),(1,1),(0,1)))
        return
    count = round((base-.47)/(.224 if old else .155))
    profile = ((0,.02),(.21,.062),(.47,.081),(.73,.065),(1,.014)) if old else ((0,.029),(.86,.019),(1,0))
    tile_count = math.ceil(length/3)
    for row in range(count):
        start = .47 + row*(base-.47)/count
        height = (base-.47)/count
        edges = (-length/2, -.52, .52, length/2) if doorway and start < 2.32 else (-length/2,length/2)
        segments = zip(edges[::2], edges[1::2])
        tone = variations[row % len(variations)] * random.uniform(.96,1.04)
        paint_row = tint(paint, tone * (.86 + .14*min(1,row/6)))
        for lo,hi in segments:
            tiles = max(1,round((hi-lo)/length*tile_count))
            for tile in range(tiles):
                x0,x1 = lo+(hi-lo)*tile/tiles, lo+(hi-lo)*(tile+1)/tiles
                flip = (tile+row)%3 == 1
                u0,u1 = (1,0) if flip else (0,1)
                for (v0,depth0),(v1,depth1) in zip(profile,profile[1:]):
                    y0 = start + height*v0 + (.006 if v0==0 else 0)
                    y1 = start + height*v1 - (.006 if v1==1 else 0)
                    if doorway and y0 < 2.32 and y1 > 2.32:
                        y1 = 2.32
                    house_surface(((x0,y0,z-depth0),(x0,y1,z-depth1),(x1,y1,z-depth1),(x1,y0,z-depth0)),
                                  paint_row,"log" if old else "boards",((u0,v0),(u0,v1),(u1,v1),(u1,v0)))
        if old:
            for x in (-length/2,length/2):
                log_end(x,start+height*.53,z-(.22 if row%2 else .14),height*.47,paint_row)


def log_end(x, y, z, radius, paint):
    def point(i, r, depth):
        angle = math.tau*i/9
        return (x+r*math.cos(angle),y+r*math.sin(angle),z+depth)

    bark = tuple(int(c*.73) for c in paint)
    for i in range(9):
        a,b = point(i,radius*.92,0),point(i+1,radius*.92,0)
        p,q = point(i,radius,.038),point(i+1,radius,.038)
        r,s = point(i,radius*.98,.33),point(i+1,radius*.98,.33)
        quad(q,b,a,p,bark)
        quad(s,q,p,r,bark)
        house_surface(((x,y,z),b,a),paint,"end grain",
                      ((.5,.5),(.5+(b[0]-x)/(2*radius),.5+(b[1]-y)/(2*radius)),
                       (.5+(a[0]-x)/(2*radius),.5+(a[1]-y)/(2*radius))))


def carved_edge(x, y, z, width, trim, count=9, drop=.088):
    for i in range(count):
        a = x-width/2 + i*width/count
        b = a + width/count
        triangle((a,y,z),((a+b)/2,y-drop*(.70 if i%2 else 1),z),(b,y,z),trim)


def house_window(x, y, z, trim, width, height, style, curtains):
    old = style in (0,2,4)
    reveal = "403c31" if old else "5d5947"
    box(x,y,z,width+.14,height+.14,.065,reveal)
    glass = "78948d" if old else "9cb4ac"
    wall_patch(x-width/2,x+width/2,y-height/2,y+height/2,z-.047,glass,"glass",x>0)
    if curtains:
        side = 1 if curtains == 1 else -1
        left,right = sorted((x+side*width*.48,x+side*width*.257))
        wall_patch(left,right,y-height*.45,y+height*.48,z-.065,
                   ("dfdbbf","c1b39c","b1c4b6")[style%3],"curtain",side<0)
        if curtains == 2:
            wall_patch(x-width*.43,x+width*.45,y-height*.46,y-height*.27,z-.083,"ccc3ad","curtain")
    jamb, face = (.112,.081) if old else (.085,.067)
    opening_width = width - .34*jamb
    opening_height = height - face
    # Join the frame and sash at their edges. Overlapping faces at the same depth
    # can flicker after the mesh positions are rounded to centimeters.
    for side in (-1,1):
        rail_x = x+side*(width/2+jamb*.33)
        box(rail_x,y,z-.087,jamb,height+.18,.113,trim)
        if old:
            wall_patch(rail_x-.027,rail_x+.027,y-height*.46,y+height*.46,z-.163,
                       tint(trim,.76),"paint",side>0)
            for k in range(4):
                yy=y-height*.38+k*height*.25
                box(rail_x,yy,z-.176,.056,.052,.022,trim,.785)
    for yy in (-height/2,height/2):
        box(x,y+yy,z-.087,opening_width,face,.113,trim)
    center_bar = .041
    box(x,y,z-.095,center_bar,opening_height,.058,trim)
    if old or style in (1,5):
        cross_y = y+height*.16
        cross_width = (opening_width-center_bar)/2
        for side in (-1,1):
            box(x+side*(center_bar+cross_width)/2,cross_y,z-.095,cross_width,.040,.058,trim)
        for dx in (-width*.25,width*.25):
            for lo, hi in ((y-height*.15,cross_y-.020),(cross_y+.020,y+opening_height/2)):
                box(x+dx,(lo+hi)/2,z-.095,.022,hi-lo,.058,trim)
    box(x,y-height/2-.075,z-.08,width+.26,.087,.235,tint(trim,.88))
    if old:
        top = y+height/2+.075
        extension = width+.25
        box(x,top,z-.083,extension,.129,.158,trim)
        box(x,top+.082,z-.095,extension+.056,.044,.176,tint(trim,1.13))
        carved_edge(x,top-.015,z-.188,extension-.045,trim,10 if style==2 else 8,.071)
        if style != 4:
            triangle((x-extension*.33,top+.094,z-.205),(x,top+.234,z-.205),
                     (x+extension*.33,top+.094,z-.205),trim)
            box(x,top+.112,z-.217,.080,.080,.024,tint(trim,.71),.785)


def stone_steps(z, style, trim, paint):
    masonry = style in (1,3,5)
    tread = "777063" if masonry else "796651"
    box(0,.22,z-.66,2.14,.44,1.26,tread)
    solid(0,.22,z-.66,2.14,.44,1.26)
    for i in range(2):
        zz=z-1.65+i*.30
        box(0,.075*(i+1),zz,1.65,.15*(i+1),.33,tint(tread,1.16))
        solid(0,.075*(i+1),zz,1.65,.15*(i+1),.33)
        box(0,.15*(i+1)-.018,zz-.172,1.70,.041,.064,tint(tread,.87))
    for side in (-1,1):
        x=side*.98
        box(x,1.38,z-1.18,.108,1.99,.108,trim if masonry else paint)
        box(x,.94,z-.79,.105,.07,.84,tint(paint,.80))
        if style != 4:
            for k in range(3):
                box(x,.72,z-.55-k*.19,.048,.42,.048,tint(trim,.87))
        box(x,2.20,z-1.17,.099,.31,.09,trim,.44*side)
    front,back=z-1.61,z+.13
    edge,peak=2.39,2.82 if style in (1,3,5) else 2.61
    for sign in (-1,1):
        e=(sign*1.29,edge,front)
        r=(0,peak,front)
        q=(0,peak+.12,back)
        p=(sign*1.29,edge+.12,back)
        panel,uv=(e,r,q,p),((0,0),(0,1),(1,1),(1,0))
        if sign < 0:
            panel,uv=panel[::-1],uv[::-1]
        house_surface(panel,tint(tread,.95),"slate" if masonry else "steel",uv)
        fascia(e,r,front-.043,trim,.094)
    box(0,edge-.064,front+.025,2.48,.101,.12,paint)
    if not masonry:
        carved_edge(0,edge-.074,front-.047,2.24,trim,20,.060)


def fascia(a, b, z, paint, depth):
    x0,y0,_ = a
    x1,y1,_ = b
    if x0 > x1:
        x0,y0,x1,y1=x1,y1,x0,y0
    face=((x0,y0-depth,z),(x0,y0+.016,z),(x1,y1+.016,z),(x1,y1-depth,z))
    house_surface(face,paint,"paint",((0,0),(0,1),(1,1),(1,0)))
    quad(*face[::-1],tint(paint,.79))


def roof(w, d, base, peak, paint, trim, body, style, sheets, random):
    half=w/2+.38
    length=d/2+.46
    sag={0:.058,2:.047,4:.084}.get(style,0)
    offset={0:.16,2:-.13,4:.18}.get(style,0)
    material=("steel","steel","slate","slate","felt","steel","slate")[style]
    slices=max(6,math.ceil(length*2/(1.04 if material=="slate" else .81)))
    for side in (-1,1):
        eaves=(side*half,base)
        profile=[(offset,peak)]
        if style==3:
            profile.append((side*half*.67,base+1.63))
        profile.append(eaves)
        for j,((xa,ya),(xb,yb)) in enumerate(zip(profile,profile[1:])):
            for i in range(slices):
                z0,z1=((2*k/slices-1)*length for k in (i,i+1))
                def point(t,z):
                    return (xa+(xb-xa)*t,ya+(yb-ya)*t-sag*math.sin(math.pi*(z+length)/(2*length))*(1-.67*t),z)

                a,b,c,e=point(1,z0),point(0,z0),point(0,z1),point(1,z1)
                p=(a,b,c,e) if side>0 else (e,c,b,a)
                u=((0,0),(0,1),(1,1),(1,0)) if side>0 else ((1,0),(1,1),(0,1),(0,0))
                sheet = sheets[(i+j+slices*(side>0))%len(sheets)]
                house_surface(p,tint(paint,sheet),material,u)
                ceiling = tuple((x,y-.055,z) for x,y,z in p[::-1])
                house_surface(ceiling,tint(body,.64),"boards",u[::-1])
                if i and material in ("steel","felt"):
                    radii = (.028,.022) if material=="steel" else (.016,.032)
                    l,t=radii
                    seam=((a[0],a[1]+l,z0),(b[0],b[1]+l,z0),
                          (b[0],b[1]+l,z0+t),(a[0],a[1]+l,z0+t))
                    quad(*(seam if side>0 else seam[::-1]),tint(paint,1.14 if i%3 else .80))
            for z in (-length,length):
                fascia((xa,ya,z),(xb,yb,z),z+.021*math.copysign(1,z),trim,.153 if style in (0,2,4) else .121)
                if style in (0,2) and z<0:
                    for k in range(12):
                        t=(k+.5)/12
                        x=xa+(xb-xa)*t
                        y=ya+(yb-ya)*t-.161
                        triangle((x-.075,y+.052,z-.027),(x,y-.055,z-.027),(x+.075,y+.052,z-.027),trim)
        box(side*half,base-.083,0,.133,.166,length*2,tint(body,.70))
        for k in range(9):
            z=(k/4-1)*(length-.12)
            box(side*(half-.17),base-.139,z,.48,.124,.10,tint(body,.81))
        if style in (1,3,5,6):
            box(side*(half+.048),base-.074,0,.14,.085,length*2,"92968e")
            box(side*(half-.145),base/2,side*(length-.31),.084,base-.18,.084,"9b9e93")
    box(offset,peak+.018,0,.158,.086,length*2,tint(paint,1.13))

    # Each fronton sits over the wall, back from the roof edge.
    saved_origin,saved_angle=origin,angle
    for sign in (-1,1):
        if sign==1:
            set_piece(group,saved_origin,math.degrees(saved_angle)+180)
        z=-d/2-.024
        edge,top=base,peak-.02
        for i in range(7):
            x0=(i/3.5-1)*(w/2)
            x1=((i+1)/3.5-1)*(w/2)
            def height(x):
                t=abs(x)/(w/2)
                if style==3:
                    return edge + ((top-edge)+(1.55-(top-edge))*t/.67 if t<.67 else 1.55*(1-t)/.33)
                return edge+(top-edge)*(1-t)
            middle=(x0+x1)/2
            a,b,c,e=(x0,edge,z),(x0,height(x0),z),(x1,height(x1),z),(x1,edge,z)
            tinting=tint(body,random.uniform(.75,.93))
            if i==3:
                m=(middle,top,z)
                house_surface((a,b,m,e),tinting,"gable",((0,0),(1,0),(1,1),(0,1)))
                house_surface((m,c,e),tinting,"gable",((1,0),(1,1),(0,1)))
            else:
                house_surface((a,b,c,e),tinting,"gable",((0,0),(1,0),(1,1),(0,1)))
            if i not in (0,6):
                box(x0,(edge+height(x0))/2,z-.021,.034,height(x0)-edge,.049,tint(body,.72))
        house_window(0,edge+(top-edge)*(.39 if style==3 else .46),z-.032,
                     trim,.69 if style==3 else .47,.79 if style==3 else .58,style,0)
        box(0,base+.013,z-.031,w+.045,.080,.085,tint(trim,.83))
        set_piece(group,saved_origin,math.degrees(saved_angle))
    chimney_x=w*.26
    low,high=peak-.90,peak+.46
    box(chimney_x,(low+high)/2,.88,.47,high-low,.50,"985f4a")
    saved_origin,saved_angle=origin,angle
    at=transform((chimney_x,0,.88))
    for i in range(4):
        set_piece(group,at,math.degrees(saved_angle)+i*90)
        wall_patch(-.235,.235,low,high,-.259,"b2775c","brick",bool(i%2))
    set_piece(group,saved_origin,math.degrees(saved_angle))
    box(chimney_x,high,.88,.61,.109,.65,"52534d")
    box(chimney_x,high+.067,.88,.30,.037,.31,"302f29")


def house(style):
    detail_rng=random.Random(7904+style)
    w,d = ((8.0,6.7),(8.0,6.7),(8.0,6.7),(8.8,6.9),(7.4,6.3),(8.7,7.0),(7.4,6.8))[style]
    front=-d/2
    bases=(3.00,3.14,2.85,3.13,2.87,3.16,3.01)
    peaks=(5.28,4.92,5.18,5.88,4.66,5.25,4.72)
    base,peak=bases[style],peaks[style]
    trim = ("d2d4be","e6d3a7","9bc5c4","eadfc6","b5c9bc","caceb1","dadbd2")[style]
    body = ("846a53","7f9d8c","786853","b7784d","696659","a89b79","939c81")[style]
    cover = ("737b73","56756a","858575","b0ac99","5b6462","704c42","666e5d")[style]
    old=style in (0,2,4)
    palette=(.84,.94,1.02,1.095) if old else (.91,.965,1.015,1.066)
    wall_tones=[rng.choice(palette) for _ in range(11 if old else 60)]
    roof_tones=[rng.uniform(.86,1.09) for _ in range(24)]
    solid(0,base/2,0,w,base+.2,d)
    box(0,.24,0,w+.12,.48,d+.12,"756e60")
    box(0,(base+.4)/2,.25,w-.04,base-.4,d-.5,body)
    box(0,1.40,front+.46,1.02,1.86,.036,"493e34")
    anchor,rotation=origin,angle
    for face in range(4):
        length,depth = (w,d) if face%2==0 else (d,w)
        z=-depth/2
        set_piece(group,anchor,math.degrees(rotation)+90*face)
        pieces=math.ceil(length/1.4)
        for tile in range(pieces):
            left,right=((p/pieces-.5)*length for p in (tile,tile+1))
            wall_patch(left-(.06 if tile==0 else 0),right+(.06 if tile==pieces-1 else 0),.045,.46,z-.073,
                       "968579" if style in (1,3,5) else "8d8878",
                       "brick" if style in (1,3,5) else "rubble",bool(tile%2))
        rows = wall_tones if old else wall_tones[face*15:face*15+15]
        wall_courses(length,base,z,body,old,face==0,style==6 and face%2==1,rows,detail_rng)
        if not old:
            for x in (-length/2,length/2):
                box(x,(base+.48)/2,z-.025,.192,base-.48,.183,tint(trim,.87))
        if face==0:
            slots=(-2.73,-1.37,2.26) if style in (0,2) else (-2.37,2.11)
        elif face==2:
            slots=(-2.25,1.91) if style!=4 else (1.9,)
        else:
            slots=(-1.67,1.45)
        for i,x in enumerate(slots):
            width=.76 if len(slots)==3 else (1.15 if style in (1,3,5) else .86)
            house_window(x,1.71+(.05 if style==3 else 0),z-.093,trim,width,.97 if old else 1.06,
                         style,(i+face+style)%3)
        box(0,base-.062,z-.045,length+.075,.135,.145,tint(body,.76))
    set_piece(group,anchor,math.degrees(rotation))

    for x in (-.52,.52):
        box(x,1.39,front-.094,.13,1.93,.31,trim)
    box(0,2.365,front-.112,1.17,.13,.29,trim)
    stone_steps(front, style, trim, body)
    if style in (1,4,6):
        set_piece(group,anchor,math.degrees(rotation)+90)
        roof(d,w,base,peak,cover,trim,body,style,roof_tones,detail_rng)
        set_piece(group,anchor,math.degrees(rotation))
    else:
        roof(w,d,base,peak,cover,trim,body,style,roof_tones,detail_rng)
    if style in (0,2,5):
        for i in range(4):
            box(1.59+i*.24,.18,front-.47,.23,.35,.22+detail_rng.uniform(-.025,.035),
                "7f684e" if i%2 else "8c755a")

    hinge=transform((-.46,0,front-.20))
    doors.append({"mesh":"Door "+str(style),"point":list(hinge),"yaw":round(math.degrees(angle))})
    name,previous,previous_angle=group,origin,angle
    set_piece("Door "+str(style))
    paint=("48665b","a28961","516653","72523d","48696a","86725d","6c704e")[style]
    box(.46,1.40,0,.91,1.82,.085,paint)
    for px in (.12,.32,.52,.72):
        box(px,1.40,-.049,.043,1.75,.025,paint)
    for py in (.88,1.94):
        box(.46,py,-.059,.78,.065,.024,"6d6451")
    box(.79,1.29,-.085,.085,.056,.07,"b1a184")
    set_piece(name,previous,math.degrees(previous_angle))
    return front


def fence_panel(x,z,length,paint,rotation):
    old_origin, old_angle = origin,angle
    set_piece(group, (x,0,z), rotation)
    for i in range(max(1,round(length/.29))):
        dx=-length/2+(i+.5)*length/max(1,round(length/.29))
        h=rng.uniform(.93,1.21)
        box(dx,.10+h/2,0,.205,h,.125,rng.choice(paint),rng.uniform(-.028,.028))
    for y in (.34,.84):
        box(0,y,.105,length,.10,.092,paint[0])
    solid(0,.73,0,length,1.46,.24,vault=True)
    set_piece(group,old_origin,math.degrees(old_angle))


def gate_mesh(index, paint):
    set_piece("Gate "+str(index))
    for i in range(7):
        x=.13+i*.25
        box(x,.63,0,.207,1.06+i*.013,.105,paint[i%len(paint)])
    for y in (.37,.87):
        box(.88,y,.08,1.71,.11,.095,paint[0])
    box(.88,.61,.08,1.5,.075,.10,paint[1],.31)
    box(1.58,.80,-.103,.15,.067,.085,"554c3e")


def apple(x,z,scale):
    cylinder(x,scale*.95,z,.16*scale,scale*1.9,"766449",r_top=.095*scale,lean=(.16,0))
    for dx,dy,dz,s in ((-.89,2.42,-.24,1.32),(.67,2.63,-.30,1.42),(.04,3.18,.26,1.18),(.11,2.28,.91,1.21)):
        boulder(x+dx*scale,dy*scale,z+dz*scale,2.15*s*scale,1.61*s*scale,2*s*scale,
                rng.choice(("638048","708948","829753","6d894b","8f9f56")))
    for a in range(14):
        theta=rng.uniform(0,math.tau)
        radius=rng.uniform(1.00,1.95)*scale
        boulder(x+math.cos(theta)*radius,rng.uniform(1.97,2.57)*scale,z+math.sin(theta)*radius,
                .14,.15,.14,rng.choice(("c57749","d0964d","a84f37")),5)
    solid(x,.61,z,.40*scale,1.22,.40*scale)


def flower(x,z,paint,scale=1):
    height=rng.uniform(.21,.44)*scale
    cylinder(x,height*.48,z,.015,height,"677744",4)
    boulder(x,height,z,.12*scale,.078*scale,.12*scale,paint,5)
    if paint == "f5edcd":
        boulder(x,height+.031,z,.054*scale,.035*scale,.054*scale,"d8a746",4)


def tuft(x,z,size,paint):
    for i in range(3):
        x0=x+rng.uniform(-.16,.16)*size
        z0=z+rng.uniform(-.15,.15)*size
        y=rng.uniform(.18,.48)*size
        dx=rng.uniform(-.17,.18)*size
        dz=rng.uniform(-.12,.14)*size
        a,b,c=(x0-.075*size,0,z0),(x0+dx,y,z0+dz),(x0+.075*size,0,z0+.03)
        triangle(a,b,c,paint)
        triangle(c,b,a,paint)


def vegetable_garden(index, x, z):
    vegetable_patches.append({"yard":index,"x":x,"z":z})
    for row,(offset,kind) in enumerate(((-1.48,"cabbage"),(0,"tomato"),(1.48,"carrot"))):
        rz=z+offset
        box(x,.09,rz,2.85,.18,1.01,"796045")
        box(x,.181,rz,2.72,.026,.89,"5d4730")
        for side in (-1,1):
            box(x,.148,rz+side*.50,2.92,.14,.085,"8d7556")
            box(x+side*1.43,.148,rz,.085,.14,1.03,"907858")
        for i in range(7):
            px=x+(i-3)*.366
            if kind=="tomato":
                cylinder(px,.65,rz,.022,.94,"927956",5,lean=(.11,.015))
                for y,dz in ((.39,-.12),(.56,.09),(.72,-.07)):
                    boulder(px,y,rz+dz,.32,.24,.30,"68834a",6)
                    if (i+row)%2:
                        boulder(px-.10,y-.08,rz+dz+.11,.090,.087,.088,"ba6345",5)
            elif kind=="cabbage":
                for dz in (-.21,.21):
                    boulder(px,.295,rz+dz,.32,.23,.30,("829753","718c55","97a55a")[(i+index)%3],6)
            else:
                for dz in (-.22,.22):
                    boulder(px,.226,rz+dz,.088,.075,.08,"bd8648",5)
                    tuft(px,rz+dz,.74,"78914d")
    cylinder(x+1.9,.36,z+1.95,.31,.72,"647878",9)
    cylinder(x+1.9,.724,z+1.95,.29,.030,"7d938b",9)


def chore_tools():
    set_piece("Watering can")
    cylinder(0,-.16,.04,.105,.15,"748c82",9)
    cylinder(0,-.087,.05,.079,.028,"879c8c",8)
    box(0,-.057,.035,.040,.116,.032,"72877d")
    box(0,-.010,.088,.047,.030,.153,"72877d")
    cylinder(.016,-.123,.185,.023,.19,"8c9f8f",6,lean=(.035,.11))
    boulder(.037,-.036,.29,.071,.070,.075,"8c9f8f",7)
    set_piece("Broom")
    cylinder(0,-.08,0,.019,1.15,"a18765",6)
    boulder(0,-.65,0,.27,.22,.14,"b4a271",6)
    box(0,-.59,0,.17,.034,.119,"847455")


def wheel(x,z,paint="33362e"):
    # Axle on X, using paired circular faces and a dark tire.
    sides=12
    for w,r,tone in ((.24,.405,paint),(.256,.238,"9a9882"),(.268,.10,"5d655a")):
        for side in (-1,1):
            xx=x+side*w/2
            points=[(xx,.43+r*math.cos(i*math.tau/sides),z+r*math.sin(i*math.tau/sides)) for i in range(sides)]
            for i in range(1,sides-1):
                face=(points[0],points[i],points[i+1])
                triangle(*(face if side>0 else face[::-1]),tone)
            if w == .24 and side == 1:
                for i in range(sides):
                    a,b=points[i],points[(i+1)%sides]
                    quad(a,(x-w/2,a[1],a[2]),(x-w/2,b[1],b[2]),b,tone)


def lamp(x,y,z,r,paint,rear=False):
    vs=[(x+r*math.cos(math.tau*i/18),y+r*math.sin(math.tau*i/18),z) for i in range(18)]
    for i,a in enumerate(vs):
        b=vs[(i+1)%len(vs)]
        if not rear:
            a,b=b,a
        triangle((x,y,z),a,b,tint(paint,1.06 if i<9 else .92))


def car_panel(y, z, width, height, tile, rear=False):
    """Map one tile onto the car in its local frame."""
    vertices = [(-width/2,y-height/2,z),(-width/2,y+height/2,z),
                (width/2,y+height/2,z),(width/2,y-height/2,z)]
    if rear:
        vertices.reverse()
    u0, u1 = 1.5/SIZE, 1-1.5/SIZE
    v0, v1 = (tile*STRIP+.5)/SIZE, ((tile+1)*STRIP-.5)/SIZE
    uv = [(u0,v0),(u0,v1),(u1,v1),(u1,v0)]
    panel = meshes.setdefault("Auto panels", bytearray())
    for i in (0,1,2,0,2,3):
        point = [round(value*100) for value in transform(vertices[i])]
        panel.extend(struct.pack("<hhhBBBHH", *point, 255,255,255, *(round(q*65535) for q in uv[i])))


def zaz_rod(a, b, radius, paint, sides=5):
    direction = tuple(q-p for p,q in zip(a,b))
    dx,dy,dz=direction
    length=math.sqrt(dx*dx+dy*dy+dz*dz)
    if length < .0001:
        return
    dx,dy,dz=(v/length for v in direction)
    wide=math.hypot(dx,dz)
    u=(-dz/wide,0,dx/wide) if wide>.001 else (1,0,0)
    v=(dy*u[2]-dz*u[1],dz*u[0]-dx*u[2],dx*u[1]-dy*u[0])
    rims=[]
    for point in (a,b):
        rims.append([tuple(point[k]+radius*(u[k]*math.cos(i*math.tau/sides)-v[k]*math.sin(i*math.tau/sides))
                           for k in range(3)) for i in range(sides)])
    prism(rims,paint,0)


def zaz_wheel(side, z, y=.285):
    x=side*.61
    sections=((-0.096,.216),(-.104,.247),(-.079,.285),(.067,.285),(.102,.261),(.111,.213),
              (.112,.186),(.096,.168),(.105,.137),(.122,.081),(.133,.034))
    tones=("262825","30342e","272b25","343732","2b2d28","8a8c7d","c5c0ab","77776d",
           "a6a79a","c3c0ad")
    def rim(offset,radius):
        pts=[(x+side*offset,y+radius*math.cos(i*math.tau/24),z+radius*math.sin(i*math.tau/24))
             for i in range(24)]
        return pts if side<0 else pts[::-1]
    rings=[rim(o,r) for o,r in sections]
    for i,(a,b) in enumerate(zip(rings,rings[1:])):
        for j in range(24):
            k=(j+1)%24
            quad(a[j],b[j],b[k],a[k],tint(tones[i],.97+.027*math.sin(j*math.tau/24)))
    outer=rings[-1]
    for i in range(24):
        triangle((x+side*.133,y,z),outer[(i+1)%24],outer[i],"b3b0a4")


def zaz_glass(points, paint):
    current=group
    set_piece("ZAZ glass",origin,math.degrees(angle))
    quad(*points,paint)
    set_piece(current,origin,math.degrees(angle))


def zaporozhets():
    set_piece("Car ZAZ",(2.86,0,10.05),-5)
    paint, shoulder, low = "e0d4a5","f0e6bc","c6b78e"
    rubber, chrome = "343831","b7bbaf"
    front,rear=-1.84,1.83
    wheel_centers=(-1.065,1.085)
    rails=((-1.84,.624,.755,.365),(-1.796,.686,.787,.337),(-1.68,.723,.804,.306),
           (-1.46,.737,.813,.280),(-.85,.743,.827,.245),(-.52,.735,.831,.246),
           (.54,.733,.835,.251),(.91,.741,.812,.269),(1.42,.741,.808,.302),
           (1.71,.711,.802,.337),(1.80,.663,.782,.368),(1.83,.62,.754,.394))

    def body_at(z):
        for (a,*start),(b,*end) in zip(rails,rails[1:]):
            if z <= b:
                t=max(0,(z-a)/(b-a))
                width, belt, sill=(u+(v-u)*t for u,v in zip(start,end))
                return width,belt,sill
        return rails[-1][1:]

    # Each slice under the belt follows the actual wheel opening.
    points={row[0] for row in rails} | {-.63,.95}
    for center in wheel_centers:
        for i in range(11):
            points.add(center-.319*math.cos(i*math.pi/10))
        points.update((center-.326,center+.326))
    zs=sorted(points)
    for side in (-1,1):
        rows=[]
        for z in zs:
            width,belt,sill=body_at(z)
            wheel_gap=min(abs(z-center) for center in wheel_centers)
            if wheel_gap<.32:
                sill=max(sill,.287+math.sqrt(.320**2-wheel_gap**2))
            rows.append(((side*(width-.048),sill,z),(side*(width+.004),sill+(belt-sill)*.30,z),
                         (side*width,belt-.057,z),(side*(width-.019),belt,z)))
        for a,b in zip(rows,rows[1:]):
            for i,tone in enumerate((low,paint,shoulder)):
                face=(a[i],a[i+1],b[i+1],b[i])
                quad(*(face if side>0 else face[::-1]),tone)
        # Chrome strip follows the shoulder, including the wrap around the nose.
        for z0,z1 in zip(zs,zs[1:]):
            w0,y0,_=body_at(z0)
            w1,y1,_=body_at(z1)
            p=((side*(w0+.002),y0-.059,z0),(side*(w0+.002),y0-.043,z0),
               (side*(w1+.002),y1-.043,z1),(side*(w1+.002),y1-.059,z1))
            quad(*(p if side>0 else p[::-1]),chrome)
        for center in wheel_centers:
            for i in range(10):
                a,b=i*math.pi/10,(i+1)*math.pi/10
                z0,z1=center-.321*math.cos(a),center-.321*math.cos(b)
                y0,y1=.285+.320*math.sin(a),.285+.320*math.sin(b)
                x=side*.704
                quad((x,y0,z0),(x,y1,z1),(side*.504,y1,z1),(side*.504,y0,z0),"514d42")
            zaz_wheel(side,center)

    for z0,z1 in zip(zs,zs[1:]):
        if z0>=-.63 and z1<=.95:
            continue
        w0,y0,_=body_at(z0)
        w1,y1,_=body_at(z1)
        for left,right in zip((-1,-.60,0,.60),(-.60,0,.60,1)):
            a=(left*(w0-.019),y0+.047*(1-left*left),z0)
            b=(right*(w0-.019),y0+.047*(1-right*right),z0)
            c=(right*(w1-.019),y1+.047*(1-right*right),z1)
            d=(left*(w1-.019),y1+.047*(1-left*left),z1)
            quad(a,d,c,b,"e8ddb0" if left==0 or right==0 else paint)
    for z in (front,rear):
        w,belt,base=body_at(z)
        bottom=w-.048
        p=((-bottom,base,z),(-w+.019,belt,z),(w-.019,belt,z),(bottom,base,z))
        quad(*(p if z<0 else p[::-1]),paint)
    for side in (-1,1):
        inset=((side*.406,.790,-1.838),(side*.413,.819,-1.65),(side*.463,.86,-.68))
        for a,b in zip(inset,inset[1:]):
            zaz_rod(a,b,.009,"928768",4)
    box(0,.789,-1.847,1.207,.017,.024,chrome)
    box(0,.763,-1.852,.084,.028,.019,"504a3d")
    box(0,.766,-1.863,.036,.017,.010,"c3c3b0")

    # A-pillar, long door glazing, B-pillar, short quarter window and rear screen.
    lower_fore=(-.63,.825,.607)
    upper_fore=(-.285,1.333,.489)
    lower_a=(-.54,.830,.636)
    lower_b=(.495,.836,.670)
    lower_c=(.951,.812,.629)
    upper_a=(-.255,1.330,.500)
    upper_b=(.452,1.367,.536)
    upper_c=(.718,1.332,.504)
    for side in (-1,1):
        def p(q,dx=0):
            z,y,x=q
            return (side*(x+dx),y,z)

        for lower0,upper0,upper1,lower1 in ((lower_a,upper_a,upper_b,lower_b),
                                          (lower_b,upper_b,upper_c,lower_c)):
            frame=(p(lower0),p(upper0),p(upper1),p(lower1))
            panel=frame if side>0 else frame[::-1]
            zaz_glass(panel,"9cb9ad")
            for a,b in zip(frame,frame[1:]+frame[:1]):
                zaz_rod(a,b,.024,rubber)
            zaz_rod(p(upper0,.016),p(upper1,.016),.025,paint)
        for bottom,top in ((lower_fore,upper_fore),(lower_a,upper_a),(lower_b,upper_b),(lower_c,upper_c)):
            zaz_rod(p(bottom,.016),p(top,.016),.028,paint)
        zaz_rod(p(lower_a,.015),p(lower_c,.010),.023,paint)
        # One seam around the long door, plus a handle, side marker and engine vents.
        door=((side*.743,.807,-.515),(side*.744,.504,-.485),(side*.702,.290,-.412),
              (side*.703,.282,.36),(side*.740,.410,.51),(side*.746,.829,.54))
        for a,b in zip(door,door[1:]):
            zaz_rod(a,b,.009,"938769",4)
        box(side*.748,.781,.344,.016,.041,.161,"b1b2a5")
        box(side*.763,.786,.337,.034,.025,.115,chrome)
        box(side*.721,.661,-1.55,.026,.082,.083,chrome)
        box(side*.737,.659,-1.55,.016,.055,.061,"a66733")
        for j in range(6):
            box(side*.737,.713,1.12+j*.055,.014,.069,.019,"938666",-.21)
        box(side*.661,.269,-.718,.029,.262,.154,"303731")
        box(side*.652,.269,1.42,.035,.272,.141,"303731")
    x0,x1=.607,.489
    a,b,c,d=(-x0,.827,-.633),(-x1,1.332,-.286),(x1,1.332,-.286),(x0,.827,-.633)
    zaz_glass((a,b,c,d),"a9c8bb")
    for p,q in ((a,b),(b,c),(c,d),(d,a)):
        zaz_rod(p,q,.022,rubber)
    a,b,c,d=(-.629,.812,.953),(-.504,1.332,.718),(.504,1.332,.718),(.629,.812,.953)
    zaz_glass((d,c,b,a),"8fa8a1")
    for p,q in ((a,b),(b,c),(c,d),(d,a)):
        zaz_rod(p,q,.020,rubber)
    # Slightly domed roof with rolled edges.
    rings=[(1.337,.509,-.292,.724),(1.377,.495,-.257,.691),(1.395,.356,-.176,.590)]
    panels=[]
    for y,w,z0,z1 in rings:
        panels.append([(-w,y,z0+.08),(-w*.80,y,z0),(w*.80,y,z0),(w,y,z0+.08),
                       (w,y,z1-.08),(w*.80,y,z1),(-w*.80,y,z1),(-w,y,z1-.08)])
    for i,(a,b) in enumerate(zip(panels,panels[1:])):
        for j in range(8):
            k=(j+1)%8
            quad(a[j],b[j],b[k],a[k],paint if i==0 else shoulder)
    for i in range(1,7):
        triangle(panels[-1][0],panels[-1][i+1],panels[-1][i],"f2e8c3")
    box(0,.335,.13,1.21,.18,2.15,"44493d")
    box(0,.763,-.47,1.15,.106,.211,"534b40")
    for x in (-.31,.31):
        box(x,.502,.110,.45,.149,.49,"66584a")
        box(x,.739,.302,.45,.469,.132,"76604e",x*.13)
    box(0,.537,.676,1.09,.161,.412,"756052")
    box(0,.723,.858,1.10,.309,.156,"6b5546")
    # Steering wheel, mirror and wipers remain visible through the panes.
    steering=[(-.308+.123*math.cos(i*math.tau/14),.883+.124*math.sin(i*math.tau/14),
               -.292+.051*math.sin(i*math.tau/14)) for i in range(14)]
    for a,b in zip(steering,steering[1:]+steering[:1]):
        zaz_rod(a,b,.015,"393830",4)
    zaz_rod((-.308,.882,-.286),(-.308,.745,-.501),.020,rubber)
    for i in (0,5,9):
        zaz_rod((-.308,.882,-.286),steering[i],.011,rubber,4)
    box(0,1.261,-.210,.182,.061,.034,"353932")
    for x in (-.31,.22):
        zaz_rod((x+.17,.841,-.626),(x-.09,.886,-.597),.010,rubber,4)
    zaz_rod((-.654,.869,-.454),(-.745,.959,-.459),.013,chrome)
    box(-.754,.966,-.465,.104,.064,.043,"42473f")

    for s in (-1,1):
        x=s*.529
        # Recessed chrome bowls and ribbed clear lenses.
        lamp(x,.650,-1.861,.155,rubber)
        lamp(x,.650,-1.875,.132,"a1a395")
        lamp(x,.650,-1.882,.113,"c5c8ad")
        for j in range(-3,4):
            h=math.sqrt(.105**2-(j*.027)**2)*1.72
            box(x+j*.027,.653,-1.889,.009,h,.010,"a8ab99")
        box(s*.331,.607,-1.853,.146,.059,.045,"4d453a")
        box(s*.331,.607,-1.882,.114,.048,.026,"b87432")
        box(s*.555,.548,1.850,.247,.111,.076,"393d35")
        box(s*.555,.548,1.893,.207,.084,.012,"bc5744")
        box(s*.626,.550,1.902,.072,.072,.017,"bf813e")
    for z in (-1.913,1.889):
        box(0,.432,z,1.373,.079,.097,rubber)
        box(0,.454,z+math.copysign(.051,z),1.265,.035,.018,chrome)
        for s in (-1,1):
            box(s*.689,.440,z-math.copysign(.042,z),.124,.081,.174,rubber)
        box(0,.450,z+math.copysign(.057,z),.408,.098,.030,"b5b5a2")
        car_panel(.450,z+math.copysign(.077,z),.392,.081,PLATE["ZAZ"],rear=z>0)
    car_panel(.605,-1.879,.518,.041,GRILLE["ZAZ"])
    for j in range(9):
        box(0,.854,.965+j*.065,.733,.017,.028,"938666")
    solid(0,.70,0,1.55,1.40,3.87)
    set_piece("Street")


def car(position, rotation, kopeyka):
    prev=group,origin,angle
    model = "2101" if kopeyka else "2106"
    set_piece("Car " + model, position, rotation)
    paint = "768b72" if kopeyka else "a14737"
    w,d = (1.62,4.06) if kopeyka else (1.71,4.03)
    box(0,.72,0,w,.58,d,paint)
    box(0,.99,0,w-.065,.105,d-.12,paint)
    box(0,.48,0,w-.11,.11,d-.16,"4d5245")
    dark="435b58"
    z0,z1 = (-.84,1.13) if kopeyka else (-.77,1.12)
    roof_y = 1.48 if kopeyka else 1.52
    inset = .65 if kopeyka else .69
    xx=w/2-.12
    a,b,c,e=(-xx,1.03,z0),(xx,1.03,z0),(inset,roof_y,z0+.39),(-inset,roof_y,z0+.39)
    h,i,j,k=(-xx,1.03,z1),(xx,1.03,z1),(inset,roof_y,z1-.20),(-inset,roof_y,z1-.20)
    for face in ((a,e,c,b),(h,i,j,k),(a,h,k,e),(b,c,j,i)):
        quad(*face,dark)
    quad(e,k,j,c,paint)
    box(0,.78,-d/2-.014,w*.92,.267,.074,"bdb8a3" if kopeyka else "50514a")
    car_panel(.783, -d/2-.068, 1.29 if kopeyka else .659, .245 if kopeyka else .219, GRILLE[model])
    for side in (-1,1):
        box(side*(xx-.055),1.23,(z0+z1)/2,.063,.51,.093,paint)
        box(side*w/2,.57,0,.036,.063,d*.88,"645c4b")
        for z in (-d*.31,d*.31):
            wheel(side*(w/2-.022),z)
        lamps = ((.647,.145),) if kopeyka else ((.67,.123),(.435,.109))
        for x,r in lamps:
            lamp(side*x,.803,-d/2-.079,r+.017,"bcb7a7" if kopeyka else "77736b")
            lamp(side*x,.803,-d/2-.098,r,"e3d8b9")
            for slit in (-.48,-.16,.16,.48):
                box(side*x+slit*r,.805,-d/2-.115,.011,r*1.35,.012,"c6bca3")
        for dz in (-.79,.03,1.08):
            box(side*(w/2+.006),.741,dz,.019,.422,.022,("546a55" if kopeyka else "74382e"))
        for dz in (-.21,.84):
            box(side*(w/2+.016),.92,dz,.030,.036,.146,"b7a995")
        box(side*(w/2+.005),.72,0,.025,.022 if kopeyka else .037,d*.90,"b6a48b")
        box(side*.63,.614,-d/2-.082,.194 if kopeyka else .243,.064,.053,"b87433")
        box(side*.63,.803,d/2+.066,.105 if kopeyka else .141,.075,.038,"cd9953")
        box(side*.54,.553,-d/2-.18,.113,.11,.09,"8e897c" if kopeyka else "534740")
        box(side*.77,1.12,-.63,.118,.078,.103,"80786b")
        box(side*.821,1.127,-.613,.025,.055,.079,"acb5a6")
        box(side*.65,.719,d/2+.028,.177 if kopeyka else .254,.143,.101,"a35439")
    for z in (-d/2-.12,d/2+.12):
        box(0,.54,z,w+.10,.12,.19,"b6b3a1" if kopeyka else "a8a897")
        box(0,.651,z,.45,.109,.064,"a39a85")
        car_panel(.651, z + math.copysign(.04,z), .45, .109, PLATE[model], rear=z>0)
    solid(0,.65,0,w+.16,1.33,d+.35)
    set_piece(prev[0],prev[1],math.degrees(prev[2]))


def yard_path(side, destination, z, width=.69):
    center, road_width = lane_cross_section(z)
    start = center + side*(road_width+.12)
    rows = []
    n = math.ceil(abs(start-destination)/.56)
    for i in range(n+1):
        t = i/n if side > 0 else 1-i/n
        x = start+(destination-start)*t
        radius = min(width+rng.uniform(-.035,.035), width*(.50+t*2))
        row = []
        for fraction, paint in ((1,"87974d"),(.70,"aa9b69"),(0,"ad9e73"),(-.70,"aa9b69"),(-1,"87974d")):
            edge_z = z+radius*fraction
            edge_center, edge_width = lane_cross_section(edge_z)
            edge = edge_center + side*(edge_width+.12)
            edge_x = max(x,edge) if side > 0 else min(x,edge)
            row.append(((edge_x, ROAD_HEIGHT, edge_z), tint(paint,rng.uniform(.97,1.03))))
        rows.append(row)
    strip_mesh(rows)


def stop(position, dwell=0, **options):
    return {"point":[round(v,3) for v in position],"dwell":dwell,**options}


def adult_route(index, side, fence_x, front, garden_z):
    task = "water" if index in (0,6) else "sweep"
    spot_x=fence_x+side*1.92
    steps = [stop(transform((0,.49,front+.40)),dwell=.60,hidden=True,door=True),
             stop(transform((0,.46,front-.43)),door=True),
             stop(transform((0,.44,front-1.14)),door=True),
             stop(transform((0,.30,front-1.38))),
             stop(transform((0,.15,front-1.65))),
             stop(transform((0,.013,front-1.93)))]
    inside=dict(steps[0],door=False,dwell={0:7,1:10,4:13,6:15}[index])
    approach=stop((spot_x,.012,steps[-1]["point"][2]))
    if task=="water":
        job=stop((spot_x,.012,garden_z),11.0,job=task,yaw=side*90)
    else:
        job=stop((spot_x,.012,steps[-1]["point"][2]-.85),11.5,job=task,yaw=-side*90)
    return_steps=[dict(p, dwell=0) for p in reversed(steps[1:])]
    residents.append({"name":"Взрослый "+str(index+1),"mesh":ADULTS[index%2],
                      "door":index,"scale":[1.16,1.175,1.12],"speed":.97,
                      "tool":"Watering can" if task=="water" else "Broom",
                      "offset":{0:6,1:16,4:4,6:10}[index],
                      "route":[inside,*steps,approach,job,approach,*return_steps,steps[0]]})


def children_routes():
    specs = [
        ("Миша",7,60,0,.79,1.18,1.1,[
            (-1.6,3.6,1.5,0),(-1.8,8,1.5,0),(-.85,13.4,.2,1),
            (-1.5,17.7,1.2,1),(-2.5,11.8,.6,0),(-2.25,4,1.8,0)]),
        ("Лена",10,100,1,.98,1.2,.5,[
            (1.8,7.5,.8,0),(1.62,12.1,1.6,0),(1.80,17.2,.7,0),
            (1.58,22.4,.4,1),(1.95,27.6,1.0,1),(2.1,22.3,.6,0),(1.4,12.2,1.2,0)]),
        ("Саша",12,100,0,1.09,1.39,2.2,[
            (-1.3,24.9,.6,0),(-1.65,29.45,.4,0),(-14,29.54,.4,1),
            (-23.7,29.54,1.5,1),(-12.7,29.52,.4,1),(-1.55,29.4,1.2,0)])]
    for name,age,max_health,variant,scale,speed,offset,course in specs:
        route=[stop((x,.04,z),dwell,run=bool(run),**({"job":"talk","yaw":75} if dwell>1 else {}))
               for x,z,dwell,run in course]
        residents.append({"name":name,"age":age,"maxHealth":max_health,"mesh":CHILDREN[variant],"door":-1,"speed":speed,
                          "scale":[scale]*3,"offset":offset,"route":route})


def yard(index,cx,cz):
    side=1 if cx>0 else -1
    set_piece("Yard "+str(index))
    fence_x=6.15 if side>0 and index>=4 else side*4.20
    edge_x=side*23
    front,back=cz-7.45,cz+7.45
    # Gate local +X changes into +Z on the left and -Z on the right.
    gate_z=cz+side*.65
    pivot_z=gate_z+side*.90
    gate_angle=side*90
    gates.append({"x":fence_x,"z":pivot_z,"yaw":gate_angle,"width":1.80,"mesh":"Gate "+str(index)})
    paints=(("8e7859","a08461","967a58"),
            ("738b73","809279","909c7b"),
            ("786a52","8b7b5d","746b55"),
            ("a08b66","ae9872","96865e"),
            ("7f9290","819d95","a0a995"),
            ("a07c64","b89378","96745e"),
            ("878359","9c946a","969068"))[index]
    for lo,hi in ((front,gate_z-.90),(gate_z+.90,back)):
        fence_panel(fence_x,(lo+hi)/2,hi-lo,paints,90)
    for z in (front,back):
        fence_panel((fence_x+edge_x)/2,z,abs(edge_x-fence_x),paints,0)
    fence_panel(edge_x,cz,back-front,paints,90)
    for z in (front,gate_z-.91,gate_z+.91,back):
        box(fence_x,.66,z,.172,1.32,.18,paints[0])
        solid(fence_x,.66,z,.18,1.32,.18)
    yard_path(side,cx-side*4.5,gate_z)
    garden_x=fence_x+side*3.75
    garden_z=cz+4.30
    for x,z,s in ((cx+side*4.0,cz-4.6,.86),(cx+side*3.6,cz+4.5,.92)):
        apple(x,z,s+rng.uniform(-.10,.10))
    for _ in range(50):
        x=rng.uniform(5,22)*side
        z=rng.uniform(front+.45,back-.45)
        if (abs(z-gate_z)<1 or (abs(x-cx)<4.4 and abs(z-cz)<4.5) or
                (abs(x-garden_x)<2.2 and abs(z-garden_z)<2.4)):
            continue
        tuft(x,z,rng.uniform(.55,1.25),rng.choice(("718447","a3a757","86934b")))
        if rng.random() < .39:
            flower(x,z,rng.choice(("f5edcd","e2ad4d","a38ba6")))
    for x in (side*6.5,side*7.3):
        for _ in range(8):
            flower(x+rng.uniform(-.36,.36),cz-4+rng.uniform(-.75,.75),"f5edcd",1.15)
    vegetable_garden(index,garden_x,garden_z)
    for px,pz in ((side*8.6,cz-4.1),(side*9.3,cz-4.3)):
        boulder(px,.11,pz,.4,.23,.35,"9c9982",5)
    set_piece("House "+str(index),(cx,0,cz+side*.42),side*90)
    front_wall = house(index)
    if index in (0,1,4,6):
        adult_route(index,side,fence_x,front_wall,garden_z)
    set_piece("Yard "+str(index))
    if index in (0,3):
        car((side*8.0,0,cz-(4.27 if index==0 else 4.53)),(8 if index==0 else -9),index==3)
    if index==1:
        # Washing line behind the porch.
        x=side*7
        for z in (cz-.1,cz+3.55):
            box(x,1.05,z,.092,2.1,.092,"918367")
        box(x,1.94,cz+1.73,.022,.022,3.65,"ccbf9e")
        for z,h,paint in ((cz+.62,.55,"d6ba92"),(cz+1.58,.70,"e5dbc0"),(cz+2.60,.47,"9baf9c")):
            box(x,1.94-h/2,z,.038,h,.71,paint)
    gate_mesh(index,paints)


def birch(x,z,scale):
    lean=(scale*.25,rng.uniform(-.37,.37))
    cylinder(x,scale*2.52,z,.19*scale,scale*5.04,"c8c5ad",7,.085*scale,lean)
    for i in range(7):
        y=(.42+i*.57)*scale
        cylinder(x+lean[0]*y/(scale*5.04),y,z+lean[1]*y/(scale*5.04),
                 (.193-i*.012)*scale,rng.uniform(.07,.15),"7d7b63" if i%3 else "555a48",7)
    for dx,dz,y,s in ((-.93,.1,4.5,1),(.79,.35,5.04,1),(.23,-.53,5.80,.89)):
        boulder(x+dx*scale,y*scale,z+dz*scale,3.3*s*scale,2.6*s*scale,2.9*s*scale,
                rng.choice(("80934d","879956","748d51","9ca65a")))


def pine(x,z,scale):
    cylinder(x,scale*2.41,z,.174*scale,scale*4.82,"806b52",6,.095*scale)
    for y, w in ((2.8,2.65),(3.73,2.24),(4.68,1.79),(5.54,1.35),(6.33,1.05)):
        lower=ring(x,y*scale,z,w*scale,w*.89*scale,7,.19)
        upper=ring(x+.12*scale,(y+2.30)*scale,z,w*.066*scale,w*.058*scale,7,.19)
        prism([lower,upper],rng.choice(("536d51","5e7550","627c54","59714f","6c8257")),.14)


def on_plot(x,z,margin=0):
    return abs(x)<23+margin and any(x*cx>0 and abs(z-cz)<7.45+margin for cx,cz in YARDS) and abs(x)>3.9-margin


def tree_fits(x,z):
    if on_plot(x,z,1.2):
        return False
    if -19 < z < -8:
        return False
    if abs(x)<24 and -8 <= z < 34:
        return False
    if 24 <= abs(x) < 41 and -8 <= z < 30:
        return False  # orchard and meadow
    center, width = lane_cross_section(z)
    if 30 < z < 91 and abs(x-center) < width+2.25:
        return False
    if 34 < z < 50 and abs(x+11) < 6:
        return False  # meadow beyond the back gardens
    return True


def forest():
    for index in range(3):
        set_piece("Pine " + str(index))
        pine(0,0,1)
        set_piece("Birch " + str(index))
        birch(0,0,1)
    for x in range(-83,84,5):
        for z in range(-44,116,5):
            px,pz=x+rng.uniform(.14,4.30),z+rng.uniform(.14,4.30)
            if not tree_fits(px,pz):
                continue
            name = ("Birch " if rng.random() < .39 else "Pine ") + str(rng.randrange(3))
            size = round(rng.uniform(.66,1.57),2)
            zone = ((x+84)//20)*10 + (z+44)//20
            trees.append({"mesh":name, "zone":zone,
                          "placement":[round(px,2),round(pz,2),size,rng.randrange(360)]})
            if BOUNDS[0] < px < BOUNDS[1] and BOUNDS[2] < pz < BOUNDS[3]:
                solid(px,1.2,pz,.38*size,2.4,.38*size)
    set_piece("Forest edge")
    for x,z,s in ((-3.8,35.6,1.20),(4.3,35.1,1.02),(-7.8,34.8,1.10),(8.7,34.9,1.03)):
        if not on_plot(x,z,1):
            birch(x,z,s)
            solid(x,1.2,z,.49,2.4,.49)
    for _ in range(115):
        x,z=rng.uniform(-25,25),rng.uniform(30.4,39.5)
        if on_plot(x,z,.6) or abs(x)<2.25:
            continue
        if rng.random()<.34:
            boulder(x,.36,z,rng.uniform(.70,1.5),.77,.72,"78853f",6)
        else:
            tuft(x,z,1.14,rng.choice(("6c8246","8d9b54","7c9150")))


def beyond_houses():
    set_piece("Orchard")
    for x in (-36,-30,29,35):
        for z in (0,6,13,20,26):
            apple(x+rng.uniform(-.75,.75), z+rng.uniform(-.78,.78), rng.uniform(.66,1.0))
    for side in (-1,1):
        yard_path(side,side*39,-7.35,.77)
    set_piece("Back meadow")
    yard_path(-1,-27,29.55,.78)
    yard_path(1,29,29.55,.85)
    for _ in range(106):
        x,z = rng.uniform(-38,-25),rng.uniform(34,46)
        tuft(x,z,rng.uniform(.68,1.48),rng.choice(("87994e","9ca457","778b48")))
        if rng.random()<.46:
            flower(x,z,rng.choice(("f5edcd","d6a446","ab94b0")))
    for x,z,scale in ((-29,43,1.6),(-28,41,1.2),(-30,41,.85)):
        boulder(x,scale*.28,z,scale,scale*.58,scale*.88,"969486",7)
        solid(x,scale*.25,z,scale*.8,scale*.50,scale*.7)
    for strip in range(3):
        set_piece("Forest trail "+str(strip))
        for _ in range(85):
            z = rng.uniform(39+strip*16,55+strip*16)
            center,width = lane_cross_section(z)
            x = center+rng.choice((-1,1))*(width+rng.uniform(.15,1.9))
            if on_plot(x,z,.15):
                continue
            if rng.random()<.23:
                boulder(x,.19,z,rng.uniform(.25,.48),.44,.48,"818e4a",6)
            elif rng.random()<.26:
                flower(x,z,rng.choice(("f5edcd","9d82a1")))
            else:
                tuft(x,z,rng.uniform(.95,1.65),rng.choice(("687d45","87994e","9ca457")))


def scenery():
    set_piece("Verge")
    for side in (-1,1):
        for i in range(155):
            z=rng.uniform(-10.9,35.6)
            x=side*rng.uniform(2.46 if z<25 else 1.78,4.0)
            if any(abs(z-(cz+side*.65))<.95 for cz in (2.4,20.4)):
                continue
            tuft(x,z,rng.uniform(.55,1.28),rng.choice(("687d45","87994e","9ca457","778b48")))
            if i%3 == 0:
                flower(x,z+.10,rng.choice(("f5edcd","f5edcd","d6a446","ab94b0")))
    for x,z in ((-3.9,-7.1),(-3.6,16.3),(3.93,14.24),(3.81,29.4)):
        boulder(x,.23,z,.82,.5,.69,"959180",6)
    # Hand-painted blank signboard and utility poles by the road.
    for x,z in ((-4.4,-9.38),(8.6,-10.17),(-17.7,-10.17)):
        cylinder(x,2.75,z,.11,5.5,"847259",6,r_top=.075,lean=(.06,.02))
        box(x,5.03,z,1.15,.095,.12,"887861")
        for d in (-.42,0,.42):
            cylinder(x+d,5.15,z,.068,.16,"d4cfb7",6)
        solid(x,1.18,z,.27,2.36,.27)
    for z_offset in (-.04,0,.04):
        quad((-17.28,5.17,-10.17+z_offset),(-4.82,5.17,-9.38+z_offset),
             (-4.82,5.19,-9.38+z_offset),(-17.28,5.19,-10.17+z_offset),"716958")
        quad((-3.98,5.17,-9.38+z_offset),(8.18,5.17,-10.17+z_offset),
             (8.18,5.19,-10.17+z_offset),(-3.98,5.19,-9.38+z_offset),"716958")
    for x in (-3.1,-2.15,-.05,.90):
        box(x,.43,86.8,.12,.86,.12,"8a7f5b")
        box(x,.67,86.8,.125,.11,.125,"e0c595")
    box(-1.1,.64,86.8,4.20,.09,.09,"9b885d")
    solid(-1.1,.64,86.8,4.20,1.28,.18)


def actors():
    set_piece("Cat body")
    boulder(0,.29,-.03,.26,.32,.52,"bb8052",7)
    boulder(0,.365,.237,.26,.25,.24,"c28b5b",7)
    boulder(0,.32,.332,.158,.12,.125,"dfc3a0",7)
    boulder(0,.363,.385,.052,.040,.03,"92735c",5)
    for x in (-.083,.083):
        prism([ring(x,.426,.236,.063,.061,3,.21),
               ring(x*1.22,.583,.247,.012,.014,3,.21)],"ac774d")
        boulder(x,.397,.336,.039,.030,.025,"5f6641",5)
        box(x,.402,.35,.012,.022,.012,"3a4333")
    for z in (-.20,-.08,.047):
        boulder(0,.406,z,.185,.065,.052,"9d633f",7)
    set_piece("Cat leg")
    boulder(0,-.091,0,.070,.19,.072,"b97d52",5)
    boulder(0,-.173,.021,.080,.069,.10,"d3ae86",6)
    set_piece("Cat tail")
    cylinder(0,.10,-.10,.034,.24,"aa754b",6,r_top=.028,lean=(0,-.13))
    cylinder(0,.26,-.23,.027,.17,"ba8655",6,r_top=.018,lean=(0,.045))


def stick_locations():
    set_piece("Stick")
    box(0,.034,0,.67,.054,.055,"866346",-.025)
    box(.296,.032,.008,.16,.040,.040,"957453",.055)
    box(-.120,.068,.005,.25,.039,.038,"917253",.32)
    box(.054,.062,-.014,.102,.023,.034,"ac8b5e")
    locations=[(-1.22,-3.25,32),(1.42,8.4,148),(-1.3,24.6,71)]
    for index,z in enumerate((45.1,47.9,49.2,51.4,53.1,55.1,58.2,60.5,62.6,64.9,66.1,68.2,70.8,
                              73.8,75.4,77.1,78.5,80.3,82.5,84.6)):
        center,width=lane_cross_section(z)
        x=center+(-1 if index%2 else 1)*(width+.34+(index%3)*.32)
        locations.append((round(x,2),z,(index*67+22)%180))
    return [{"point":[x,.026,z],"yaw":yaw} for x,z,yaw in locations]


def write():
    sticks = stick_locations()
    child_mesh, rig = child_assets()
    meshes[PLAYER] = child_mesh
    for name in (*CHILDREN,*ADULTS):
        meshes[name] = child_assets(name)[0]
    data=bytearray(b"CDH5")
    data.extend(struct.pack("<H",len(meshes)))
    for name,mesh in meshes.items():
        label=name.encode("ascii")
        data.extend(struct.pack("<B",len(label)))
        data.extend(label)
        vertex_size = 15 if is_skinned(name) else 13 if name == "Auto panels" or name.startswith("House skin ") else 9
        assert len(mesh) % (vertex_size*3) == 0, name
        data.extend(struct.pack("<I",len(mesh)//vertex_size))
        data.extend(mesh)
    (ROOT/"VillageMeshes.bytes").write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
    (ROOT/"AutoPanels.bytes").write_bytes(build_atlas())
    (ROOT/"HouseSurfaces.bytes").write_bytes(build_house_atlas())
    layout={
        "bounds":BOUNDS,
        "spawn":[-.56,0,-7.1],
        "spawnYaw":9.0,
        "gates":gates,
        "sticks":sticks,
        "doors":doors,
        "residents":residents,
        "vegetablePatches":vegetable_patches,
        "rig":rig,
        "trees":trees,
        "solids": [{"box":s,"vault":i in vault_fences} for i,s in enumerate(solids)],
        "catPath":[{"x":x, "z":z} for x,z in ((.95,-1.55),(1.88,1.2),(1.68,4.9),(1.14,10.0),(1.5,15.1),
                   (1.2,20.2),(-.95,15.7),(-1.28,9.9),(-1.37,4.8),(-1.76,-.55),(-.31,-2.4))],
        "catStops":[2.7,.6,1.5,0,2.1,1.2,0,2.2,0,1.1,.7],
        "catAlertRadius":2.7,
        "catFleeSpeed":4.9,
    }
    (ROOT/"VillageLayout.json").write_text(json.dumps(layout, separators=(",", ":"))+"\n")
    print(f"{len(meshes)} meshes, {sum(len(m)//(45 if is_skinned(name) else 39 if name == "Auto panels" or name.startswith("House skin ") else 27) for name,m in meshes.items()):,} triangles, {len(solids)} colliders")


ground()
roads()
for index,(cx,cz) in enumerate(YARDS):
    yard(index,cx,cz)
forest()
beyond_houses()
scenery()
actors()
chore_tools()
children_routes()
zaporozhets()
write()
