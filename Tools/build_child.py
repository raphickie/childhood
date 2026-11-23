"""Build an original child character with a shared skin and locomotion poses."""
import math
import struct

from build_faces import build_head

PLAYER = "Player character"
CHILDREN = ("Resident child berry", "Resident child blue")
ADULTS = ("Resident adult green", "Resident adult plum")
SHIRTS = ("d6a455","e1b964","efce89","dfb25a","dfb15c","dfb15e","d9a955","ddaa5b",
          "efce87","dba955","deb05b","ddac59")


def is_skinned(name):
    return name == PLAYER or name.startswith("Resident ")
HIP_Y = .574
THIGH = .251
SHIN = .242


def child_assets(variant=PLAYER):
    adult = variant in ADULTS
    girl = variant == CHILDREN[1]
    cloth = {
        CHILDREN[0]: ("a25857","b76c6d","e2ab9a"),
        CHILDREN[1]: ("527b92","638fa6","b0d3d5"),
        ADULTS[0]: ("677d63","77916d","98a981"),
        ADULTS[1]: ("795a68","976b7c","bd8d9c"),
    }.get(variant)
    palette_shift = {}
    if cloth:
        palette_shift.update({c:cloth[2 if c in ("efce87","efce89") else i%2] for i,c in enumerate(SHIRTS)})
    if adult:
        palette_shift.update({c:"434b51" for c in ("657f83","79949a","6b8b94","6f8e91",
                                                   "8ca4a4","79979c","799296","75909a")})

    bones, positions, mesh = [], [], bytearray()

    def bone(name, parent, x, y, z):
        bones.append({"name":name, "parent":parent, "offset":[x,y,z]})
        px,py,pz = positions[parent] if parent >= 0 else (0,0,0)
        positions.append((px+x,py+y,pz+z))
        return len(bones)-1

    hips = bone("Hips",-1,0,HIP_Y,0)
    chest = bone("Chest",hips,0,.16,0)
    head = bone("Head",chest,0,.432,.012)
    limbs = []
    for prefix,side in (("Left",-1),("Right",1)):
        arm = bone(prefix+" shoulder",chest,side*.195,.342,.001)
        elbow = bone(prefix+" elbow",arm,0,-.193,0)
        leg = bone(prefix+" thigh",hips,side*.093,0,0)
        knee = bone(prefix+" knee",leg,0,-THIGH,0)
        foot = bone(prefix+" foot",knee,0,-SHIN,0)
        limbs.append((arm,elbow,leg,knee,foot))
    eyes = bone("Eyes",head,0,.143,.120)
    hands = [bone(side + " hand", elbow, 0, -.167, .009)
             for side, (_, elbow, *_) in zip(("Left", "Right"), limbs)]

    def attached(index):
        return (index,index,255)

    def blend(upper,lower,y,center,seam=.07):
        a = min(1,max(0,(y-center+seam)/(2*seam)))
        return (upper,lower,round(255*a))

    def surface(sections, palette, skin, sides=16):
        sides += 4
        if len(sections) >= 6:
            smooth = []
            for i,(a,b) in enumerate(zip(sections,sections[1:])):
                previous=sections[max(0,i-1)]
                after=sections[min(len(sections)-1,i+2)]
                smooth.extend((a,tuple((9*(left+right)-prev-future)/16
                                        for left,right,prev,future in zip(a,b,previous,after))))
            sections=smooth+[sections[-1]]
            palette=[palette[min(i//2,len(palette)-1)] for i in range(len(sections)-1)]
        rings = [[(round((x+rx*math.cos(i*math.tau/sides))*1000),
                   round(y*1000),round((z+rz*math.sin(i*math.tau/sides))*1000))
                  for i in range(sides)] for y,x,z,rx,rz in sections]
        faces = []
        for level,(lo,hi) in enumerate(zip(rings,rings[1:])):
            paint = palette[min(level,len(palette)-1)]
            for i in range(sides):
                j=(i+1)%sides
                faces.extend(((lo[i],hi[i],hi[j],paint),(lo[i],hi[j],lo[j],paint)))
        for i in range(1,sides-1):
            faces.extend(((rings[0][0],rings[0][i],rings[0][i+1],palette[0]),
                          (rings[-1][0],rings[-1][i+1],rings[-1][i],palette[-1])))
        emit(faces, skin)

    def emit(faces, skin):
        normals = {}
        for a,b,c,_ in faces:
            u = [b[i]-a[i] for i in range(3)]
            v = [c[i]-a[i] for i in range(3)]
            n = [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            for p in (a,b,c):
                normal=normals.setdefault(p,[0,0,0])
                for i in range(3):
                    normal[i] += n[i]
        for a,b,c,paint in faces:
            if a==b or b==c or a==c:
                continue
            for p in (a,b,c):
                normal=normals[p]
                length=math.sqrt(sum(c*c for c in normal)) or 1
                packed_normal=[round(c*127/length) for c in normal]
                tone=paint(p) if callable(paint) else palette_shift.get(paint,paint)
                mesh.extend(struct.pack("<hhhBBBbbbBBB",*p,*bytes.fromhex(tone),
                                        *packed_normal,*skin(p[1]/1000)))

    def oval(x,y,z,rx,ry,rz,paint,index,sides=14):
        rings = [(y+ry*math.sin(t), x, z, rx*math.cos(t), rz*math.cos(t))
                 for t in [-1.42,-.92,-.45,0,.45,.92,1.42]]
        surface(rings,[paint],lambda _:attached(index),sides)

    # Denim shorts and a softly rounded striped T-shirt.
    surface([(.548,0,0,.127,.088),(.568,0,.003,.189,.125),(.633,0,0,.196,.129),
             (.704,0,-.006,.169,.112),(.735,0,0,.151,.107)],["657f83","79949a","6b8b94"],
             lambda y:blend(chest,hips,y,.72))
    surface([(.682,0,0,.160,.105),(.724,0,.003,.178,.111),(.805,0,.001,.172,.114),
             (.840,0,.001,.177,.114),(.890,0,.006,.186,.118),(.928,0,.006,.189,.117),
             (.978,0,0,.200,.123),(1.048,0,0,.205,.120),(1.102,0,.004,.163,.101),
             (1.145,0,.014,.084,.074)],["d6a455","e1b964","efce89","dfb25a","efce89",
             "dfb15c","dfb15e","d9a955","ddaa5b"],lambda y:blend(chest,hips,y,.746,.11))
    oval(0,1.123,.018,.065,.086,.063,"d3a37d",head)
    style = {PLAYER:"player", CHILDREN[0]:"boy", CHILDREN[1]:"girl",
             ADULTS[0]:"man", ADULTS[1]:"woman"}[variant]
    build_head(style,head,eyes,oval,lambda faces,index:emit(faces,lambda _:attached(index)))
    if adult:
        if variant == ADULTS[1]:
            surface([(.70,0,.102,.118,.015),(.88,0,.112,.136,.019),
                     (1.015,0,.112,.127,.017)],["bfab8f","cfbb9c"],lambda _:attached(chest))
    elif girl:
        # The dress and braids give Lena a silhouette of her own.
        surface([(.392,0,0,.259,.207),(.412,0,0,.250,.199),(.533,0,.004,.219,.167),
                 (.65,0,.007,.186,.130),(.758,0,.006,.167,.112),(.815,0,.006,.172,.109)],
                ["9ab8bf","6994a5","5f879b","6e98a8","a1c3c6"],lambda y:blend(chest,hips,y,.746,.078))
        surface([(.729,0,.005,.178,.124),(.769,0,.005,.178,.123)],
                ["a2c3c5"],lambda y:blend(chest,hips,y,.746,.078))
    else:
        # The pack follows the torso. Straps stay attached when the shoulders swing.
        surface([(.762,0,-.147,.082,.046),(.793,0,-.161,.135,.064),(.87,0,-.178,.146,.078),
                 (1.001,0,-.159,.135,.068),(1.05,0,-.13,.077,.035)],
                ["547267","597c73","64897d","708e78"],lambda _:attached(chest))
        oval(0,.848,-.241,.108,.067,.023,"879778",chest)
        for side in (-1,1):
            surface([(.779,side*.112,.088,.019,.016),(.90,side*.133,.114,.019,.017),
                     (1.02,side*.133,.107,.021,.017),(1.09,side*.119,.078,.021,.015),
                     (1.119,side*.116,.040,.019,.019),(1.112,side*.116,-.043,.019,.049)],
                    ["668579"],lambda _:attached(chest),10)

    for side,(arm,elbow,leg,knee,foot),hand in zip((-1,1),limbs,hands):
        x,y,z=positions[arm]
        surface([(.711,x,.009,.037,.032),
                 (.753,x,0,.038,.033),(.818,x,-.003,.050,.043),(.878,x,0,.054,.047),
                 (.944,x,0,.058,.054),(.954,x,0,.070,.064),(1.013,x,0,.077,.069),
                 (1.074,x-.009*side,0,.085,.077),(1.134,x-.034*side,0,.031,.040)],
                (["dcaa81","dca981"]+[cloth[0]]*6 if adult else
                 ["dcaa81","dca981","d6a27b","d9a783","efce87","dba955","deb05b","ddac59"]),
                lambda v: blend(arm,elbow,v,positions[elbow][1],.066))
        surface([(.643,x,.012,.027,.025),(.669,x,.015,.040,.033),(.705,x,.010,.041,.033),
                 (.723,x,.010,.036,.031)], ["d4a079","dca880","dcaa81"], lambda _: attached(hand), 14)
        oval(x-side*.027,.687,.032,.018,.031,.017,"e1ad86",hand,8)
        x,_,_=positions[leg]
        surface([(.075,x,-.009,.042,.042),(.115,x,-.008,.047,.044),(.15,x,-.009,.051,.048),
                 (.185,x,-.004,.059,.055),(.252,x,.005,.064,.056),(.315,x,.009,.067,.068),
                 (.378,x,.000,.068,.063),(.398,x,.000,.082,.078),(.431,x,0,.086,.083),
                 (.500,x,-.010,.094,.091),(.562,x,-.008,.093,.104),(.607,x,0,.075,.086)],
                (["434b51"]*11 if adult else ["e1dbbf","e1dbbf","d6a780","dcad86","d6a780",
                 "dcab82","d6a780" if girl else "6f8e91","dcad86" if girl else "8ca4a4",
                 "d6a780" if girl else "79979c","799296","75909a"]),
                lambda v: blend(leg,knee,v,positions[knee][1],.091))
        surface([(.010,x,.062,.047,.097),(.023,x,.063,.062,.123),(.046,x,.061,.063,.123),
                 (.071,x,.056,.061,.112),(.103,x,.033,.055,.078),(.124,x,.007,.039,.046)],
                ["766653","bcab86","466862","5c7a6e","667e73"],lambda _:attached(foot))
        for z in (.067,.096,.123):
            oval(x,.099-z*.095,z,.041,.005,.006,"d5c8a4",foot,10)

    def gait(running):
        duty = .31 if running else .60
        stride = 1.49 if running else .86
        travel = duty*stride
        ankle = .097

        def smooth(t):
            t = min(1, max(0, t))
            return t*t*(3-2*t)

        def roll_height(pitch):
            # Lift the ankle just enough to keep the heel or toe on the ground.
            return (.158 if pitch > 0 else -.052) * math.sin(math.radians(pitch))

        def foot_target(t, flight):
            if t < duty:
                u = t/duty
                pitch = 0 if running else -14*(1-smooth(u/.25)) + 13*smooth((u-.72)/.28)
                return ankle+roll_height(pitch), stride*(duty*.5-t), pitch
            u=(t-duty)/(1-duty)
            hump = math.sin(math.pi*u)**2
            if running:
                # Preserve the planted foot's speed at toe-off and landing, with a short backward sweep.
                eased = u**3*(10+u*(-15+6*u))
                tangent = stride*(1-duty)*((1-u)*u**10-u*(1-u)**10)
                return (ankle+.186*hump+.026*flight, travel*(eased-.5)+tangent,
                        13*hump*math.sin(math.tau*u))
            eased=u*u*(3-2*u)
            tangent = -stride*(1-duty)*u*(1-u)*(1-2*u)
            pitch = 13-27*smooth(u)
            return ankle+roll_height(pitch)+.075*hump, travel*(eased-.5)+tangent, pitch

        frames=[]
        for i in range(64):
            phase=i/64
            samples=[(phase+.5*j)%1 for j in range(2)]
            cycle=math.tau*phase
            flight = 0
            margin = .026
            reach = THIGH+SHIN-.014
            hip_height = .533 - .006*math.cos(2*cycle-.38)
            if running:
                # Each step has a brief flight phase. Lift both feet and crest the hips midway through it.
                step = phase%.5
                flight_pos = max(0,(step-duty)/(.5-duty))
                flight = math.sin(math.pi*flight_pos)**3
                crest = 4*math.pi*(step-(.5+duty)/2)
                hip_height = .503 + .017*math.cos(crest)
                margin = .024
                reach = THIGH+SHIN-.025

            targets=[foot_target(t,flight) for t in samples]
            # Continuous reach constraint through lift-off and landing.
            for y,z,_ in targets:
                reachable = y+math.sqrt(max(.001,reach**2-z*z))
                blend = max(0, margin-abs(hip_height-reachable))/margin
                hip_height=min(hip_height,reachable)-blend*blend*margin/4
            angles=[[0,0,0] for _ in bones]
            angles[chest]=[16+1.8*math.sin(2*cycle) if running else 3+.65*math.sin(2*cycle),
                           (6 if running else 5)*math.cos(cycle),
                           (3.5 if running else 1.9)*math.sin(cycle)]
            angles[head]=[-8 if running else -1.5,-angles[chest][1]*.54,-angles[chest][2]*.68]
            for j,((arm,elbow,leg,knee,foot),(y,z,pitch),t) in enumerate(zip(limbs,targets,samples)):
                down=hip_height-y
                distance=min(THIGH+SHIN-.009,math.hypot(down,z))
                knee_flex=math.pi-math.acos((THIGH**2+SHIN**2-distance**2)/(2*THIGH*SHIN))
                thigh=-math.degrees(math.atan2(z,down)+math.acos(
                    (THIGH**2+distance**2-SHIN**2)/(2*THIGH*distance)))
                shin=math.degrees(knee_flex)
                angles[leg][0],angles[knee][0],angles[foot][0]=thigh,shin,pitch-thigh-shin
                pump=math.cos(math.tau*(t-.105))
                angles[arm]=[(34 if running else 19)*pump+(5 if running else 1),0,
                             (-1 if j==0 else 1)*(10 if running else 8)]
                angles[elbow][0]=(-74 if running else -13)+(9 if running else 7)*pump
            frames.append([round(hip_height-HIP_Y,4)]+[round(x,2) for row in angles for x in row])
        return {"stride":stride,"frames":[{"pose":row} for row in frames]}

    idle=[[0,0,0] for _ in bones]
    for j,(arm,elbow,*_) in enumerate(limbs):
        idle[arm]=[2,0,(-1 if j==0 else 1)*7]
        idle[elbow][0]=-7

    def guard_pose(phase, moving=False, sideways=False):
        hip_height = .515
        pose = [v.copy() for v in idle]
        rhythm = math.sin(math.tau * phase) if moving else 0
        pose[chest] = [9, 15 + 2 * rhythm, 1.5 * rhythm]
        pose[head] = [-4, -10, -rhythm]
        for i, (arm, elbow, thigh, knee, foot) in enumerate(limbs):
            sign = -1 if i == 0 else 1
            t = (phase + .5 * i) % 1
            duty = .67
            stride = .44 if sideways else .62
            if not moving:
                travel, lift = 0, 0
            elif t < duty:
                travel, lift = stride * (duty / 2 - t), 0
            else:
                u = (t-duty)/(1-duty)
                travel = stride * (duty * (u*u*(3-2*u) - .5) - (1-duty)*u*(1-u)*(1-2*u))
                lift = .049 * math.sin(math.pi*u)**2
            lateral = sign * .095 + (travel if sideways else 0)
            forward = -sign * .089 + (travel if not sideways else 0)
            vertical = hip_height-.096-lift
            down = math.hypot(vertical, lateral)
            distance = min(THIGH+SHIN-.008, math.hypot(forward, down))
            bend = math.pi-math.acos((THIGH**2+SHIN**2-distance**2)/(2*THIGH*SHIN))
            upper = -math.atan2(forward, down)-math.acos((THIGH**2+distance**2-SHIN**2)/(2*THIGH*distance))
            spread = math.degrees(math.atan2(lateral, vertical))
            pose[thigh] = [math.degrees(upper), 0, spread]
            pose[knee][0] = math.degrees(bend)
            pose[foot] = [-math.degrees(upper+bend), sign * 8, -spread]
            pose[arm] = [-44 + i*12 + 2*rhythm, sign*7, sign*19]
            pose[elbow][0] = -108 - i*6 + 3*rhythm
        return [round(hip_height-HIP_Y,4)]+[round(x,2) for row in pose for x in row]

    def strike(stick):
        # Normalized time, torso, striking arm, elbow, and the free counter-swinging arm.
        keys = ([(0, (0,0,0), (2,0,7), -7, 2),
                 (.28, (4,32,7), (-133,17,23), -75, 16),
                 (.48, (15,-12,-3), (-91,-12,7), -13, -35),
                 (.66, (20,-33,-7), (-48,-28,-9), -36, -19),
                 (.81, (7,-13,-2), (-27,-11,2), -49, -9),
                 (1, (0,0,0), (2,0,7), -7, 2)] if stick else
                [(0, (0,0,0), (2,0,7), -7, 2),
                 (.27, (-3,25,4), (18,12,25), -83, -24),
                 (.51, (12,-13,-4), (-82,-7,-7), -11, 18),
                 (.68, (16,-23,-7), (-66,-26,-15), -36, 11),
                 (.82, (6,-9,-2), (-23,-6,2), -36, 3),
                 (1, (0,0,0), (2,0,7), -7, 2)])
        duration = .59 if stick else .43
        left, left_elbow, *_ = limbs[0]
        right, right_elbow, *_ = limbs[1]
        frames = []
        for t, torso, arm, elbow, counter in keys:
            pose = [v.copy() for v in idle]
            pose[chest] = torso
            pose[head] = [-torso[0] * .45, -torso[1] * .47, -torso[2] * .6]
            pose[right] = arm
            pose[right_elbow][0] = elbow
            pose[left][0] = counter
            pose[left_elbow][0] = -7 - 17 * abs(counter - 2) / 37
            frames.append({"time":t,"pose":[0]+[round(x,2) for row in pose for x in row]})
        return {"stride":duration,"contact":keys[2][0]*duration,"frames":frames}

    def activity(kind):
        frames=[]
        for i in range(24):
            t=i*math.tau/24
            wave=math.sin(t)
            pose=[v.copy() for v in idle]
            la,le,*_=limbs[0]
            ra,re,*_=limbs[1]
            if kind == "water":
                pose[chest]=[12+4*wave,5,0]
                pose[head]=[10+4*wave,-3,0]
                pose[ra]=[-31-12*wave,0,9]
                pose[re][0]=-33+11*math.cos(t)
                pose[la][0]=-12
            elif kind == "sweep":
                pose[chest]=[14,13*wave,2]
                pose[head]=[10,-6*wave,0]
                pose[ra]=[-23+14*wave,11*wave,15]
                pose[re][0]=-20-5*wave
                pose[la]=[-42,4,-13]
                pose[le][0]=-38+8*wave
            elif kind == "reprimand":
                elapsed = i * 1.40 / 24
                lean = max(0, min(1, elapsed / .17, (1.32 - elapsed) / .24))
                nearest = min(abs(elapsed - hit) for hit in (.30, .62, .94))
                swing = max(0, 1 - nearest / .12) ** 2
                pose[chest] = [43 * lean, (12 - 20 * swing) * lean, -3 * lean]
                pose[head][0] = -21 * lean
                pose[ra] = [-23 * lean - 68 * swing, 0, (17 - 30 * swing) * lean]
                pose[re][0] = -15 * lean - 17 * (1 - swing) * lean
                pose[la][0] = -21 * lean
                pose[le][0] = -21 * lean
                for _, _, thigh, knee, foot in limbs:
                    pose[thigh][0] = -42 * lean
                    pose[knee][0] = 84 * lean
                    pose[foot][0] = -42 * lean
            else:
                pose[chest][1]=4*wave
                pose[head][2]=6*wave
                pose[ra]=[-16+10*wave,0,12]
                pose[re][0]=-53+13*wave
            lift = -.13 * lean if kind == "reprimand" else 0
            frames.append({"pose":[round(lift, 4)]+[round(x,2) for row in pose for x in row]})
        duration = {"water": 2.45, "reprimand": 1.40}.get(kind, 1.35)
        return {"stride":duration,"frames":frames}

    def crouch_pose(phase, moving):
        hip_height=.401
        pose=[v.copy() for v in idle]
        pose[chest]=[24,3*math.sin(math.tau*phase) if moving else 0,0]
        pose[head][0]=-18
        for i, (arm,elbow,leg,knee,foot) in enumerate(limbs):
            t=(phase+.5*i)%1
            z=.035 if i==0 else -.035
            y=.097
            if moving:
                duty=.63
                travel=.66*duty
                if t<duty:
                    z=travel*(.5-t/duty)
                else:
                    u=(t-duty)/(1-duty)
                    z=travel*(u*u*(3-2*u)-.5)-.66*(1-duty)*u*(1-u)*(1-2*u)
                    y+=.064*math.sin(math.pi*u)**2
            down=hip_height-y
            distance=math.hypot(down,z)
            shin=math.pi-math.acos((THIGH**2+SHIN**2-distance**2)/(2*THIGH*SHIN))
            thigh=-math.atan2(z,down)-math.acos((THIGH**2+distance**2-SHIN**2)/(2*THIGH*distance))
            pose[leg][0]=math.degrees(thigh)
            pose[knee][0]=math.degrees(shin)
            pose[foot][0]=-math.degrees(thigh+shin)
            pose[arm][0]=-12+(13*math.cos(math.tau*t) if moving else 0)
            pose[elbow][0]=-28
        return [round(hip_height-HIP_Y,4)]+[round(x,2) for row in pose for x in row]

    def leap(vault):
        if vault:
            keys=[(0,0,0,0,0,0),(-.07,28,-63,38,57,62),
                  (-.035,54,-96,57,99,105),(-.035,31,-49,73,57,86),
                  (-.09,19,-25,36,56,58),(0,0,0,0,0,0)]
        else:
            keys=[(0,0,0,0,0,0),(-.065,18,23,30,55,45),
                  (-.01,11,-86,30,76,59),(-.025,7,-45,42,36,38),
                  (-.08,17,-20,35,61,58),(0,0,0,0,0,0)]
        frames=[]
        for lift,lean,arms,left,right,bend in keys:
            pose=[v.copy() for v in idle]
            pose[chest][0]=lean
            pose[head][0]=-lean*.64
            for j,(arm,elbow,leg,knee,foot) in enumerate(limbs):
                pose[arm][0]=arms+(13 if vault and j==0 else 0)
                pose[elbow][0]=-bend*.62
                pose[leg][0]=-(left if not j else right)
                pose[knee][0]=bend
                pose[foot][0]=-bend*.42
            frames.append({"pose":[lift]+[round(x,2) for row in pose for x in row]})
        return {"stride":1,"frames":frames}

    down = [v.copy() for v in idle]
    down[hips][2] = -86
    down[chest] = [18,8,0]
    down[head] = [17,-18,6]
    for side,(arm,elbow,leg,knee,foot) in zip((-1,1),limbs):
        down[arm] = [-76 if side>0 else -46,side*18,side*7]
        down[elbow][0] = -93 if side>0 else -76
        down[leg][0] = -39
        down[knee][0] = 69
        down[foot][0] = -25

    rig = None
    if variant == PLAYER:
        rig = {"bones":bones,"idle":[0]+[x for row in idle for x in row],
               "walk":gait(False),"run":gait(True),"walkSpeed":1.68,"runSpeed":3.76,
               "crouchIdle":crouch_pose(0,False),"crouchSpeed":.88,
               "downPose":[-.354]+[x for row in down for x in row],
               "jump":leap(False),"vault":leap(True),
               "palmStrike":strike(False),"stickStrike":strike(True),
               "guardIdle":guard_pose(0),
               "guardWalk":{"stride":.62,"frames":[{"pose":guard_pose(i/64, True)} for i in range(64)]},
               "guardSide":{"stride":.44,"frames":[{"pose":guard_pose(i/64, True, True)} for i in range(64)]},
               "crouch":{"stride":.66,"frames":[{"pose":crouch_pose(i/48,True)} for i in range(48)]},
               **{kind:activity(kind) for kind in ("water","sweep","talk","reprimand")}}
    return mesh, rig
